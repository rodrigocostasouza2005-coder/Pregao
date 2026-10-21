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


def _bloco_editorial_html(texto: str) -> str:
    """Formata o briefing de texto em secoes legiveis sem alterar seu conteudo."""
    secoes = []
    titulo_secao = "BRIEFING"
    linhas_secao = []

    def fechar_secao():
        nonlocal titulo_secao, linhas_secao
        if not linhas_secao and not secoes:
            return
        itens = []
        paragrafo = []

        def fechar_paragrafo():
            if paragrafo:
                conteudo = " ".join(paragrafo)
                itens.append(
                    "<p style='margin:0 0 0.65rem;line-height:1.65;color:#E6E6E6;'>"
                    + texto_para_html(conteudo) + "</p>"
                )
                paragrafo.clear()

        for linha in linhas_secao:
            limpa = linha.strip()
            if not limpa:
                fechar_paragrafo()
                continue
            if limpa.startswith("- "):
                fechar_paragrafo()
                item = limpa[2:].strip()
                tag = ""
                m = re.match(r"^\[(INTERPRETAÇÃO|INTERPRETACAO)\]\s*", item, re.I)
                if m:
                    tag = (
                        "<span style='display:inline-block;border:1px solid #8B6A32;"
                        "border-radius:3px;padding:1px 5px;margin-right:6px;"
                        "font-size:0.65rem;letter-spacing:.04em;color:#FFC266;'>"
                        "INTERPRETAÇÃO</span>"
                    )
                    item = item[m.end():]
                itens.append(
                    "<div style='display:flex;gap:8px;align-items:flex-start;"
                    "padding:7px 9px;margin:4px 0;background:#101010;"
                    "border-left:2px solid #3A3A3A;border-radius:2px;'>"
                    "<span style='color:#FFA028;font-weight:700;'>›</span>"
                    "<div style='min-width:0;overflow-wrap:anywhere;line-height:1.55;'>"
                    + tag + texto_para_html(item) + "</div></div>"
                )
            else:
                paragrafo.append(limpa)
        fechar_paragrafo()
        if itens:
            secoes.append(
                "<section style='margin:0 0 12px;border:1px solid #292929;"
                "border-radius:5px;overflow:hidden;'>"
                "<div style='padding:9px 12px;background:#111;"
                "border-bottom:1px solid #292929;color:#FFA028;"
                "font-size:.75rem;font-weight:700;letter-spacing:.08em;'>"
                + html.escape(titulo_secao)
                + "</div><div style='padding:10px 12px;'>"
                + "".join(itens) + "</div></section>"
            )
        linhas_secao = []

    for linha in (texto or "").splitlines():
        limpa = linha.strip()
        eh_titulo = bool(
            re.match(r"^\d+\.\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9 &/—–():,-]{3,}$", limpa)
            or limpa in {"FONTES", "LIMITAÇÕES", "LIMITACOES"}
        )
        if eh_titulo:
            fechar_secao()
            titulo_secao = limpa
        else:
            linhas_secao.append(linha)
    fechar_secao()
    return (
        "<div style='max-width:100%;font-size:.84rem;overflow-wrap:anywhere;'>"
        + "".join(secoes) + "</div>"
    )


