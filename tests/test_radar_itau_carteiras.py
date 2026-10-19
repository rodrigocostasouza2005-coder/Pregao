# -*- coding: utf-8 -*-
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.research.itau_carteiras import CASA, CARTEIRA, _url_artigo_mes, parsear_artigo


def test_parser_itau_top5_aceita_tabela_com_cinco_tickers():
    html = """
    <h1>Carteira Top 5 Outubro 2026</h1>
    <table>
      <tr><th>Empresas</th><th>Recomendação</th><th>Peso</th><th>Preço justo</th></tr>
      <tr><td>Embraer (EMBJ3)</td><td>OP</td><td>20%</td><td>124,00</td></tr>
      <tr><td>XP Inc. (XPBR31)</td><td>OP</td><td>20%</td><td>118,0</td></tr>
      <tr><td>PETROBRAS (PETR4)</td><td>OP</td><td>20%</td><td>64,0</td></tr>
      <tr><td>Sabesp (SBSP3)</td><td>OP</td><td>20%</td><td>33,1</td></tr>
      <tr><td>Eneva (ENEV3)</td><td>OP</td><td>20%</td><td>32,7</td></tr>
    </table>
    """
    itens = parsear_artigo(html, "https://hub-conteudo.cloud.itau.com.br/investimentos/carteira-top-5-outubro-2026/", date(2026, 10, 19))
    assert itens is not None
    assert {x["ticker"] for x in itens} == {"PETR4", "XPBR31", "EMBJ3", "SBSP3", "ENEV3"}
    assert all(x["casa"] == CASA and x["carteira"] == CARTEIRA for x in itens)
    assert all(x["fonte_url"].startswith("https://hub-conteudo.cloud.itau.com.br/") for x in itens)
    alvos = {x["ticker"]: x["preco_alvo"] for x in itens}
    assert alvos == {"EMBJ3": 124.0, "XPBR31": 118.0, "PETR4": 64.0, "SBSP3": 33.1, "ENEV3": 32.7}


def test_parser_itau_rejeita_pagina_de_mes_incorreto():
    html = "<h1>Carteira Top 5 Setembro 2026</h1><table><tr><th>Empresas</th></tr></table>"
    assert parsear_artigo(html, "https://example.com", date(2026, 10, 19)) is None


def test_parser_itau_aceita_linhas_textuais_da_pagina_oficial():
    html = """
    <h1>Carteira Top 5 Outubro 2026</h1>
    <p>Embraer (EMBJ3) | Bens de Capital | OP | 20%</p>
    <p>XP Inc. (XPBR31) | Bancos e Serviços Financeiros | OP | 20%</p>
    <p>Eneva (ENEV3) | Energia | OP | 20%</p>
    <p>SABESP (SBSP3) | Utilities | OP | 20%</p>
    <p>PETROBRAS (PETR4) | Petróleo | OP | 20%</p>
    """
    itens = parsear_artigo(html, "https://hub-conteudo.cloud.itau.com.br/investimentos/carteira-top-5-outubro-2026/", date(2026, 10, 19))
    assert itens is not None
    assert {x["ticker"] for x in itens} == {"EMBJ3", "XPBR31", "ENEV3", "SBSP3", "PETR4"}


def test_localiza_link_oficial_da_carteira_do_mes():
    html = """
    <a href="/investimentos/carteiras-recomendadas/carteira-top-5-setembro-2026/">Setembro</a>
    <a href="/investimentos/carteiras-recomendadas/carteira-top-5-outubro-2026/">Outubro</a>
    <a href="/investimentos/carteiras-recomendadas/carteira-top-5-outubro-2025/">Ano anterior</a>
    """
    assert _url_artigo_mes(html, date(2026, 10, 19)) == "https://hub-conteudo.cloud.itau.com.br/investimentos/carteiras-recomendadas/carteira-top-5-outubro-2026/"


def test_parser_itau_rejeita_composicao_incompleta():
    html = """
    <h1>Carteira Top 5 Outubro 2026</h1>
    <p>Embraer (EMBJ3)</p><p>XP Inc. (XPBR31)</p><p>ENEVA (ENEV3)</p>
    """
    assert parsear_artigo(html, "https://www.itau.com.br/investimentos/carteira-top-5-outubro-2026/", date(2026, 10, 19)) is None
