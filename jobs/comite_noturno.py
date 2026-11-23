# -*- coding: utf-8 -*-
"""Execução noturna do Comitê de Investimentos sobre o universo real do Pregão.

Combina watchlists dos usuários e carteiras públicas vigentes (Itaú, Genial,
Safra), deduplica, respeita análises recentes e limita a quantidade por rodada.
Cada ticker usa o fluxo oficial data.coordenador_central.fluxos.analisar_ticker,
que registra a análise e a telemetria individual dos especialistas.
"""
import time
from datetime import datetime, timedelta, timezone

import config
from data.coordenador_central.fluxos import analisar_ticker
from data.radar_quedas import listar_carteiras, normalizar_ticker
from data.supabase_client import obter_cliente
from data.user_prefs import uniao_watchlists_todos_usuarios

_TABELA_EXECUCOES = "coordenador_execucoes"
LIMITE_TICKERS_RODADA = 20
JANELA_ANALISE_RECENTE_HORAS = 18
_TAMANHO_PAGINA = 1000
_STATUS_QUE_EVITAM_DUPLICIDADE = {"EM_ANDAMENTO", "CONCLUIDA", "PARCIAL"}


def _deve_usar_sintese_ia(ticker: str, *, ia_ativa: bool, limite: int, sinteses_usadas: int, tickers_com_sintese_ia: set) -> bool:
    """Decide, PARA 1 TICKER desta rodada, se a chamada de `analisar_ticker`
    deve pedir a camada hibrida de IA real (sintese_ia=True) - guard de
    custo explicito (missao "PREGAO 2.3-B", 2026-11-13), 3 condicoes
    independentes, qualquer uma False basta pra negar:

    1. `ia_ativa` - config.sintese_ia_comite_ativa() lido 1x por rodada por
       quem chama (nunca lido aqui dentro, pra manter esta funcao pura e
       facil de testar sem mockar config/secrets).
    2. `ticker not in tickers_com_sintese_ia` - nunca pede sintese de IA
       2x pro MESMO ticker na MESMA rodada (mesmo que `selecionados`
       viesse com duplicidade por algum motivo futuro - a deduplicacao
       de `_montar_universo` hoje ja' garante isso na pratica, mas o
       guard fica aqui tambem, explicito e barato, em vez de confiar so'
       na deduplicacao de outra funcao).
    3. `sinteses_usadas < limite` - teto de tickers/rodada com IA pedida
       (ver config.limite_sinteses_ia_comite_por_noite()); quando o teto
       e' atingido, os tickers restantes da rodada continuam sendo
       analisados normalmente - so' caem pro Comite 100% deterministico
       (sintese_ia=False), nunca sao pulados."""
    if not ia_ativa:
        return False
    if ticker in tickers_com_sintese_ia:
        return False
    if sinteses_usadas >= limite:
        return False
    return True


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

    # Camada hibrida de IA real (Groq) - missao "PREGAO 2.3-B", 2026-11-13.
    # DESLIGADA por padrao (ver config.SINTESE_IA_COMITE_ATIVA_PADRAO /
    # config.sintese_ia_comite_ativa()) - so' lida 1x por rodada aqui, nunca
    # dentro do loop, pra nao reler secrets/env a cada ticker. Quando ligada,
    # `limite_ia` e `tickers_com_sintese_ia`/`sinteses_ia_usadas` garantem o
    # guard de custo (ver _deve_usar_sintese_ia acima): nunca mais de 1
    # ticker repetido na mesma rodada, nunca mais tickers-com-IA que o teto
    # configurado - os tickers excedentes ainda sao analisados, so' sem IA.
    ia_ativa = config.sintese_ia_comite_ativa()
    limite_ia = config.limite_sinteses_ia_comite_por_noite() if ia_ativa else 0
    sinteses_ia_usadas = 0
    tickers_com_sintese_ia: set = set()
    print(
        f"[comite_noturno] sintese_ia: ativa={ia_ativa} "
        f"limite_tickers_por_noite={limite_ia if ia_ativa else 'n/a (desligada)'}"
    )

    print(
        f"[comite_noturno] universo={len(universo)} recentes_pulados={len(universo) - len(pendentes)} "
        f"selecionados={len(selecionados)} excedentes={excedentes}"
    )
    for ticker in selecionados:
        usar_sintese_ia = _deve_usar_sintese_ia(
            ticker, ia_ativa=ia_ativa, limite=limite_ia,
            sinteses_usadas=sinteses_ia_usadas, tickers_com_sintese_ia=tickers_com_sintese_ia,
        )
        try:
            resultado = analisar_ticker(ticker, sintese_ia=usar_sintese_ia)
            if usar_sintese_ia:
                sinteses_ia_usadas += 1
                tickers_com_sintese_ia.add(ticker)
            status_ticker = (resultado or {}).get("status_execucao")
            if status_ticker == "CONCLUIDA":
                concluidas += 1
            else:
                parciais += 1
            print(
                f"[comite_noturno] ticker={ticker} status={status_ticker or 'SEM_STATUS'} "
                f"sintese_ia={usar_sintese_ia} "
                f"analise_id={(resultado or {}).get('_analise_id', 'nao_informado')}"
            )
        except Exception as exc:
            falhas += 1
            print(f"[comite_noturno] ticker={ticker} falhou (sintese_ia={usar_sintese_ia}): {exc!r}")

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
        f"aguardando_proxima_rodada={excedentes}; sinteses_ia={sinteses_ia_usadas}"
    )
    duracao_ms = int((time.monotonic() - inicio) * 1000)
    log_ok = _concluir_execucao(
        cliente, execucao_id, status=status, duracao_ms=duracao_ms,
        resumo=resumo, erro=(f"{falhas} ticker(s) falharam." if falhas else None),
    )
    if not log_ok:
        print("[comite_noturno] aviso: a rodada terminou, mas o resumo não foi persistido.")
        return 1

    # Persistência diária da Carteira Recomendada (snapshot + histórico de
    # revisão + acompanhamento) - reaproveita esta mesma rodada noturna em
    # vez de propor um cron novo. Isolado em try/except por segurança
    # extra: jobs.carteira_recomendada_job.executar() já nunca lança por
    # si só, mas uma falha de import ou algo inesperado aqui nunca deve
    # derrubar o status/retorno do Comitê, que já foi decidido acima.
    try:
        from jobs.carteira_recomendada_job import executar as executar_carteira_recomendada
        executar_carteira_recomendada()
    except Exception as exc:
        print(f"[comite_noturno] persistência da carteira recomendada falhou "
              f"(rodada principal do Comitê não é afetada): {exc!r}")

    print(f"[comite_noturno] status={status} {resumo}")
    return 0 if status == "OK" else (1 if status == "ERRO" else 0)


if __name__ == "__main__":
    raise SystemExit(executar())
