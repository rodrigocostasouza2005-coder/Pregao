# -*- coding: utf-8 -*-
"""COORDENADOR CENTRAL (Fase E, pedido do Rodrigo, 2026-10-31) - área
dedicada à orquestração de especialistas (ver data/coordenador_central/).
Mesmo visual terminal preto+âmbar do resto do app (classes CSS no mesmo
padrão de ui/research_tab.py - .painel-titulo já vem de style.css,
badges/tabela seguem o mesmo esquema de .casas-badge/.casas-tabela);
reutiliza ui/design_system.py (números mono/alinhados, alta/baixa via
classe_sinal/numero_financeiro_html/variacao_html) a partir da
reformulação visual de 2026-11-06.

5 subabas (ver ui/navegacao.py):
- Visão Geral: contagem de especialistas, análises em andamento/
  concluídas, tempo médio.
- Especialistas: tabela com métricas reais (metricas_especialistas()).
- Execuções: análises recentes (listar_analises_recentes()).
- Histórico: abrir 1 análise específica (obter_analise(id)), com filtro
  opcional por ticker (client-side - ver render_historico).
- Analisar: dispara os 3 fluxos de verdade, com spinner REAL durante a
  execução (nunca simula progresso - ver render_analisar).

A análise consolidada (render_consolidado, usada por render_historico e
render_analisar) foi reorganizada em 2026-11-06 pra deixar explícito, em
qualquer análise: (1) a RECOMENDAÇÃO fundamentada do Comitê bem no topo
(_render_cabecalho_decisao - sinal_comite, nunca um resumo genérico);
(2) o que CADA especialista analisou, numa aba própria (Market
Researcher/Earnings Reviewer/Valuation/Model Builder/Valuation Reviewer -
dados usados, premissas quando houver, tese e pontos favoráveis/
contrários), em vez de uma lista vertical de expanders; (3) o que as
casas de research publicaram (dado externo, nunca confundido com
parecer de um especialista do Comitê); (4) a síntese final -
conclusão/divergências/pontos de revisão/material de apoio. A lógica de
consolidação real (data/coordenador_central/consolidacao.py e
pareceres.py) não mudou - só a apresentação; nenhum valor foi
recalculado, simplificado ou concatenado à força."""

import html
from datetime import datetime, timezone

import streamlit as st

import config
from data.coordenador_central import execucoes_agendadas, fluxos, persistencia
from data.coordenador_central.dcf import calcular_sensibilidade_dcf
from data.coordenador_central.registro import listar_especialistas
from data.empresa_perfil import obter_perfil_empresa
from data.prices import obter_nome_yf
from ui.design_system import (
    divisor, lista_compacta, numero_financeiro_html, subtitulo, variacao_html,
)
from ui.design_system import moeda_html as ds_moeda_html
from ui.design_system import pct_html as ds_pct_html
from ui.dcf_operacional import render_dcf_operacional

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
/* coord-tabela-execagendadas (redesign estrutural 2026-11-12, Agente D):
   esta tabela passou a dividir a largura da tela com outro painel (grade
   2 colunas em VISÃO GERAL, ver render_visao_geral) - sem um min-width
   explícito, a coluna livre "Resumo / erro" cortava o texto em vez de
   deixar o wrapper (.coord-tabela-wrap, que já tem overflow-x:auto)
   rolar horizontalmente - mesma técnica já usada em .coord-tabela-dcf/
   .coord-tabela-sens acima pro mesmo problema. */
.coord-tabela-execagendadas { min-width: 560px; }
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


def _idade_formatada(iso_ts: str | None) -> str:
    """Mesmo formato de ui/saude_dados_tab.py:_idade_formatada (min/h/d) -
    cópia local pra não importar entre abas que são frentes separadas
    (ver CLAUDE.md regra 8: Saúde dos Dados é frente isolada)."""
    if not iso_ts:
        return "—"
    try:
        ts = datetime.fromisoformat(str(iso_ts).replace("Z", "+00:00"))
    except ValueError:
        return "—"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    minutos = (datetime.now(timezone.utc) - ts).total_seconds() / 60
    if minutos < 0:
        minutos = 0
    if minutos < 60:
        return f"há {int(minutos)}min"
    horas = minutos / 60
    if horas < 48:
        return f"há {horas:.0f}h"
    return f"há {horas / 24:.0f}d"


def _nome_empresa_exibicao(ticker: str | None) -> str | None:
    """Nome de exibição da empresa pro ticker - mesma cascata já usada em
    ui/radar_tab.py (config.TICKER_NOME primeiro - cadastro manual,
    gratuito -, fallback obter_nome_yf - cacheado 24h em data/prices.py);
    nunca duplica essa lógica nem inventa nome novo. Usado só pro
    cabeçalho da análise consolidada (achado real, auditoria 2026-11-11:
    o cabeçalho identificava a análise só pelo ticker, nunca pelo nome da
    empresa - campo pedido explicitamente)."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return None
    try:
        nome = config.TICKER_NOME.get(ticker) or obter_nome_yf(ticker)
    except Exception:
        return None
    return nome or None


def _duracao_formatada(duracao_ms) -> str:
    if not isinstance(duracao_ms, (int, float)):
        return "—"
    if duracao_ms < 1000:
        return f"{int(duracao_ms)}ms"
    return f"{duracao_ms / 1000:.1f}s"


# ============================================================
# ÚLTIMAS EXECUÇÕES AGENDADAS (jobs/coordenador.py, cron)
# ============================================================

def _render_execucoes_agendadas():
    """Lê coordenador_execucoes (execucoes_agendadas.listar_ultimas_execucoes())
    e mostra, por tipo de rotina agendada, o status mais recente, há
    quanto tempo, duração e resumo/erro - equivalente em Streamlit do
    painel "Status dos especialistas" já existente na versão web
    (web/app/(terminal)/inteligencia/page.tsx), que até 2026-11-05 não
    tinha nenhum lado no Streamlit."""
    execucoes = execucoes_agendadas.listar_ultimas_execucoes()
    if execucoes is None:
        st.warning("Histórico de execuções agendadas indisponível no momento (Supabase fora do ar).")
        return

    por_tipo = {e.get("tipo"): e for e in execucoes}
    linhas = []
    for tipo, rotulo in execucoes_agendadas.ROTULOS_TIPO.items():
        execucao = por_tipo.get(tipo)
        if execucao is None:
            linhas.append(
                "<tr>"
                f"<td class='coord-nome'>{html.escape(rotulo)}</td>"
                "<td><span class='coord-badge coord-badge-indisponivel'>NUNCA RODOU</span></td>"
                "<td>—</td><td>—</td><td>—</td>"
                "</tr>"
            )
            continue
        status = execucao.get("status")
        resumo_ou_erro = execucao.get("erro") if status == "ERRO" else execucao.get("resumo")
        linhas.append(
            "<tr>"
            f"<td class='coord-nome'>{html.escape(rotulo)}</td>"
            f"<td>{_badge_status(status)}</td>"
            f"<td>{html.escape(_idade_formatada(execucao.get('iniciado_em')))}</td>"
            f"<td>{html.escape(_duracao_formatada(execucao.get('duracao_ms')))}</td>"
            f"<td>{html.escape(str(resumo_ou_erro) if resumo_ou_erro else '—')}</td>"
            "</tr>"
        )

    tabela_html = (
        "<div class='coord-tabela-wrap'><table class='coord-tabela coord-tabela-execagendadas'><thead><tr>"
        "<th>Rotina</th><th>Status</th><th>Última execução</th><th>Duração</th><th>Resumo / erro</th>"
        "</tr></thead><tbody>" + "".join(linhas) + "</tbody></table></div>"
    )
    st.markdown(tabela_html, unsafe_allow_html=True)


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
    está 100% saudável agora não deve aparecer como "com falha").

    REDESIGN ESTRUTURAL (2026-11-12, Agente D - redesign visual terminal):
    antes desta mudança a tela inteira era 1 coluna só, de cima pra baixo
    (título → nota → expander fechável com a tabela de execuções agendadas
    → 8 métricas num único `flex-wrap` → 1 linha de texto sobre a última
    análise) - nenhuma composição lado a lado, nenhuma hierarquia visual
    entre "especialistas" e "análises", e a tabela de execuções agendadas
    só aparecia se o usuário clicasse pra abrir o expander. Reorganizado
    em 2 REGIÕES de 2 colunas cada (mesmo mecanismo de `st.container(key=
    "coord_grid_...")` + CSS responsivo já usado por VISÃO GERAL/MERCADO/
    RESEARCH, ver style.css): (1) ESPECIALISTAS | ANÁLISES SOB DEMANDA lado
    a lado (as 8 métricas agrupadas por assunto, não mais um bloco só); (2)
    ÚLTIMAS EXECUÇÕES AGENDADAS (promovida de expander fechável pra painel
    sempre visível) | ANÁLISES SOB DEMANDA RECENTES (preview das 5 mais
    recentes, novo - mas sobre os MESMOS dados de `analises` já buscados
    pras métricas acima, zero consulta nova) com atalho pra Execuções (lista
    completa). Zero dado novo, zero cálculo novo - só reagrupamento."""
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

    duracoes = [a["duracao_ms"] for a in analises if isinstance(a.get("duracao_ms"), (int, float))]
    tempo_medio = f"{(sum(duracoes) / len(duracoes)) / 1000:.1f}s" if duracoes else "—"

    with st.container(key="coord_grid_visao_stats"):
        col_especialistas, col_analises = st.columns(2, gap="small")
        with col_especialistas:
            with st.container(border=True):
                st.markdown('<div class="painel-titulo" style="font-size:0.74rem;">ESPECIALISTAS</div>', unsafe_allow_html=True)
                st.markdown(
                    "<div class='coord-metricas'>"
                    + _metrica_html(total, "Registrados")
                    + _metrica_html(operacionais, "Operacionais")
                    + _metrica_html(com_falha, "Com falha recente")
                    + _metrica_html(sem_historico, "Sem evidência de execução")
                    + "</div>",
                    unsafe_allow_html=True,
                )
        with col_analises:
            with st.container(border=True):
                st.markdown('<div class="painel-titulo" style="font-size:0.74rem;">ANÁLISES SOB DEMANDA</div>', unsafe_allow_html=True)
                st.markdown(
                    "<div class='coord-metricas'>"
                    + _metrica_html(em_andamento, "Em andamento")
                    + _metrica_html(concluidas, "Concluídas")
                    + _metrica_html(parciais, "Parciais")
                    + _metrica_html(tempo_medio, "Tempo médio")
                    + "</div>",
                    unsafe_allow_html=True,
                )

    with st.container(key="coord_grid_visao_execucoes"):
        col_agendadas, col_demanda = st.columns(2, gap="small")
        with col_agendadas:
            with st.container(border=True):
                st.markdown('<div class="painel-titulo" style="font-size:0.74rem;">ÚLTIMAS EXECUÇÕES AGENDADAS</div>', unsafe_allow_html=True)
                st.markdown(
                    "<div class='coord-nota' style='margin-top:0;'>Rotinas do agendador via cron "
                    "(jobs/coordenador.py, tabela coordenador_execucoes) - diferente das análises sob "
                    "demanda ao lado: aqui cada linha é 1 rodada automática de 1 rotina.</div>",
                    unsafe_allow_html=True,
                )
                _render_execucoes_agendadas()
        with col_demanda:
            with st.container(border=True):
                st.markdown('<div class="painel-titulo" style="font-size:0.74rem;">ANÁLISES SOB DEMANDA RECENTES</div>', unsafe_allow_html=True)
                if not analises:
                    st.markdown(
                        "<div class='coord-nota' style='margin-top:0;'>Nenhuma análise executada ainda "
                        "nesta instalação — use a subaba Analisar.</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    linhas = []
                    for a in analises[:5]:
                        duracao = f"{a['duracao_ms']}ms" if isinstance(a.get("duracao_ms"), (int, float)) else "—"
                        linhas.append(
                            "<tr>"
                            f"<td>{html.escape(str(a.get('solicitacao') or ''))}</td>"
                            f"<td>{_badge_status(a.get('status'))}</td>"
                            f"<td>{_fmt_data(a.get('iniciado_em'))}</td>"
                            f"<td>{duracao}</td>"
                            "</tr>"
                        )
                    tabela_html = (
                        "<div class='coord-tabela-wrap'><table class='coord-tabela'><thead><tr>"
                        "<th>Solicitação</th><th>Status</th><th>Início</th><th>Duração</th>"
                        "</tr></thead><tbody>" + "".join(linhas) + "</tbody></table></div>"
                    )
                    st.markdown(tabela_html, unsafe_allow_html=True)
                    st.caption(f"{len(analises)} análise(s) no total - lista completa em COORDENADOR › Execuções.")


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
        # Erro técnico da ÚLTIMA execução (coluna `erro` de
        # coordenador_especialistas_execucoes, já gravada, antes nunca
        # exibida em nenhuma tela - achado real, auditoria 2026-11-05).
        # Nunca HTML cru: html.escape protege contra texto de exceção
        # que por acaso contenha caracteres de markup.
        ultimo_erro = m.get("ultimo_erro_tecnico")
        erro_titulo = html.escape(ultimo_erro) if ultimo_erro else ""
        erro_html = (
            f"<span title='{erro_titulo}' style='cursor:help;'>{html.escape(ultimo_erro[:60])}"
            f"{'…' if len(ultimo_erro) > 60 else ''}</span>"
            if ultimo_erro else "—"
        )
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
            f"<td>{erro_html}</td>"
            "</tr>"
        )

    tabela_html = (
        "<div class='coord-tabela-wrap'><table class='coord-tabela'><thead><tr>"
        "<th>Especialista</th><th>Descrição</th><th>Status</th><th>Pré-requisitos</th>"
        "<th>Execuções</th><th>Tempo médio (ms)</th><th>Taxa de sucesso</th><th>Última execução</th>"
        "<th>Último erro técnico</th>"
        "</tr></thead><tbody>" + "".join(linhas) + "</tbody></table></div>"
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
        "<div class='coord-tabela-wrap'><table class='coord-tabela'><thead><tr>"
        "<th>ID</th><th>Solicitação</th><th>Fluxo</th><th>Início</th><th>Status</th><th>Duração</th><th>Erro</th>"
        "</tr></thead><tbody>" + "".join(linhas) + "</tbody></table></div>"
    )
    st.markdown(tabela_html, unsafe_allow_html=True)


