# Harness visual LOCAL (sem login/auth/Supabase) - exercita ui/navegacao.py
# (render_nav_principal + render_subnav) pra TODAS as 8 areas/29 subabas do
# registro AREAS real, sem mock de dado de nenhuma aba (navegacao.py e'
# puramente estrutural - nao renderiza conteudo de aba nenhuma). Mesmo
# padrao de docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py.
#
# Usado pela missao "experiencia/design system" (2026-11-11) pra auditar a
# nav principal (8 areas) + subnav (29 subabas) de uma vez, sem precisar de
# 29 harnesses de conteudo separados (o conteudo de cada aba e' testado nos
# harnesses especificos de cada modulo).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.navegacao as navegacao

st.set_page_config(page_title="harness nav", layout="wide")
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

# admin=True pra ver TODAS as 29 subabas (inclusive as 3 admin-only em MAIS)
areas = navegacao.disponiveis(config.ABAS_DISPONIVEIS, eh_admin=True)

area_id = navegacao.render_nav_principal(areas)
area = next(a for a in areas if a.id == area_id)
sub_id = navegacao.render_subnav(area)

st.markdown(
    f"<div class='painel-titulo' style='margin-top:1rem;'>{navegacao.rotulo_rota(area_id, sub_id)}</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div class='cinza' style='font-size:0.78rem;'>Harness so' da NAVEGACAO "
    "(ui/navegacao.py) - conteudo real de cada subaba fica nos harnesses "
    "especificos de cada modulo (radar/workspace/top-mercado/paineis).</div>",
    unsafe_allow_html=True,
)

st.caption(f"area_id={area_id} sub_id={sub_id} total_areas={len(areas)} "
           f"total_subs={sum(len(a.subabas) for a in areas)}")
