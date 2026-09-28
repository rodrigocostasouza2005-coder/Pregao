# -*- coding: utf-8 -*-
"""Busca/autocomplete de ativo reutilizável (pedido no redesign do
terminal) - usa st.selectbox sobre uma lista de opções pré-carregada
(cacheada): o campo de busca nativo do Streamlit/BaseWeb já filtra as
opções por substring ao digitar (bate tanto por ticker quanto por nome,
já que a opção mostrada é "TICKER — Nome"), já tem navegação por
teclado (↑/↓/Enter/Esc) de graça, sem nenhuma chamada de rede por tecla
digitada e sem componente customizado (JS) nenhum.

Universo de dados: combina a composição oficial do Ibovespa (B3, via
data/ibovespa.py:obter_composicao_oficial, cache de 24h - mesma fonte já
usada pela aba MERCADO) + config.TICKER_ALIASES (BDRs) + a watchlist
atual do usuário. Se a B3 falhar, cai pro fallback estático
(config.IBOVESPA_SETORES) - nunca fica sem nenhuma opção. Ainda NÃO é o
universo completo de tickers da B3 fora do índice (não existe hoje uma
fonte local/cacheada pra isso, e buscar isso ao vivo a cada tecla
violaria a regra de não bater em API por tecla). Ticker fora dessa lista
continua funcionando normalmente via validação direta (ver app.py, ainda
oferece um campo de texto solto pra esse caso - a busca aqui é um atalho
pros mais comuns, não uma restrição do que pode ser adicionado)."""

import streamlit as st

import config
from data.ibovespa import obter_composicao_oficial


def _universo_ativos(extras: tuple) -> dict:
    """ticker -> "TICKER — Nome" pra montar as opções da busca. Nome
    prioriza config.TICKER_NOME/NOMES_ATIVOS_BUSCA (curadoria manual,
    nomes mais "limpos"), cai pro nome oficial vindo da B3 (composição
    oficial) se o ticker não estiver curado, e por último fica sem nome
    (só o ticker aparece - não inventa nome). `extras` (ex: a watchlist
    atual) garante que tickers fora da composição pelo menos aparecem na
    busca. Função é barata (só dicts em memória, a composição oficial já
    vem cacheada) - não precisa de cache_data própria."""
    composicao = obter_composicao_oficial() or {}
    universo_base = set(composicao.keys()) or set(config.IBOVESPA_SETORES.keys())
    tickers = universo_base | set(config.TICKER_ALIASES.keys()) | set(extras)
    opcoes = {}
    for t in sorted(tickers):
        nome = (
            config.TICKER_NOME.get(t)
            or config.NOMES_ATIVOS_BUSCA.get(t)
            or composicao.get(t, {}).get("nome")
            or ""
        )
        opcoes[t] = f"{t} — {nome}" if nome else t
    return opcoes


def buscar_ativo(label: str, chave: str, extras: list | None = None, ajuda: str | None = None):
    """Selectbox com busca nativa (ticker OU nome da empresa) sobre o
    universo curado de ativos (ver _universo_ativos). Retorna o TICKER
    escolhido, ou None se nada foi selecionado ainda."""
    opcoes_dict = _universo_ativos(tuple(sorted(extras or [])))
    tickers_ordenados = sorted(opcoes_dict.keys())
    return st.selectbox(
        label, tickers_ordenados, index=None,
        format_func=lambda t: opcoes_dict.get(t, t),
        placeholder="Digite o ticker ou nome da empresa…",
        key=chave, help=ajuda,
    )