def _exibir_texto(texto: str):
    st.markdown(_bloco_editorial_html(texto), unsafe_allow_html=True)


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
            st.caption("Edição publicada · conteúdo original do e-mail. Seções e itens foram organizados visualmente para facilitar a leitura; o texto factual não é reescrito.")
            _exibir_texto(publicada["conteudo"])

    with st.expander("Gerar prévia com os dados de agora (não envia e-mail)"):
        st.caption("Monta o briefing com as mesmas funções do envio agendado — leva alguns segundos e consulta "
                   "as fontes ao vivo. Nada é enviado nem registrado.")
        if st.button("LIMPAR CACHE E ATUALIZAR PRÉVIA", key="mc_atualizar_previa"):
            _previa.clear()
            st.session_state.pop("mc_previa", None)
            st.toast("Cache da prévia limpo. Gere novamente para consultar os dados atuais.")
        if st.button("GERAR PRÉVIA", key="mc_gerar_previa"):
            with st.spinner("Montando o Morning Call..."):
                try:
                    st.session_state["mc_previa"] = _previa(_hora_ref())
                    st.session_state["mc_previa_em"] = datetime.now(TZ_SP)
                except Exception as exc:
                    st.session_state["mc_previa"] = None
                    print(f"[morning_call_tab] previa falhou: {exc!r}")
                    st.error("Não foi possível montar a prévia agora (fontes indisponíveis). Tente novamente em alguns minutos.")
        if st.session_state.get("mc_previa"):
            gerada_em = st.session_state.get("mc_previa_em")
            if gerada_em:
                st.caption(f"Prévia montada em {gerada_em.strftime('%d/%m/%Y às %H:%M:%S')} (Brasília).")
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
        if st.button("LIMPAR CACHE DO PDF", key="mc_atualizar_pdf"):
            _pdf.clear()
            st.session_state.pop("mc_pdf", None)
            st.toast("Cache do PDF limpo. Gere novamente para consultar os dados atuais.")
        if st.button("GERAR PDF DE HOJE", key="mc_gerar_pdf"):
            with st.spinner("Montando o PDF (pode levar até 1 minuto)..."):
                try:
                    st.session_state["mc_pdf"] = _pdf(_hora_ref())
                    st.session_state["mc_pdf_em"] = datetime.now(TZ_SP)
                except Exception as exc:
                    st.session_state["mc_pdf"] = None
                    print(f"[morning_call_tab] PDF falhou: {exc!r}")
                    st.error("Não foi possível gerar o PDF agora (fontes indisponíveis). Tente novamente em alguns minutos.")
        if st.session_state.get("mc_pdf"):
            gerado_em = st.session_state.get("mc_pdf_em")
            if gerado_em:
                st.caption(f"PDF montado em {gerado_em.strftime('%d/%m/%Y às %H:%M:%S')} (Brasília).")
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
        total_enviadas = sum(1 for ed in edicoes if ed.get("status") == "ENVIADA")
        total_falhas = sum(1 for ed in edicoes if ed.get("status") == "FALHA_ENVIO")
        c1, c2, c3 = st.columns(3)
        c1.metric("EDIÇÕES", len(edicoes))
        c2.metric("ENVIADAS", total_enviadas)
        c3.metric("FALHAS", total_falhas)
        st.caption("Horários de Brasília. ENVIADA = envio confirmado pelo provedor; FALHA_ENVIO = conteúdo gerado, mas sem confirmação.")
        busca = st.text_input(
            "Buscar no histórico",
            placeholder="Data, manchete, empresa ou palavra-chave…",
            key="mc_historico_busca",
        ).strip().casefold()
        filtro_status = st.selectbox(
            "Filtrar status",
            ["Todos os status", "ENVIADA", "FALHA_ENVIO"],
            key="mc_historico_status",
        )
        limite = st.selectbox(
            "Quantidade",
            [10, 20, 60],
            format_func=lambda n: f"Últimas {n} edições",
            key="mc_historico_limite",
        )
        filtradas = []
        for ed in edicoes:
            if filtro_status != "Todos os status" and ed.get("status") != filtro_status:
                continue
            texto_busca = f"{ed['data'].strftime('%d/%m/%Y')} {ed.get('status', '')} {ed.get('conteudo') or ''}".casefold()
            if busca and busca not in texto_busca:
                continue
            filtradas.append(ed)
        st.caption(f"{len(filtradas)} edição(ões) encontrada(s).")
        if not filtradas:
            st.info("Nenhuma edição corresponde aos filtros.")
            return
        for ed in filtradas[:limite]:
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
            # marca como "ja perguntado" tambem aqui: quem muda a
            # preferencia direto em MORNING CALL › Preferências (sem
            # passar pelo banner de onboarding) nao deve ver a oferta
            # reaparecer depois.
            prefs["morning_call_email_perguntado"] = True
            if persistir_fn():
                st.toast(
                    "Preferência de Morning Call por e-mail salva." if ativo
                    else "Você não vai mais receber o Morning Call por e-mail.",
                )
            else:
                st.warning("Preferência aplicada nesta sessão (banco indisponível, não foi salva).")
            st.rerun()
        st.caption(f"Destino: {usuario['email']} · dias úteis, por volta das 08h (Brasília).")
