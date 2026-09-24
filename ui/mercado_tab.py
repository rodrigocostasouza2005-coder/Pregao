# -*- coding: utf-8 -*-
"""Interface da aba MERCADO: visão ampla do pregão (não é sobre um papel
específico, ao contrário de EQUITY) - altas/baixas, mais negociados,
termômetro, mapa de calor setorial e mercados globais. Dados vêm de
data/mercado.py, sobre a lista curada de config.IBOVESPA_COMPOSICAO (não
é a composição oficial completa do índice - ver aviso fixo no topo da
aba e o comentário em config.py)."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from data.mercado import (
    obter_altas_baixas, obter_dados_treemap, obter_desempenho_setorial,
    obter_mais_negociados, obter_mercados_globais, obter_panorama_ibovespa, obter_termometro,
)
from ui import paineis


def _tema_atual(prefs):
    return config.TEMAS.get(prefs["tema"], config.TEMAS["AMBAR"])


def _fmt_pct(valor, prefs):
    sinal = "+" if valor >= 0 else ""
    return f"{sinal}{config.formatar_numero(valor, 2, prefs['formato_numerico'])}%"


def _layout_grafico_escuro(fig, tema, altura=340):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=tema["fundo"],
        plot_bgcolor=tema["fundo"],
        font=dict(color=tema["cinza"], family="IBM Plex Mono", size=11),
        height=altura,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    fig.update_xaxes(gridcolor="#1A1A1A")
    fig.update_yaxes(gridcolor="#1A1A1A")


def _painel_termometro(prefs):
    st.markdown('<div class="painel-titulo">MERCADO</div>', unsafe_allow_html=True)
    st.caption(
        "Baseado numa lista curada de blue chips de alta liquidez do Ibovespa "
        f"({len(config.IBOVESPA_COMPOSICAO)} papéis configurados) - não é a composição "
        "oficial completa do índice (~86 papéis, rebalanceada trimestralmente pela B3). "
        "Ver MANUAL.md."
    )
    term = obter_termometro()
    if term["total"] == 0:
        st.warning("Dados de mercado indisponíveis no momento (fonte fora do ar ou bloqueada).")
        return False

    tema = _tema_atual(prefs)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"<div style='text-align:center;'><div class='alta' style='font-size:1.6rem; font-weight:700;'>{term['alta']}</div>"
            f"<div class='cinza' style='font-size:0.7rem;'>EM ALTA</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div style='text-align:center;'><div class='baixa' style='font-size:1.6rem; font-weight:700;'>{term['baixa']}</div>"
            f"<div class='cinza' style='font-size:0.7rem;'>EM BAIXA</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div style='text-align:center;'><div class='neutro' style='font-size:1.6rem; font-weight:700;'>{term['estavel']}</div>"
            f"<div class='cinza' style='font-size:0.7rem;'>ESTÁVEIS</div></div>",
            unsafe_allow_html=True,
        )

    pct_alta = term["alta"] / term["total"] * 100
    pct_baixa = term["baixa"] / term["total"] * 100
    pct_estavel = 100 - pct_alta - pct_baixa
    st.markdown(
        f"<div style='display:flex; height:8px; margin-top:0.6rem; overflow:hidden;'>"
        f"<div style='width:{pct_alta:.1f}%; background:{tema['alta']};'></div>"
        f"<div style='width:{pct_estavel:.1f}%; background:{tema['cinza']};'></div>"
        f"<div style='width:{pct_baixa:.1f}%; background:{tema['baixa']};'></div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    return True


def _tabela_papeis(papeis, prefs, titulo):
    st.markdown(f"<div class='cinza' style='font-size:0.72rem; text-transform:uppercase; margin-bottom:0.2rem;'>{titulo}</div>", unsafe_allow_html=True)
    if not papeis:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    linhas = "".join(
        f"<tr><td style='padding:0.15rem 0.4rem 0.15rem 0;'>{p['ticker']}</td>"
        f"<td style='padding:0.15rem 0.4rem; text-align:right;' class='neutro'>R$ {config.formatar_numero(p['preco'], 2, prefs['formato_numerico'])}</td>"
        f"<td style='padding:0.15rem 0 0.15rem 0.4rem; text-align:right;' class='{"alta" if p["variacao_pct"] >= 0 else "baixa"}'>{_fmt_pct(p['variacao_pct'], prefs)}</td></tr>"
        for p in papeis
    )
    st.markdown(
        f"<table style='width:100%; font-size:0.8rem; border-collapse:collapse;'>{linhas}</table>",
        unsafe_allow_html=True,
    )


def _painel_altas_baixas(prefs):
    altas, baixas = obter_altas_baixas(10)
    c1, c2 = st.columns(2)
    with c1:
        _tabela_papeis(altas, prefs, "Maiores altas")
    with c2:
        _tabela_papeis(baixas, prefs, "Maiores baixas")


def _painel_mais_negociados(prefs):
    st.markdown('<div class="painel-titulo">MAIS NEGOCIADOS</div>', unsafe_allow_html=True)
    st.caption("Por volume financeiro estimado no dia (preço × volume em ações) - proxy de liquidez/atenção do mercado.")
    negociados = obter_mais_negociados(10)
    if not negociados:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    linhas = "".join(
        f"<tr><td style='padding:0.2rem 0.4rem 0.2rem 0;'>{p['ticker']}</td>"
        f"<td style='padding:0.2rem 0.4rem; text-align:right;' class='neutro'>R$ {config.formatar_numero(p['volume_financeiro'] / 1_000_000, 1, prefs['formato_numerico'])} mi</td>"
        f"<td style='padding:0.2rem 0 0.2rem 0.4rem; text-align:right;' class='{"alta" if p["variacao_pct"] >= 0 else "baixa"}'>{_fmt_pct(p['variacao_pct'], prefs)}</td></tr>"
        for p in negociados
    )
    st.markdown(
        f"<table style='width:100%; font-size:0.8rem; border-collapse:collapse;'>{linhas}</table>",
        unsafe_allow_html=True,
    )


def _painel_setorial(prefs):
    st.markdown('<div class="painel-titulo">DESEMPENHO SETORIAL</div>', unsafe_allow_html=True)
    setores = obter_desempenho_setorial()
    if not setores:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    tema = _tema_atual(prefs)
    df = pd.DataFrame(setores)
    cores = [tema["alta"] if v >= 0 else tema["baixa"] for v in df["variacao_media_pct"]]
    fig = go.Figure(go.Bar(
        x=df["variacao_media_pct"], y=df["setor"], orientation="h",
        marker_color=cores, text=df["variacao_media_pct"].map(lambda v: _fmt_pct(v, prefs)),
        textposition="outside",
    ))
    fig.update_yaxes(autorange="reversed")
    _layout_grafico_escuro(fig, tema, altura=max(240, 28 * len(setores)))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _painel_treemap(prefs):
    st.markdown('<div class="painel-titulo">MAPA DO MERCADO</div>', unsafe_allow_html=True)
    st.caption("Tamanho do retângulo = volume financeiro no dia · cor = variação % no dia.")
    df = obter_dados_treemap()
    if df.empty:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    tema = _tema_atual(prefs)
    limite = max(df["variacao_pct"].abs().max(), 0.5)
    fig = px.treemap(
        df, path=[px.Constant("IBOVESPA"), "setor", "ticker"], values="tamanho",
        color="variacao_pct", color_continuous_scale=[tema["baixa"], tema["cinza"], tema["alta"]],
        range_color=[-limite, limite],
    )
    fig.update_traces(texttemplate="%{label}<br>%{color:+.2f}%")
    fig.update_layout(
        paper_bgcolor=tema["fundo"], plot_bgcolor=tema["fundo"],
        font=dict(color=tema["neutro"], family="IBM Plex Mono", size=11),
        height=420, margin=dict(l=4, r=4, t=4, b=4), coloraxis_showscale=False,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _painel_globais(prefs):
    st.markdown('<div class="painel-titulo">MERCADOS GLOBAIS</div>', unsafe_allow_html=True)
    globais = obter_mercados_globais()
    if not globais:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    partes = []
    for g in globais:
        cls = "alta" if g["variacao_pct"] >= 0 else "baixa"
        partes.append(
            f"<div style='min-width:9rem;'><span class='cinza' style='font-size:0.7rem;'>{g['nome']}</span><br>"
            f"<span class='neutro' style='font-size:0.85rem;'>{config.formatar_numero(g['preco'], 0, prefs['formato_numerico'])}</span> "
            f"<span class='{cls}' style='font-size:0.78rem;'>{_fmt_pct(g['variacao_pct'], prefs)}</span></div>"
        )
    st.markdown(
        "<div style='display:flex; flex-wrap:wrap; gap:1rem;'>" + "".join(partes) + "</div>",
        unsafe_allow_html=True,
    )


# TERMOMETRO fica de fora do registro reordenavel de proposito: alem de
# ser o painel de abertura da aba, ele tambem funciona como "gate" (se
# nao tem dado nenhum, os outros 5 nem tentam renderizar - ver
# render_mercado). Os outros 5 sao os que fazem sentido reordenar (ver
# ui/paineis.py, adotado pela primeira vez aqui).
REGISTRO_PAINEIS = [
    ("altas_baixas", "Maiores altas/baixas", _painel_altas_baixas),
    ("mais_negociados", "Mais negociados", _painel_mais_negociados),
    ("setorial", "Desempenho setorial", _painel_setorial),
    ("treemap", "Mapa do mercado", _painel_treemap),
    ("globais", "Mercados globais", _painel_globais),
]


def render_mercado(prefs: dict):
    """Ponto de entrada da aba MERCADO, chamado pelo app.py."""
    with st.container(border=True):
        tem_dados = _painel_termometro(prefs)

    if not tem_dados:
        return

    # 1o prefs: pra paineis.renderizar calcular a ordem salva do usuario.
    # 2o prefs: repassado como argumento pra cada _painel_*(prefs) do
    # registro acima (todos tem essa mesma assinatura de 1 argumento).
    paineis.renderizar("MERCADO", REGISTRO_PAINEIS, prefs, prefs)
