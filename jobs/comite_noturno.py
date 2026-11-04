# -*- coding: utf-8 -*-
"""Execução noturna do Comitê de Investimentos sobre o universo real do Pregão.

Combina watchlists dos usuários e carteiras públicas vigentes (Itaú, Genial,
Safra), deduplica, respeita análises recentes e limita a quantidade por rodada.
Cada ticker usa o fluxo oficial data.coordenador_central.fluxos.analisar_ticker,
que registra a análise e a telemetria individual dos especialistas.
"""
import time
from datetime import datetime, timedelta, timezone

from data.coordenador_central.fluxos import analisar_ticker
from data.radar_quedas import listar_carteiras, normalizar_ticker
from data.supabase_client import obter_cliente
from data.user_prefs import uniao_watchlists_todos_usuarios

_TABELA_EXECUCOES = "coordenador_execucoes"
LIMITE_TICKERS_RODADA = 20
JANELA_ANALISE_RECENTE_HORAS = 18
_TAMANHO_PAGINA = 1000
_STATUS_QUE_EVITAM_DUPLICIDADE = {"EM_ANDAMENTO", "CONCLUIDA", "PARCIAL"}


def _agora_utc(agora=None):
    agora = agora or datetime.now(timezone.utc)
    if agora.tzinfo is None:
        return agora.replace(tzinfo=timezone.utc)
    return agora.astimezone(timezone.utc)


def _montar_universo(watchlists, carteiras):
    """Watchlists têm prioridade; carteiras recomendadas complementam o universo."""
    por_ticker = {}
    for ticker in sorted(watchlists or []):
        normalizado = normalizar_ticker(ticker)
        if normalizado:
            por_ticker.setdefault(normalizado, set()).add("watchlist")
    for linha in carteiras or []:
        normalizado = normalizar_ticker((linha or {}).get("ticker"))
        if normalizado:
            por_ticker.setdefault(normalizado, set()).add("carteira_recomendada")
    ordenados = sorted(
        por_ticker,
        key=lambda ticker: (
            0 if "watchlist" in por_ticker[ticker] else 1,
            ticker,
        ),
    )
    return ordenados, por_ticker


def _tickers_com_analise_recente(cliente, agora=None):
    """Retorna tickers analisados nas últimas 18h; None sinaliza falha de consulta.

    Inclui EM_ANDAMENTO para impedir duplicidade concorrente e CONCLUIDA/PARCIAL
    para não repetir trabalho recente. ERRO pode ser reprocessado na próxima rodada.
    """
    corte = (_agora_utc(agora) - timedelta(hours=JANELA_ANALISE_RECENTE_HORAS)).isoformat()
    tickers = set()
    inicio = 0
    try:
        while True:
            resposta = (
                cliente.table("coordenador_analises")
                .select("ticker,status,iniciado_em")
                .gte("iniciado_em", corte)
                .order("iniciado_em", desc=True)
                .range(inicio, inicio + _TAMANHO_PAGINA - 1)
                .execute()
            )
            linhas = resposta.data or []
            for linha in linhas:
                if linha.get("status") not in _STATUS_QUE_EVITAM_DUPLICIDADE:
                    continue
                ticker = normalizar_ticker(linha.get("ticker"))
                if ticker:
                    tickers.add(ticker)
            if len(linhas) < _TAMANHO_PAGINA:
                break
            inicio += _TAMANHO_PAGINA
    except Exception as exc:
        print(f"[comite_noturno] falha ao consultar análises recentes: {exc!r}")
        return None
    return tickers


def _iniciar_execucao(cliente):
    try:
        resposta = cliente.table(_TABELA_EXECUCOES).insert({
            "tipo": "comite_noturno",
            "status": "EM_ANDAMENTO",
            "iniciado_em": _agora_utc().isoformat(),
        }).execute()
        return resposta.data[0]["id"] if resposta.data else None
    except Exception as exc:
        print(f"[comite_noturno] falha ao registrar início da rodada: {exc!r}")
        return None


