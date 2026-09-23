# -*- coding: utf-8 -*-
"""Cotações e histórico de preços via yfinance (tickers da B3, sufixo .SA)."""

import re

import pandas as pd
import streamlit as st
import yfinance as yf

from config import PERIODOS_BUFFER, PERIODOS_GRAFICO

# sufixo de classe de acao (ON/PN/PNA/PNB/UNT) + segmento de listagem (N1/N2/NM/MA/MB)
# no final do nome, ex: "VALE ON NM" -> "VALE". So remove se vier separado
# por espaco: o yfinance as vezes cola o sufixo no nome (sem espaco), caso
# em que a limpeza nao acerta - por isso tickers problematicos tambem
# entram direto no config.TICKER_NOME.
_SUFIXO_CLASSE_ACAO = re.compile(r"\s+(ON|PN[ABC]?|UNT)(\s+(N[1-3]|NM|MA|MB))?\s*$", re.IGNORECASE)

# sufixo juridico no final do longName, ex: "Vale S.A." -> "Vale",
# "BB Seguridade Participacoes S.A." -> remove "S.A." e depois
# "Participacoes" (aplicado em loop, ja que pode ter mais de um no final)
_SUFIXO_JURIDICO = re.compile(r"\s*(S\.A\.?|S/A|Participações|Holding)\s*$", re.IGNORECASE)

# dias corridos aproximados de cada periodo de exibicao, usados pra recortar
# o historico depois de calcular as medias moveis sobre o buffer maior
_DIAS_EXIBICAO = {
    "1mo": 31,
    "3mo": 93,
    "6mo": 186,
    "1y": 366,
    "5y": 1827,
}


def _para_symbol_yf(ticker: str) -> str:
    """Converte 'PETR4' -> 'PETR4.SA' (mantém se já tiver sufixo, ou se for
    indice/moeda do yfinance, ex: '^BVSP', 'USDBRL=X', que nao levam .SA)."""
    ticker = ticker.strip().upper()
    if ticker.startswith("^") or "=" in ticker or ticker.endswith(".SA"):
        return ticker
    return ticker + ".SA"


def validar_ticker(ticker: str) -> bool:
    """Confirma no yfinance se o ticker existe e tem histórico recente."""
    try:
        symbol = _para_symbol_yf(ticker)
        hist = yf.Ticker(symbol).history(period="5d")
        return not hist.empty
    except Exception:
        return False


@st.cache_data(ttl=30, show_spinner=False)
def obter_cotacao(ticker: str) -> dict:
    """Preço atual, variação do dia, mín/máx dia, volume e mín/máx 52 semanas."""
    symbol = _para_symbol_yf(ticker)
    try:
        fi = yf.Ticker(symbol).fast_info
        preco = fi["lastPrice"]
        fechamento_anterior = fi["previousClose"]
        if preco is None or fechamento_anterior in (None, 0):
            raise ValueError("dados incompletos retornados pelo yfinance")

        variacao = preco - fechamento_anterior
        variacao_pct = (variacao / fechamento_anterior) * 100

        # o yfinance as vezes reporta o dia com dayHigh/dayLow/lastVolume
        # zerados (visto no SMFT3: papel ainda sem negocio no dia, ou
        # atraso na atualizacao) - 0 pareceria uma cotacao valida, entao
        # vira None e a interface mostra "-" em vez de "0,00"
        maxima_dia = fi["dayHigh"] or None
        minima_dia = fi["dayLow"] or None
        volume = fi["lastVolume"] or None

        return {
            "ticker": ticker,
            "preco": preco,
            "variacao": variacao,
            "variacao_pct": variacao_pct,
            "maxima_dia": maxima_dia,
            "minima_dia": minima_dia,
            "volume": volume,
            "maxima_52s": fi["yearHigh"],
            "minima_52s": fi["yearLow"],
            "erro": None,
        }
    except Exception as e:
        return {"ticker": ticker, "erro": str(e)}


