# -*- coding: utf-8 -*-
"""Historico de recomendacoes/precos-alvo por casa+ticker (tabela
research_recomendacoes_historico, ver sql/research.sql) - NAO perecivel
como research_itens (5 dias, ver store.RETENCAO_DIAS). Existe porque
'O QUE MUDOU' e Research Radar (PROGRESSO.md, fase RESEARCH 2026-10-01)
precisam comparar o valor de HOJE com um valor de verdade do PASSADO, e
research_itens por design nao guarda isso.

So' grava uma linha NOVA quando recomendacao/preco_alvo realmente mudam
desde o ultimo snapshot conhecido daquele casa+ticker - cresce devagar
(poucas linhas por ticker/ano na pratica), e cada linha e' um fato real
("a Genial tinha X, passou a ter Y"), nunca um valor inventado/estimado.

Fonte de dado estruturado historico: Genial (data/research/genial.py), agora
desativada para novas coletas; snapshots ja salvos continuam consultaveis.
A arquitetura permanece generica (campo
'casa' em toda consulta) pra outras fontes alimentarem a mesma tabela no
futuro, se/quando tiverem dado estruturado equivalente."""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from data.supabase_client import obter_cliente

from .base import TTL_COLETA

# Genial Analisa e XP permanecem no histórico já salvo, mas seus coletores
# foram desativados: bloqueios externos persistentes impedem atualização.
COLETA_GENIAL_ATIVA = False

_CAMPOS_COMPARADOS = ("recomendacao", "preco_alvo")
_TZ_SP = ZoneInfo("America/Sao_Paulo")


def ultimo_snapshot(casa: str, ticker: str) -> dict | None:
    """Snapshot mais recente salvo pra esse casa+ticker, ou None se nunca
    houve nenhum (banco fora do ar tambem cai aqui - tratado como 'sem
    historico anterior pra comparar', nunca gera um falso 'mudou')."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (
            cliente.table("research_recomendacoes_historico")
            .select("*")
            .eq("casa", casa).eq("ticker", ticker)
            .order("capturado_em", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as exc:
        print(f"[research.historico] ultimo_snapshot({casa!r}, {ticker!r}) falhou: {exc!r}")
        return None


def historico_ticker(casa: str, ticker: str, limite: int = 10) -> list:
    """Ultimos `limite` snapshots (mais recente primeiro) desse casa+ticker
    - pra exibir evolucao de recomendacao/preco-alvo ao longo do tempo.
    [] se nao houver nenhum ou o banco estiver fora do ar."""
    cliente = obter_cliente()
    if cliente is None:
        return []
    try:
        resp = (
            cliente.table("research_recomendacoes_historico")
            .select("*")
            .eq("casa", casa).eq("ticker", ticker)
            .order("capturado_em", desc=True)
            .limit(limite)
            .execute()
        )
        return resp.data
    except Exception as exc:
        print(f"[research.historico] historico_ticker({casa!r}, {ticker!r}) falhou: {exc!r}")
        return []


def _mudou(anterior: dict | None, recomendacao, preco_alvo) -> bool:
    if anterior is None:
        return True  # primeiro snapshot conhecido - sempre vale registrar
    return anterior.get("recomendacao") != recomendacao or anterior.get("preco_alvo") != preco_alvo


def registrar_se_mudou(casa: str, ticker: str, recomendacao, preco_alvo, potencial_pct=None) -> dict | None:
    """Compara com o ultimo snapshot salvo; so' grava um NOVO snapshot se
    recomendacao OU preco_alvo mudaram de verdade (ou se nunca houve
    nenhum snapshot ainda - primeiro registro). Retorna o snapshot
    ANTERIOR (dict) quando uma mudanca REAL foi detectada e gravada -
    None se nada mudou, se e' o primeiro snapshot (nada pra comparar
    ainda), ou se o banco falhou. Quem chama usa o retorno pra montar
    'recomendacao/preco-alvo mudou de A pra B'."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    anterior = ultimo_snapshot(casa, ticker)
    if not _mudou(anterior, recomendacao, preco_alvo):
        return None
    try:
        cliente.table("research_recomendacoes_historico").insert({
            "casa": casa, "ticker": ticker, "recomendacao": recomendacao,
            "preco_alvo": preco_alvo, "potencial_pct": potencial_pct,
        }).execute()
    except Exception as exc:
        print(f"[research.historico] registrar_se_mudou({casa!r}, {ticker!r}) falhou ao gravar: {exc!r}")
        return None
    return anterior


