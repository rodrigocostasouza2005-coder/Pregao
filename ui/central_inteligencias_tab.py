# -*- coding: utf-8 -*-
"""CENTRAL DE INTELIGÊNCIAS (missão noturna 2026-11-12, Agente A) -
console READ-ONLY sobre as inteligências (especialistas do Comitê +
resumos de IA) já registradas/persistidas pelo resto do app. Não
implementa NENHUMA lógica nova de especialista/IA (isso é dos módulos
data/coordenador_central/* e data/ia_cache.py, já existentes) - esta
tela só LÊ o que já está lá e organiza numa visão única por agente:
nome, função, motor (determinístico vs IA), status operacional, última
execução, duração, taxa de sucesso, erro técnico mais recente, e um
histórico de análises com a justificativa auditável (resumo/evidências)
que cada especialista produziu - nunca chain-of-thought privado de
modelo, só o que os módulos de persistência já guardam.

Suposição documentada (o "Agente B" desta missão trabalha em paralelo
na parte de inteligências/persistência - ver instruções da missão): o
schema real de coordenador_analises/coordenador_especialistas_execucoes
(sql/coordenador_central.sql) não tem uma coluna "modelo_ia" por
especialista hoje - quase todos são "zero IA" por design (fachada
determinística sobre módulos já existentes, ver docstrings de
data/coordenador_central/registro.py). O único caso real de IA dentro
do registro de especialistas é `memoria_research` (busca semântica via
GEMINI_API_KEY) - a coluna MOTOR abaixo é derivada do campo real
`pre_requisitos` do registro (não é um palpite solto). Resumos gerados
por LLM de verdade (Groq) vivem numa tabela SEPARADA (resumos_ia_cache,
ver data/ia_cache.py) usada por Research/Notícias - a seção 2 desta
tela cobre esse caso real de "modelo de IA usado" com dado que já é
persistido hoje (campo `modelo`), sem inventar nenhum valor."""

import html

import streamlit as st

from data import ia_cache
from data.coordenador_central import persistencia
from data.coordenador_central.registro import listar_especialistas
from ui.design_system import divisor, subtitulo

_CSS_CENTRAL = """
.central-nota { color: var(--cinza); font-size: 0.7rem; margin: 0.1rem 0 0.9rem 0; line-height: 1.5; }
.central-tabela-wrap { width: 100%; max-width: 100%; overflow-x: auto; margin: 0.35rem 0 1rem; border: 1px solid var(--borda); border-radius: 3px; }
.central-tabela { width: 100%; border-collapse: collapse; font-size: 0.76rem; }
.central-tabela th {
    text-align: left; color: var(--cinza); font-size: 0.64rem; letter-spacing: 0.03em;
    padding: 0.3rem 0.5rem; border-bottom: 1px solid var(--borda); white-space: nowrap;
}
.central-tabela td { text-align: left; padding: 0.35rem 0.5rem; border-bottom: 1px solid var(--borda); vertical-align: top; white-space: nowrap; }
.central-tabela td:nth-child(1), .central-tabela th:nth-child(1) { white-space: normal; }
/* Função (2ª coluna) é a descrição completa do especialista (texto livre,
   pode passar de 150 caracteres) - sem isto ela forçava a linha inteira
   pra 1 só, empurrando Motor/Status/Execuções/Última execução/Erro pra
   fora da viewport (só visíveis rolando horizontalmente, mesmo em
   1440px) - achado real via screenshot Playwright nesta missão. Quebra
   em várias linhas dentro de uma largura máxima, as colunas de status
   (o que a maioria dos usuários realmente precisa ver de cara) ficam
   sempre visíveis sem rolagem. */
.central-tabela td:nth-child(2) { white-space: normal; max-width: 360px; }
.central-nome { color: var(--destaque); font-weight: 600; }
.central-badge {
    display: inline-block; border: 1px solid var(--borda); border-radius: 3px; padding: 0 6px;
    font-size: 0.6rem; letter-spacing: 0.04em; font-family: 'IBM Plex Mono', monospace; white-space: nowrap;
}
.central-badge-ok { border-color: var(--alta); color: var(--alta); }
.central-badge-indisponivel { border-color: var(--cinza); color: var(--cinza); }
.central-badge-erro { border-color: var(--baixa); color: var(--baixa); }
.central-badge-andamento { border-color: var(--destaque); color: var(--destaque); }
.central-motor-ia { color: var(--ciano); }
.central-vazio { color: var(--cinza); font-size: 0.78rem; padding: 0.6rem 0; }
.central-execucao { border: 1px solid var(--borda); padding: 0.5rem 0.65rem; margin-bottom: 0.4rem; font-size: 0.76rem; }
.central-execucao-topo { display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; flex-wrap: wrap; }
.central-execucao-meta { color: var(--cinza); font-size: 0.66rem; margin-top: 0.2rem; }
@media (max-width: 700px) {
    .central-tabela { font-size: 0.7rem; }
    .central-tabela th, .central-tabela td { padding: 0.3rem 0.4rem; }
}
"""


def _injetar_css():
    st.markdown(f"<style>{_CSS_CENTRAL}</style>", unsafe_allow_html=True)


