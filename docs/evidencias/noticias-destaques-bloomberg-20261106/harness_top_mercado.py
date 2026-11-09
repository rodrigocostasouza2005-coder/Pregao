# Harness visual LOCAL (sem login/auth) - valida a reformulacao de
# NOTICIAS > Destaques/Brasil/Internacional (ui/top_mercado_tab.py:
# render_top_mercado) direto, sem depender de login/Supabase/coleta real
# de RSS. Mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.top_mercado_tab as top_mercado_tab

st.set_page_config(page_title="harness top_mercado", layout="wide")
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

PREFS = {"formato_numerico": "BR", "watchlist": ["PETR4", "VALE3", "ITUB4"], "tema": "AMBAR"}

_ITENS_BRASIL = [
    {
        "titulo": "Petrobras anuncia novo plano de investimentos para 2027",
        "titulos": ["Petrobras anuncia novo plano de investimentos para 2027"],
        "veiculos": ["InfoMoney", "Valor Econômico", "Reuters Brasil"],
        "fontes": [
            {"veiculo": "InfoMoney", "link": "https://exemplo.com/petr4-1"},
            {"veiculo": "Valor Econômico", "link": "https://exemplo.com/petr4-2"},
            {"veiculo": "Reuters Brasil", "link": "https://exemplo.com/petr4-3"},
        ],
        "fontes_count": 3,
        "data": "2026-11-06T10:05:00-03:00",
        "link": "https://exemplo.com/petr4-1",
        "score": 92,
        "selo": "CONFIRMADA",
        "regras": ["3 veículos confiáveis"],
        "importancia": 980,
        "criterio_ranking": ["3 fontes", "veículo confiável", "tema de mercado"],
        "tickers": ["PETR4"],
        "setores": ["Petróleo e Gás"],
        "regiao": "BR",
        "ao_vivo": False,
    },
    {
        "titulo": "Banco Central eleva Selic em 0,25 p.p., para 11,75% ao ano",
        "titulos": ["Banco Central eleva Selic em 0,25 p.p., para 11,75% ao ano"],
        "veiculos": ["G1", "CNN Brasil"],
        "fontes": [
            {"veiculo": "G1", "link": "https://exemplo.com/selic-1"},
            {"veiculo": "CNN Brasil", "link": "https://exemplo.com/selic-2"},
        ],
        "fontes_count": 2,
        "data": "2026-11-06T09:40:00-03:00",
        "link": "https://exemplo.com/selic-1",
        "score": 78,
        "selo": "PROVÁVEL",
        "regras": ["2 veículos"],
        "importancia": 860,
        "criterio_ranking": ["2 fontes", "recência alta"],
        "tickers": [],
        "setores": ["Macro"],
        "regiao": "BR",
        "ao_vivo": False,
    },
    {
        "titulo": "Vale eleva produção de minério de ferro no trimestre",
        "titulos": ["Vale eleva produção de minério de ferro no trimestre"],
        "veiculos": ["Valor Econômico"],
        "fontes": [{"veiculo": "Valor Econômico", "link": "https://exemplo.com/vale3-1"}],
        "fontes_count": 1,
        "data": "2026-11-05T19:00:00-03:00",
        "link": "https://exemplo.com/vale3-1",
        "score": 40,
        "selo": "NÃO CONFIRMADA",
        "regras": ["1 veículo"],
        "importancia": 520,
        "criterio_ranking": ["1 fonte"],
        "tickers": ["VALE3"],
        "setores": ["Mineração"],
        "regiao": "BR",
        "ao_vivo": False,
    },
]

_ITENS_INTL = [
    {
        "titulo": "Fed sinaliza corte de juros na próxima reunião",
        "titulos": ["Fed sinaliza corte de juros na próxima reunião"],
        "veiculos": ["Reuters", "CNBC"],
        "fontes": [
            {"veiculo": "Reuters", "link": "https://exemplo.com/fed-1"},
            {"veiculo": "CNBC", "link": "https://exemplo.com/fed-2"},
        ],
        "fontes_count": 2,
        "data": "2026-11-06T08:15:00-03:00",
        "link": "https://exemplo.com/fed-1",
        "score": 88,
        "selo": "CONFIRMADA",
        "regras": ["2 veículos confiáveis"],
        "importancia": 910,
        "criterio_ranking": ["2 fontes", "veículo confiável"],
        "tickers": [],
        "setores": ["Macro"],
        "regiao": "INT",
        "ao_vivo": False,
    },
    {
        "titulo": "Apple anuncia recompra recorde de ações após resultado",
        "titulos": ["Apple anuncia recompra recorde de ações após resultado"],
        "veiculos": ["MarketWatch"],
        "fontes": [{"veiculo": "MarketWatch", "link": "https://exemplo.com/aapl-1"}],
        "fontes_count": 1,
        "data": "2026-11-06T07:50:00-03:00",
        "link": "https://exemplo.com/aapl-1",
        "score": 55,
        "selo": "SUSPEITA",
        "regras": ["1 veículo", "linguagem promocional"],
        "importancia": 430,
        "criterio_ranking": ["1 fonte"],
        "tickers": [],
        "setores": ["Tecnologia"],
        "regiao": "INT",
        "ao_vivo": False,
    },
]

_ITENS_TUDO = _ITENS_BRASIL + _ITENS_INTL


def _top_mercado(setor="TODOS"):
    return _ITENS_BRASIL


def _top_mercado_intl(setor="TODOS"):
    return _ITENS_INTL


def _top_mercado_tudo(setor="TODOS"):
    return sorted(_ITENS_TUDO, key=lambda n: n["importancia"], reverse=True)


params = st.query_params
regiao = params.get("regiao", "TUDO")
titulo = {"TUDO": "DESTAQUES", "BRASIL": "BRASIL", "INTERNACIONAL": "INTERNACIONAL"}[regiao]

# render_top_mercado real (nao .__wrapped__): este harness roda dentro de
# uma sessao Streamlit real via `streamlit run` + Playwright, nao em modo
# bare/AppTest - @st.fragment funciona normalmente aqui (ver
# feedback_streamlit_fragment_bare_mode, que so se aplica a chamada fora
# de sessao real).
#
# IMPORTANTE: render_top_mercado busca a funcao de coleta por
# `_BUSCADORES[regiao]` - esse dict e' montado UMA VEZ no import do modulo
# (`_BUSCADORES = {"BRASIL": obter_top_mercado, ...}`), guardando o OBJETO
# funcao direto. Dar patch.object em `top_mercado_tab.obter_top_mercado*`
# troca so' o atributo do modulo, nao o valor ja' capturado dentro do
# dict - por isso o patch tem que mirar `_BUSCADORES` em si (achado real
# ao montar este harness: sem isso a 1ª tentativa acabou chamando as
# funcoes REAIS, que bateram no Google News de verdade).
with patch.dict(
    top_mercado_tab._BUSCADORES,
    {"BRASIL": _top_mercado, "INTERNACIONAL": _top_mercado_intl, "TUDO": _top_mercado_tudo},
):
    top_mercado_tab.render_top_mercado(PREFS, regiao_fixa=regiao, titulo=titulo)
