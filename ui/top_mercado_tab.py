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
from ui.news_tab import _injetar_css, _prontos_para_lista, _renderizar_lista

_REGIOES = ["BRASIL", "INTERNACIONAL", "TUDO"]
_SETORES = ["TODOS"] + NOMES_SETORES

_BUSCADORES = {
    "BRASIL": obter_top_mercado,
    "INTERNACIONAL": obter_top_mercado_internacional,
    "TUDO": obter_top_mercado_tudo,
}


@st.fragment
def render_top_mercado(prefs: dict, regiao_fixa: str | None = None, setor_fixo: str | None = None,
                       titulo: str = "TOP MERCADO"):
    """Ponto de entrada da aba TOP MERCADO, chamado pelo app.py.

    regiao_fixa/setor_fixo (PREGAO 2.0, ui/navegacao.py): NOTICIAS >
    Destaques/Brasil/Internacional ja sao a escolha de regiao, e SETORES >
    Visao por Setor ja escolheu o setor - o pill correspondente some
    (mesma busca/cache/ranking de sempre, nenhuma coleta paralela).

    @st.fragment (perf, 2026-10-01): pills de região/setor disparavam
    rerun da pagina inteira a cada clique (sintoma: tela pula pro topo).
    Mesmo padrao de CVM/NEWS - isola o rerun so' neste bloco."""
    _injetar_css()

    with st.container(border=True):
        st.markdown(f'<div class="painel-titulo">{titulo}</div>', unsafe_allow_html=True)

        # regiao (pills curtas) e setor (select compacto) na MESMA linha: os
        # 13 pills de setor ocupavam ~5 linhas antes da primeira manchete
        if regiao_fixa and setor_fixo:
            regiao, setor = regiao_fixa, setor_fixo
        else:
            if regiao_fixa:
                regiao = regiao_fixa
                c_setor, _vazio = st.columns([0.3, 0.7], gap="small")
            else:
                c_regiao, c_setor = st.columns([0.55, 0.45], gap="small", vertical_alignment="bottom")
                with c_regiao:
                    regiao = st.pills(
                        "Região", _REGIOES, default="BRASIL", selection_mode="single", key="top_pill_regiao",
                    ) or "BRASIL"
            with c_setor:
                setor = setor_fixo or st.selectbox("Setor", _SETORES, index=0, key="top_select_setor")

        st.caption(
            "Ranking estimado por regras (nº de fontes, recência, veículos confiáveis, temas) — "
            "não é medição de audiência. Clique na manchete para ver os detalhes."
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
            f"<div class='cinza' style='font-size:0.68rem; margin:0.4rem 0 0.5rem 0;'>{len(itens)} do momento</div>",
            unsafe_allow_html=True,
        )

        # fotos já validadas pelo coletor: 1 leitura em lote pra lista
        # inteira, nunca rede/IA por linha; falha do cache = lista sem foto
        _renderizar_lista(itens, mostrar_ticker=True, prefixo="top", watchlist=prefs.get("watchlist") or [])
