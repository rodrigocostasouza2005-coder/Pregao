# -*- coding: utf-8 -*-
"""Testes de data/research/nord.py - mocka requests.get, nunca faz
chamada de rede. Fixtures reais capturadas em 24/10/2026:
- tests/fixtures/research/nord_sitemap_20261024.xml: recorte real de
  blocos <url> do sitemap verdadeiro (nordinvestimentos.com.br/blog/
  sitemap.xml, 1.17MB completo) - mistura posts que devem bater o filtro
  (ticker B3 + "resultado(s)" no slug) com os que devem ser ignorados
  (tag/autor, web-stories, "vale a pena" sem resultado).
- tests/fixtures/research/nord_post_petr4_20261024.html: página real do
  post "petrobras-petr4-resultados-1t26", com o bloco ld+json real que
  o módulo lê (headline/datePublished/author/url)."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.nord as nord_mod

_FIXTURES = Path(__file__).parent / "fixtures" / "research"
_SITEMAP = (_FIXTURES / "nord_sitemap_20261024.xml").read_bytes()
_POST_PETR4 = (_FIXTURES / "nord_post_petr4_20261024.html").read_text(encoding="utf-8")


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
    with patch.object(nord_mod, "permitido", return_value=True):
        yield


def test_candidatos_do_sitemap_filtra_so_ticker_mais_resultado():
    candidatos = nord_mod._candidatos_do_sitemap(_SITEMAP)
    locs = [loc for _, loc in candidatos]
    assert "https://www.nordinvestimentos.com.br/blog/petrobras-petr4-resultados-1t26/" in locs
    assert "https://www.nordinvestimentos.com.br/blog/itau-itub3-itub4-resultados-3t25/" in locs
    # paginas estaticas/educacionais NUNCA entram, mesmo tendo ticker no slug
    assert not any("vale-a-pena-investir-pine4" in loc for loc in locs)
    assert not any("web-stories" in loc for loc in locs)
    assert not any("/tags/" in loc or "/autores/" in loc or "/videos/" in loc for loc in locs)


def test_candidatos_ordenados_por_lastmod_desc():
    candidatos = nord_mod._candidatos_do_sitemap(_SITEMAP)
    lastmods = [lm for lm, _ in candidatos]
    assert lastmods == sorted(lastmods, reverse=True)


def test_candidatos_extrai_dois_tickers_de_slug_multi_empresa():
    candidatos = nord_mod._candidatos_do_sitemap(_SITEMAP)
    locs = [loc for _, loc in candidatos]
    assert "https://www.nordinvestimentos.com.br/blog/petrobras-petr3-petr4-resultado-4t25/" in locs


def test_item_le_headline_data_autor_e_tickers_do_ld_json_real():
    item = nord_mod._item(_POST_PETR4, "https://www.nordinvestimentos.com.br/blog/petrobras-petr4-resultados-1t26/")
    assert item is not None
    assert "Petrobras" in item["titulo"]
    assert item["data"] == "2026-05-12"
    assert item["publicado_em"].startswith("2026-05-12T10:04:00")
    assert item["autor"] == "Fabiano Vaz"
    assert item["tickers"] == ["PETR4"]
    assert item["tipo"] == "ACOES"
    assert item["casa"] == "Nord Research"
    assert item["link"] == "https://www.nordinvestimentos.com.br/blog/petrobras-petr4-resultados-1t26/"


def test_item_sem_bloco_ld_json_devolve_none():
    assert nord_mod._item("<html><body>sem nada</body></html>", "https://x/y") is None


def test_obter_relatorios_sucesso_fim_a_fim():
    with patch.object(nord_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=_POST_PETR4),
        ]
        resultado = nord_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) == 1
    assert resultado[0]["tickers"] == ["PETR4"]
    assert nord_mod.motivo_ultima_falha() is None


def test_obter_relatorios_sitemap_sem_candidato_e_lista_vazia_nao_none():
    sitemap_vazio = (
        b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://www.nordinvestimentos.com.br/blog/vale-a-pena-investir-pine4/</loc></url>"
        b"</urlset>"
    )
    with patch.object(nord_mod.requests, "get", return_value=_resp(200, content=sitemap_vazio)):
        resultado = nord_mod.obter_relatorios()
    assert resultado == []


def test_obter_relatorios_sitemap_http_erro_retorna_none_com_motivo():
    with patch.object(nord_mod.requests, "get", return_value=_resp(503)):
        resultado = nord_mod.obter_relatorios()
    assert resultado is None
    assert "503" in nord_mod.motivo_ultima_falha()


def test_obter_relatorios_sitemap_malformado_retorna_none():
    with patch.object(nord_mod.requests, "get", return_value=_resp(200, content=b"nao e xml")):
        resultado = nord_mod.obter_relatorios()
    assert resultado is None
    assert "XML" in nord_mod.motivo_ultima_falha()


def test_obter_relatorios_excecao_de_rede_no_sitemap_registra_motivo():
    """Mesmo padrao de montebravo.py: o motivo guardado traz so' o tipo
    da excecao (a mensagem completa so' vai pro print(), nao pro motivo
    persistido - ver docstring de motivo_ultima_falha)."""
    with patch.object(nord_mod.requests, "get", side_effect=ConnectionError("DNS falhou")):
        resultado = nord_mod.obter_relatorios()
    assert resultado is None
    assert "ConnectionError" in nord_mod.motivo_ultima_falha()


def test_obter_relatorios_todos_os_posts_falham_retorna_none():
    with patch.object(nord_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [_resp(404) for _ in range(nord_mod._MAX_ITENS)]
        resultado = nord_mod.obter_relatorios()
    assert resultado is None
    assert "nenhuma página individual respondeu" in nord_mod.motivo_ultima_falha()


def test_obter_relatorios_1_post_falha_isolado_nao_derruba_os_outros():
    post_sem_ld_json = "<html><body>bloqueio</body></html>"
    with patch.object(nord_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP),
            _resp(200, text=post_sem_ld_json),
        ] + [_resp(200, text=_POST_PETR4) for _ in range(nord_mod._MAX_ITENS)]
        resultado = nord_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) >= 1


def test_obter_relatorios_respeita_robots_no_sitemap():
    with patch.object(nord_mod, "permitido", return_value=False):
        resultado = nord_mod.obter_relatorios()
    assert resultado is None
    assert "robots" in nord_mod.motivo_ultima_falha()


def test_obter_relatorios_limita_numero_de_posts_buscados():
    with patch.object(nord_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP)] + [
            _resp(200, text=_POST_PETR4) for _ in range(50)
        ]
        nord_mod.obter_relatorios()
    # 1 chamada pro sitemap + no maximo _MAX_ITENS chamadas de post
    assert mock_get.call_count <= 1 + nord_mod._MAX_ITENS
