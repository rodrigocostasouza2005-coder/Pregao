# -*- coding: utf-8 -*-
"""Aba CALENDÁRIO: agenda de resultados corporativos (2026-10-01).
Ponto de entrada: render_calendario(prefs), chamado pelo app.py.

V1 só resultados (ITR/DFP) - ver data/eventos.py pra a lógica de cálculo
(CONFIRMADO/ESTIMADO/PRAZO_CVM) - nada disso muda aqui, so' a
APRESENTAÇÃO.

Reaproveita identificadores já existentes (ticker, config.IBOVESPA_SETORES
pro filtro de setor, data.cvm/data.news/data.research pro contexto do
evento) - nenhum sistema de dado novo, nenhuma chamada de IA.

REDESIGN VISUAL (2026-10-05): calendário mensal em grade (7 colunas,
SEG-DOM) + painel lateral "EVENTOS DO DIA" + detalhe sob demanda do
evento selecionado, no lugar da lista plana com `st.expander` que
despejava RESEARCH/NEWS/DOCUMENTOS/HISTÓRICO direto no corpo de cada
evento. Esse conteúdo de contexto agora fica atrás de abas compactas
(ver _painel_contexto) dentro do detalhe, só quando selecionado - nunca
mais os 4 de uma vez. Nenhuma chamada de rede nova: a grade/painel só
leem os eventos já calculados por calcular_calendario (1x por render,
não por célula/clique) - trocar de dia/evento é só re-leitura de um
dict em memória."""

import calendar
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

import config
from data.cvm import obter_documentos_cvm
from data.eventos import (
    PRIORIDADE_STATUS, STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_LABEL, STATUS_PRAZO_CVM,
    calcular_calendario_cacheado, obter_snapshot_calendario,
)
from data.news import obter_noticias
from data.research import CASAS
from data.research.store import listar_itens

_TZ_SP = ZoneInfo("America/Sao_Paulo")

_DIAS_SEMANA = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
_MESES_NOME = [
    "", "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
]
_NOMES_CASAS = [c["nome"] for c in CASAS]

