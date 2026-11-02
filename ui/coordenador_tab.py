# -*- coding: utf-8 -*-
"""COORDENADOR CENTRAL (Fase E, pedido do Rodrigo, 2026-10-31) - área
dedicada à orquestração de especialistas (ver data/coordenador_central/).
Mesmo visual terminal preto+âmbar do resto do app (classes CSS no mesmo
padrão de ui/research_tab.py - .painel-titulo já vem de style.css,
badges/tabela seguem o mesmo esquema de .casas-badge/.casas-tabela).

5 subabas (ver ui/navegacao.py):
- Visão Geral: contagem de especialistas, análises em andamento/
  concluídas, tempo médio.
- Especialistas: tabela com métricas reais (metricas_especialistas()).
- Execuções: análises recentes (listar_analises_recentes()).
- Histórico: abrir 1 análise específica (obter_analise(id)).
- Analisar: dispara os 3 fluxos de verdade, com spinner REAL durante a
  execução (nunca simula progresso - ver render_analisar)."""

import html

import streamlit as st

from data.coordenador_central import fluxos, persistencia
from data.coordenador_central.registro import listar_especialistas
from ui.design_system import lista_compacta, subtitulo

_CSS_COORDENADOR = """
.coord-nota { color: var(--cinza); font-size: 0.7rem; margin: 0.1rem 0 0.8rem 0; line-height: 1.5; }
.coord-metricas { display: flex; flex-wrap: wrap; gap: 1.2rem; margin-bottom: 0.8rem; }
.coord-metrica { min-width: 140px; }
.coord-metrica-valor { font-size: 1.4rem; font-weight: 600; color: var(--destaque); font-family: 'IBM Plex Mono', monospace; }
.coord-metrica-rotulo { font-size: 0.68rem; color: var(--cinza); letter-spacing: 0.03em; text-transform: uppercase; }
.coord-tabela { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.coord-tabela th {
    text-align: left; color: var(--cinza); font-size: 0.64rem; letter-spacing: 0.03em;
    padding: 0.3rem 0.5rem; border-bottom: 1px solid var(--borda);
}
.coord-tabela td { text-align: left; padding: 0.35rem 0.5rem; border-bottom: 1px solid var(--borda); vertical-align: top; }
.coord-nome { color: var(--destaque); font-weight: 600; }
.coord-badge {
    display: inline-block; border: 1px solid var(--borda); border-radius: 3px; padding: 0 6px;
    font-size: 0.6rem; letter-spacing: 0.04em; font-family: 'IBM Plex Mono', monospace;
}
.coord-badge-ok { border-color: var(--alta); color: var(--alta); }
.coord-badge-indisponivel { border-color: var(--cinza); color: var(--cinza); }
.coord-badge-erro { border-color: var(--baixa); color: var(--baixa); }
.coord-badge-andamento { border-color: var(--destaque); color: var(--destaque); }
.coord-conclusao-linha { font-size: 0.78rem; margin: 0.15rem 0; }
.coord-conclusao-tag { color: var(--cinza); font-size: 0.65rem; margin-right: 0.3rem; }
.coord-evidencia { font-size: 0.74rem; padding: 0.2rem 0; border-bottom: 1px solid var(--borda); }
"""

_FLUXOS = {
    "analise_ticker": ("Análise de ticker", fluxos.analisar_ticker),
    "comparar_casas": ("Comparar casas", fluxos.comparar_casas),
    "catalisadores": ("Identificar catalisadores", fluxos.identificar_catalisadores),
}

_SUGESTOES = [
    ("Analisar PETR4", "analise_ticker", "PETR4"),
    ("Comparar casas sobre VALE3", "comparar_casas", "VALE3"),
    ("Identificar catalisadores de WEGE3", "catalisadores", "WEGE3"),
]

def _injetar_css():
    st.markdown(f"<style>{_CSS_COORDENADOR}</style>", unsafe_allow_html=True)


