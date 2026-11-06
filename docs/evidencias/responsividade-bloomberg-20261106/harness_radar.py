# Harness visual LOCAL (sem login/auth/Supabase) - valida responsividade de
# RADAR > Alertas e RADAR > Carteiras Recomendadas (ui/radar_tab.py) direto,
# mockando so' as funcoes de data/radar_quedas.py (mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py).
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.radar_tab as radar_tab
from data import radar_quedas as rq
from data import market_makers

st.set_page_config(page_title="harness radar", layout="wide")
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

PREFS = {"formato_numerico": "BR", "tema": "AMBAR"}

AGORA = datetime.now(timezone.utc)
VERIFICADO_RECENTE = (AGORA - timedelta(hours=2)).isoformat()
VERIFICADO_VELHO = (AGORA - timedelta(hours=200)).isoformat()

_CARTEIRAS = [
    {"casa": rq.CASA_ITAU, "carteira": "Top 5", "ticker": "PETR4", "empresa": "Petrobras",
     "preco_alvo": 42.0, "data_publicacao": "2026-11-01", "fonte_url": "https://exemplo.com/itau",
     "verificado_em": VERIFICADO_RECENTE, "vigente": True},
    {"casa": rq.CASA_ITAU, "carteira": "Top 5", "ticker": "VALE3", "empresa": "Vale",
     "preco_alvo": 78.0, "data_publicacao": "2026-11-01", "fonte_url": "https://exemplo.com/itau",
     "verificado_em": VERIFICADO_RECENTE, "vigente": True},
    {"casa": rq.CASA_ITAU, "carteira": "Top 5", "ticker": "ITUB4", "empresa": "Itau Unibanco",
     "preco_alvo": 38.0, "data_publicacao": "2026-11-01", "fonte_url": "https://exemplo.com/itau",
     "verificado_em": VERIFICADO_RECENTE, "vigente": True},
    {"casa": rq.CASA_SAFRA, "carteira": "Carteira Recomendada", "ticker": "MGLU3", "empresa": "Magazine Luiza",
     "preco_alvo": 2.6, "data_publicacao": "2026-10-15", "fonte_url": "https://exemplo.com/safra",
     "verificado_em": VERIFICADO_VELHO, "vigente": True},
    {"casa": rq.CASA_SAFRA, "carteira": "Carteira Recomendada", "ticker": "WEGE3", "empresa": "WEG",
     "preco_alvo": 55.0, "data_publicacao": "2026-10-15", "fonte_url": "https://exemplo.com/safra",
     "verificado_em": VERIFICADO_VELHO, "vigente": True},
]

_PAINEL = [
    {"ticker": "PETR4", "empresa": "Petrobras", "casas": [rq.CASA_ITAU], "carteiras": ["Top 5"],
     "preco": 34.10, "fechamento_anterior": 36.52, "variacao_pct": -6.63,
     "distancia_gatilho_pp": None, "estado": "ALERTA"},
    {"ticker": "MGLU3", "empresa": "Magazine Luiza", "casas": [rq.CASA_SAFRA], "carteiras": ["Carteira Recomendada"],
     "preco": 2.02, "fechamento_anterior": 2.11, "variacao_pct": -2.84,
     "distancia_gatilho_pp": -1.16, "estado": "ATENCAO"},
    {"ticker": "VALE3", "empresa": "Vale", "casas": [rq.CASA_ITAU], "carteiras": ["Top 5"],
     "preco": 71.80, "fechamento_anterior": 71.00, "variacao_pct": 1.13,
     "distancia_gatilho_pp": 5.13, "estado": "NORMAL"},
    {"ticker": "ITUB4", "empresa": "Itau Unibanco", "casas": [rq.CASA_ITAU], "carteiras": ["Top 5"],
     "preco": 34.21, "fechamento_anterior": 34.21, "variacao_pct": 0.0,
     "distancia_gatilho_pp": 4.0, "estado": "NORMAL"},
    {"ticker": "WEGE3", "empresa": "WEG", "casas": [rq.CASA_SAFRA], "carteiras": ["Carteira Recomendada"],
     "preco": None, "fechamento_anterior": None, "variacao_pct": None,
     "distancia_gatilho_pp": None, "estado": "SEM_COTACAO"},
]

_ALERTAS = [
    {"ticker": "PETR4", "empresa": "Petrobras", "variacao_pct": -6.63, "fechamento_anterior": 36.52,
     "preco_atual": 34.10, "casas": [rq.CASA_ITAU], "carteiras": ["Top 5"],
     "fontes": ["https://exemplo.com/itau"], "status": "ENVIADO",
     "pregao": AGORA.date().isoformat(), "alertado_em": AGORA.isoformat()},
    {"ticker": "MGLU3", "empresa": "Magazine Luiza", "variacao_pct": -4.90, "fechamento_anterior": 2.20,
     "preco_atual": 2.09, "casas": [rq.CASA_SAFRA], "carteiras": ["Carteira Recomendada"],
     "fontes": ["https://exemplo.com/safra"], "status": "PENDENTE_ENVIO",
     "pregao": (AGORA - timedelta(days=1)).date().isoformat(), "alertado_em": (AGORA - timedelta(days=1)).isoformat()},
]

_RESUMO_FONTES = {
    rq.CASA_ITAU: {"ativos": 3, "verificado_em": VERIFICADO_RECENTE, "desatualizada": False,
                   "carteiras": ["Top 5"], "data_publicacao": "2026-11-01"},
    rq.CASA_SAFRA: {"ativos": 2, "verificado_em": VERIFICADO_VELHO, "desatualizada": True,
                     "carteiras": ["Carteira Recomendada"], "data_publicacao": "2026-10-15"},
}


def _alertas_periodo(dias):
    return _ALERTAS


def _contexto_ticker(ticker, janela="7 DIAS"):
    return {"ticker": ticker, "interpretacao": None, "riscos": []}


# NAO usar unittest.mock.patch como context manager/stop() aqui: o
# Streamlit reexecuta este arquivo inteiro a cada interacao (rerun), mas
# o processo e' o MESMO - stop() desfaria o mock assim que o render
# terminasse e o PROXIMO rerun (clique num pill/selectbox) bateria direto
# nas funcoes reais (sem Supabase neste ambiente, retornam None) antes
# deste script voltar a rodar e re-aplicar o patch. Atribuicao direta,
# idempotente a cada rerun, sem stop - mock sempre no lugar.
rq.listar_carteiras = lambda: _CARTEIRAS
rq.painel_monitorados = lambda: _PAINEL
rq.resumo_fontes_vigentes = lambda: _RESUMO_FONTES
rq.alertas_periodo = _alertas_periodo
market_makers.contexto_ticker = _contexto_ticker

secao = st.query_params.get("secao", "alertas")
if secao == "carteiras":
    radar_tab.render_radar_carteiras(PREFS)
else:
    radar_tab.render_radar_alertas(PREFS)
