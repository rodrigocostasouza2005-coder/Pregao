# Harness visual LOCAL (sem login/auth/Supabase/rede) - exercita
# ui/top_mercado_tab.py (render_top_mercado), que so' escolhe REGIAO/SETOR
# e reusa o componente de lista de ui/news_tab.py (_renderizar_lista) - ver
# docstring do proprio modulo. Mocka as 3 funcoes de data/news.py que
# buscam os dados; o restante (selo/score/hora/fontes) e' renderizado pelo
# componente real de news_tab.py, sem mock.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.top_mercado_tab as top_mercado_tab

st.set_page_config(page_title="harness top mercado", layout="wide")
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


def _item(idx, titulo, ticker=None, regiao="BR"):
    return {
        "titulo": titulo, "link": f"https://exemplo.com/materia-{idx}",
        "data": "2026-11-11T09:30:00-03:00", "selo": "CONFIRMADA", "score": 9,
        "regras": ["veículo confiável", "2+ fontes"], "fontes_count": 3,
        "fontes": ["Valor Econômico", "InfoMoney", "Reuters"], "veiculos": ["Valor Econômico"],
        "importancia": 100 - idx, "criterio_ranking": ["3 fontes", "recente", "veículo confiável"],
        "regiao": regiao, "ticker": ticker, "tickers": [ticker] if ticker else [],
        "setores": [],
    }


_ITENS_BR = [_item(1, "Petrobras anuncia novo plano de investimentos", "PETR4"),
             _item(2, "Banco Central mantém Selic em reunião de novembro")]
_ITENS_INT = [_item(3, "Fed sinaliza corte de juros em dezembro", regiao="INT")]
_ITENS_TUDO = _ITENS_BR + _ITENS_INT

with patch.object(top_mercado_tab, "_BUSCADORES", {
    "BRASIL": lambda setor: _ITENS_BR,
    "INTERNACIONAL": lambda setor: _ITENS_INT,
    "TUDO": lambda setor: _ITENS_TUDO,
}):
    # sessao REAL do Streamlit (streamlit run, nao AppTest bare mode) - o
    # @st.fragment do proprio render_top_mercado executa normalmente, sem
    # precisar de .__wrapped__ (ver feedback_streamlit_fragment_bare_mode).
    top_mercado_tab.render_top_mercado({"watchlist": ["PETR4"]})