def _badge_status(rotulo: str, classe: str) -> str:
    return f"<span class='central-badge {classe}'>{html.escape(rotulo)}</span>"


def _fmt_data(valor) -> str:
    if valor is None:
        return "—"
    texto = str(valor)
    if "T" in texto:
        texto = texto.split("T", 1)[0] + " " + texto.split("T", 1)[1][:5]
    return texto


def _motor(especialista) -> str:
    """Determinístico (regra/fachada sobre código já existente) ou IA -
    derivado do campo REAL `pre_requisitos` do registro (ver docstring
    do módulo), nunca um palpite por nome."""
    if "GEMINI_API_KEY" in especialista.pre_requisitos:
        return "<span class='central-motor-ia'>IA (Gemini · busca semântica)</span>"
    return "Determinístico (regra/fachada)"


def _secao_especialistas():
    subtitulo("ESPECIALISTAS DO COMITÊ")
    st.markdown(
        "<div class='central-nota'>Inteligências Python já existentes no PREGÃO, orquestradas pelo "
        "Coordenador Central (data/coordenador_central/registro.py) - cada uma reaproveitada, nunca "
        "reescrita. MOTOR vem do pré-requisito real de cada especialista: só memoria_research usa IA "
        "de verdade (busca semântica); os demais são fachada determinística sobre módulos já existentes "
        "do app (zero chamada de IA nova).</div>",
        unsafe_allow_html=True,
    )
    especialistas = listar_especialistas()
    metricas = persistencia.metricas_especialistas()
    if metricas == {} and persistencia.listar_analises_recentes(limite=1) is None:
        st.markdown(
            "<div class='central-vazio'>Métricas de execução indisponíveis agora (Supabase fora do ar) - "
            "lista de especialistas abaixo é o cadastro estático (sempre disponível).</div>",
            unsafe_allow_html=True,
        )

    linhas = []
    for e in especialistas:
        m = metricas.get(e.id) or {}
        total = m.get("total_execucoes", 0)
        taxa_recente = m.get("taxa_sucesso_recente_pct", 0)
        if total == 0:
            status_html = _badge_status("SEM HISTÓRICO", "central-badge-indisponivel")
        elif taxa_recente >= 100.0:
            status_html = _badge_status("OPERACIONAL", "central-badge-ok")
        elif taxa_recente > 0.0:
            status_html = _badge_status("INSTÁVEL", "central-badge-andamento")
        else:
            status_html = _badge_status("FALHANDO", "central-badge-erro")

        ultimo_erro = m.get("ultimo_erro_tecnico")
        erro_html = (
            f"<span title='{html.escape(ultimo_erro)}' style='cursor:help;'>"
            f"{html.escape(ultimo_erro[:50])}{'…' if len(ultimo_erro) > 50 else ''}</span>"
            if ultimo_erro else "—"
        )
        tempo_medio = m.get("tempo_medio_ms")
        linhas.append(
            "<tr>"
            f"<td class='central-nome'>{html.escape(e.nome)}</td>"
            f"<td>{html.escape(e.descricao)}</td>"
            f"<td>{_motor(e)}</td>"
            f"<td>{status_html}</td>"
            f"<td>{total}</td>"
            f"<td>{m.get('taxa_sucesso_pct', '—')}%</td>"
            f"<td>{tempo_medio if tempo_medio is not None else '—'}</td>"
            f"<td>{_fmt_data(m.get('ultima_execucao_em'))}</td>"
            f"<td>{erro_html}</td>"
            "</tr>"
        )
    tabela = (
        "<div class='central-tabela-wrap'><table class='central-tabela'><thead><tr>"
        "<th>Agente</th><th>Função</th><th>Motor</th><th>Status</th><th>Execuções</th>"
        "<th>Taxa sucesso</th><th>Tempo médio (ms)</th><th>Última execução</th><th>Último erro</th>"
        "</tr></thead><tbody>" + "".join(linhas) + "</tbody></table></div>"
    )
    st.markdown(tabela, unsafe_allow_html=True)


def _secao_resumos_ia():
    subtitulo("RESUMOS GERADOS POR IA (RESEARCH / NOTÍCIAS)")
    st.markdown(
        "<div class='central-nota'>Cache global de resumos gerados por LLM (Groq) pra publicações de "
        "research e grupos de notícia (data/ia_cache.py) - cada linha agrega por modelo de IA "
        "efetivamente usado, nunca mostra o conteúdo do resumo nem nenhuma credencial.</div>",
        unsafe_allow_html=True,
    )
    stats = ia_cache.estatisticas_modelos()
    if stats is None:
        st.markdown(
            "<div class='central-vazio'>Indisponível agora (Supabase fora do ar).</div>",
            unsafe_allow_html=True,
        )
        return
    if not stats:
        st.markdown(
            "<div class='central-vazio'>Nenhum resumo de IA cacheado ainda nesta instalação.</div>",
            unsafe_allow_html=True,
        )
        return
    linhas = "".join(
        "<tr>"
        f"<td>{html.escape(str(s['origem']).upper())}</td>"
        f"<td>{html.escape(str(s['modelo']))}</td>"
        f"<td>{s['total']}</td>"
        f"<td>{s['concluidos']}</td>"
        f"<td>{_fmt_data(s['ultimo_atualizado_em'])}</td>"
        "</tr>"
        for s in stats
    )
    tabela = (
        "<div class='central-tabela-wrap'><table class='central-tabela'><thead><tr>"
        "<th>Origem</th><th>Modelo</th><th>Total cacheado</th><th>Concluídos</th><th>Última atualização</th>"
        "</tr></thead><tbody>" + linhas + "</tbody></table></div>"
    )
    st.markdown(tabela, unsafe_allow_html=True)


