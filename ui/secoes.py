# -*- coding: utf-8 -*-
"""Subabas do PREGAO 2.0 (ui/navegacao.py) que sao so' composicao de
paineis ja existentes, sem modulo proprio: MERCADO > Mercados Globais e
Agenda, atalhos da Visao Geral e MAIS > Watchlist. Nenhum dado novo -
mesmas funcoes/caches dos paineis de origem."""

import streamlit as st

import config
from ui import navegacao
from ui.calendario_tab import render_calendario
from ui.macro_tab import _painel_cenario_global
from ui.mercado_tab import _painel_globais
from ui.visao_geral import _painel_watchlist_compacta


def render_atalhos_visao_geral():
    """Fluxo central do produto (mercado -> movimento -> motivo -> ativo
    -> acompanhar) como atalhos de uma linha, abaixo do workspace da
    Visao Geral (que continua personalizavel e intocado)."""
    atalhos = [
        ("Alertas do Radar", "radar", "alertas"), ("Notícias em destaque", "noticias", "destaques"),
        ("Agenda", "mercado", "agenda"), ("Mapa setorial", "setores", "mapa"),
        ("Morning Call", "morning-call", "edicao"),
    ]
    with st.container(key="vg_atalhos"):
        cols = st.columns(len(atalhos))
        for col, (rotulo, area, sub) in zip(cols, atalhos):
            with col:
                navegacao.link(f"{rotulo} ↗", area, sub, chave=f"vg_atalho_{area}_{sub}", width="stretch")


def render_mercados_globais(prefs: dict):
    with st.container(border=True):
        _painel_globais(prefs)
        st.caption("Índices e futuros internacionais — Yahoo Finance, com atraso típico de mercado.")
    with st.container(border=True):
        _painel_cenario_global(prefs)
    # achado real (auditoria "missao master" 2026-10-31): sem margem
    # superior, este texto colava direto na borda do container acima
    # (cuja ultima linha interna e' outra legenda em cinza do mesmo
    # tamanho) - as duas legendas visualmente se fundiam/sobrepunham.
    st.markdown(
        "<div class='cinza' style='font-size:0.72rem; margin-top:0.6rem;'>Relação com o Brasil: commodities "
        "(petróleo, minério) pesam em PETR/VALE e no câmbio; Treasuries e VIX medem o apetite global por risco. "
        "Leitura geral, não sinal de negociação.</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    with cols[0]:
        navegacao.link("Câmbio e commodities ↗", "macro", "cambio", chave="glob_cambio", width="stretch")
    with cols[1]:
        navegacao.link("Notícias internacionais ↗", "noticias", "internacional", chave="glob_news", width="stretch")


def render_agenda(prefs: dict):
    st.markdown(
        "<div class='cinza' style='font-size:0.72rem; margin-bottom:0.3rem;'>Resultados corporativos (datas "
        "confirmadas, estimadas ou prazo CVM — o status de cada data vem indicado). Eventos econômicos e "
        "decisões de bancos centrais: MACRO › Calendário Econômico.</div>",
        unsafe_allow_html=True,
    )
    render_calendario(prefs)


def render_watchlist(prefs: dict):
    with st.container(border=True):
        _painel_watchlist_compacta(prefs)
        st.caption("Adicione ou remova tickers pela barra lateral (WATCHLIST) ou pela busca global no topo.")
    watchlist = prefs.get("watchlist") or []
    if watchlist:
        cols = st.columns(min(len(watchlist), 6))
        for i, t in enumerate(watchlist):
            with cols[i % len(cols)]:
                navegacao.link(t, "analises", "empresas", chave=f"wl_abrir_{t}", ticker=t, width="stretch",
                               ajuda=f"Abrir {config.TICKER_NOME.get(t, t)} em ANÁLISES › Empresas")
