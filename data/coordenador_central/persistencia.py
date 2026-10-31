# -*- coding: utf-8 -*-
"""Persistência do Coordenador Central (sql/coordenador_central.sql) -
duas tabelas NOVAS (coordenador_analises / coordenador_especialistas_execucoes),
nunca reaproveitando coordenador_execucoes (esse é o log do SCHEDULER
puro em jobs/coordenador.py, formato incompatível).

Mesmo padrão try/except de data/research/store.py - nunca lança
exceção; None é distinto de vazio ([]/{}) em toda função que lê."""

import uuid
from datetime import datetime, timezone

from data.supabase_client import obter_cliente

_TABELA_ANALISES = "coordenador_analises"
_TABELA_ESPECIALISTAS_EXECUCOES = "coordenador_especialistas_execucoes"

# "Falha recente" (ui/coordenador_tab.py:render_visao_geral) = taxa de
# sucesso < 100% nas últimas N execuções de um especialista - N
# documentado aqui (não é janela de tempo, é contagem de execuções,
# porque especialistas são acionados com frequência bem diferente entre
# si - uma janela de tempo fixa deixaria um especialista raramente
# acionado sempre "sem dado recente").
N_EXECUCOES_RECENTES = 10


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def iniciar_analise(solicitacao: str, tipo_fluxo: str, ticker: str = None) -> str:
    """Reserva uma linha EM_ANDAMENTO ANTES de rodar qualquer especialista
    - rastro de que a análise começou mesmo se o processo cair no meio
    (mesmo princípio de jobs/coordenador.py:_iniciar_execucao). Sempre
    devolve um id (uuid4().hex) - mesmo se o Supabase estiver
    indisponível, quem chama precisa de um id pra seguir o fluxo; só não
    haverá log persistido desta análise nesse caso."""
    analise_id = uuid.uuid4().hex
    cliente = obter_cliente()
    if cliente is None:
        return analise_id
    try:
        cliente.table(_TABELA_ANALISES).insert({
            "id": analise_id, "solicitacao": solicitacao, "tipo_fluxo": tipo_fluxo,
            "ticker": ticker, "status": "EM_ANDAMENTO", "iniciado_em": _agora_iso(),
        }).execute()
    except Exception as exc:
        print(f"[coordenador_central] iniciar_analise falhou: {exc!r}")
    return analise_id


def concluir_analise(analise_id: str, status: str, resultado: dict = None, erro: str = None) -> bool:
    """Atualiza a linha reservada por iniciar_analise com o resultado
    final (status CONCLUIDA/ERRO). False se o Supabase estiver
    indisponível ou a escrita falhar - nunca lança."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        cliente.table(_TABELA_ANALISES).update({
            "status": status, "concluido_em": _agora_iso(), "resultado": resultado, "erro": erro,
        }).eq("id", analise_id).execute()
        return True
    except Exception as exc:
        print(f"[coordenador_central] concluir_analise falhou: {exc!r}")
        return False


def registrar_execucao_especialista(analise_id: str, especialista_id: str, resultado: dict) -> bool:
    """1 linha por acionamento de especialista dentro de uma análise -
    usada por metricas_especialistas() pra monitorar desempenho ao longo
    do tempo. `erro_tecnico` do resultado do executor é persistido aqui
    (coluna `erro`) só pra diagnóstico técnico - nunca exibido na UI."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        cliente.table(_TABELA_ESPECIALISTAS_EXECUCOES).insert({
            "analise_id": analise_id, "especialista_id": especialista_id,
            "disponivel": bool(resultado.get("disponivel")),
            "duracao_ms": resultado.get("duracao_ms"),
            "erro": resultado.get("erro_tecnico"),
            "executado_em": _agora_iso(),
        }).execute()
        return True
    except Exception as exc:
        print(f"[coordenador_central] registrar_execucao_especialista falhou: {exc!r}")
        return False


def listar_analises_recentes(limite: int = 20) -> list | None:
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (
            cliente.table(_TABELA_ANALISES).select("*")
            .order("iniciado_em", desc=True).limit(limite).execute()
        )
        return resp.data or []
    except Exception as exc:
        print(f"[coordenador_central] listar_analises_recentes falhou: {exc!r}")
        return None


def obter_analise(analise_id: str) -> dict | None:
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = cliente.table(_TABELA_ANALISES).select("*").eq("id", analise_id).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception as exc:
        print(f"[coordenador_central] obter_analise falhou: {exc!r}")
        return None


def metricas_especialistas() -> dict:
    """Por especialista: total de execuções, sucessos, taxa de sucesso
    (%) e tempo médio (ms) - calculado em Python sobre
    coordenador_especialistas_execucoes (sem SQL agregado). {} quando o
    Supabase está indisponível OU ainda não há nenhuma execução
    registrada - os dois casos degradam igual aqui (chamador só precisa
    saber "nada pra mostrar", ver ui/coordenador_tab.py)."""
    cliente = obter_cliente()
    if cliente is None:
        return {}
    try:
        resp = cliente.table(_TABELA_ESPECIALISTAS_EXECUCOES).select("*").execute()
        linhas = resp.data or []
    except Exception as exc:
        print(f"[coordenador_central] metricas_especialistas falhou: {exc!r}")
        return {}

    por_especialista = {}
    for linha in linhas:
        especialista_id = linha.get("especialista_id")
        if not especialista_id:
            continue
        por_especialista.setdefault(especialista_id, []).append(linha)

    resultado = {}
    for especialista_id, execucoes in por_especialista.items():
        execucoes_ordenadas = sorted(execucoes, key=lambda l: l.get("executado_em") or "", reverse=True)
        total_execucoes = len(execucoes_ordenadas)
        sucessos = sum(1 for l in execucoes_ordenadas if l.get("disponivel"))
        duracoes = [l["duracao_ms"] for l in execucoes_ordenadas if isinstance(l.get("duracao_ms"), (int, float))]
        tempo_medio = (sum(duracoes) / len(duracoes)) if duracoes else None

        recentes = execucoes_ordenadas[:N_EXECUCOES_RECENTES]
        sucessos_recentes = sum(1 for l in recentes if l.get("disponivel"))
        taxa_recente = (sucessos_recentes / len(recentes) * 100) if recentes else 0.0

        resultado[especialista_id] = {
            "total_execucoes": total_execucoes,
            "sucessos": sucessos,
            "taxa_sucesso_pct": round((sucessos / total_execucoes * 100) if total_execucoes else 0.0, 1),
            "taxa_sucesso_recente_pct": round(taxa_recente, 1),
            "n_execucoes_recentes_consideradas": len(recentes),
            "tempo_medio_ms": round(tempo_medio, 1) if tempo_medio is not None else None,
            "ultima_execucao_em": execucoes_ordenadas[0].get("executado_em") if execucoes_ordenadas else None,
        }
    return resultado
