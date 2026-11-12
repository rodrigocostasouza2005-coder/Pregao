# Harness visual LOCAL (sem login/auth/Supabase) - replica so' o BLOCO que
# foi alterado em app.py (sidebar "WATCHLIST", linha do card por ticker
# dentro de _fragmento_watchlist) pra validar visualmente a troca do
# cls/sinal manual por design_system.variacao_html(). app.py em si roda
# via "with st.sidebar:" no modulo principal (precisa de login real/
# Supabase pra rodar completo) - este harness isola so' o HTML gerado por
# aquele trecho, usando o MESMO helper real (ui/design_system.py), nao uma
# reimplementacao.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.design_system as design_system

st.set_page_config(page_title="harness sidebar watchlist", layout="wide")
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

_COTACOES = {
    "PETR4": {"preco": 36.52, "variacao_pct": 3.14, "nome": "Petrobras"},
    "VALE3": {"preco": 71.80, "variacao_pct": -1.02, "nome": "Vale"},
    "ITUB4": {"preco": 34.21, "variacao_pct": 0.0, "nome": "Itau Unibanco"},
    "MGLU3": {"preco": None, "variacao_pct": None, "nome": "Magazine Luiza", "erro": "sem dado"},
}

with st.sidebar:
    st.markdown('<div class="painel-titulo">WATCHLIST</div>', unsafe_allow_html=True)
    for t, cot in _COTACOES.items():
        if cot.get("erro"):
            var_html = "<span class='cinza'>--</span>"
        else:
            # mesma chamada introduzida em app.py:_fragmento_watchlist
            var_html = design_system.variacao_html(cot["variacao_pct"], "BR")
        col_info, col_remover = st.columns([4, 1])
        col_info.markdown(
            f"<div style='padding-bottom:0.35rem; margin-bottom:0.35rem; border-bottom:1px solid var(--borda);'>"
            f"<div style='display:flex; justify-content:space-between; align-items:baseline;'>"
            f"<span style='color:var(--destaque); font-weight:600;'>{t}</span>{var_html}</div>"
            f"<div class='cinza' style='font-size:0.66rem; margin-top:0.1rem;'>{cot['nome']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        col_remover.button("x", key=f"remover_{t}")
