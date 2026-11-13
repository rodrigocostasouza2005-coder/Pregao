# -*- coding: utf-8 -*-
"""Telemetria das chamadas de IA da ARQUITETURA HIBRIDA (missão "PREGÃO
2.1 — IA real híbrida", 2026-11-13) - tabela ia_hibrida_execucoes (ver
sql/ia_hibrida_execucoes.sql, PROPOSTA, não aplicada em produção por
este agente).

Por que um módulo/tabela PRÓPRIOS em vez de reaproveitar data/ia_cache.py
(resumos_ia_cache) ou coordenador_especialistas_execucoes: nenhum dos dois
serve pra auditoria de FALHA. ia_cache.py apaga de propósito a reserva
quando a geração falha (nunca bloquear a próxima tentativa) - uma falha
de IA ali não deixa rastro consultável. coordenador_especialistas_
execucoes é telemetria POR ESPECIALISTA determinístico (disponível/erro
técnico), não tem campo pra modelo/provedor/fontes/entrada de uma chamada
de IA. Este módulo é só OBSERVABILIDADE (nunca usado por nenhuma lógica
de cache/retry/decisão) - toda chamada de IA nova da camada híbrida
(ver data/market_researcher.py:sintese_qualitativa_research e
data/coordenador_central/sintese_ia.py:sintetizar_leitura_comite) grava
exatamente 1 linha aqui, sucesso OU falha, sem nunca apagar nada.

Nunca lança exceção: Supabase fora do ar ou tabela ainda não criada
(migração proposta não aplicada) degrada pra {"ok": False, ...}/None -
quem chama (as funções de síntese) já tem o resultado da IA em mãos
antes de registrar; perder o registro nunca derruba a síntese."""

import hashlib
import json
from datetime import datetime, timezone

from data.supabase_client import obter_cliente

_TABELA = "ia_hibrida_execucoes"
_TAMANHO_MAX_RESUMO = 600


def hash_entrada(payload) -> str:
    """sha256 do payload serializado (chaves ordenadas, determinístico) -
    identidade da entrada sem gravar o prompt gigante em texto puro
    (pedido explícito da missão)."""
    serializado = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _truncar(texto: str, tamanho: int = _TAMANHO_MAX_RESUMO) -> str | None:
    if not texto:
        return None
    texto = str(texto)
    return texto if len(texto) <= tamanho else texto[:tamanho] + "…"


def registrar_execucao(
    *,
    origem: str,
    provedor: str,
    modelo: str | None,
    entrada_hash: str,
    sucesso: bool,
    ticker: str | None = None,
    entrada_resumo: str | None = None,
    fontes: list | None = None,
    duracao_ms: int | None = None,
    motivo_falha: str | None = None,
    resultado_resumo: str | None = None,
) -> bool:
    """Grava 1 linha de auditoria pra UMA chamada de IA da camada híbrida.
    False (nunca lança) quando o Supabase está indisponível ou a tabela
    ainda não existe (migração proposta não aplicada) - a síntese já foi
    gerada e devolvida a quem pediu antes desta chamada; perder o
    registro de telemetria nunca derruba a funcionalidade real."""
    cliente = obter_cliente()
    if cliente is None:
        print(f"[ia_hibrida_telemetria] registrar_execucao({origem!r}): Supabase indisponível - telemetria não gravada")
        return False
    try:
        cliente.table(_TABELA).insert({
            "origem": origem, "ticker": ticker, "provedor": provedor, "modelo": modelo,
            "entrada_hash": entrada_hash, "entrada_resumo": _truncar(entrada_resumo, 300),
            "fontes": fontes or [], "duracao_ms": duracao_ms, "sucesso": bool(sucesso),
            "motivo_falha": _truncar(motivo_falha, 300), "resultado_resumo": _truncar(resultado_resumo),
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return True
    except Exception as exc:
        # best-effort de propósito (mesmo padrão de data/ia_cache.py) - a
        # tabela proposta (sql/ia_hibrida_execucoes.sql) pode ainda não
        # ter sido aplicada em produção; isso nunca deve derrubar a
        # síntese que já foi gerada e devolvida.
        print(f"[ia_hibrida_telemetria] registrar_execucao({origem!r}) falhou ({type(exc).__name__}): {exc!r}")
        return False


def listar_execucoes_recentes(origem: str | None = None, limite: int = 50) -> list | None:
    """Leitura read-only pra consulta/observabilidade (ex: painel de
    Saúde dos Dados ou Central de Inteligências, fora do escopo desta
    missão). None se o Supabase estiver indisponível ou a tabela não
    existir ainda; [] se a tabela existir e estiver vazia."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        consulta = cliente.table(_TABELA).select("*").order("criado_em", desc=True).limit(limite)
        if origem:
            consulta = consulta.eq("origem", origem)
        return consulta.execute().data or []
    except Exception as exc:
        print(f"[ia_hibrida_telemetria] listar_execucoes_recentes falhou: {exc!r}")
        return None
