# -*- coding: utf-8 -*-
"""MARKET MAKERS: camada de inteligencia de mercado compartilhada entre
RADAR e MORNING CALL. Fachada fina sobre data/radar.py (nenhum coletor
novo, nenhuma chamada de IA nova) - so' combina o que ja existia
espalhado (catalisadores, mudancas de tese/CVM, evidencias de
noticia/documento, alerta de qualidade dos indicadores) numa unica
funcao reaproveitavel, pra Morning Call e RADAR nunca precisarem
repetir a mesma consulta nem desenvolver a propria versao.

Contrato de cada evidencia: tipo_evidencia ja' vem de data/radar.py
(TIPO_FATO/TIPO_CALCULO/TIPO_INSUFICIENTE/TIPO_ESTIMATIVA_TERCEIRO/
TIPO_HIPOTESE) - FATO/CALCULO sao verificaveis (fonte+data reais),
HIPOTESE/ESTIMATIVA sao sempre rotuladas como tal na apresentacao,
nunca misturadas sem rotulo. Fonte indisponivel -> lista vazia (nunca
exception), pra uma falha parcial nunca derrubar o resto da pagina/
edicao que consome isto."""
from datetime import datetime
from zoneinfo import ZoneInfo

from data.radar import (
    TIPO_ESTIMATIVA_TERCEIRO,
    TIPO_FATO,
    catalisadores,
    evidencias_recentes,
    linha_valuation,
    mudancas_tese,
)

TZ_SP = ZoneInfo("America/Sao_Paulo")


def _riscos(tickers: tuple) -> dict:
    """{ticker: [alertas de qualidade]} só pra quem tem algum alerta -
    mesmos alertas já calculados pelo Valuation Radar (P/L, margem,
    dívida/EBITDA), sem recalcular nada."""
    riscos = {}
    for ticker in tickers:
        try:
            linha = linha_valuation(ticker)
        except Exception as exc:
            print(f"[market_makers] risco indisponível para {ticker}: {exc!r}")
            continue
        alertas = linha.get("alerta_qualidade") or []
        if alertas:
            riscos[ticker] = alertas
    return riscos


def inteligencia_mercado(tickers: tuple, janela: str = "7 DIAS") -> dict:
    """Visão agregada (multi-ticker) da inteligência de mercado: usada
    pela página MARKET MAKERS e pelo Morning Call. Cada bloco degrada
    sozinho (lista/dict vazio) se a fonte dele falhar - nunca derruba
    os outros blocos."""
    tickers = tuple(dict.fromkeys(tickers))  # preserva ordem, remove duplicata
    agora = datetime.now(TZ_SP)
    try:
        eventos = catalisadores(tickers)
    except Exception as exc:
        print(f"[market_makers] catalisadores indisponíveis: {exc!r}")
        eventos = []
    try:
        mudancas = mudancas_tese(tickers, janela)
    except Exception as exc:
        print(f"[market_makers] mudanças de tese indisponíveis: {exc!r}")
        mudancas = []
    try:
        evidencias = evidencias_recentes(tickers)
    except Exception as exc:
        print(f"[market_makers] evidências indisponíveis: {exc!r}")
        evidencias = []
    return {
        "gerado_em": agora,
        "tickers": tickers,
        "janela": janela,
        "catalisadores": eventos,
        "mudancas": mudancas,
        "evidencias": evidencias,
        "riscos": _riscos(tickers),
    }


def contexto_ticker(ticker: str, janela: str = "7 DIAS") -> dict:
    """Mesma inteligência, recortada pra 1 ativo - usada pelo RADAR pra
    explicar POR QUE um alerta de queda pode importar: cruza o próprio
    movimento com catalisador/mudança de tese REAL na mesma janela.
    `interpretacao` só existe quando há evidência FATO que caiba na
    janela (nunca inventa uma explicação pra preencher a tela -
    None é uma resposta honesta aqui, não um bug)."""
    dados = inteligencia_mercado((ticker,), janela)
    catalisadores_ticker = [c for c in dados["catalisadores"] if c["ticker"] == ticker]
    mudancas_ticker = [m for m in dados["mudancas"] if m["ticker"] == ticker]
    riscos_ticker = dados["riscos"].get(ticker, [])

    interpretacao = None
    if mudancas_ticker:
        m = mudancas_ticker[0]
        interpretacao = {
            "texto": f"{m['categoria']}: {m['descricao']} ({m['data_evento'].strftime('%d/%m/%Y')}).",
            "tipo_evidencia": m.get("tipo_evidencia", TIPO_FATO),
            "fonte_url": m.get("fonte_url"),
            "fonte_label": m.get("fonte_label"),
        }
    elif catalisadores_ticker:
        c = catalisadores_ticker[0]
        interpretacao = {
            "texto": f"Catalisador próximo: {c['categoria']} em {c['data'].strftime('%d/%m/%Y')} ({c['status_label']}).",
            "tipo_evidencia": TIPO_FATO if c.get("confirmado") else TIPO_ESTIMATIVA_TERCEIRO,
            "fonte_url": c.get("fonte_url"),
            "fonte_label": c.get("fonte_label"),
        }

    return {
        "ticker": ticker,
        "gerado_em": dados["gerado_em"],
        "catalisadores": catalisadores_ticker,
        "mudancas": mudancas_ticker,
        "riscos": riscos_ticker,
        "interpretacao": interpretacao,
    }
