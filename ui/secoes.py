# -*- coding: utf-8 -*-
"""Subabas do PREGAO 2.0 (ui/navegacao.py) que sao so' composicao de
paineis ja existentes, sem modulo proprio: MERCADO > Mercados Globais e
Agenda, atalhos da Visao Geral e MAIS > Watchlist. Nenhum dado novo -
mesmas funcoes/caches dos paineis de origem."""

import html

import streamlit as st

import config
from data.mercado import obter_cotacoes_lote
from data.news import obter_noticias_watchlist
from data.prices import obter_indicadores
from ui import design_system as ds
from ui import navegacao
from ui.calendario_tab import render_calendario
from ui.macro_tab import _painel_cenario_global
from ui.mercado_tab import _painel_globais
from ui.news_tab import _CLASSE_SELO, _fmt_hora_curta, _texto_tag, _tooltip_regras, _truncar
from ui.visao_geral import _teses_research_watchlist


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
    """MAIS > Watchlist - reformulada (2026-11-06) como terminal denso de
    comparação lado a lado, no lugar do widget compacto emprestado da
    VISÃO GERAL (`_painel_watchlist_compacta`, que continua intocada e em
    uso lá - ver docstring do import removido daqui). Mesma identidade
    visual das outras abas (ui/design_system.py: numero_financeiro_html/
    variacao_html/classe_sinal, preto+âmbar, sem card de SaaS). ZERO dado
    novo - só reorganiza/expõe lado a lado o que já é coletado em
    data/mercado.py (cotação em lote), data/prices.py (indicadores de
    valuation, mesma fonte de ANÁLISES › Fundamentos), data/research
    (recomendação/preço-alvo das casas, via ui.visao_geral.
    _teses_research_watchlist - nunca gerado pelo PREGÃO) e data/news.py
    (notícias por ticker, agregadas pra watchlist inteira)."""
    watchlist = prefs.get("watchlist") or []
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">WATCHLIST</div>', unsafe_allow_html=True)
        if not watchlist:
            st.markdown(
                "<div class='cinza' style='font-size:0.78rem;'>Adicione tickers na barra lateral.</div>",
                unsafe_allow_html=True,
            )
        else:
            _tabela_watchlist_comparativa(prefs, watchlist)
        st.caption("Adicione ou remova tickers pela barra lateral (WATCHLIST) ou pela busca global no topo. "
                   "Cotação/volume: Yahoo Finance (lote único). Valuation: mesma fonte de ANÁLISES › Fundamentos. "
                   "Recomendação/preço-alvo: atribuídos pela casa de research, nunca gerados pelo PREGÃO.")
    if not watchlist:
        return

    with st.container(border=True):
        _noticias_watchlist_compactas(watchlist)

    cols = st.columns(min(len(watchlist), 6))
    for i, t in enumerate(watchlist):
        with cols[i % len(cols)]:
            navegacao.link(t, "analises", "empresas", chave=f"wl_abrir_{t}", ticker=t, width="stretch",
                           ajuda=f"Abrir {config.TICKER_NOME.get(t, t)} em ANÁLISES › Empresas")
    cols_fundo = st.columns(2)
    with cols_fundo[0]:
        navegacao.link("Fundamentos completos (comparar) ↗", "analises", "fundamentos", chave="wl_fundamentos",
                       width="stretch")
    with cols_fundo[1]:
        navegacao.link("Research · Casas de Análise ↗", "research", "casas", chave="wl_research", width="stretch")


# ===================== componentes novos da Watchlist (2026-11-06) =========
#
# Funções de apoio SÓ de render_watchlist (acima) - ver docstring dela.
# Ficam aqui (fim do arquivo, nova função, nada editado nas demais já
# existentes) por instrução explícita da missão de reformulação visual.

def _celula_fmt(valor, formatador):
    """'—' pra campo ausente (nunca inventa número) - mesmo critério usado
    em toda tabela de indicador do app (ex: ui/analises_tab.py:_celula)."""
    return formatador(valor) if valor is not None else "—"


