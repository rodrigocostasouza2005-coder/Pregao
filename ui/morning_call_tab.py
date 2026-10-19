# -*- coding: utf-8 -*-
"""Area MORNING CALL do PREGAO 2.0 (ui/navegacao.py). Ate aqui o Morning
Call so' existia como e-mail/PDF do job agendado (jobs/morning_call.py) +
o toggle de inscricao em CONFIG - esta area da' acesso a ele no app.

NUNCA envia e-mail e nunca grava em morning_call_execucoes: le o
historico do proprio job (data/morning_call_historico.py) e, so' quando
o usuario pede (botao), monta uma previa/PDF com as MESMAS funcoes do
job (montar_morning_call/montar_edicao/gerar_pdf), sem enviar_email."""

import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from data.morning_call_historico import listar_edicoes

TZ_SP = ZoneInfo("America/Sao_Paulo")
_URL = re.compile(r"https?://[^\s<>\"')]+")


def texto_para_html(texto: str) -> str:
    """Texto do Morning Call -> HTML seguro: escapa tudo e so' depois
    transforma URL em link (links verificaveis, abrem em nova aba)."""
    escapado = html.escape(texto or "")
    return _URL.sub(lambda m: f"<a href='{m.group(0)}' target='_blank' rel='noopener'>{m.group(0)}</a>", escapado)


def _exibir_texto(texto: str):
    st.markdown(
        "<div style='white-space:pre-wrap; font-size:0.8rem; line-height:1.45; overflow-wrap:anywhere;'>"
        f"{texto_para_html(texto)}</div>",
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=1800, show_spinner=False)
def _previa(hora_ref: str) -> str:
    # hora_ref so' entra na chave do cache (no maximo 1 previa por hora)
    from jobs.morning_call import montar_morning_call

    return montar_morning_call(datetime.now(TZ_SP))


@st.cache_data(ttl=1800, show_spinner=False)
def _pdf(hora_ref: str) -> bytes:
    from data.morning_call_editorial import montar_edicao
    from jobs.morning_call_pdf import gerar_pdf

    return gerar_pdf(montar_edicao(datetime.now(TZ_SP)))


def _hora_ref() -> str:
    return datetime.now(TZ_SP).strftime("%Y-%m-%d %H")


def _cabecalho_edicao(ed: dict):
    hoje = datetime.now(TZ_SP).date()
    rotulo_dia = "hoje" if ed["data"] == hoje else "NÃO é a edição de hoje"
    cls = "alta" if ed["status"] == "ENVIADA" else "baixa"
    st.markdown(
        f"<div class='cinza' style='font-size:0.7rem; margin-bottom:0.4rem;'>Edição de "
        f"<b>{ed['data'].strftime('%d/%m/%Y')}</b> ({rotulo_dia}) · gerada às "
        f"{ed['executado_em'].strftime('%H:%M')} (Brasília) · <span class='{cls}'>{ed['status']}</span></div>",
        unsafe_allow_html=True,
    )


def render_edicao_atual(prefs: dict):
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">MORNING CALL — EDIÇÃO ATUAL</div>', unsafe_allow_html=True)
        edicoes = listar_edicoes()
        publicada = next((e for e in (edicoes or []) if e["conteudo"]), None)
        if edicoes is None:
            st.warning("Histórico indisponível (banco fora do ar) — use a prévia abaixo.")
        elif publicada is None:
            st.info("Nenhuma edição publicada registrada ainda.")
        else:
            _cabecalho_edicao(publicada)
            st.caption("Texto exatamente como foi enviado por e-mail. Fatos, [INTERPRETAÇÃO] e projeções vêm "
                       "marcados no próprio texto; cada seção cita as fontes.")
            _exibir_texto(publicada["conteudo"])

    with st.expander("Gerar prévia com os dados de agora (não envia e-mail)"):
        st.caption("Monta o briefing com as mesmas funções do envio agendado — leva alguns segundos e consulta "
                   "as fontes ao vivo. Nada é enviado nem registrado.")
        if st.button("GERAR PRÉVIA", key="mc_gerar_previa"):
            with st.spinner("Montando o Morning Call..."):
                try:
                    st.session_state["mc_previa"] = _previa(_hora_ref())
                except Exception as exc:
                    st.session_state["mc_previa"] = None
                    print(f"[morning_call_tab] previa falhou: {exc!r}")
                    st.error("Não foi possível montar a prévia agora (fontes indisponíveis). Tente novamente em alguns minutos.")
        if st.session_state.get("mc_previa"):
            _exibir_texto(st.session_state["mc_previa"])


