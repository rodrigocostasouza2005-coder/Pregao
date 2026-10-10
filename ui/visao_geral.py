# -*- coding: utf-8 -*-
"""Aba "0 VISÃO GERAL" - home do PREGÃO (redesign do terminal, ver
PROGRESSO.md). Objetivo: em ~10 segundos, entender o que está
acontecendo no mercado. NÃO tem coleta/lógica de dado própria - é
composição de painéis/funções que já existem em outras abas (MERCADO,
MACRO, NEWS), reaproveitados diretamente (mesmo cache, sem nenhuma
consulta nova). Onde a função original já é "pesada demais" pra um
resumo (a lista completa de notícias, por exemplo), usa a mesma função
de dado com um limite de itens menor, não uma cópia da lógica."""

import plotly.graph_objects as go
import streamlit as st

import config
from data.ibovespa import obter_composicao_oficial
from data.macro import obter_cdi
from data.mercado import obter_cotacoes_lote, obter_mercados_globais
from data.news import obter_top_mercado_tudo
from data.prices import obter_cotacao, obter_cotacao_indice, obter_historico, obter_historico_intraday
from ui import graficos, workspace
from ui.mercado_tab import _painel_altas_baixas, _painel_globais, _painel_mais_negociados, _painel_setorial
from ui.news_tab import _injetar_css, _renderizar_lista

_PERIODOS_IBOV = ["1D", "1S", "1M", "3M", "6M", "1A", "5A"]
_QTD_NOTICIAS = 8


def _tema_atual(prefs):
    return config.TEMAS.get(prefs["tema"], config.TEMAS["AMBAR"])


def _fmt_pct(valor, prefs):
    sinal = "+" if valor >= 0 else ""
    return f"{sinal}{config.formatar_numero(valor, 2, prefs['formato_numerico'])}%"


def _card_mercado(rotulo: str, preco, variacao_pct, prefs, casas_preco: int = 2):
    if preco is None or variacao_pct is None:
        st.markdown(
            f"<div style='padding:0.4rem 0.6rem; border:1px solid var(--borda);'>"
            f"<div class='cinza' style='font-size:0.68rem;'>{rotulo}</div>"
            f"<div class='cinza' style='font-size:0.95rem;'>—</div></div>",
            unsafe_allow_html=True,
        )
        return
    cls = "alta" if variacao_pct >= 0 else "baixa"
    st.markdown(
        f"<div style='padding:0.4rem 0.6rem; border:1px solid var(--borda);'>"
        f"<div class='cinza' style='font-size:0.68rem;'>{rotulo}</div>"
        f"<div class='neutro' style='font-size:0.95rem; font-weight:600;'>{config.formatar_numero(preco, casas_preco, prefs['formato_numerico'])}</div>"
        f"<div class='{cls}' style='font-size:0.78rem;'>{_fmt_pct(variacao_pct, prefs)}</div></div>",
        unsafe_allow_html=True,
    )


