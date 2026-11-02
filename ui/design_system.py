# -*- coding: utf-8 -*-
"""Componentes HTML compartilhados do design system do PREGÃO (achado
real, auditoria "missao master" 2026-10-31): varias abas escritas por
sessoes diferentes usavam st.markdown("**Texto**")/st.metric() pra
subtitulo de secao - unica forma de conteudo do app que renderizava no
tamanho de fonte PADRAO do Streamlit, bem maior que o resto (que usa
HTML com font-size explicito em quase toda parte). Criado como modulo
proprio (nao deixado dentro de ui/analises_tab.py, onde nasceu) porque o
mesmo padrao se repetiu em pelo menos 2 abas (ANALISES, COORDENADOR
CENTRAL) escritas por sessoes diferentes - fica aqui pra ser o lugar
obvio de importar em qualquer aba nova."""

import html

import streamlit as st


def subtitulo(texto: str):
    """Subtítulo de seção compacto - mesmo tamanho de fonte usado em
    quase todo o resto do app (~0.72rem), nunca o padrão do Streamlit.
    `texto` é sempre escapado (é um rótulo curto, nunca HTML pré-formatado -
    diferente de lista_compacta, que recebe HTML de quem chama)."""
    st.markdown(
        f"<div style='font-size:0.72rem; font-weight:700; letter-spacing:0.03em; "
        f"margin:0.7rem 0 0.3rem 0; color:var(--neutro);'>{html.escape(texto)}</div>",
        unsafe_allow_html=True,
    )


def lista_compacta(linhas_html):
    """Lista com marcador, mesmo tamanho de fonte do resto do app (ver
    subtitulo) - substitui `st.markdown(f"- {texto}")` solto, que também
    herdava o tamanho padrão do Streamlit. `linhas_html`: iterável de
    strings já em HTML (quem chama decide se escapa ou não, mesma
    responsabilidade que st.markdown sempre teve)."""
    st.markdown(
        "".join(
            f"<div style='font-size:0.78rem; padding:0.12rem 0 0.12rem 0.9rem; position:relative;'>"
            f"<span style='position:absolute; left:0;'>·</span>{linha}</div>"
            for linha in linhas_html
        ),
        unsafe_allow_html=True,
    )