_CSS_CALENDARIO = """
/* a correcao de flex-wrap das pills (rotulos longos, ex: "HISTÓRICO
   (4)" de CONTEXTO, estourando a largura do painel) foi centralizada
   em style.css (2026-10-08, auditoria de responsividade) - aplicava
   so' a 4 arquivos (duplicados) e deixava MACRO/MERCADO/TOP MERCADO/
   VISAO GERAL de fora do mesmo bug. Nada pra repetir aqui agora. */
.cal-data-grupo {
    margin-top: 0.7rem; font-size: 0.68rem; color: var(--cinza);
    letter-spacing: 0.06em; border-bottom: 1px solid var(--borda); padding-bottom: 0.25rem;
}
.cal-linha-evento { font-size: 0.8rem; padding: 0.1rem 0; font-family: 'IBM Plex Mono', monospace; }
.cal-ticker { color: var(--destaque); font-weight: 600; }
.cal-subtitulo { color: var(--cinza); font-size: 0.72rem; margin: 0.1rem 0 0.7rem 0; }
.cal-atualizado { color: var(--cinza); font-size: 0.62rem; margin: -0.3rem 0 0.6rem 0; letter-spacing: 0.02em; }
.cal-atualizado-alerta { color: var(--destaque); }

/* grade: cabecalho de dias da semana - mais respiro antes da 1a linha */
.cal-grade-cabecalho {
    display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; font-size: 0.64rem;
    color: var(--cinza); letter-spacing: 0.07em; text-align: center; margin: 0.6rem 0 0.4rem 0;
}

/* cada celula do dia: borda propria (separa visualmente do fundo, como
   uma grade/planilha de verdade - nao e' um "card"), padding generoso,
   altura minima pra nunca parecer espremida mesmo em dias sem evento */
[class*="st-key-cal_cel_"] {
    border: 1px solid var(--borda); padding: 0.4rem 0.45rem 0.55rem 0.45rem;
    margin-bottom: 0.45rem; min-height: 4.6rem;
}
/* numero do dia: bem maior e mais legivel que o resto da celula */
.st-key-cal_grade_area button { padding: 0.1rem 0 !important; min-height: 26px !important; }
.st-key-cal_grade_area button p { font-size: 1.0rem !important; font-weight: 600 !important; }

.cal-mes-titulo { text-align: center; font-size: 0.85rem; color: var(--destaque); letter-spacing: 0.06em; padding-top: 0.3rem; font-weight: 600; }

/* evento dentro da celula: 3 linhas (ticker / periodo / status), com
   respiro vertical e separador discreto entre eventos do mesmo dia */
.cal-cel-evento {
    font-family: 'IBM Plex Mono', monospace; margin-top: 0.5rem; padding-top: 0.35rem;
    border-top: 1px solid var(--borda);
}
.cal-cel-evento:first-of-type { border-top: none; margin-top: 0.35rem; padding-top: 0; }
.cal-cel-ticker { font-size: 0.74rem; font-weight: 700; color: var(--destaque); line-height: 1.3; }
.cal-cel-periodo { font-size: 0.63rem; color: var(--cinza); margin-top: 0.08rem; }
.cal-cel-status { font-size: 0.6rem; letter-spacing: 0.03em; margin-top: 0.12rem; }
.cal-cel-mais { font-size: 0.6rem; color: var(--cinza); margin-top: 0.3rem; }

/* painel lateral - mais respiro entre dia selecionado, lista de eventos e detalhe */
.cal-dia-selecionado-titulo { font-size: 0.88rem; color: var(--destaque); font-weight: 700; margin: 0.1rem 0 0.7rem 0; }
.cal-evt-status-dot { font-size: 1.15rem; text-align: center; padding-top: 0.35rem; }
.cal-detalhe-evento { font-size: 0.82rem; line-height: 1.75; padding: 0.3rem 0 0.1rem 0; }
.cal-detalhe-evento .cal-ticker { font-size: 0.95rem; }
.cal-detalhe-aviso { color: var(--cinza); font-size: 0.68rem; line-height: 1.5; margin-top: 0.5rem; }

.cal-legenda { font-size: 0.66rem; color: var(--cinza); margin-top: 0.7rem; display: flex; gap: 1.1rem; flex-wrap: wrap; }

/* CONTEXTO: respiro entre o titulo da secao, as abas e o conteudo */
.cal-contexto-titulo {
    font-size: 0.66rem; color: var(--cinza); letter-spacing: 0.06em;
    border-top: 1px solid var(--borda); padding-top: 0.7rem; margin-top: 0.8rem; margin-bottom: 0.5rem;
}
.cal-contexto-linha { font-size: 0.78rem; line-height: 1.7; padding: 0.25rem 0; font-family: 'IBM Plex Mono', monospace; }

/* mobile (bug real corrigido, 2026-10-10 - confirmado por screenshot real
   do Playwright a 390px): a grade sempre tem 7 colunas (SEG-DOM), entao
   cada celula fica com so' uns 40-45px uteis numa tela de celular - sem
   isto, o NUMERO DO DIA ("28") e o TICKER ("MGLU3") quebravam letra por
   letra dentro da celula (nenhum texto tem white-space:nowrap), ficando
   ilegiveis. white-space:nowrap + reticencias (nunca deixa o texto
   quebrar linha) + fonte/padding um pouco menores pra sobrar espaco de
   verdade pro conteudo. */
@media (max-width: 640px) {
    [class*="st-key-cal_cel_"] {
        padding: 0.2rem 0.2rem 0.3rem 0.2rem; min-height: 3.6rem;
    }
    .st-key-cal_grade_area button p { font-size: 0.82rem !important; white-space: nowrap !important; }
    .cal-cel-evento { margin-top: 0.3rem; padding-top: 0.2rem; }
    .cal-cel-ticker, .cal-cel-periodo, .cal-cel-status, .cal-cel-mais {
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .cal-cel-ticker { font-size: 0.62rem; }
    .cal-cel-periodo, .cal-cel-status, .cal-cel-mais { font-size: 0.52rem; }
    .cal-grade-cabecalho { font-size: 0.56rem; gap: 2px; }
}
"""


def _injetar_css():
    st.markdown(f"<style>{_CSS_CALENDARIO}</style>", unsafe_allow_html=True)


def _cor_status(status: str) -> str:
    return {"CONFIRMADO": "var(--alta)", "ESTIMADO": "var(--destaque)", "PRAZO_CVM": "var(--cinza)"}.get(status, "var(--cinza)")


def _badge_status(status: str) -> str:
    return f"<span style='color:{_cor_status(status)};'>●</span> {STATUS_LABEL.get(status, status)}"


def _subheader(texto: str, primeiro: bool = False):
    """Subtítulo compacto dentro de um painel (V3, 2026-10-02): separa
    visualmente PRÓXIMOS RESULTADOS de PRAZOS CVM dentro do mesmo painel
    - PRAZO CVM != data de divulgação (regra explícita desta fase, ver
    PROGRESSO.md), então as duas listas nunca podem aparecer misturadas
    sob o mesmo rótulo."""
    borda = "" if primeiro else "border-top:1px solid var(--borda); padding-top:0.4rem; margin-top:0.5rem;"
    st.markdown(
        f"<div style='font-size:0.68rem; color:var(--cinza); letter-spacing:0.05em; {borda} margin-bottom:0.3rem;'>{texto}</div>",
        unsafe_allow_html=True,
    )


