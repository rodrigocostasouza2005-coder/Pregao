# -*- coding: utf-8 -*-
"""Coletor da Levante Ideias de Investimentos (data/research/levante.py)
com o feed real capturado deste ambiente em 12/11/2026
(tests/fixtures/research/levante_feed_20261112.xml) - 3 itens reais, cada
um com ticker B3 na categoria (RAIZ4/CSNA3/AZZA3) e disclaimer de analista
CNPI real no content:encoded."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import data.research as research
import data.research.levante as lv

_FIXTURE = Path(__file__).parent / "fixtures" / "research" / "levante_feed_20261112.xml"


def _resp(status=200, conteudo=None, tipo="text/html; charset=UTF-8"):
    return SimpleNamespace(status_code=status, content=conteudo if conteudo is not None else _FIXTURE.read_bytes(),
                           headers={"content-type": tipo})


def test_feed_real_traz_os_3_itens_com_ticker_e_campos_normalizados():
    itens = lv.parse_feed(_FIXTURE.read_bytes())
    assert len(itens) == 3
    raizen = itens[0]
    assert raizen["casa"] == "Levante Ideias de Investimentos"
    assert raizen["data"] == "2026-11-09"
    assert raizen["publicado_em"] == "2026-11-09T13:05:50+00:00"
    assert raizen["tickers"] == ["RAIZ4"]
    assert raizen["tipo"] == "ACOES"
    assert raizen["autor"] == "Mauricio Silva"
    assert raizen["link"] == (
        "https://levanteideias.com.br/artigos/e-eu-com-isso/"
        "raizen-raiz4-aprova-aumento-de-capital-de-ate-398-bilhoes-de-reais-e-avanca-na-execucao-da-recuperacao"
    )
    assert itens[1]["tickers"] == ["CSNA3"]
    assert itens[2]["tickers"] == ["AZZA3"] and itens[2]["autor"] == "Equipe Levante"


def test_item_sem_ticker_e_sem_categoria_de_research_fica_fora():
    xml = _FIXTURE.read_text(encoding="utf-8")
    xml = xml.replace(
        "</channel></rss>",
        "<item><title>Como funciona o Tesouro Direto</title>"
        "<link>https://levanteideias.com.br/artigos/educacao/tesouro-direto</link>"
        "<pubDate>Mon, 09 Nov 2026 10:00:00 +0000</pubDate>"
        "<category><![CDATA[educacao financeira]]></category>"
        "</item></channel></rss>",
    )
    titulos = [i["titulo"] for i in lv.parse_feed(xml.encode("utf-8"))]
    assert "Como funciona o Tesouro Direto" not in titulos
    assert len(titulos) == 3


def test_item_com_categoria_research_mas_sem_ticker_entra_como_macro():
    xml = _FIXTURE.read_text(encoding="utf-8")
    xml = xml.replace(
        "</channel></rss>",
        "<item><title>Ouvindo o que o Copom não disse</title>"
        "<link>https://levanteideias.com.br/artigos/copom</link>"
        "<pubDate>Thu, 06 Aug 2026 13:29:24 +0000</pubDate>"
        "<category><![CDATA[research]]></category>"
        "</item></channel></rss>",
    )
    itens = lv.parse_feed(xml.encode("utf-8"))
    copom = next(i for i in itens if i["titulo"] == "Ouvindo o que o Copom não disse")
    assert copom["tipo"] == "MACRO" and copom["tickers"] == []


def test_link_canonico_sem_rastreamento_e_dedup():
    xml = _FIXTURE.read_text(encoding="utf-8").replace(
        "-recuperacao</link>", "-recuperacao?utm_source=rss#x</link>", 1,
    )
    itens = lv.parse_feed(xml.encode("utf-8"))
    links = [i["link"] for i in itens]
    assert links.count(
        "https://levanteideias.com.br/artigos/e-eu-com-isso/"
        "raizen-raiz4-aprova-aumento-de-capital-de-ate-398-bilhoes-de-reais-e-avanca-na-execucao-da-recuperacao",
    ) == 1


def test_item_sem_data_e_descartado_nunca_inventa_data():
    xml = _FIXTURE.read_text(encoding="utf-8").replace(
        "<pubDate>Mon, 09 Nov 2026 13:05:50 +0000</pubDate>", "",
    )
    titulos = [i["titulo"] for i in lv.parse_feed(xml.encode("utf-8"))]
    assert not any("Raízen" in t for t in titulos)


def test_pagina_de_erro_ou_bloqueio_nao_vira_research():
    with patch.object(lv, "permitido", return_value=True), \
         patch.object(lv.requests, "get", return_value=_resp(403, b"<html>Access Denied</html>", "text/html")):
        assert lv.obter_relatorios() is None
    assert "HTTP 403" in lv.motivo_ultima_falha()
    with patch.object(lv, "permitido", return_value=True), \
         patch.object(lv.requests, "get", return_value=_resp(200, b"<html><body>login</body></html>", "text/html")):
        assert lv.obter_relatorios() is None
    assert "não é um feed" in lv.motivo_ultima_falha()


def test_robots_e_rede():
    with patch.object(lv, "permitido", return_value=False):
        assert lv.obter_relatorios() is None
    assert "robots" in lv.motivo_ultima_falha()
    with patch.object(lv, "permitido", return_value=True), \
         patch.object(lv.requests, "get", side_effect=TimeoutError("lento")):
        assert lv.obter_relatorios() is None
    with patch.object(lv, "permitido", return_value=True), patch.object(lv.requests, "get", return_value=_resp()):
        assert len(lv.obter_relatorios()) == 3 and lv.motivo_ultima_falha() is None


def test_casa_registrada_e_coletada_pelo_fluxo_existente():
    casa = next(c for c in research.CASAS if c["id"] == "levante")
    assert casa["disponivel"] and casa["obter_relatorios"] is lv.obter_relatorios
    salvos = []
    with patch.object(lv, "permitido", return_value=True), patch.object(lv.requests, "get", return_value=_resp()), \
         patch.object(research.store, "salvar_itens", side_effect=lambda itens: salvos.extend(itens) or True), \
         patch.object(research, "registrar_tentativa", lambda *a, **k: None):
        n, ok = research.coletar_casa(casa)
    assert ok and n == 3 and {i["casa"] for i in salvos} == {"Levante Ideias de Investimentos"}
