# Harness visual LOCAL (sem login/auth/Supabase) - adaptado de
# docs/evidencias/regressao-toque-ipad-radar-20261112/harness_nav_sidebar.py.
# Mesmo padrao: st.set_page_config(initial_sidebar_state="auto") + style.css
# real + sidebar WATCHLIST real (mock) + navegacao.render_nav_principal/
# render_subnav reais, SEM precisar de login Google/Supabase. Acrescenta um
# bloco de "conteudo principal" real (render_mercado com cotacoes mockadas)
# pra poder medir, via Playwright, se a sidebar overlay cobre esse conteudo
# em telas touch de tablet (~1024px) - achado registrado em
# docs/evidencias/fase6-ux-missao-master-20261123/LEIA.md, nunca corrigido.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
from ui import navegacao

st.set_page_config(page_title="harness sidebar overlap", layout="wide", initial_sidebar_state="auto")
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

# --- marcador de CONTEUDO PRINCIPAL real (preenche a largura do stMain,
# nasce rente a borda esquerda igual a qualquer painel real do app - ver
# ui/visao_geral.py/ui/mercado_tab.py, todos comecam direto no
# block-container sem margem lateral propria). id estavel pra medir via
# Playwright (getBoundingClientRect), independente de classe/hash do
# Streamlit. 6 "paineis" marcam visualmente linhas de conteudo real (fundo
# contrastante, pra aparecer claro no screenshot mesmo coberto por overlay). ----
st.markdown(
    "<div id='conteudo-principal-teste' style=\"background:#1a3a1a; border:2px solid #22C55E; "
    "padding:1rem; min-height:600px;\">"
    "<h3 style='color:#22C55E; margin:0 0 0.5rem 0;'>CONTEUDO PRINCIPAL (marcador de teste)</h3>"
    + "".join(
        f"<div style='padding:0.4rem 0; border-bottom:1px solid #22C55E;'>linha de conteudo real {i}"
        f" - ticker de exemplo PETR{i}</div>"
        for i in range(1, 7)
    )
    + "</div>",
    unsafe_allow_html=True,
)
st.markdown(f"ROTA={area_atual}/{sub_atual}")