def _painel_mercado_agora(prefs):
    st.markdown('<div class="painel-titulo">MERCADO AGORA</div>', unsafe_allow_html=True)
    # achado real (2026-10-08): VISAO GERAL reaproveita _painel_altas_baixas/
    # _painel_setorial de ui/mercado_tab.py, mas NAO _painel_termometro -
    # que e' onde mora o unico aviso visivel de "B3 indisponivel, usando
    # lista curada de fallback". Quem so' abre a VISAO GERAL nunca via
    # esse aviso e nunca saberia que a base mudou. Mesma checagem
    # (barata, cacheada) exposta aqui pra nao degradar silenciosamente.
    if not obter_composicao_oficial():
        st.caption(
            f"B3 indisponível no momento - altas/baixas e desempenho setorial usam lista curada de "
            f"fallback ({len(config.IBOVESPA_SETORES)} papéis)."
        )
    globais = {g["nome"]: g for g in obter_mercados_globais()}
    cdi_df = obter_cdi(dias_historico=5)
    cdi_atual = float(cdi_df["cdi_anualizado_pct"].iloc[-1]) if cdi_df is not None and not cdi_df.empty else None
    # variacao real (p.p.) entre a ultima leitura e a anterior do CDI
    # anualizado - achado real (2026-10-08): antes era "0.0" fixo (nunca
    # calculado), fazendo o card sempre pintar verde e mostrar "+0,00%"
    # mesmo quando a taxa de fato mudou no dia. None (nunca 0.0) quando
    # so' ha' 1 leitura - sem dado suficiente pra comparar, o card mostra
    # "—" (ver _card_mercado), nunca uma variacao inventada.
    cdi_variacao = None
    if cdi_df is not None and len(cdi_df) >= 2:
        anterior = float(cdi_df["cdi_anualizado_pct"].iloc[-2])
        cdi_variacao = cdi_atual - anterior if cdi_atual is not None else None

    ibov = obter_cotacao_indice("IBOVESPA", "^BVSP")
    dolar = obter_cotacao_indice("DOLAR", "USDBRL=X")
    petr4 = obter_cotacao("PETR4")
    vale3 = obter_cotacao("VALE3")

    with st.container(key="visao_geral_mercado_agora_cols"):
        cols = st.columns(7)
        with cols[0]:
            _card_mercado("IBOV", None if ibov.get("erro") else ibov["preco"], None if ibov.get("erro") else ibov["variacao_pct"], prefs, 0)
        with cols[1]:
            _card_mercado("DÓLAR", None if dolar.get("erro") else dolar["preco"], None if dolar.get("erro") else dolar["variacao_pct"], prefs)
        with cols[2]:
            _card_mercado("DI (CDI anual.)", cdi_atual, cdi_variacao, prefs)
        with cols[3]:
            sp500 = globais.get("S&P 500")
            _card_mercado("S&P 500", sp500["preco"] if sp500 else None, sp500["variacao_pct"] if sp500 else None, prefs, 0)
        with cols[4]:
            nasdaq = globais.get("Nasdaq")
            _card_mercado("NASDAQ", nasdaq["preco"] if nasdaq else None, nasdaq["variacao_pct"] if nasdaq else None, prefs, 0)
        with cols[5]:
            _card_mercado("PETR4", None if petr4.get("erro") else petr4["preco"], None if petr4.get("erro") else petr4["variacao_pct"], prefs)
        with cols[6]:
            _card_mercado("VALE3", None if vale3.get("erro") else vale3["preco"], None if vale3.get("erro") else vale3["variacao_pct"], prefs)


def _painel_ibov_grafico(prefs):
    st.markdown('<div class="painel-titulo">IBOVESPA</div>', unsafe_allow_html=True)
    tema = _tema_atual(prefs)

    padrao = st.session_state.get("vg_periodo_ibov_valido", "6M")
    if padrao not in _PERIODOS_IBOV:
        padrao = "6M"
    sel = st.segmented_control(
        "Período", _PERIODOS_IBOV, default=padrao, label_visibility="collapsed", key="vg_periodo_ibov",
    )
    periodo = sel or padrao
    st.session_state["vg_periodo_ibov_valido"] = periodo

    # causa raiz real (2026-10-08): _PERIODOS_IBOV inclui "1D"/"1S", mas so'
    # PERIODOS_GRAFICO (periodos diarios/semanais) tem esses rotulos - os
    # intradiarios sao' outra tabela (PERIODOS_INTRADIARIOS / obter_historico_
    # intraday), igual ja' tratado no grafico de MERCADO (app.py). Sem esse
    # branch, selecionar "1D"/"1S" aqui ia pra obter_historico() e estourava
    # KeyError em PERIODOS_GRAFICO[periodo_label] (data/prices.py).
    if periodo in config.PERIODOS_INTRADIARIOS:
        df = obter_historico_intraday(config.SIMBOLO_IBOVESPA, periodo)
    else:
        df = obter_historico(config.SIMBOLO_IBOVESPA, periodo)
    if df is None or df.empty:
        st.warning("Não foi possível obter o histórico do Ibovespa.")
        return

    fig = go.Figure(go.Scatter(
        x=df["Data"], y=df["Close"], mode="lines",
        line=dict(color=tema["destaque"], width=1.8), fill="tozeroy",
        fillcolor=tema["destaque"] + "18",
    ))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=tema["fundo"], plot_bgcolor=tema["fundo"],
        font=dict(color=tema["cinza"], family="IBM Plex Mono", size=11),
        height=320, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
    )
    fig.update_xaxes(gridcolor="#1A1A1A")
    fig.update_yaxes(gridcolor="#1A1A1A")
    chave = graficos.zoom_key("vg_ibov", periodo)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave)


