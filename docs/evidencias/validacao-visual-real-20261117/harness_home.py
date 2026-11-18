# Harness visual LOCAL (sem login/auth) - segunda opiniao independente
# sobre a reformulacao de HOME/VISAO GERAL pedida pelo Rodrigo (grafico
# principal amplo, radar de eventos integrado, faixa dinamica de
# cotacoes, rankings densos). Mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py:
# chama render_visao_geral direto, com config.PREFS_PADRAO e todas as
# fontes de dado mockadas com dados realistas (nunca inventados na UI -
# so' no mock, pra ter o que mostrar no screenshot).
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.calendario_tab as calendario_tab_mod
import ui.graficos as graficos_mod
import ui.visao_geral as vg
from data.eventos import STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM

st.set_page_config(page_title="harness home", layout="wide")
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
PREFS["watchlist"] = ["PETR4", "VALE3", "ITUB4", "MGLU3", "WEGE3"]

_COMPOSICAO = {t: {} for t in [
    "PETR4", "VALE3", "ITUB4", "MGLU3", "WEGE3", "BBAS3", "ABEV3", "B3SA3", "PRIO3", "SUZB3",
]}

_GLOBAIS = [
    {"nome": "S&P 500", "preco": 6812.4, "variacao_pct": 0.42},
    {"nome": "Nasdaq", "preco": 23480.1, "variacao_pct": 0.71},
]

_CDI = pd.DataFrame({"cdi_anualizado_pct": [14.9, 14.9, 14.85, 14.85, 14.8]})

_IBOV = {"preco": 148230.0, "variacao_pct": 1.18, "erro": None}
_DOLAR = {"preco": 5.41, "variacao_pct": -0.35, "erro": None}
_PETR4 = {"preco": 36.52, "variacao_pct": 3.14, "erro": None}
_VALE3 = {"preco": 71.80, "variacao_pct": -1.02, "erro": None}

_ALTAS = [
    {"ticker": "PRIO3", "preco": 42.10, "variacao_pct": 5.8, "setor": "Petróleo e Gás"},
    {"ticker": "PETR4", "preco": 36.52, "variacao_pct": 3.14, "setor": "Petróleo e Gás"},
    {"ticker": "CSAN3", "preco": 11.20, "variacao_pct": 2.9, "setor": "Petróleo e Gás"},
    {"ticker": "WEGE3", "preco": 54.30, "variacao_pct": 1.4, "setor": "Bens de Capital e Industrial"},
]
_BAIXAS = [
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
     "fontes_count": 4},
    {"titulo": "Magazine Luiza revisa guidance após queda nas vendas do 3T", "link": "https://exemplo.com/mglu3",
     "data": "2026-11-06T08:30:00-03:00", "selo": "PROVÁVEL", "score": 6, "regras": ["2 veículos"],
     "fontes_count": 2},
    {"titulo": "Vale eleva produção de minério de ferro no trimestre", "link": "https://exemplo.com/vale3",
     "data": "2026-11-05T19:00:00-03:00", "selo": "NÃO CONFIRMADA", "score": 2, "regras": ["1 veículo"],
     "fontes_count": 1},
    {"titulo": "Itaú supera estimativas de lucro no terceiro trimestre", "link": "https://exemplo.com/itub4",
     "data": "2026-11-05T15:00:00-03:00", "selo": "CONFIRMADA", "score": 8, "regras": ["veículo confiável"],
     "fontes_count": 3},
    {"titulo": "WEG anuncia expansão de capacidade produtiva em Jaraguá do Sul", "link": "https://exemplo.com/wege3",
     "data": "2026-11-05T11:00:00-03:00", "selo": "CONFIRMADA", "score": 7, "regras": ["veículo confiável"],
     "fontes_count": 2},
]

_SINTESE = {
    "ok": True,
    "gerado_em": (datetime.now() - timedelta(minutes=12)).isoformat(),
    "atual": True,
    "dados": {
        "resumo_executivo": {
            "texto": "Ibov sobe puxado por petroleiras, com Petrobras e PRIO liderando ganhos; Varejo "
                     "segue pressionado por revisão de guidance da Magazine Luiza."
        },
        "movimentos": [
            {"evento": "Petrobras sobe com alta do petróleo Brent acima de US$ 86", "fonte": "Valor Econômico"},
        ],
        "oportunidades_riscos": [
            {"ativo_ou_setor": "Petróleo e Gás", "argumento_favoravel": "Brent em alta sustenta margens.",
             "argumento_contrario": "Risco cambial pode reverter ganho em reais."},
            {"ativo_ou_setor": "MGLU3", "argumento_favoravel": "Múltiplo já comprimido.",
             "argumento_contrario": "Guidance revisado para baixo é sinal de fraqueza operacional."},
        ],
        "cenarios": [
            {"tipo": "principal", "cenario": "Ibovespa sustenta alta puxado por commodities",
             "sinalizadores": "Brent > US$ 85, dólar estável"},
        ],
    },
}

