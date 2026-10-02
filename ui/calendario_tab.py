# -*- coding: utf-8 -*-
"""Aba CALENDÁRIO: agenda de resultados corporativos (2026-10-01).
Ponto de entrada: render_calendario(prefs), chamado pelo app.py.

V1 só resultados (ITR/DFP) - ver data/eventos.py pra a lógica de cálculo
e a explicação de por que todo evento hoje é status PRAZO_CVM (não há
fonte automática confiável de data CONFIRMADA/ESTIMADA integrada ainda).

Reaproveita identificadores já existentes (ticker, config.IBOVESPA_SETORES
pro filtro de setor, data.cvm/data.news/data.research pro contexto do
evento) - nenhum sistema de dado novo, nenhuma chamada de IA."""

from datetime import date, timedelta

import streamlit as st

import config
from data.cvm import obter_documentos_cvm
from data.eventos import (
    PRIORIDADE_STATUS, STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_LABEL, STATUS_PRAZO_CVM, calcular_calendario,
)
from data.news import obter_noticias
from data.research import CASAS
from data.research.store import listar_itens

_DIAS_SEMANA = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
_NOMES_CASAS = [c["nome"] for c in CASAS]

_CSS_CALENDARIO = """
[data-testid="stButtonGroup"] { flex-wrap: wrap !important; row-gap: 0.3rem; }
.cal-data-grupo {
    margin-top: 0.7rem; font-size: 0.68rem; color: var(--cinza);
    letter-spacing: 0.06em; border-bottom: 1px solid var(--borda); padding-bottom: 0.25rem;
}
.cal-linha-evento { font-size: 0.8rem; padding: 0.1rem 0; font-family: 'IBM Plex Mono', monospace; }
.cal-ticker { color: var(--destaque); font-weight: 600; }
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


def _contexto_cvm(documentos: list):
    """documentos: ja' buscado 1x por _detalhe_evento (obter_documentos_cvm)
    e reaproveitado aqui E em _contexto_historico - evita bater 2x na
    mesma fonte pro mesmo ticker no mesmo render (pedido explicito:
    evitar N+1)."""
    if not documentos:
        return
    st.markdown("<div style='font-size:0.65rem; color:var(--cinza); margin-top:0.5rem;'>CVM · DOCUMENTOS RECENTES</div>", unsafe_allow_html=True)
    for d in documentos[:3]:
        st.markdown(
            f"<div class='cal-linha-evento'>[{d['data'][:10]}] "
            f"<a href='{d['link']}' target='_blank' style='color:var(--neutro); text-decoration:none;'>{(d['assunto'] or '')[:90]}</a></div>",
            unsafe_allow_html=True,
        )


def _contexto_historico(documentos: list):
    """HISTÓRICO (hub do evento, 2026-10-02): resultados JA' publicados
    pelo ticker - mesmo tipo "RESULTADOS" que data/eventos.py usa pra
    saber se um trimestre ja' foi entregue (ver _ja_entregou), so' que
    aqui mostrado pro usuario em vez de so' usado internamente pro
    calculo. Reaproveita os MESMOS documentos ja' buscados pra
    _contexto_cvm (nenhuma chamada nova a fonte nenhuma) - so' filtra
    por tipo e muda o rotulo, pra distinguir de "documentos recentes"
    (generico, qualquer tipo) ali em cima."""
    resultados = sorted(
        (d for d in documentos if d["tipo"] == "RESULTADOS"),
        key=lambda d: d["data"], reverse=True,
    )
    if not resultados:
        return
    st.markdown("<div style='font-size:0.65rem; color:var(--cinza); margin-top:0.5rem;'>HISTÓRICO · RESULTADOS ANTERIORES</div>", unsafe_allow_html=True)
    for d in resultados[:4]:
        ref = f" (ref. {str(d['data_referencia'])[:10]})" if d.get("data_referencia") else ""
        st.markdown(
            f"<div class='cal-linha-evento'>[{d['data'][:10]}] "
            f"<a href='{d['link']}' target='_blank' style='color:var(--neutro); text-decoration:none;'>{d['tipo_label']}{ref}</a></div>",
            unsafe_allow_html=True,
        )


def _contexto_news(ticker: str):
    noticias = obter_noticias(ticker)
    if not noticias:
        return
    st.markdown("<div style='font-size:0.65rem; color:var(--cinza); margin-top:0.5rem;'>NEWS · NOTÍCIAS RECENTES</div>", unsafe_allow_html=True)
    for n in noticias[:3]:
        st.markdown(
            f"<div class='cal-linha-evento'>[{n['data'][:10]}] "
            f"<a href='{n['link']}' target='_blank' style='color:var(--neutro); text-decoration:none;'>{n['titulo']}</a></div>",
            unsafe_allow_html=True,
        )


def _contexto_research(ticker: str):
    itens = listar_itens(_NOMES_CASAS) or []
    relacionados = [i for i in itens if ticker in (i.get("tickers") or [])][:3]
    if not relacionados:
        return
    st.markdown("<div style='font-size:0.65rem; color:var(--cinza); margin-top:0.5rem;'>RESEARCH · RELATÓRIOS RECENTES</div>", unsafe_allow_html=True)
    for r in relacionados:
        st.markdown(
            f"<div class='cal-linha-evento'>[{r['data'][:10] if r['data'] else '—'}] {r['casa']} · "
            f"<a href='{r['link']}' target='_blank' style='color:var(--neutro); text-decoration:none;'>{r['titulo']}</a></div>",
            unsafe_allow_html=True,
        )


def _detalhe_evento(evento: dict):
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
            "<div class='cinza' style='font-size:0.68rem; margin-top:0.3rem;'>"
            "Prazo regulatório para entrega do documento. Não representa necessariamente "
            "a data de divulgação do resultado.</div>"
        )
    st.markdown(
        f"<div style='font-size:0.8rem;'>"
        f"<span class='cal-ticker'>{evento['ticker']}</span> — {evento['empresa']}<br>"
        f"<span class='cinza'>{evento['periodo']} · {evento['data'].strftime('%d/%m/%Y')}{horario_txt}</span><br>"
        f"{_badge_status(evento['status'])}<br>"
        f"<span class='cinza' style='font-size:0.68rem;'>Fonte: {fonte_txt}</span>"
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
            f"<div class='cinza' style='font-size:0.65rem; margin-top:0.15rem;'>"
            f"também identificado como {STATUS_LABEL.get(alt['status'], alt['status'])} "
            f"({alt['data'].strftime('%d/%m/%Y')}) via {alt['fonte']}</div>",
            unsafe_allow_html=True,
        )

    # hub do evento (2026-10-02): RESEARCH / NEWS / CVM / HISTORICO, nessa
    # ordem (pedido explicito) - SOMENTE SE ja' houver dado no sistema
    # (secao oculta se vazia); nunca gera chamada de IA (so' le titulo/
    # data/link de fontes ja cacheadas - mesmas funcoes que EQUITY/CVM/
    # NEWS/RESEARCH ja' usam). obter_documentos_cvm chamado 1x aqui
    # (nao 2x) e reaproveitado por CVM e HISTORICO - evita N+1.
    documentos_cvm = obter_documentos_cvm(evento["ticker"]) or []
    _contexto_research(evento["ticker"])
    _contexto_news(evento["ticker"])
    _contexto_cvm(documentos_cvm)
    _contexto_historico(documentos_cvm)


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

    eventos = calcular_calendario(watchlist)
    if not eventos:
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Nenhum evento calculável no momento "
            "(fonte CVM indisponível).</div>",
            unsafe_allow_html=True,
        )
        return

    hoje = date.today()
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


def _painel_agenda(prefs: dict):
    # titulo neutro (V3, 2026-10-02): "CALENDARIO DE RESULTADOS" sugeria
    # que todo evento listado e' uma data de resultado - hoje a imensa
    # maioria e' PRAZO CVM (cada linha ja mostra seu status/badge real,
    # ver _badge_status, so' o titulo do painel que precisava deixar de
    # prometer algo que a lista nao entrega)
    st.markdown('<div class="painel-titulo">CALENDÁRIO</div>', unsafe_allow_html=True)

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

    with st.spinner("Calculando calendário..."):
        eventos = calcular_calendario(tickers)

    hoje = date.today()
    eventos = _filtrar_janela(eventos, janela, hoje)

    if not eventos:
        # mensagem pedida explicitamente (V3): so' quando NAO ha evento
        # NENHUM (nem PRAZO CVM) no periodo - se so' houver PRAZO CVM,
        # a lista abaixo mostra eles normalmente (nenhum filtro por
        # status acontece aqui, so' por janela de tempo)
        st.markdown(
            "<div class='cinza' style='font-size:0.8rem; margin-top:0.4rem;'>Nenhum evento no período.</div>",
            unsafe_allow_html=True,
        )
        return

    por_data = {}
    for e in eventos:
        por_data.setdefault(e["data"], []).append(e)

    for data_evento in sorted(por_data.keys()):
        rotulo = f"{data_evento.strftime('%d %b').upper()} — {_DIAS_SEMANA[data_evento.weekday()]}"
        st.markdown(f"<div class='cal-data-grupo'>{rotulo}</div>", unsafe_allow_html=True)
        for e in por_data[data_evento]:
            with st.expander(f"{e['ticker']}  ·  {e['empresa']}  ·  {e['periodo']}  ·  {STATUS_LABEL.get(e['status'], e['status'])}"):
                _detalhe_evento(e)


def render_calendario(prefs: dict):
    """Ponto de entrada da aba CALENDÁRIO, chamado pelo app.py."""
    _injetar_css()

    with st.container(border=True):
        _painel_proximos_watchlist(prefs)

    with st.container(border=True):
        _painel_agenda(prefs)
