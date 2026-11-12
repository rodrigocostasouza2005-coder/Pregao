# -*- coding: utf-8 -*-
"""Testes de data/research/jpmorgan.py - mocka requests.get, nunca faz
chamada de rede. Fixtures reais capturadas em 11/11/2026:
- tests/fixtures/research/jpmorgan_sitemap_20261111.xml: recorte real de
  blocos <url> do sitemap verdadeiro (jpmorgan.com/US/en/sitemap.xml) -
  mistura 2 artigos de Global Research (devem bater o filtro) com a
  própria página-índice e uma página de outra seção de /insights (devem
  ser ignoradas).
- tests/fixtures/research/jpmorgan_panel_20261111.html: o bloco real
  <aside class="cmp-article-side-panel"> da página
  insights/global-research/current-events/us-midterms-markets (eyebrow/
  título/data/descrição reais, não inventados)."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.jpmorgan as jpm_mod

_FIXTURES = Path(__file__).parent / "fixtures" / "research"
_SITEMAP = (_FIXTURES / "jpmorgan_sitemap_20261111.xml").read_bytes()
_PAINEL_MIDTERMS = (_FIXTURES / "jpmorgan_panel_20261111.html").read_text(encoding="utf-8")


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
    with patch.object(jpm_mod, "permitido", return_value=True):
        yield


def test_candidatos_do_sitemap_filtra_so_global_research_com_slug():
    candidatos = jpm_mod._candidatos_do_sitemap(_SITEMAP)
    locs = [loc for _, loc in candidatos]
    assert "https://www.jpmorgan.com/insights/global-research/current-events/us-midterms-markets" in locs
    assert "https://www.jpmorgan.com/insights/global-research/global-bond-market-update" in locs
    # página-índice (sem slug depois de global-research/) nunca entra
    assert "https://www.jpmorgan.com/insights/global-research" not in locs
    # outras seções de /insights (sem o metadado usado aqui) ficam fora
    assert not any("insights/banking" in loc for loc in locs)


def test_candidatos_ordenados_por_lastmod_desc():
    candidatos = jpm_mod._candidatos_do_sitemap(_SITEMAP)
    lastmods = [lm for lm, _ in candidatos]
    assert lastmods == sorted(lastmods, reverse=True)


def test_item_le_eyebrow_titulo_e_data_do_painel_real():
    item = jpm_mod._item(
        _PAINEL_MIDTERMS,
        "https://www.jpmorgan.com/insights/global-research/current-events/us-midterms-markets",
    )
    assert item is not None
    assert "midterms" in item["titulo"].lower()
    assert item["data"] == "2026-11-06"
    assert item["setor"] == "Global Research"
    assert item["casa"] == "J.P. Morgan Global Research"
    assert item["tipo"] == "MACRO"
    assert item["link"] == "https://www.jpmorgan.com/insights/global-research/current-events/us-midterms-markets"


def test_item_sem_painel_devolve_none():
    assert jpm_mod._item("<html><body>sem nada</body></html>", "https://x/y") is None


def test_item_painel_sem_data_devolve_none():
    html = (
        '<aside class="cmp-article-side-panel-content">'
        '<p class="eyebrow">Global Research</p>'
        '<h1 class="title">Sem data aqui</h1>'
        "</aside>"
    )
    assert jpm_mod._item(html, "https://x/y") is None


def test_parse_data_en_reconhece_mes_por_extenso():
    assert jpm_mod._parse_data_en("November 06, 2026").isoformat() == "2026-11-06"
    assert jpm_mod._parse_data_en("texto sem data nenhuma") is None


def test_obter_relatorios_sucesso_fim_a_fim():
    with patch.object(jpm_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=_PAINEL_MIDTERMS),
            _resp(200, text=_PAINEL_MIDTERMS),
        ]
        resultado = jpm_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) == 2
    assert jpm_mod.motivo_ultima_falha() is None


def test_obter_relatorios_sitemap_sem_candidato_e_lista_vazia_nao_none():
    sitemap_vazio = (
        b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://www.jpmorgan.com/insights/global-research</loc></url>"
        b"</urlset>"
    )
    with patch.object(jpm_mod.requests, "get", return_value=_resp(200, content=sitemap_vazio)):
        resultado = jpm_mod.obter_relatorios()
    assert resultado == []


def test_obter_relatorios_sitemap_http_erro_retorna_none_com_motivo():
    with patch.object(jpm_mod.requests, "get", return_value=_resp(503)):
        resultado = jpm_mod.obter_relatorios()
    assert resultado is None
    assert "503" in jpm_mod.motivo_ultima_falha()


def test_obter_relatorios_sitemap_malformado_retorna_none():
    with patch.object(jpm_mod.requests, "get", return_value=_resp(200, content=b"nao e xml")):
        resultado = jpm_mod.obter_relatorios()
    assert resultado is None
    assert "XML" in jpm_mod.motivo_ultima_falha()


def test_obter_relatorios_excecao_de_rede_no_sitemap_registra_motivo():
    with patch.object(jpm_mod.requests, "get", side_effect=ConnectionError("DNS falhou")):
        resultado = jpm_mod.obter_relatorios()
    assert resultado is None
    assert "ConnectionError" in jpm_mod.motivo_ultima_falha()


def test_obter_relatorios_todas_as_paginas_falham_retorna_none():
    with patch.object(jpm_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [_resp(404) for _ in range(jpm_mod._MAX_ITENS)]
        resultado = jpm_mod.obter_relatorios()
    assert resultado is None
    assert "nenhuma página individual respondeu" in jpm_mod.motivo_ultima_falha()


def test_obter_relatorios_1_pagina_falha_isolada_nao_derruba_as_outras():
    pagina_sem_painel = "<html><body>bloqueio</body></html>"
    with patch.object(jpm_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=pagina_sem_painel),
        ] + [_resp(200, text=_PAINEL_MIDTERMS) for _ in range(jpm_mod._MAX_ITENS)]
        resultado = jpm_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) >= 1


def test_obter_relatorios_respeita_robots_no_sitemap():
    with patch.object(jpm_mod, "permitido", return_value=False):
        resultado = jpm_mod.obter_relatorios()
    assert resultado is None
    assert "robots" in jpm_mod.motivo_ultima_falha()


def test_obter_relatorios_limita_numero_de_paginas_buscadas():
    with patch.object(jpm_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [
            _resp(200, text=_PAINEL_MIDTERMS) for _ in range(50)
        ]
        jpm_mod.obter_relatorios()
    assert mock_get.call_count <= 1 + jpm_mod._MAX_ITENS


def test_testar_conexao_respeita_robots_txt():
    with patch.object(jpm_mod, "permitido", return_value=False):
        ok, detalhe = jpm_mod.testar_conexao()
    assert ok is False
    assert "robots" in detalhe


def test_testar_conexao_ok():
    with patch.object(jpm_mod.requests, "get", return_value=_resp(200, content=_SITEMAP)):
        ok, detalhe = jpm_mod.testar_conexao()
    assert ok is True