@st.cache_data(ttl=30, show_spinner=False)
def obter_cotacao_indice(nome: str, symbol: str) -> dict:
    """
    Cotacao de indice/moeda pra ticker tape (ex: Ibovespa, dolar). Usa
    info() em vez de fast_info porque o fast_info do yfinance nao da um
    previousClose confiavel pra pares de moeda (mercado 24/5, sem
    fechamento diario bem definido) - testado, previousClose vinha igual
    ao preco atual.
    """
    try:
        info = yf.Ticker(symbol).info
        preco = info.get("regularMarketPrice")
        fechamento_anterior = info.get("regularMarketPreviousClose")
        if preco is None or fechamento_anterior in (None, 0):
            raise ValueError("dados incompletos retornados pelo yfinance")
        variacao = preco - fechamento_anterior
        variacao_pct = (variacao / fechamento_anterior) * 100
        return {"nome": nome, "preco": preco, "variacao": variacao, "variacao_pct": variacao_pct, "erro": None}
    except Exception as e:
        return {"nome": nome, "erro": str(e)}


def _dividend_yield_12m(ticker_obj, preco_atual: float):
    """DY = soma dos dividendos/JCP pagos nos ultimos 12 meses / preco atual.
    Calculado a partir do historico de dividendos (mais confiavel pra B3 do
    que o campo 'dividendYield' do yfinance, que em alguns papeis destoa
    do que realmente foi pago). None se nao houver historico ou preco."""
    try:
        divs = ticker_obj.dividends
        if divs.empty or not preco_atual:
            return None
        limite = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
        soma_12m = divs[divs.index >= limite].sum()
        if soma_12m <= 0:
            return None
        return (soma_12m / preco_atual) * 100
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def obter_indicadores(ticker: str) -> dict:
    """Indicadores fundamentalistas via yfinance. Campos ausentes viram None
    (a interface mostra '-' em vez de inventar)."""
    symbol = _para_symbol_yf(ticker)
    tk = yf.Ticker(symbol)
    try:
        info = tk.info
    except Exception:
        info = {}
    preco_atual = info.get("currentPrice") or info.get("regularMarketPrice")
    return {
        "valor_mercado": info.get("marketCap"),
        "pl": info.get("trailingPE"),
        "pvp": info.get("priceToBook"),
        "dividend_yield": _dividend_yield_12m(tk, preco_atual),
        "beta": info.get("beta"),
    }


_JANELAS_RETORNO_DIAS = {"1D": 1, "1S": 7, "1M": 30, "3M": 91, "6M": 182, "12M": 365}


@st.cache_data(ttl=300, show_spinner=False)
def calcular_retornos(ticker: str) -> dict:
    """Retorno percentual em varias janelas (1D/1S/1M/3M/6M/12M/ANO=YTD).
    None na janela que nao tiver historico suficiente."""
    symbol = _para_symbol_yf(ticker)
    try:
        df = yf.Ticker(symbol).history(period="2y", interval="1d")
        if df.empty:
            return {}
        df = df.reset_index()
        col_data = "Date" if "Date" in df.columns else "Datetime"
        df = df.rename(columns={col_data: "Data"})
        df = _descartar_linhas_invalidas(df)
        if df.empty:
            return {}
    except Exception:
        return {}

    preco_atual = df.iloc[-1]["Close"]
    data_atual = df.iloc[-1]["Data"]

    resultados = {}
    for rotulo, dias in _JANELAS_RETORNO_DIAS.items():
        alvo = data_atual - pd.Timedelta(days=dias)
        anteriores = df[df["Data"] <= alvo]
        if anteriores.empty:
            resultados[rotulo] = None
        else:
            preco_base = anteriores.iloc[-1]["Close"]
            resultados[rotulo] = ((preco_atual - preco_base) / preco_base) * 100

    inicio_ano = df[df["Data"].dt.year == data_atual.year]
    resultados["ANO"] = (
        ((preco_atual - inicio_ano.iloc[0]["Close"]) / inicio_ano.iloc[0]["Close"]) * 100
        if not inicio_ano.empty else None
    )

    return resultados


