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


def _feed(bozo=False, entries=None, bozo_exception=None):
    return SimpleNamespace(bozo=bozo, entries=entries or [], bozo_exception=bozo_exception)


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


def test_falha_com_excecao_de_rede_registra_motivo_especifico():
    """Achado real (producao, GitHub Actions run 38989522110): sem isso,
    uma falha total do feed aparecia so' como 'falhou apos Xs', sem
    distinguir erro de DNS/timeout de feed malformado - motivo_falha novo,
    mesmo padrao de genial.py/xp.py."""
    erro = ConnectionError("Name or service not known")
    with patch.object(lives_mod.feedparser, "parse", side_effect=[erro, erro]), \
         patch.object(lives_mod.time, "sleep"):
        resultado = lives_mod.obter_relatorios()
    assert resultado is None
    assert "Name or service not known" in lives_mod.motivo_ultima_falha()


def test_falha_com_feed_malformado_sem_excecao_registra_motivo_generico():
    with patch.object(lives_mod.feedparser, "parse", return_value=_feed(bozo=True, entries=[])), \
         patch.object(lives_mod.time, "sleep"):
        resultado = lives_mod.obter_relatorios()
    assert resultado is None
    assert "sem entradas validas" in lives_mod.motivo_ultima_falha()


def test_falha_imprime_o_erro_real_no_console(capsys):
    """Achado real (auditoria 2026-10-18): as falhas reais de producao
    encontradas no historico do GitHub Actions (runs 38832834568/
    38982985477/38989522110/39088619143, todas rapidas - 1.7 a 4.5s,
    nunca um travamento) nao tinham NENHUM detalhe visivel no log puro -
    motivo_ultima_falha() so' chega no Supabase via registrar_tentativa,
    sem acesso ao banco nao da pra saber se foi erro de rede ou resposta
    vazia. genial.py/xp.py JA imprimem cada tentativa (visivel nos Logs
    do GitHub Actions) - esse print() estava faltando so' aqui."""
    erro = ConnectionError("Name or service not known")
    with patch.object(lives_mod.feedparser, "parse", side_effect=[erro, erro]), \
         patch.object(lives_mod.time, "sleep"):
        lives_mod.obter_relatorios()
    saida = capsys.readouterr().out
    assert "Name or service not known" in saida
    assert saida.count("[genial_lives] tentativa") == 2


def test_sucesso_depois_de_uma_falha_anterior_limpa_o_motivo():
    with patch.object(lives_mod.feedparser, "parse", return_value=_feed(bozo=True, entries=[])), \
         patch.object(lives_mod.time, "sleep"):
        lives_mod.obter_relatorios()
    assert lives_mod.motivo_ultima_falha() is not None

    with patch.object(lives_mod.feedparser, "parse", return_value=_feed(entries=[_entry()])), \
         patch.object(lives_mod.time, "sleep"):
        resultado = lives_mod.obter_relatorios()
    assert resultado is not None
    assert lives_mod.motivo_ultima_falha() is None


def test_falha_de_parse_registra_status_tipo_e_redirecionamento():
    """Achado real 22/10: SAXParseException nas 2 tentativas sem nenhuma
    pista do que o YouTube devolveu - o motivo passa a trazer status HTTP,
    tipo de conteúdo e o host final quando houve redirecionamento."""
    feed = SimpleNamespace(bozo=True, entries=[], bozo_exception=Exception("not well-formed (invalid token)"),
                           status=200, headers={"content-type": "text/html; charset=utf-8"},
                           href="https://consent.youtube.com/m?continue=x")
    with patch.object(lives_mod.feedparser, "parse", return_value=feed), \
         patch.object(lives_mod.time, "sleep"):
        assert lives_mod.obter_relatorios() is None
    motivo = lives_mod.motivo_ultima_falha()
    assert "HTTP 200" in motivo and "text/html" in motivo and "consent.youtube.com" in motivo


def test_categoria_falha_sem_nenhuma_chamada_e_erro():
    assert lives_mod.categoria_ultima_falha() == "erro"


def test_categoria_falha_reconhece_bloqueio_404_do_endpoint_do_youtube():
    """Achado real 24/10: feed.get('/feeds/videos.xml') passou a devolver
    HTTP 404 (text/html, pagina de erro do Google) pro canal da Genial E
    pra 2 canais de controle sem nenhuma relacao com a Genial (Google
    Developers e o canal oficial do YouTube) - confirma bloqueio do
    endpoint inteiro pro IP de saida, nao o canal que mudou/sumiu."""
    feed = SimpleNamespace(bozo=True, entries=[], bozo_exception=Exception("not well-formed (invalid token)"),
                           status=404, headers={"content-type": "text/html; charset=UTF-8"}, href="")
    with patch.object(lives_mod.feedparser, "parse", return_value=feed), \
         patch.object(lives_mod.time, "sleep"):
        assert lives_mod.obter_relatorios() is None
    assert lives_mod.categoria_ultima_falha() == "bloqueio_externo_conhecido"


def test_categoria_falha_nao_reconhece_erro_diferente_ex_403():
    """Um sintoma DIFERENTE (ex: 403 em vez de 404, ou canal removido de
    outra forma) nao pode herdar a classificacao de bloqueio conhecido -
    só o sintoma exato ja confirmado conta, pra nunca mascarar uma falha
    realmente nova."""
    feed = SimpleNamespace(bozo=True, entries=[], bozo_exception=Exception("not well-formed (invalid token)"),
                           status=403, headers={"content-type": "text/html; charset=UTF-8"}, href="")
    with patch.object(lives_mod.feedparser, "parse", return_value=feed), \
         patch.object(lives_mod.time, "sleep"):
        assert lives_mod.obter_relatorios() is None
    assert lives_mod.categoria_ultima_falha() == "erro"


def test_categoria_falha_volta_a_erro_depois_de_sucesso():
    feed_bloqueio = SimpleNamespace(bozo=True, entries=[], bozo_exception=Exception("not well-formed (invalid token)"),
                                    status=404, headers={"content-type": "text/html; charset=UTF-8"}, href="")
    with patch.object(lives_mod.feedparser, "parse", return_value=feed_bloqueio), \
         patch.object(lives_mod.time, "sleep"):
        lives_mod.obter_relatorios()
    assert lives_mod.categoria_ultima_falha() == "bloqueio_externo_conhecido"

    with patch.object(lives_mod.feedparser, "parse", return_value=_feed(entries=[_entry()])), \
         patch.object(lives_mod.time, "sleep"):
        assert lives_mod.obter_relatorios() is not None
    assert lives_mod.categoria_ultima_falha() == "erro"
