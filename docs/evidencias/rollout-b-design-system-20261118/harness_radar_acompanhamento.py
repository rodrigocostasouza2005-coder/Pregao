# Harness visual LOCAL ad-hoc (sem login/auth/Supabase real) para
# confirmar que ui/radar_tab.py:render_radar_acompanhamento continua
# renderizando corretamente apos a migracao de _classe_var pra
# design_system.classe_sinal (missao "rollout B" do design system,
# 2026-11-18) - mesmo padrao dos harnesses salvos em
# docs/evidencias/validacao-visual-real-20261117/ (streamlit run +
# Playwright real via shot.py daquela mesma pasta), exercitando de
# proposito _linha_posicao_gerenciar com 1 posicao de lucro positivo
# (deve sair "rq-alta") e 1 de lucro negativo (deve sair "rq-baixa") -
# exatamente o codigo mudado nesta PR.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

import config
import ui.radar_tab as radar_tab
from data import posicoes as posicoes_mod
from data import radar

st.set_page_config(page_title="harness radar - acompanhamento", layout="wide")
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
PREFS["watchlist"] = ["PETR4", "VALE3"]
USUARIO = {"sub": "harness-user", "email": "harness@local"}

_POSICOES = [
    {"ticker": "PETR4", "quantidade": 100, "preco_medio": 30.0},
    {"ticker": "VALE3", "quantidade": 50, "preco_medio": 66.0},
]
_RISCO = {
    "carteira_cadastrada": False,
    "motivo": "Carteira de risco simulada - ignorada neste harness (só confirma a cor/alinhamento das linhas de posição acima).",
    "posicoes": [
        {"ticker": "PETR4", "lucro_pct": 12.5},
        {"ticker": "VALE3", "lucro_pct": -6.3},
    ],
}

with patch.object(posicoes_mod, "obter_posicoes", return_value=_POSICOES), \
     patch.object(radar, "risco_carteira", return_value=_RISCO), \
     patch("data.radar_quedas.alertas_periodo", return_value=[]):
    radar_tab.render_radar_acompanhamento(PREFS, USUARIO)
