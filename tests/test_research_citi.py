# -*- coding: utf-8 -*-
"""Testes de data/research/citi.py - mocka requests.get, nunca faz
chamada de rede. Fixtures reais capturadas em 11/11/2026:
- tests/fixtures/research/citi_sitemap_20261111.xml: recorte real de
  <url> do sitemap verdadeiro (citigroup.com/global/sitemap.xml) - 2 itens
  de /global/insights/ (devem bater o filtro), a página-índice
  /global/insights/research e um item de /global/news/perspectives/
  (devem ser ignorados).
- tests/fixtures/research/citi_article_20261111.html: o bloco ld+json
  real (array schema.org, nó NewsArticle com headline/datePublished) da
  página global/insights/markets-edition-reassessing-the-balance-of-risks."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.citi as citi_mod

_FIXTURES = Path(__file__).parent / "fixtures" / "research"
_SITEMAP = (_FIXTURES / "citi_sitemap_20261111.xml").read_bytes()
_ARTIGO = (_FIXTURES / "citi_article_20261111.html").read_text(encoding="utf-8")


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
    with patch.object(citi_mod, "permitido", return_value=True):
        yield


def test_candidatos_do_sitemap_filtra_so_insights_exclui_indice_e_news():
    candidatos = citi_mod._candidatos_do_sitemap(_SITEMAP)
    locs = [loc for _, loc in candidatos]
    assert "https://www.citigroup.com/global/insights/markets-edition-reassessing-the-balance-of-risks" in locs
    assert "https://www.citigroup.com/global/insights/pix-commercial-adoption-instant-payments" in locs
    assert "https://www.citigroup.com/global/insights/research" not in locs
    assert not any("news/perspectives" in loc for loc in locs)


def test_candidatos_ordenados_por_lastmod_desc():
    candidatos = citi_mod._candidatos_do_sitemap(_SITEMAP)
    lastmods = [lm for lm, _ in candidatos]
    assert lastmods == sorted(lastmods, reverse=True)


def test_item_le_headline_e_data_do_ld_json_real():
    item = citi_mod._item(
        _ARTIGO, "https://www.citigroup.com/global/insights/markets-edition-reassessing-the-balance-of-risks",
    )
    assert item is not None
    assert "Markets Edition" in item["titulo"]
    assert item["data"] == "2026-11-10"
    assert item["publicado_em"].startswith("2026-11-10T18:37:34")
    assert item["casa"] == "Citi Global Insights"
    assert item["tipo"] == "MACRO"


def test_item_sem_bloco_ld_json_devolve_none():
    assert citi_mod._item("<html><body>sem nada</body></html>", "https://x/y") is None


def test_item_ld_json_sem_no_de_artigo_devolve_none():
    html = (
        '<script type="application/ld+json">'
        '[{"@type":"Organization","name":"Citigroup"}]'
        "</script>"
    )
    assert citi_mod._item(html, "https://x/y") is None


def test_obter_relatorios_sucesso_fim_a_fim():
    with patch.object(citi_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=_ARTIGO),
            _resp(200, text=_ARTIGO),
        ]
        resultado = citi_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) == 2
    assert citi_mod.motivo_ultima_falha() is None


def test_obter_relatorios_sitemap_sem_candidato_e_lista_vazia_nao_none():
    sitemap_vazio = (
        b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://www.citigroup.com/global/insights/research</loc></url>"
        b"</urlset>"
    )
    with patch.object(citi_mod.requests, "get", return_value=_resp(200, content=sitemap_vazio)):
        resultado = citi_mod.obter_relatorios()
    assert resultado == []


def test_obter_relatorios_sitemap_http_erro_retorna_none_com_motivo():
    with patch.object(citi_mod.requests, "get", return_value=_resp(503)):
        resultado = citi_mod.obter_relatorios()
    assert resultado is None
    assert "503" in citi_mod.motivo_ultima_falha()


def test_obter_relatorios_sitemap_malformado_retorna_none():
    with patch.object(citi_mod.requests, "get", return_value=_resp(200, content=b"nao e xml")):
        resultado = citi_mod.obter_relatorios()
    assert resultado is None
    assert "XML" in citi_mod.motivo_ultima_falha()


def test_obter_relatorios_excecao_de_rede_no_sitemap_registra_motivo():
    with patch.object(citi_mod.requests, "get", side_effect=ConnectionError("DNS falhou")):
        resultado = citi_mod.obter_relatorios()
    assert resultado is None
    assert "ConnectionError" in citi_mod.motivo_ultima_falha()


def test_obter_relatorios_todas_as_paginas_falham_retorna_none():
    with patch.object(citi_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [_resp(404) for _ in range(citi_mod._MAX_ITENS)]
        resultado = citi_mod.obter_relatorios()
    assert resultado is None
    assert "nenhuma página individual respondeu" in citi_mod.motivo_ultima_falha()


def test_obter_relatorios_1_pagina_falha_isolada_nao_derruba_as_outras():
    pagina_sem_ld_json = "<html><body>bloqueio</body></html>"
    with patch.object(citi_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=pagina_sem_ld_json),
        ] + [_resp(200, text=_ARTIGO) for _ in range(citi_mod._MAX_ITENS)]
        resultado = citi_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) >= 1


def test_obter_relatorios_respeita_robots_no_sitemap():
    with patch.object(citi_mod, "permitido", return_value=False):
        resultado = citi_mod.obter_relatorios()
    assert resultado is None
    assert "robots" in citi_mod.motivo_ultima_falha()


def test_obter_relatorios_limita_numero_de_paginas_buscadas():
    with patch.object(citi_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [
            _resp(200, text=_ARTIGO) for _ in range(50)
        ]
        citi_mod.obter_relatorios()
    assert mock_get.call_count <= 1 + citi_mod._MAX_ITENS


def test_testar_conexao_respeita_robots_txt():
    with patch.object(citi_mod, "permitido", return_value=False):
        ok, detalhe = citi_mod.testar_conexao()
    assert ok is False
    assert "robots" in detalhe


def test_testar_conexao_ok():
    with patch.object(citi_mod.requests, "get", return_value=_resp(200, content=_SITEMAP)):
        ok, detalhe = citi_mod.testar_conexao()
    assert ok is True