def _tabela_watchlist_comparativa(prefs, watchlist: list):
    """Tabela densa (uma linha por ativo, não cards) pra comparar a
    watchlist inteira lado a lado: cotação+variação+volume (lote único,
    data/mercado.py:obter_cotacoes_lote - mesmo mecanismo de
    _painel_watchlist_compacta), valuation básico (P/L, P/VP, DY 12M -
    mesma fonte de ANÁLISES › Fundamentos, data/prices.py:obter_indicadores)
    e a recomendação/preço-alvo mais recente de research pra esse ticker,
    quando existir uma casa com cobertura salva
    (ui.visao_geral._teses_research_watchlist - só leitura do que a casa
    já publicou, nunca uma recomendação calculada pelo PREGÃO)."""
    fmt = prefs["formato_numerico"]
    cotacoes = obter_cotacoes_lote(tuple(watchlist))
    teses_por_ticker = dict(_teses_research_watchlist(prefs))

    cabecalho = (
        "<tr style='font-size:0.6rem; color:var(--cinza);'>"
        "<td style='padding:0 0.4rem 0.3rem 0;'>ATIVO</td>"
        "<td style='padding:0 0.4rem 0.3rem; text-align:right;'>PREÇO</td>"
        "<td style='padding:0 0.4rem 0.3rem; text-align:right;'>VAR. %</td>"
        "<td style='padding:0 0.4rem 0.3rem; text-align:right;'>VOL. (R$ MI)</td>"
        "<td style='padding:0 0.4rem 0.3rem; text-align:right;'>P/L</td>"
        "<td style='padding:0 0.4rem 0.3rem; text-align:right;'>P/VP</td>"
        "<td style='padding:0 0.4rem 0.3rem; text-align:right;'>DY 12M</td>"
        "<td style='padding:0 0 0.3rem 0.4rem;'>RECOMENDAÇÃO</td></tr>"
    )
    linhas = [cabecalho]
    for t in watchlist:
        cot = cotacoes.get(t, {"erro": "sem dado"})
        link_ticker = html.escape(t, quote=True)
        nome_curto = html.escape(config.TICKER_NOME.get(t, t))
        ativo_html = (
            f"<a href='?ticker={link_ticker}' class='vg-ticker-link' style='font-weight:700;'>{html.escape(t)}</a>"
            f"<div class='cinza' style='font-size:0.6rem;'>{nome_curto}</div>"
        )
        if cot.get("erro"):
            linhas.append(
                f"<tr><td style='padding:0.25rem 0.4rem 0.25rem 0; vertical-align:top;'>{ativo_html}</td>"
                f"<td colspan='6' class='cinza' style='vertical-align:top; padding-top:0.3rem;'>cotação indisponível agora</td>"
                f"<td style='vertical-align:top; padding-top:0.3rem;'>—</td></tr>"
            )
            continue

        vol_mi = cot.get("volume_financeiro")
        vol_fmt = config.formatar_numero(vol_mi / 1_000_000, 1, fmt) if vol_mi else "—"
        ind = obter_indicadores(t)
        pl_fmt = _celula_fmt(ind.get("pl"), lambda v: config.formatar_multiplo(v, 2, fmt))
        pvp_fmt = _celula_fmt(ind.get("pvp"), lambda v: config.formatar_multiplo(v, 2, fmt))
        dy_fmt = _celula_fmt(ind.get("dividend_yield"), lambda v: config.formatar_numero(v, 2, fmt) + "%")

        tese = teses_por_ticker.get(t)
        if tese:
            recomendacao = (tese.get("recomendacao") or "").upper()
            cor_rec = "alta" if "COMPRA" in recomendacao else ("baixa" if "VENDA" in recomendacao else "cinza")
            alvo = (
                f" · R$ {config.formatar_numero(tese['preco_alvo'], 2, fmt)}" if tese.get("preco_alvo") else ""
            )
            rec_html = (
                f"<span class='{cor_rec}' style='font-weight:700;'>{html.escape(recomendacao)}</span>"
                f"<span class='cinza' style='font-size:0.6rem;'>{alvo} · {html.escape(tese['casa'])}</span>"
            )
        else:
            rec_html = "<span class='cinza'>—</span>"

        linhas.append(
            "<tr>"
            f"<td style='padding:0.25rem 0.4rem 0.25rem 0; vertical-align:top;'>{ativo_html}</td>"
            f"<td style='padding:0.25rem 0.4rem; text-align:right; vertical-align:top;'>"
            f"{ds.numero_financeiro_html(cot['preco'], 2, fmt, prefixo='R$ ')}</td>"
            f"<td style='padding:0.25rem 0.4rem; text-align:right; vertical-align:top;'>"
            f"{ds.variacao_html(cot['variacao_pct'], fmt)}</td>"
            f"<td style='padding:0.25rem 0.4rem; text-align:right; vertical-align:top;' class='neutro'>{vol_fmt}</td>"
            f"<td style='padding:0.25rem 0.4rem; text-align:right; vertical-align:top;' class='neutro'>{pl_fmt}</td>"
            f"<td style='padding:0.25rem 0.4rem; text-align:right; vertical-align:top;' class='neutro'>{pvp_fmt}</td>"
            f"<td style='padding:0.25rem 0.4rem; text-align:right; vertical-align:top;' class='neutro'>{dy_fmt}</td>"
            f"<td style='padding:0.25rem 0 0.25rem 0.4rem; vertical-align:top; font-size:0.68rem;'>{rec_html}</td>"
            "</tr>"
        )
    st.markdown(
        "<div style='overflow-x:auto; overflow-y:hidden;'>"
        f"<table style='width:100%; font-size:0.78rem; border-collapse:collapse;'>{''.join(linhas)}</table></div>",
        unsafe_allow_html=True,
    )


