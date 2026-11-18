# Harness visual LOCAL (sem login/auth) - segunda opiniao independente
# sobre MERCADO > PAINEL (render_mercado, ui/mercado_tab.py). Mesmo
# padrao de harness_home.py neste mesmo diretorio.
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.mercado_tab as mt

st.set_page_config(page_title="harness mercado", layout="wide")
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

PREFS = dict(config.PREFS_PADRAO)
PREFS["watchlist"] = ["PETR4", "VALE3", "ITUB4"]

_COMPOSICAO = {t: {} for t in [
    "PETR4", "VALE3", "ITUB4", "MGLU3", "WEGE3", "BBAS3", "ABEV3", "B3SA3", "PRIO3", "SUZB3",
]}

_GLOBAIS = [
    {"nome": "S&P 500", "preco": 6812.4, "variacao_pct": 0.42},
    {"nome": "Nasdaq", "preco": 23480.1, "variacao_pct": 0.71},
    {"nome": "Dow Jones", "preco": 51508.0, "variacao_pct": -0.03},
    {"nome": "FTSE 100 (Londres)", "preco": 10674.0, "variacao_pct": -1.01},
]

_CDI = pd.DataFrame({"cdi_anualizado_pct": [14.9, 14.9, 14.85, 14.85, 14.8]})
_IBOV = {"preco": 148230.0, "variacao_pct": 1.18, "erro": None}
_DOLAR = {"preco": 5.41, "variacao_pct": -0.35, "erro": None}

_ALTAS_POOL = [
    {"ticker": "PRIO3", "preco": 42.10, "variacao_pct": 5.8, "setor": "Petróleo e Gás"},
    {"ticker": "PETR4", "preco": 36.52, "variacao_pct": 3.14, "setor": "Petróleo e Gás"},
    {"ticker": "CSAN3", "preco": 11.20, "variacao_pct": 2.9, "setor": "Petróleo e Gás"},
    {"ticker": "WEGE3", "preco": 54.30, "variacao_pct": 1.4, "setor": "Bens de Capital e Industrial"},
    {"ticker": "BBAS3", "preco": 28.40, "variacao_pct": 0.9, "setor": "Bancos e Serviços Financeiros"},
]
_BAIXAS_POOL = [
    {"ticker": "MGLU3", "preco": 2.11, "variacao_pct": -6.4, "setor": "Varejo"},
    {"ticker": "VALE3", "preco": 71.80, "variacao_pct": -1.02, "setor": "Mineração e Siderurgia"},
    {"ticker": "LREN3", "preco": 14.90, "variacao_pct": -0.8, "setor": "Varejo"},
]

_NEGOCIADOS = [
    {"ticker": "PETR4", "preco": 36.52, "variacao_pct": 3.14, "setor": "Petróleo e Gás", "volume_financeiro": 4.2e9},
    {"ticker": "VALE3", "preco": 71.80, "variacao_pct": -1.02, "setor": "Mineração e Siderurgia", "volume_financeiro": 3.1e9},
    {"ticker": "ITUB4", "preco": 34.21, "variacao_pct": 0.3, "setor": "Bancos e Serviços Financeiros", "volume_financeiro": 2.6e9},
    {"ticker": "BBAS3", "preco": 28.40, "variacao_pct": 0.9, "setor": "Bancos e Serviços Financeiros", "volume_financeiro": 2.1e9},
    {"ticker": "MGLU3", "preco": 2.11, "variacao_pct": -6.4, "setor": "Varejo", "volume_financeiro": 1.8e9},
    {"ticker": "WEGE3", "preco": 54.30, "variacao_pct": 1.4, "setor": "Bens de Capital e Industrial", "volume_financeiro": 1.2e9},
]

_SETORES = [
    {"setor": "Petróleo e Gás", "variacao_media_pct": 3.4, "n_papeis": 6},
    {"setor": "Bens de Capital e Industrial", "variacao_media_pct": 1.1, "n_papeis": 5},
    {"setor": "Bancos e Serviços Financeiros", "variacao_media_pct": 0.5, "n_papeis": 9},
    {"setor": "Saúde", "variacao_media_pct": 0.1, "n_papeis": 4},
    {"setor": "Mineração e Siderurgia", "variacao_media_pct": -0.6, "n_papeis": 3},
    {"setor": "Varejo", "variacao_media_pct": -3.8, "n_papeis": 7},
]

_NOTICIAS = [
    {"titulo": "Petrobras anuncia novo plano de investimentos para 2027", "link": "https://exemplo.com/petr4",
     "data": "2026-11-06T10:00:00-03:00", "selo": "CONFIRMADA", "score": 9, "regras": ["veículo confiável"],
     "fontes_count": 4, "tickers": ["PETR4"]},
    {"titulo": "Magazine Luiza revisa guidance após queda nas vendas do 3T", "link": "https://exemplo.com/mglu3",
     "data": "2026-11-06T08:30:00-03:00", "selo": "PROVÁVEL", "score": 6, "regras": ["2 veículos"],
     "fontes_count": 2, "tickers": ["MGLU3"]},
    {"titulo": "Vale eleva produção de minério de ferro no trimestre", "link": "https://exemplo.com/vale3",
     "data": "2026-11-05T19:00:00-03:00", "selo": "NÃO CONFIRMADA", "score": 2, "regras": ["1 veículo"],
     "fontes_count": 1, "tickers": ["VALE3"]},
]

_TERMOMETRO = {"alta": 48, "baixa": 29, "estavel": 7, "total": 84}

_PANORAMA = [
    {"ticker": p["ticker"], "preco": p["preco"], "variacao_pct": p["variacao_pct"], "setor": p["setor"],
     "volume_financeiro": v}
    for p, v in zip(
        _ALTAS_POOL + _BAIXAS_POOL,
        [4.2e9, 1.0e9, 0.6e9, 1.2e9, 2.1e9, 1.8e9, 3.1e9, 0.4e9],
    )
]


def _historico(ticker, periodo):
    n = 130
    rng = np.random.default_rng(3)
    base = 36.5
    passos = rng.normal(0, base * 0.012, n).cumsum()
    close = base + passos - passos[0]
    datas = pd.bdate_range(end=datetime.now(), periods=n)
    return pd.DataFrame({
        "Data": datas, "Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close,
        "Volume": rng.integers(1_000_000, 9_000_000, n),
    })


with patch.object(mt, "obter_composicao_oficial", return_value=_COMPOSICAO), \
     patch.object(mt, "obter_mercados_globais", return_value=_GLOBAIS), \
     patch.object(mt, "obter_cdi", return_value=_CDI), \
     patch.object(mt, "obter_cotacao_indice", side_effect=lambda nome, _s: _IBOV if "IBOV" in nome else _DOLAR), \
     patch.object(mt, "obter_termometro", return_value=_TERMOMETRO), \
     patch.object(mt, "obter_altas_baixas", return_value=(_ALTAS_POOL, _BAIXAS_POOL)), \
     patch.object(mt, "obter_mais_negociados", return_value=_NEGOCIADOS), \
     patch.object(mt, "obter_desempenho_setorial", return_value=_SETORES), \
     patch.object(mt, "obter_top_mercado_tudo", return_value=_NOTICIAS), \
     patch.object(mt, "obter_panorama_ibovespa", return_value=_PANORAMA), \
     patch.object(mt, "obter_momento_panorama", return_value=datetime.now() - timedelta(minutes=4)):
    mt.render_mercado(PREFS, persistir_fn=None)