# ============================================================
# HISTÓRICO
# ============================================================

def _badge_recomendacao(recomendacao: str) -> str:
    """Mesmo vocabulário visual de _badge_status (ok=var(--alta), erro=
    var(--baixa), andamento=var(--destaque) pra "requer atenção",
    indisponivel=var(--cinza) pra "sem base") - nunca uma paleta nova só
    pra recomendação de analista. Cobre os 3 vocabulários de recomendação
    que convivem nesta tela: COMPRA/NEUTRO/VENDA/INSUFICIENTE (Market/
    Earnings/Valuation/casas de research), MODELADO/INSUFICIENTE (Model
    Builder) e APROVADO/COM RESSALVAS/INSUFICIENTE (Valuation Reviewer)."""
    texto = str(recomendacao or "").upper()
    if texto in ("COMPRA", "APROVADO", "MODELADO", "DESCONTO RELATIVO"):
        classe = "coord-badge-ok"
    elif texto in ("VENDA", "PRÊMIO RELATIVO"):
        classe = "coord-badge-erro"
    elif texto in ("NEUTRO", "MISTO", "COM RESSALVAS"):
        classe = "coord-badge-andamento"
    else:
        classe = "coord-badge-indisponivel"
    return f"<span class='coord-badge {classe}'>{html.escape(str(recomendacao or '—'))}</span>"


# Promovidos pro design system na onda "Visão 360" (2026-11-26): a tela
# nova (ui/visao_360_tab.py) precisava exatamente destes 2 formatadores -
# duplicá-los lá seria a 2a cópia da mesma regra. A implementação agora
# mora em ui/design_system.py (moeda_html/pct_html, docstrings completas
# lá); estes 2 nomes continuam existindo como alias porque são usados 40+
# vezes neste módulo e exercitados por nome nos testes - zero ponto de
# chamada tocado, zero mudança de comportamento.
_moeda_html = ds_moeda_html
_pct_html = ds_pct_html


_CORES_RECOMENDACAO = {"COMPRA": "var(--alta)", "VENDA": "var(--baixa)", "NEUTRO": "var(--neutro)"}


def _cor_recomendacao(recomendacao: str) -> str:
    """Cor do texto grande de recomendação no cabeçalho - var(--alta)/
    var(--baixa) pra COMPRA/VENDA (mesmas variáveis de classe_sinal(),
    nunca um hex novo), var(--neutro) pra NEUTRO (neutro de propósito,
    não é "positivo" nem "negativo" - classe_sinal() não serve aqui
    porque seu critério é só 2 vias, >=0 é "alta"). INSUFICIENTE
    (ausência de sinal, não um terceiro veredito) cai no cinza."""
    return _CORES_RECOMENDACAO.get(str(recomendacao or "").upper(), "var(--cinza)")


def _badge_confianca(categoria: str) -> str:
    """Badge de confiança da consolidação (ALTA/MEDIA/BAIXA/INSUFICIENTE,
    ver data/coordenador_central/consolidacao.py:_confianca) - cor varia
    com a categoria real (antes da reformulação visual, o badge era
    sempre 'coord-badge-ok'/verde mesmo quando a confiança era BAIXA ou
    INSUFICIENTE)."""
    mapa = {
        "ALTA": "coord-badge-ok", "MEDIA": "coord-badge-andamento",
        "BAIXA": "coord-badge-erro", "INSUFICIENTE": "coord-badge-indisponivel",
    }
    classe = mapa.get(str(categoria or "").upper(), "coord-badge-indisponivel")
    return f"<span class='coord-badge {classe}'>CONFIANÇA {html.escape(str(categoria or '—'))}</span>"


def _render_cabecalho_decisao(consolidado: dict):
    """Cabeçalho único no topo da análise consolidada: recomendação
    quantitativa do Comitê (sinal_comite - COMPRA/NEUTRO/VENDA/
    INSUFICIENTE), confiança da consolidação e resumo executivo - tudo
    que antes ficava espalhado em 2 blocos (Resumo executivo + Sinal do
    Comitê, nessa ordem) agora concentrado num só lugar, na frente de
    tudo (reformulação visual 2026-11-06, pedido do Rodrigo: "resultado
    final deve apresentar recomendação fundamentada"). A lógica de
    consolidação (data/coordenador_central/consolidacao.py e pareceres.py)
    não muda - só a apresentação.

    REDESIGN ESTRUTURAL (2026-11-12, Agente D): antes, narrativa (empresa/
    recomendação/confiança/resumo/justificativa) e o painel numérico de
    preços-alvo ficavam EMPILHADOS, nessa ordem, ocupando a largura toda os
    dois - o leitor via primeiro um bloco de texto, só depois os números.
    Agora é um painel de decisão em 2 colunas lado a lado (mesmo mecanismo
    de grade responsiva de VISÃO GERAL/MERCADO, `st.container(key=
    "coord_grid_...")`, ver style.css): esquerda = narrativa da decisão
    (o "porquê"), direita = os preços-alvo/potencial (o "quanto") - lidos
    ao mesmo tempo, não em sequência. Usada por HISTÓRICO e ANALISAR (toda
    análise consolidada passa por aqui). Nenhum campo novo, nenhum valor
    recalculado - só a composição."""
    sinal = consolidado.get("sinal_comite") or {}
    confianca = consolidado.get("confianca") or {}
    recomendacao = str(sinal.get("sinal") or "INSUFICIENTE")

    with st.container(key="coord_grid_cabecalho_decisao"):
        col_narrativa, col_numeros = st.columns([0.52, 0.48], gap="small")
        with col_narrativa:
            # Empresa + ticker no topo - achado real (auditoria 2026-11-11): a
            # análise consolidada nunca identificava QUAL empresa estava sendo
            # analisada no próprio cabeçalho (só aparecia em texto corrido no
            # resumo executivo, ou fora desta função, no cabeçalho de
            # render_historico - render_analisar não mostrava nada). ticker vem
            # de consolidado["ticker"] (consolidacao.consolidar) com fallback pro
            # campo legado em pareceres_analistas, pra não quebrar consolidados
            # antigos/fixtures de teste que só tinham o campo lá.
            ticker = consolidado.get("ticker") or (consolidado.get("pareceres_analistas") or {}).get("ticker")
            if ticker:
                nome_empresa = _nome_empresa_exibicao(ticker)
                rotulo_empresa = f"{nome_empresa} ({ticker})" if nome_empresa and nome_empresa.upper() != ticker else ticker
                st.markdown(
                    f"<div style='font-size:0.95rem; font-weight:600; margin-bottom:0.25rem;'>{html.escape(rotulo_empresa)}</div>",
                    unsafe_allow_html=True,
                )

            st.markdown(
                f"<div style='display:flex; align-items:baseline; gap:0.6rem; flex-wrap:wrap; margin-bottom:0.2rem;'>"
                f"<span style='font-size:0.68rem; color:var(--cinza); letter-spacing:0.05em; text-transform:uppercase;'>RECOMENDAÇÃO DO COMITÊ</span>"
                f"<span style='font-size:1.3rem; font-weight:700; color:{_cor_recomendacao(recomendacao)};'>{html.escape(recomendacao)}</span>"
                f"{_badge_confianca(confianca.get('categoria'))}"
                "</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div style='font-size:0.78rem; margin-bottom:0.4rem;'>{html.escape(str(consolidado.get('resumo_executivo') or ''))}</div>"
                f"<div class='coord-nota' style='margin-bottom:0.6rem;'>{html.escape(confianca.get('justificativa') or '')}</div>",
                unsafe_allow_html=True,
            )
            if sinal:
                st.markdown(
                    f"<div class='coord-nota'>{html.escape(str(sinal.get('justificativa') or ''))}</div>"
                    "<div class='coord-nota'>Cálculo independente do parecer de Valuation (aba abaixo): este sinal "
                    "pontua ROE, margem, dívida, FCF, crescimento e P/L relativo (sem usar DCF), enquanto a "
                    "recomendação do parecer de Valuation vem do upside do DCF oficial. Os dois podem divergir "
                    "para o mesmo ticker.</div>",
                    unsafe_allow_html=True,
                )
        with col_numeros:
            _render_metricas_preco_alvo(sinal)


