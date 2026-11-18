# Harness visual LOCAL (sem login/auth/Supabase/rede real) - Fase 4
# (revalidacao pos-reestruturacao, 2026-11-18): RESEARCH > Morning Call:
# Edicao Atual (ui/morning_call_tab.py:render_edicao_atual) - MORNING
# CALL deixou de ser area propria de 1o nivel e virou 4 subabas de
# RESEARCH (PR #329); mesma funcao de sempre, so' a area que hospeda
# mudou. Mocka listar_edicoes/obter_sintese_mercado/
# alertas_confiabilidade - as 2 secoes atras de expander/botao (jornal
# completo ao vivo, edicao oficial) ficam fechadas por padrao, igual
# produção - nao forcadas abertas aqui (zero chamada de rede real).
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.morning_call_tab as mc

st.set_page_config(page_title="harness morning call - edicao atual", layout="wide")
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
PREFS["watchlist"] = ["PETR4", "VALE3", "ITUB4"]

_TZ_SP = ZoneInfo("America/Sao_Paulo")
_AGORA = datetime.now(_TZ_SP)

# Shape real de data/morning_call_historico.py:listar_edicoes - "data" e'
# um date (nao string), "executado_em" um datetime com tz (ver
# _cabecalho_edicao, que chama .strftime/.astimezone direto nos dois).
_EDICOES = [
    {
        "data": _AGORA.date(), "status": "ENVIADA",
        "executado_em": _AGORA - timedelta(hours=3),
        "conteudo": "Edição de hoje — Ibovespa abre em alta puxado por petroleiras.",
    },
]

_SINTESE = {
    "ok": True,
    "gerado_em": (_AGORA - timedelta(minutes=12)).isoformat(),
    "atual": True,
    "dados": {
        "resumo_executivo": {
            "texto": "Ibov sobe puxado por petroleiras, com Petrobras e PRIO liderando ganhos; Varejo "
                     "segue pressionado por revisão de guidance da Magazine Luiza."
        },
        "movimentos": [
            {"evento": "Petrobras sobe com alta do petróleo Brent acima de US$ 86", "fonte": "Valor Econômico"},
        ],
        "oportunidades_riscos": [
            {"ativo_ou_setor": "Petróleo e Gás", "argumento_favoravel": "Brent em alta sustenta margens.",
             "argumento_contrario": "Risco cambial pode reverter ganho em reais."},
        ],
        "cenarios": [
            {"tipo": "principal", "cenario": "Ibovespa sustenta alta puxado por commodities",
             "sinalizadores": "Brent > US$ 85, dólar estável"},
        ],
    },
}

with patch.object(mc, "listar_edicoes", return_value=_EDICOES), \
     patch.object(mc, "obter_sintese_mercado", return_value=_SINTESE), \
     patch.object(mc, "alertas_confiabilidade", return_value=[]):
    mc.render_edicao_atual(PREFS)
