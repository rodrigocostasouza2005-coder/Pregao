# -*- coding: utf-8 -*-
"""Area SETORES do PREGAO 2.0 (ui/navegacao.py). Sem coleta propria:

- Mapa Setorial: paineis DESEMPENHO SETORIAL/MAPA DO MERCADO da aba
  MERCADO (ui/mercado_tab.py), mesmo dado (composicao oficial do
  Ibovespa + config.IBOVESPA_SETORES).
- Visao por Setor / Catalisadores: taxonomia de data/news_setores.SETORES
  (a MESMA que classifica as noticias), empresas curadas ali, noticias
  pelo ranking de TOP MERCADO filtrado pelo setor e texto editorial fixo
  de data/radar_setorial.CATALOGO (o mesmo do Morning Call), sempre
  marcado como interpretacao - nunca gerado na hora pra "preencher".
"""

import html

import streamlit as st

from data.mercado import obter_cotacoes_lote
from data.news_setores import NOMES_SETORES, SETORES
from data.radar_setorial import CATALOGO
from ui import design_system as ds
from ui import navegacao
from ui.mercado_tab import _painel_setorial, _painel_treemap
from ui.radar_tab import _injetar_css as _css_radar
from ui.radar_tab import _secao_catalisadores
from ui.top_mercado_tab import render_top_mercado

KEY_SETOR = "setor_atual"


def setores_do_ticker(ticker: str) -> list:
    """Setores (taxonomia de noticias) que listam o ticker entre as
    empresas curadas - [] se nenhum. Nunca adivinha por nome."""
    return [nome for nome, cfg in SETORES.items() if ticker in cfg["tickers"]]


def ir_para_setor(setor: str, sub_id: str = "setor"):
    """Callback de vinculo (empresa/noticia -> setor)."""
    st.session_state[KEY_SETOR] = setor
    navegacao.ir_para("setores", sub_id)


def _seletor_setor() -> str:
    # chave de widget separada da memoria (KEY_SETOR, chave comum): o
    # Streamlit apaga o estado de um widget que nao renderizou no run -
    # sem isso o setor escolhido se perderia ao trocar de subaba
    atual = st.session_state.get(KEY_SETOR)
    if atual not in NOMES_SETORES:
        atual = NOMES_SETORES[0]
    escolha = st.selectbox(
        "Setor", NOMES_SETORES, index=NOMES_SETORES.index(atual), key="setores_seletor",
    )
    st.session_state[KEY_SETOR] = escolha
    return escolha


def render_mapa_setorial(prefs: dict):
    with st.container(border=True):
        _painel_setorial(prefs)
    with st.container(border=True):
        _painel_treemap(prefs)
    st.caption(
        "Setores do Ibovespa pela classificação de config.IBOVESPA_SETORES (média simples da variação dos "
        "papéis). A Visão por Setor usa a taxonomia de notícias, que agrupa alguns setores de forma diferente."
    )


