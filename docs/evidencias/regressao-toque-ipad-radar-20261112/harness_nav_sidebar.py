# Harness visual LOCAL (sem login/auth/Supabase) - replica so' o que o bug
# de toque em iPad (PR #270) depende: st.set_page_config(initial_sidebar_
# state="auto") + style.css real + sidebar WATCHLIST real (bloco de
# app.py:529+, dados mock) + navegacao.render_nav_principal/render_subnav
# reais (mesmo padrao de harness_radar.py, docs/evidencias/
# responsividade-bloomberg-20261106/) - sem precisar de login Google real
# nem Supabase. Objetivo: reproduzir a condicao exata do bug (sidebar
# auto-aberta cobrindo a subnav em viewport de iPad) pra servir de
# regressao caso o CSS do fix (.st-key-nav_sub z-index) seja revertido.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
from ui import navegacao

st.set_page_config(page_title="harness nav+sidebar", layout="wide", initial_sidebar_state="auto")
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

# --- sidebar WATCHLIST (dados mock, mesmo HTML/classes de app.py:529+) ----
with st.sidebar:
    st.markdown('<div class="painel-titulo">WATCHLIST</div>', unsafe_allow_html=True)
    for t in ["PETR4", "VALE3", "ITUB4"]:
        col_info, col_remover = st.columns([4, 1])
        col_info.markdown(
            f"<div style='padding-bottom:0.35rem; margin-bottom:0.35rem; border-bottom:1px solid var(--borda);'>"
            f"<span style='color:var(--destaque); font-weight:600;'>{t}</span></div>",
            unsafe_allow_html=True,
        )
        col_remover.button("x", key=f"remover_{t}")

# --- nav principal + subnav reais (ui/navegacao.py), sem mock -------------
areas_nav = navegacao.disponiveis(config.ABAS_DISPONIVEIS, eh_admin=False)
navegacao.aplicar_url_de_entrada(areas_nav)
area_atual = navegacao.render_nav_principal(areas_nav)
area_obj = next(a for a in areas_nav if a.id == area_atual)
sub_atual = navegacao.render_subnav(area_obj)
navegacao.publicar_url(area_atual, sub_atual)
st.markdown(f"ROTA={area_atual}/{sub_atual}")
