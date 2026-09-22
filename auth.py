# -*- coding: utf-8 -*-
"""Login Google nativo do Streamlit (st.login/st.user) e tela de apresentação."""

import streamlit as st


def logado() -> bool:
    return bool(st.user.is_logged_in)


def dados_usuario() -> dict:
    """sub (ID estável do Google) e email (minúsculo) do usuário logado."""
    return {
        "sub": st.user.sub,
        "email": (st.user.email or "").lower(),
        "nome": getattr(st.user, "name", "") or "",
    }


def tela_apresentacao():
    """Tela exibida sem login: sem dados de mercado, só apresentação."""
    st.markdown('<div class="pregao-logo">PREGÃO</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(
            """
            <p class="cinza" style="text-align:center; padding:2rem 1rem; font-size:1rem;
               letter-spacing:0.05em; line-height:1.8;">
                TERMINAL DE MERCADO PESSOAL — AÇÕES DA B3, CURVA DE JUROS,
                NOTÍCIAS, RESEARCH DE CASAS DE ANÁLISE E FATOS RELEVANTES DA CVM,
                TUDO EM UM SÓ LUGAR. 100% GRATUITO.
            </p>
            """,
            unsafe_allow_html=True,
        )
        _, col, _ = st.columns([1, 1, 1])
        with col:
            if st.button("ENTRAR COM GOOGLE", width="stretch"):
                st.login()
