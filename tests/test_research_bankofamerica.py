# -*- coding: utf-8 -*-
"""Testes de data/research/bankofamerica.py - mocka requests.get, nunca
faz chamada de rede. Fixtures reais capturadas em 11/11/2026:
- tests/fixtures/research/bankofamerica_sitemap_20261111.xml: recorte real
  de <url> do sitemap verdadeiro (institute.bankofamerica.com) - 2 artigos
  de /economic-insights/ (devem bater o filtro), a própria página-índice
  e uma página de outra seção (/transformation/, devem ser ignoradas).
- tests/fixtures/research/bankofamerica_article_20261111.html: <title>
  real da página economic-insights/trading-down.html (a página não expõe
  data de publicação confiável no HTML - por isso o módulo usa o lastmod
  do sitemap, ver docstring de data/research/bankofamerica.py)."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.bankofamerica as boa_mod

_FIXTURES = Path(__file__).parent / "fixtures" / "research"
_SITEMAP = (_FIXTURES / "bankofamerica_sitemap_20261111.xml").read_bytes()
_ARTIGO = (_FIXTURES / "bankofamerica_article_20261111.html").read_text(encoding="utf-8")


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
    with patch.object(boa_mod, "permitido", return_value=True):
        yield


def test_candidatos_do_sitemap_filtra_so_economic_insights_com_slug():
    candidatos = boa_mod._candidatos_do_sitemap(_SITEMAP)
    locs = [loc for _, loc in candidatos]
    assert "https://institute.bankofamerica.com/economic-insights/trading-down.html" in locs
    assert "https://institute.bankofamerica.com/economic-insights/monthly-employment-report-october-2026.html" in locs
    assert "https://institute.bankofamerica.com/economic-insights.html" not in locs
    assert not any("transformation" in loc for loc in locs)


def test_candidatos_ordenados_por_lastmod_desc():
    candidatos = boa_mod._candidatos_do_sitemap(_SITEMAP)
    lastmods = [lm for lm, _ in candidatos]
    assert lastmods == sorted(lastmods, reverse=True)


def test_candidatos_sem_lastmod_nunca_entra():
    sitemap = (
        b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://institute.bankofamerica.com/economic-insights/sem-data.html</loc></url>"
        b"</urlset>"
    )
    assert boa_mod._candidatos_do_sitemap(sitemap) == []


def test_item_le_titulo_real_e_usa_lastmod_como_data():
    item = boa_mod._item(
        _ARTIGO, "https://institute.bankofamerica.com/economic-insights/trading-down.html", "2026-11-06",
    )
    assert item is not None
    assert item["titulo"] == "Can consumers escape inflation?"
    assert item["data"] == "2026-11-06"
    assert item["casa"] == "BofA Institute"
    assert item["tipo"] == "MACRO"


def test_item_sem_titulo_devolve_none():
    assert boa_mod._item("<html><head></head></html>", "https://x/y", "2026-11-06") is None


def test_obter_relatorios_sucesso_fim_a_fim():
    with patch.object(boa_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=_ARTIGO),
            _resp(200, text=_ARTIGO),
        ]
        resultado = boa_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) == 2
    assert boa_mod.motivo_ultima_falha() is None


def test_obter_relatorios_sitemap_sem_candidato_e_lista_vazia_nao_none():
    sitemap_vazio = (
        b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://institute.bankofamerica.com/economic-insights.html</loc></url>"
        b"</urlset>"
    )
    with patch.object(boa_mod.requests, "get", return_value=_resp(200, content=sitemap_vazio)):
        resultado = boa_mod.obter_relatorios()
    assert resultado == []


def test_obter_relatorios_sitemap_http_erro_retorna_none_com_motivo():
    with patch.object(boa_mod.requests, "get", return_value=_resp(503)):
        resultado = boa_mod.obter_relatorios()
    assert resultado is None
    assert "503" in boa_mod.motivo_ultima_falha()


def test_obter_relatorios_sitemap_malformado_retorna_none():
    with patch.object(boa_mod.requests, "get", return_value=_resp(200, content=b"nao e xml")):
        resultado = boa_mod.obter_relatorios()
    assert resultado is None
    assert "XML" in boa_mod.motivo_ultima_falha()


def test_obter_relatorios_excecao_de_rede_no_sitemap_registra_motivo():
    with patch.object(boa_mod.requests, "get", side_effect=ConnectionError("DNS falhou")):
        resultado = boa_mod.obter_relatorios()
    assert resultado is None
    assert "ConnectionError" in boa_mod.motivo_ultima_falha()


def test_obter_relatorios_todas_as_paginas_falham_retorna_none():
    with patch.object(boa_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [_resp(404) for _ in range(boa_mod._MAX_ITENS)]
        resultado = boa_mod.obter_relatorios()
    assert resultado is None
    assert "nenhuma página individual respondeu" in boa_mod.motivo_ultima_falha()


def test_obter_relatorios_1_pagina_falha_isolada_nao_derruba_as_outras():
    pagina_sem_titulo = "<html><head></head></html>"
    with patch.object(boa_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=pagina_sem_titulo),
        ] + [_resp(200, text=_ARTIGO) for _ in range(boa_mod._MAX_ITENS)]
        resultado = boa_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) >= 1


def test_obter_relatorios_respeita_robots_no_sitemap():
    with patch.object(boa_mod, "permitido", return_value=False):
        resultado = boa_mod.obter_relatorios()
    assert resultado is None
    assert "robots" in boa_mod.motivo_ultima_falha()


def test_obter_relatorios_limita_numero_de_paginas_buscadas():
    with patch.object(boa_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [
            _resp(200, text=_ARTIGO) for _ in range(50)
        ]
        boa_mod.obter_relatorios()
    assert mock_get.call_count <= 1 + boa_mod._MAX_ITENS


def test_testar_conexao_respeita_robots_txt():
    with patch.object(boa_mod, "permitido", return_value=False):
        ok, detalhe = boa_mod.testar_conexao()
    assert ok is False
    assert "robots" in detalhe


def test_testar_conexao_ok():
    with patch.object(boa_mod.requests, "get", return_value=_resp(200, content=_SITEMAP)):
        ok, detalhe = boa_mod.testar_conexao()
    assert ok is True
