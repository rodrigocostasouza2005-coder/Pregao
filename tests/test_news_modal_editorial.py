# -*- coding: utf-8 -*-
"""Testes da FASE C (modal editorial de NEWS, 2026-10-09) - pipeline
completo de _gerar_resumo_grupo com o formato novo (RESUMO em parágrafos +
LEITURA DE MERCADO opcional, ver data/news.py:_PROMPT_SISTEMA_RESUMO)
cobrindo os 5 cenários pedidos pelo Rodrigo:

1. matéria com texto completo disponível (fonte única, com imagem)
2. matéria só com manchete/snippet (todas as fontes bloquearam o texto)
3. notícia sem imagem (texto ok, og:image ausente)
4. falha de extração (download/decode quebrou)
5. matéria com números relevantes (fidelidade do resumo preserva o dado)

Mais a checagem de que IMAGEM nunca é trocada entre matérias diferentes
(correspondência imagem-matéria) quando duas chamadas distintas de
_gerar_resumo_grupo acontecem em sequência (nunca compartilham estado).

Groq (_chamar_groq) e extração (_extrair_texto_artigo) são mockados -
nenhuma chamada de rede nem custo de API. Uso:
python tests/test_news_modal_editorial.py (python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.news as news_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        # 2026-10-10: faz a checagem REALMENTE falhar sob pytest (antes so'
        # imprimia e guardava em _FALHAS, lido so' pelo runner `__main__` -
        # sob pytest toda funcao test_* passava mesmo com condicao=False,
        # a menos que outra linha lancasse excecao por acidente; ver
        # investigacao registrada no relatorio da auditoria 2026-10-10)
        raise AssertionError(f"{nome} {detalhe}".strip())


_RESUMO_EDITORIAL_FAKE = (
    "RESUMO:\n"
    "A empresa Alfa anunciou revisão do plano de investimentos para 2027, "
    "citando queda no preço de referência da commodity.\n\n"
    "Segundo o comunicado, o capex previsto cai de R$ 12 bilhões para "
    "R$ 9,5 bilhões, e o projeto Beta foi postergado em 8 meses.\n\n"
    "LEITURA DE MERCADO:\n"
    "A revisão pode pressionar a margem do setor no curto prazo, a depender "
    "do próximo balanço trimestral."
)


# ============================================================
# 1. texto completo disponível (fonte única, com imagem) - caminho feliz
# ============================================================

def test_1a_texto_completo_gera_resumo_editorial_nao_parcial_com_imagem():
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("Texto longo o suficiente extraído da matéria real, com bastante conteúdo jornalístico pra render um resumo completo de verdade.",
                                     "https://veiculo.com/foto-alfa.jpg", "https://veiculo.com/materia-alfa", None)), \
         patch.object(news_mod, "_chamar_groq", return_value=(_RESUMO_EDITORIAL_FAKE, None)):
        resultado = news_mod._gerar_resumo_grupo(
            "Alfa revisa plano de investimentos",
            (("InfoMoney", "https://news.google.com/alfa"),),
            ("Alfa revisa plano de investimentos",),
        )
    _checar("1a resumo gerado", bool(resultado["resumo"]))
    _checar("1b parcial=False (texto completo, não é síntese de manchete)", resultado.get("parcial") is False)
    _checar("1c imagem da PRÓPRIA matéria (nunca de outra)", resultado["imagem"] == "https://veiculo.com/foto-alfa.jpg")
    _checar("1d link_original preservado", resultado["link_original"] == "https://veiculo.com/materia-alfa")

    paragrafos, leitura = news_mod.separar_secoes_resumo(resultado["resumo"])
    _checar("1e 2 parágrafos no corpo do resumo", len(paragrafos) == 2)
    _checar("1f leitura de mercado presente", leitura is not None)


# ============================================================
# 2. só manchete/snippet disponível (todas as fontes bloquearam o texto)
# ============================================================

def test_2a_so_manchetes_gera_resumo_parcial_sem_imagem():
    resumo_manchetes = (
        "RESUMO:\n"
        "Fontes diferentes reportam que a empresa Beta anunciou mudança na diretoria."
    )
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=(None, None, "https://veiculo.com/materia-beta", "conteúdo muito curto (provável paywall/bloqueio)")), \
         patch.object(news_mod, "_chamar_groq", return_value=(resumo_manchetes, None)):
        resultado = news_mod._gerar_resumo_grupo(
            "Beta troca diretoria",
            (("Valor", "https://news.google.com/beta1"), ("Estadão", "https://news.google.com/beta2")),
            ("Beta troca diretoria", "Beta anuncia novo CEO"),
        )
    _checar("2a resumo ainda sai (fallback manchetes)", bool(resultado["resumo"]))
    _checar("2b parcial=True (síntese só com manchetes, nunca finge texto completo)", resultado.get("parcial") is True)
    _checar("2c imagem None (nunca atribui foto de UMA fonte ao grupo sintetizado por manchetes)", resultado["imagem"] is None)


def test_2b_so_1_titulo_sem_texto_nenhum_nao_tenta_manchetes():
    """Com só 1 título no grupo, não há o que sintetizar a partir de
    'manchetes de fontes diferentes' - desiste sem chamar o Groq de novo."""
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=(None, None, "https://veiculo.com/materia-gama", "erro ao baixar: timeout")), \
         patch.object(news_mod, "_chamar_groq") as mock_groq:
        resultado = news_mod._gerar_resumo_grupo(
            "Gama anuncia resultado",
            (("InfoMoney", "https://news.google.com/gama"),),
            ("Gama anuncia resultado",),
        )
    _checar("2d sem resumo (só 1 fonte, sem texto)", resultado["resumo"] is None)
    _checar("2e motivo cita a falha real de download", "erro ao baixar" in (resultado["motivo_indisponivel"] or ""))
    _checar("2f nunca chama o Groq sem ter nem texto nem manchetes extras", mock_groq.call_count == 0)


# ============================================================
# 3. notícia sem imagem (texto ok, og:image ausente)
# ============================================================

def test_3a_texto_completo_sem_og_image_nunca_inventa_imagem():
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("Texto longo o suficiente extraído da matéria real, com conteúdo jornalístico suficiente pra resumir.",
                                     None, "https://veiculo.com/materia-delta", None)), \
         patch.object(news_mod, "_chamar_groq", return_value=("RESUMO:\nDelta anunciou resultado trimestral acima do esperado.", None)):
        resultado = news_mod._gerar_resumo_grupo(
            "Delta supera estimativas",
            (("InfoMoney", "https://news.google.com/delta"),),
            ("Delta supera estimativas",),
        )
    _checar("3a resumo gerado mesmo sem imagem", bool(resultado["resumo"]))
    _checar("3b imagem None (nunca inventa/completa uma foto)", resultado["imagem"] is None)
    _checar("3c parcial=False (ainda é texto completo, só não tem foto)", resultado.get("parcial") is False)


# ============================================================
# 4. falha de extração (download/decode quebrou em TODAS as fontes)
# ============================================================

def test_4a_falha_total_de_extracao_sem_fallback_de_manchete_suficiente():
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=(None, None, None, "não foi possível resolver o link original")), \
         patch.object(news_mod, "_chamar_groq") as mock_groq:
        resultado = news_mod._gerar_resumo_grupo(
            "Épsilon noticiada",
            (("Suno", "https://news.google.com/epsilon"),),
            ("Épsilon noticiada",),
        )
    _checar("4a sem resumo (falha total, 1 título só)", resultado["resumo"] is None)
    _checar("4b motivo explica a falha de decode", "resolver o link" in (resultado["motivo_indisponivel"] or ""))
    _checar("4c imagem None", resultado["imagem"] is None)
    _checar("4d nunca chama Groq sem conteúdo nenhum pra resumir", mock_groq.call_count == 0)


def test_4b_falha_de_cota_do_groq_desiste_sem_tentar_as_outras_fontes():
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("Texto suficientemente longo extraído com sucesso da primeira fonte do grupo pra passar do limite mínimo.",
                                     "https://veiculo.com/foto.jpg", "https://veiculo.com/materia", None)) as mock_extrair, \
         patch.object(news_mod, "_chamar_groq", return_value=(None, "cota")):
        resultado = news_mod._gerar_resumo_grupo(
            "Zeta noticiada",
            (("Fonte1", "https://news.google.com/zeta1"), ("Fonte2", "https://news.google.com/zeta2")),
            ("Zeta noticiada",),
        )
    _checar("4e falha de cota propaga motivo_indisponivel='cota'", resultado["motivo_indisponivel"] == "cota")
    _checar("4f desiste na primeira fonte (falha da IA, não da fonte - tentar outra repetiria o erro)", mock_extrair.call_count == 1)


# ============================================================
# 5. matéria com números relevantes - fidelidade do resumo
# ============================================================

def test_5a_numeros_da_fonte_chegam_intactos_ao_prompt_da_ia():
    """Não dá pra testar o que a IA real responde (mock) - mas dá pra
    garantir que o texto COM os números da fonte chega intacto no prompt
    enviado ao Groq (_resumir_com_groq), nunca truncado antes do número
    nem resumido por conta própria antes de chegar na IA."""
    texto_com_numeros = (
        "A companhia reportou lucro líquido de R$ 2,3 bilhões no trimestre, "
        "alta de 18% em relação ao ano anterior. A receita somou R$ 14,7 "
        "bilhões, com margem EBITDA de 32,4%."
    )
    prompts_recebidos = []

    def _fake_chamar_groq(prompt_sistema, prompt_usuario):
        prompts_recebidos.append(prompt_usuario)
        return _RESUMO_EDITORIAL_FAKE, None

    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=(texto_com_numeros, "https://veiculo.com/foto.jpg", "https://veiculo.com/materia", None)), \
         patch.object(news_mod, "_chamar_groq", side_effect=_fake_chamar_groq):
        news_mod._gerar_resumo_grupo(
            "Companhia reporta lucro",
            (("InfoMoney", "https://news.google.com/lucro"),),
            ("Companhia reporta lucro",),
        )
    _checar("5a prompt enviado à IA contém o número de lucro intacto", "R$ 2,3 bilhões" in prompts_recebidos[0])
    _checar("5b prompt enviado à IA contém a margem EBITDA intacta", "32,4%" in prompts_recebidos[0])


def test_5b_separar_secoes_preserva_numeros_do_resumo_gerado():
    bruto = (
        "RESUMO:\n"
        "A companhia reportou lucro líquido de R$ 2,3 bilhões no trimestre, "
        "alta de 18% em relação ao ano anterior."
    )
    paragrafos, _ = news_mod.separar_secoes_resumo(bruto)
    _checar("5c número preservado ao separar seções (nunca perdido no parsing)", "R$ 2,3 bilhões" in paragrafos[0])
    _checar("5d percentual preservado", "18%" in paragrafos[0])


# ============================================================
# 6. correspondência imagem-matéria entre 2 chamadas distintas em sequência
# ============================================================

def test_6a_imagens_de_grupos_diferentes_nunca_se_misturam():
    def _fake_extrair(link):
        if "grupo-a" in link:
            return ("Texto da matéria A, longo o suficiente pra passar do limite mínimo de extração exigido.",
                    "https://veiculo.com/foto-A.jpg", "https://veiculo.com/materia-a", None)
        return ("Texto da matéria B, também longo o suficiente pra passar do limite mínimo exigido pelo extrator.",
                "https://veiculo.com/foto-B.jpg", "https://veiculo.com/materia-b", None)

    with patch.object(news_mod, "_extrair_texto_artigo", side_effect=_fake_extrair), \
         patch.object(news_mod, "_chamar_groq", return_value=("RESUMO:\nResumo qualquer, só pra validar a imagem associada.", None)):
        resultado_a = news_mod._gerar_resumo_grupo("Matéria A", (("Fonte", "https://news.google.com/grupo-a"),), ("Matéria A",))
        resultado_b = news_mod._gerar_resumo_grupo("Matéria B", (("Fonte", "https://news.google.com/grupo-b"),), ("Matéria B",))

    _checar("6a imagem do grupo A é a foto A", resultado_a["imagem"] == "https://veiculo.com/foto-A.jpg")
    _checar("6b imagem do grupo B é a foto B (nunca a do grupo A)", resultado_b["imagem"] == "https://veiculo.com/foto-B.jpg")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass  # ja' registrado em _FALHAS por _checar

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DO MODAL EDITORIAL DE NEWS (FASE C) PASSARAM")
