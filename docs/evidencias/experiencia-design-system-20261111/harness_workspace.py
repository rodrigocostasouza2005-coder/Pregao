# Harness visual LOCAL (sem login/auth/Supabase) - exercita
# ui/workspace.py (renderizar_workspace: toolbar, drag/resize JS, popover
# "⚙" por painel) com 2 paineis de exemplo, mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.workspace as workspace

st.set_page_config(page_title="harness workspace", layout="wide")
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


def _painel_a():
    st.markdown('<div class="painel-titulo">PAINEL A</div>', unsafe_allow_html=True)
    st.markdown("<div class='cinza'>Conteúdo de exemplo A.</div>", unsafe_allow_html=True)


def _painel_b():
    st.markdown('<div class="painel-titulo">PAINEL B</div>', unsafe_allow_html=True)
    st.markdown("<div class='cinza'>Conteúdo de exemplo B.</div>", unsafe_allow_html=True)


registro = [("a", "Painel A", _painel_a), ("b", "Painel B", _painel_b)]
prefs = {"layout_paineis_livre": {}, "ordem_paineis": {}, "paineis_visiveis": {}}
workspace.renderizar_workspace("harness", registro, prefs)
