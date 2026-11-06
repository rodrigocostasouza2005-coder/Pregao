# Harness visual LOCAL (sem login/auth) - valida a reformulacao de MAIS >
# Watchlist (ui/secoes.py:render_watchlist) direto, sem depender de
# login/Supabase real. Mesmo padrao de
# docs/evidencias/design-system-fundacao-20261106/harness_design_system.py.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.secoes as secoes

st.set_page_config(page_title="harness watchlist", layout="wide")
with open(config.BASE_DIR / "style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

tema = config.TEMAS["AMBAR"]
_css_vars = (
    f":root {{"
    f"--bg:{tema['fundo']}; --painel-bg:{tema['painel']}; --borda:{tema['borda']}; "
    f"--destaque:{tema['destaque']}; --alta:{tema['alta']}; --baixa:{tema['baixa']}; "
    f"--neutro:{tema['neutro']}; --cinza:{tema['cinza']}; --ciano:{tema['ciano']}; "
    f"--padding-painel:0.4rem; --fonte-base:0.9rem;"
    f"}}"
)
st.markdown(f"<style>{_css_vars}</style>", unsafe_allow_html=True)
st.markdown(
    "<style>body{background:var(--bg);} .stApp{background:var(--bg);}</style>",
    unsafe_allow_html=True,
)

PREFS = {"formato_numerico": "BR", "watchlist": ["PETR4", "VALE3", "ITUB4", "MGLU3", "WEGE3"], "tema": "AMBAR"}


def _cotacoes(tickers):
    base = {
        "PETR4": {"preco": 36.52, "variacao_pct": 3.14, "volume_financeiro": 1_250_000_000.0, "erro": None},
        "VALE3": {"preco": 71.80, "variacao_pct": -1.02, "volume_financeiro": 980_000_000.0, "erro": None},
        "ITUB4": {"preco": 34.21, "variacao_pct": 0.0, "volume_financeiro": 540_000_000.0, "erro": None},
        "MGLU3": {"preco": 2.11, "variacao_pct": -12.47, "volume_financeiro": 210_000_000.0, "erro": None},
        "WEGE3": {"erro": "sem dado"},
    }
    return {t: base.get(t, {"erro": "sem dado"}) for t in tickers}


def _indicadores(ticker):
    dados = {
        "PETR4": {"pl": 5.2, "pvp": 1.1, "dividend_yield": 12.4},
        "VALE3": {"pl": 6.8, "pvp": 0.9, "dividend_yield": 8.1},
        "ITUB4": {"pl": None, "pvp": 1.8, "dividend_yield": 6.4},
        "MGLU3": {"pl": None, "pvp": 0.4, "dividend_yield": None},
        "WEGE3": {"pl": 28.3, "pvp": 7.9, "dividend_yield": 1.2},
    }
    return dados.get(ticker, {"pl": None, "pvp": None, "dividend_yield": None})


def _teses(prefs):
    return [
        ("PETR4", {"casa": "XP", "recomendacao": "COMPRA", "preco_alvo": 42.0}),
        ("MGLU3", {"casa": "Genial", "recomendacao": "VENDA", "preco_alvo": 1.60}),
    ]


def _noticias(tickers):
    return (
        [
            {"ticker": "PETR4", "titulo": "Petrobras anuncia novo plano de investimentos para 2027",
             "link": "https://exemplo.com/petr4", "data": "2026-11-06T10:00:00-03:00",
             "selo": "CONFIRMADA", "score": 9, "regras": ["veículo confiável"]},
            {"ticker": "MGLU3", "titulo": "Magazine Luiza revisa guidance após queda nas vendas do 3T",
             "link": "https://exemplo.com/mglu3", "data": "2026-11-06T08:30:00-03:00",
             "selo": "PROVÁVEL", "score": 6, "regras": ["2 veículos"]},
            {"ticker": "VALE3", "titulo": "Vale eleva produção de minério de ferro no trimestre",
             "link": "https://exemplo.com/vale3", "data": "2026-11-05T19:00:00-03:00",
             "selo": "NÃO CONFIRMADA", "score": 2, "regras": ["1 veículo"]},
        ],
        ["WEGE3"],
    )


with patch.object(secoes, "obter_cotacoes_lote", side_effect=_cotacoes), \
     patch.object(secoes, "obter_indicadores", side_effect=_indicadores), \
     patch.object(secoes, "_teses_research_watchlist", side_effect=_teses), \
     patch.object(secoes, "obter_noticias_watchlist", side_effect=_noticias):
    secoes.render_watchlist(PREFS)
