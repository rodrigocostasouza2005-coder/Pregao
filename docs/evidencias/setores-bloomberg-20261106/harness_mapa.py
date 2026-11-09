# Harness visual LOCAL (sem login/auth) - valida a reformulacao de
# SETORES > Mapa Setorial (ui.setores_tab.render_mapa_setorial) direto,
# sem depender de login/Supabase real. Mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

import config
import ui.mercado_tab as mercado_tab
import ui.setores_tab as setores_tab
from _mock_data import (
    mock_cotacao_indice, mock_desempenho_setorial, mock_momento_panorama, mock_panorama_ibovespa,
)

st.set_page_config(page_title="harness setores - mapa", layout="wide")
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

with patch.object(mercado_tab, "obter_desempenho_setorial", side_effect=mock_desempenho_setorial), \
     patch.object(mercado_tab, "obter_panorama_ibovespa", side_effect=mock_panorama_ibovespa), \
     patch.object(mercado_tab, "obter_momento_panorama", side_effect=mock_momento_panorama), \
     patch.object(mercado_tab, "obter_cotacao_indice", side_effect=mock_cotacao_indice):
    setores_tab.render_mapa_setorial(PREFS)
