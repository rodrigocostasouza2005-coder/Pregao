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
.coord-tabela-wrap { width: 100%; max-width: 100%; overflow-x: auto; margin: 0.35rem 0 0.9rem; border: 1px solid var(--borda); border-radius: 3px; }
.coord-tabela { width: 100%; border-collapse: collapse; font-size: 0.76rem; }
.coord-tabela-dcf { min-width: 650px; }
.coord-tabela-sens { min-width: 520px; }
.coord-tabela-premissas { min-width: 0; }
.coord-tabela-dcf th:not(:first-child), .coord-tabela-dcf td:not(:first-child),
.coord-tabela-sens th:not(:first-child), .coord-tabela-sens td:not(:first-child),
.coord-tabela-premissas td:last-child { text-align: right; font-variant-numeric: tabular-nums; }
.coord-tabela-dcf td:nth-child(2), .coord-tabela-sens td { font-family: 'IBM Plex Mono', monospace; }
.coord-tabela tr:last-child td { border-bottom: 0; }
.coord-tabela td, .coord-tabela th { white-space: nowrap; }
.coord-tabela td:first-child, .coord-tabela th:first-child { white-space: normal; }
.coord-valuation-destaque { border-left: 3px solid var(--destaque); padding: 0.55rem 0.8rem; margin: 0.45rem 0 0.75rem; background: transparent; }
.coord-valuation-preco { color: var(--destaque); font: 600 1.35rem 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; }
.coord-valuation-legenda { color: var(--cinza); font-size: 0.68rem; margin-top: 0.15rem; }
@media (max-width: 700px) {
  .coord-tabela { font-size: 0.7rem; }
  .coord-tabela th, .coord-tabela td { padding: 0.3rem 0.4rem; }
  .coord-valuation-preco { font-size: 1.15rem; }
}
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
        "PARCIAL": ("coord-badge-andamento", "PARCIAL"),
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
    sem_historico = sum(1 for e in especialistas if not (metricas.get(e.id) or {}).get("total_execucoes", 0))
    com_falha = sum(
        1 for e in especialistas
        if (metricas.get(e.id) or {}).get("total_execucoes", 0) > 0
        and (metricas.get(e.id) or {}).get("taxa_sucesso_recente_pct", 0.0) < 100.0
    )
    operacionais = sum(
        1 for e in especialistas
        if (metricas.get(e.id) or {}).get("total_execucoes", 0) > 0
        and (metricas.get(e.id) or {}).get("taxa_sucesso_recente_pct", 0.0) >= 100.0
    )

    analises = persistencia.listar_analises_recentes(limite=50)
    if analises is None:
        st.warning("Histórico de análises indisponível no momento (Supabase fora do ar) - métricas abaixo refletem só o registro de especialistas.")
        analises = []
    em_andamento = sum(1 for a in analises if a.get("status") == "EM_ANDAMENTO")
    concluidas = sum(1 for a in analises if a.get("status") == "CONCLUIDA")
    parciais = sum(1 for a in analises if a.get("status") == "PARCIAL")
    ultima = analises[0] if analises else None

    duracoes = [a["duracao_ms"] for a in analises if isinstance(a.get("duracao_ms"), (int, float))]
    tempo_medio = f"{(sum(duracoes) / len(duracoes)) / 1000:.1f}s" if duracoes else "—"

    st.markdown(
        "<div class='coord-metricas'>"
        + _metrica_html(total, "Especialistas registrados")
        + _metrica_html(operacionais, "Operacionais")
        + _metrica_html(com_falha, "Com falha recente")
        + _metrica_html(sem_historico, "Sem evidência de execução")
        + _metrica_html(em_andamento, "Análises em andamento")
        + _metrica_html(concluidas, "Análises concluídas")
        + _metrica_html(parciais, "Análises parciais")
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

    sinal = consolidado.get("sinal_comite") or {}
    if sinal:
        subtitulo("Sinal do Comitê")
        alvo_modelo = sinal.get("preco_alvo_modelo")
        alvo_pl = sinal.get("preco_alvo_pl_setorial")
        alvo_consenso = sinal.get("preco_alvo_consenso")
        upside_modelo = sinal.get("upside_modelo_pct")
        moeda_modelo = sinal.get("moeda_preco_alvo_modelo") or "R$"
        alvo_modelo_txt = f"{moeda_modelo} {alvo_modelo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(alvo_modelo, (int, float)) else "não calculado"
        alvo_pl_txt = f"{moeda_modelo} {alvo_pl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(alvo_pl, (int, float)) else "não calculado"
        alvo_consenso_txt = f"{moeda_modelo} {alvo_consenso:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(alvo_consenso, (int, float)) else "não disponível"
        upside_modelo_txt = f"{upside_modelo:+.1f}%" if isinstance(upside_modelo, (int, float)) else "—"
        st.markdown(
            f"<div class='coord-metricas'><div class='coord-metrica'><div class='coord-metrica-valor'>{html.escape(str(sinal.get('sinal') or 'INSUFICIENTE'))}</div><div class='coord-metrica-rotulo'>Recomendação quantitativa</div></div>"
            f"<div class='coord-metrica'><div class='coord-metrica-valor'>{html.escape(str(sinal.get('score') if sinal.get('score') is not None else '—'))}</div><div class='coord-metrica-rotulo'>Score</div></div>"
            f"<div class='coord-metrica'><div class='coord-metrica-valor'>{html.escape(str(sinal.get('confianca') or '—'))}</div><div class='coord-metrica-rotulo'>Confiança</div></div></div>"
            f"<div class='coord-nota'>Alvo do Model Builder: {html.escape(alvo_modelo_txt)} · "
            f"Potencial: {html.escape(upside_modelo_txt)} · P/L setorial: {html.escape(alvo_pl_txt)} · "
            f"Consenso das casas: {html.escape(alvo_consenso_txt)}</div>"
            f"<div class='coord-nota'>{html.escape(str(sinal.get('justificativa') or ''))}</div>",
            unsafe_allow_html=True,
        )

    pareceres = consolidado.get("pareceres_analistas") or {}
    analistas = pareceres.get("analistas") or []
    if analistas:
        subtitulo("Pareceres dos analistas")
        for analista in analistas:
            analista_id = str(analista.get("id") or "")
            nome = html.escape(str(analista.get("nome") or analista_id or "Analista"))
            vies = html.escape(str(analista.get("vies") or "SEM BASE"))
            tese = html.escape(str(analista.get("tese") or "Parecer indisponível."))
            especialidade = html.escape(str(analista.get("especialidade") or ""))
            metodo_analista = html.escape(str(analista.get("metodo") or ""))
            recomendacao = html.escape(str(analista.get("recomendacao") or "INSUFICIENTE"))
            with st.expander(f"{nome} — {recomendacao} ({vies})", expanded=True):
                st.markdown(
                    f"<div class='coord-nota'>{especialidade}</div>"
                    f"<div class='coord-nota'>Método: {metodo_analista}</div>"
                    f"<b>Tese</b><div class='coord-conclusao-linha'>{tese}</div>",
                    unsafe_allow_html=True,
                )
                pros = analista.get("pros") or []
                contras = analista.get("contras") or []
                col_pro, col_con = st.columns(2)
                with col_pro:
                    st.markdown("**Pontos favoráveis**")
                    lista_compacta(html.escape(str(x)) for x in pros) if pros else st.caption("Sem evidência favorável estruturada.")
                with col_con:
                    st.markdown("**Pontos contrários**")
                    lista_compacta(html.escape(str(x)) for x in contras) if contras else st.caption("Sem evidência contrária estruturada.")

                # Preço-alvo é responsabilidade do Model Builder ou de uma casa
                # de research; os analistas de fundamentos e resultados não
                # devem exibir um campo vazio que pareça uma falha.
                if analista_id == "valuation_reviewer":
                    dcf = analista.get("dcf") or {}
                    alvo = analista.get("preco_alvo")
                    moeda_alvo = dcf.get("moeda") or analista.get("moeda") or "R$"
                    upside = analista.get("upside_pct")
                    alvo_txt = (
                        f"{moeda_alvo} {alvo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        if isinstance(alvo, (int, float)) else "Não calculado"
                    )
                    upside_txt = f"{upside:+.1f}%" if isinstance(upside, (int, float)) else "—"
                    if dcf.get("disponivel"):
                        st.markdown(
                            "<div class='coord-valuation-destaque'>"
                            "<div class='coord-valuation-legenda'>PREÇO-ALVO PRINCIPAL · DCF · CENÁRIO-BASE</div>"
                            f"<div class='coord-valuation-preco'>{html.escape(alvo_txt)}</div>"
                            f"<div class='coord-valuation-legenda'>Potencial sobre a cotação: {html.escape(upside_txt)}</div>"
                            "</div>",
                            unsafe_allow_html=True,
                        )
                        subtitulo("DCF — preços-alvo por cenário")
                        cenarios = dcf.get("cenarios") or {}
                        linhas_dcf = ["<table class='coord-tabela coord-tabela-dcf'><thead><tr><th>Cenário</th><th>Preço-alvo</th><th>Potencial</th><th>Crescimento FCF</th><th>WACC</th><th>g terminal</th></tr></thead><tbody>"]
                        for chave in ("otimista", "base", "pessimista"):
                            c = cenarios.get(chave) or {}
                            valor = c.get("preco_alvo")
                            potencial = c.get("upside_pct")
                            valor_txt = f"{moeda_alvo} {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(valor, (int, float)) else "—"
                            potencial_c = f"{potencial:+.1f}%" if isinstance(potencial, (int, float)) else "—"
                            crescimento_txt = f"{c.get('crescimento_fcf', 0) * 100:.1f}%"
                            wacc_txt = f"{c.get('wacc', 0) * 100:.1f}%"
                            terminal_txt = f"{c.get('g_terminal', 0) * 100:.1f}%"
                            linhas_dcf.append(
                                f"<tr><td>{html.escape(str(c.get('rotulo') or chave.upper()))}</td>"
                                f"<td>{html.escape(valor_txt)}</td><td>{html.escape(potencial_c)}</td>"
                                f"<td>{html.escape(crescimento_txt)}</td><td>{html.escape(wacc_txt)}</td>"
                                f"<td>{html.escape(terminal_txt)}</td></tr>"
                            )
                        linhas_dcf.append("</tbody></table>")
                        st.markdown("<div class='coord-tabela-wrap'>" + "".join(linhas_dcf) + "</div>", unsafe_allow_html=True)

                        premissas = dcf.get("premissas") or {}
                        subtitulo("Premissas utilizadas e rastreabilidade")
                        def _fmt_moeda_dcf(valor):
                            if not isinstance(valor, (int, float)):
                                return "—"
                            return f"{moeda_alvo} {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        linhas_premissas = [
                            ("FCF inicial (TTM)", _fmt_moeda_dcf(premissas.get("fcf_base"))),
                            ("Dívida líquida" + (f" — {premissas.get('origem_divida_liquida')}" if premissas.get("origem_divida_liquida") else ""), _fmt_moeda_dcf(premissas.get("divida_liquida"))),
                            ("Ações (estimadas por valor de mercado ÷ cotação)", f"{premissas.get('acoes'):,.0f}".replace(",", ".") if isinstance(premissas.get("acoes"), (int, float)) else "—"),
                            ("Crescimento FCF otimista", f"{premissas.get('crescimento_fcf_otimista') * 100:.1f}%" if isinstance(premissas.get("crescimento_fcf_otimista"), (int, float)) else "—"),
                            ("Crescimento FCF base", f"{premissas.get('crescimento_fcf_base') * 100:.1f}%" if isinstance(premissas.get("crescimento_fcf_base"), (int, float)) else "—"),
                            ("Crescimento FCF pessimista", f"{premissas.get('crescimento_fcf_pessimista') * 100:.1f}%" if isinstance(premissas.get("crescimento_fcf_pessimista"), (int, float)) else "—"),
                            ("WACC", f"{premissas.get('wacc') * 100:.1f}%" if isinstance(premissas.get("wacc"), (int, float)) else "—"),
                            ("Crescimento perpétuo", f"{premissas.get('g_terminal') * 100:.1f}%" if isinstance(premissas.get("g_terminal"), (int, float)) else "—"),
                        ]
                        tabela_premissas = ["<table class='coord-tabela coord-tabela-premissas'><thead><tr><th>Premissa</th><th>Valor utilizado</th></tr></thead><tbody>"]
                        for rotulo, valor in linhas_premissas:
                            tabela_premissas.append(f"<tr><td>{html.escape(rotulo)}</td><td>{html.escape(str(valor))}</td></tr>")
                        tabela_premissas.append("</tbody></table>")
                        st.markdown("<div class='coord-tabela-wrap'>" + "".join(tabela_premissas) + "</div>", unsafe_allow_html=True)
                        st.caption(
                            f"Fonte: {dcf.get('fonte_premissas') or 'não identificada'} · "
                            f"Data-base: {dcf.get('data_base') or 'não informada'} · "
                            f"Moeda: {dcf.get('moeda') or 'não identificada'}. "
                            "FCF, dívida e valor de mercado permanecem na unidade monetária original da fonte."
                        )

                        sensibilidade = calcular_sensibilidade_dcf(
                            dcf.get("premissas"),
                            preco_atual=analista.get("preco_atual"),
                        )
                        if sensibilidade.get("disponivel"):
                            subtitulo("Sensibilidade do cenário-base")
                            st.caption("Preço-alvo por ação variando WACC (linhas) e crescimento do FCF (colunas), em pontos percentuais. As demais premissas permanecem constantes.")
                            passos = sensibilidade.get("passos_crescimento") or []
                            crescimento_base = premissas.get("crescimento_fcf_base", 0)
                            cabecalho = "".join(f"<th>{(float(crescimento_base) + delta) * 100:.1f}%</th>" for delta in passos)
                            tabela_sens = [f"<table class='coord-tabela coord-tabela-sens'><thead><tr><th>WACC \\ Crescimento</th>{cabecalho}</tr></thead><tbody>"]
                            for linha_sens in sensibilidade.get("linhas") or []:
                                celulas = []
                                for celula in linha_sens.get("celulas") or []:
                                    valor = celula.get("preco_alvo")
                                    valor_txt = _fmt_moeda_dcf(valor) if isinstance(valor, (int, float)) else "—"
                                    celulas.append(f"<td>{html.escape(valor_txt)}</td>")
                                tabela_sens.append(f"<tr><th>{linha_sens.get('wacc', 0) * 100:.1f}%</th>{''.join(celulas)}</tr>")
                            tabela_sens.append("</tbody></table>")
                            st.markdown("<div class='coord-tabela-wrap'>" + "".join(tabela_sens) + "</div>", unsafe_allow_html=True)
                    else:
                        # O alvo por múltiplos não deve ser confundido com DCF.
                        rotulo_alvo = "Referência por P/L setorial (não é DCF)" if isinstance(alvo, (int, float)) else "Preço-alvo por DCF indisponível"
                        st.markdown(
                            f"**{rotulo_alvo}:** {html.escape(alvo_txt)}"
                            f" · potencial {html.escape(upside_txt)}",
                            unsafe_allow_html=True,
                        )
                        subtitulo("Por que o DCF não foi calculado")
                        campos = dcf.get("campos_faltantes") or []
                        nomes_campos = {
                            "fcf_base": "FCF inicial (TTM)",
                            "wacc": "WACC",
                            "g_terminal": "crescimento perpétuo",
                            "divida_liquida": "dívida líquida",
                            "acoes": "quantidade de ações",
                            "crescimento_fcf_otimista": "crescimento do FCF — otimista",
                            "crescimento_fcf_base": "crescimento do FCF — base",
                            "crescimento_fcf_pessimista": "crescimento do FCF — pessimista",
                        }
                        if campos:
                            faltantes_txt = ", ".join(nomes_campos.get(c, c) for c in campos)
                            st.warning(f"Premissas/dados ausentes: {faltantes_txt}.")
                        else:
                            st.info(dcf.get("motivo") or "As premissas explícitas ainda não foram fornecidas.")
                        st.caption(
                            "Para obter os três preços-alvo, faça uma nova análise em "
                            "Analisar → Premissas do DCF, informe as cinco taxas e acione os especialistas. "
                            "Os dados financeiros-base são coletados automaticamente; se não houver FCF, "
                            "dívida ou ações compatíveis, o DCF continuará bloqueado."
                        )

    casas = pareceres.get("casas_research") or []
    if casas:
        subtitulo("O que dizem as casas de research")
        linhas = ["<table class='coord-tabela'><thead><tr><th>Casa</th><th>Recomendação</th><th>Preço-alvo</th><th>Potencial</th><th>Publicação</th></tr></thead><tbody>"]
        for casa in casas:
            alvo = casa.get("preco_alvo")
            alvo_txt = f"R$ {alvo:,.2f}" if isinstance(alvo, (int, float)) else "—"
            alvo_txt = alvo_txt.replace(",", "X").replace(".", ",").replace("X", ".")
            upside = casa.get("upside_pct")
            upside_txt = f"{upside:+.1f}%" if isinstance(upside, (int, float)) else "—"
            titulo = html.escape(str(casa.get("titulo") or ""))
            link = casa.get("link")
            casa_nome = html.escape(str(casa.get("casa") or "—"))
            casa_html = f"<a href='{html.escape(str(link), quote=True)}' target='_blank' rel='noopener'>{casa_nome}</a>" if link else casa_nome
            linhas.append(f"<tr><td>{casa_html}<div class='coord-nota'>{titulo}</div></td><td>{html.escape(str(casa.get('recomendacao') or '—'))}</td><td>{html.escape(alvo_txt)}</td><td>{html.escape(upside_txt)}</td><td>{html.escape(_fmt_data(casa.get('data_publicacao')))}</td></tr>")
        linhas.append("</tbody></table>")
        st.markdown("".join(linhas), unsafe_allow_html=True)
        for casa in casas:
            with st.expander(f"Tese e riscos — {casa.get('casa') or 'Casa'}"):
                premissas = casa.get("tese") or []
                riscos_casa = casa.get("contras") or []
                projecoes = casa.get("projecoes") or {}
                st.markdown("**Tese / premissas publicadas**")
                lista_compacta(html.escape(str(x)) for x in premissas) if premissas else st.caption("A extração estruturada não encontrou premissas para esta publicação.")
                st.markdown("**Riscos apontados pela casa**")
                lista_compacta(html.escape(str(x)) for x in riscos_casa) if riscos_casa else st.caption("A extração estruturada não encontrou riscos para esta publicação.")
                if projecoes:
                    st.markdown("**Projeções extraídas**")
                    lista_compacta(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in projecoes.items() if v is not None)
        consenso = pareceres.get("preco_alvo_consenso") or {}
        mediana = consenso.get("mediana")
        upside = consenso.get("upside_pct")
        if isinstance(mediana, (int, float)):
            mediana_txt = f"R$ {mediana:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            upside_txt = f" · potencial {upside:+.1f}%" if isinstance(upside, (int, float)) else ""
            st.markdown(f"<div class='coord-nota'>Mediana dos preços-alvo publicados: <b>{html.escape(mediana_txt)}</b>{html.escape(upside_txt)} · {html.escape(str(consenso.get('n_casas') or 0))} casa(s). Não é preço-alvo proprietário do Pregão.</div>", unsafe_allow_html=True)

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

    premissas_dcf = None
    if fluxo_escolhido == "analise_ticker":
        with st.expander("Premissas do DCF — opcional, sem valores padrão"):
            usar_dcf = st.checkbox("Calcular DCF com premissas informadas", key="coord_dcf_ativar")
            st.caption("As cinco taxas abaixo são premissas do analista, não previsões automáticas do sistema. O Pregão coleta FCF, EBITDA, alavancagem, valor de mercado e cotação nos fundamentos disponíveis; se faltar algum dado-base ou houver incompatibilidade de moeda, o DCF será bloqueado.")
            if usar_dcf:
                c1, c2, c3 = st.columns(3)
                with c1:
                    g_otimista = st.text_input("Crescimento FCF — otimista (%)", key="coord_dcf_g_otimista", help="Taxa anual de crescimento do fluxo de caixa livre no cenário otimista.")
                    g_base = st.text_input("Crescimento FCF — base (%)", key="coord_dcf_g_base", help="Taxa anual de crescimento do fluxo de caixa livre no cenário central.")
                with c2:
                    g_pessimista = st.text_input("Crescimento FCF — pessimista (%)", key="coord_dcf_g_pessimista", help="Taxa anual de crescimento do fluxo de caixa livre no cenário pessimista.")
                    wacc = st.text_input("WACC (%)", key="coord_dcf_wacc", help="Custo médio ponderado de capital usado para descontar os fluxos. Precisa ser maior que o crescimento perpétuo.")
                with c3:
                    g_terminal = st.text_input("Crescimento perpétuo (%)", key="coord_dcf_g_terminal", help="Taxa de crescimento de longo prazo após o quinto ano.")
                entradas = {
                    "crescimento_fcf_otimista": g_otimista,
                    "crescimento_fcf_base": g_base,
                    "crescimento_fcf_pessimista": g_pessimista,
                    "wacc": wacc,
                    "g_terminal": g_terminal,
                }
                try:
                    if all(str(v).strip() for v in entradas.values()):
                        premissas_dcf = {k: float(str(v).strip().replace(",", ".")) for k, v in entradas.items()}
                    else:
                        st.caption("Preencha as cinco taxas para habilitar o DCF nesta análise.")
                except ValueError:
                    st.warning("Use apenas números nas premissas do DCF (ex.: 12,5).")

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
            if fluxo_id == "analise_ticker" and premissas_dcf is not None:
                consolidado = funcao_fluxo(ticker_executar, premissas_dcf=premissas_dcf)
            else:
                consolidado = funcao_fluxo(ticker_executar)
        except Exception as exc:
            st.error(f"Falha ao executar a análise: {exc!r}")
            return

    st.success(f"Análise concluída em {consolidado.get('_duracao_ms', 0) / 1000:.1f}s.")
    _render_consolidado(consolidado)
