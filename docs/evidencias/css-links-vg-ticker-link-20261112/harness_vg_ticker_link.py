# Harness visual LOCAL (sem login/auth/Supabase, mesmo padrao de
# docs/evidencias/regressao-toque-ipad-radar-20261112/harness_nav_sidebar.py):
# reproduz a condicao exata do bug de CSS da classe .vg-ticker-link (link
# azul/sublinhado padrao do navegador vencendo a cor ambar/tema do projeto)
# usando o MESMO HTML literal que os call-sites reais produzem (copiado de
# ui/visao_geral.py:531 e ui/secoes.py:161) dentro de um st.markdown comum
# (mesmo wrapper data-testid="stMarkdown" que o app real usa), + style.css
# real do projeto + variaveis de tema reais (config.TEMAS["AMBAR"]).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config

st.set_page_config(page_title="harness vg-ticker-link", layout="wide")

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

# --- link real de ticker, HTML literal copiado de ui/visao_geral.py:531 ---
st.markdown(
    "<a href='?ticker=PETR4' class='vg-ticker-link' id='link-teste-vg'>PETR4</a>",
    unsafe_allow_html=True,
)

# --- link externo de verdade (controle negativo: NAO deve ser afetado
# pela correcao, que precisa ficar escopada so' a .vg-ticker-link) ---
st.markdown(
    "<a href='https://github.com' target='_blank' rel='noopener' id='link-teste-externo'>GitHub (controle externo)</a>",
    unsafe_allow_html=True,
)