def _render_metricas_preco_alvo(sinal: dict):
    """Painel numérico de preços-alvo/potencial do sinal quantitativo do
    Comitê - extraído de dentro de `_render_cabecalho_decisao` (ver
    docstring lá) pra virar a COLUNA DIREITA do cabeçalho de decisão, ao
    lado da narrativa, em vez de um bloco empilhado abaixo dela. Mesmos
    6 campos de sempre, nenhum valor recalculado."""
    if not sinal:
        return
    alvo_modelo = sinal.get("preco_alvo_modelo")
    alvo_pl = sinal.get("preco_alvo_pl_setorial")
    alvo_consenso = sinal.get("preco_alvo_consenso")
    upside_modelo = sinal.get("upside_modelo_pct")
    moeda_modelo = sinal.get("moeda_preco_alvo_modelo") or "R$"
    # Preço atual + data de referência (campo pedido explicitamente,
    # achado real auditoria 2026-11-11: o dado já existia em
    # fundamentos/sinal_comite, mas nenhuma tela mostrava o preço
    # atual da cotação usada como base de todos os upsides acima).
    preco_atual = sinal.get("preco_atual")
    data_referencia = _fmt_data(sinal.get("preco_atual_consultado_em"))
    rotulo_preco_atual = "Preço atual" + (f" · {data_referencia}" if data_referencia != "—" else "")
    st.markdown(
        f"<div class='coord-metricas'>"
        f"<div class='coord-metrica'><div class='coord-metrica-valor'>{_moeda_html(preco_atual, moeda_modelo, fallback='dado insuficiente')}</div><div class='coord-metrica-rotulo'>{html.escape(rotulo_preco_atual)}</div></div>"
        f"<div class='coord-metrica'><div class='coord-metrica-valor'>{html.escape(str(sinal.get('score') if sinal.get('score') is not None else '—'))}</div><div class='coord-metrica-rotulo'>Score do sinal quantitativo</div></div>"
        f"<div class='coord-metrica'><div class='coord-metrica-valor'>{_moeda_html(alvo_modelo, moeda_modelo, fallback='não calculado')}</div><div class='coord-metrica-rotulo'>Alvo — Model Builder (DCF)</div></div>"
        f"<div class='coord-metrica'><div class='coord-metrica-valor'>{variacao_html(upside_modelo) if isinstance(upside_modelo, (int, float)) else '—'}</div><div class='coord-metrica-rotulo'>Potencial sobre a cotação</div></div>"
        f"<div class='coord-metrica'><div class='coord-metrica-valor'>{_moeda_html(alvo_pl, moeda_modelo, fallback='não calculado')}</div><div class='coord-metrica-rotulo'>Alvo — P/L setorial</div></div>"
        f"<div class='coord-metrica'><div class='coord-metrica-valor'>{_moeda_html(alvo_consenso, moeda_modelo, fallback='não disponível')}</div><div class='coord-metrica-rotulo'>Consenso das casas de research</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _linhas_evidencias_perfil(evidencias: list) -> list:
    """Formata evidências de research (casa/texto/data_publicacao/link -
    mesmo shape usado em todo data/empresa_perfil.py) como linhas HTML
    'CASA (data): texto', com link quando houver. Nenhum texto inventado:
    só reformata trechos verbatim já extraídos pela pipeline de research
    (ver data/empresa_perfil.py:_evidencias_por_palavras_chave)."""
    linhas = []
    for evidencia in evidencias or []:
        casa = html.escape(str(evidencia.get("casa") or "—"))
        data_evidencia = html.escape(_fmt_data(evidencia.get("data_publicacao")))
        texto = html.escape(str(evidencia.get("texto") or ""))
        link = evidencia.get("link")
        casa_html = (
            f"<a href='{html.escape(str(link), quote=True)}' target='_blank' rel='noopener'>{casa}</a>"
            if link else casa
        )
        linhas.append(f"{casa_html} ({data_evidencia}): {texto}")
    return linhas


def _render_pergunta_perfil(pergunta: dict | None, rotulo: str):
    """1 das 18 perguntas do Perfil da Empresa (ver data/empresa_perfil.py)
    - disponivel=False mostra o motivo_indisponivel literal que a própria
    camada de dados já traz (NUNCA um texto genérico de preenchimento,
    regra explícita do pedido original do Rodrigo); disponivel=True sem
    evidências estruturadas (ex.: pressões de margem quando só há o dado
    numérico, já exibido nos indicadores financeiros do parecer do
    especialista) mostra uma nota honesta em vez de uma lista vazia.

    O rótulo usa `subtitulo()` (design system) desde 2026-11-26. Era
    `st.markdown(f"**{rotulo}**")` - a única forma de conteúdo do app que
    renderiza no tamanho de fonte PADRÃO do Streamlit, bem maior que o
    resto da tela (ver docstring de ui/design_system.py, que nasceu
    exatamente pra isso). Confirmado com Playwright na Visão 360: cada
    pergunta do perfil saía com um título gigante no meio de um bloco de
    texto de 0.78rem, quebrando a hierarquia visual da página. Mesmo
    tratamento aplicado aos demais `**rótulos**` deste módulo (pontos
    favoráveis/contrários, tese/riscos/projeções das casas e os blocos da
    síntese de IA)."""
    pergunta = pergunta or {}
    subtitulo(rotulo)
    if not pergunta.get("disponivel"):
        st.caption(str(pergunta.get("motivo_indisponivel") or "Dado indisponível para este ticker."))
        return
    linhas = _linhas_evidencias_perfil(pergunta.get("evidencias"))
    if linhas:
        lista_compacta(linhas)
    else:
        st.caption("Disponível, mas sem trecho de research estruturado associado (ver indicadores financeiros do parecer do especialista para o dado numérico).")


def _render_pergunta_quebra_tese_perfil(pergunta: dict | None):
    """Pergunta 18 ('o que quebraria a tese') - repasse de riscos (mesmo
    shape das demais perguntas de evidência) + divergência entre casas
    sobre as premissas centrais (dado próprio desta pergunta, calculado
    em data/research/comparador.py, nunca uma conclusão nova composta
    aqui)."""
    pergunta = pergunta or {}
    subtitulo("O que quebraria a tese")
    if not pergunta.get("disponivel"):
        st.caption(str(pergunta.get("motivo_indisponivel") or "Dado indisponível para este ticker."))
        return
    linhas = _linhas_evidencias_perfil(pergunta.get("evidencias"))
    for divergencia in (pergunta.get("dado") or {}).get("divergencia_entre_casas") or []:
        premissa = html.escape(str(divergencia.get("premissa") or ""))
        mencionam = ", ".join(html.escape(str(c)) for c in (divergencia.get("casas_que_mencionam") or [])) or "—"
        nao_mencionam = ", ".join(html.escape(str(c)) for c in (divergencia.get("casas_que_nao_mencionam") or [])) or "—"
        linhas.append(f"Divergência entre casas sobre a premissa \"{premissa}\" — mencionam: {mencionam}; não mencionam: {nao_mencionam}")
    if linhas:
        lista_compacta(linhas)
    else:
        st.caption("Disponível, mas sem trecho de risco estruturado associado.")


def _render_perfil_identificacao(identificacao: dict, perguntas: dict):
    """Bloco (a) do Perfil da Empresa: 'o que a empresa faz' e 'como
    ganha dinheiro' são o MESMO resumo institucional repassado pela
    camada de dados (yfinance não separa as duas perguntas) - mostrado
    uma vez só, com setor/indústria/país como metadados curtos ao
    lado (identificacao, não perguntas - já vem separado na origem)."""
    metadados = []
    for rotulo, chave in (("Setor", "setor"), ("Indústria", "industria"), ("País", "pais")):
        valor = (identificacao or {}).get(chave)
        if valor:
            metadados.append(f"{html.escape(rotulo)}: {html.escape(str(valor))}")
    subtitulo("O que a empresa faz / como ganha dinheiro")
    if metadados:
        st.markdown(
            f"<div class='coord-nota' style='margin-top:-0.2rem;'>{' · '.join(metadados)}</div>",
            unsafe_allow_html=True,
        )
    pergunta = (perguntas or {}).get("o_que_a_empresa_faz") or {}
    if pergunta.get("disponivel"):
        st.markdown(
            f"<div style='font-size:0.78rem; line-height:1.5;'>{html.escape(str(pergunta.get('dado') or ''))}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption(str(pergunta.get("motivo_indisponivel") or "Dado indisponível para este ticker."))


def _render_perfil_momento_atual(perguntas: dict):
    """Bloco (b) do Perfil da Empresa: perspectivas, pressões de margem,
    riscos e o que quebraria a tese - as 4 perguntas que respondem
    diretamente ao pedido do Rodrigo ('resumo... do momento que ela está
    passando')."""
    subtitulo("Momento atual")
    _render_pergunta_perfil((perguntas or {}).get("perspectivas"), "Perspectivas")
    _render_pergunta_perfil((perguntas or {}).get("pressoes_de_margem"), "Pressões sobre a margem")
    _render_pergunta_perfil((perguntas or {}).get("riscos"), "Principais riscos")
    _render_pergunta_quebra_tese_perfil((perguntas or {}).get("o_que_quebraria_a_tese"))


def _render_perfil_posicionamento(perguntas: dict):
    """Bloco (d) do Perfil da Empresa: posição competitiva, vantagens
    competitivas e concorrentes - só existem quando algum relatório de
    research monitorado menciona o assunto explicitamente (ver
    data/empresa_perfil.py); quando não, cada pergunta mostra seu
    próprio motivo, nunca omite a seção inteira em silêncio."""
    subtitulo("Posicionamento competitivo")
    _render_pergunta_perfil((perguntas or {}).get("posicao_competitiva"), "Posição competitiva")
    _render_pergunta_perfil((perguntas or {}).get("vantagens_competitivas"), "Vantagens competitivas")
    _render_pergunta_perfil((perguntas or {}).get("concorrentes"), "Concorrentes")


def _render_perfil_research_consenso(research: dict):
    """Achado real (auditoria de continuação, 2026-11-23): data/
    empresa_perfil.py:obter_perfil_empresa já calcula e devolve a chave
    'research' completa (dispersão de preço-alvo, divergência de
    recomendação entre casas e evolução histórica - quem mudou de
    posição hoje), mas o único consumidor desta função em ui/*.py nunca
    lia essa chave - dado real já calculado (zero custo novo, zero IA
    nova, mesma fonte já usada por ui/analises_tab.py) ficava sem tela
    justamente na aba pensada pra responder "o que os analistas estão
    dizendo" (pedido literal do Rodrigo). Mostra só o que já existe,
    nunca recalcula nada; indisponibilidade é sempre explícita (nunca
    uma seção ausente em silêncio)."""
    research = research or {}
    subtitulo("Consenso entre casas de research")
    if not research.get("disponivel"):
        st.caption(str(research.get("motivo") or "Research consolidado indisponível para este ticker."))
        return
    if not research.get("casas"):
        # disponivel=True com 0 casas (ver data/research/comparador.py:
        # comparar_ticker, "banco respondeu, zero publicacao estruturada
        # pra esse ticker") - dispersao/divergencia/evolucao nem existem
        # nesse caso (comparar_ticker não as calcula sem nenhuma casa).
        # Mostra o motivo explícito em vez de uma seção silenciosamente
        # vazia (mesmo princípio de todo o resto do Perfil da Empresa).
        st.caption(str(research.get("motivo") or "Nenhuma casa de research monitorada cobre este ticker."))
        return

    dispersao = research.get("dispersao_precos_alvo") or {}
    if dispersao:
        if dispersao.get("amostra_insuficiente"):
            st.caption(str(dispersao.get("resumo") or "Amostra insuficiente para medir dispersão de preço-alvo."))
        else:
            moeda = str(dispersao.get("moeda") or "BRL")
            linhas_dispersao = [
                f"Preço-alvo mínimo: {_moeda_html(dispersao.get('minimo'), moeda)}",
                f"Preço-alvo mediano: {_moeda_html(dispersao.get('mediana'), moeda)}",
                f"Preço-alvo máximo: {_moeda_html(dispersao.get('maximo'), moeda)}",
            ]
            lista_compacta(linhas_dispersao)
            st.caption(str(dispersao.get("resumo") or ""))

    divergencia = research.get("divergencia_recomendacao") or {}
    if divergencia:
        partes_divergencia = []
        if divergencia.get("numerica"):
            partes_divergencia.append(
                f"Preços-alvo divergem numericamente entre {divergencia.get('n_casas_com_preco_alvo')} casa(s)."
            )
        if divergencia.get("qualitativa"):
            partes_divergencia.append("Categorias de recomendação divergem entre as casas monitoradas.")
        if divergencia.get("casa_mais_otimista") and divergencia.get("casa_mais_cautelosa"):
            partes_divergencia.append(
                f"Mais otimista: {divergencia['casa_mais_otimista']} · Mais cautelosa: {divergencia['casa_mais_cautelosa']}"
                f" (critério: {divergencia.get('criterio_otimismo') or 'não informado'})."
            )
        if partes_divergencia:
            lista_compacta([html.escape(p) for p in partes_divergencia])
        elif not divergencia.get("amostra_insuficiente_qualitativa"):
            st.caption("Casas monitoradas convergem na recomendação e no preço-alvo.")

    evolucao = research.get("evolucao_historica") or {}
    mudancas_hoje = sorted(
        casa for casa, info in evolucao.items() if info.get("mudou_recomendacao_ou_alvo_hoje")
    )
    if mudancas_hoje:
        st.caption("Mudou recomendação ou preço-alvo hoje: " + ", ".join(mudancas_hoje) + ".")


def _render_perfil_noticias(perfil: dict):
    """Bloco (e) do Perfil da Empresa: até 5 notícias recentes
    (metadado - título/data/selo/link, nunca resumo editorial, ver
    docstring de data/empresa_perfil.py) - nenhuma notícia disponível é
    um resultado real (fonte indisponível ou sem publicação recente),
    mostrado de forma honesta, nunca omitido."""
    subtitulo("Notícias recentes")
    noticias = (perfil.get("noticias_recentes") or []) if perfil.get("noticias_disponivel") else []
    if not noticias:
        st.caption("Não há notícia recente disponível para este ticker no momento.")
        return
    linhas = []
    for noticia in noticias[:5]:
        titulo = html.escape(str(noticia.get("titulo") or ""))
        data_noticia = html.escape(_fmt_data(noticia.get("data")))
        selo = noticia.get("selo")
        link = noticia.get("link")
        titulo_html = (
            f"<a href='{html.escape(str(link), quote=True)}' target='_blank' rel='noopener'>{titulo}</a>"
            if link else titulo
        )
        selo_txt = f" · {html.escape(str(selo))}" if selo else ""
        linhas.append(f"{titulo_html} ({data_noticia}){selo_txt}")
    lista_compacta(linhas)


def render_perfil_empresa_tab(ticker: str):
    """ANÁLISES > Perfil da Empresa - história do negócio + momento atual
    (pedido literal do Rodrigo: 'eu queria que tivesse a opinião do
    analistas, quando eu fosse ver o preço atual da empresa, gostaria de
    um resumo da história e do momento que ela está passando' - missão
    perfil-empresa-ui-20261118). Consome data/empresa_perfil.py:
    obter_perfil_empresa, camada de consolidação já pronta e testada
    (tests/test_empresa_perfil.py).

    Extraído do st.expander dentro de COMITÊ > Histórico (via
    render_consolidado) em 2026-11-23 - pedido explícito do Rodrigo pra
    virar aba própria/independente (ANÁLISES > Perfil da Empresa, ver
    ui/navegacao.py e app.py rota ("analises", "perfil")), revertendo a
    decisão original de 2026-11-18 ('nunca em aba separada'). Função
    renomeada de _render_perfil_empresa (privada) pra
    render_perfil_empresa_tab (pública) nesta mesma mudança; chamada por
    app.py com o ticker já resolvido pelo seletor da watchlist (mesmo
    padrão de ANÁLISES > Empresas).

    obter_perfil_empresa é função pura (nunca deveria lançar: cada
    fonte que falhar vira disponivel=False só no campo afetado), mas a
    chamada em si bate em yfinance/Supabase via comparar_ticker/
    obter_indicadores - o try/except aqui segue o mesmo padrão de
    resiliência de render_analisar (linha ~1388): nunca deixa uma falha
    de rede quebrar a página; mostra uma mensagem honesta em vez de
    `st.error` bloqueante. A carga em si foi extraída pra
    `obter_perfil_para_tela` (API pública, mais abaixo) em 2026-11-26, pra
    ANÁLISES > Visão 360 consumir o MESMO perfil com o mesmo tratamento de
    falha, sem repetir o try/except."""
    _injetar_css()
    with st.container(border=True):
        st.markdown(
            '<div class="painel-titulo">PERFIL DA EMPRESA — RESUMO DO NEGÓCIO E MOMENTO ATUAL</div>',
            unsafe_allow_html=True,
        )
        if not ticker:
            st.info("Selecione um ticker para ver o perfil da empresa.")
            return
        perfil, motivo_perfil = obter_perfil_para_tela(ticker)
        if perfil is None:
            st.caption(motivo_perfil)
            return

        _render_perfil_identificacao(perfil.get("identificacao") or {}, perfil.get("perguntas") or {})
        divisor()
        _render_perfil_momento_atual(perfil.get("perguntas") or {})
        divisor()
        _render_perfil_posicionamento(perfil.get("perguntas") or {})
        divisor()
        _render_perfil_research_consenso(perfil.get("research") or {})
        divisor()
        _render_perfil_noticias(perfil)


def _render_parecer_model_builder(analista: dict, recomendacao: str):
    """Bloco do Model Builder (DCF em 3 cenários + premissas +
    sensibilidade) - conteúdo idêntico ao que existia antes da
    reorganização visual, só movido pra dentro da aba do próprio
    analista em vez de um expander sequencial."""
    modelo_disponivel = recomendacao == "MODELADO"
    cenarios_modelo = analista.get("cenarios") or {}
    premissas_modelo = analista.get("premissas") or {}
    sensibilidade_modelo = analista.get("sensibilidade") or {}
    if not modelo_disponivel:
        st.warning(str(analista.get("tese") or "Modelo indisponível; premissas explícitas são necessárias."))
        faltantes = analista.get("campos_faltantes") or []
        if faltantes:
            st.caption("Campos ausentes: " + ", ".join(str(x) for x in faltantes))
        return

    moeda_modelo = str(analista.get("moeda") or "moeda do ativo")
    base_modelo = cenarios_modelo.get("base") or {}
    alvo_base_modelo = base_modelo.get("preco_alvo")
    if isinstance(alvo_base_modelo, (int, float)):
        upside_base = base_modelo.get("upside_pct")
        st.markdown(
            "<div class='coord-valuation-destaque'><div class='coord-valuation-legenda'>PREÇO-ALVO · CENÁRIO-BASE</div>"
            f"<div class='coord-valuation-preco'>{_moeda_html(alvo_base_modelo, moeda_modelo)}</div>"
            f"<div class='coord-valuation-legenda'>Potencial: {variacao_html(upside_base) if isinstance(upside_base, (int, float)) else '—'} · {html.escape(moeda_modelo)}</div></div>",
            unsafe_allow_html=True,
        )

    subtitulo("Dados e premissas adotadas")
    st.caption(
        f"Fonte: {analista.get('fontes') or ['Não informada']} · "
        f"Data-base: {analista.get('data_base') or 'Não informada'} · "
        "Método: DCF de 5 anos + Gordon Growth. Valores na moeda/unidade dos dados de origem."
    )
    origem_divida = premissas_modelo.get("origem_divida_liquida")
    itens_premissas = [
        ("FCF inicial (TTM)", _moeda_html(premissas_modelo.get("fcf_base"), moeda_modelo)),
        ("Dívida líquida" + (f" — {origem_divida}" if origem_divida else ""), _moeda_html(premissas_modelo.get("divida_liquida"), moeda_modelo)),
        ("Ações", numero_financeiro_html(premissas_modelo.get("acoes"), casas=0) if isinstance(premissas_modelo.get("acoes"), (int, float)) else "—"),
        ("Crescimento FCF pessimista", _pct_html(premissas_modelo.get("crescimento_fcf_pessimista"))),
        ("Crescimento FCF base", _pct_html(premissas_modelo.get("crescimento_fcf_base"))),
        ("Crescimento FCF otimista", _pct_html(premissas_modelo.get("crescimento_fcf_otimista"))),
        ("WACC", _pct_html(premissas_modelo.get("wacc"))),
        ("Crescimento perpétuo", _pct_html(premissas_modelo.get("g_terminal"))),
    ]
    linhas_premissas = [f"<tr><td>{html.escape(rotulo)}</td><td>{exibicao}</td></tr>" for rotulo, exibicao in itens_premissas]
    st.markdown("<div class='coord-tabela-wrap'><table class='coord-tabela coord-tabela-premissas'><tbody>" + "".join(linhas_premissas) + "</tbody></table></div>", unsafe_allow_html=True)

    subtitulo("Modelo DCF — três cenários")
    linhas_modelo = ["<table class='coord-tabela coord-tabela-dcf'><thead><tr><th>Cenário</th><th>Preço-alvo</th><th>Upside</th><th>Cresc. FCF</th><th>WACC</th><th>g terminal</th><th>Valor da firma</th><th>Valor do patrimônio</th></tr></thead><tbody>"]
    for chave in ("pessimista", "base", "otimista"):
        cenario = cenarios_modelo.get(chave) or {}
        alvo = cenario.get("preco_alvo")
        upside = cenario.get("upside_pct")
        firma = cenario.get("valor_empresa")
        patrimonio = cenario.get("valor_patrimonio")
        linhas_modelo.append(
            f"<tr><td>{html.escape(chave.upper())}</td><td>{_moeda_html(alvo, moeda_modelo)}</td>"
            f"<td>{variacao_html(upside) if isinstance(upside, (int, float)) else '—'}</td>"
            f"<td>{_pct_html(cenario.get('crescimento_fcf'))}</td><td>{_pct_html(cenario.get('wacc'))}</td><td>{_pct_html(cenario.get('g_terminal'))}</td>"
            f"<td>{_moeda_html(firma, moeda_modelo, casas=0)}</td><td>{_moeda_html(patrimonio, moeda_modelo, casas=0)}</td></tr>"
        )
    linhas_modelo.append("</tbody></table>")
    st.markdown("<div class='coord-tabela-wrap'>" + "".join(linhas_modelo) + "</div>", unsafe_allow_html=True)

    if sensibilidade_modelo.get("disponivel"):
        subtitulo("Sensibilidade do preço-alvo-base")
        st.caption("Preço-alvo variando WACC (linhas) e crescimento do FCF (colunas); demais premissas constantes.")
        crescimento_base_modelo = premissas_modelo.get("crescimento_fcf_base") or 0
        linhas_sens = ["<table class='coord-tabela coord-tabela-sens'><thead><tr><th>WACC ↓ / Cresc. FCF →</th>"]
        for passo in sensibilidade_modelo.get("passos_crescimento") or []:
            linhas_sens.append(f"<th>{_pct_html(passo + crescimento_base_modelo)}</th>")
        linhas_sens.append("</tr></thead><tbody>")
        for linha in sensibilidade_modelo.get("linhas") or []:
            linhas_sens.append(f"<tr><td>{_pct_html(linha.get('wacc'))}</td>")
            for celula in linha.get("celulas") or []:
                linhas_sens.append(f"<td>{_moeda_html(celula.get('preco_alvo'), moeda_modelo)}</td>")
            linhas_sens.append("</tr>")
        linhas_sens.append("</tbody></table>")
        st.markdown("<div class='coord-tabela-wrap'>" + "".join(linhas_sens) + "</div>", unsafe_allow_html=True)
        st.caption(str(sensibilidade_modelo.get("observacao") or "Sensibilidade varia WACC e crescimento FCF-base."))
    else:
        st.caption("Sensibilidade indisponível: " + str(sensibilidade_modelo.get("motivo") or "não calculada."))


def _render_parecer_valuation_reviewer(analista: dict):
    """Bloco do Valuation Reviewer (revisão do DCF do Model Builder:
    preço-alvo principal, cenários, premissas e sensibilidade) - mesmo
    conteúdo de antes, só reorganizado visualmente. Corrige o bug real
    (NameError) do bloco legado: calcular_sensibilidade_dcf precisa
    estar importado no topo do módulo (ver import no cabeçalho deste
    arquivo) - antes da correção (2026-11-06), esta chamada estourava
    sempre que o DCF estava disponível, e nenhum teste existente
    exercitava esse caminho."""
    dcf = analista.get("dcf") or {}
    alvo = analista.get("preco_alvo")
    moeda_alvo = dcf.get("moeda") or analista.get("moeda") or "R$"
    upside = analista.get("upside_pct")

    if not dcf.get("disponivel"):
        # O alvo por múltiplos não deve ser confundido com DCF.
        alvo_txt = _moeda_html(alvo, moeda_alvo, fallback="Não calculado")
        rotulo_alvo = "Referência por P/L setorial (não é DCF)" if isinstance(alvo, (int, float)) else "Preço-alvo por DCF indisponível"
        st.markdown(
            f"**{rotulo_alvo}:** {alvo_txt} · potencial "
            f"{variacao_html(upside) if isinstance(upside, (int, float)) else '—'}",
            unsafe_allow_html=True,
        )
        subtitulo("Por que o DCF não foi calculado")
        campos = dcf.get("campos_faltantes") or []
        nomes_campos = {
            "fcf_base": "FCF inicial (TTM)", "wacc": "WACC", "g_terminal": "crescimento perpétuo",
            "divida_liquida": "dívida líquida", "acoes": "quantidade de ações",
            "crescimento_fcf_otimista": "crescimento do FCF — otimista",
            "crescimento_fcf_base": "crescimento do FCF — base",
            "crescimento_fcf_pessimista": "crescimento do FCF — pessimista",
        }
        if campos:
            st.warning("Premissas/dados ausentes: " + ", ".join(nomes_campos.get(c, c) for c in campos) + ".")
        else:
            st.info(dcf.get("motivo") or "As premissas explícitas ainda não foram fornecidas.")
        st.caption(
            "Para obter os três preços-alvo, faça uma nova análise em "
            "Analisar → Premissas do DCF, informe as cinco taxas e acione os especialistas. "
            "Os dados financeiros-base são coletados automaticamente; se não houver FCF, "
            "dívida ou ações compatíveis, o DCF continuará bloqueado."
        )
        return

    st.markdown(
        "<div class='coord-valuation-destaque'>"
        "<div class='coord-valuation-legenda'>PREÇO-ALVO PRINCIPAL · DCF · CENÁRIO-BASE</div>"
        f"<div class='coord-valuation-preco'>{_moeda_html(alvo, moeda_alvo)}</div>"
        f"<div class='coord-valuation-legenda'>Potencial sobre a cotação: {variacao_html(upside) if isinstance(upside, (int, float)) else '—'}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    subtitulo("Dados e premissas adotadas")
    premissas = dcf.get("premissas") or {}
    st.caption(
        f"Fonte: {dcf.get('fonte_premissas') or 'não identificada'} · "
        f"Data-base: {dcf.get('data_base') or 'não informada'} · "
        f"Moeda: {dcf.get('moeda') or 'não identificada'}. "
        "FCF, dívida e valor de mercado permanecem na unidade monetária original da fonte."
    )
    linhas_premissas = [
        ("FCF inicial (TTM)", _moeda_html(premissas.get("fcf_base"), moeda_alvo)),
        ("Dívida líquida" + (f" — {premissas.get('origem_divida_liquida')}" if premissas.get("origem_divida_liquida") else ""), _moeda_html(premissas.get("divida_liquida"), moeda_alvo)),
        ("Ações (estimadas por valor de mercado ÷ cotação)", numero_financeiro_html(premissas.get("acoes"), casas=0) if isinstance(premissas.get("acoes"), (int, float)) else "—"),
        ("Crescimento FCF otimista", _pct_html(premissas.get("crescimento_fcf_otimista"))),
        ("Crescimento FCF base", _pct_html(premissas.get("crescimento_fcf_base"))),
        ("Crescimento FCF pessimista", _pct_html(premissas.get("crescimento_fcf_pessimista"))),
        ("WACC", _pct_html(premissas.get("wacc"))),
        ("Crescimento perpétuo", _pct_html(premissas.get("g_terminal"))),
    ]
    tabela_premissas = ["<table class='coord-tabela coord-tabela-premissas'><thead><tr><th>Premissa</th><th>Valor utilizado</th></tr></thead><tbody>"]
    for rotulo, exibicao in linhas_premissas:
        tabela_premissas.append(f"<tr><td>{html.escape(rotulo)}</td><td>{exibicao}</td></tr>")
    tabela_premissas.append("</tbody></table>")
    st.markdown("<div class='coord-tabela-wrap'>" + "".join(tabela_premissas) + "</div>", unsafe_allow_html=True)

    subtitulo("DCF — preços-alvo por cenário")
    cenarios = dcf.get("cenarios") or {}
    linhas_dcf = ["<table class='coord-tabela coord-tabela-dcf'><thead><tr><th>Cenário</th><th>Preço-alvo</th><th>Potencial</th><th>Crescimento FCF</th><th>WACC</th><th>g terminal</th></tr></thead><tbody>"]
    for chave in ("otimista", "base", "pessimista"):
        c = cenarios.get(chave) or {}
        valor = c.get("preco_alvo")
        potencial = c.get("upside_pct")
        linhas_dcf.append(
            f"<tr><td>{html.escape(str(c.get('rotulo') or chave.upper()))}</td>"
            f"<td>{_moeda_html(valor, moeda_alvo)}</td><td>{variacao_html(potencial) if isinstance(potencial, (int, float)) else '—'}</td>"
            f"<td>{_pct_html(c.get('crescimento_fcf', 0))}</td><td>{_pct_html(c.get('wacc', 0))}</td>"
            f"<td>{_pct_html(c.get('g_terminal', 0))}</td></tr>"
        )
    linhas_dcf.append("</tbody></table>")
    st.markdown("<div class='coord-tabela-wrap'>" + "".join(linhas_dcf) + "</div>", unsafe_allow_html=True)

    sensibilidade = calcular_sensibilidade_dcf(dcf.get("premissas"), preco_atual=analista.get("preco_atual"))
    if sensibilidade.get("disponivel"):
        subtitulo("Sensibilidade do cenário-base")
        st.caption("Preço-alvo por ação variando WACC (linhas) e crescimento do FCF (colunas), em pontos percentuais. As demais premissas permanecem constantes.")
        crescimento_base = premissas.get("crescimento_fcf_base", 0)
        cabecalho = "".join(f"<th>{_pct_html(float(crescimento_base) + delta)}</th>" for delta in (sensibilidade.get("passos_crescimento") or []))
        tabela_sens = [f"<table class='coord-tabela coord-tabela-sens'><thead><tr><th>WACC \\ Crescimento</th>{cabecalho}</tr></thead><tbody>"]
        for linha_sens in sensibilidade.get("linhas") or []:
            celulas = [f"<td>{_moeda_html(celula.get('preco_alvo'), moeda_alvo)}</td>" for celula in (linha_sens.get("celulas") or [])]
            tabela_sens.append(f"<tr><th>{_pct_html(linha_sens.get('wacc', 0))}</th>{''.join(celulas)}</tr>")
        tabela_sens.append("</tbody></table>")
        st.markdown("<div class='coord-tabela-wrap'>" + "".join(tabela_sens) + "</div>", unsafe_allow_html=True)
    else:
        st.caption("Sensibilidade indisponível: " + str(sensibilidade.get("motivo") or "não calculada."))


_ROTULOS_INDICADORES = (
    ("roe_pct", "ROE"),
    ("margem_liquida_pct", "Margem líquida"),
    ("divida_liquida_ebitda_x", "Dívida líquida/EBITDA"),
    ("fluxo_caixa_livre", "Fluxo de caixa livre (FCF)"),
    ("pl_x", "P/L"),
    ("pl_mediana_setor_x", "P/L — mediana do setor"),
    ("roic_trimestral_pct", "ROIC trimestral (não anualizado)"),
    ("receita_liquida_yoy_pct", "Receita líquida — variação YoY"),
)


def _render_indicadores_financeiros(indicadores: dict):
    """Tabela de indicadores financeiros reais (pareceres.py:_parecer_market)
    - os MESMOS números já citados em prosa na tese/pros/contras do Market
    Researcher, só expostos também num ponto único e estruturado (campo
    pedido explicitamente: "indicadores financeiros" e "ROIC" - antes só
    existiam como texto corrido, achado real da auditoria 2026-11-11).
    Nunca recalcula nada; indicador ausente aparece como "—", nunca 0."""
    if not indicadores:
        return
    moeda = indicadores.get("moeda") or "R$"
    subtitulo("Indicadores financeiros")
    linhas = []
    for chave, rotulo in _ROTULOS_INDICADORES:
        valor = indicadores.get(chave)
        if valor is None:
            exibicao = "—"
        elif chave.endswith("_pct"):
            # Variação (sinal importa - usa a cor de alta/baixa real);
            # os demais percentuais (ROE/margem/ROIC) são nível, não
            # variação, mas aqui também usam a mesma formatação sem cor
            # (nenhum dos dois é uma comparação explícita de 2 pontos).
            exibicao = variacao_html(valor) if chave == "receita_liquida_yoy_pct" else _pct_html(valor, escala=1.0)
        elif chave.endswith("_x"):
            exibicao = numero_financeiro_html(valor, casas=2, formato="BR", sufixo="x")
        else:
            exibicao = _moeda_html(valor, moeda)
        linhas.append(f"<tr><td>{html.escape(rotulo)}</td><td>{exibicao}</td></tr>")
    st.markdown(
        "<div class='coord-tabela-wrap'><table class='coord-tabela coord-tabela-premissas'><tbody>"
        + "".join(linhas) + "</tbody></table></div>",
        unsafe_allow_html=True,
    )


def _render_achados_revisao(analista: dict):
    """Bloco próprio do Valuation Reviewer: achados estruturados da
    revisão independente (lista de {tipo, descricao}) + limitações
    declaradas - NUNCA os genéricos "Pontos favoráveis"/"Pontos
    contrários" usados pelos demais especialistas (reformulação de
    apresentação por especialista, achado real de auditoria anterior).

    Esses 2 campos (achados/limitacoes) são os que pareceres.py de fato
    devolve pra este especialista (ver montar_pareceres) - "contras" do
    parecer já é só achados reformatado em texto corrido
    (f"{tipo}: {descricao}"), e "pros" é só a frase fixa de "nenhuma
    inconsistência" quando não há achado; mostrar os dois ao lado de um
    bloco de achados estruturado duplicaria a mesma informação 2x sob
    rótulos diferentes. Achados vazios + revisão disponível é um
    resultado REAL (revisão concluída, nada encontrado) - nunca tratado
    como ausência de dado."""
    dcf = analista.get("dcf") or {}
    achados = [a for a in (analista.get("achados") or []) if isinstance(a, dict)]
    subtitulo("Achados da revisão independente")
    if achados:
        lista_compacta(
            f"<b>{html.escape(str(a.get('tipo') or 'ACHADO'))}</b>: {html.escape(str(a.get('descricao') or ''))}"
            for a in achados
        )
    elif dcf.get("disponivel"):
        st.caption("Revisão concluída: nenhuma inconsistência encontrada nos cenários do Model Builder.")
    else:
        st.caption("Revisão ainda não disponível para esta análise.")


def _render_parecer_analista(analista: dict):
    """Conteúdo de 1 aba da seção "Pareceres por especialista": método/
    dados usados, premissas (quando houver), tese e pontos favoráveis/
    contrários - mesmo conteúdo que antes ficava num st.expander
    sequencial por analista; aqui vira o corpo de 1 aba (st.tabs), pra
    deixar claro que cada analista é uma visão independente, lida em
    paralelo (não uma lista vertical só de texto).

    REFORMULAÇÃO POR ESPECIALISTA (cards claros, achado real de auditoria
    anterior): "Pontos favoráveis"/"Pontos contrários" só é exibido pros
    especialistas cujo schema real tem esses campos (market_researcher/
    earnings_reviewer/valuation_comparables - ver
    data/coordenador_central/pareceres.py:montar_pareceres). model_builder
    NUNCA teve pros/contras no próprio dict (chave ausente, não lista
    vazia) - antes esta função ainda assim mostrava "Sem evidência
    favorável/contrária estruturada" pra ele, um placeholder que sugeria
    dado ausente quando na verdade esse campo nunca existiu pra este
    especialista (o que ele de fato produz - cenários/premissas - já
    aparece abaixo, via _render_parecer_model_builder). valuation_reviewer
    tem pros/contras no dict, mas são só achados/motivo reformatados em
    texto corrido; mostra-se em vez disso o campo real e mais rico
    (achados estruturados + limitações), via _render_achados_revisao."""
    analista_id = str(analista.get("id") or "")
    recomendacao = str(analista.get("recomendacao") or "INSUFICIENTE")
    vies = html.escape(str(analista.get("vies") or "SEM BASE"))
    tese = html.escape(str(analista.get("tese") or "Parecer indisponível."))
    especialidade = html.escape(str(analista.get("especialidade") or ""))
    metodo_analista = html.escape(str(analista.get("metodo") or ""))

    # Fontes utilizadas - campo pedido explicitamente; existia nos dados
    # de pareceres.py (market_researcher/earnings_reviewer/model_builder)
    # mas esta função genérica nunca exibia (achado real, auditoria
    # 2026-11-11) - só o bloco especial do Model Builder mostrava "Fonte:"
    # embutido no texto. Aqui vira 1 linha por analista, sempre que houver.
    fontes_analista = [str(f) for f in (analista.get("fontes") or []) if f]
    fontes_html = (
        f"<div class='coord-nota'>Fontes: {html.escape(', '.join(fontes_analista))}</div>"
        if fontes_analista else ""
    )
    st.markdown(
        f"<div style='margin-bottom:0.3rem;'>{_badge_recomendacao(recomendacao)} "
        f"<span class='coord-nota' style='margin:0;'>viés: {vies}</span></div>"
        f"<div class='coord-nota'>Especialidade: {especialidade}</div>"
        f"<div class='coord-nota'>Método/dados utilizados: {metodo_analista}</div>"
        f"{fontes_html}"
        f"<b>Tese</b><div class='coord-conclusao-linha'>{tese}</div>",
        unsafe_allow_html=True,
    )

    # Indicadores financeiros estruturados (ROE, margem líquida, dívida
    # líquida/EBITDA, FCF, P/L vs. mediana setorial, ROIC trimestral) -
    # hoje só o Market Researcher carrega esse bloco (ver
    # pareceres.py:_parecer_market); antes esses números só existiam como
    # texto corrido dentro da tese/pros/contras, sem 1 tabela só com o
    # indicador bruto (campo pedido explicitamente: "indicadores
    # financeiros" e "ROIC").
    if analista.get("indicadores"):
        _render_indicadores_financeiros(analista["indicadores"])

    if analista_id == "model_builder":
        # Sem bloco de pros/contras aqui - o schema real deste
        # especialista não tem esses campos (ver docstring da função).
        pass
    elif analista_id == "valuation_reviewer":
        _render_achados_revisao(analista)
    else:
        pros = analista.get("pros") or []
        contras = analista.get("contras") or []
        col_pro, col_con = st.columns(2)
        with col_pro:
            subtitulo("Pontos favoráveis")
            lista_compacta(html.escape(str(x)) for x in pros) if pros else st.caption("Sem evidência favorável estruturada.")
        with col_con:
            subtitulo("Pontos contrários")
            lista_compacta(html.escape(str(x)) for x in contras) if contras else st.caption("Sem evidência contrária estruturada.")

    # Limitações declaradas pelo próprio especialista (ex.: Earnings
    # Reviewer/Valuation Reviewer) - achado real (auditoria 2026-11-11):
    # existiam em pareceres.py mas nunca eram mostradas em nenhuma tela.
    limitacoes_analista = [str(x) for x in (analista.get("limitacoes") or []) if x]
    if limitacoes_analista:
        st.caption("Limitações declaradas: " + " · ".join(limitacoes_analista))

    # Modelo consultável: o DCF pertence ao Model Builder. Exibir aqui
    # evita depender de um campo legado do Reviewer.
    if analista_id == "model_builder":
        divisor()
        _render_parecer_model_builder(analista, recomendacao)

    # Preço-alvo é responsabilidade do Model Builder ou de uma casa de
    # research; os analistas de fundamentos e resultados não devem
    # exibir um campo vazio que pareça uma falha.
    if analista_id == "valuation_reviewer":
        divisor()
        _render_parecer_valuation_reviewer(analista)


def _render_casas_research(casas: list, consenso: dict):
    """Dados externos (não são 1 agente do Comitê): o que cada casa de
    research publicou pro mesmo ticker - preço-alvo é sempre atribuído à
    casa, nunca ao Pregão."""
    subtitulo("Dados externos — o que dizem as casas de research")
    linhas = ["<table class='coord-tabela'><thead><tr><th>Casa</th><th>Recomendação</th><th>Preço-alvo</th><th>Potencial</th><th>Publicação</th></tr></thead><tbody>"]
    for casa in casas:
        alvo = casa.get("preco_alvo")
        upside = casa.get("upside_pct")
        titulo = html.escape(str(casa.get("titulo") or ""))
        link = casa.get("link")
        casa_nome = html.escape(str(casa.get("casa") or "—"))
        casa_html = f"<a href='{html.escape(str(link), quote=True)}' target='_blank' rel='noopener'>{casa_nome}</a>" if link else casa_nome
        linhas.append(
            f"<tr><td>{casa_html}<div class='coord-nota'>{titulo}</div></td>"
            f"<td>{_badge_recomendacao(casa.get('recomendacao'))}</td>"
            f"<td>{_moeda_html(alvo, 'R$')}</td>"
            f"<td>{variacao_html(upside) if isinstance(upside, (int, float)) else '—'}</td>"
            f"<td>{html.escape(_fmt_data(casa.get('data_publicacao')))}</td></tr>"
        )
    linhas.append("</tbody></table>")
    st.markdown("<div class='coord-tabela-wrap'>" + "".join(linhas) + "</div>", unsafe_allow_html=True)
    for casa in casas:
        with st.expander(f"Tese e riscos — {casa.get('casa') or 'Casa'}"):
            premissas = casa.get("tese") or []
            riscos_casa = casa.get("contras") or []
            projecoes = casa.get("projecoes") or {}
            subtitulo("Tese / premissas publicadas")
            lista_compacta(html.escape(str(x)) for x in premissas) if premissas else st.caption("A extração estruturada não encontrou premissas para esta publicação.")
            subtitulo("Riscos apontados pela casa")
            lista_compacta(html.escape(str(x)) for x in riscos_casa) if riscos_casa else st.caption("A extração estruturada não encontrou riscos para esta publicação.")
            if projecoes:
                subtitulo("Projeções extraídas")
                lista_compacta(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in projecoes.items() if v is not None)
    mediana = consenso.get("mediana")
    upside_consenso = consenso.get("upside_pct")
    if isinstance(mediana, (int, float)):
        upside_txt = f" · potencial {variacao_html(upside_consenso)}" if isinstance(upside_consenso, (int, float)) else ""
        st.markdown(
            f"<div class='coord-nota'>Mediana dos preços-alvo publicados: <b>{_moeda_html(mediana, 'R$')}</b>{upside_txt} · "
            f"{html.escape(str(consenso.get('n_casas') or 0))} casa(s). Não é preço-alvo proprietário do Pregão.</div>",
            unsafe_allow_html=True,
        )


def _render_divergencia_comite(divergencia_comite: dict | None):
    """Painel dedicado à divergência ENTRE os próprios especialistas do
    Comitê (market_researcher/earnings_reviewer/valuation_comparables
    comparados entre si na escala COMPRA/VENDA/NEUTRO - ver
    data/coordenador_central/consolidacao.py:
    _divergencia_entre_analistas_comite). Mostra só os 3 campos que
    consolidar() já calcula: quantos especialistas comparáveis entraram
    na checagem (n_analistas_comparados), se divergem (divergente) e o
    resumo textual pronto (resumo, com a atribuição por especialista
    embutida) - nenhum texto novo é composto aqui, nenhum "motivo"
    inventado além do que a própria função devolve. Nunca decide quem
    está certo (o Coordenador não tem esse mecanismo): só torna visível
    o que já era calculado e nunca tinha tela."""
    if not divergencia_comite:
        return
    divergente = bool(divergencia_comite.get("divergente"))
    badge = (
        "<span class='coord-badge coord-badge-andamento'>DIVERGENTE</span>"
        if divergente
        else "<span class='coord-badge coord-badge-ok'>CONVERGENTE</span>"
    )
    n_comparados = divergencia_comite.get("n_analistas_comparados")
    with st.expander("Divergência entre especialistas do Comitê", expanded=divergente):
        st.markdown(
            f"<div style='margin-bottom:0.3rem; display:flex; align-items:center; gap:0.5rem;'>{badge}"
            f"<span class='coord-nota' style='margin:0;'>"
            f"{html.escape(str(n_comparados if n_comparados is not None else '—'))} especialista(s) "
            "com recomendação comparável (COMPRA/VENDA/NEUTRO) comparados entre si.</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='coord-conclusao-linha'>{html.escape(str(divergencia_comite.get('resumo') or ''))}</div>",
            unsafe_allow_html=True,
        )


def _render_sintese_final(consolidado: dict):
    """Fecho da análise consolidada: conclusão determinística (rotulada
    FATO/CÁLCULO INTERNO/DADO INSUFICIENTE), divergências e pontos que
    precisam de revisão humana, e - como material de apoio, no fim -
    evidências e a visão bruta por especialista. Nada aqui é novo
    cálculo: só reagrupa visualmente o que data/coordenador_central/
    consolidacao.py já devolve (conclusao/pontos_atencao/divergencias/
    evidencias/visao_especialistas), colocado por último de propósito
    (a recomendação e o resumo já apareceram no cabeçalho)."""
    conclusao = consolidado.get("conclusao") or []
    if conclusao:
        subtitulo("Conclusão consolidada do Comitê")
        for linha in conclusao:
            st.markdown(f"<div class='coord-conclusao-linha'>{html.escape(linha)}</div>", unsafe_allow_html=True)

    pontos_atencao = consolidado.get("pontos_atencao") or []
    divergencias = (consolidado.get("divergencias") or {}).get("cross_comparador_memoria")
    tem_divergencias = bool(divergencias and divergencias.get("divergencias"))
    if pontos_atencao or tem_divergencias:
        subtitulo("Divergências e pontos que precisam de revisão")
        if pontos_atencao:
            with st.expander(f"Pontos de atenção ({len(pontos_atencao)})"):
                lista_compacta(html.escape(str(p)) for p in pontos_atencao)
        if tem_divergencias:
            # Rótulo explícito (antes só "Divergências identificadas") pra
            # nunca se confundir com o painel de divergência ENTRE
            # especialistas do Comitê abaixo - são dois conceitos
            # diferentes (ver _render_divergencia_comite).
            with st.expander(f"Divergência: comparador × memória de research ({len(divergencias['divergencias'])})"):
                lista_compacta(
                    f"<b>{html.escape(d['casa'])}</b> ({html.escape(str(d['tipo']))}, {html.escape(str(d['campo']))}): "
                    f"comparador=<code>{html.escape(str(d['comparador'] if d['comparador'] is not None else '—'))}</code> "
                    f"vs memória de research=<code>{html.escape(str(d['memoria_research'] if d['memoria_research'] is not None else '—'))}</code>"
                    for d in divergencias["divergencias"]
                )

    # Divergência ENTRE os especialistas do Comitê entre si (market_researcher/
    # earnings_reviewer/valuation_comparables comparados na escala COMPRA/VENDA/
    # NEUTRO - ver data/coordenador_central/consolidacao.py:
    # _divergencia_entre_analistas_comite). CONCEITO DIFERENTE do bloco acima
    # (cross_comparador_memoria compara fonte externa vs. memória de research
    # interna - mesmo tipo de dado, duas fontes) - por isso é uma seção própria,
    # com rótulo explícito, nunca misturada no mesmo expander. Antes desta
    # mudança esse cálculo já existia em consolidar() mas nunca era exibido em
    # nenhuma tela (achado de auditoria). Exibe só o que consolidar() já
    # calculou - nunca um "veredito" de quem está certo; o Coordenador não tem
    # esse mecanismo, só registra convergência/divergência.
    divergencia_comite = (consolidado.get("divergencias") or {}).get("entre_analistas_comite")
    if divergencia_comite:
        subtitulo("Divergência entre especialistas do Comitê")
        _render_divergencia_comite(divergencia_comite)

    evidencias = consolidado.get("evidencias") or []
    visao_especialistas = consolidado.get("visao_especialistas") or {}
    if evidencias or visao_especialistas:
        subtitulo("Material de apoio")
        if evidencias:
            with st.expander(f"Evidências ({len(evidencias)})"):
                for e in evidencias:
                    st.markdown(
                        f"<div class='coord-evidencia'><span class='coord-conclusao-tag'>{html.escape(e.get('especialista') or '')}</span>"
                        f"{html.escape(e.get('fonte') or '—')} · {_fmt_data(e.get('data'))} — "
                        f"{html.escape(e.get('titulo') or '')}</div>",
                        unsafe_allow_html=True,
                    )
        if visao_especialistas:
            def _linha_especialista(especialista_id, r):
                if r.get("disponivel"):
                    disp = "disponível"
                else:
                    motivo = html.escape(str(r.get("motivo_indisponivel")))
                    disp = f"indisponível ({motivo})"
                return f"<code>{html.escape(especialista_id)}</code> — {disp}: {html.escape(r.get('resumo') or '—')}"

            with st.expander(f"Visão bruta por especialista acionado ({len(visao_especialistas)})"):
                lista_compacta(
                    _linha_especialista(especialista_id, r)
                    for especialista_id, r in visao_especialistas.items()
                )


def _render_sintese_ia(consolidado: dict):
    """Leitura qualitativa de IA real (Groq) sobre o consolidado -
    missão "PREGÃO 2.3-B — fiação real da síntese de IA no Comitê"
    (2026-11-13). Só aparece quando a análise foi executada com
    sintese_ia=True (hoje, atrás de config.sintese_ia_comite_ativa(),
    DESLIGADA por padrão em produção - ver config.py e o checkbox em
    render_analisar) - as 2 chaves lidas aqui
    ('sintese_divergencia_comite_ia'/'sintese_qualitativa_research_ia')
    são ADITIVAS (data/coordenador_central/fluxos.py:_anexar_sintese_ia),
    nunca substituem nem recalculam a recomendação/preço-alvo/confiança
    já mostrados em _render_cabecalho_decisao/_render_sintese_final (a
    fonte de verdade numérica continua 100% determinística).

    Cada bloco expõe explicitamente o MODELO usado (nunca caixa-preta) e,
    quando indisponível (sem GROQ_API_KEY, rate limit, erro de rede,
    resposta em formato inesperado), mostra o motivo real em vez de
    esconder a seção - mesmo padrão de transparência das demais fontes
    deste painel. Toda chamada de IA desta camada é registrada em
    ia_hibrida_execucoes (ver data/ia_hibrida_telemetria.py) - modelo,
    provedor, horário, sucesso/motivo de falha, fontes citadas."""
    sintese_comite = consolidado.get("sintese_divergencia_comite_ia")
    sintese_research = consolidado.get("sintese_qualitativa_research_ia")
    if not sintese_comite and not sintese_research:
        return

    subtitulo("Leitura de IA (Groq) — interpretativa, não recalcula números")
    st.markdown(
        "<div class='coord-nota'>Esta seção é gerada por IA para EXPLICAR em prosa o que os pareceres "
        "e números determinísticos acima já mostram - nunca decide recomendação, preço-alvo ou confiança "
        "(esses continuam exclusivamente do cálculo determinístico, sempre auditável acima). Cada chamada "
        "fica registrada (modelo, horário, sucesso/motivo de falha) para auditoria.</div>",
        unsafe_allow_html=True,
    )

    if sintese_comite:
        if sintese_comite.get("disponivel"):
            modelo = html.escape(str(sintese_comite.get("modelo") or "—"))
            st.markdown(
                f"<div class='coord-conclusao-linha'><span class='coord-conclusao-tag'>IA · {modelo}</span>"
                f"<b>Leitura sobre a convergência/divergência do Comitê:</b> "
                f"{html.escape(str(sintese_comite.get('leitura') or ''))}</div>",
                unsafe_allow_html=True,
            )
            if sintese_comite.get("fator_decisivo"):
                st.caption(f"Fator decisivo apontado pela IA: {sintese_comite['fator_decisivo']}")
            citados = sintese_comite.get("especialistas_citados") or []
            if citados:
                st.caption("Especialistas citados nesta leitura: " + ", ".join(citados))
        else:
            st.caption(
                f"Leitura de IA sobre o Comitê indisponível nesta análise: "
                f"{sintese_comite.get('motivo') or 'motivo não informado'}."
            )

    if sintese_research:
        if sintese_research.get("disponivel"):
            modelo = html.escape(str(sintese_research.get("modelo") or "—"))
            st.markdown(
                f"<div class='coord-conclusao-linha'><span class='coord-conclusao-tag'>IA · {modelo}</span>"
                f"<b>Leitura do research externo monitorado:</b> "
                f"{html.escape(str(sintese_research.get('sintese') or ''))}</div>",
                unsafe_allow_html=True,
            )
            casas_citadas = sintese_research.get("casas_citadas") or []
            if casas_citadas:
                st.caption("Casas citadas nesta leitura: " + ", ".join(str(c) for c in casas_citadas))
            with st.expander("Convergências, divergências e pontos de atenção apontados pela IA (research externo)"):
                for rotulo, chave in (("Convergências", "convergencias"), ("Divergências", "divergencias"), ("Pontos de atenção", "pontos_atencao")):
                    itens = sintese_research.get(chave) or []
                    if itens:
                        subtitulo(rotulo)
                        lista_compacta(html.escape(str(i)) for i in itens)
        else:
            st.caption(
                f"Leitura de IA sobre o research externo indisponível nesta análise: "
                f"{sintese_research.get('motivo') or 'motivo não informado'}."
            )


def render_consolidado(consolidado: dict):
    """Monta a análise consolidada em 3 blocos, nesta ordem (reformulação
    visual 2026-11-06, pedido do Rodrigo; perfil da empresa que viveu
    aqui entre 2026-11-18 e 2026-11-23 foi extraído pra aba própria -
    ANÁLISES > Perfil da Empresa, ver render_perfil_empresa_tab e
    app.py rota ("analises", "perfil")): (1) cabeçalho de decisão -
    recomendação fundamentada do Comitê bem no topo; (2) pareceres por
    especialista, 1 aba por analista (o que cada um analisou/dados/
    premissas/tese) + dados externos das casas de research; (3) síntese
    final - conclusão, divergências, pontos de revisão e material de
    apoio. A lógica de consolidação real (data/coordenador_central/
    consolidacao.py + pareceres.py) não muda - só a apresentação; nenhum
    valor é recalculado ou simplificado aqui."""
    _render_cabecalho_decisao(consolidado)
    divisor()

    pareceres = consolidado.get("pareceres_analistas") or {}
    analistas = pareceres.get("analistas") or []
    if analistas:
        subtitulo("Pareceres por especialista — o que cada um analisou")
        st.markdown(
            "<div class='coord-nota' style='margin-top:-0.3rem;'>Cada aba é o parecer independente de 1 "
            "especialista do Comitê: dados utilizados, premissas (quando houver), tese e pontos favoráveis/"
            "contrários. A recomendação consolidada já apareceu no topo desta página.</div>",
            unsafe_allow_html=True,
        )
        abas = st.tabs([str(a.get("nome") or a.get("id") or "Analista") for a in analistas])
        for aba, analista in zip(abas, analistas):
            with aba:
                _render_parecer_analista(analista)

    casas = pareceres.get("casas_research") or []
    if casas:
        divisor()
        _render_casas_research(casas, pareceres.get("preco_alvo_consenso") or {})

    divisor()
    _render_sintese_final(consolidado)

    if consolidado.get("sintese_divergencia_comite_ia") or consolidado.get("sintese_qualitativa_research_ia"):
        divisor()
        _render_sintese_ia(consolidado)


# ============================================================
# API PÚBLICA DE COMPOSIÇÃO (consumida por ui/visao_360_tab.py)
#
# A Visão 360 (ANÁLISES > Visão 360, redesign 2026-11-26) precisa dos
# MESMOS blocos que esta aba já renderiza - perfil da empresa pergunta por
# pergunta, parecer de 1 especialista, casas de research, divergência entre
# especialistas, síntese final e síntese de IA - mas numa hierarquia visual
# própria (ex.: "Momento atual" e "Principais riscos" viram 2 blocos
# separados lá, enquanto aqui são 1 só; os pareceres viram lista lateral em
# vez de st.tabs). Em vez de duplicar o conteúdo desses blocos na tela nova
# (ou de importar função privada de outro módulo de UI, o que a convenção
# deste projeto evita - ver docstring de _nome_empresa_exibicao), cada
# bloco ganha UM nome público aqui, delegando pra implementação privada que
# já existia e continua sendo a única.
#
# Por que as privadas não foram simplesmente renomeadas: elas são
# exercitadas POR NOME em tests/test_coordenador_tab_cards_especialistas.py,
# tests/test_coordenador_tab_divergencia_comite.py,
# tests/test_coordenador_tab_perfil_empresa.py e
# tests/test_coordenador_central_consolidacao.py - renomear trocaria um
# risco de duplicação por um churn de teste sem ganho nenhum.
# ============================================================

def injetar_css():
    """Injeta o CSS deste módulo (`.coord-*`: nota, métrica, selo, tabela
    com rolagem, destaque de valuation) - obrigatório antes de chamar
    QUALQUER render_* daqui de fora.

    Bug real encontrado nesta missão (2026-11-26): `render_perfil_empresa_tab`
    e `render_consolidado` emitem markup `.coord-nota`/`.coord-metrica-valor`/
    `.coord-badge`/`.coord-tabela`, mas nenhuma das duas injetava o CSS - só
    as 5 subabas de COMITÊ chamavam `_injetar_css`. Resultado: em ANÁLISES >
    Perfil da Empresa e em ANÁLISES > Visão 360 (que chamam as duas direto)
    esses blocos renderizavam SEM estilo - texto no tamanho padrão do
    Streamlit, selo sem borda/cor, tabela sem o wrapper de rolagem. Era uma
    das causas concretas da tela de análise parecer "relatório bruto"."""
    _injetar_css()


def obter_perfil_para_tela(ticker: str) -> tuple:
    """`(perfil, motivo)` - carrega data/empresa_perfil.py:
    obter_perfil_empresa com o MESMO tratamento de falha de
    `render_perfil_empresa_tab` (que agora usa esta função): a camada de
    dados é pura e cada fonte que falha vira `disponivel=False` só no
    campo afetado, mas a chamada em si bate em yfinance/Supabase - uma
    falha de rede devolve `(None, motivo)` em vez de derrubar a tela.
    Extraída pra que a Visão 360 consuma o MESMO perfil sem repetir o
    try/except nem chamar a fonte duas vezes na mesma página.

    O DETALHE TÉCNICO da falha (repr da exceção) vai pro log do servidor,
    nunca pra tela - antes de 2026-11-26 o repr era concatenado na
    mensagem do usuário, que via coisas como "KeyError('currentPrice')"
    numa aba de análise. Regra explícita da missão de redesign: nome de
    coluna, SQL, migration e exceção interna só existem em log/ferramenta
    de dev; o usuário vê o FATO (a fonte não respondeu)."""
    if not ticker:
        return None, "Selecione um ticker para ver o perfil da empresa."
    try:
        return obter_perfil_empresa(ticker), None
    except Exception as exc:
        print(f"[coordenador_tab] perfil da empresa indisponível pra {ticker}: {exc!r}")
        return None, ("Perfil da empresa indisponível no momento: as fontes de research/fundamentos "
                      "não responderam nesta consulta.")


def render_perfil_pergunta(pergunta: dict | None, rotulo: str):
    """1 pergunta do Perfil da Empresa (evidências de research verbatim ou
    o motivo_indisponivel literal da camada de dados)."""
    _render_pergunta_perfil(pergunta, rotulo)


def render_perfil_pergunta_quebra_tese(pergunta: dict | None):
    """Pergunta "o que quebraria a tese" (evidências + divergência entre
    casas sobre as premissas centrais)."""
    _render_pergunta_quebra_tese_perfil(pergunta)


def render_perfil_identificacao(identificacao: dict, perguntas: dict):
    """Bloco "o que a empresa faz / como ganha dinheiro" + setor/indústria/
    país."""
    _render_perfil_identificacao(identificacao, perguntas)


def render_perfil_posicionamento(perguntas: dict):
    """Bloco "posicionamento competitivo" (posição, vantagens,
    concorrentes)."""
    _render_perfil_posicionamento(perguntas)


def render_perfil_research_consenso(research: dict):
    """Bloco de consenso entre casas de research já calculado por
    data/empresa_perfil.py (dispersão de preço-alvo, divergência,
    mudanças de hoje)."""
    _render_perfil_research_consenso(research)


def render_perfil_noticias(perfil: dict):
    """Bloco de notícias recentes do perfil (metadado: título/data/selo/
    link, nunca resumo editorial)."""
    _render_perfil_noticias(perfil)


def render_parecer_especialista(analista: dict):
    """Parecer completo de 1 especialista do Comitê - método/dados, tese,
    indicadores, pontos favoráveis/contrários, achados, limitações e (pro
    Model Builder/Valuation Reviewer) o DCF com cenários/premissas/
    sensibilidade."""
    _render_parecer_analista(analista)


def render_casas_research(casas: list, consenso: dict):
    """Dado externo: o que cada casa de research publicou pro ticker
    (preço-alvo sempre atribuído à casa, nunca ao Pregão)."""
    _render_casas_research(casas, consenso)


def render_divergencia_comite(divergencia_comite: dict | None):
    """Painel de convergência/divergência ENTRE os especialistas do
    Comitê (nunca um veredito de quem está certo)."""
    _render_divergencia_comite(divergencia_comite)


def render_sintese_final(consolidado: dict):
    """Fecho da análise consolidada: conclusão determinística rotulada,
    pontos de atenção, divergências e material de apoio."""
    _render_sintese_final(consolidado)


def render_sintese_ia(consolidado: dict):
    """Leitura qualitativa de IA (Groq) sobre o consolidado - aditiva,
    nunca recalcula recomendação/preço-alvo/confiança."""
    _render_sintese_ia(consolidado)


def badge_recomendacao_html(recomendacao: str) -> str:
    """Selo da recomendação de 1 especialista/casa, cobrindo os 3
    vocabulários que convivem no Comitê (ver _badge_recomendacao)."""
    return _badge_recomendacao(recomendacao)


def badge_confianca_html(categoria: str) -> str:
    """Selo da confiança da consolidação (ALTA/MEDIA/BAIXA/
    INSUFICIENTE), com cor variando por categoria."""
    return _badge_confianca(categoria)


def cor_recomendacao(recomendacao: str) -> str:
    """Cor do texto grande de recomendação (var(--alta)/var(--baixa)/
    var(--neutro)/var(--cinza) - nunca um hex novo)."""
    return _cor_recomendacao(recomendacao)


def fmt_data(valor) -> str:
    """Data em texto curto (YYYY-MM-DD) ou "—" - mesma normalização usada
    em toda esta aba."""
    return _fmt_data(valor)


def nome_empresa_exibicao(ticker: str | None) -> str | None:
    """Nome de exibição da empresa (config.TICKER_NOME, fallback
    obter_nome_yf cacheado 24h) - mesma cascata de sempre."""
    return _nome_empresa_exibicao(ticker)


def render_historico(prefs: dict = None):
    """Abre 1 análise antiga específica (obter_analise(id)) - mostra
    solicitação original, especialistas participantes, evidências,
    divergências, conclusão, data e duração.

    Filtro por ticker (campo de texto abaixo): persistencia.py ainda não
    tem uma função dedicada de busca por ticker (listar_analises_recentes/
    obter_analise são as únicas hoje) - filtra em Python sobre a lista já
    carregada em vez de duplicar lógica de busca em outro módulo.
    Client-side de propósito (nunca editado em persistencia.py: outra
    frente trabalha nesse arquivo em paralelo - ver CLAUDE.md regra 3).
    Se uma função de busca por ticker passar a existir lá, a troca é
    só nesta função, sem mudar o contrato desta aba."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">HISTÓRICO DE ANÁLISES</div>', unsafe_allow_html=True)

    analises = persistencia.listar_analises_recentes(limite=50)
    if analises is None:
        st.warning("Histórico indisponível no momento (Supabase fora do ar).")
        return
    if not analises:
        st.info("Nenhuma análise executada ainda nesta instalação.")
        return

    filtro_ticker = st.text_input(
        "Filtrar por ticker", key="coord_historico_filtro_ticker",
        placeholder="ex: PETR4 — deixe vazio pra ver todas",
    ).strip().upper()
    analises_filtradas = (
        [a for a in analises if (a.get("ticker") or "").strip().upper() == filtro_ticker]
        if filtro_ticker else analises
    )
    if not analises_filtradas:
        st.info(f"Nenhuma análise encontrada para o ticker '{filtro_ticker}' nas últimas {len(analises)} análise(s).")
        return

    opcoes = {f"{a.get('solicitacao')} — {_fmt_data(a.get('iniciado_em'))} ({(a.get('id') or '')[:8]})": a.get("id") for a in analises_filtradas}
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
    render_consolidado(resultado)


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

    render_dcf_operacional()

    col_ticker, col_fluxo = st.columns([2, 2])
    with col_ticker:
        # Compatibilidade com a Visão 360 (missão visao-360-empresa-20261124):
        # este campo sempre foi 100% independente do ticker global (watchlist/
        # seletor de ANÁLISES) - um usuário que chegasse aqui via o CTA
        # "Executar Comitê para este ticker" (ver ui/visao_360_tab.py,
        # navegacao.ir_para("comite", "visao-geral", ticker) grava
        # "ticker_selecionado") encontrava o campo vazio, tendo que digitar o
        # ticker de novo. Pré-popula SÓ quando este campo ainda não tem valor
        # nenhum nesta sessão (nunca sobrescreve uma escolha que o usuário já
        # tenha feito manualmente aqui, mesmo que ela seja diferente do
        # ticker global).
        if not st.session_state.get("coord_analisar_ticker") and st.session_state.get("ticker_selecionado"):
            st.session_state["coord_analisar_ticker"] = st.session_state["ticker_selecionado"]
        ticker = st.text_input("Ticker", key="coord_analisar_ticker", placeholder="ex: PETR4").strip().upper()
    with col_fluxo:
        fluxo_escolhido = st.selectbox(
            "Tipo de análise", list(_FLUXOS.keys()), key="coord_analisar_fluxo",
            format_func=lambda k: _FLUXOS[k][0],
        )

    premissas_dcf = None
    usar_sintese_ia = False
    if fluxo_escolhido == "analise_ticker":
        # Checkbox de síntese de IA real (Groq) - missão "PREGÃO 2.3-B",
        # 2026-11-13. Só aparece quando config.sintese_ia_comite_ativa()
        # está ligada (hoje, DESLIGADA por padrão em produção - ver
        # config.py); com a config desligada, o analista nem vê a opção,
        # pra deixar claro que a ativação é uma decisão de configuração
        # do Rodrigo, não um toggle qualquer de UI. Mesmo gate que
        # jobs/comite_noturno.py usa pra decidir se passa sintese_ia=True
        # pra fluxos.analisar_ticker - um único interruptor pros 2
        # caminhos de produção.
        if config.sintese_ia_comite_ativa():
            usar_sintese_ia = st.checkbox(
                "Pedir leitura de IA (Groq) sobre este Comitê — chamada real à Groq, custo real",
                key="coord_sintese_ia_ativar",
                help=(
                    "Gera uma leitura em prosa (Groq) do porquê da convergência/divergência entre os "
                    "especialistas do Comitê e do que o research externo monitorado diz sobre o ticker. "
                    "Nunca recalcula recomendação, preço-alvo ou confiança - esses continuam exclusivamente "
                    "do cálculo determinístico. Cada chamada é registrada (modelo/horário/sucesso) para "
                    "auditoria."
                ),
            )
        else:
            st.caption(
                "Leitura de IA (Groq) sobre este Comitê está desligada por configuração "
                "(SINTESE_IA_COMITE_ATIVA=False) - ativação pendente de decisão do Rodrigo."
            )
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
    # usar_sintese_ia só é True quando sugestao_clicada é None (as 3
    # sugestões abaixo disparam direto, sem passar pelo checkbox acima -
    # permanecem 100% determinísticas, mesmo padrão de sempre) E o
    # checkbox foi marcado nesta execução (que só existe quando
    # config.sintese_ia_comite_ativa() está ligada, ver acima).
    with st.spinner(f"Executando {nome_fluxo} para {ticker_executar} — acionando especialistas em paralelo…"):
        try:
            if fluxo_id == "analise_ticker":
                kwargs_fluxo = {"sintese_ia": usar_sintese_ia and not sugestao_clicada}
                if premissas_dcf is not None:
                    kwargs_fluxo["premissas_dcf"] = premissas_dcf
                consolidado = funcao_fluxo(ticker_executar, **kwargs_fluxo)
            else:
                consolidado = funcao_fluxo(ticker_executar)
        except Exception as exc:
            st.error(f"Falha ao executar a análise: {exc!r}")
            return

    duracao_txt = f"{consolidado.get('_duracao_ms', 0) / 1000:.1f}s"
    status_execucao = consolidado.get("status_execucao")
    # Mesma categorização de _badge_status (CONCLUIDA=sucesso, PARCIAL=
    # alerta, qualquer outra coisa=erro) - achado real (2 auditorias,
    # 2026-11-05): antes sempre mostrava st.success mesmo quando a
    # análise ficou PARCIAL (especialista indisponível OU falha ao
    # persistir o resultado completo, ver persistencia.concluir_analise).
    if status_execucao == "CONCLUIDA":
        st.success(f"Análise concluída em {duracao_txt}.")
    elif status_execucao == "PARCIAL":
        st.warning(
            f"Análise concluída em {duracao_txt}, mas de forma PARCIAL - algum especialista "
            "ficou indisponível nesta rodada ou houve falha ao persistir o resultado completo "
            "(ver 'Pontos de atenção' e a coluna Erro em Execuções/Histórico)."
        )
    else:
        st.error(
            f"Análise finalizada em {duracao_txt} com status inesperado "
            f"({status_execucao or 'desconhecido'}) - não assuma que terminou bem."
        )
    render_consolidado(consolidado)
