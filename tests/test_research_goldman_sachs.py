# -*- coding: utf-8 -*-
"""Testes de data/research/goldman_sachs.py - mocka requests.get, nunca
faz chamada de rede. Fixtures reais capturadas em 12/11/2026:
- goldman_sachs_sitemapindex_20261112.xml: resposta real de
  goldmansachs.com/sitemap.xml (<sitemapindex> com 1 entrada,
  sitemap-1.xml).
- goldman_sachs_sitemap_20261112.xml: recorte real de <url> do sitemap
  filho verdadeiro (sitemap-1.xml) - 2 itens de /insights/articles/
  (devem bater o filtro) e 1 item de
  /community-transformation/.../insights/... (deve ser ignorado).
- goldman_sachs_article_20261112.html: o bloco ld+json real (NewsArticle,
  headline/datePublished) da página
  insights/articles/why-the-ecb-is-unlikely-to-keep-rates-higher-than-3-percent."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.goldman_sachs as gs_mod

_FIXTURES = Path(__file__).parent / "fixtures" / "research"
_INDICE = (_FIXTURES / "goldman_sachs_sitemapindex_20261112.xml").read_bytes()
_SITEMAP = (_FIXTURES / "goldman_sachs_sitemap_20261112.xml").read_bytes()
_ARTIGO = (_FIXTURES / "goldman_sachs_article_20261112.html").read_text(encoding="utf-8")


def _resp(status_code=200, content=b"", text="", headers=None):
    class _R:
        pass
    r = _R()
    r.status_code = status_code
    r.content = content
    r.text = text
    r.headers = headers or {"content-type": "application/xml"}
    return r


@pytest.fixture(autouse=True)
def _sem_robots_check():
    with patch.object(gs_mod, "permitido", return_value=True):
        yield


def test_sitemaps_filhos_le_indice_real():
    filhos = gs_mod._sitemaps_filhos(_INDICE)
    assert filhos == ["https://www.goldmansachs.com/sitemap-1.xml"]


def test_candidatos_do_urlset_filtra_so_insights_articles():
    candidatos = gs_mod._candidatos_do_urlset(_SITEMAP)
    locs = [loc for _, loc in candidatos]
    assert "https://www.goldmansachs.com/insights/articles/us-assets-will-benefit-from-steady-growth-and-persistent-advantages" in locs
    assert "https://www.goldmansachs.com/insights/articles/from_briefings_12-mar-2021" in locs
    assert not any("community-transformation" in loc for loc in locs)
    assert len(candidatos) == 2


def test_item_le_headline_e_data_do_ld_json_real():
    item = gs_mod._item(
        _ARTIGO, "https://www.goldmansachs.com/insights/articles/why-the-ecb-is-unlikely-to-keep-rates-higher-than-3-percent",
    )
    assert item is not None
    assert item["titulo"] == "Why the ECB Is Unlikely to Keep Rates Higher Than 3%"
    assert item["data"] == "2026-09-25"
    assert item["casa"] == "Goldman Sachs Insights"
    assert item["tipo"] == "MACRO"
    assert item["setor"] == "Energy"


def test_item_sem_bloco_ld_json_devolve_none():
    assert gs_mod._item("<html><body>sem nada</body></html>", "https://x/y") is None


def test_obter_relatorios_sucesso_fim_a_fim_segue_indice():
    with patch.object(gs_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_INDICE),
            _resp(200, content=_SITEMAP),
            _resp(200, text=_ARTIGO),
            _resp(200, text=_ARTIGO),
        ]
        resultado = gs_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) == 2
    assert gs_mod.motivo_ultima_falha() is None


def test_obter_relatorios_indice_sem_candidato_e_lista_vazia_nao_none():
    sitemap_vazio = (
        b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://www.goldmansachs.com/insights/articles</loc></url>"
        b"</urlset>"
    )
    with patch.object(gs_mod.requests, "get", return_value=_resp(200, content=sitemap_vazio)):
        resultado = gs_mod.obter_relatorios()
    assert resultado == []


def test_obter_relatorios_indice_http_erro_retorna_none_com_motivo():
    with patch.object(gs_mod.requests, "get", return_value=_resp(503)):
        resultado = gs_mod.obter_relatorios()
    assert resultado is None
    assert "503" in gs_mod.motivo_ultima_falha()


def test_obter_relatorios_indice_malformado_retorna_none():
    with patch.object(gs_mod.requests, "get", return_value=_resp(200, content=b"nao e xml")):
        resultado = gs_mod.obter_relatorios()
    assert resultado is None
    assert "XML" in gs_mod.motivo_ultima_falha()


def test_obter_relatorios_excecao_de_rede_retorna_none():
    with patch.object(gs_mod.requests, "get", side_effect=ConnectionError("DNS falhou")):
        resultado = gs_mod.obter_relatorios()
    assert resultado is None
    assert "ConnectionError" in gs_mod.motivo_ultima_falha()


def test_obter_relatorios_todas_as_paginas_falham_retorna_none():
    with patch.object(gs_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_INDICE), _resp(200, content=_SITEMAP),
        ] + [_resp(404) for _ in range(gs_mod._MAX_ITENS)]
        resultado = gs_mod.obter_relatorios()
    assert resultado is None
    assert "nenhuma página individual respondeu" in gs_mod.motivo_ultima_falha()


def test_obter_relatorios_respeita_robots_no_indice():
    with patch.object(gs_mod, "permitido", return_value=False):
        resultado = gs_mod.obter_relatorios()
    assert resultado is None
    assert "robots" in gs_mod.motivo_ultima_falha()


def test_testar_conexao_respeita_robots_txt():
    with patch.object(gs_mod, "permitido", return_value=False):
        ok, detalhe = gs_mod.testar_conexao()
    assert ok is False
    assert "robots" in detalhe


def test_testar_conexao_ok():
    with patch.object(gs_mod.requests, "get", return_value=_resp(200, content=_INDICE)):
        ok, detalhe = gs_mod.testar_conexao()
    assert ok is True
