# -*- coding: utf-8 -*-
"""Visão de mercado amplo (aba MERCADO): altas/baixas, mais negociados,
termômetro, desempenho setorial, mapa de calor (treemap) e mercados
globais - universo de tickers vem da composição oficial da B3
(data/ibovespa.py:obter_composicao_oficial), com fallback pra lista
curada estática (config.IBOVESPA_SETORES) se a B3 falhar. Setor de cada
papel sempre vem da curadoria manual (a B3 não classifica por setor
nesse endpoint) - ver comentário em config.py.

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

# timeout explicito (yf.download ja tem default interno de 10s nesta
# versao da lib, mas deixado explicito de proposito em vez de depender
# do default implicito - mesmo principio de data/prices.py:_TIMEOUT_YF)
_TIMEOUT_YF = 15

from config import IBOVESPA_SETORES, INDICES_GLOBAIS
from data.coletores_status import registrar_tentativa
from data.ibovespa import obter_composicao_oficial
from data.prices import _para_symbol_yf

_TTL_LOTE = 90  # segundos - batch pesado, nao vale reconsultar a cada poucos segundos

# janelas de desempenho alem do dia (pedido do Rodrigo, 2026-09-28) - dias
# CORRIDOS, mesma convencao ja usada em data/prices.py:_JANELAS_RETORNO_DIAS
# (1S=7/1M=30) pra bater com o que o resto do app ja chama de "semana"/"mes".
_JANELAS_DESEMPENHO_DIAS = {"variacao_semana_pct": 7, "variacao_mes_pct": 30}

# campo do dict de cada papel (ver _linha_papel) por janela de exibicao -
# usado pelas funcoes obter_* que aceitam `janela` (dia/semana/mes)
CAMPO_VARIACAO_POR_JANELA = {
    "dia": "variacao_pct", "semana": "variacao_semana_pct", "mes": "variacao_mes_pct",
}


@st.cache_data(ttl=_TTL_LOTE, show_spinner=False)
def _baixar_lote(tickers: tuple) -> pd.DataFrame | None:
    """yf.download em lote pros tickers dados (tupla, hashable p/ cache).
    Retorna DataFrame multi-nivel (colunas: (campo, symbol)) ou None se a
    chamada falhar por completo. Usa period='2mo' (nao '5d'): garante
    historico suficiente pra calcular desempenho de semana/mes (7/30 dias
    corridos), alem de continuar garantindo pelo menos 2 candles pra
    variacao do dia mesmo se o pregao de hoje ainda nao fechou."""
    symbols = [_para_symbol_yf(t) for t in tickers]
    try:
        df = yf.download(symbols, period="2mo", group_by="ticker", threads=True, progress=False, auto_adjust=False, timeout=_TIMEOUT_YF)
        if df.empty:
            registrar_tentativa("MERCADO", "yfinance (lote)", execucao_ok=False,
                                 erro="yf.download retornou vazio", categoria="Cotacoes")
            return None
        registrar_tentativa("MERCADO", "yfinance (lote)", execucao_ok=True,
                             registros_novos=len(symbols), categoria="Cotacoes")
        return df
    except Exception as e:
        # registro de SAUDE DOS DADOS (ver data/saude_dados.py) - so'
        # numa execucao real (cache miss do @st.cache_data acima), nunca
        # muda o comportamento de retorno (continua None na falha)
        registrar_tentativa("MERCADO", "yfinance (lote)", execucao_ok=False,
                             erro=str(e)[:300], categoria="Cotacoes")
        return None


def _linha_papel(df: pd.DataFrame, ticker: str, symbol: str) -> dict | None:
    """Extrai preco/variacao/volume do papel a partir do DataFrame em lote
    (_baixar_lote). None se o papel nao tiver pelo menos 2 candles validos
    (recem-listado, sem negocio, ou o yfinance nao retornou esse symbol).
    variacao_semana_pct/variacao_mes_pct ficam None (nao inventa dado) se
    nao houver candle disponivel na janela pedida (ex: papel listado ha
    menos de 30 dias)."""
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

        data_atual = fechamentos.index[-1]
        resultado = {
            "ticker": ticker,
            "preco": preco,
            "variacao_pct": variacao_pct,
            "volume": volume_hoje,
            "volume_financeiro": preco * volume_hoje,
        }
        for campo, dias in _JANELAS_DESEMPENHO_DIAS.items():
            alvo = data_atual - pd.Timedelta(days=dias)
            anteriores = fechamentos[fechamentos.index <= alvo]
            if anteriores.empty:
                resultado[campo] = None
                continue
            base = float(anteriores.iloc[-1])
            resultado[campo] = ((preco - base) / base * 100) if base else None
        return resultado
    except Exception:
        return None


def obter_cotacoes_lote(tickers: tuple) -> dict:
    """{ticker: {"preco", "variacao_pct", "erro"}} pra VARIOS tickers de
    uma vez, via UMA UNICA requisicao em lote (_baixar_lote, mesmo
    mecanismo de obter_panorama_ibovespa) - pensado pra telas que mostram
    a watchlist inteira (ex: VISÃO GERAL, ticker tape do header). N+1
    real corrigido (2026-10-08): essas telas chamavam
    data/prices.py:obter_cotacao (1 yf.Ticker().fast_info por papel) num
    loop - com watchlist de 10+ tickers e cache (30s) expirado, a
    renderização ficava bloqueada numa sequência de round-trips
    sequenciais ao Yahoo. Ticker que o lote não trouxe (symbol não
    respondeu/recém-listado) cai com erro, nunca quebra o resto."""
    if not tickers:
        return {}
    df = _baixar_lote(tuple(tickers))
    if df is None:
        return {t: {"erro": "fonte de cotação indisponível"} for t in tickers}
    resultado = {}
    for t in tickers:
        linha = _linha_papel(df, t, _para_symbol_yf(t))
        if linha is None:
            resultado[t] = {"erro": "sem dado"}
        else:
            resultado[t] = {"preco": linha["preco"], "variacao_pct": linha["variacao_pct"], "erro": None}
    return resultado


@st.cache_data(ttl=_TTL_LOTE, show_spinner="atualizando panorama do mercado…")
def obter_panorama_ibovespa() -> list:
    """show_spinner com texto (nao False): achado real (2026-10-08) - a
    auditoria de feedback de carregamento ausente (CVM/NEWS/MACRO/
    RESEARCH, commit 9fd20a1) tinha deixado mercado.py de fora. Em
    consulta fria (cache de 90s expirado), MERCADO/VISÃO GERAL (que
    reaproveita este mesmo painel - ver ui/visao_geral.py) ficavam
    parados sem nenhum aviso ate o yf.download (~80 tickers) responder.
    Seguro mostrar o spinner aqui (ao contrario de _baixar_lote, usado
    tambem por obter_cotacoes_lote DENTRO de fragments com run_every -
    essa funcao nunca e' chamada de dentro de um fragment, confirmado
    nao ha' risco de o spinner "piscar" a cada atualizacao automatica).

    Lista de dicts {ticker, setor, preco, variacao_pct,
    variacao_semana_pct, variacao_mes_pct, volume, volume_financeiro}
    pra cada papel da composição oficial do Ibovespa (B3) que respondeu
    com dado valido (as duas variacoes extras podem vir None
    individualmente - ver _linha_papel). Setor sempre vem da curadoria
    manual (IBOVESPA_SETORES); ticker sem entrada la cai em "Outros" -
    nao inventa setor. [] se o lote inteiro falhar (yfinance fora do ar/
    bloqueado) - quem chama trata como "sem dados agora", nunca mostra
    numero inventado."""
    composicao = obter_composicao_oficial()
    tickers = tuple(composicao.keys()) if composicao else tuple(IBOVESPA_SETORES.keys())
    df = _baixar_lote(tickers)
    if df is None:
        return []
    resultado = []
    for ticker in tickers:
        symbol = _para_symbol_yf(ticker)
        linha = _linha_papel(df, ticker, symbol)
        if linha:
            linha["setor"] = IBOVESPA_SETORES.get(ticker, "Outros")
            resultado.append(linha)
    return resultado


def obter_altas_baixas(n: int = 10, janela: str = "dia") -> tuple:
    """(maiores_altas, maiores_baixas) por variacao na janela pedida
    (dia/semana/mes - ver CAMPO_VARIACAO_POR_JANELA), ambas ordenadas da
    mais extrema pra menos extrema, ate n itens cada. Papel sem dado
    valido na janela (ex: listado ha menos de 30 dias) fica de fora, nao
    aparece com numero inventado."""
    campo = CAMPO_VARIACAO_POR_JANELA[janela]
    papeis = [p for p in obter_panorama_ibovespa() if p.get(campo) is not None]
    ordenado = sorted(papeis, key=lambda p: p[campo], reverse=True)
    altas = [p for p in ordenado if p[campo] > 0][:n]
    baixas = sorted([p for p in ordenado if p[campo] < 0], key=lambda p: p[campo])[:n]
    return altas, baixas


def obter_mais_negociados(n: int = 10) -> list:
    """Papeis com maior volume financeiro (preco x volume) no dia -
    proxy de liquidez/atencao do mercado, ja que volume em quantidade de
    acoes nao e comparavel entre papeis de preco muito diferente."""
    papeis = obter_panorama_ibovespa()
    return sorted(papeis, key=lambda p: p["volume_financeiro"], reverse=True)[:n]


def obter_termometro(janela: str = "dia") -> dict:
    """Contagem simples de papeis em alta / baixa / estaveis (variacao
    exatamente 0, raro mas possivel) na janela pedida (dia/semana/mes).
    Papel sem dado valido na janela fica fora de 'total' (nao conta nem
    como alta/baixa/estavel - contagem so' sobre quem respondeu)."""
    campo = CAMPO_VARIACAO_POR_JANELA[janela]
    papeis = [p for p in obter_panorama_ibovespa() if p.get(campo) is not None]
    alta = sum(1 for p in papeis if p[campo] > 0)
    baixa = sum(1 for p in papeis if p[campo] < 0)
    estavel = len(papeis) - alta - baixa
    return {"alta": alta, "baixa": baixa, "estavel": estavel, "total": len(papeis)}


def obter_desempenho_setorial(janela: str = "dia") -> list:
    """Variacao media (%) por setor na janela pedida (dia/semana/mes -
    media simples entre os papeis do setor com dado valido nessa janela,
    sem ponderar por valor de mercado - o projeto nao busca valor de
    mercado em lote, so' por papel individual sob demanda em
    data/prices.py). Ordenado do melhor pro pior desempenho. [] se nao
    houver panorama disponivel."""
    campo = CAMPO_VARIACAO_POR_JANELA[janela]
    papeis = obter_panorama_ibovespa()
    por_setor: dict = {}
    for p in papeis:
        if p.get(campo) is not None:
            por_setor.setdefault(p["setor"], []).append(p[campo])
    resultado = [
        {"setor": setor, "variacao_media_pct": sum(vals) / len(vals), "n_papeis": len(vals)}
        for setor, vals in por_setor.items() if vals
    ]
    resultado.sort(key=lambda s: s["variacao_media_pct"], reverse=True)
    return resultado



@st.cache_data(ttl=_TTL_LOTE, show_spinner="atualizando mercados globais…")
def _baixar_lote_bruto(symbols: tuple) -> pd.DataFrame | None:
    """Igual _baixar_lote, mas SEM passar os symbols por _para_symbol_yf -
    usado pros indices globais (config.INDICES_GLOBAIS), que ja vem no
    formato exato que o yfinance espera (ex: '^GSPC', '000001.SS') e NAO
    devem levar o sufixo '.SA' (esse sufixo e' so' pra tickers da B3 sem
    prefixo/sufixo especial - _para_symbol_yf aplicava ele errado em cima
    de '000001.SS', virando '000001.SS.SA', symbol invalido).

    show_spinner com texto (mesmo achado de obter_panorama_ibovespa acima):
    unica usuaria desta funcao e' obter_mercados_globais, nunca chamada de
    dentro de um fragment - seguro mostrar o spinner sem risco de piscar
    a cada atualizacao automatica."""
    try:
        df = yf.download(list(symbols), period="5d", group_by="ticker", threads=True, progress=False, auto_adjust=False, timeout=_TIMEOUT_YF)
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