def render_relatorio_completo(prefs: dict):
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">RELATÓRIO COMPLETO (PDF EDITORIAL)</div>', unsafe_allow_html=True)
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>O mesmo jornal em PDF anexado ao e-mail (capa, Brasil, "
            "exterior, empresas, radar setorial, fontes e limitações). O PDF das edições anteriores não é "
            "armazenado — aqui ele é montado com os dados de agora, sob demanda.</div>",
            unsafe_allow_html=True,
        )
        if st.button("GERAR PDF DE HOJE", key="mc_gerar_pdf"):
            with st.spinner("Montando o PDF (pode levar até 1 minuto)..."):
                try:
                    st.session_state["mc_pdf"] = _pdf(_hora_ref())
                except Exception as exc:
                    st.session_state["mc_pdf"] = None
                    print(f"[morning_call_tab] PDF falhou: {exc!r}")
                    st.error("Não foi possível gerar o PDF agora (fontes indisponíveis). Tente novamente em alguns minutos.")
        if st.session_state.get("mc_pdf"):
            st.download_button(
                "BAIXAR PDF", st.session_state["mc_pdf"],
                file_name=f"pregao-morning-call-{datetime.now(TZ_SP).strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf", key="mc_baixar_pdf",
            )


def render_historico(prefs: dict):
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">HISTÓRICO DE EDIÇÕES</div>', unsafe_allow_html=True)
        edicoes = listar_edicoes()
        if edicoes is None:
            st.warning("Histórico indisponível (banco fora do ar).")
            return
        if not edicoes:
            st.info("Nenhuma edição registrada ainda.")
            return
        st.caption("Uma linha por dia (horário de Brasília). ENVIADA = pelo menos um envio confirmado pelo "
                   "provedor de e-mail; FALHA_ENVIO = o texto foi gerado, mas o envio falhou.")
        for ed in edicoes[:60]:
            rotulo = f"{ed['data'].strftime('%d/%m/%Y')} · {ed['status']}"
            with st.expander(rotulo):
                if ed["conteudo"]:
                    _cabecalho_edicao(ed)
                    _exibir_texto(ed["conteudo"])
                else:
                    st.caption("Texto não registrado nesta execução.")


def render_preferencias(prefs: dict, usuario: dict, persistir_fn):
    """Mesmo toggle de efeito imediato que vivia em CONFIG (default
    DESLIGADO, opt-in explicito - ver config.PREFS_PADRAO e
    jobs/morning_call.py:listar_assinantes_morning_call). So' muda a
    preferencia do proprio usuario; nao dispara envio."""
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">PREFERÊNCIAS DE RECEBIMENTO</div>', unsafe_allow_html=True)
        ativo = st.toggle(
            "RECEBER MORNING CALL POR E-MAIL",
            value=prefs.get("morning_call_email_ativo", False),
            help=(
                "Envia o briefing diário (mercados, macro, agenda, notícias) por "
                f"e-mail às 08h BRT, em dias úteis, para {usuario['email']}. "
                "Pode ser desligado a qualquer momento - efeito imediato."
            ),
            key="toggle_morning_call_email",
        )
        if ativo != prefs.get("morning_call_email_ativo", False):
            prefs["morning_call_email_ativo"] = ativo
            if persistir_fn():
                st.toast(
                    "Preferência de Morning Call por e-mail salva." if ativo
                    else "Você não vai mais receber o Morning Call por e-mail.",
                )
            else:
                st.warning("Preferência aplicada nesta sessão (banco indisponível, não foi salva).")
            st.rerun()
        st.caption(f"Destino: {usuario['email']} · dias úteis, por volta das 08h (Brasília).")