def _limpar_sufixo_juridico(nome: str) -> str:
    """Remove S.A./S/A/Participacoes do final, repetindo ate nao sobrar nenhum."""
    anterior = None
    while anterior != nome:
        anterior = nome
        nome = _SUFIXO_JURIDICO.sub("", nome).strip()
    return nome


def _limpar_nome_curto(nome: str) -> str:
    """Remove sufixo de classe de acao/segmento e ajusta capitalizacao (shortName)."""
    nome = _SUFIXO_CLASSE_ACAO.sub("", nome).strip()
    return nome.title()


@st.cache_data(ttl=86400, show_spinner=False)
def obter_nome_yf(ticker: str) -> str:
    """
    Nome da empresa via yfinance (fallback pra quando nao esta no config.TICKER_NOME,
    que fica so pras excecoes onde isso aqui nao da conta). longName e' a fonte
    principal (ja vem bem capitalizado, so tira o sufixo juridico do final);
    shortName limpo entra so se o longName nao existir.
    """
    symbol = _para_symbol_yf(ticker)
    try:
        info = yf.Ticker(symbol).info
    except Exception:
        return ""

    nome_longo = (info.get("longName") or "").strip()
    if nome_longo:
        return _limpar_sufixo_juridico(nome_longo)

    nome_curto = (info.get("shortName") or "").strip()
    if nome_curto:
        return _limpar_nome_curto(nome_curto)

    return ""


def _descartar_linhas_invalidas(df):
    """Remove candles com Open/High/Low/Close <= 0 ou NaN - o yfinance as
    vezes publica o pregao do dia assim antes de fechar/consolidar (visto
    no SMFT3: O/H/L=0 com Close ainda valido). Nunca mostrar 0 como cotacao."""
    colunas = ["Open", "High", "Low", "Close"]
    valido = (df[colunas] > 0).all(axis=1) & df[colunas].notna().all(axis=1)
    return df[valido].reset_index(drop=True)


def calcular_medias_moveis(df):
    """Adiciona colunas MM20, MM50 e MM200 (média móvel simples do fechamento)."""
    df = df.copy()
    df["MM20"] = df["Close"].rolling(window=20).mean()
    df["MM50"] = df["Close"].rolling(window=50).mean()
    df["MM200"] = df["Close"].rolling(window=200).mean()
    return df


@st.cache_data(ttl=300, show_spinner=False)
def obter_historico(ticker: str, periodo_label: str):
    """
    Histórico OHLCV + médias móveis para o período escolhido (ex: '1M', '1A').
    Busca um período maior (buffer) pra ter dados suficientes pra calcular
    MM20/50/200 mesmo no inicio da janela exibida, e só depois recorta pro
    período pedido. None se falhar.
    """
    symbol = _para_symbol_yf(ticker)
    period_exibicao, interval = PERIODOS_GRAFICO[periodo_label]
    period_buffer, _ = PERIODOS_BUFFER[periodo_label]
    try:
        df = yf.Ticker(symbol).history(period=period_buffer, interval=interval)
        if df.empty:
            return None
        df = df.reset_index()
        # yfinance nomeia a coluna de data como 'Date' (diario) ou 'Datetime' (intraday)
        col_data = "Date" if "Date" in df.columns else "Datetime"
        df = df.rename(columns={col_data: "Data"})
        df = _descartar_linhas_invalidas(df)
        if df.empty:
            return None

        df = calcular_medias_moveis(df)

        dias = _DIAS_EXIBICAO.get(period_exibicao, 186)
        corte = df["Data"].max() - pd.Timedelta(days=dias)
        df = df[df["Data"] >= corte].reset_index(drop=True)

        return df
    except Exception:
        return None


def dias_sem_pregao(df):
    """Dias uteis dentro do periodo do df que nao tem pregao (feriados), pra
    remover do eixo X do grafico via rangebreaks."""
    datas = df["Data"]
    if datas.dt.tz is not None:
        datas = datas.dt.tz_localize(None)
    datas = datas.dt.normalize()
    dias_uteis = pd.bdate_range(datas.min(), datas.max())
    faltando = dias_uteis.difference(pd.DatetimeIndex(datas.unique()))
    return list(faltando)
