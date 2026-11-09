# Harness visual LOCAL (sem login/auth) - valida a reformulacao de
# SETORES > Visao por Setor (ui.setores_tab.render_visao_setor, que por
# sua vez chama _tabela_empresas/_bloco_por_que_importa daqui +
# ui.top_mercado_tab.render_top_mercado - mesmo componente ja usado em
# NOTICIAS) direto, sem depender de login/Supabase real. Mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

import config
import ui.setores_tab as setores_tab
import ui.top_mercado_tab as top_mercado_tab
from _mock_data import SETOR, mock_cotacoes_lote, mock_top_mercado_tudo

st.set_page_config(page_title="harness setores - visao", layout="wide")
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

PREFS = {"formato_numerico": "BR", "tema": "AMBAR", "watchlist": []}
st.session_state.setdefault(setores_tab.KEY_SETOR, SETOR)

with patch.object(setores_tab, "obter_cotacoes_lote", side_effect=mock_cotacoes_lote), \
     patch.dict(top_mercado_tab._BUSCADORES, {"TUDO": mock_top_mercado_tudo}):
    setores_tab.render_visao_setor(PREFS)
