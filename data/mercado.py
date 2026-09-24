# -*- coding: utf-8 -*-
"""Visão de mercado amplo (aba MERCADO): altas/baixas, mais negociados,
termômetro, desempenho setorial, mapa de calor (treemap) e mercados
globais - tudo sobre a composição aproximada do Ibovespa em
config.IBOVESPA_COMPOSICAO (lista curada, ver comentário lá).

Busca em LOTE (yf.download com vários tickers de uma vez) em vez de um
yf.Ticker().fast_info por papel: com ~60 tickers, uma requisição em lote
é ordens de magnitude mais rápida que 60 requisições sequenciais (mesmo
motivo por trás do ThreadPoolExecutor no TOP MERCADO - ver data/news.py).

Curva de juros (DI futuro) NÃO é reimplementada aqui: já existe uma curva
de juros prefixada real (ANBIMA ETTJ) na aba MACRO (data/macro.py,
obter_curva_pre) - duplicar o painel seria redundante. Agenda de
Copom/resultados também NÃO está aqui: exigiria uma fonte de dados de
calendário confiável que o projeto ainda não integra (não dá pra inventar
datas) - ver MELHORIAS FUTURAS em PROGRESSO.md."""

import pandas as pd
import streamlit as st
import yfinance as yf

from config import IBOVESPA_COMPOSICAO, INDICES_GLOBAIS
from data.prices import _para_symbol_yf

_TTL_LOTE = 90  # segundos - batch pesado, nao vale reconsultar a cada poucos segundos


@st.cache_data(ttl=_TTL_LOTE, show_spinner=False)
def _baixar_lote(tickers: tuple) -> pd.DataFrame | None:
    """yf.download em lote pros tickers dados (tupla, hashable p/ cache).
    Retorna DataFrame multi-nivel (colunas: (campo, symbol)) ou None se a
    chamada falhar por completo. Usa period='5d' (nao '1d'): garante pelo
    menos 2 candles pra calcular variacao mesmo se o pregao de hoje ainda
    nao fechou ou tiver 1 dia sem negociacao pra algum papel."""
    symbols = [_para_symbol_yf(t) for t in tickers]
    try:
        df = yf.download(symbols, period="5d", group_by="ticker", threads=True, progress=False, auto_adjust=False)
        return df if not df.empty else None
    except Exception:
        return None


def _linha_papel(df: pd.DataFrame, ticker: str, symbol: str) -> dict | None:
    """Extrai preco/variacao/volume do papel a partir do DataFrame em lote
    (_baixar_lote). None se o papel nao tiver pelo menos 2 candles validos
    (recem-listado, sem negocio, ou o yfinance nao retornou esse symbol)."""
    try:
        sub = df[symbol] if isinstance(df.columns, pd.MultiIndex) else df
        fechamentos = sub["Close"].dropna()
        if len(fechamentos) < 2:
            return None
        preco = float(fechamentos.iloc[-1])
        fechamento_anterior = float(fechamentos.iloc[-2])
        if fechamento_anterior == 0:
            return None
        volume = sub["Volume"].dropna()
        volume_hoje = float(volume.iloc[-1]) if len(volume) else 0.0
        variacao_pct = (preco - fechamento_anterior) / fechamento_anterior * 100
        return {
            "ticker": ticker,
            "preco": preco,
            "variacao_pct": variacao_pct,
            "volume": volume_hoje,
            "volume_financeiro": preco * volume_hoje,
        }
    except Exception:
        return None


@st.cache_data(ttl=_TTL_LOTE, show_spinner=False)
def obter_panorama_ibovespa() -> list:
    """Lista de dicts {ticker, setor, preco, variacao_pct, volume,
    volume_financeiro} pra cada papel de IBOVESPA_COMPOSICAO que
    respondeu com dado valido. [] se o lote inteiro falhar (yfinance fora
    do ar/bloqueado) - quem chama trata como "sem dados agora", nunca
    mostra numero inventado."""
    tickers = tuple(IBOVESPA_COMPOSICAO.keys())
    df = _baixar_lote(tickers)
    if df is None:
        return []
    resultado = []
    for ticker in tickers:
        symbol = _para_symbol_yf(ticker)
        linha = _linha_papel(df, ticker, symbol)
        if linha:
            linha["setor"] = IBOVESPA_COMPOSICAO[ticker]
            resultado.append(linha)
    return resultado