def _badge_status(status: str) -> str:
    mapa = {
        "CONCLUIDA": ("coord-badge-ok", "CONCLUÍDA"),
        "OK": ("coord-badge-ok", "OK"),
        "EM_ANDAMENTO": ("coord-badge-andamento", "EM ANDAMENTO"),
        "ERRO": ("coord-badge-erro", "ERRO"),
    }
    classe, rotulo = mapa.get(status, ("coord-badge-indisponivel", status or "—"))
    return f"<span class='coord-badge {classe}'>{html.escape(rotulo)}</span>"


def _fmt_data(valor) -> str:
    if valor is None:
        return "—"
    texto = str(valor)
    if "T" in texto:
        texto = texto.split("T", 1)[0]
    return texto[:10] if len(texto) >= 10 else texto


def _metrica_html(valor, rotulo: str) -> str:
    return (
        f"<div class='coord-metrica'><div class='coord-metrica-valor'>{html.escape(str(valor))}</div>"
        f"<div class='coord-metrica-rotulo'>{html.escape(rotulo)}</div></div>"
    )


# ============================================================
# VISÃO GERAL
# ============================================================

def render_visao_geral(prefs: dict = None):
    """Contagem de especialistas (total/operacionais/com falha recente),
    análises em andamento/concluídas, última execução, tempo médio.

    "Falha recente" = taxa de sucesso < 100% nas últimas
    persistencia.N_EXECUCOES_RECENTES execuções desse especialista (ver
    persistencia.py:metricas_especialistas -> taxa_sucesso_recente_pct),
    calculado em Python sobre as linhas mais recentes de
    coordenador_especialistas_execucoes - nunca sobre o histórico
    completo (um especialista que já teve 1 falha antiga isolada mas
    está 100% saudável agora não deve aparecer como "com falha")."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">COORDENADOR CENTRAL — VISÃO GERAL</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='coord-nota'>Orquestração sob demanda das inteligências já existentes do PREGÃO "
        "(\"especialistas\") - execução paralela/isolada, consolidação determinística e persistência. "
        "Não substitui jobs/coordenador.py (esse é o agendador puro via GitHub Actions).</div>",
        unsafe_allow_html=True,
    )

    especialistas = listar_especialistas()
    metricas = persistencia.metricas_especialistas()
    total = len(especialistas)
    com_falha = sum(
        1 for e in especialistas
        if (metricas.get(e.id) or {}).get("taxa_sucesso_recente_pct", 100.0) < 100.0
    )
    operacionais = total - com_falha

    analises = persistencia.listar_analises_recentes(limite=50)
    if analises is None:
        st.warning("Histórico de análises indisponível no momento (Supabase fora do ar) - métricas abaixo refletem só o registro de especialistas.")
        analises = []
    em_andamento = sum(1 for a in analises if a.get("status") == "EM_ANDAMENTO")
    concluidas = sum(1 for a in analises if a.get("status") == "CONCLUIDA")
    ultima = analises[0] if analises else None

    duracoes = [a["duracao_ms"] for a in analises if isinstance(a.get("duracao_ms"), (int, float))]
    tempo_medio = f"{(sum(duracoes) / len(duracoes)) / 1000:.1f}s" if duracoes else "—"

    st.markdown(
        "<div class='coord-metricas'>"
        + _metrica_html(total, "Especialistas registrados")
        + _metrica_html(operacionais, "Operacionais")
        + _metrica_html(com_falha, "Com falha recente")
        + _metrica_html(em_andamento, "Análises em andamento")
        + _metrica_html(concluidas, "Análises concluídas")
        + _metrica_html(tempo_medio, "Tempo médio por análise")
        + "</div>",
        unsafe_allow_html=True,
    )

    if ultima:
        st.markdown(
            f"<div class='coord-nota'>Última execução: <b>{html.escape(ultima.get('solicitacao') or '')}</b> "
            f"({_fmt_data(ultima.get('iniciado_em'))}) — {_badge_status(ultima.get('status'))}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("Nenhuma análise executada ainda nesta instalação - use a subaba Analisar.")


# ============================================================
# ESPECIALISTAS
# ============================================================

def render_especialistas(prefs: dict = None):
    """Tabela com nome/descrição/status/última execução/quantidade de
    execuções/tempo médio/taxa de sucesso por especialista - usa
    metricas_especialistas() (dados reais do Supabase, [] / {} quando
    não há histórico ainda - nunca inventa número)."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">ESPECIALISTAS REGISTRADOS</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='coord-nota'>Cada especialista é uma inteligência Python já existente no PREGÃO, "
        "reaproveitada (nunca reescrita) - ver data/coordenador_central/registro.py.</div>",
        unsafe_allow_html=True,
    )

    especialistas = listar_especialistas()
    metricas = persistencia.metricas_especialistas()

    linhas = []
    for e in especialistas:
        m = metricas.get(e.id) or {}
        total_execucoes = m.get("total_execucoes", 0)
        taxa_recente = m.get("taxa_sucesso_recente_pct", 0)
        if total_execucoes == 0:
            status_html = "<span class='coord-badge coord-badge-indisponivel'>SEM HISTÓRICO</span>"
        elif taxa_recente >= 100.0:
            status_html = "<span class='coord-badge coord-badge-ok'>OPERACIONAL</span>"
        elif taxa_recente > 0.0:
            status_html = "<span class='coord-badge coord-badge-andamento'>INSTÁVEL</span>"
        else:
            status_html = "<span class='coord-badge coord-badge-erro'>FALHANDO</span>"

        pre_req = ", ".join(e.pre_requisitos) if e.pre_requisitos else "nenhum"
        linhas.append(
            "<tr>"
            f"<td class='coord-nome'>{html.escape(e.nome)}</td>"
            f"<td>{html.escape(e.descricao)}</td>"
            f"<td>{status_html}</td>"
            f"<td>{html.escape(pre_req)}</td>"
            f"<td>{total_execucoes}</td>"
            f"<td>{m.get('tempo_medio_ms', '—')}</td>"
            f"<td>{m.get('taxa_sucesso_pct', '—')}%</td>"
            f"<td>{_fmt_data(m.get('ultima_execucao_em'))}</td>"
            "</tr>"
        )

    tabela_html = (
        "<table class='coord-tabela'><thead><tr>"
        "<th>Especialista</th><th>Descrição</th><th>Status</th><th>Pré-requisitos</th>"
        "<th>Execuções</th><th>Tempo médio (ms)</th><th>Taxa de sucesso</th><th>Última execução</th>"
        "</tr></thead><tbody>" + "".join(linhas) + "</tbody></table>"
    )
    st.markdown(tabela_html, unsafe_allow_html=True)


