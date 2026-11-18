# Harness visual LOCAL (sem login/auth, sem Supabase real) para validar o
# redesign ESTRUTURAL de RADAR > Alertas/Carteiras Recomendadas/Teses/
# Valuation/Acompanhamento (Agente A, 2026-11-12) - mesmo padrão de
# docs/evidencias/agente-d-redesign-estrutural-20261112/harness_radar.py
# (mesma missão, frente diferente). Dados mockados representativos - o
# que este harness precisa confirmar é a GRADE/composição/hierarquia ao
# redor dos blocos reais (ui/radar_tab.py), não a lógica de cálculo (já
# coberta por tests/test_radar_tab*.py, não tocada por esta missão).
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.radar_tab as radar_tab
from data import radar_quedas as rq_mod

ABA = sys.argv[1] if len(sys.argv) > 1 else "alertas"

st.set_page_config(page_title=f"harness radar - {ABA}", layout="wide")
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
st.markdown("<style>body{background:var(--bg);} .stApp{background:var(--bg);}</style>", unsafe_allow_html=True)

PREFS = dict(config.PREFS_PADRAO)
PREFS["watchlist"] = ["PETR4", "VALE3", "ITUB4", "MGLU3", "WEGE3"]

_RESUMO_FONTES = {
    "Itaú Investimentos": {"ativos": 10, "verificado_em": "2026-11-12T10:00:00+00:00", "desatualizada": False,
                            "carteiras": ["Top 5"], "data_publicacao": "2026-11-10"},
    "Safra Corretora": {"ativos": 12, "verificado_em": "2026-11-01T10:00:00+00:00", "desatualizada": True,
                         "carteiras": ["Top 10 Ações"], "data_publicacao": "2026-10-20"},
}
_LINHAS_CARTEIRAS = [
    {"casa": "Itaú Investimentos", "carteira": "Top 5", "ticker": "PETR4", "empresa": "Petrobras",
     "preco_alvo": 44.0, "data_publicacao": "2026-11-10", "verificado_em": "2026-11-12T10:00:00+00:00",
     "fonte_url": "https://itau.com.br/x"},
    {"casa": "Itaú Investimentos", "carteira": "Top 5", "ticker": "VALE3", "empresa": "Vale",
     "preco_alvo": 68.0, "data_publicacao": "2026-11-10", "verificado_em": "2026-11-12T10:00:00+00:00",
     "fonte_url": "https://itau.com.br/x"},
    {"casa": "Safra Corretora", "carteira": "Top 10 Ações", "ticker": "ITUB4", "empresa": "Itaú Unibanco",
     "preco_alvo": 38.0, "data_publicacao": "2026-10-20", "verificado_em": "2026-11-01T10:00:00+00:00",
     "fonte_url": "https://safra.com.br/x"},
]
_MONITORADOS = [
    {"ticker": "PETR4", "empresa": "Petrobras", "preco": 36.10, "fechamento_anterior": 37.92,
     "variacao_pct": -4.8, "estado": "ALERTA", "distancia_gatilho_pp": None,
     "casas": ["Itaú Investimentos"], "carteiras": ["Top 5"]},
    {"ticker": "VALE3", "empresa": "Vale", "preco": 62.0, "fechamento_anterior": 64.0,
     "variacao_pct": -3.1, "estado": "ATENCAO", "distancia_gatilho_pp": 0.9,
     "casas": ["Itaú Investimentos"], "carteiras": ["Top 5"]},
    {"ticker": "ITUB4", "empresa": "Itaú Unibanco", "preco": 35.5, "fechamento_anterior": 35.2,
     "variacao_pct": 0.8, "estado": "NORMAL", "distancia_gatilho_pp": 4.8,
     "casas": ["Safra Corretora"], "carteiras": ["Top 10 Ações"]},
]
_ALERTAS = [
    {"ticker": "PETR4", "empresa": "Petrobras", "pregao": "2026-11-12", "variacao_pct": -4.8,
     "preco_atual": 36.10, "fechamento_anterior": 37.92, "casas": ["Itaú Investimentos"],
     "carteiras": ["Top 5"], "fontes": ["https://itau.com.br/x"],
     "alertado_em": "2026-11-12T15:31:05+00:00", "status": "ENVIADO"},
]


def _fake_evidencias(tickers, watchlist):
    st.markdown(
        "<div class='radar-alerta'><div class='radar-alerta-topo'>"
        "<span class='radar-ticker'>PETR4</span><span class='radar-categoria'>há 1 dia</span></div>"
        "<div class='radar-descricao'>Petrobras anuncia novo plano de investimentos para 2027</div></div>",
        unsafe_allow_html=True,
    )


def _fake_copiloto(tickers):
    st.markdown("<div class='rq-nota'>Pergunte algo sobre PETR4/VALE3/ITUB4 (copiloto de research).</div>",
                unsafe_allow_html=True)


def _fake_risco(prefs, sub):
    st.markdown(
        "<div class='rq-nota'>2 posições cadastradas · exposição total R$ 48.200,00 · "
        "concentração máxima: PETR4 (38,4% da carteira).</div>",
        unsafe_allow_html=True,
    )


def _sem_fragment(fn):
    """@st.fragment nao executa o corpo em modo bare, mas ESTE harness roda
    dentro de uma sessao Streamlit real (via `streamlit run`), entao
    .__wrapped__ nao e' necessario pra execucao - usado aqui so' pra manter
    o MESMO padrao do harness irmao (agente-d), sem custo."""
    return getattr(fn, "__wrapped__", fn)


def _ir():
    if ABA == "alertas":
        _sem_fragment(radar_tab.render_radar_alertas)(PREFS)
    elif ABA == "carteiras":
        _sem_fragment(radar_tab.render_radar_carteiras)(PREFS)
    elif ABA == "teses":
        _sem_fragment(radar_tab.render_teses)(PREFS, {"sub": "usuario-mock", "email": "x@x.com"})
    elif ABA == "valuation":
        _sem_fragment(radar_tab.render_valuation)(PREFS)
    elif ABA == "acompanhamento":
        _sem_fragment(radar_tab.render_radar_acompanhamento)(PREFS, {"sub": "usuario-mock", "email": "x@x.com"})
    else:
        raise SystemExit(f"aba desconhecida: {ABA}")


with patch.object(rq_mod, "resumo_fontes_vigentes", return_value=_RESUMO_FONTES), \
     patch.object(rq_mod, "listar_carteiras", return_value=_LINHAS_CARTEIRAS), \
     patch.object(rq_mod, "painel_monitorados", return_value=_MONITORADOS), \
     patch.object(rq_mod, "alertas_periodo", return_value=_ALERTAS), \
     patch.object(radar_tab, "_secao_evidencias", side_effect=_fake_evidencias), \
     patch.object(radar_tab, "_secao_copiloto", side_effect=_fake_copiloto), \
     patch.object(radar_tab, "_secao_risco", side_effect=_fake_risco):
    _ir()
