# Harness visual LOCAL (sem login/auth) - valida a reformulacao Bloomberg
# de ANALISES > Fundamentos (ui/analises_tab.py:render_fundamentos) direto,
# sem depender de login/Supabase/Yahoo Finance/CVM reais. Mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.analises_tab as at_mod

st.set_page_config(page_title="harness fundamentos", layout="wide")
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

PREFS = {"formato_numerico": "BR", "watchlist": ["PETR4", "VALE3", "ITUB4", "MGLU3", "WEGE3"]}

# Dados realistas cobrindo: linha normal com margens positivas (PETR4),
# linha com margem/ROE negativos (coloracao .baixa - MGLU3), P/L N.M.
# (lucro negativo - MGLU3), linha "indisponivel agora" (WEGE3, sem
# nenhum campo), e uma linha so' parcialmente coletada (ITUB4).
_INDICADORES = {
    "PETR4": {
        "valor_mercado": 450_000_000_000.0, "pl": 5.8, "pvp": 1.4, "dividend_yield": 14.2,
        "roe": 24.1, "margem_liquida": 18.3, "margem_operacional": 22.7, "margem_ebitda": 35.4,
        "fluxo_caixa_livre": 38_500_000_000.0, "divida_liquida": 180_000_000_000.0,
        "divida_liquida_ebitda": 1.2, "beta": 0.95, "_coletado_em": "2026-11-06T12:00:00+00:00",
    },
    "VALE3": {
        "valor_mercado": 280_000_000_000.0, "pl": 7.1, "pvp": 1.6, "dividend_yield": 9.8,
        "roe": 19.5, "margem_liquida": 21.0, "margem_operacional": 28.9, "margem_ebitda": 41.2,
        "fluxo_caixa_livre": 15_200_000_000.0, "divida_liquida": 45_000_000_000.0,
        "divida_liquida_ebitda": 0.7, "beta": 1.1, "_coletado_em": "2026-11-06T11:30:00+00:00",
    },
    "ITUB4": {
        "valor_mercado": 320_000_000_000.0, "pl": None, "pvp": 2.1, "dividend_yield": None,
        "roe": None, "margem_liquida": None, "margem_operacional": None, "margem_ebitda": None,
        "fluxo_caixa_livre": None, "divida_liquida": None, "divida_liquida_ebitda": None,
        "beta": 0.8, "_coletado_em": "2026-11-06T09:15:00+00:00",
    },
    "MGLU3": {
        "valor_mercado": 6_800_000_000.0, "pl": -3.4, "pvp": 0.6, "dividend_yield": 0.0,
        "roe": -11.2, "margem_liquida": -4.8, "margem_operacional": -1.9, "margem_ebitda": 3.1,
        "fluxo_caixa_livre": -820_000_000.0, "divida_liquida": 7_100_000_000.0,
        "divida_liquida_ebitda": 4.9, "beta": 1.6, "_coletado_em": "2026-11-06T10:45:00+00:00",
    },
    "WEGE3": {k: None for k in (
        "valor_mercado", "pl", "pvp", "dividend_yield", "roe", "margem_liquida",
        "margem_operacional", "margem_ebitda", "fluxo_caixa_livre", "divida_liquida",
        "divida_liquida_ebitda", "beta",
    )},
}


def _indicadores(ticker):
    return _INDICADORES.get(ticker, {})


def _cotacao(simbolo):
    base = {
        "PETR4": {"preco": 38.42, "variacao_pct": 1.8, "erro": None},
        "BZ=F": {"preco": 82.15, "variacao_pct": -0.6, "erro": None},
        "CL=F": {"preco": 78.30, "variacao_pct": -0.4, "erro": None},
        "USDBRL=X": {"preco": 5.21, "variacao_pct": 0.3, "erro": None},
    }
    return base.get(simbolo, {"preco": None, "variacao_pct": None, "erro": "sem dado"})


def _historico(casa, ticker, limite=5):
    if ticker != "PETR4":
        return []
    return [
        {"capturado_em": "2026-11-01T14:00:00+00:00", "casa": "genial", "recomendacao": "COMPRA", "preco_alvo": 44.0},
        {"capturado_em": "2026-09-15T14:00:00+00:00", "casa": "genial", "recomendacao": "COMPRA", "preco_alvo": 41.5},
    ]


with patch.object(at_mod, "obter_indicadores", side_effect=_indicadores), \
     patch.object(at_mod, "obter_cotacao", side_effect=_cotacao), \
     patch.object(at_mod, "historico_ticker", side_effect=_historico):
    at_mod.render_fundamentos(PREFS)
