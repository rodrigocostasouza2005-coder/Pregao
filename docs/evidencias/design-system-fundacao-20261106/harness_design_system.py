# Harness visual LOCAL (sem login/auth) - valida a fundação do design
# system (ui/design_system.py + classes novas em style.css) direto, sem
# depender de nenhuma aba inteira. Segue o mesmo padrão de harness isolado
# já usado em docs/evidencias/imagens-news-20261019/harness_visual.py.
import streamlit as st

import config
import ui.design_system as ds
import ui.mercado_tab as mt

st.set_page_config(page_title="harness design system", layout="wide")
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

PREFS = {"formato_numerico": "BR"}

ds.subtitulo("SUBTITULO DE SECAO (ja existia)")

with st.container(border=True):
    st.markdown('<div class="painel-titulo">NUMERO FINANCEIRO ALINHADO (novo)</div>', unsafe_allow_html=True)
    linhas = [
        ("PETR4", 36.52, 3.14),
        ("VALE3", 71.8, -1.02),
        ("ITUB4", 158400.0, 0.0),
        ("MGLU3", 2.11, -12.47),
    ]
    tabela_html = "<div style='display:flex; flex-direction:column; width:16rem;'>"
    for ticker, preco, var_pct in linhas:
        tabela_html += (
            f"<div style='display:flex; justify-content:space-between; padding:0.15rem 0;'>"
            f"<span class='neutro'>{ticker}</span>"
            f"{ds.numero_financeiro_html(preco, 2, PREFS['formato_numerico'])}"
            f"<span>{ds.variacao_html(var_pct, PREFS['formato_numerico'])}</span>"
            f"</div>"
        )
    tabela_html += "</div>"
    st.markdown(tabela_html, unsafe_allow_html=True)

ds.divisor()

with st.container(border=True):
    st.markdown('<div class="painel-titulo">INDICADOR POSITIVO/NEGATIVO (classe_sinal)</div>', unsafe_allow_html=True)
    st.markdown(
        f"<span class='{ds.classe_sinal(3.1)}'>ALTA (classe_sinal(3.1) = '{ds.classe_sinal(3.1)}')</span>"
        f" &nbsp;|&nbsp; "
        f"<span class='{ds.classe_sinal(-3.1)}'>BAIXA (classe_sinal(-3.1) = '{ds.classe_sinal(-3.1)}')</span>",
        unsafe_allow_html=True,
    )

ds.divisor()

with st.container(border=True):
    st.markdown('<div class="painel-titulo">DENSIDADE COMPACTA (.ds-compacto)</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='ds-compacto'>"
        + "".join(f"<div class='neutro'>Linha densa {i} - item de feed/ranking</div>" for i in range(5))
        + "</div>",
        unsafe_allow_html=True,
    )

ds.divisor()

with st.container(border=True):
    st.markdown(
        '<div class="painel-titulo">PROVA DE CONCEITO: ui/mercado_tab.py:_item_ticker_html '
        "refatorada p/ usar design_system</div>",
        unsafe_allow_html=True,
    )
    linha = "".join([
        mt._item_ticker_html("IBOVESPA", 136000.0, 0.82, 0, PREFS),
        mt._item_ticker_html("DÓLAR", 5.42, -0.31, 2, PREFS),
        mt._item_ticker_html("S&P 500", 6800.1, 0.0, 0, PREFS),
        mt._item_ticker_html("SEM DADO", None, None, 2, PREFS),
    ])
    st.markdown(f"<div style='display:flex;'>{linha}</div>", unsafe_allow_html=True)
