# -*- coding: utf-8 -*-
"""Testes de data/research/morgan_stanley.py - mocka requests.get, nunca
faz chamada de rede. Fixtures reais capturadas em 11/11/2026:
- tests/fixtures/research/morgan_stanley_sitemap_20261111.xml: recorte
  real de <url> do sitemap verdadeiro (morganstanley.com/sitemap.xml) -
  2 artigos de /insights/articles/ (devem bater o filtro), 1 podcast e a
  própria página-índice de /insights/articles (devem ser ignorados).
- tests/fixtures/research/morgan_stanley_article_20261111.html: <title> e
  meta `content_publishedAt` reais da página
  insights/articles/2026-us-midterm-election-results-market-impact."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.morgan_stanley as ms_mod

_FIXTURES = Path(__file__).parent / "fixtures" / "research"
_SITEMAP = (_FIXTURES / "morgan_stanley_sitemap_20261111.xml").read_bytes()
_ARTIGO = (_FIXTURES / "morgan_stanley_article_20261111.html").read_text(encoding="utf-8")


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
    with patch.object(ms_mod, "permitido", return_value=True):
        yield


def test_candidatos_do_sitemap_filtra_so_insights_articles():
    candidatos = ms_mod._candidatos_do_sitemap(_SITEMAP)
    locs = [loc for _, loc in candidatos]
    assert "https://www.morganstanley.com/insights/articles/2026-us-midterm-election-results-market-impact" in locs
    assert "https://www.morganstanley.com/insights/articles/agentic-commerce-ai-agents-30-trillion-consumer-spending" in locs
    assert not any("podcasts" in loc for loc in locs)
    assert "https://www.morganstanley.com/insights/articles" not in locs


def test_candidatos_ordenados_por_lastmod_desc():
    candidatos = ms_mod._candidatos_do_sitemap(_SITEMAP)
    lastmods = [lm for lm, _ in candidatos]
    assert lastmods == sorted(lastmods, reverse=True)


def test_item_le_titulo_e_data_do_meta_tag_real():
    item = ms_mod._item(
        _ARTIGO, "https://www.morganstanley.com/insights/articles/2026-us-midterm-election-results-market-impact",
    )
    assert item is not None
    assert item["titulo"] == "What the U.S. Midterm Sweep Could Mean for Markets"
    assert item["data"] == "2026-11-04"
    assert item["publicado_em"].startswith("2026-11-04T05:00:00")
    assert item["casa"] == "Morgan Stanley Insights"
    assert item["tipo"] == "MACRO"


def test_item_sem_meta_data_devolve_none():
    html = "<html><head><title>Sem data | Morgan Stanley</title></head></html>"
    assert ms_mod._item(html, "https://x/y") is None


def test_item_sem_titulo_devolve_none():
    html = '<html><head><meta name="content_publishedAt" content="2026-11-04T05:00:00Z"/></head></html>'
    assert ms_mod._item(html, "https://x/y") is None


def test_obter_relatorios_sucesso_fim_a_fim():
    with patch.object(ms_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=_ARTIGO),
            _resp(200, text=_ARTIGO),
        ]
        resultado = ms_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) == 2
    assert ms_mod.motivo_ultima_falha() is None


def test_obter_relatorios_sitemap_sem_candidato_e_lista_vazia_nao_none():
    sitemap_vazio = (
        b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://www.morganstanley.com/insights/articles</loc></url>"
        b"</urlset>"
    )
    with patch.object(ms_mod.requests, "get", return_value=_resp(200, content=sitemap_vazio)):
        resultado = ms_mod.obter_relatorios()
    assert resultado == []


def test_obter_relatorios_sitemap_http_erro_retorna_none_com_motivo():
    with patch.object(ms_mod.requests, "get", return_value=_resp(503)):
        resultado = ms_mod.obter_relatorios()
    assert resultado is None
    assert "503" in ms_mod.motivo_ultima_falha()


def test_obter_relatorios_sitemap_malformado_retorna_none():
    with patch.object(ms_mod.requests, "get", return_value=_resp(200, content=b"nao e xml")):
        resultado = ms_mod.obter_relatorios()
    assert resultado is None
    assert "XML" in ms_mod.motivo_ultima_falha()


def test_obter_relatorios_excecao_de_rede_no_sitemap_registra_motivo():
    with patch.object(ms_mod.requests, "get", side_effect=ConnectionError("DNS falhou")):
        resultado = ms_mod.obter_relatorios()
    assert resultado is None
    assert "ConnectionError" in ms_mod.motivo_ultima_falha()


def test_obter_relatorios_todas_as_paginas_falham_retorna_none():
    with patch.object(ms_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [_resp(404) for _ in range(ms_mod._MAX_ITENS)]
        resultado = ms_mod.obter_relatorios()
    assert resultado is None
    assert "nenhuma página individual respondeu" in ms_mod.motivo_ultima_falha()


def test_obter_relatorios_1_pagina_falha_isolada_nao_derruba_as_outras():
    pagina_sem_meta = "<html><head><title>Sem data | Morgan Stanley</title></head></html>"
    with patch.object(ms_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=pagina_sem_meta),
        ] + [_resp(200, text=_ARTIGO) for _ in range(ms_mod._MAX_ITENS)]
        resultado = ms_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) >= 1


def test_obter_relatorios_respeita_robots_no_sitemap():
    with patch.object(ms_mod, "permitido", return_value=False):
        resultado = ms_mod.obter_relatorios()
    assert resultado is None
    assert "robots" in ms_mod.motivo_ultima_falha()


def test_obter_relatorios_limita_numero_de_paginas_buscadas():
    with patch.object(ms_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [
            _resp(200, text=_ARTIGO) for _ in range(50)
        ]
        ms_mod.obter_relatorios()
    assert mock_get.call_count <= 1 + ms_mod._MAX_ITENS


def test_testar_conexao_respeita_robots_txt():
    with patch.object(ms_mod, "permitido", return_value=False):
        ok, detalhe = ms_mod.testar_conexao()
    assert ok is False
    assert "robots" in detalhe


def test_testar_conexao_ok():
    with patch.object(ms_mod.requests, "get", return_value=_resp(200, content=_SITEMAP)):
        ok, detalhe = ms_mod.testar_conexao()
    assert ok is True
