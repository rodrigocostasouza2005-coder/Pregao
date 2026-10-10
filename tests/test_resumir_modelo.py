# -*- coding: utf-8 -*-
"""Testes do achado real (FASE 8, 2026-10-08): a coluna "modelo" do
cache global de IA (data/ia_cache.py:resumos_ia_cache) ficava SEMPRE
vazia porque nem data/research/resumir.py nem data/news.py incluiam a
chave "modelo" no dict retornado pra ia_cache.obter_resumo_com_cache -
mesmo o PRINCIPAL ja calculando internamente qual dos 2 modelos (
principal/fallback) de fato gerou o resumo (usou_fallback, antes
descartado com '_'). Corrigido SEM NUNCA presumir: o modelo reportado e'
sempre o que RESPONDEU de verdade (principal OU fallback, nunca
assumido), e None quando essa informacao genuinamente nao existir.

Mocka _chamar_groq (nivel mais baixo) e config - nunca faz chamada de
rede/API real. Uso: python tests/test_resumir_modelo.py (venv)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.resumir as resumir_mod
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


# ============================================================
# RESEARCH (data/research/resumir.py) - tem fallback de modelo real
# ============================================================

def test_1_modelo_principal_quando_responde_de_primeira():
    def _fake_chamar_groq(chave, modelo, mensagens, max_tokens):
        return ("Resumo gerado com sucesso.", None) if modelo == "modelo-principal" else (None, "nao deveria chamar o fallback")

    with patch.object(resumir_mod.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(resumir_mod.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(resumir_mod, "_chamar_groq", side_effect=_fake_chamar_groq):
        resumo, motivo, dados = resumir_mod.resumir_com_groq("texto curto de teste", "Titulo de teste")
    _checar("1a resumo gerado normalmente", resumo is not None)
    _checar("1b 'modelo' reportado e' o PRINCIPAL (respondeu de primeira, sem fallback)",
            dados.get("modelo") == "modelo-principal", f"(dados={dados})")


def test_2_modelo_fallback_quando_principal_falha():
    def _fake_chamar_groq(chave, modelo, mensagens, max_tokens):
        if modelo == "modelo-principal":
            return None, "erro de rede"
        return "Resumo gerado pelo fallback.", None

    with patch.object(resumir_mod.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(resumir_mod.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(resumir_mod, "_chamar_groq", side_effect=_fake_chamar_groq):
        resumo, motivo, dados = resumir_mod.resumir_com_groq("texto curto de teste", "Titulo de teste")
    _checar("2a resumo gerado (pelo fallback)", resumo is not None)
    _checar("2b 'modelo' reportado e' o FALLBACK (nao o principal, que de fato falhou) - achado real corrigido",
            dados.get("modelo") == "modelo-fallback", f"(dados={dados})")


def test_3_sem_resumo_nenhum_modelo_e_reportado():
    with patch.object(resumir_mod.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(resumir_mod.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(resumir_mod, "_chamar_groq", return_value=(None, "erro de rede")):
        resumo, motivo, dados = resumir_mod.resumir_com_groq("texto curto de teste", "Titulo de teste")
    _checar("3a sem resumo (os 2 modelos falharam)", resumo is None)
    _checar("3b dados_estruturados vazio (nenhum 'modelo' chutado pra uma geracao que nao aconteceu)",
            dados == {}, f"(dados={dados})")


def test_4_gerar_resumo_usa_o_modelo_real_no_store_e_no_retorno():
    doc_salvo = []
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=("texto do relatorio", None)), \
         patch.object(resumir_mod.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(resumir_mod.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(resumir_mod, "_chamar_groq",
                      side_effect=lambda chave, modelo, mensagens, max_tokens:
                      (None, "erro") if modelo == "modelo-principal" else ("Resumo via fallback.", None)), \
         patch.object(resumir_mod.store, "salvar_resumo",
                      side_effect=lambda link, resumo, modelo, **k: doc_salvo.append(modelo) or True):
        resultado = resumir_mod._gerar_resumo("https://exemplo.com/doc", "Titulo", None, "Casa Teste", "OUTRO")
    _checar("4a store.salvar_resumo recebeu o modelo REAL (fallback), nao o principal presumido",
            doc_salvo == ["modelo-fallback"], f"(doc_salvo={doc_salvo})")
    _checar("4b dict retornado por _gerar_resumo tambem inclui o 'modelo' real",
            resultado.get("modelo") == "modelo-fallback", f"(resultado={resultado})")


def test_5_gerar_resumo_sem_texto_nunca_reporta_modelo():
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=(None, "login necessário")):
        resultado = resumir_mod._gerar_resumo("https://exemplo.com/doc", "Titulo", None, "Casa Teste", "OUTRO")
    _checar("5 falha na extracao de texto (antes de chamar IA) -> resultado sem 'modelo' nenhum",
            "modelo" not in resultado or resultado.get("modelo") is None, f"(resultado={resultado})")


# ============================================================
# NEWS (data/news.py) - SEM fallback de modelo (sempre 1 so', sem
# ambiguidade) - so' precisa propagar o valor, nunca inventar.
# ============================================================

def test_6_gerar_resumo_grupo_reporta_o_modelo_usado():
    with patch.object(news_mod.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-news")), \
         patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("texto bem longo da materia " * 50, None, "https://exemplo.com/1", None)), \
         patch.object(news_mod, "_resumir_com_groq", return_value=("Resumo da noticia.", None)):
        resultado = news_mod._gerar_resumo_grupo("Titulo da noticia", (("Valor Econômico", "https://exemplo.com/1"),))
    _checar("6a resumo gerado", resultado.get("resumo") is not None)
    _checar("6b 'modelo' reportado e' o unico modelo usado pelo NEWS (sem ambiguidade de fallback)",
            resultado.get("modelo") == "modelo-news", f"(resultado={resultado})")


def test_7_gerar_resumo_grupo_sem_sucesso_nenhum_nao_reporta_modelo():
    with patch.object(news_mod.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-news")), \
         patch.object(news_mod, "_extrair_texto_artigo", return_value=(None, None, None, "bloqueado")):
        resultado = news_mod._gerar_resumo_grupo("Titulo da noticia", (("Valor Econômico", "https://exemplo.com/1"),))
    _checar("7 nenhuma fonte deu certo -> sem resumo, sem 'modelo' reportado",
            resultado.get("resumo") is None and "modelo" not in resultado, f"(resultado={resultado})")


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
    print("TODOS OS TESTES DO MODELO REAL NO CACHE DE IA PASSARAM")
