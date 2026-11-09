# Harness visual LOCAL (sem login/auth) - valida a reformulacao de MAIS >
# SISTEMA (ui/sistema_tab.py:render_sistema) direto, sem depender de
# login/Supabase real. Mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py.
# render_sistema le CHANGELOG.md/PROGRESSO.md/MANUAL.md DIRETO do disco
# (sao arquivos reais do repo, nao dado mockado) - nenhum mock de dados
# necessario aqui, so' tema/CSS pro harness isolado.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
from ui.sistema_tab import render_sistema

st.set_page_config(page_title="harness sistema", layout="wide")
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

PREFS = {"formato_numerico": "BR"}

render_sistema(PREFS)