def _ultimo_snapshot_por_ticker(casa: str, tickers: list) -> dict:
    """Mesmo dado de ultimo_snapshot(casa, ticker), mas pra VARIOS tickers
    de uma vez (1 unica query com `in_`, nao 1 por ticker) - correcao de
    N+1 real encontrada na auditoria de infra (2026-11-11):
    processar_recomendacoes fazia 1 SELECT por item da lista (watchlist
    inteira, pode ser dezenas de tickers) so' pra achar o snapshot
    anterior de cada um, antes mesmo de considerar os INSERTs de quem
    mudou. Devolve {ticker: linha-mais-recente-ou-None} - None explicito
    pros tickers pedidos que nao tem nenhum snapshot ainda (1o registro).
    {} (todos None implicitamente) se o banco estiver fora do ar."""
    tickers = sorted({t for t in tickers if t})
    if not tickers:
        return {}
    cliente = obter_cliente()
    if cliente is None:
        return {}
    try:
        resp = (
            cliente.table("research_recomendacoes_historico")
            .select("*")
            .eq("casa", casa).in_("ticker", tickers)
            .order("capturado_em", desc=True)
            .execute()
        )
    except Exception as exc:
        print(f"[research.historico] _ultimo_snapshot_por_ticker({casa!r}, {len(tickers)} ticker(s)) falhou: {exc!r}")
        return {}
    por_ticker = {}
    for linha in resp.data or []:
        # ordenado desc por capturado_em - a PRIMEIRA linha vista pra um
        # ticker e' sempre a mais recente; ignora as demais.
        por_ticker.setdefault(linha["ticker"], linha)
    return por_ticker


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def processar_recomendacoes(casa: str, recomendacoes: list) -> list:
    """Compara cada recomendacao da lista com o ultimo snapshot salvo e
    retorna so' as MUDANÇAS de verdade detectadas (lista de {ticker,
    casa, de, para} - 'de'/'para' = {recomendacao, preco_alvo}) - pra UI
    de 'O QUE MUDOU'. Quem mudou (ou nunca teve snapshot) grava uma linha
    NOVA - mesma regra de registrar_se_mudou/_mudou, so' que em lote: 1
    SELECT pra todos os tickers (_ultimo_snapshot_por_ticker, via `in_`)
    + 1 INSERT so' com as linhas que de fato mudaram, em vez de 1
    SELECT+INSERT por ticker (correcao de N+1, auditoria 2026-11-11 -
    com a watchlist inteira, era 1 + 2*N idas ao Supabase; agora e'
    sempre 1 + (0 ou 1), independente de N).

    @st.cache_data(ttl=TTL_COLETA) de proposito: sem isso, toda vez que a
    aba RESEARCH renderiza de novo (qualquer interacao, nao so' quando o
    dado de verdade mudou), isso bateria no Supabase a toa - o cache
    garante que so' roda de verdade uma vez por janela de atualizacao
    (mesma janela que obter_recomendacoes() ja usa pra nao rebuscar da
    fonte)."""
    if not recomendacoes:
        return []
    tickers = [rec["ticker"] for rec in recomendacoes]
    anteriores = _ultimo_snapshot_por_ticker(casa, tickers)

    mudancas, linhas_novas = [], []
    for rec in recomendacoes:
        ticker = rec["ticker"]
        recomendacao, preco_alvo = rec.get("recomendacao"), rec.get("preco_alvo")
        anterior = anteriores.get(ticker)
        if not _mudou(anterior, recomendacao, preco_alvo):
            continue
        linhas_novas.append({
            "casa": casa, "ticker": ticker, "recomendacao": recomendacao,
            "preco_alvo": preco_alvo, "potencial_pct": rec.get("potencial_pct"),
        })
        if anterior is not None:
            mudancas.append({
                "ticker": ticker,
                "casa": casa,
                "de": {"recomendacao": anterior.get("recomendacao"), "preco_alvo": anterior.get("preco_alvo")},
                "para": {"recomendacao": recomendacao, "preco_alvo": preco_alvo},
            })

    if not linhas_novas:
        return mudancas

    cliente = obter_cliente()
    if cliente is None:
        return []  # nada foi (nem pode ser) persistido - nunca reporta mudanca nao gravada
    try:
        cliente.table("research_recomendacoes_historico").insert(linhas_novas).execute()
    except Exception as exc:
        print(
            f"[research.historico] processar_recomendacoes({casa!r}) falhou ao gravar "
            f"{len(linhas_novas)} snapshot(s) novo(s) em lote: {exc!r} - nenhuma mudanca "
            "sera reportada (mesma regra de registrar_se_mudou: so' reporta o que foi gravado de verdade)"
        )
        return []  # mesmo padrao de registrar_se_mudou: falha ao gravar -> None/nao reporta
    return mudancas


