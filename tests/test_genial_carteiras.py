# -*- coding: utf-8 -*-
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.research.genial_carteiras import parsear_lista


def _html(mes="Outubro", ano=2026, dia="01", tickers=None):
    tickers = tickers or [
        "PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "BBSE3", "WEGE3",
        "FLRY3", "UGPA3", "GGBR4", "JHSF3", "EMBJ3", "CASH3", "MILS3",
        "VBBR3", "CXSE3", "GOAU4", "DXCO3", "TGMA3", "RADL3",
    ]
    grupos = [tickers[:8], tickers[8:14], tickers[14:]]
    secoes = []
    for nome, grupo in zip(
        ["Carteira Ibovespa 10+", "Carteira Ibovespa 5+", "Carteira Small Caps 8+"],
        grupos,
    ):
        secoes.append("<h2>" + nome + "</h2>")
        secoes.extend("<h3>" + ticker + " · Empresa " + ticker + "</h3>" for ticker in grupo)
    return (
        "<html><body><h1>Carteira Recomendada de Ações · "
        + mes + " de " + str(ano) + "</h1><p>Publicado em "
        + dia + " de " + mes + " de " + str(ano)
        + " às 07:00:00</p>" + "".join(secoes) + "</body></html>"
    )


def test_parseia_carteiras_mensais_oficiais_com_data_e_composicao():
    itens = parsear_lista(_html(), "https://exemplo.com/carteira", hoje=date(2026, 10, 14))
    assert itens is not None
    assert len(itens) == 20
    assert {item["carteira"] for item in itens} == {
        "Ibovespa 10+", "Ibovespa 5+", "Small Caps 8+"
    }
    assert all(item["data_publicacao"] == "2026-10-01" for item in itens)
    assert all(item["fonte_url"] == "https://exemplo.com/carteira" for item in itens)


def test_rejeita_artigo_de_mes_anterior():
    assert parsear_lista(
        _html(mes="Setembro"), "https://exemplo.com/carteira", hoje=date(2026, 10, 14)
    ) is None


def test_rejeita_composicao_parcial():
    assert parsear_lista(
        _html(tickers=["PETR4", "VALE3", "ITUB4"]),
        "https://exemplo.com/carteira",
        hoje=date(2026, 10, 14),
    ) is None
