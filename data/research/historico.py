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

import streamlit as st

from data.supabase_client import obter_cliente

from .base import TTL_COLETA

_CAMPOS_COMPARADOS = ("recomendacao", "preco_alvo")


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
