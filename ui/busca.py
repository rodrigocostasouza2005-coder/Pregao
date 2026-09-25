# -*- coding: utf-8 -*-
"""Busca/autocomplete de ativo reutilizável (pedido no redesign do
terminal) - usa st.selectbox sobre uma lista de opções pré-carregada
(cacheada): o campo de busca nativo do Streamlit/BaseWeb já filtra as
opções por substring ao digitar (bate tanto por ticker quanto por nome,
já que a opção mostrada é "TICKER — Nome"), já tem navegação por
teclado (↑/↓/Enter/Esc) de graça, sem nenhuma chamada de rede por tecla
digitada e sem componente customizado (JS) nenhum.

Universo de dados: combina config.IBOVESPA_COMPOSICAO (lista curada de
blue chips, mesma já usada pela aba MERCADO) + config.TICKER_ALIASES
(BDRs) + a watchlist atual do usuário - NÃO é o universo completo de
tickers da B3 (não existe hoje uma fonte local/cacheada pra isso, e
buscar isso ao vivo a cada tecla violaria a regra de não bater em API
por tecla) - mesma ressalva já documentada em config.IBOVESPA_COMPOSICAO.
Ticker fora dessa lista curada continua funcionando normalmente via
validação direta (ver app.py, ainda oferece um campo de texto solto
pra esse caso - a busca aqui é um atalho pros mais comuns, não uma
restrição do que pode ser adicionado)."""

import streamlit as st

import config


def _universo_ativos(extras: tuple) -> dict:
    """ticker -> "TICKER — Nome" pra montar as opções da busca. Nomes
    vêm só de config.NOMES_ATIVOS_BUSCA/TICKER_NOME (estático, sem
    request nenhum) - ver comentário lá sobre por que não busca nome
    ao vivo pra montar essa lista (~74 tickers via yfinance levaria
    dezenas de segundos). `extras` (ex: a watchlist atual) garante que
    tickers fora da lista curada pelo menos aparecem na busca (sem
    nome, só o ticker) em vez de ficarem invisíveis. Função é barata
    (só dicts em memória) - não precisa de cache_data."""
    tickers = set(config.IBOVESPA_COMPOSICAO.keys()) | set(config.TICKER_ALIASES.keys()) | set(extras)
    opcoes = {}
    for t in sorted(tickers):
        nome = config.TICKER_NOME.get(t) or config.NOMES_ATIVOS_BUSCA.get(t) or ""
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
