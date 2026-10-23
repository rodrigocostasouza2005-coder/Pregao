# -*- coding: utf-8 -*-
"""MARKET MAKERS (data/market_makers.py): fachada fina sobre
data/radar.py - sem coletor novo, sem IA nova. Testes cobrem a
degradação (fonte indisponível não derruba o resto) e que
`interpretacao` só aparece quando há evidência real de mudança de tese
ou catalisador (nunca inventada pra preencher a tela)."""
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from data import market_makers
from data.radar import TIPO_ESTIMATIVA_TERCEIRO, TIPO_FATO

TZ_SP = ZoneInfo("America/Sao_Paulo")


def _catalisador(ticker="PETR4", confirmado=False):
    return {
        "ticker": ticker, "empresa": "Petrobras", "categoria": "Resultado corporativo",
        "data": date(2026, 11, 14), "status": "PRAZO_CVM", "status_label": "PRAZO CVM",
        "fonte_label": "CVM", "fonte_url": None, "confirmado": confirmado,
    }


def _mudanca(ticker="PETR4"):
    return {
        "ticker": ticker, "categoria": "Research — recomendação/preço-alvo",
        "descricao": "Genial revisou PETR4 de NEUTRO para COMPRA",
        "data_evento": date(2026, 10, 20), "fonte_label": "Genial", "fonte_url": "https://genial.com",
        "tipo_evidencia": TIPO_FATO,
    }


def test_inteligencia_mercado_combina_os_tres_blocos_sem_duplicar_fonte():
    with patch.object(market_makers, "catalisadores", return_value=[_catalisador()]), \
         patch.object(market_makers, "mudancas_tese", return_value=[_mudanca()]), \
         patch.object(market_makers, "evidencias_recentes", return_value=[{"_tipo_item": "noticia"}]):
        dados = market_makers.inteligencia_mercado(("PETR4",))

    assert dados["catalisadores"] == [_catalisador()]
    assert dados["mudancas"] == [_mudanca()]
    assert len(dados["evidencias"]) == 1
    assert dados["tickers"] == ("PETR4",)


def test_fonte_indisponivel_degrada_sem_quebrar_as_outras():
    with patch.object(market_makers, "catalisadores", side_effect=Exception("fonte fora do ar")), \
         patch.object(market_makers, "mudancas_tese", return_value=[_mudanca()]), \
         patch.object(market_makers, "evidencias_recentes", return_value=[]):
        dados = market_makers.inteligencia_mercado(("PETR4",))

    assert dados["catalisadores"] == []  # degrada, não propaga a exceção
    assert dados["mudancas"] == [_mudanca()]  # os outros blocos continuam ok


def test_contexto_ticker_sem_nenhuma_evidencia_nao_inventa_interpretacao():
    with patch.object(market_makers, "catalisadores", return_value=[]), \
         patch.object(market_makers, "mudancas_tese", return_value=[]), \
         patch.object(market_makers, "evidencias_recentes", return_value=[]), \
         patch.object(market_makers, "linha_valuation", return_value={"alerta_qualidade": []}):
        ctx = market_makers.contexto_ticker("WEGE3")

    assert ctx["interpretacao"] is None
    assert ctx["catalisadores"] == []
    assert ctx["mudancas"] == []


def test_contexto_ticker_com_mudanca_de_tese_real_explica_o_movimento():
    with patch.object(market_makers, "catalisadores", return_value=[]), \
         patch.object(market_makers, "mudancas_tese", return_value=[_mudanca("WEGE3")]), \
         patch.object(market_makers, "evidencias_recentes", return_value=[]), \
         patch.object(market_makers, "linha_valuation", return_value={"alerta_qualidade": []}):
        ctx = market_makers.contexto_ticker("WEGE3")

    assert ctx["interpretacao"]["tipo_evidencia"] == TIPO_FATO
    assert "Genial revisou" in ctx["interpretacao"]["texto"]
    assert ctx["interpretacao"]["fonte_url"] == "https://genial.com"


def test_contexto_ticker_catalisador_nao_confirmado_vira_estimativa_nao_fato():
    with patch.object(market_makers, "catalisadores", return_value=[_catalisador("WEGE3", confirmado=False)]), \
         patch.object(market_makers, "mudancas_tese", return_value=[]), \
         patch.object(market_makers, "evidencias_recentes", return_value=[]), \
         patch.object(market_makers, "linha_valuation", return_value={"alerta_qualidade": []}):
        ctx = market_makers.contexto_ticker("WEGE3")

    assert ctx["interpretacao"]["tipo_evidencia"] == TIPO_ESTIMATIVA_TERCEIRO


def test_riscos_so_lista_tickers_com_alerta_de_qualidade_real():
    respostas = {"WEGE3": {"alerta_qualidade": ["dívida/EBITDA acima do histórico"]}, "PETR4": {"alerta_qualidade": []}}
    with patch.object(market_makers, "linha_valuation", side_effect=lambda t: respostas[t]):
        riscos = market_makers._riscos(("WEGE3", "PETR4"))

    assert riscos == {"WEGE3": ["dívida/EBITDA acima do histórico"]}