def _linha_resumo(e: dict):
    st.markdown(
        f"<div class='cal-linha-evento'><span class='cal-ticker'>{e['ticker']}</span> "
        f"<span class='cinza'>{e['data'].strftime('%d/%m')}</span> · {e['periodo']} · {_badge_status(e['status'])}</div>",
        unsafe_allow_html=True,
    )


def _universo_tickers(filtro: str, prefs: dict, setor: str = None) -> list:
    if filtro == "MINHA WATCHLIST":
        return list(prefs.get("watchlist") or [])
    if filtro == "SETOR" and setor:
        return [t for t, s in config.IBOVESPA_SETORES.items() if s == setor]
    return list(config.IBOVESPA_SETORES.keys())


def _filtrar_janela(eventos: list, janela: str, hoje: date) -> list:
    dias = 7 if janela == "SEMANA" else 31
    limite = hoje + timedelta(days=dias)
    return [e for e in eventos if hoje <= e["data"] <= limite]


# ============================================================
# CONTEXTO do evento (RESEARCH/NEWS/DOCUMENTOS/HISTÓRICO) - abas
# compactas, 1 secao visivel por vez, so' aparecem quando ha' dado
# (2026-10-05: antes ficavam as 4 sempre despejadas no corpo do evento).
# ============================================================

def _dados_contexto(ticker: str) -> dict:
    """Busca (1x cada) os dados de RESEARCH/NEWS/DOCUMENTOS(CVM)/
    HISTÓRICO do ticker - mesmas fontes/cache de sempre
    (obter_documentos_cvm/obter_noticias/listar_itens), zero IA, zero
    fonte nova. obter_documentos_cvm chamado so' 1 vez aqui e
    reaproveitado por DOCUMENTOS e HISTÓRICO (evita N+1, mesma regra de
    antes)."""
    documentos_cvm = obter_documentos_cvm(ticker)
    documentos_cvm = documentos_cvm if documentos_cvm is not None else []
    itens_research = [i for i in (listar_itens(_NOMES_CASAS) or []) if ticker in (i.get("tickers") or [])][:3]
    noticias = (obter_noticias(ticker) or [])[:3]
    historico = sorted(
        (d for d in documentos_cvm if d["tipo"] == "RESULTADOS"),
        key=lambda d: d["data"], reverse=True,
    )[:4]
    return {
        "RESEARCH": itens_research,
        "NEWS": noticias,
        "DOCUMENTOS": documentos_cvm[:3],
        "HISTÓRICO": historico,
    }


def _render_contexto_research(itens: list):
    for r in itens:
        st.markdown(
            f"<div class='cal-contexto-linha'>[{r['data'][:10] if r['data'] else '—'}] {r['casa']} · "
            f"<a href='{r['link']}' target='_blank' style='color:var(--neutro); text-decoration:none;'>{r['titulo']}</a></div>",
            unsafe_allow_html=True,
        )


def _render_contexto_news(noticias: list):
    for n in noticias:
        st.markdown(
            f"<div class='cal-contexto-linha'>[{n['data'][:10]}] "
            f"<a href='{n['link']}' target='_blank' style='color:var(--neutro); text-decoration:none;'>{n['titulo']}</a></div>",
            unsafe_allow_html=True,
        )


def _render_contexto_documentos(documentos: list):
    for d in documentos:
        st.markdown(
            f"<div class='cal-contexto-linha'>[{d['data'][:10]}] "
            f"<a href='{d['link']}' target='_blank' style='color:var(--neutro); text-decoration:none;'>{(d['assunto'] or '')[:90]}</a></div>",
            unsafe_allow_html=True,
        )


def _render_contexto_historico(historico: list):
    for d in historico:
        ref = f" (ref. {str(d['data_referencia'])[:10]})" if d.get("data_referencia") else ""
        st.markdown(
            f"<div class='cal-contexto-linha'>[{d['data'][:10]}] "
            f"<a href='{d['link']}' target='_blank' style='color:var(--neutro); text-decoration:none;'>{d['tipo_label']}{ref}</a></div>",
            unsafe_allow_html=True,
        )


_RENDERIZADORES_CONTEXTO = {
    "RESEARCH": _render_contexto_research, "NEWS": _render_contexto_news,
    "DOCUMENTOS": _render_contexto_documentos, "HISTÓRICO": _render_contexto_historico,
}


