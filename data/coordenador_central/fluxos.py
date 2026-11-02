# -*- coding: utf-8 -*-
"""Fluxos de alto nível do Coordenador Central - o que a UI (ver
ui/coordenador_tab.py) chama. Cada fluxo grava 1 linha de execução
ANTES de rodar qualquer especialista e ATUALIZA ao final (nunca grava só
no fim - se o processo cair no meio, fica rastro de que começou, ver
data/coordenador_central/persistencia.py).

Fluxo A - analisar_ticker: visão agregada de 1 ticker.
Fluxo B - comparar_casas: comparação entre casas de research + as
publicações originais que sustentam cada posição.
Fluxo C - identificar_catalisadores: eventos que podem mover o papel.

Encadeamento real (Fluxo B): só aciona memoria_research se o comparador
já indicou que existe pelo menos 1 casa cobrindo o ticker - sem isso,
memoria_research(ticker=X) sempre devolveria zero resultado (mesma
fonte de dado do comparador) e só gastaria uma chamada sem benefício."""

import time

from data.coordenador_central import consolidacao, executor, persistencia


def _especialista_pulado(especialista_id: str, motivo: str) -> dict:
    """Resultado no mesmo formato de executor.py, mas sem rodar nada -
    usado quando um fluxo decide, com base no resultado de outro
    especialista, que não vale a pena acionar este (ver comparar_casas)."""
    return {
        "id": especialista_id, "execucao_id": None, "disponivel": True,
        "resumo": motivo, "evidencias": [], "motivo_indisponivel": None,
        "duracao_ms": 0, "erro_tecnico": None, "dados": None, "pulado": True,
    }


def _registrar_execucoes(analise_id: str, resultados: dict) -> None:
    for especialista_id, resultado in resultados.items():
        persistencia.registrar_execucao_especialista(analise_id, especialista_id, resultado)


def _concluir_com_erro(analise_id: str, exc: Exception) -> None:
    persistencia.concluir_analise(analise_id, "ERRO", None, erro=repr(exc))


def analisar_ticker(ticker: str) -> dict:
    """Fluxo A: fundamentos/catalisadores/cobertura (analise_ticker) +
    comparação entre casas (comparador) + publicações originais
    (memoria_research) + notícias + catalisadores de calendário - tudo
    em paralelo via executor.executar_varios."""
    ticker = (ticker or "").strip().upper()
    analise_id = persistencia.iniciar_analise(f"Analisar {ticker}", "analise_ticker", ticker)
    inicio = time.monotonic()
    try:
        resultados = executor.executar_varios(
            ["analise_ticker", "comparador", "memoria_research", "noticias", "catalisadores"], ticker=ticker,
        )
        _registrar_execucoes(analise_id, resultados)
        consolidado = consolidacao.consolidar(resultados, ticker=ticker)
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        persistencia.concluir_analise(analise_id, "CONCLUIDA", consolidado)
        consolidado["_analise_id"] = analise_id
        consolidado["_duracao_ms"] = duracao_ms
        return consolidado
    except Exception as exc:
        _concluir_com_erro(analise_id, exc)
        raise


def comparar_casas(ticker: str, casas: list = None) -> dict:
    """Fluxo B: comparador primeiro; memoria_research só é acionado se o
    comparador encontrou cobertura real (ver docstring do módulo -
    encadeamento). `casas` filtra memoria_research por 1, várias ou
    nenhuma casa (2026-11-01: embeddings.buscar/store.listar_premissas
    agora aceitam lista - gap antigo "só filtra com exatamente 1 casa"
    fechado, repassa `casas` inteira direto)."""
    ticker = (ticker or "").strip().upper()
    analise_id = persistencia.iniciar_analise(f"Comparar casas sobre {ticker}", "comparar_casas", ticker)
    inicio = time.monotonic()
    try:
        resultado_comparador = executor.executar_especialista("comparador", ticker=ticker)
        resultados = {"comparador": resultado_comparador}

        casas_encontradas = (resultado_comparador.get("dados") or {}).get("casas") or []
        if casas_encontradas:
            casa_filtro = list(casas) if casas else None
            resultados["memoria_research"] = executor.executar_especialista(
                "memoria_research", ticker=ticker, casa=casa_filtro,
            )
        else:
            resultados["memoria_research"] = _especialista_pulado(
                "memoria_research",
                "Não acionado: o comparador não encontrou nenhuma casa cobrindo este ticker na biblioteca "
                "permanente de research - buscar as publicações originais não traria nenhum resultado novo.",
            )

        _registrar_execucoes(analise_id, resultados)
        consolidado = consolidacao.consolidar(resultados, ticker=ticker)
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        persistencia.concluir_analise(analise_id, "CONCLUIDA", consolidado)
        consolidado["_analise_id"] = analise_id
        consolidado["_duracao_ms"] = duracao_ms
        return consolidado
    except Exception as exc:
        _concluir_com_erro(analise_id, exc)
        raise


def identificar_catalisadores(ticker: str) -> dict:
    """Fluxo C: catalisadores de calendário/proventos + notícias +
    próximo resultado esperado + publicações da memória de research que
    mencionem o ticker - tudo em paralelo."""
    ticker = (ticker or "").strip().upper()
    analise_id = persistencia.iniciar_analise(f"Identificar catalisadores de {ticker}", "catalisadores", ticker)
    inicio = time.monotonic()
    try:
        resultados = executor.executar_varios(
            ["catalisadores", "noticias", "calendario", "memoria_research"], ticker=ticker,
        )
        _registrar_execucoes(analise_id, resultados)
        consolidado = consolidacao.consolidar(resultados, ticker=ticker)
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        persistencia.concluir_analise(analise_id, "CONCLUIDA", consolidado)
        consolidado["_analise_id"] = analise_id
        consolidado["_duracao_ms"] = duracao_ms
        return consolidado
    except Exception as exc:
        _concluir_com_erro(analise_id, exc)
        raise
