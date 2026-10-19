# -*- coding: utf-8 -*-
"""Testes do redesign editorial do card de NEWS (2026-10-19, pedido do
Rodrigo: resumo "visualmente ruim" e sem análise suficientemente útil).

Cobre a camada de DADOS (data/news.py):
1. extrair_por_que_importa - bloco novo opcional (relevância econômica/
   financeira), com a MESMA disciplina de "nunca força seção sem
   evidência" já usada pra LEITURA DE MERCADO (_leitura_sem_base).
2. separar_secoes_resumo continua ignorando o bloco POR QUE IMPORTA (não
   deixa esse texto vazar pra dentro de "paragrafos") - garantia crítica
   pra não quebrar data/morning_call_editorial.py, que reusa esta MESMA
   função numa sessão paralela (PR #84) sem saber do bloco novo.
3. Formato antigo (resumo já cacheado antes desta mudança, sem o
   marcador POR QUE IMPORTA) continua funcionando sem nenhuma migração -
   ver data/ia_cache.py:_VERSAO_CHAVE_NEWS (bump v4->v5 força
   reprocessamento 1x por grupo, nunca quebra o que já está cacheado).
4. _sanitizar_por_que_importa - o bloco novo passa pelos MESMOS gates de
   qualidade do bloco RESUMO (genérico/causalidade sem evidência); se
   reprovar, só a seção é removida, nunca o resumo inteiro.
5. _gerar_resumo_grupo (fim a fim, Groq mockado) com os 3 blocos.

Groq e extração de matéria são mockados - nenhuma chamada real de rede
nem de IA (sem GROQ_API_KEY disponível neste ambiente - ver relatório
final sobre o que depende de validação em produção).

Uso: pytest tests/test_news_resumo_editorial_v5.py (venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.news as news_mod
import data.ia_cache as ia_cache_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


# ============================================================
# 1. extrair_por_que_importa
# ============================================================

def test_1a_bloco_presente_e_extraido():
    bruto = (
        "RESUMO:\nA empresa Alfa anunciou corte no capex de 2027.\n\n"
        "POR QUE IMPORTA:\nA Alfa responde por 8% do índice setorial, então "
        "um corte desse porte tende a pesar na média do setor.\n\n"
        "LEITURA DE MERCADO:\nO movimento pode sinalizar cautela do setor "
        "como um todo, a depender do próximo balanço trimestral."
    )
    importa = news_mod.extrair_por_que_importa(bruto)
    _checar("1a bloco POR QUE IMPORTA extraído", importa is not None)
    _checar("1b conteúdo correto (não mistura com RESUMO/LEITURA)",
            importa == "A Alfa responde por 8% do índice setorial, então "
                       "um corte desse porte tende a pesar na média do setor.")


def test_1b_bloco_no_fim_sem_leitura_de_mercado_depois():
    bruto = (
        "RESUMO:\nA empresa Beta reportou lucro acima do esperado.\n\n"
        "POR QUE IMPORTA:\nO resultado é relevante porque a Beta é a maior "
        "do setor em valor de mercado."
    )
    importa = news_mod.extrair_por_que_importa(bruto)
    _checar("1c bloco no fim do texto (sem LEITURA depois) também é extraído",
            importa == "O resultado é relevante porque a Beta é a maior do setor em valor de mercado.")


def test_1c_sem_marcador_formato_antigo_retorna_none():
    """Resumo já cacheado ANTES desta mudança (2026-10-19) nunca tem o
    marcador POR QUE IMPORTA - extrair_por_que_importa precisa devolver
    None sem quebrar, nunca inventar um bloco que o modelo não gerou."""
    bruto = (
        "RESUMO:\nA empresa Gama anunciou fusão com a Delta.\n\n"
        "LEITURA DE MERCADO:\nA fusão pode criar sinergias operacionais."
    )
    _checar("1d formato antigo (só RESUMO/LEITURA) -> None", news_mod.extrair_por_que_importa(bruto) is None)


def test_1d_campo_vazio_ou_curto_demais_vira_none():
    """Mesma disciplina de _leitura_sem_base: o modelo as vezes escreve
    'não informado' em vez de OMITIR o bloco - tratado como ausente."""
    bruto1 = "RESUMO:\nTexto qualquer.\n\nPOR QUE IMPORTA:\nnão informado"
    bruto2 = "RESUMO:\nTexto qualquer.\n\nPOR QUE IMPORTA:\ncurto"
    _checar("1e 'não informado' -> None", news_mod.extrair_por_que_importa(bruto1) is None)
    _checar("1f texto curto demais -> None", news_mod.extrair_por_que_importa(bruto2) is None)


def test_1e_vazio_ou_none_nunca_quebra():
    _checar("1g string vazia -> None", news_mod.extrair_por_que_importa("") is None)
    _checar("1h None -> None", news_mod.extrair_por_que_importa(None) is None)


# ============================================================
# 2. separar_secoes_resumo continua ignorando o bloco novo
#    (garantia de compatibilidade com data/morning_call_editorial.py)
# ============================================================

def test_2a_paragrafos_nunca_incluem_o_texto_de_por_que_importa():
    bruto = (
        "RESUMO:\nA empresa Alfa anunciou corte no capex de 2027.\n\n"
        "POR QUE IMPORTA:\nA Alfa responde por 8% do índice setorial.\n\n"
        "LEITURA DE MERCADO:\nO movimento pode sinalizar cautela do setor."
    )
    paragrafos, leitura = news_mod.separar_secoes_resumo(bruto)
    texto_paragrafos = " ".join(paragrafos)
    _checar("2a corpo não contém o texto de POR QUE IMPORTA",
            "índice setorial" not in texto_paragrafos, f"(paragrafos={paragrafos!r})")
    _checar("2b corpo contém o texto correto do RESUMO",
            "corte no capex" in texto_paragrafos)
    _checar("2c leitura de mercado ainda corretamente extraída (não afetada)",
            leitura == "O movimento pode sinalizar cautela do setor.")


def test_2b_sem_leitura_depois_do_por_que_importa_tambem_funciona():
    bruto = (
        "RESUMO:\nA empresa Beta reportou lucro acima do esperado.\n\n"
        "POR QUE IMPORTA:\nA Beta é a maior do setor em valor de mercado."
    )
    paragrafos, leitura = news_mod.separar_secoes_resumo(bruto)
    _checar("2d corpo não inclui o bloco POR QUE IMPORTA",
            "maior do setor" not in " ".join(paragrafos))
    _checar("2e leitura None (não havia bloco LEITURA)", leitura is None)
    _checar("2f corpo preserva o conteúdo do RESUMO", "lucro acima do esperado" in " ".join(paragrafos))


def test_2c_formato_antigo_sem_marcador_novo_e_100pct_compativel():
    """Garantia central de não-regressão: resumo no formato EXATO de
    antes desta mudança continua produzindo o MESMO resultado de
    separar_secoes_resumo - Morning Call (PR #84, sessão paralela) nunca
    pode ver nenhuma mudança de comportamento aqui."""
    bruto = (
        "RESUMO:\nA empresa Gama anunciou fusão com a Delta.\n\n"
        "LEITURA DE MERCADO:\nA fusão pode criar sinergias operacionais."
    )
    paragrafos, leitura = news_mod.separar_secoes_resumo(bruto)
    _checar("2g formato antigo: 1 parágrafo", paragrafos == ["A empresa Gama anunciou fusão com a Delta."])
    _checar("2h formato antigo: leitura preservada", leitura == "A fusão pode criar sinergias operacionais.")


# ============================================================
# 3. _sanitizar_por_que_importa - gates de qualidade do bloco novo
# ============================================================

def test_3a_bloco_generico_e_removido_sem_descartar_o_resto():
    titulo = "Petrobras revisa plano de investimentos"
    bruto = (
        "RESUMO:\nA companhia reduziu o capex previsto de 2027 de R$ 12 "
        "bilhões para R$ 9,5 bilhões, segundo o comunicado.\n\n"
        "POR QUE IMPORTA:\nO mercado segue atento aos próximos movimentos "
        "da companhia.\n\n"
        "LEITURA DE MERCADO:\nA revisão pode pressionar fornecedores do "
        "setor, a depender do cronograma revisado."
    )
    sanitizado = news_mod._sanitizar_por_que_importa(bruto, titulo, "texto fonte qualquer")
    _checar("3a bloco genérico removido", news_mod.extrair_por_que_importa(sanitizado) is None)
    paragrafos, leitura = news_mod.separar_secoes_resumo(sanitizado)
    _checar("3b RESUMO preservado intacto", "R$ 9,5 bilhões" in " ".join(paragrafos))
    _checar("3c LEITURA DE MERCADO preservada intacta", leitura is not None and "fornecedores" in leitura)


def test_3b_bloco_com_causalidade_sem_evidencia_e_removido():
    titulo = "Alfa anuncia resultado trimestral"
    texto_fonte = "A Alfa reportou lucro de R$ 500 milhões no trimestre."
    bruto = (
        "RESUMO:\nA Alfa reportou lucro de R$ 500 milhões no trimestre.\n\n"
        "POR QUE IMPORTA:\nIsso importa por causa de pesquisas eleitorais "
        "recentes sobre o setor."
    )
    sanitizado = news_mod._sanitizar_por_que_importa(bruto, titulo, texto_fonte)
    _checar("3d bloco com causalidade sem base no texto-fonte é removido",
            news_mod.extrair_por_que_importa(sanitizado) is None)
    paragrafos, _ = news_mod.separar_secoes_resumo(sanitizado)
    _checar("3e RESUMO preservado", "R$ 500 milhões" in " ".join(paragrafos))


def test_3c_bloco_bom_e_preservado():
    titulo = "Alfa anuncia resultado trimestral"
    texto_fonte = "A Alfa reportou lucro de R$ 500 milhões, 8% do setor bancário."
    bruto = (
        "RESUMO:\nA Alfa reportou lucro de R$ 500 milhões no trimestre.\n\n"
        "POR QUE IMPORTA:\nA Alfa representa 8% do setor bancário, então o "
        "resultado tem peso relevante na média do setor."
    )
    sanitizado = news_mod._sanitizar_por_que_importa(bruto, titulo, texto_fonte)
    _checar("3f bloco bom (apoiado no texto-fonte) é preservado",
            news_mod.extrair_por_que_importa(sanitizado) is not None)


def test_3d_sem_bloco_nenhum_devolve_o_resumo_sem_mudanca():
    bruto = "RESUMO:\nTexto qualquer sem o bloco novo."
    sanitizado = news_mod._sanitizar_por_que_importa(bruto, "Título qualquer", "texto fonte")
    _checar("3g sem bloco POR QUE IMPORTA -> resumo devolvido sem mudança", sanitizado == bruto)


# ============================================================
# 4. _gerar_resumo_grupo fim a fim (Groq mockado) com os 3 blocos
# ============================================================

_RESUMO_COM_3_BLOCOS = (
    "RESUMO:\n"
    "A empresa Alfa anunciou revisão do plano de investimentos para 2027, "
    "citando queda no preço de referência da commodity. O capex previsto "
    "cai de R$ 12 bilhões para R$ 9,5 bilhões.\n\n"
    "POR QUE IMPORTA:\n"
    "A Alfa responde por 15% da produção nacional da commodity, então um "
    "corte desse porte tende a influenciar a oferta agregada do setor.\n\n"
    "LEITURA DE MERCADO:\n"
    "A revisão pode pressionar a margem de fornecedores da Alfa no curto "
    "prazo, a depender do cronograma de pagamentos revisado."
)


def test_4a_resumo_com_3_blocos_chega_intacto_no_resultado():
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("Texto longo o suficiente extraído da matéria real, com conteúdo "
                                     "jornalístico de verdade pra passar do limite mínimo de extração.",
                                     None, "https://veiculo.com/materia-alfa", None)), \
         patch.object(news_mod, "_chamar_groq", return_value=(_RESUMO_COM_3_BLOCOS, None)):
        resultado = news_mod._gerar_resumo_grupo(
            "Alfa revisa plano de investimentos",
            (("InfoMoney", "https://news.google.com/alfa"),),
            ("Alfa revisa plano de investimentos",),
        )
    _checar("4a resumo gerado", bool(resultado["resumo"]))
    paragrafos, leitura = news_mod.separar_secoes_resumo(resultado["resumo"])
    importa = news_mod.extrair_por_que_importa(resultado["resumo"])
    _checar("4b bloco RESUMO preservado", "R$ 9,5 bilhões" in " ".join(paragrafos))
    _checar("4c bloco POR QUE IMPORTA preservado (fonte boa, não genérico)", importa is not None and "15%" in importa)
    _checar("4d bloco LEITURA DE MERCADO preservado", leitura is not None and "fornecedores" in leitura)


def test_4b_por_que_importa_ruim_e_removido_mas_resumo_ainda_sai():
    resumo_com_importa_generico = (
        "RESUMO:\nA empresa Beta reportou lucro líquido de R$ 500 milhões no "
        "trimestre, alta de 18% em relação ao ano anterior.\n\n"
        "POR QUE IMPORTA:\nÉ importante acompanhar os próximos movimentos da "
        "companhia no mercado."
    )
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("Texto longo o suficiente extraído da matéria real, com conteúdo "
                                     "jornalístico de verdade pra passar do limite mínimo de extração.",
                                     None, "https://veiculo.com/materia-beta", None)), \
         patch.object(news_mod, "_chamar_groq", return_value=(resumo_com_importa_generico, None)):
        resultado = news_mod._gerar_resumo_grupo(
            "Beta reporta lucro",
            (("InfoMoney", "https://news.google.com/beta"),),
            ("Beta reporta lucro",),
        )
    _checar("4e resumo ainda sai (não descarta o todo por causa do bloco ruim)", bool(resultado["resumo"]))
    _checar("4f bloco POR QUE IMPORTA genérico foi removido",
            news_mod.extrair_por_que_importa(resultado["resumo"]) is None)
    paragrafos, _ = news_mod.separar_secoes_resumo(resultado["resumo"])
    _checar("4g RESUMO preservado intacto", "R$ 500 milhões" in " ".join(paragrafos))


def test_4c_fallback_manchetes_tambem_passa_pela_sanitizacao():
    resumo_manchetes_com_importa_generico = (
        "RESUMO:\nFontes diferentes reportam que a empresa Zeta anunciou "
        "mudança na diretoria.\n\n"
        "POR QUE IMPORTA:\nVale a pena acompanhar de perto os próximos passos."
    )
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=(None, None, "https://veiculo.com/materia-zeta", "conteúdo muito curto")), \
         patch.object(news_mod, "_chamar_groq", return_value=(resumo_manchetes_com_importa_generico, None)):
        resultado = news_mod._gerar_resumo_grupo(
            "Zeta troca diretoria",
            (("Valor", "https://news.google.com/zeta1"), ("Estadão", "https://news.google.com/zeta2")),
            ("Zeta troca diretoria", "Zeta anuncia novo CEO"),
        )
    _checar("4h resumo via fallback de manchetes ainda sai", bool(resultado["resumo"]))
    _checar("4i bloco POR QUE IMPORTA genérico removido também no caminho de fallback",
            news_mod.extrair_por_que_importa(resultado["resumo"]) is None)


# ============================================================
# 5. cache (versão/chave) - bump v4 -> v5
# ============================================================

def test_5a_versao_da_chave_de_cache_foi_atualizada():
    _checar("5a _VERSAO_CHAVE_NEWS é 'v5' (novo formato editorial)",
            ia_cache_mod._VERSAO_CHAVE_NEWS == "v5", f"(valor atual={ia_cache_mod._VERSAO_CHAVE_NEWS!r})")


def test_5b_chave_muda_em_relacao_a_versao_anterior():
    """Garante que um resumo cacheado sob v4 (prompt antigo, sem o bloco
    POR QUE IMPORTA) nunca é servido como se já tivesse o formato novo -
    bump de versão força 1 regeneração por grupo, igual ao padrão
    v1->v2->v3->v4 já usado neste módulo."""
    titulo = "Alfa revisa plano de investimentos"
    links = ("https://veiculo.com/materia-alfa",)
    chave_v5 = ia_cache_mod.chave_news(titulo, links)
    chave_v4_simulada = hashlib_sha256_v4(titulo, links)
    _checar("5b chave v5 difere da chave que seria gerada sob v4",
            chave_v5 != chave_v4_simulada)


def hashlib_sha256_v4(titulo: str, links: tuple) -> str:
    import hashlib
    identidade = "v4" + "|" + titulo.strip().lower() + "|" + "|".join(sorted(links))
    return hashlib.sha256(identidade.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DO REDESIGN EDITORIAL DE NEWS (v5) PASSARAM")