def _painel_contexto(evento: dict):
    """CONTEXTO do evento selecionado - abas compactas (so' as que tem
    dado aparecem, com a contagem no rotulo), 1 secao renderizada por
    vez. Nunca aparece nada se nenhuma das 4 fontes tiver dado pro
    ticker (sem secao vazia)."""
    dados = _dados_contexto(evento["ticker"])
    disponiveis = [chave for chave, itens in dados.items() if itens]
    if not disponiveis:
        return
    st.markdown("<div class='cal-contexto-titulo'>CONTEXTO</div>", unsafe_allow_html=True)
    rotulos = {chave: f"{chave} ({len(dados[chave])})" for chave in disponiveis}
    escolha = st.pills(
        "Contexto", disponiveis, default=disponiveis[0], format_func=lambda k: rotulos[k],
        label_visibility="collapsed", key=f"cal_contexto_{evento['ticker']}_{evento['periodo']}",
    )
    escolha = escolha if escolha in disponiveis else disponiveis[0]
    _RENDERIZADORES_CONTEXTO[escolha](dados[escolha])


def _detalhe_evento(evento: dict):
    """Metadado compacto do evento selecionado - ticker/empresa/
    periodo/data/status/fonte + avisos obrigatórios. NUNCA inclui
    RESEARCH/NEWS/DOCUMENTOS/HISTÓRICO (ver _painel_contexto, chamado
    separadamente por quem usa esta função - mantém este bloco enxuto,
    sempre visível, sem dump de dados)."""
    horario_txt = f" · {evento['horario']}" if evento.get("horario") else ""
    fonte_txt = evento["fonte"]
    if evento.get("origem_url"):
        fonte_txt = f"<a href='{evento['origem_url']}' target='_blank' style='color:var(--cinza);'>{fonte_txt}</a>"
    aviso_desatualizado = ""
    if evento.get("_pode_estar_desatualizado"):
        aviso_desatualizado = (
            "<div class='cinza' style='font-size:0.68rem; margin-top:0.2rem;'>"
            "⚠ não reconfirmado na última atualização - pode estar desatualizado</div>"
        )
    # aviso explicito obrigatorio (V3, 2026-10-02): PRAZO CVM e' o prazo
    # REGULATORIO pra entrega do documento, nunca a data em que a empresa
    # de fato vai divulgar o resultado - as duas coisas sao frequentemente
    # diferentes na pratica (empresa costuma divulgar bem antes do prazo
    # maximo legal). Sem esse aviso no detalhe, o usuario podia interpretar
    # a data mostrada como "quando o resultado sai".
    aviso_prazo_cvm = ""
    if evento["status"] == STATUS_PRAZO_CVM:
        aviso_prazo_cvm = (
            "<div class='cal-detalhe-aviso'>"
            "Prazo regulatório para entrega do documento. Não representa necessariamente "
            "a data de divulgação do resultado.</div>"
        )
    st.markdown(
        f"<div class='cal-detalhe-evento'>"
        f"<div><span class='cal-ticker'>{evento['ticker']}</span> — {evento['empresa']}</div>"
        f"<div class='cinza'>{evento['periodo']} · {evento['data'].strftime('%d/%m/%Y')}{horario_txt}</div>"
        f"<div>{_badge_status(evento['status'])}</div>"
        f"<div class='cinza' style='font-size:0.68rem;'>Fonte: {fonte_txt}</div>"
        f"{aviso_prazo_cvm}"
        f"{aviso_desatualizado}"
        f"</div>",
        unsafe_allow_html=True,
    )
    # nunca esconder a origem: se havia uma fonte de confiabilidade MENOR
    # pro mesmo (ticker,periodo) que perdeu a deduplicacao (ver
    # data/eventos.py:mesclar_eventos), ela continua visivel aqui, so'
    # nao vira uma linha/evento duplicado na agenda
    for alt in evento.get("_fontes_alternativas") or []:
        st.markdown(
            f"<div class='cal-detalhe-aviso'>"
            f"também identificado como {STATUS_LABEL.get(alt['status'], alt['status'])} "
            f"({alt['data'].strftime('%d/%m/%Y')}) via {alt['fonte']}</div>",
            unsafe_allow_html=True,
        )


_LIMIAR_SNAPSHOT_DESATUALIZADO_H = 48  # coletor roda a cada 30min quando ativo (seg-sex 07h-20h) - passar disso so' acontece se o agendamento parou de verdade (ja aconteceu antes, ver data/eventos_coleta.py)


