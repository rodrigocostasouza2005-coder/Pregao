# Harness visual LOCAL (sem login/auth/Supabase/rede) - exercita
# ui/busca.py (buscar_ativo) e ui/paineis.py (renderizar, popover "⚙" de
# tamanho/visibilidade) com 2 paineis de exemplo, mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.busca as busca
import ui.paineis as paineis

st.set_page_config(page_title="harness busca+paineis", layout="wide")
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

_COMPOSICAO = {
    "PETR4": {"nome": "Petrobras"}, "VALE3": {"nome": "Vale"}, "ITUB4": {"nome": "Itau Unibanco"},
}

with patch("ui.busca.obter_composicao_oficial", return_value=_COMPOSICAO):
    st.markdown('<div class="painel-titulo">BUSCA DE ATIVO (ui/busca.py)</div>', unsafe_allow_html=True)
    busca.buscar_ativo("Buscar ativo", chave="harness_busca", extras=["PETR4"])

    st.markdown('<div class="painel-titulo" style="margin-top:1.2rem;">PAINEIS (ui/paineis.py)</div>', unsafe_allow_html=True)

    def _painel_a():
        st.markdown("<div class='cinza'>Conteúdo do painel A (exemplo)</div>", unsafe_allow_html=True)

    def _painel_b():
        st.markdown("<div class='cinza'>Conteúdo do painel B (exemplo)</div>", unsafe_allow_html=True)

    registro = [("a", "Painel A", _painel_a), ("b", "Painel B", _painel_b)]
    prefs = {"ordem_paineis": {}, "paineis_visiveis": {}, "tamanho_paineis": {"harness": {"a": "1/2", "b": "1/2"}}}
    paineis.renderizar("harness", registro, prefs)
