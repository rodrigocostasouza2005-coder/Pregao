# Setup comum aos harnesses deste diretorio (CSS vars do tema AMBAR +
# style.css real) - mesmo padrao de docs/evidencias/watchlist-bloomberg-
# 20261106/harness_watchlist.py e docs/evidencias/validacao-independente-
# home-mercado-20261106/harness_mercado.py, extraido pra nao repetir em
# cada um dos 5 harnesses desta pasta.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config


def preparar_pagina(titulo: str):
    st.set_page_config(page_title=titulo, layout="wide")
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
