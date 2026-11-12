# -*- coding: utf-8 -*-
"""Testes de data/research/jefferies.py - mocka requests.get, nunca faz
chamada de rede. Fixtures reais capturadas em 12/11/2026:
- jefferies_sitemap_20261112.xml: recorte real de <url> do
  post-sitemap.xml verdadeiro - 2 itens sob /insights/ (devem bater o
  filtro) e 1 item da home (jefferies.com/, página-sitemap.xml, deve ser
  ignorado).
- jefferies_article_20261112.html: os blocos ld+json reais (Article no
  @graph + NewsArticle avulso) da página
  insights/markets/whats-driving-healthcare-dealmaking-right-now/."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.jefferies as jf_mod

_FIXTURES = Path(__file__).parent / "fixtures" / "research"
_SITEMAP = (_FIXTURES / "jefferies_sitemap_20261112.xml").read_bytes()
_ARTIGO = (_FIXTURES / "jefferies_article_20261112.html").read_text(encoding="utf-8")


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
    with patch.object(jf_mod, "permitido", return_value=True):
        yield


def test_candidatos_do_sitemap_filtra_so_insights_exclui_home():
    candidatos = jf_mod._candidatos_do_sitemap(_SITEMAP)
    locs = [loc for _, loc in candidatos]
    assert "https://www.jefferies.com/insights/markets/can-startups-outsmart-big-tech-in-the-ai-race/" in locs
    assert "https://www.jefferies.com/insights/markets/strategic-focus-and-spending-continues-growing-in-the-office-of-the-cfo/" in locs
    assert "https://www.jefferies.com/" not in locs
    assert len(candidatos) == 2


def test_item_le_headline_autor_e_setor_do_ld_json_real():
    item = jf_mod._item(
        _ARTIGO, "https://www.jefferies.com/insights/markets/whats-driving-healthcare-dealmaking-right-now/",
    )
    assert item is not None
    assert "Healthcare Dealmaking" in item["titulo"]
    assert item["data"] == "2026-11-10"
    assert item["publicado_em"].startswith("2026-11-10T16:28:06")
    assert item["casa"] == "Jefferies Insights"
    assert item["autor"] == "amarx"
    assert item["setor"] == "Markets"
    assert item["tipo"] == "MACRO"


def test_item_sem_bloco_ld_json_devolve_none():
    assert jf_mod._item("<html><body>sem nada</body></html>", "https://x/y") is None


def test_item_ld_json_sem_no_de_artigo_devolve_none():
    html = (
        '<script type="application/ld+json">'
        '{"@graph":[{"@type":"Organization","name":"Jefferies"}]}'
        "</script>"
    )
    assert jf_mod._item(html, "https://x/y") is None


def test_obter_relatorios_sucesso_fim_a_fim():
    with patch.object(jf_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=_ARTIGO),
            _resp(200, text=_ARTIGO),
        ]
        resultado = jf_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) == 2
    assert jf_mod.motivo_ultima_falha() is None


def test_obter_relatorios_sitemap_sem_candidato_e_lista_vazia_nao_none():
    sitemap_vazio = (
        b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://www.jefferies.com/</loc></url>"
        b"</urlset>"
    )
    with patch.object(jf_mod.requests, "get", return_value=_resp(200, content=sitemap_vazio)):
        resultado = jf_mod.obter_relatorios()
    assert resultado == []


def test_obter_relatorios_sitemap_http_erro_retorna_none_com_motivo():
    with patch.object(jf_mod.requests, "get", return_value=_resp(503)):
        resultado = jf_mod.obter_relatorios()
    assert resultado is None
    assert "503" in jf_mod.motivo_ultima_falha()


def test_obter_relatorios_sitemap_malformado_retorna_none():
    with patch.object(jf_mod.requests, "get", return_value=_resp(200, content=b"nao e xml")):
        resultado = jf_mod.obter_relatorios()
    assert resultado is None
    assert "XML" in jf_mod.motivo_ultima_falha()


def test_obter_relatorios_excecao_de_rede_no_sitemap_registra_motivo():
    with patch.object(jf_mod.requests, "get", side_effect=ConnectionError("DNS falhou")):
        resultado = jf_mod.obter_relatorios()
    assert resultado is None
    assert "ConnectionError" in jf_mod.motivo_ultima_falha()


def test_obter_relatorios_todas_as_paginas_falham_retorna_none():
    with patch.object(jf_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [_resp(404) for _ in range(jf_mod._MAX_ITENS)]
        resultado = jf_mod.obter_relatorios()
    assert resultado is None
    assert "nenhuma página individual respondeu" in jf_mod.motivo_ultima_falha()


def test_obter_relatorios_1_pagina_falha_isolada_nao_derruba_as_outras():
    pagina_sem_ld_json = "<html><body>bloqueio</body></html>"
    with patch.object(jf_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=pagina_sem_ld_json),
        ] + [_resp(200, text=_ARTIGO) for _ in range(jf_mod._MAX_ITENS)]
        resultado = jf_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) >= 1


def test_obter_relatorios_respeita_robots_no_sitemap():
    with patch.object(jf_mod, "permitido", return_value=False):
        resultado = jf_mod.obter_relatorios()
    assert resultado is None
    assert "robots" in jf_mod.motivo_ultima_falha()


def test_obter_relatorios_limita_numero_de_paginas_buscadas():
    with patch.object(jf_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [
            _resp(200, text=_ARTIGO) for _ in range(50)
        ]
        jf_mod.obter_relatorios()
    assert mock_get.call_count <= 1 + jf_mod._MAX_ITENS


def test_testar_conexao_respeita_robots_txt():
    with patch.object(jf_mod, "permitido", return_value=False):
        ok, detalhe = jf_mod.testar_conexao()
    assert ok is False
    assert "robots" in detalhe


def test_testar_conexao_ok():
    with patch.object(jf_mod.requests, "get", return_value=_resp(200, content=_SITEMAP)):
        ok, detalhe = jf_mod.testar_conexao()
    assert ok is True