def _rotulo_atualizacao() -> tuple | None:
    """Indicador discreto de quando o snapshot foi gerado pela ultima
    vez (ver data/eventos.py:obter_snapshot_calendario) - None se nunca
    houve snapshot ainda (cai pro calculo em tempo real, sem indicador
    nenhum pra nao afirmar uma "ultima atualizacao" que nao existe).
    Retorna (texto, desatualizado: bool) - desatualizado=True so' quando
    a idade passa de _LIMIAR_SNAPSHOT_DESATUALIZADO_H (sinaliza sem
    deixar de ser discreto - so' muda a cor, nunca vira alarme grande,
    pedido explicito do Rodrigo)."""
    snapshot = obter_snapshot_calendario()
    if not snapshot or not snapshot.get("atualizado_em"):
        return None
    try:
        atualizado = datetime.fromisoformat(str(snapshot["atualizado_em"]))
    except ValueError:
        return None
    if atualizado.tzinfo is None:
        atualizado = atualizado.replace(tzinfo=timezone.utc)
    minutos = (datetime.now(timezone.utc) - atualizado).total_seconds() / 60
    if minutos < 1:
        return "atualizado agora", False
    if minutos < 60:
        return f"atualizado há {int(minutos)} min", False
    horas = minutos / 60
    desatualizado = horas > _LIMIAR_SNAPSHOT_DESATUALIZADO_H
    if horas < 24:
        return f"atualizado há {int(horas)}h", desatualizado
    return f"atualizado há {int(horas // 24)}d", desatualizado


def _legenda_status():
    itens = [(STATUS_CONFIRMADO, "CONFIRMADO"), (STATUS_ESTIMADO, "ESTIMADO"), (STATUS_PRAZO_CVM, "PRAZO CVM")]
    html = "".join(f"<span><span style='color:{_cor_status(s)};'>●</span> {rotulo}</span>" for s, rotulo in itens)
    st.markdown(f"<div class='cal-legenda'>{html}</div>", unsafe_allow_html=True)


def _painel_proximos_watchlist(prefs: dict):
    """V3 (2026-10-02): PRÓXIMOS RESULTADOS e PRAZOS CVM aparecem como
    duas listas SEPARADAS e nunca sob o mesmo rótulo - regra explícita
    desta fase: PRAZO CVM != data de divulgação. Antes, todo evento
    (hoje sempre PRAZO_CVM, ver data/eventos.py) entrava direto sob
    "PRÓXIMOS RESULTADOS DA WATCHLIST", o que podia passar a impressão
    de que o prazo regulatório É a data em que a empresa vai divulgar."""
    st.markdown('<div class="painel-titulo">RESULTADOS DA WATCHLIST</div>', unsafe_allow_html=True)
    watchlist = list(prefs.get("watchlist") or [])
    if not watchlist:
        st.info("Adicione tickers na barra lateral para ver os próximos resultados.")
        return

    eventos = calcular_calendario_cacheado(watchlist)
    if not eventos:
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Nenhum evento calculável no momento "
            "(fonte CVM indisponível).</div>",
            unsafe_allow_html=True,
        )
        return

    hoje = datetime.now(_TZ_SP).date()
    proximos_7d = sum(1 for e in eventos if (e["data"] - hoje).days <= 7)
    st.markdown(
        f"<div class='cinza' style='font-size:0.68rem; margin-bottom:0.35rem;'>{proximos_7d} evento(s) nos próximos 7 dias</div>",
        unsafe_allow_html=True,
    )

    confirmados_estimados = sorted(
        (e for e in eventos if e["status"] in (STATUS_CONFIRMADO, STATUS_ESTIMADO)),
        key=lambda e: (-PRIORIDADE_STATUS[e["status"]], e["data"]),
    )
    prazos_cvm = sorted((e for e in eventos if e["status"] == STATUS_PRAZO_CVM), key=lambda e: e["data"])

    _subheader("PRÓXIMOS RESULTADOS", primeiro=True)
    if not confirmados_estimados:
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Nenhuma data de divulgação confirmada.</div>",
            unsafe_allow_html=True,
        )
    else:
        for e in confirmados_estimados[:10]:
            _linha_resumo(e)

    if prazos_cvm:
        _subheader("PRAZOS CVM")
        for e in prazos_cvm[:10]:
            _linha_resumo(e)


# ============================================================
# Grade mensal/semanal (2026-10-05) - 7 colunas (SEG-DOM), uma linha por
# semana. MÊS usa o mês inteiro (calendar.monthdatescalendar, inclui
# dias de borda do mês anterior/seguinte, esmaecidos); SEMANA usa so' a
# semana corrente - mesma função de render pras duas (reaproveitada).
# ============================================================

def _semanas_do_mes(ano: int, mes: int) -> list:
    return calendar.Calendar(firstweekday=0).monthdatescalendar(ano, mes)