def _noticias_watchlist_compactas(watchlist: list, limite: int = 8):
    """Feed compacto de notícias (data/news.py:obter_noticias_watchlist,
    mesma agregação/selo/score de confiabilidade já usados em NOTÍCIAS e
    VISÃO GERAL) filtrado pra só a watchlist atual - lista densa (1 linha
    por item, sem card), ticker em destaque igual ao resto da tabela
    acima pra facilitar ligar manchete -> ativo."""
    st.markdown('<div class="painel-titulo">NOTÍCIAS DA WATCHLIST</div>', unsafe_allow_html=True)
    noticias, falhas = obter_noticias_watchlist(watchlist)
    if not noticias:
        aviso = "busca de notícias indisponível agora" if falhas else "sem notícias recentes pra esses tickers"
        st.markdown(f"<div class='cinza' style='font-size:0.78rem;'>{aviso}.</div>", unsafe_allow_html=True)
        return
    linhas = []
    for n in noticias[:limite]:
        ticker_n = n.get("ticker") or (n.get("tickers") or [""])[0]
        tag_ticker = f"<span style='color:var(--destaque); font-weight:700; font-size:0.68rem;'>{html.escape(ticker_n)}</span> · " if ticker_n else ""
        classe_selo = _CLASSE_SELO.get(n["selo"], "selo-naoconfirmada")
        tooltip = html.escape(_tooltip_regras(n))
        linhas.append(
            "<div style='display:flex; justify-content:space-between; gap:0.5rem; align-items:baseline; "
            "padding:0.22rem 0; border-bottom:1px solid var(--borda);'>"
            f"<span style='font-size:0.68rem;'>{tag_ticker}"
            f"<a href='{html.escape(n['link'])}' target='_blank' rel='noopener' class='vg-ticker-link'>"
            f"{html.escape(_truncar(n['titulo']))}</a>"
            f" <span class='selo-tag {classe_selo}' title='{tooltip}'>{_texto_tag(n)}</span></span>"
            f"<span class='cinza' style='font-size:0.62rem; white-space:nowrap;'>{_fmt_hora_curta(n['data'])}</span>"
            "</div>"
        )
    st.markdown("".join(linhas), unsafe_allow_html=True)
    if falhas:
        st.caption(f"Sem resposta da fonte agora para: {', '.join(falhas)}.")