def _justificativa_especialista(analise: dict):
    """Justificativa AUDITÁVEL (resumo/evidências) por especialista dentro
    de 1 análise consolidada - NUNCA chain-of-thought privado do modelo
    (não existe esse dado aqui: o executor isolado, data/coordenador_
    central/executor.py, só persiste resumo/evidencias/dados do contrato
    padrão, nunca um raciocínio livre). Formato de `resultado` varia por
    tipo_fluxo (ver data/coordenador_central/fluxos.py/consolidacao.py) -
    lê de forma defensiva (.get em tudo), nunca assume uma chave presente."""
    resultado = analise.get("resultado") or {}
    por_especialista = resultado.get("visao_especialistas") or resultado.get("especialistas") or {}
    if not isinstance(por_especialista, dict) or not por_especialista:
        st.markdown(
            "<div class='central-nota'>Sem detalhe por especialista persistido para esta análise "
            "(formato de resultado sem a chave esperada, ou análise ainda EM_ANDAMENTO/ERRO).</div>",
            unsafe_allow_html=True,
        )
        return
    for especialista_id, dados in por_especialista.items():
        if not isinstance(dados, dict):
            continue
        resumo = dados.get("resumo") or "sem resumo disponível"
        evidencias = dados.get("evidencias") or []
        st.markdown(
            f"<div class='central-execucao'><div class='central-execucao-topo'>"
            f"<span class='central-nome'>{html.escape(str(especialista_id))}</span></div>"
            f"<div>{html.escape(str(resumo))}</div>"
            + (
                "<div class='central-execucao-meta'>Fontes: " + "; ".join(
                    html.escape(str(ev.get("fonte") or ev.get("titulo") or "—")) for ev in evidencias[:5]
                ) + "</div>" if evidencias else ""
            )
            + "</div>",
            unsafe_allow_html=True,
        )


def _secao_historico():
    subtitulo("HISTÓRICO DE ANÁLISES (COMITÊ)")
    analises = persistencia.listar_analises_recentes(limite=15)
    if analises is None:
        st.markdown(
            "<div class='central-vazio'>Histórico indisponível agora (Supabase fora do ar).</div>",
            unsafe_allow_html=True,
        )
        return
    if not analises:
        st.markdown(
            "<div class='central-vazio'>Nenhuma análise registrada ainda nesta instalação.</div>",
            unsafe_allow_html=True,
        )
        return
    mapa_status = {
        "CONCLUIDA": ("central-badge-ok", "CONCLUÍDA"), "PARCIAL": ("central-badge-andamento", "PARCIAL"),
        "EM_ANDAMENTO": ("central-badge-andamento", "EM ANDAMENTO"), "ERRO": ("central-badge-erro", "ERRO"),
    }
    for a in analises:
        classe, rotulo = mapa_status.get(a.get("status"), ("central-badge-indisponivel", a.get("status") or "—"))
        duracao = f"{a['duracao_ms']}ms" if isinstance(a.get("duracao_ms"), (int, float)) else "—"
        rotulo_expander = (
            f"{a.get('solicitacao') or a.get('tipo_fluxo')} — {rotulo} — {_fmt_data(a.get('iniciado_em'))} — {duracao}"
        )
        with st.expander(rotulo_expander):
            st.markdown(
                f"<div class='central-execucao-meta'>Fluxo: {html.escape(a.get('tipo_fluxo') or '—')} · "
                f"Ticker: {html.escape(a.get('ticker') or '—')} · "
                f"Status: {_badge_status(rotulo, classe)}"
                + (f" · Erro: {html.escape(a['erro'])}" if a.get("erro") else "")
                + "</div>",
                unsafe_allow_html=True,
            )
            _justificativa_especialista(a)


def render_central(prefs: dict = None):
    _injetar_css()
    st.markdown('<div class="painel-titulo">CENTRAL DE INTELIGÊNCIAS</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='central-nota'>Console read-only: nome do agente, função, motor (determinístico vs IA), "
        "status, última execução, duração e erro técnico mais recente de cada inteligência já registrada no "
        "app, cruzado com o histórico real já persistido pelo Comitê. Nunca mostra credencial/token nem "
        "raciocínio livre de modelo - só a justificativa auditável (resumo e fontes) que já é persistida.</div>",
        unsafe_allow_html=True,
    )
    _secao_especialistas()
    divisor()
    _secao_resumos_ia()
    divisor()
    _secao_historico()
