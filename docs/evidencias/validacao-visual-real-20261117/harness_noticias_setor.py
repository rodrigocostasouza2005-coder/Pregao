# Harness visual LOCAL (sem login/auth/Supabase/rede real) - Fase 4
# (revalidacao pos-reestruturacao, 2026-11-18): NOTICIAS > Visao por Setor
# (ui/setores_tab.py:render_visao_setor), subaba NOVA nesta area - antes
# vivia na area SETORES (dissolvida no PR #328). Mesma funcao de sempre,
# so' a area que hospeda mudou. Mocka obter_cotacoes_lote (tabela
# EMPRESAS DO SETOR) e _BUSCADORES de ui/top_mercado_tab.py (usado
# internamente por render_visao_setor pra montar a coluna de noticias do
# setor) - taxonomia real (data/news_setores.SETORES) e texto editorial
# real (data/radar_setorial.CATALOGO) NAO mockados (sao dado estatico do
# projeto, sem rede).
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.setores_tab as setores_tab
import ui.top_mercado_tab as top_mercado_tab

st.set_page_config(page_title="harness noticias - visao por setor", layout="wide")
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
st.markdown("<style>body{background:var(--bg);} .stApp{background:var(--bg);}</style>", unsafe_allow_html=True)

PREFS = dict(config.PREFS_PADRAO)
PREFS["watchlist"] = ["PETR4", "VALE3", "PRIO3"]
PREFS["formato_numerico"] = "BR"

_COTACOES = {
    "PETR4": {"preco": 36.52, "variacao_pct": 3.14, "erro": None},
    "PRIO3": {"preco": 42.10, "variacao_pct": 5.8, "erro": None},
    "CSAN3": {"preco": 11.20, "variacao_pct": 2.9, "erro": None},
}


def _item(idx, titulo, ticker=None):
    return {
        "titulo": titulo, "link": f"https://exemplo.com/materia-{idx}",
        "data": "2026-11-17T09:30:00-03:00", "selo": "CONFIRMADA", "score": 9,
        "regras": ["veículo confiável"], "fontes_count": 3,
        "fontes": ["Valor Econômico"], "veiculos": ["Valor Econômico"],
        "importancia": 100 - idx, "criterio_ranking": ["recente"],
        "regiao": "BR", "ticker": ticker, "tickers": [ticker] if ticker else [], "setores": [],
    }


_ITENS_SETOR = [_item(1, "Petrobras anuncia novo plano de investimentos para 2027", "PETR4"),
                _item(2, "PRIO eleva produção após nova aquisição de campo maduro", "PRIO3")]

with patch.object(setores_tab, "obter_cotacoes_lote", return_value=_COTACOES), \
     patch.object(top_mercado_tab, "_BUSCADORES", {
         "BRASIL": lambda setor: _ITENS_SETOR,
         "INTERNACIONAL": lambda setor: [],
         "TUDO": lambda setor: _ITENS_SETOR,
     }):
    setores_tab.render_visao_setor(PREFS)