def _tabela_empresas(setor: str, prefs: dict):
    """EMPRESAS DO SETOR - tabela densa (mesmo padrao das outras tabelas
    HTML pos-fundacao: ui/secoes.py:_tabela_watchlist_comparativa,
    ui/radar_tab.py, ui/visao_geral.py), nao mais 1 st.button por linha
    (3 st.columns cada) com sinal/cor reimplementados na mao - exatamente
    o padrao apontado como duplicado na docstring de ui/design_system.py
    (regra 2, cita este arquivo). Ticker clicavel via `?ticker=X`
    (ui.navegacao.ticker_da_url, lido em app.py) em vez de navegacao.link:
    mesmo destino (ANALISES > Empresas com o ticker pre-selecionado),
    sem widget por linha."""
    tickers = SETORES[setor]["tickers"]
    cotacoes = obter_cotacoes_lote(tuple(tickers))
    fmt = prefs["formato_numerico"]
    variacoes = []
    st.markdown('<div class="painel-titulo">EMPRESAS DO SETOR</div>', unsafe_allow_html=True)
    cabecalho = (
        "<tr style='font-size:0.6rem; color:var(--cinza);'>"
        "<td style='padding:0 0.4rem 0.3rem 0;'>TICKER</td>"
        "<td style='padding:0 0.4rem 0.3rem; text-align:right;'>PREÇO</td>"
        "<td style='padding:0 0 0.3rem 0.4rem; text-align:right;'>VAR. %</td></tr>"
    )
    linhas = [cabecalho]
    for t in tickers:
        cot = cotacoes.get(t, {"erro": "sem dado"})
        ticker_html = f"<a href='?ticker={html.escape(t, quote=True)}' class='vg-ticker-link'>{html.escape(t)}</a>"
        if cot.get("erro"):
            linhas.append(
                "<tr>"
                f"<td style='padding:0.22rem 0.4rem 0.22rem 0;'>{ticker_html}</td>"
                "<td colspan='2' class='cinza' style='text-align:right; font-size:0.78rem;'>—</td>"
                "</tr>"
            )
            continue
        variacoes.append(cot["variacao_pct"])
        linhas.append(
            "<tr>"
            f"<td style='padding:0.22rem 0.4rem 0.22rem 0;'>{ticker_html}</td>"
            f"<td style='padding:0.22rem 0.4rem; text-align:right;'>"
            f"{ds.numero_financeiro_html(cot['preco'], 2, fmt, prefixo='R$ ')}</td>"
            f"<td style='padding:0.22rem 0 0.22rem 0.4rem; text-align:right;'>"
            f"{ds.variacao_html(cot['variacao_pct'], fmt)}</td>"
            "</tr>"
        )
    st.markdown(
        "<div style='overflow-x:auto;'>"
        f"<table style='width:100%; font-size:0.8rem; border-collapse:collapse;'>{''.join(linhas)}</table></div>",
        unsafe_allow_html=True,
    )
    if variacoes:
        media = sum(variacoes) / len(variacoes)
        st.markdown(
            ds.divisor_html()
            + f"<div class='cinza' style='font-size:0.7rem; margin-top:-0.15rem;'>Média simples do dia "
            f"({len(variacoes)} de {len(tickers)} com cotação): {ds.variacao_html(media, fmt)} · Yahoo Finance, "
            f"com atraso. Clique num ticker para abrir a empresa.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("Cotações indisponíveis no momento.")


def render_visao_setor(prefs: dict):
    setor = _seletor_setor()
    col_emp, col_news = st.columns([1, 1.6])
    with col_emp:
        with st.container(border=True):
            _tabela_empresas(setor, prefs)
        with st.container(border=True):
            _bloco_por_que_importa(setor)
    with col_news:
        render_top_mercado(prefs, regiao_fixa="TUDO", setor_fixo=setor, titulo=f"NOTÍCIAS — {setor}")


def _bloco_por_que_importa(setor: str):
    cfg = CATALOGO.get(setor)
    st.markdown('<div class="painel-titulo">POR QUE IMPORTA <span class="cinza" style="font-size:0.62rem;'
                'font-weight:400;">INTERPRETAÇÃO</span></div>', unsafe_allow_html=True)
    if not cfg:
        st.caption("Sem texto editorial para este setor.")
        return
    st.markdown(f"<div style='font-size:0.8rem; margin-bottom:0.6rem;'>{html.escape(cfg['importa'])}</div>",
                unsafe_allow_html=True)
    st.caption("Texto editorial fixo (o mesmo do radar setorial do Morning Call) — explica o mecanismo, "
               "não é previsão nem recomendação.")


def render_catalisadores_setor(prefs: dict):
    _css_radar()
    setor = _seletor_setor()
    cfg = CATALOGO.get(setor) or {}
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">EVENTOS CORPORATIVOS DAS EMPRESAS DO SETOR '
                    '<span class="cinza" style="font-size:0.62rem;font-weight:400;">FATO</span></div>',
                    unsafe_allow_html=True)
        _secao_catalisadores(list(SETORES[setor]["tickers"]))
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">O QUE ACOMPANHAR <span class="cinza" style="font-size:0.62rem;'
                    'font-weight:400;">INTERPRETAÇÃO</span></div>', unsafe_allow_html=True)
        if cfg.get("acompanhar"):
            st.markdown(f"<div style='font-size:0.8rem;'>{html.escape(cfg['acompanhar'])}</div>",
                        unsafe_allow_html=True)
        else:
            st.caption("Sem orientação editorial cadastrada para este setor.")
    col_a, col_b = st.columns(2)
    with col_a:
        navegacao.link("Indicadores macro relacionados ↗", "macro", "juros", chave="setor_cat_macro", width="stretch",
                       ajuda="Juros, inflação e expectativas (MACRO › Juros)")
    with col_b:
        st.button("Notícias do setor ↗", key="setor_cat_news", width="stretch",
                  on_click=ir_para_setor, args=(setor, "setor"), help="Abrir em SETORES › Visão por Setor")
