# -*- coding: utf-8 -*-
"""Interface da aba TOP MERCADO: as noticias mais "importantes" do
momento (sem fonte publica de "mais lida" - estimativa por regras, ver
data/news.py:_calcular_importancia). Reaproveita a lista/card de
ui/news_tab.py (_renderizar_lista, _injetar_css) - mesmo componente
visual da aba NEWS.

Seletor de regiao BRASIL/INTERNACIONAL/TUDO e filtro de setor
(data/news_setores.py). TUDO junta os dois pools num ranking so' (tag
BR/INT em cada linha, ver ui/news_tab.py:_bloco_rank_coluna)."""

import streamlit as st

from data.news import obter_top_mercado, obter_top_mercado_internacional, obter_top_mercado_tudo
from data.news_setores import NOMES_SETORES
from ui.news_tab import _injetar_css, _renderizar_lista

_REGIOES = ["BRASIL", "INTERNACIONAL", "TUDO"]
_SETORES = ["TODOS"] + NOMES_SETORES

_BUSCADORES = {
    "BRASIL": obter_top_mercado,
    "INTERNACIONAL": obter_top_mercado_internacional,
    "TUDO": obter_top_mercado_tudo,
}


def render_top_mercado(prefs: dict):
    """Ponto de entrada da aba TOP MERCADO, chamado pelo app.py."""
    _injetar_css()

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">TOP MERCADO</div>', unsafe_allow_html=True)

        regiao = st.pills(
            "Região", _REGIOES, default="BRASIL", selection_mode="single", key="top_pill_regiao",
        ) or "BRASIL"
        setor = st.pills(
            "Setor", _SETORES, default="TODOS", selection_mode="single", key="top_pill_setor",
        ) or "TODOS"

        st.caption(
            "Ranking por estimativa de relevância (nº de fontes cobrindo o fato, recência, "
            "veículos confiáveis, temas de mercado) — não existe fonte pública de \"mais lida\", "
            "isso não é medição real de audiência. Clique numa manchete para ver os detalhes."
        )

        itens = _BUSCADORES[regiao](setor)
        if itens is None:
            st.warning("Fontes de mercado indisponíveis no momento.")
            return
        if not itens:
            rotulo_setor = "" if setor == "TODOS" else f" em {setor}"
            st.info(f"Nenhuma notícia de mercado encontrada{rotulo_setor} no momento.")
            return

        st.markdown(
            f"<div class='cinza' style='font-size:0.68rem; margin:0.3rem 0 0.4rem 0;'>top {len(itens)} do momento</div>",
            unsafe_allow_html=True,
        )

        _renderizar_lista(itens, mostrar_ticker=True, prefixo="top", watchlist=prefs.get("watchlist") or [])
