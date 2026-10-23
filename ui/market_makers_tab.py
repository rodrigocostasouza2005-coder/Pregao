# -*- coding: utf-8 -*-
"""Área MARKET MAKERS do PREGAO 2.0 (ui/navegacao.py): primeira página
dedicada à inteligência de mercado que RADAR já calculava espalhada em
"Minha Tese"/copiloto (data/radar.py) - esta aba não duplica nenhuma
fonte/coleta, só dá à mesma camada (agora em data/market_makers.py,
reutilizada também pelo Morning Call - ver data/morning_call_editorial.py)
uma apresentação própria, auditável: conclusão, catalisador, ativo
afetado, risco, data e fonte - sempre explícitos, nunca um resumo de IA
tentando parecer confiante sem evidência."""
import html
from datetime import date

import streamlit as st

from data.market_makers import inteligencia_mercado
from data.radar import TIPO_ESTIMATIVA_TERCEIRO, TIPO_FATO
from ui.radar_tab import _injetar_css, _selo_evidencia as _selo


def _linha_mudanca(m: dict) -> str:
    fonte = ""
    if m.get("fonte_url"):
        fonte = f" · <a href='{html.escape(m['fonte_url'], quote=True)}' target='_blank' rel='noopener'>{html.escape(m.get('fonte_label') or 'fonte')}</a>"
    elif m.get("fonte_label"):
        fonte = f" · {html.escape(m['fonte_label'])}"
    return (
        "<div class='radar-alerta'><div class='radar-alerta-topo'>"
        f"<span><span class='radar-ticker'>{html.escape(m['ticker'])}</span> "
        f"<span class='radar-categoria'>{html.escape(m['categoria'])}</span></span>"
        f"{_selo(m.get('tipo_evidencia', TIPO_FATO))}</div>"
        f"<div class='radar-descricao'>{html.escape(m['descricao'])}</div>"
        f"<div class='radar-meta'>{m['data_evento'].strftime('%d/%m/%Y')}{fonte}</div></div>"
    )


def _linha_catalisador(c: dict) -> str:
    fonte = ""
    if c.get("fonte_url"):
        fonte = f" · <a href='{html.escape(c['fonte_url'], quote=True)}' target='_blank' rel='noopener'>{html.escape(c.get('fonte_label') or 'fonte')}</a>"
    elif c.get("fonte_label"):
        fonte = f" · {html.escape(c['fonte_label'])}"
    tipo = TIPO_FATO if c.get("confirmado") else TIPO_ESTIMATIVA_TERCEIRO
    return (
        "<div class='radar-alerta'><div class='radar-alerta-topo'>"
        f"<span><span class='radar-ticker'>{html.escape(c['ticker'])}</span> "
        f"<span class='radar-categoria'>{html.escape(c['categoria'])}</span></span>"
        f"{_selo(tipo)}</div>"
        f"<div class='radar-meta'>{c['data'].strftime('%d/%m/%Y')} · {html.escape(c['status_label'])}{fonte}</div></div>"
    )


def render_market_makers(prefs: dict, sub: str):
    """Ponto de entrada da aba MARKET MAKERS, chamado pelo app.py."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">MARKET MAKERS</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='radar-subtitulo'>Catalisadores, mudanças de tese e riscos dos ativos da sua watchlist — "
        "a mesma inteligência que o RADAR usa pra contextualizar alertas e que o Morning Call usa no briefing "
        "diário, numa página só, pra nunca ter que repetir a consulta.</div>",
        unsafe_allow_html=True,
    )
    watchlist = prefs.get("watchlist") or []
    if not watchlist:
        st.info("Adicione tickers na watchlist (barra lateral) para o Market Makers analisar os ativos.")
        return

    try:
        dados = inteligencia_mercado(tuple(watchlist))
    except Exception as exc:
        st.warning(f"Inteligência de mercado indisponível nesta execução ({exc!r}).")
        return

    st.caption(
        f"Gerado às {dados['gerado_em'].strftime('%d/%m/%Y %H:%M')} (Brasília) · "
        f"{len(watchlist)} ativo(s) na watchlist · sem chamada de IA nova (dados já agregados pelo RADAR)."
    )

    with st.container(border=True):
        st.markdown('<div class="painel-titulo" style="font-size:.78rem;">O QUE MUDOU — RESEARCH E CVM</div>', unsafe_allow_html=True)
        mudancas = dados.get("mudancas") or []
        if not mudancas:
            st.markdown("<div class='radar-vazio'>Nenhuma mudança de tese/CVM verificada na janela de 7 dias.</div>", unsafe_allow_html=True)
        else:
            for m in mudancas:
                st.markdown(_linha_mudanca(m), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="painel-titulo" style="font-size:.78rem;">CATALISADORES — PRÓXIMOS 60 DIAS</div>', unsafe_allow_html=True)
        eventos = [c for c in (dados.get("catalisadores") or []) if c["data"] >= date.today()]
        if not eventos:
            st.markdown("<div class='radar-vazio'>Nenhum catalisador (resultado/proventos) nos próximos 60 dias.</div>", unsafe_allow_html=True)
        else:
            for c in eventos[:20]:
                st.markdown(_linha_catalisador(c), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="painel-titulo" style="font-size:.78rem;">RISCOS — ALERTA DE QUALIDADE DOS INDICADORES</div>', unsafe_allow_html=True)
        riscos = dados.get("riscos") or {}
        if not riscos:
            st.markdown("<div class='radar-vazio'>Nenhum alerta de qualidade nos indicadores (P/L, margem, dívida/EBITDA) da watchlist.</div>", unsafe_allow_html=True)
        else:
            for ticker, alertas in riscos.items():
                st.markdown(
                    f"<div class='radar-alerta'><div class='radar-alerta-topo'>"
                    f"<span class='radar-ticker'>{html.escape(ticker)}</span></div>"
                    f"<div class='radar-descricao'>{html.escape('; '.join(alertas))}</div></div>",
                    unsafe_allow_html=True,
                )

    st.caption(
        "Conclusão sempre citando ticker, categoria, data e fonte real (ou declarando dado insuficiente) — "
        "nunca uma interpretação inventada pra preencher a página. Ver RADAR › Alertas para o contexto "
        "aplicado diretamente a cada alerta de queda."
    )
