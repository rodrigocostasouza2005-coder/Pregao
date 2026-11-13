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


# ============================================================
# obter_texto_transcricao / _formatar_timestamp (missao noturna
# 2026-11-12/13, frente LIVES GENIAL - sem nenhuma cobertura de teste
# antes desta auditoria). Mocka youtube_transcript_api.YouTubeTranscriptApi
# .fetch diretamente (classe real da lib instalada, so' o metodo de rede
# e' mockado) - segmentos sao SimpleNamespace(text, start, duration),
# mesmo shape de FetchedTranscriptSnippet (ver youtube_transcript_api).
# ============================================================

def _segmento(texto, start, duration=2.0):
    return SimpleNamespace(text=texto, start=start, duration=duration)


def test_timestamp_formata_mm_ss_abaixo_de_1_hora():
    assert lives_mod._formatar_timestamp(0) == "00:00"
    assert lives_mod._formatar_timestamp(65) == "01:05"
    assert lives_mod._formatar_timestamp(3599) == "59:59"


def test_timestamp_formata_hh_mm_ss_a_partir_de_1_hora():
    assert lives_mod._formatar_timestamp(3600) == "01:00:00"
    assert lives_mod._formatar_timestamp(3725) == "01:02:05"


def test_transcricao_sem_video_id_no_link_retorna_none():
    texto, motivo = lives_mod.obter_texto_transcricao("https://www.youtube.com/watch?v=")
    assert texto is None
    assert "sem id de vídeo" in motivo


def test_transcricao_legenda_indisponivel_retorna_motivo_sem_quebrar():
    from youtube_transcript_api._errors import TranscriptsDisabled

    with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch",
               side_effect=TranscriptsDisabled("abc12345678")):
        texto, motivo = lives_mod.obter_texto_transcricao("https://www.youtube.com/watch?v=abc12345678")
    assert texto is None
    assert "legenda indisponível" in motivo


def test_transcricao_erro_generico_na_busca_nao_quebra():
    with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch", side_effect=RuntimeError("timeout")):
        texto, motivo = lives_mod.obter_texto_transcricao("https://www.youtube.com/watch?v=abc12345678")
    assert texto is None
    assert "erro ao buscar legenda" in motivo


def test_transcricao_muito_curta_retorna_none_mesmo_com_varios_segmentos_vazios():
    segmentos = [_segmento("", 0.0), _segmento("oi", 1.0), _segmento("", 2.0), _segmento("tudo bem", 3.0)]
    with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch", return_value=segmentos):
        texto, motivo = lives_mod.obter_texto_transcricao("https://www.youtube.com/watch?v=abc12345678")
    assert texto is None
    assert "muito curta" in motivo


def test_transcricao_boa_junta_segmentos_e_insere_marcador_a_cada_60s():
    fala_longa = "palavra " * 40  # >200 chars de fala real, ultrapassa o limiar minimo
    segmentos = [
        _segmento(fala_longa, 0.0),
        _segmento("inicio do segundo minuto", 61.0),
        _segmento("ainda dentro do mesmo minuto", 90.0),
        _segmento("terceiro minuto comecando", 125.0),
    ]
    with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch", return_value=segmentos):
        texto, motivo = lives_mod.obter_texto_transcricao("https://www.youtube.com/watch?v=abc12345678")
    assert motivo is None
    assert texto is not None
    assert "[00:00]" in texto
    assert "[01:01]" in texto  # 61s cruza o limiar de 60s -> novo marcador
    assert "[02:05]" in texto  # 125s cruza o limiar de 2x60s -> novo marcador
    # 90s NAO cruza um novo limiar de 60s em relacao ao marcador anterior (61s) -
    # soh' 1 marcador por minuto de conteudo, nao por segmento
    assert texto.count("[01:01]") == 1 and "[01:30]" not in texto
    assert "ainda dentro do mesmo minuto" in texto


def test_transcricao_ignora_segmentos_vazios_mas_preserva_os_com_texto():
    fala_longa = "conteudo real da live " * 15
    segmentos = [_segmento(fala_longa, 0.0), _segmento("", 30.0), _segmento("   ", 45.0)]
    with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch", return_value=segmentos):
        texto, motivo = lives_mod.obter_texto_transcricao("https://www.youtube.com/watch?v=abc12345678")
    assert motivo is None
    # so' 1 marcador (todo o conteudo real esta no 1o segmento, em t=0) -
    # segmentos vazios/so'-espaco nunca geram marcador nem texto proprio
    assert texto.count("[00:00]") == 1
