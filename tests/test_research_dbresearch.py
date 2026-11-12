# -*- coding: utf-8 -*-
"""Testes de data/research/dbresearch.py - mocka requests.get, nunca faz
chamada de rede. Fixture real capturada em 12/11/2026:
- dbresearch_ri_mac_20261112.html: 3 blocos <article> reais da página de
  listagem (dbresearch.com/PROD/IE-PROD/Macro__Research_Institute/
  RI_MAC.alias), copiados verbatim da resposta real (inclui o prefixo de
  classe hash real "RWTAB...", confirmando que o parser não depende
  dele)."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.dbresearch as db_mod

_FIXTURES = Path(__file__).parent / "fixtures" / "research"
_LISTAGEM = (_FIXTURES / "dbresearch_ri_mac_20261112.html").read_text(encoding="utf-8")


def _resp(status_code=200, content=b"", text="", headers=None):
    class _R:
        pass
    r = _R()
    r.status_code = status_code
    r.content = content
    r.text = text
    r.headers = headers or {"content-type": "text/html"}
    return r


@pytest.fixture(autouse=True)
def _sem_robots_check():
    with patch.object(db_mod, "permitido", return_value=True):
        yield


def test_parse_listagem_le_titulo_data_e_link_reais():
    itens = db_mod.parse_listagem(_LISTAGEM)
    assert itens is not None
    assert len(itens) == 3
    primeiro = itens[0]
    assert primeiro["titulo"] == "Sea change: the market implications of the threat to the maritime commons"
    assert primeiro["data"] == "2026-11-12"
    assert primeiro["casa"] == "Deutsche Bank Research Institute"
    assert primeiro["link"] == (
        "https://www.dbresearch.com/PROD/IE-PROD/PROD0000000000658795/"
        "Sea_change%3A_the_market_implications_of_the_threat_.xhtml"
    )
    assert primeiro["tipo"] == "MACRO"
    datas = [i["data"] for i in itens]
    assert datas == ["2026-11-12", "2026-11-11", "2026-11-11"]


def test_parse_listagem_nao_depende_do_prefixo_hash_da_classe():
    # troca o prefixo hash real por outro valor - o parser usa só o
    # sufixo ("-date"/"-title"/"-attachment"), nunca o prefixo
    trocado = _LISTAGEM.replace("RWTAB17945203898620", "RWTAB99999999999999")
    itens = db_mod.parse_listagem(trocado)
    assert len(itens) == 3


def test_parse_listagem_sem_article_devolve_none():
    assert db_mod.parse_listagem("<html><body>sem nada aqui</body></html>") is None


def test_parse_listagem_article_sem_data_valida_e_descartado():
    html = '<article><div class="X-title"><a href="/y">Titulo</a></div><div class="X-date">data invalida</div></article>'
    assert db_mod.parse_listagem(html) == []


def test_obter_relatorios_sucesso():
    with patch.object(db_mod.requests, "get", return_value=_resp(200, text=_LISTAGEM)):
        resultado = db_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) == 3
    assert db_mod.motivo_ultima_falha() is None


def test_obter_relatorios_http_erro_retorna_none_com_motivo():
    with patch.object(db_mod.requests, "get", return_value=_resp(404)):
        resultado = db_mod.obter_relatorios()
    assert resultado is None
    assert "404" in db_mod.motivo_ultima_falha()


def test_obter_relatorios_pagina_sem_article_retorna_none():
    with patch.object(db_mod.requests, "get", return_value=_resp(200, text="<html><body>vazio</body></html>")):
        resultado = db_mod.obter_relatorios()
    assert resultado is None
    assert "article" in db_mod.motivo_ultima_falha()


def test_obter_relatorios_excecao_de_rede_registra_motivo():
    with patch.object(db_mod.requests, "get", side_effect=ConnectionError("DNS falhou")):
        resultado = db_mod.obter_relatorios()
    assert resultado is None
    assert "ConnectionError" in db_mod.motivo_ultima_falha()


def test_obter_relatorios_respeita_robots_txt():
    with patch.object(db_mod, "permitido", return_value=False):
        resultado = db_mod.obter_relatorios()
    assert resultado is None
    assert "robots" in db_mod.motivo_ultima_falha()


def test_testar_conexao_respeita_robots_txt():
    with patch.object(db_mod, "permitido", return_value=False):
        ok, detalhe = db_mod.testar_conexao()
    assert ok is False
    assert "robots" in detalhe


def test_testar_conexao_ok():
    with patch.object(db_mod.requests, "get", return_value=_resp(200, content=_LISTAGEM.encode("utf-8"))):
        ok, detalhe = db_mod.testar_conexao()
    assert ok is True