def _painel_noticias_resumo(prefs):
    _injetar_css()
    st.markdown('<div class="painel-titulo">MARKET NEWS</div>', unsafe_allow_html=True)
    itens = obter_top_mercado_tudo("TODOS")
    if not itens:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    _renderizar_lista(itens[:_QTD_NOTICIAS], mostrar_ticker=True, prefixo="vg", watchlist=prefs.get("watchlist") or [])


def _painel_watchlist_compacta(prefs):
    st.markdown('<div class="painel-titulo">MINHA WATCHLIST</div>', unsafe_allow_html=True)
    watchlist = prefs.get("watchlist") or []
    if not watchlist:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>Adicione tickers na barra lateral.</div>", unsafe_allow_html=True)
        return
    linhas = []
    # obter_cotacoes_lote (N+1 real corrigido, 2026-10-08): 1 UNICA
    # requisicao em lote pra watchlist inteira, em vez de 1
    # yf.Ticker().fast_info POR TICKER (obter_cotacao) - com watchlist
    # grande e cache expirado, essa tela ficava bloqueada numa sequencia
    # de round-trips sequenciais ao Yahoo.
    cotacoes = obter_cotacoes_lote(tuple(watchlist))
    for t in watchlist:
        cot = cotacoes.get(t, {"erro": "sem dado"})
        if cot.get("erro"):
            linhas.append(f"<tr><td style='padding:0.2rem 0.4rem 0.2rem 0;'>{t}</td><td colspan='2' class='cinza'>—</td></tr>")
            continue
        cls = "alta" if cot["variacao_pct"] >= 0 else "baixa"
        linhas.append(
            f"<tr><td style='padding:0.2rem 0.4rem 0.2rem 0;'><span style='color:var(--destaque); font-weight:600;'>{t}</span></td>"
            f"<td style='padding:0.2rem 0.4rem; text-align:right;' class='neutro'>R$ {config.formatar_numero(cot['preco'], 2, prefs['formato_numerico'])}</td>"
            f"<td style='padding:0.2rem 0 0.2rem 0.4rem; text-align:right;' class='{cls}'>{_fmt_pct(cot['variacao_pct'], prefs)}</td></tr>"
        )
    st.markdown(f"<table style='width:100%; font-size:0.8rem; border-collapse:collapse;'>{''.join(linhas)}</table>", unsafe_allow_html=True)


# paineis registrados (ver ui/paineis.py/ui/workspace.py) - ETAPA 5
# (2026-10-01): VISÃO GERAL migra pro workspace modular, mesma mecanica
# ja' validada em MERCADO/MACRO. Conteúdo de cada painel intocado (3
# reaproveitados direto de ui/mercado_tab.py, já registrados lá também -
# pid local aqui não colide, cada aba_id tem sua própria tabela de
# ordem/visibilidade/layout em prefs). Ordem abaixo = ordem padrão atual
# (mesma sequência que render_visao_geral já tinha antes da migração).
REGISTRO_PAINEIS = [
    ("mercado_agora", "Mercado agora", _painel_mercado_agora),
    ("ibov_grafico", "Ibovespa", _painel_ibov_grafico),
    ("altas_baixas", "Maiores altas/baixas", _painel_altas_baixas),
    ("mais_negociados", "Mais negociados", _painel_mais_negociados),
    ("setorial", "Desempenho setorial", _painel_setorial),
    ("noticias_resumo", "Market news", _painel_noticias_resumo),
    ("globais", "Mercados globais", _painel_globais),
    ("watchlist_compacta", "Minha watchlist", _painel_watchlist_compacta),
]


def render_visao_geral(prefs: dict, persistir_fn=None):
    """Ponto de entrada da aba VISÃO GERAL, chamado pelo app.py.
    `persistir_fn` (opcional): ver ui/workspace.py:renderizar_workspace."""
    workspace.renderizar_workspace("VISÃO GERAL", REGISTRO_PAINEIS, prefs, prefs, persistir_fn=persistir_fn)