def obter_altas_baixas(n: int = 10) -> tuple:
    """(maiores_altas, maiores_baixas) por variacao_pct, ambas ordenadas
    da mais extrema pra menos extrema, ate n itens cada."""
    papeis = obter_panorama_ibovespa()
    ordenado = sorted(papeis, key=lambda p: p["variacao_pct"], reverse=True)
    altas = [p for p in ordenado if p["variacao_pct"] > 0][:n]
    baixas = sorted([p for p in ordenado if p["variacao_pct"] < 0], key=lambda p: p["variacao_pct"])[:n]
    return altas, baixas


def obter_mais_negociados(n: int = 10) -> list:
    """Papeis com maior volume financeiro (preco x volume) no dia -
    proxy de liquidez/atencao do mercado, ja que volume em quantidade de
    acoes nao e comparavel entre papeis de preco muito diferente."""
    papeis = obter_panorama_ibovespa()
    return sorted(papeis, key=lambda p: p["volume_financeiro"], reverse=True)[:n]


def obter_termometro() -> dict:
    """Contagem simples de papeis em alta / baixa / estaveis (variacao
    exatamente 0, raro mas possivel) no panorama do dia."""
    papeis = obter_panorama_ibovespa()
    alta = sum(1 for p in papeis if p["variacao_pct"] > 0)
    baixa = sum(1 for p in papeis if p["variacao_pct"] < 0)
    estavel = len(papeis) - alta - baixa
    return {"alta": alta, "baixa": baixa, "estavel": estavel, "total": len(papeis)}


def obter_desempenho_setorial() -> list:
    """Variacao media (%) por setor (media simples entre os papeis do
    setor no panorama do dia, sem ponderar por valor de mercado - o
    projeto nao busca valor de mercado em lote, so' por papel individual
    sob demanda em data/prices.py). Ordenado do melhor pro pior
    desempenho. [] se nao houver panorama disponivel."""
    papeis = obter_panorama_ibovespa()
    por_setor: dict = {}
    for p in papeis:
        por_setor.setdefault(p["setor"], []).append(p["variacao_pct"])
    resultado = [
        {"setor": setor, "variacao_media_pct": sum(vals) / len(vals), "n_papeis": len(vals)}
        for setor, vals in por_setor.items()
    ]
    resultado.sort(key=lambda s: s["variacao_media_pct"], reverse=True)
    return resultado


def obter_dados_treemap() -> pd.DataFrame:
    """DataFrame pronto pro px.treemap do mapa de mercado: colunas
    ticker/setor/variacao_pct/tamanho. 'tamanho' usa volume_financeiro
    (proxy de relevancia do papel no pregao de hoje, ja que valor de
    mercado nao e buscado em lote) - papel sem negocio no dia (tamanho 0)
    e excluido, senao o treemap reserva area pra um retangulo invisivel."""
    papeis = obter_panorama_ibovespa()
    linhas = [p for p in papeis if p["volume_financeiro"] > 0]
    if not linhas:
        return pd.DataFrame(columns=["ticker", "setor", "variacao_pct", "tamanho"])
    return pd.DataFrame([
        {"ticker": p["ticker"], "setor": p["setor"], "variacao_pct": p["variacao_pct"], "tamanho": p["volume_financeiro"]}
        for p in linhas
    ])


@st.cache_data(ttl=_TTL_LOTE, show_spinner=False)
def _baixar_lote_bruto(symbols: tuple) -> pd.DataFrame | None:
    """Igual _baixar_lote, mas SEM passar os symbols por _para_symbol_yf -
    usado pros indices globais (config.INDICES_GLOBAIS), que ja vem no
    formato exato que o yfinance espera (ex: '^GSPC', '000001.SS') e NAO
    devem levar o sufixo '.SA' (esse sufixo e' so' pra tickers da B3 sem
    prefixo/sufixo especial - _para_symbol_yf aplicava ele errado em cima
    de '000001.SS', virando '000001.SS.SA', symbol invalido)."""
    try:
        df = yf.download(list(symbols), period="5d", group_by="ticker", threads=True, progress=False, auto_adjust=False)
        return df if not df.empty else None
    except Exception:
        return None


def obter_mercados_globais() -> list:
    """Principais indices globais (config.INDICES_GLOBAIS): preco e
    variacao %, mesmo mecanismo de lote do panorama do Ibovespa. []
    se o lote falhar."""
    nomes = list(INDICES_GLOBAIS.keys())
    symbols = tuple(INDICES_GLOBAIS.values())
    df = _baixar_lote_bruto(symbols)
    if df is None:
        return []
    resultado = []
    for nome, symbol in zip(nomes, symbols):
        linha = _linha_papel(df, nome, symbol)
        if linha:
            resultado.append({"nome": nome, "preco": linha["preco"], "variacao_pct": linha["variacao_pct"]})
    return resultado
