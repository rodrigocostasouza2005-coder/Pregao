# -*- coding: utf-8 -*-
"""Teste do bug real corrigido (2026-10-09, FASE 8 - pedido do Rodrigo
sobre Morning Call "Resumo ainda nao gerado"): ui/research_tab.py
_abrir_resumo_live gerava+persistia o resumo (data/research/resumir.py:
obter_resumo, upsert no Supabase) mas nao atualizava o dict `rel` em
memoria - o card por tras do dialogo (ui/news_tab.py:_cartao_live, MESMA
referencia de dict, ver _montar_feed) continuava lendo rel.get('resumo')
como vazio e mostrando "Resumo ainda nao gerado" no MESMO clique, so'
corrigindo no PROXIMO rerun da pagina inteira.

st.dialog precisa de um ScriptRunContext de verdade pra abrir o modal -
patcheia streamlit.dialog pra um decorator identidade ANTES de importar
ui.research_tab, pra testar so' a LOGICA da funcao (sem a UI do modal
em si, que so' se confirma com AppTest/Playwright reais, ja' fora do
escopo deste teste unitario). Elementos st.markdown/st.caption/etc fora
de uma sessao real so' avisam no log (nao quebram) - comportamento
padrao do Streamlit em "bare mode".

Uso: python tests/test_research_resumo_live_sync.py (python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

_dialog_original = st.dialog
st.dialog = lambda *a, **k: (lambda fn: fn)  # decorator identidade so' pra este teste

import ui.research_tab as research_tab  # noqa: E402 (import depois do patch de proposito)

st.dialog = _dialog_original  # restaura pra nao afetar outro modulo que importe depois

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


def test_1a_resumo_gerado_com_sucesso_sincroniza_rel_no_mesmo_clique():
    rel = {
        "link": "https://youtube.com/watch?v=abc", "titulo": "Morning Call 09/10",
        "casa": "Genial (Lives)", "autor": "Zé Márcio", "data": "2026-10-09",
        "tipo": "LIVE", "tickers": [],
    }
    resultado_groq = {"resumo": "RESUMO\n\nMercado abriu em alta...", "motivo_indisponivel": None,
                       "preco_alvo": None, "recomendacao": None}
    with patch.object(research_tab, "obter_resumo", return_value=resultado_groq) as mock_obter:
        research_tab._abrir_resumo_live(rel, extrator=None)
    _checar("1a obter_resumo foi chamado (geracao real disparada, nao pulada)", mock_obter.called)
    _checar(
        "1b rel['resumo'] reflete o resumo recem-gerado/persistido, sem esperar o proximo rerun "
        "(bug real: card por tras do dialogo continuava 'Resumo ainda nao gerado' no mesmo clique)",
        rel.get("resumo") == resultado_groq["resumo"], f"(rel={rel})",
    )


def test_1c_falha_na_geracao_nao_fabrica_resumo_nem_mascara_o_motivo():
    rel = {
        "link": "https://youtube.com/watch?v=def", "titulo": "Resumo da Manhã 09/10",
        "casa": "Genial (Lives)", "autor": "", "data": "2026-10-09", "tipo": "LIVE", "tickers": [],
    }
    resultado_falha = {"resumo": None, "motivo_indisponivel": "indisponivel",
                        "preco_alvo": None, "recomendacao": None}
    with patch.object(research_tab, "obter_resumo", return_value=resultado_falha):
        research_tab._abrir_resumo_live(rel, extrator=None)
    _checar(
        "1c falha na geracao (ex: sem legenda/transcricao) NUNCA grava um resumo fabricado em rel - "
        "continua None, pronto pra tentar de novo no proximo clique (nunca 'trava' num erro permanente)",
        rel.get("resumo") is None, f"(rel={rel})",
    )


def test_1d_resumo_ja_existente_no_formato_novo_nao_chama_obter_resumo_de_novo():
    rel = {
        "link": "https://youtube.com/watch?v=ghi", "titulo": "Fechamento Genial 08/10",
        "casa": "Genial (Lives)", "autor": "", "data": "2026-10-08", "tipo": "LIVE", "tickers": [],
        "resumo": "RESUMO\n\nJa existente, formato novo.",
    }
    with patch.object(research_tab, "obter_resumo") as mock_obter:
        research_tab._abrir_resumo_live(rel, extrator=None)
    _checar("1d resumo ja persistido (formato novo) -> nunca gera de novo (economiza cota de IA)",
             not mock_obter.called)


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE SINCRONIA DO RESUMO LIVE PASSARAM")
