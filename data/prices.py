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


@st.cache_resource(show_spinner=False)
def _ultima_cotacao_indice_valida() -> dict:
    """nome -> ultimo dict de cotacao de indice/moeda que veio sem erro.
    st.cache_resource = estado compartilhado entre sessoes/reruns no
    mesmo processo do servidor - usado como fallback quando o yfinance
    falhar, pra nunca mostrar "--" na ticker tape se ja tivermos um valor
    valido recente (o yfinance falha bem mais em IP de datacenter, como
    o do Streamlit Cloud, do que localmente - visto na pratica com
    IBOVESPA/DOLAR ficando "--" em producao)."""
    return {}


@st.cache_data(ttl=30, show_spinner=False)
def obter_cotacao_indice(nome: str, symbol: str) -> dict:
    """
    Cotacao de indice/moeda pra ticker tape (ex: Ibovespa, dolar). Usa
    history() em vez de info()/fast_info: fast_info nao da um
    previousClose confiavel pra pares de moeda (mercado 24/5, sem
    fechamento diario bem definido - testado, previousClose vinha igual
    ao preco atual); info() e' uma chamada mais pesada e mais sujeita a
    falhar/ser limitada pelo Yahoo Finance em IP de datacenter - history()
    e' o mesmo caminho ja usado (e confiavel) pro grafico de precos.

    Se essa chamada falhar, cai pro ultimo valor que deu certo
    (_ultima_cotacao_indice_valida) em vez de mostrar erro/"--" - so
    retorna erro se NUNCA tiver conseguido buscar esse indice ainda.
    """
    cache = _ultima_cotacao_indice_valida()
    try:
        hist = yf.Ticker(symbol).history(period="5d")
        if len(hist) < 2:
            raise ValueError("histórico insuficiente retornado pelo yfinance")
        preco = float(hist["Close"].iloc[-1])
        fechamento_anterior = float(hist["Close"].iloc[-2])
        if fechamento_anterior == 0:
            raise ValueError("fechamento anterior zerado")
        variacao = preco - fechamento_anterior
        variacao_pct = (variacao / fechamento_anterior) * 100
        resultado = {"nome": nome, "preco": preco, "variacao": variacao, "variacao_pct": variacao_pct, "erro": None}
        cache[nome] = resultado
        return resultado
    except Exception as e:
        if nome in cache:
            return cache[nome]
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
def _historico_semanal_ibov():
    """Fechamentos semanais do Ibovespa, 2 anos - base pro calculo local
    de beta (_calcular_beta). Cacheado separado do beta em si: varios
    tickers da watchlist reusam o mesmo historico do indice dentro do
    TTL, em vez de cada um buscar de novo."""
    try:
        hist = yf.Ticker("^BVSP").history(period="2y", interval="1wk")["Close"]
        return hist if not hist.empty else None
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def _calcular_beta(ticker: str) -> float | None:
    """Beta calculado localmente: cov(retornos semanais do ticker,
    retornos semanais do Ibovespa) / var(retornos semanais do Ibovespa),
    2 anos de historico. O campo 'beta' do yfinance costuma vir mal
    calculado pra acoes da B3 (referencia de mercado errada, periodo
    curto etc - ver BACKLOG.md) - por isso recalculado aqui em vez de
    usar info['beta']. None se nao houver historico suficiente."""
    symbol = _para_symbol_yf(ticker)
    try:
        hist_ticker = yf.Ticker(symbol).history(period="2y", interval="1wk")["Close"]
    except Exception:
        return None
    hist_ibov = _historico_semanal_ibov()
    if hist_ibov is None or len(hist_ticker) < 20 or len(hist_ibov) < 20:
        return None
    ret_ticker = hist_ticker.pct_change().dropna()
    ret_ibov = hist_ibov.pct_change().dropna()
    df = pd.DataFrame({"ticker": ret_ticker, "ibov": ret_ibov}).dropna()
    if len(df) < 20:
        return None
    variancia_ibov = df["ibov"].var()
    if not variancia_ibov:
        return None
    return float(df["ticker"].cov(df["ibov"]) / variancia_ibov)


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
        "beta": _calcular_beta(ticker),
    }


_JANELAS_RETORNO_DIAS = {"1D": 1, "1S": 7, "1M": 30, "3M": 91, "6M": 182, "12M": 365}


@st.cache_data(ttl=300, show_spinner=False)
def _precos_base_retornos(ticker: str) -> dict:
    """Preco de fechamento de referencia em cada janela (1D/1S/.../ANO=YTD),
    pra calcular retorno percentual contra o preco atual de fora (fast_info,
    o mesmo do painel PRECOS). Cacheavel porque so depende de historico
    (estavel dentro do TTL); o preco atual muda a cada 30s e fica de fora
    de proposito, senao o cache nunca acertaria. None na janela sem
    historico suficiente."""
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

    data_atual = df.iloc[-1]["Data"]

    bases = {}
    for rotulo, dias in _JANELAS_RETORNO_DIAS.items():
        alvo = data_atual - pd.Timedelta(days=dias)
        anteriores = df[df["Data"] <= alvo]
        bases[rotulo] = float(anteriores.iloc[-1]["Close"]) if not anteriores.empty else None

    inicio_ano = df[df["Data"].dt.year == data_atual.year]
    bases["ANO"] = float(inicio_ano.iloc[0]["Close"]) if not inicio_ano.empty else None

    return bases


def calcular_retornos(ticker: str, preco_atual: float) -> dict:
    """Retorno percentual em varias janelas (1D/1S/1M/3M/6M/12M/ANO=YTD),
    sempre contra o mesmo preco_atual usado no painel PRECOS (fast_info) -
    garante que 1D bate com a VARIACAO DIA e as demais janelas partem do
    mesmo ponto, nao do fechamento historico de ontem."""
    bases = _precos_base_retornos(ticker)
    if not bases or not preco_atual:
        return {}
    return {
        rotulo: ((preco_atual - base) / base) * 100 if base else None
        for rotulo, base in bases.items()
    }


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


_PERIODOS_INTRADIARIOS_YF = {
    "1D": ("5d", "5m"),   # busca 5 pregoes e filtra so o mais recente - funciona
    "1S": ("5d", "30m"),  # tambem com mercado fechado (fim de semana/feriado)
}


@st.cache_data(ttl=90, show_spinner=False)
def obter_historico_intraday(ticker: str, periodo_label: str):
    """
    Historico intradiario (candles de 5min pro '1D', 30min pro '1S') +
    medias moveis. Se o mercado estiver fechado, '1D' mostra o ultimo
    pregao completo disponivel (filtra pela data mais recente que tiver
    dado, em vez de depender do periodo 'ultimo dia' do yfinance, que se
    comporta de forma inconsistente fora do horario de pregao). None se
    a fonte nao tiver intradiario pro ticker (comum em alguns papeis).
    """
    symbol = _para_symbol_yf(ticker)
    period, interval = _PERIODOS_INTRADIARIOS_YF[periodo_label]
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval)
        if df.empty:
            return None
        df = df.reset_index()
        col_data = "Date" if "Date" in df.columns else "Datetime"
        df = df.rename(columns={col_data: "Data"})
        df = _descartar_linhas_invalidas(df)
        if df.empty:
            return None

        if periodo_label == "1D":
            ultimo_dia = df["Data"].dt.date.max()
            df = df[df["Data"].dt.date == ultimo_dia].reset_index(drop=True)

        df = calcular_medias_moveis(df)
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
