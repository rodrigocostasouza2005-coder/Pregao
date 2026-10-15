# -*- coding: utf-8 -*-
"""Testes de data/research/genial_lives.py (feed RSS do YouTube) - mocka
feedparser.parse, nunca faz chamada de rede.

Regressao 2026-10-15: feedparser nunca lanca excecao por falha de rede
(absorve internamente e marca feed.bozo=True com entries=[]) - sem
retry, uma instabilidade transitoria de conexao parecia identica a
"feed malformado de verdade" e descartava a coleta inteira na 1a
tentativa."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.genial_lives as lives_mod


def _feed(bozo=False, entries=None):
    return SimpleNamespace(bozo=bozo, entries=entries or [])


def _entry(titulo="15/10 Morning Call Genial", video_id="abc123", publicado="2026-10-15T10:00:00Z"):
    return {"title": titulo, "yt_videoid": video_id, "published": publicado, "published_parsed": None}


def test_sucesso_na_primeira_tentativa_nao_tenta_de_novo():
    with patch.object(lives_mod.feedparser, "parse", return_value=_feed(entries=[_entry()])) as mock_parse, \
         patch.object(lives_mod.time, "sleep") as mock_sleep:
        resultado = lives_mod.obter_relatorios()
    assert resultado is not None and len(resultado) == 1
    assert mock_parse.call_count == 1
    assert not mock_sleep.called


def test_falha_transitoria_se_recupera_na_segunda_tentativa():
    with patch.object(lives_mod.feedparser, "parse", side_effect=[_feed(bozo=True, entries=[]), _feed(entries=[_entry()])]) as mock_parse, \
         patch.object(lives_mod.time, "sleep") as mock_sleep:
        resultado = lives_mod.obter_relatorios()
    assert resultado is not None and len(resultado) == 1
    assert mock_parse.call_count == 2
    assert mock_sleep.called


def test_falha_nas_duas_tentativas_retorna_none():
    with patch.object(lives_mod.feedparser, "parse", return_value=_feed(bozo=True, entries=[])), \
         patch.object(lives_mod.time, "sleep"):
        resultado = lives_mod.obter_relatorios()
    assert resultado is None


def test_excecao_na_primeira_tentativa_tambem_tenta_de_novo():
    with patch.object(lives_mod.feedparser, "parse", side_effect=[Exception("boom"), _feed(entries=[_entry()])]), \
         patch.object(lives_mod.time, "sleep"):
        resultado = lives_mod.obter_relatorios()
    assert resultado is not None and len(resultado) == 1


def test_feed_respondeu_sem_video_de_programa_conhecido_e_lista_vazia_nao_none():
    with patch.object(lives_mod.feedparser, "parse", return_value=_feed(entries=[_entry(titulo="video qualquer sem programa")])), \
         patch.object(lives_mod.time, "sleep"):
        resultado = lives_mod.obter_relatorios()
    assert resultado == []
