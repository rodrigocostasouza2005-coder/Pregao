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

Fonte de dado estruturado hoje: so' Genial (data/research/genial.py:
obter_recomendacoes/obter_swing_trade) - arquitetura generica (campo
'casa' em toda consulta) pra outras fontes alimentarem a mesma tabela no
futuro, se/quando tiverem dado estruturado equivalente."""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from data.supabase_client import obter_cliente

from .base import TTL_COLETA

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
    except Exception:
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
    except Exception:
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
    except Exception:
        return None
    return anterior


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def processar_recomendacoes(casa: str, recomendacoes: list) -> list:
    """Chama registrar_se_mudou pra cada recomendacao da lista (st.cache_data
    hashea o CONTEUDO da lista/dict, nao precisa ser tupla) e retorna só
    as MUDANÇAS de verdade detectadas (lista de {ticker, casa, de, para} -
    'de'/'para' = {recomendacao, preco_alvo}) - pra UI de 'O QUE MUDOU'.

    @st.cache_data(ttl=TTL_COLETA) de proposito: sem isso, toda vez que a
    aba RESEARCH renderiza de novo (qualquer interacao, nao so' quando o
    dado de verdade mudou), isso bateria no Supabase (1 select + talvez 1
    insert por ticker da watchlist) a toa - o cache garante que so' roda
    de verdade uma vez por janela de atualizacao (mesma janela que
    obter_recomendacoes() ja usa pra nao rebuscar da fonte)."""
    mudancas = []
    for rec in recomendacoes:
        anterior = registrar_se_mudou(
            casa, rec["ticker"], rec.get("recomendacao"), rec.get("preco_alvo"),
            potencial_pct=rec.get("potencial_pct"),
        )
        if anterior is not None:
            mudancas.append({
                "ticker": rec["ticker"],
                "casa": casa,
                "de": {"recomendacao": anterior.get("recomendacao"), "preco_alvo": anterior.get("preco_alvo")},
                "para": {"recomendacao": rec.get("recomendacao"), "preco_alvo": rec.get("preco_alvo")},
            })
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
    except Exception:
        return []


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
    mudancas = []
    for ticker in _tickers_capturados_hoje(casa):
        ultimos = historico_ticker(casa, ticker, limite=2)
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
