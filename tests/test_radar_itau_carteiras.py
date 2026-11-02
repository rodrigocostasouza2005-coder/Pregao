# -*- coding: utf-8 -*-
from datetime import date

from data.research.itau_carteiras import (
    CASA, CARTEIRA, _artigos_disponiveis, parsear_artigo,
)


def test_seleciona_publicacao_mais_recente_ja_disponivel():
    html = """
    <a href="/investimentos/carteiras-recomendadas/carteira-top-5-setembro-2026/">Setembro</a>
    <a href="/investimentos/carteiras-recomendadas/carteira-top-5-outubro-2026/">Outubro</a>
    <a href="/investimentos/carteiras-recomendadas/carteira-top-5-novembro-2026/">Novembro (futuro)</a>
    <a href="/investimentos/carteiras-recomendadas/carteira-top-5-outubro-2025/">Outubro ano anterior</a>
    """
    artigos = _artigos_disponiveis(
        html, "https://www.itau.com.br/investimentos/carteiras-recomendadas/",
        date(2026, 11, 2),
    )
    assert len(artigos) == 3
    assert artigos[0][1] == date(2026, 10, 1)
    assert "outubro-2026" in artigos[0][0]


def test_parser_aceita_composicao_top5_e_preserva_data_publicacao():
    url = "https://hub-conteudo.cloud.itau.com.br/investimentos/carteira-top-5-outubro-2026/"
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
    itens = parsear_artigo(html, url, date(2026, 11, 2))
    assert itens is not None
    assert {item["ticker"] for item in itens} == {"EMBJ3", "XPBR31", "PETR4", "SBSP3", "ENEV3"}
    assert all(item["casa"] == CASA and item["carteira"] == CARTEIRA for item in itens)
    assert all(item["data_publicacao"] == "2026-10-01" for item in itens)


def test_parser_rejeita_publicacao_futura_ou_composicao_incompleta():
    url = "https://hub-conteudo.cloud.itau.com.br/carteira-top-5-novembro-2026/"
    html = "<h1>Carteira Top 5 Novembro 2026</h1>"
    assert parsear_artigo(html, url, date(2026, 10, 31)) is None