# ============================================================
# EXECUÇÕES
# ============================================================

def render_execucoes(prefs: dict = None):
    """Lista as análises recentes (listar_analises_recentes()) com id/
    solicitação/horário/status/duração/erro."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">EXECUÇÕES RECENTES</div>', unsafe_allow_html=True)

    analises = persistencia.listar_analises_recentes(limite=30)
    if analises is None:
        st.warning("Histórico de execuções indisponível no momento (Supabase fora do ar).")
        return
    if not analises:
        st.info("Nenhuma análise executada ainda nesta instalação - use a subaba Analisar.")
        return

    linhas = []
    for a in analises:
        duracao = f"{a['duracao_ms']}ms" if isinstance(a.get("duracao_ms"), (int, float)) else "—"
        linhas.append(
            "<tr>"
            f"<td style='font-family:monospace;font-size:0.68rem;'>{html.escape((a.get('id') or '')[:12])}</td>"
            f"<td>{html.escape(a.get('solicitacao') or '')}</td>"
            f"<td>{html.escape(a.get('tipo_fluxo') or '')}</td>"
            f"<td>{_fmt_data(a.get('iniciado_em'))}</td>"
            f"<td>{_badge_status(a.get('status'))}</td>"
            f"<td>{duracao}</td>"
            f"<td>{html.escape(a.get('erro') or '—')}</td>"
            "</tr>"
        )
    tabela_html = (
        "<table class='coord-tabela'><thead><tr>"
        "<th>ID</th><th>Solicitação</th><th>Fluxo</th><th>Início</th><th>Status</th><th>Duração</th><th>Erro</th>"
        "</tr></thead><tbody>" + "".join(linhas) + "</tbody></table>"
    )
    st.markdown(tabela_html, unsafe_allow_html=True)


# ============================================================
# HISTÓRICO
# ============================================================

def _render_consolidado(consolidado: dict):
    # subtitulo/lista_compacta (achado real, auditoria "missao master"
    # 2026-10-31): mesmo padrao de st.markdown("**Texto**")/"- item" cru
    # ja corrigido em ui/analises_tab.py - renderizava no tamanho de
    # fonte PADRAO do Streamlit, maior que o resto do app.
    subtitulo("Resumo executivo")
    st.markdown(
        f"<div style='font-size:0.78rem;'>{html.escape(str(consolidado.get('resumo_executivo') or ''))}</div>",
        unsafe_allow_html=True,
    )

    confianca = consolidado.get("confianca") or {}
    st.markdown(
        f"<span class='coord-badge coord-badge-ok'>CONFIANÇA {html.escape(str(confianca.get('categoria') or '—'))}</span> "
        f"<span class='coord-nota'>{html.escape(confianca.get('justificativa') or '')}</span>",
        unsafe_allow_html=True,
    )

    def _linha_especialista(especialista_id, r):
        if r.get("disponivel"):
            disp = "disponível"
        else:
            motivo = html.escape(str(r.get("motivo_indisponivel")))
            disp = f"indisponível ({motivo})"
        return (
            f"<code>{html.escape(especialista_id)}</code> — {disp}: "
            f"{html.escape(r.get('resumo') or '—')}"
        )

    subtitulo("Visão por especialista")
    lista_compacta(
        _linha_especialista(especialista_id, r)
        for especialista_id, r in (consolidado.get("visao_especialistas") or {}).items()
    )

    conclusao = consolidado.get("conclusao") or []
    if conclusao:
        subtitulo("Conclusão")
        for linha in conclusao:
            st.markdown(f"<div class='coord-conclusao-linha'>{html.escape(linha)}</div>", unsafe_allow_html=True)

    pontos_atencao = consolidado.get("pontos_atencao") or []
    if pontos_atencao:
        with st.expander(f"Pontos de atenção ({len(pontos_atencao)})"):
            lista_compacta(html.escape(str(p)) for p in pontos_atencao)

    divergencias = (consolidado.get("divergencias") or {}).get("cross_comparador_memoria")
    if divergencias and divergencias.get("divergencias"):
        with st.expander(f"Divergências identificadas ({len(divergencias['divergencias'])})"):
            lista_compacta(
                f"<b>{html.escape(d['casa'])}</b> ({html.escape(str(d['tipo']))}, {html.escape(str(d['campo']))}): "
                f"comparador=<code>{html.escape(str(d['comparador']))}</code> "
                f"vs memória de research=<code>{html.escape(str(d['memoria_research']))}</code>"
                for d in divergencias["divergencias"]
            )

    evidencias = consolidado.get("evidencias") or []
    if evidencias:
        with st.expander(f"Evidências ({len(evidencias)})"):
            for e in evidencias:
                st.markdown(
                    f"<div class='coord-evidencia'><span class='coord-conclusao-tag'>{html.escape(e.get('especialista') or '')}</span>"
                    f"{html.escape(e.get('fonte') or '—')} · {_fmt_data(e.get('data'))} — "
                    f"{html.escape(e.get('titulo') or '')}</div>",
                    unsafe_allow_html=True,
                )


def render_historico(prefs: dict = None):
    """Abre 1 análise antiga específica (obter_analise(id)) - mostra
    solicitação original, especialistas participantes, evidências,
    divergências, conclusão, data e duração."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">HISTÓRICO DE ANÁLISES</div>', unsafe_allow_html=True)

    analises = persistencia.listar_analises_recentes(limite=50)
    if analises is None:
        st.warning("Histórico indisponível no momento (Supabase fora do ar).")
        return
    if not analises:
        st.info("Nenhuma análise executada ainda nesta instalação.")
        return

    opcoes = {f"{a.get('solicitacao')} — {_fmt_data(a.get('iniciado_em'))} ({(a.get('id') or '')[:8]})": a.get("id") for a in analises}
    escolha = st.selectbox("Análise", list(opcoes.keys()), key="coord_historico_escolha")
    analise_id = opcoes.get(escolha)
    if not analise_id:
        return

    analise = persistencia.obter_analise(analise_id)
    if analise is None:
        st.warning("Não foi possível carregar esta análise (Supabase indisponível no momento).")
        return

    duracao = f"{analise['duracao_ms']}ms" if isinstance(analise.get("duracao_ms"), (int, float)) else "—"
    st.markdown(
        f"**Solicitação:** {analise.get('solicitacao')}  \n"
        f"**Fluxo:** {analise.get('tipo_fluxo')} · **Ticker:** {analise.get('ticker') or '—'}  \n"
        f"**Início:** {_fmt_data(analise.get('iniciado_em'))} · **Duração:** {duracao} · "
        f"{_badge_status(analise.get('status'))}",
        unsafe_allow_html=True,
    )

    if analise.get("status") == "ERRO":
        st.error(f"Esta análise terminou em erro: {analise.get('erro') or 'motivo não especificado'}")
        return

    resultado = analise.get("resultado")
    if not resultado:
        st.info("Esta análise ainda não tem resultado consolidado (pode estar em andamento).")
        return
    _render_consolidado(resultado)


