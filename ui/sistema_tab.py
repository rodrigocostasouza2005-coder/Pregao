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

# Reformulação visual (missão "MAIS admin Bloomberg", 2026-11-06): os 3
# documentos eram renderizados direto num st.markdown solto - os
# cabeçalhos "#"/"##" deles ("# CHANGELOG — PREGÃO", "## 2026-11-02 — ...")
# saiam no tamanho PADRÃO do Streamlit, bem maior que o resto do app
# (mesmo problema que motivou ui/design_system.py, aqui vindo de
# cabeçalho de markdown real, não de um "**rótulo**" solto). CSS escopado
# via st.container(key=...) encolhe só os cabeçalhos DENTRO de cada aba de
# documento - zero mudança no conteúdo/arquivo lido, só no tamanho em que
# ele aparece. Painel com borda (`st.container(border=True)`) + altura
# máxima com scroll próprio: PROGRESSO.md só cresce (log de execução,
# ~6500 linhas) - sem isso a aba inteira ficava do tamanho do arquivo.
_CSS_DOC = """
<style>
[class*="st-key-sistema_doc_"] {
    max-height: 32rem;
    overflow-y: auto;
    padding-right: 0.6rem;
}
[class*="st-key-sistema_doc_"] [data-testid="stMarkdownContainer"] {
    font-size: 0.8rem;
    line-height: 1.55;
}
[class*="st-key-sistema_doc_"] [data-testid="stMarkdownContainer"] h1 {
    font-size: 1.0rem; color: var(--destaque); letter-spacing: 0.02em;
    margin: 0 0 0.5rem 0; padding-bottom: 0.3rem; border-bottom: 1px solid var(--borda);
}
[class*="st-key-sistema_doc_"] [data-testid="stMarkdownContainer"] h2 {
    font-size: 0.88rem; color: var(--neutro); margin: 0.9rem 0 0.3rem 0;
}
[class*="st-key-sistema_doc_"] [data-testid="stMarkdownContainer"] h3 {
    font-size: 0.8rem; color: var(--cinza); margin: 0.6rem 0 0.25rem 0;
}
[class*="st-key-sistema_doc_"] [data-testid="stMarkdownContainer"] code {
    font-size: 0.76rem; background: color-mix(in srgb, var(--borda) 35%, transparent);
}
</style>
"""


def _ler(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="utf-8")
    except Exception:
        return ""


def _render_doc(chave: str, caminho: Path, nome_ausente: str):
    """Painel denso (borda + CSS escopado de _CSS_DOC) pra 1 documento -
    mesmo tratamento pros 3 (CHANGELOG/PROGRESSO/MANUAL), ver docstring
    de _CSS_DOC."""
    texto = _ler(caminho)
    with st.container(border=True, key=f"sistema_doc_{chave}"):
        st.markdown(texto if texto else f"_{nome_ausente} não encontrado._")


def render_sistema(prefs: dict):
    """Ponto de entrada da aba SISTEMA, chamado pelo app.py - so aparece
    no menu de quem esta em config.obter_emails_admin() (ver app.py)."""
    st.markdown('<div class="painel-titulo">SISTEMA</div>', unsafe_allow_html=True)
    st.caption(
        "Visível só pra e-mails admin — documentação de desenvolvimento, "
        "não é um painel de dados do mercado."
    )
    st.markdown(_CSS_DOC, unsafe_allow_html=True)

    aba_changelog, aba_progresso, aba_manual = st.tabs(["CHANGELOG", "PROGRESSO", "MANUAL"])

    with aba_changelog:
        _render_doc("changelog", _CHANGELOG, "CHANGELOG.md")

    with aba_progresso:
        _render_doc("progresso", _PROGRESSO, "PROGRESSO.md")

    with aba_manual:
        _render_doc("manual", _MANUAL, "MANUAL.md")