def _semana_atual(hoje: date) -> list:
    inicio = hoje - timedelta(days=hoje.weekday())
    return [[inicio + timedelta(days=i) for i in range(7)]]


def _grade_calendario(semanas: list, eventos_por_data: dict, mes_referencia, dia_selecionado: date):
    # destaque visual, nessa ordem (a ultima regra que bater "ganha" em
    # empate de especificidade): dias fora do mes esmaecidos (celula
    # inteira, nao so' os eventos) -> HOJE com borda ambar discreta ->
    # dia SELECIONADO com borda+fundo ambar mais forte (se hoje==
    # selecionado, a regra de selecionado vem depois e prevalece)
    regras = []
    if mes_referencia is not None:
        chaves_fora = [
            f"cal_cel_{dia.isoformat()}" for semana in semanas for dia in semana if dia.month != mes_referencia
        ]
        if chaves_fora:
            seletor = ", ".join(f".st-key-{c}" for c in chaves_fora)
            regras.append(f"{seletor} {{ opacity: 0.4; }}")
    chave_hoje = f"cal_cel_{datetime.now(_TZ_SP).date().isoformat()}"
    regras.append(f".st-key-{chave_hoje} {{ border-color: var(--destaque) !important; }}")
    if dia_selecionado is not None:
        chave_sel = f"cal_cel_{dia_selecionado.isoformat()}"
        regras.append(
            f".st-key-{chave_sel} {{ border-color: var(--destaque) !important; "
            f"background-color: rgba(255,160,40,0.08) !important; }}"
            f".st-key-{chave_sel} button {{ color: var(--destaque) !important; }}"
        )
    st.markdown(f"<style>{' '.join(regras)}</style>", unsafe_allow_html=True)

    with st.container(key="cal_grade_area"):
        st.markdown(
            "<div class='cal-grade-cabecalho'>" + "".join(f"<div>{d}</div>" for d in _DIAS_SEMANA) + "</div>",
            unsafe_allow_html=True,
        )
        for semana in semanas:
            cols = st.columns(7)
            for i, dia in enumerate(semana):
                with cols[i]:
                    with st.container(key=f"cal_cel_{dia.isoformat()}"):
                        eventos_dia = eventos_por_data.get(dia, [])
                        if st.button(f"{dia.day:02d}", key=f"cal_grid_dia_{dia.isoformat()}", width="stretch"):
                            st.session_state["cal_dia_selecionado"] = dia
                            st.session_state["cal_evento_selecionado"] = (
                                (eventos_dia[0]["ticker"], eventos_dia[0]["periodo"]) if eventos_dia else None
                            )
                            st.rerun()
                        # so' 3 eventos por celula (nunca espremer mais pra caber) -
                        # TICKER / PERÍODO / ●STATUS, cada um na sua linha
                        for e in eventos_dia[:3]:
                            cor = _cor_status(e["status"])
                            horario_txt = f" · {e['horario']}" if e.get("horario") else ""
                            st.markdown(
                                f"<div class='cal-cel-evento'>"
                                f"<div class='cal-cel-ticker'>{e['ticker']}</div>"
                                f"<div class='cal-cel-periodo'>{e['periodo']}{horario_txt}</div>"
                                f"<div class='cal-cel-status' style='color:{cor};'>● {STATUS_LABEL.get(e['status'], e['status'])}</div>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )
                        if len(eventos_dia) > 3:
                            st.markdown(
                                f"<div class='cal-cel-mais'>+{len(eventos_dia) - 3} evento(s)</div>",
                                unsafe_allow_html=True,
                            )


def _painel_lateral(eventos_por_data: dict, dia_selecionado: date):
    st.markdown('<div class="painel-titulo">EVENTOS DO DIA</div>', unsafe_allow_html=True)
    if dia_selecionado is None:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>Nenhum dia selecionado.</div>", unsafe_allow_html=True)
        return

    rotulo_dia = f"{dia_selecionado.day} {dia_selecionado.strftime('%b').upper()} · {_DIAS_SEMANA[dia_selecionado.weekday()]}"
    st.markdown(f"<div class='cal-dia-selecionado-titulo'>{rotulo_dia}</div>", unsafe_allow_html=True)

    eventos_dia = eventos_por_data.get(dia_selecionado, [])
    if not eventos_dia:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>Nenhum evento neste dia.</div>", unsafe_allow_html=True)
        return

    # linhas da lista ficam minimas de proposito (so' um ponto colorido
    # por status + o ticker) - empresa/periodo/status completos so'
    # aparecem 1x, no detalhe abaixo do evento selecionado (evita
    # repetir a mesma informacao duas vezes na mesma tela)
    chave_sel = st.session_state.get("cal_evento_selecionado")
    evento_selecionado = None
    for e in eventos_dia:
        chave = (e["ticker"], e["periodo"])
        if chave == chave_sel:
            evento_selecionado = e
        cor = _cor_status(e["status"])
        col_dot, col_btn = st.columns([1, 9])
        with col_dot:
            st.markdown(f"<div class='cal-evt-status-dot'><span style='color:{cor};'>●</span></div>", unsafe_allow_html=True)
        with col_btn:
            horario_txt = f"{e['horario']}  " if e.get("horario") else ""
            if st.button(f"{horario_txt}{e['ticker']}", key=f"cal_evt_{chave[0]}_{chave[1]}", width="stretch"):
                st.session_state["cal_evento_selecionado"] = chave
                st.rerun()

    if evento_selecionado is None:
        evento_selecionado = eventos_dia[0]

    st.markdown("<div style='border-top:1px solid var(--borda); margin:0.9rem 0 0.3rem 0;'></div>", unsafe_allow_html=True)
    _detalhe_evento(evento_selecionado)
    _painel_contexto(evento_selecionado)


def _dia_mais_relevante(datas_com_evento: list, hoje: date):
    """Pro auto-select ao abrir o mês/semana: prioriza o primeiro dia
    com evento a partir de hoje (inclusive); se so' houver eventos no
    passado dentro da janela visível, cai pro mais recente deles -
    nunca deixa sem seleção se houver pelo menos 1 evento visível."""
    futuros = sorted(d for d in datas_com_evento if d >= hoje)
    if futuros:
        return futuros[0]
    return max(datas_com_evento) if datas_com_evento else None


def _painel_agenda(prefs: dict):
    # titulo neutro (V3, 2026-10-02): "CALENDARIO DE RESULTADOS" sugeria
    # que todo evento listado e' uma data de resultado - hoje a imensa
    # maioria e' PRAZO CVM (cada linha ja mostra seu status/badge real,
    # ver _badge_status, so' o titulo do painel que precisava deixar de
    # prometer algo que a lista nao entrega)
    st.markdown('<div class="painel-titulo">CALENDÁRIO</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='cal-subtitulo'>Eventos de resultados e conferências das empresas</div>",
        unsafe_allow_html=True,
    )
    info_atualizacao = _rotulo_atualizacao()
    if info_atualizacao:
        texto_atualizacao, desatualizado = info_atualizacao
        classe_atualizacao = "cal-atualizado cal-atualizado-alerta" if desatualizado else "cal-atualizado"
        st.markdown(f"<div class='{classe_atualizacao}'>{texto_atualizacao}</div>", unsafe_allow_html=True)

    col_universo, col_janela = st.columns(2)
    with col_universo:
        filtro = st.pills(
            "Universo", ["MINHA WATCHLIST", "TODOS", "SETOR"], default="MINHA WATCHLIST",
            key="cal_filtro_universo", label_visibility="collapsed",
        ) or "MINHA WATCHLIST"
    setor_escolhido = None
    if filtro == "SETOR":
        setores = sorted({s for s in config.IBOVESPA_SETORES.values()})
        setor_escolhido = st.selectbox("Setor", setores, key="cal_setor", label_visibility="collapsed")
    with col_janela:
        janela = st.pills(
            "Janela", ["SEMANA", "MÊS"], default="MÊS", key="cal_janela", label_visibility="collapsed",
        ) or "MÊS"

    tickers = _universo_tickers(filtro, prefs, setor_escolhido)
    if not tickers:
        st.info("Nenhum ticker nesse filtro.")
        return

    # achado da auditoria de cobertura (2026-10-08): o calendario "parecia"
    # mostrar so' 2-3 empresas - nao e' bug de coleta/parsing/dedup (a fonte
    # CVM cobre as ~84 empresas de config.IBOVESPA_SETORES normalmente),
    # e' o filtro padrao (MINHA WATCHLIST) + a watchlist padrao de quem
    # nunca editou (config.TICKERS_PADRAO) ter so' 3 tickers. Essa legenda
    # deixa o escopo atual explicito e aponta o caminho pra ver tudo, sem
    # mudar o filtro/comportamento padrao nem inflar numero de empresas.
    if filtro == "MINHA WATCHLIST":
        total_universo = len(config.IBOVESPA_SETORES)
        st.markdown(
            f"<div class='cal-atualizado'>mostrando sua watchlist "
            f"({len(tickers)} ativo{'s' if len(tickers) != 1 else ''}) · "
            f"toque em TODOS para ver as {total_universo} empresas do Ibovespa cobertas</div>",
            unsafe_allow_html=True,
        )

    with st.spinner("Calculando calendário..."):
        eventos = calcular_calendario_cacheado(tickers)

    hoje = datetime.now(_TZ_SP).date()
    eventos = _filtrar_janela(eventos, janela, hoje)

    if not eventos:
        # mensagem pedida explicitamente (V3): so' quando NAO ha evento
        # NENHUM (nem PRAZO CVM) no periodo - se so' houver PRAZO CVM,
        # a grade abaixo mostra eles normalmente (nenhum filtro por
        # status acontece aqui, so' por janela de tempo)
        st.markdown(
            "<div class='cinza' style='font-size:0.8rem; margin-top:0.4rem;'>Nenhum evento no período.</div>",
            unsafe_allow_html=True,
        )
        return

    eventos_por_data = {}
    for e in eventos:
        eventos_por_data.setdefault(e["data"], []).append(e)
    for lista in eventos_por_data.values():
        lista.sort(key=lambda e: -PRIORIDADE_STATUS[e["status"]])

    if janela == "MÊS":
        ano_mes = st.session_state.get("cal_mes_ano")
        if ano_mes is None:
            primeiro_dia_relevante = _dia_mais_relevante(list(eventos_por_data.keys()), hoje) or hoje
            ano_mes = (primeiro_dia_relevante.year, primeiro_dia_relevante.month)
        ano_ref, mes_ref = ano_mes

        col_prev, col_titulo, col_next = st.columns([1, 4, 1])
        with col_prev:
            if st.button("←", key="cal_mes_anterior", width="stretch"):
                mes_ref -= 1
                if mes_ref == 0:
                    mes_ref, ano_ref = 12, ano_ref - 1
                st.session_state["cal_mes_ano"] = (ano_ref, mes_ref)
                st.session_state.pop("cal_dia_selecionado", None)
                st.rerun()
        with col_titulo:
            st.markdown(f"<div class='cal-mes-titulo'>{_MESES_NOME[mes_ref]} {ano_ref}</div>", unsafe_allow_html=True)
        with col_next:
            if st.button("→", key="cal_mes_proximo", width="stretch"):
                mes_ref += 1
                if mes_ref == 13:
                    mes_ref, ano_ref = 1, ano_ref + 1
                st.session_state["cal_mes_ano"] = (ano_ref, mes_ref)
                st.session_state.pop("cal_dia_selecionado", None)
                st.rerun()

        st.session_state["cal_mes_ano"] = (ano_ref, mes_ref)
        semanas = _semanas_do_mes(ano_ref, mes_ref)
        mes_referencia = mes_ref
    else:
        semanas = _semana_atual(hoje)
        mes_referencia = None

    datas_visiveis = [d for semana in semanas for d in semana]
    dia_selecionado = st.session_state.get("cal_dia_selecionado")
    if dia_selecionado not in datas_visiveis:
        # abriu o mes/semana agora (ou navegou pra um mes sem selecao
        # ainda) - seleciona automaticamente o 1o dia relevante com
        # evento, se existir (pedido explicito: nunca abrir "vazio" se
        # houver algo pra mostrar)
        datas_com_evento_visiveis = [d for d in datas_visiveis if d in eventos_por_data]
        dia_selecionado = _dia_mais_relevante(datas_com_evento_visiveis, hoje) or datas_visiveis[0]
        st.session_state["cal_dia_selecionado"] = dia_selecionado
        eventos_do_dia_inicial = eventos_por_data.get(dia_selecionado, [])
        st.session_state["cal_evento_selecionado"] = (
            (eventos_do_dia_inicial[0]["ticker"], eventos_do_dia_inicial[0]["periodo"]) if eventos_do_dia_inicial else None
        )

    col_grade, col_lateral = st.columns([3, 1])
    with col_grade:
        _grade_calendario(semanas, eventos_por_data, mes_referencia, dia_selecionado)
        _legenda_status()
    with col_lateral:
        _painel_lateral(eventos_por_data, dia_selecionado)


@st.fragment
def render_calendario(prefs: dict):
    """Ponto de entrada da aba CALENDÁRIO, chamado pelo app.py.

    @st.fragment (perf, 2026-10-08): navegação de mês, seleção de
    dia/evento e as pills de CONTEXTO disparavam st.rerun() da PÁGINA
    INTEIRA a cada clique - mesmo sintoma ("tela pula pro topo", perde
    posição de scroll, recalcula o resto da página sem necessidade) já
    corrigido em CVM/RESEARCH/TOP MERCADO/NEWS. Mesmo padrão aplicado
    aqui - não muda nenhum dado/cálculo, só o ESCOPO do rerun."""
    _injetar_css()

    with st.container(border=True):
        _painel_proximos_watchlist(prefs)

    with st.container(border=True):
        _painel_agenda(prefs)
