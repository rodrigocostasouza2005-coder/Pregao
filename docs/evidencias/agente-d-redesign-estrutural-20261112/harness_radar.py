# Harness visual LOCAL (sem login/auth, sem Supabase real) para validar o
# redesign ESTRUTURAL de RADAR > Oportunidades/Acompanhamento (Agente D,
# 2026-11-12) - mesmo padrão de harness_coordenador.py neste mesmo
# diretório. As funções de SEÇÃO (_secao_mudancas_tese/_secao_catalisadores/
# _secao_evidencias/_secao_risco) são substituídas por fakes que só
# desenham algumas linhas HTML representativas - o que este harness precisa
# confirmar é a GRADE/composição ao redor delas (ui/radar_tab.py:
# render_radar_oportunidades/render_radar_acompanhamento), não a lógica de
# cálculo real dessas seções (coberta por tests/test_radar_tab*.py, não
# tocada por esta missão).
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.radar_tab as radar_tab
from data import radar_quedas as rq_mod

ABA = sys.argv[1] if len(sys.argv) > 1 else "oportunidades"

st.set_page_config(page_title=f"harness radar - {ABA}", layout="wide")
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
PREFS["watchlist"] = ["PETR4", "VALE3", "ITUB4", "MGLU3", "WEGE3"]


def _fake_mudancas_tese(tickers, janela, prefs):
    st.markdown('<div class="radar-pergunta">O QUE MUDOU?</div>', unsafe_allow_html=True)
    linhas = [
        ("PETR4", "XP revisou preço-alvo de R$ 40,00 para R$ 44,00 (+10,0%)", "há 2 dias"),
        ("VALE3", "Fato relevante CVM: aprovação de programa de recompra de ações", "há 5 dias"),
        ("MGLU3", "Genial rebaixou recomendação de NEUTRO para VENDA", "há 6 dias"),
    ]
    for ticker, texto, quando in linhas:
        st.markdown(
            f"<div class='radar-alerta'><div class='radar-alerta-topo'>"
            f"<span class='radar-ticker'>{ticker}</span><span class='radar-categoria'>{quando}</span></div>"
            f"<div class='radar-descricao'>{texto}</div></div>",
            unsafe_allow_html=True,
        )


def _fake_catalisadores(tickers):
    linhas = [
        ("PETR4", "Resultado trimestral", "15/11/2026"),
        ("VALE3", "Pagamento de proventos", "22/11/2026"),
        ("ITUB4", "Resultado trimestral (estimado)", "05/12/2026"),
    ]
    for ticker, categoria, data in linhas:
        st.markdown(
            f"<div class='radar-alerta'><div class='radar-alerta-topo'>"
            f"<span><span class='radar-ticker'>{ticker}</span> <span class='radar-categoria'>{categoria}</span></span>"
            f"<span style='color:var(--destaque); font-size:0.68rem;'>● ESTIMADO</span></div>"
            f"<div class='radar-meta'>{data}</div></div>",
            unsafe_allow_html=True,
        )


def _fake_evidencias(tickers, watchlist):
    linhas = [
        ("PETR4", "Petrobras anuncia novo plano de investimentos para 2027", "há 1 dia"),
        ("VALE3", "Vale eleva produção de minério de ferro no trimestre", "há 3 dias"),
    ]
    for ticker, titulo, quando in linhas:
        st.markdown(
            f"<div class='radar-alerta'><div class='radar-alerta-topo'>"
            f"<span><span class='radar-ticker'>{ticker}</span></span>"
            f"<span class='radar-categoria'>{quando}</span></div>"
            f"<div class='radar-descricao'>{titulo}</div></div>",
            unsafe_allow_html=True,
        )


def _fake_risco(prefs, sub):
    st.markdown(
        "<div class='rq-nota'>2 posições cadastradas · exposição total R$ 48.200,00 · "
        "concentração máxima: PETR4 (38,4% da carteira).</div>",
        unsafe_allow_html=True,
    )


def _sem_fragment(fn):
    """@st.fragment nao executa o corpo em modo bare (fora de uma sessao
    Streamlit real) - achado ja documentado em sessoes anteriores
    (MEMORY.md: "st.fragment em bare mode nao executa"). `.__wrapped__`
    chama a funcao original, sem o wrapper de fragment."""
    return getattr(fn, "__wrapped__", fn)


def _ir():
    if ABA == "oportunidades":
        _sem_fragment(radar_tab.render_radar_oportunidades)(PREFS)
    elif ABA == "acompanhamento":
        _sem_fragment(radar_tab.render_radar_acompanhamento)(PREFS, {"sub": "usuario-mock"})
    else:
        raise SystemExit(f"aba desconhecida: {ABA}")


_ALERTAS_90D = [
    {"ticker": "MGLU3", "data_alerta": "2026-11-01", "preco_alerta": 2.05, "variacao_pct": -6.1,
     "email_status": "ENVIADO", "casas": ["Genial"]},
]

with patch.object(radar_tab, "_secao_mudancas_tese", side_effect=_fake_mudancas_tese), \
     patch.object(radar_tab, "_secao_catalisadores", side_effect=_fake_catalisadores), \
     patch.object(radar_tab, "_secao_evidencias", side_effect=_fake_evidencias), \
     patch.object(radar_tab, "_secao_risco", side_effect=_fake_risco), \
     patch.object(rq_mod, "alertas_periodo", return_value=_ALERTAS_90D), \
     patch.object(radar_tab, "_tabela_alertas_html", return_value="<table class='rq-tabela'><tr><td>MGLU3</td><td>-6,1%</td></tr></table>"):
    _ir()
