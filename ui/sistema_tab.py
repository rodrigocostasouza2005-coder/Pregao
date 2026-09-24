# -*- coding: utf-8 -*-
"""Interface da aba SISTEMA (so admin, ver config.obter_emails_admin):
ultimas entradas do CHANGELOG, status da fila de trabalho (PROGRESSO.md)
e o manual do app (MANUAL.md). Le os arquivos direto do disco - nao tem
tabela no banco, e' documentacao de desenvolvimento, nao dado de
produto."""

from pathlib import Path

import streamlit as st

import config

_CHANGELOG = config.BASE_DIR / "CHANGELOG.md"
_PROGRESSO = config.BASE_DIR / "PROGRESSO.md"
_MANUAL = config.BASE_DIR / "MANUAL.md"


def _ler(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="utf-8")
    except Exception:
        return ""


def render_sistema(prefs: dict):
    """Ponto de entrada da aba SISTEMA, chamado pelo app.py - so aparece
    no menu de quem esta em config.obter_emails_admin() (ver app.py)."""
    st.markdown('<div class="painel-titulo">SISTEMA</div>', unsafe_allow_html=True)
    st.caption(
        "Visível só pra e-mails admin — documentação de desenvolvimento, "
        "não é um painel de dados do mercado."
    )

    aba_changelog, aba_progresso, aba_manual = st.tabs(["CHANGELOG", "PROGRESSO", "MANUAL"])

    with aba_changelog:
        texto = _ler(_CHANGELOG)
        st.markdown(texto if texto else "_CHANGELOG.md não encontrado._")

    with aba_progresso:
        texto = _ler(_PROGRESSO)
        st.markdown(texto if texto else "_PROGRESSO.md não encontrado._")

    with aba_manual:
        texto = _ler(_MANUAL)
        st.markdown(texto if texto else "_MANUAL.md não encontrado._")