_EVENTOS = [
    {"ticker": "PETR4", "data": date.today() + timedelta(days=3), "status": STATUS_CONFIRMADO, "periodo": "3T26"},
    {"ticker": "VALE3", "data": date.today() + timedelta(days=9), "status": STATUS_ESTIMADO, "periodo": "3T26"},
    {"ticker": "ITUB4", "data": date.today() + timedelta(days=16), "status": STATUS_PRAZO_CVM, "periodo": "3T26"},
]

_COTACOES_LOTE = {
    "PETR4": {"preco": 36.52, "variacao_pct": 3.14, "volume_financeiro": 4.2e9, "erro": None},
    "VALE3": {"preco": 71.80, "variacao_pct": -1.02, "volume_financeiro": 3.1e9, "erro": None},
    "ITUB4": {"preco": 34.21, "variacao_pct": 0.3, "volume_financeiro": 2.6e9, "erro": None},
    "MGLU3": {"preco": 2.11, "variacao_pct": -6.4, "volume_financeiro": 1.8e9, "erro": None},
    "WEGE3": {"preco": 54.30, "variacao_pct": 1.4, "volume_financeiro": 1.2e9, "erro": None},
}

_TESES = [
    ("PETR4", {"casa": "XP", "recomendacao": "COMPRA", "preco_alvo": 42.0}),
    ("MGLU3", {"casa": "Genial", "recomendacao": "VENDA", "preco_alvo": 1.60}),
]


def _historico(ticker, periodo):
    n = 130
    rng = np.random.default_rng(7)
    base = 36.5 if ticker != config.SIMBOLO_IBOVESPA else 148000.0
    passos = rng.normal(0, base * 0.012, n).cumsum()
    close = base + passos - passos[0]
    datas = pd.bdate_range(end=datetime.now(), periods=n)
    df = pd.DataFrame({
        "Data": datas,
        "Open": close * (1 - rng.normal(0, 0.003, n)),
        "High": close * (1 + abs(rng.normal(0, 0.006, n))),
        "Low": close * (1 - abs(rng.normal(0, 0.006, n))),
        "Close": close,
        "Volume": rng.integers(1_000_000, 9_000_000, n),
    })
    df["MM20"] = df["Close"].rolling(20).mean()
    df["MM50"] = df["Close"].rolling(50).mean()
    return df


with patch.object(vg, "obter_composicao_oficial", return_value=_COMPOSICAO), \
     patch.object(vg, "obter_mercados_globais", return_value=_GLOBAIS), \
     patch.object(vg, "obter_cdi", return_value=_CDI), \
     patch.object(vg, "obter_cotacao_indice", side_effect=lambda nome, _s: _IBOV if nome == "IBOVESPA" else _DOLAR), \
     patch.object(vg, "obter_cotacao", side_effect=lambda t: _PETR4 if t == "PETR4" else _VALE3), \
     patch.object(vg, "obter_altas_baixas", return_value=(_ALTAS, _BAIXAS)), \
     patch.object(vg, "obter_mais_negociados", return_value=_NEGOCIADOS), \
     patch.object(vg, "obter_desempenho_setorial", return_value=_SETORES), \
     patch.object(vg, "obter_top_mercado_tudo", return_value=_NOTICIAS), \
     patch.object(vg, "obter_sintese_mercado", return_value=_SINTESE), \
     patch.object(vg, "calcular_calendario_cacheado", return_value=_EVENTOS), \
     patch.object(vg, "obter_cotacoes_lote", return_value=_COTACOES_LOTE), \
     patch.object(vg, "_casas_ativas", return_value=["genial"]), \
     patch.object(vg, "preparar_leitura", return_value=(
         [{"casa": "XP", "tickers": ["PETR4"], "recomendacao": "COMPRA", "preco_alvo": 42.0},
          {"casa": "Genial", "tickers": ["MGLU3"], "recomendacao": "VENDA", "preco_alvo": 1.60}], [], [], [])), \
     patch.object(calendario_tab_mod, "calcular_calendario_cacheado", return_value=_EVENTOS), \
     patch.object(graficos_mod, "obter_historico", side_effect=_historico), \
     patch.object(graficos_mod, "obter_historico_intraday", side_effect=_historico):
    vg.render_visao_geral(PREFS, persistir_fn=None)