def _concluir_execucao(cliente, execucao_id, *, status, duracao_ms, resumo, erro=None):
    if cliente is None or execucao_id is None:
        return False
    try:
        cliente.table(_TABELA_EXECUCOES).update({
            "status": status,
            "concluido_em": _agora_utc().isoformat(),
            "duracao_ms": duracao_ms,
            "resumo": resumo,
            "erro": erro,
        }).eq("id", execucao_id).execute()
        return True
    except Exception as exc:
        print(f"[comite_noturno] falha ao concluir rodada: {exc!r}")
        return False


def executar(agora=None, limite=None):
    """Roda até 20 tickers por padrão; 0=sucesso, 1=falha real ou rodada parcial."""
    inicio = time.monotonic()
    cliente = obter_cliente()
    if cliente is None:
        print("[comite_noturno] Supabase indisponível; execução cancelada.")
        return 1

    execucao_id = _iniciar_execucao(cliente)
    limite = LIMITE_TICKERS_RODADA if limite is None else max(0, int(limite))

    watchlists = uniao_watchlists_todos_usuarios(cliente)
    if watchlists is None:
        status, erro, resumo = "ERRO", "Não foi possível consultar as watchlists.", "universo indisponível"
        _concluir_execucao(cliente, execucao_id, status=status,
                           duracao_ms=int((time.monotonic() - inicio) * 1000),
                           resumo=resumo, erro=erro)
        return 1

    carteiras = listar_carteiras()
    if carteiras is None:
        status, erro, resumo = "ERRO", "Não foi possível consultar as carteiras recomendadas vigentes.", "universo parcial não executado"
        _concluir_execucao(cliente, execucao_id, status=status,
                           duracao_ms=int((time.monotonic() - inicio) * 1000),
                           resumo=resumo, erro=erro)
        return 1

    universo, origens = _montar_universo(watchlists, carteiras)
    recentes = _tickers_com_analise_recente(cliente, agora)
    if recentes is None:
        _concluir_execucao(cliente, execucao_id, status="ERRO",
                           duracao_ms=int((time.monotonic() - inicio) * 1000),
                           resumo="universo identificado; consulta de idempotência falhou",
                           erro="Não foi possível consultar análises recentes; execução interrompida para evitar duplicidade.")
        return 1

    pendentes = [ticker for ticker in universo if ticker not in recentes]
    selecionados = pendentes[:limite]
    excedentes = max(0, len(pendentes) - len(selecionados))
    concluidas = parciais = falhas = 0

    print(
        f"[comite_noturno] universo={len(universo)} recentes_pulados={len(universo) - len(pendentes)} "
        f"selecionados={len(selecionados)} excedentes={excedentes}"
    )
    for ticker in selecionados:
        try:
            resultado = analisar_ticker(ticker)
            status_ticker = (resultado or {}).get("status_execucao")
            if status_ticker == "CONCLUIDA":
                concluidas += 1
            else:
                parciais += 1
            print(
                f"[comite_noturno] ticker={ticker} status={status_ticker or 'SEM_STATUS'} "
                f"analise_id={(resultado or {}).get('_analise_id', 'nao_informado')}"
            )
        except Exception as exc:
            falhas += 1
            print(f"[comite_noturno] ticker={ticker} falhou: {exc!r}")

    total = len(selecionados)
    if falhas == total and total > 0:
        status = "ERRO"
    elif falhas or parciais or excedentes:
        status = "PARCIAL"
    else:
        status = "OK"

    resumo = (
        f"universo={len(universo)}; analisados={total}; concluidas={concluidas}; "
        f"parciais={parciais}; falhas={falhas}; recentes_pulados={len(universo) - len(pendentes)}; "
        f"aguardando_proxima_rodada={excedentes}"
    )
    duracao_ms = int((time.monotonic() - inicio) * 1000)
    log_ok = _concluir_execucao(
        cliente, execucao_id, status=status, duracao_ms=duracao_ms,
        resumo=resumo, erro=(f"{falhas} ticker(s) falharam." if falhas else None),
    )
    if not log_ok:
        print("[comite_noturno] aviso: a rodada terminou, mas o resumo não foi persistido.")
        return 1
    print(f"[comite_noturno] status={status} {resumo}")
    return 0 if status == "OK" else (1 if status == "ERRO" else 0)


if __name__ == "__main__":
    raise SystemExit(executar())
