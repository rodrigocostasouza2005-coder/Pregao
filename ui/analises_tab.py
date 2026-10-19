# -*- coding: utf-8 -*-
"""Area ANALISES do PREGAO 2.0 (ui/navegacao.py). Empresas = a antiga
EQUITY (continua em app.py, intocada no miolo); aqui ficam a barra de
vinculos da empresa (empresa -> setor/noticias/radar/fundamentos) e a
subaba Fundamentos. Valuation/Teses vem de ui/radar_tab.py.

Fundamentos so' mostra o que a fonte reporta HOJE (data/prices.py:
obter_indicadores, Yahoo Finance, cache de 12h) - receita, lucro e fluxo
de caixa em serie historica nao existem em nenhuma fonte integrada, e a
tela diz isso em vez de estimar."""

import streamlit as st

import config
from data.prices import obter_indicadores
from ui import navegacao
from ui.setores_tab import ir_para_setor, setores_do_ticker


def _ir_noticias_do_ticker(ticker: str, watchlist: tuple):
    # o filtro de NOTICIAS > Empresas so' oferece tickers da watchlist
    if ticker in watchlist:
        st.session_state["news_pill_ticker"] = ticker
    navegacao.ir_para("noticias", "empresas")


def _ir_radar_do_ticker(ticker: str):
    st.session_state["rq_ticker"] = ticker
    navegacao.ir_para("radar", "alertas")


def barra_contexto_empresa(ticker: str, prefs: dict):
    """Vinculos contextuais da empresa selecionada. Setor so' aparece se o
    ticker estiver na lista curada de algum setor (data/news_setores) -
    nunca por semelhanca de nome."""
    setores = setores_do_ticker(ticker)
    botoes = [("Notícias ↗", _ir_noticias_do_ticker, (ticker, tuple(prefs.get("watchlist") or [])), "Notícias desta empresa (NOTÍCIAS › Empresas)"),
              ("Radar ↗", _ir_radar_do_ticker, (ticker,), "Alertas de queda deste ativo (RADAR › Alertas)"),
              ("Fundamentos ↗", navegacao.ir_para, ("analises", "fundamentos"), "ANÁLISES › Fundamentos"),
              ("Valuation ↗", navegacao.ir_para, ("analises", "valuation"), "ANÁLISES › Valuation")]
    botoes += [(f"Setor: {s} ↗", ir_para_setor, (s,), "SETORES › Visão por Setor") for s in setores]
    with st.container(key="empresa_contexto"):
        cols = st.columns(len(botoes))
        for i, (rotulo, fn, args, ajuda) in enumerate(botoes):
            with cols[i]:
                st.button(rotulo, key=f"empresa_ctx_{i}_{ticker}", on_click=fn, args=args, help=ajuda,
                          width="stretch")
    if not setores:
        st.caption("Setor: não classificado (ticker fora das listas curadas de data/news_setores.py).")


def _celula(valor, formatador):
    return formatador(valor) if valor is not None else "—"


def render_fundamentos(prefs: dict):
    fmt = prefs["formato_numerico"]
    watchlist = prefs.get("watchlist") or []
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">FUNDAMENTOS — WATCHLIST</div>', unsafe_allow_html=True)
        if not watchlist:
            st.info("Adicione tickers na watchlist para comparar fundamentos.")
            return
        pct = lambda v: config.formatar_numero(v, 2, fmt) + "%"  # noqa: E731
        mult = lambda v: config.formatar_multiplo(v, 2, fmt)  # noqa: E731
        vm = lambda v: config.formatar_valor_mercado(v, fmt)  # noqa: E731
        colunas = [
            ("VALOR DE MERCADO", "valor_mercado", vm), ("P/L", "pl", mult), ("P/VP", "pvp", mult),
            ("DY 12M", "dividend_yield", pct), ("ROE", "roe", pct), ("M. LÍQUIDA", "margem_liquida", pct),
            ("M. OPERAC.", "margem_operacional", pct), ("M. EBITDA", "margem_ebitda", pct),
            ("DÍV. LÍQUIDA", "divida_liquida", vm),
            ("DL/EBITDA", "divida_liquida_ebitda", lambda v: config.formatar_numero(v, 1, fmt) + "x"),
        ]
        linhas = []
        for t in watchlist:
            ind = obter_indicadores(t)
            celulas = "".join(
                f"<td style='padding:0.2rem 0.4rem; text-align:right;' class='neutro'>{_celula(ind.get(c), f)}</td>"
                for _, c, f in colunas
            )
            linhas.append(f"<tr><td style='padding:0.2rem 0.4rem 0.2rem 0;'><span style='color:var(--destaque); "
                          f"font-weight:600;'>{t}</span></td>{celulas}</tr>")
        cabecalho = "".join(f"<th style='text-align:right; font-weight:400; padding:0 0.4rem 0.2rem;'>{r}</th>"
                            for r, _, _ in colunas)
        st.markdown(
            "<div style='overflow-x:auto; overflow-y:hidden;'><table style='width:100%; font-size:0.78rem; "
            "border-collapse:collapse;'><thead><tr class='cinza' style='font-size:0.66rem;'>"
            f"<th style='text-align:left; font-weight:400; padding:0 0.4rem 0.2rem 0;'>TICKER</th>{cabecalho}</tr>"
            f"</thead><tbody>{''.join(linhas)}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Dados REPORTADOS pela fonte (Yahoo Finance, últimos 12 meses), atualizados a cada 12h; — = campo "
            "não informado pela fonte (nunca estimado). Receita, lucro e fluxo de caixa em série histórica "
            "ainda não têm fonte integrada; documentos de resultado oficiais ficam em NOTÍCIAS › Documentos CVM."
        )
    cols = st.columns(2)
    with cols[0]:
        navegacao.link("Documentos de resultado (CVM) ↗", "noticias", "documentos", chave="fund_cvm", width="stretch")
    with cols[1]:
        navegacao.link("Valuation por múltiplos ↗", "analises", "valuation", chave="fund_val", width="stretch")