def _tickers_capturados_hoje(casa: str) -> list:
    """Tickers com pelo menos 1 linha gravada HOJE (fuso America/Sao_Paulo)
    em research_recomendacoes_historico pra essa casa - usado so' por
    mudancas_hoje (ver docstring la') pra saber ONDE procurar, sem
    precisar de uma consulta por ticker. [] se nao houver nenhuma hoje
    ou o banco estiver fora do ar."""
    cliente = obter_cliente()
    if cliente is None:
        return []
    inicio_dia_br = datetime.combine(datetime.now(_TZ_SP).date(), time.min, tzinfo=_TZ_SP)
    inicio_dia_utc = inicio_dia_br.astimezone(timezone.utc)
    try:
        resp = (
            cliente.table("research_recomendacoes_historico")
            .select("ticker")
            .eq("casa", casa)
            .gte("capturado_em", inicio_dia_utc.isoformat())
            .execute()
        )
        return sorted({linha["ticker"] for linha in resp.data})
    except Exception as exc:
        print(f"[research.historico] _tickers_capturados_hoje({casa!r}) falhou: {exc!r}")
        return []


def _ultimos_dois_por_ticker(casa: str, tickers: list) -> dict:
    """Pros tickers dados, devolve {ticker: [snapshot_mais_recente,
    snapshot_anterior]} (so' os 2 ultimos, mesmo recorte de
    historico_ticker(casa, ticker, limite=2)) - numa UNICA query (`in_`),
    nao 1 por ticker. Correcao de N+1 real encontrada na auditoria de
    infra (2026-11-11): mudancas_hoje chamava historico_ticker (1 SELECT)
    pra CADA ticker capturado no dia - com M tickers, eram 1+M idas ao
    Supabase; agora e' sempre 1+1, independente de M. Ticker sem nenhum
    snapshot nao aparece no dict (equivalente a historico_ticker
    devolver [])."""
    tickers = sorted({t for t in tickers if t})
    if not tickers:
        return {}
    cliente = obter_cliente()
    if cliente is None:
        return {}
    try:
        resp = (
            cliente.table("research_recomendacoes_historico")
            .select("*")
            .eq("casa", casa).in_("ticker", tickers)
            .order("capturado_em", desc=True)
            .execute()
        )
    except Exception as exc:
        print(f"[research.historico] _ultimos_dois_por_ticker({casa!r}, {len(tickers)} ticker(s)) falhou: {exc!r}")
        return {}
    por_ticker = {}
    for linha in resp.data or []:
        # ordenado desc por capturado_em - as 2 PRIMEIRAS linhas vistas
        # pra um ticker sao sempre as 2 mais recentes; ignora o resto.
        lista = por_ticker.setdefault(linha["ticker"], [])
        if len(lista) < 2:
            lista.append(linha)
    return por_ticker


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def mudancas_hoje(casa: str) -> list:
    """Mesmo formato/proposito de processar_recomendacoes (lista de
    {ticker, casa, de, para} pro Research Radar/'O QUE MUDOU'), mas lida
    do historico JA' PERSISTIDO em vez de exigir uma chamada AO VIVO a'
    fonte - bug real corrigido (2026-10-09): em producao (Streamlit
    Cloud), Genial tem tentar_coleta_automatica=False (bloqueada por WAF
    - ver data/research/__init__.py), entao obter_recomendacoes() nunca
    roda la' e processar_recomendacoes nunca tinha recomendacoes pra
    comparar - MESMO com coletor_local.py alimentando
    research_recomendacoes_historico via coletar_snapshot_genial() toda
    vez que roda de uma rede onde a Genial nao esta' bloqueada. O
    Research Radar/'O QUE MUDOU' em producao ficavam permanentemente
    vazios pra Genial, nao por falta de dado real, mas porque a UI so'
    sabia ler o dado AO VIVO (desligado), nunca o PERSISTIDO.

    Pra cada ticker com uma linha capturada HOJE, compara os 2 snapshots
    mais recentes (historico_ticker, ja existente) - so' conta como
    mudanca se os 2 existirem e diferirem (1 snapshot so' = primeiro
    registro conhecido, nunca "mudou" - mesma regra de _mudou). []
    se nao houver nenhuma mudanca hoje ou o banco estiver fora do ar."""
    tickers_hoje = _tickers_capturados_hoje(casa)
    if not tickers_hoje:
        return []
    por_ticker = _ultimos_dois_por_ticker(casa, tickers_hoje)

    mudancas = []
    for ticker in tickers_hoje:
        ultimos = por_ticker.get(ticker, [])
        if len(ultimos) < 2:
            continue
        atual, anterior = ultimos[0], ultimos[1]
        if atual.get("recomendacao") == anterior.get("recomendacao") and atual.get("preco_alvo") == anterior.get("preco_alvo"):
            continue
        mudancas.append({
            "ticker": ticker,
            "casa": casa,
            "de": {"recomendacao": anterior.get("recomendacao"), "preco_alvo": anterior.get("preco_alvo")},
            "para": {"recomendacao": atual.get("recomendacao"), "preco_alvo": atual.get("preco_alvo")},
        })
    return mudancas


def coletar_snapshot_genial() -> tuple[int, int]:
    """Busca obter_recomendacoes() da Genial AGORA (sem cache, chamada
    direta - pensada pra rodar fora de uma sessao Streamlit, ex:
    coletor_local.py) e registra no historico so' o que mudou de
    verdade. Retorna (n_comparados, n_mudancas). (0, 0) se a fonte
    falhar (WAF/rede) - nunca lança excecao pra quem chama.

    Nao usa processar_recomendacoes (decorado com st.cache_data) de
    proposito: um script standalone roda uma vez só e encerra, cache de
    sessao nao faz sentido aqui - chama registrar_se_mudou direto por
    item."""
    if not COLETA_GENIAL_ATIVA:
        return 0, 0

    from . import genial

    recomendacoes = genial.obter_recomendacoes() or []
    n_mudancas = 0
    for rec in recomendacoes:
        anterior = registrar_se_mudou(
            "Genial Analisa", rec["ticker"], rec.get("recomendacao"), rec.get("preco_alvo"),
            potencial_pct=rec.get("potencial_pct"),
        )
        if anterior is not None:
            n_mudancas += 1
    return len(recomendacoes), n_mudancas
