# Harness visual LOCAL (sem login/auth/Supabase/rede) pra render_calendario
# (ui/calendario_tab.py, rota MERCADO > Agenda, dispatch via
# ui/secoes.py:render_agenda) - checagem de confirmacao desta auditoria
# (2026-11-13): esta subaba nao tinha evidencia visual fresca registrada
# em docs/evidencias/ ainda. Mocka so' calcular_calendario_cacheado/
# obter_snapshot_calendario/universo_calendario/obter_documentos_cvm/
# obter_noticias/listar_itens - zero rede real.
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.calendario_tab as calendario_tab_mod
from data.eventos import STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM

st.set_page_config(page_title="harness calendario", layout="wide")
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

HOJE = date.today()
_TICKERS = ["PETR4", "VALE3", "ITUB4", "MGLU3", "WEGE3", "BBAS3", "ABEV3"]


def _evento(ticker, dias, status, periodo="3T26", horario=None):
    return {
        "ticker": ticker, "empresa": f"EMPRESA {ticker}", "periodo": periodo,
        "data": HOJE + timedelta(days=dias), "horario": horario,
        "status": status, "fonte": "B3/CVM (FCA)", "origem_url": "https://www.rad.cvm.gov.br/",
        "tipo_evento": "RESULTADO", "coletado_em": None,
    }


_EVENTOS = [
    _evento("PETR4", 2, STATUS_CONFIRMADO, horario="18:00"),
    _evento("VALE3", 5, STATUS_ESTIMADO),
    _evento("ITUB4", 9, STATUS_PRAZO_CVM),
    _evento("MGLU3", 12, STATUS_PRAZO_CVM),
    _evento("WEGE3", -3, STATUS_CONFIRMADO),
    _evento("BBAS3", 16, STATUS_ESTIMADO),
]

_DOCS_CVM = [
    {"ticker": "PETR4", "tipo": "RESULTADOS", "data": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
     "data_referencia": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
     "link": "https://www.rad.cvm.gov.br/doc-1", "assunto": "Resultado do 2º Trimestre de 2026 (ITR)"},
]
_NOTICIAS = [
    {"data": datetime.now(timezone.utc).isoformat(), "titulo": "Petrobras anuncia novo plano de investimentos",
     "link": "https://exemplo.com/petr4"},
]
_RESEARCH_ITENS = [
    {"data": datetime.now(timezone.utc).isoformat(), "casa": "XP", "titulo": "PETR4: mantemos COMPRA",
     "link": "https://exemplo.com/xp-petr4", "tickers": ["PETR4"]},
]

PREFS = dict(config.PREFS_PADRAO)
PREFS["watchlist"] = _TICKERS
PREFS["formato_numerico"] = "BR"

with patch.object(calendario_tab_mod, "calcular_calendario_cacheado", return_value=_EVENTOS), \
     patch.object(calendario_tab_mod, "obter_snapshot_calendario", return_value={
         "atualizado_em": (datetime.now(timezone.utc) - timedelta(minutes=18)).isoformat()}), \
     patch.object(calendario_tab_mod, "universo_calendario", return_value=_TICKERS + ["CSAN3", "PRIO3"]), \
     patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=_DOCS_CVM), \
     patch.object(calendario_tab_mod, "obter_noticias", return_value=_NOTICIAS), \
     patch.object(calendario_tab_mod, "listar_itens", return_value=_RESEARCH_ITENS):
    calendario_tab_mod.render_calendario.__wrapped__(PREFS)
