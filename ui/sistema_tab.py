# -*- coding: utf-8 -*-
"""Interface da aba SISTEMA (so admin, ver config.obter_emails_admin):
ultimas entradas do CHANGELOG, status da fila de trabalho (PROGRESSO.md),
o manual do app (MANUAL.md) e a saude de EXECUCAO dos agendamentos
(cron do GitHub Actions - missao "agendamento" 2026-11-13, ver
data/agendamentos_saude.py). Os 3 documentos continuam lidos direto do
disco; a aba AGENDAMENTOS le tabelas que ja existem no Supabase
(coletores_status, coordenador_execucoes) - nunca inventa dado.

Auditoria de uso do design system (ui/design_system.py, missao rollout A,
2026-11-14): este arquivo nao importa o modulo de proposito - renderiza
texto markdown de arquivos de documentacao (sem numero financeiro, sinal
de alta/baixa ou divisor manual; o border-bottom em _CSS_DOC e' estilo
estatico de cabecalho de markdown, nao um divisor dinamico entre secoes).
A aba AGENDAMENTOS (adicionada depois dessa auditoria) usa so' emoji +
st.container/st.columns pra status, mesmo padrao sem design_system das
demais sub-abas deste arquivo."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

import config
from data.agendamentos_saude import saude_agendamentos

_CHANGELOG = config.BASE_DIR / "CHANGELOG.md"
_PROGRESSO = config.BASE_DIR / "PROGRESSO.md"
_MANUAL = config.BASE_DIR / "MANUAL.md"
_TZ_SP = ZoneInfo("America/Sao_Paulo")

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


def _fmt_hora_brt(iso_utc: str | None) -> str:
    if not iso_utc:
        return "—"
    try:
        dt = datetime.fromisoformat(str(iso_utc).replace("Z", "+00:00"))
    except ValueError:
        return "—"
    if dt.tzinfo is None:
        return "—"
    return dt.astimezone(_TZ_SP).strftime("%d/%m %H:%M") + " BRT"


def _badge_agendamento(linha: dict) -> str:
    """Rótulo + cor do status de 1 workflow agendado - nunca pinta verde
    sem dado real (ver docstring de data/agendamentos_saude.py:
    "atrasado"=None é tratado como neutro, não OK)."""
    if not linha["disponivel"]:
        return "🔘 SEM DADO (Supabase indisponível)"
    if linha["atrasado"] is True:
        return "🔴 ATRASADO"
    if linha["execucao_ok"] is False:
        return "🟡 ÚLTIMA TENTATIVA FALHOU"
    if linha["atrasado"] is False:
        return "🟢 EM DIA"
    # atrasado is None e execucao_ok não é False: fora da janela avaliável,
    # mas sem falha conhecida - neutro, não "OK" fabricado.
    return "⚪ SEM AVALIAÇÃO AGORA (fora da janela esperada)"


def _render_agendamentos():
    """Saúde de EXECUÇÃO dos 3 workflows agendados do GitHub Actions
    (Morning Call, Radar de Quedas, Comitê Noturno) - missão
    "agendamento" 2026-11-13. Causa raiz documentada em MANUAL.md
    ("Disparo externo dos agendamentos"): o `schedule` do GitHub Actions
    atrasa/descarta disparos sob carga (confirmado de novo hoje); isto
    aqui é a MITIGAÇÃO de visibilidade - nunca conserta o agendador em
    si, só garante que o atraso/ausência fica visível no app em vez de
    só no histórico do Actions."""
    st.caption(
        "Última tentativa/sucesso de cada rotina agendada (lido de "
        "coletores_status/coordenador_execucoes, já escritos pelos "
        "próprios jobs) - \"SEM DADO\" é dito explicitamente, nunca "
        "tratado como OK. Causa raiz de atraso/ausência de disparo: ver "
        "aba MANUAL → \"Disparo externo dos agendamentos\"."
    )
    linhas = saude_agendamentos()
    for linha in linhas:
        with st.container(border=True):
            col1, col2 = st.columns([3, 2])
            with col1:
                st.markdown(f"**{linha['rotulo']}**")
                st.markdown(_badge_agendamento(linha))
            with col2:
                st.caption(f"Última tentativa: {_fmt_hora_brt(linha['ultima_tentativa_em'])}")
                st.caption(f"Último sucesso: {_fmt_hora_brt(linha['ultimo_sucesso_em'])}")
            detalhe = linha.get("motivo_atraso") or linha.get("ultimo_erro")
            if detalhe:
                st.caption(f"Detalhe: {detalhe}")


def render_sistema(prefs: dict):
    """Ponto de entrada da aba SISTEMA, chamado pelo app.py - so aparece
    no menu de quem esta em config.obter_emails_admin() (ver app.py)."""
    st.markdown('<div class="painel-titulo">SISTEMA</div>', unsafe_allow_html=True)
    st.caption(
        "Visível só pra e-mails admin — documentação de desenvolvimento, "
        "não é um painel de dados do mercado."
    )
    st.markdown(_CSS_DOC, unsafe_allow_html=True)

    aba_changelog, aba_progresso, aba_manual, aba_agendamentos = st.tabs(
        ["CHANGELOG", "PROGRESSO", "MANUAL", "AGENDAMENTOS"]
    )

    with aba_changelog:
        _render_doc("changelog", _CHANGELOG, "CHANGELOG.md")

    with aba_progresso:
        _render_doc("progresso", _PROGRESSO, "PROGRESSO.md")

    with aba_manual:
        _render_doc("manual", _MANUAL, "MANUAL.md")

    with aba_agendamentos:
        _render_agendamentos()