# ============================================================
# ANALISAR
# ============================================================

def render_analisar(prefs: dict = None):
    """Campo de entrada (ticker) + sugestões clicáveis que chamam os
    fluxos de fluxos.py DE VERDADE, com spinner real durante a execução
    (nunca simula progresso)."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">ANALISAR</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='coord-nota'>Aciona os especialistas de verdade, em paralelo, e consolida o resultado. "
        "Cada chamada aqui executa código real (sem dado simulado) - pode levar alguns segundos.</div>",
        unsafe_allow_html=True,
    )

    col_ticker, col_fluxo = st.columns([2, 2])
    with col_ticker:
        ticker = st.text_input("Ticker", key="coord_analisar_ticker", placeholder="ex: PETR4").strip().upper()
    with col_fluxo:
        fluxo_escolhido = st.selectbox(
            "Tipo de análise", list(_FLUXOS.keys()), key="coord_analisar_fluxo",
            format_func=lambda k: _FLUXOS[k][0],
        )

    acionar = st.button("Acionar especialistas", key="coord_analisar_botao", disabled=not ticker)

    subtitulo("Sugestões")
    cols = st.columns(len(_SUGESTOES))
    sugestao_clicada = None
    for col, (rotulo, fluxo_id, ticker_sugerido) in zip(cols, _SUGESTOES):
        with col:
            if st.button(rotulo, key=f"coord_sugestao_{fluxo_id}"):
                sugestao_clicada = (fluxo_id, ticker_sugerido)

    if sugestao_clicada:
        fluxo_id, ticker_executar = sugestao_clicada
    elif acionar:
        fluxo_id, ticker_executar = fluxo_escolhido, ticker
    else:
        return

    if not ticker_executar:
        st.warning("Informe um ticker.")
        return

    nome_fluxo, funcao_fluxo = _FLUXOS[fluxo_id]
    with st.spinner(f"Executando {nome_fluxo} para {ticker_executar} — acionando especialistas em paralelo…"):
        try:
            consolidado = funcao_fluxo(ticker_executar)
        except Exception as exc:
            st.error(f"Falha ao executar a análise: {exc!r}")
            return

    st.success(f"Análise concluída em {consolidado.get('_duracao_ms', 0) / 1000:.1f}s.")
    _render_consolidado(consolidado)
