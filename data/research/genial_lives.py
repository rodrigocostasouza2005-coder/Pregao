# -*- coding: utf-8 -*-
"""Lives/vídeos da Genial no YouTube (Morning Call, Resumo da Manhã,
Fechamento de Mercado, Podcast Genial Analisa, Estratégia em Ação,
Conversa com Zé Márcio, Reunião do Copom) - identificados pelo TÍTULO do
vídeo (não existe categoria estruturada no feed público do YouTube).

Sem API key: usa o feed RSS público do canal (funciona pra qualquer canal
do YouTube, sem autenticação - só devolve os ~15 vídeos mais recentes,
suficiente aqui: o gate de 30min do research já evita recoleta constante,
e o objetivo é pegar os programas do dia/semana, não um arquivo
histórico) + youtube_transcript_api pra legenda automática (gerada pelo
YouTube, existe pra todo vídeo testado do canal - ver decisão registrada
em PROGRESSO.md sobre a viabilidade confirmada com vídeos reais).

O resumo (Groq) NÃO é gerado na coleta - é gerado sob demanda, igual toda
outra casa de research (ver ui/research_tab.py:_linha_relatorio, botão
RESUMIR / resumo automático da watchlist). Este modulo so contribui o
`obter_relatorios` (metadados) e o `obter_texto_transcricao` (extrator de
texto que entra no lugar do "baixar a pagina" generico - ver CASAS em
data/research/__init__.py, mesmo mecanismo que xp.py usa pra XP).

ATENCAO - excecao deliberada a regra de robots.txt do projeto (2026-09-28,
pedido explicito do Rodrigo): o robots.txt do YouTube proibe
/feeds/videos.xml e /api/ pra bots genericos (User-agent: *). Toda outra
coleta do projeto respeita robots.txt via permitido() (data/research/
base.py) e fica desligada se o robots.txt proibir - aqui NAO: o feed é
lido direto, sem checar. Justificativa registrada: uso estritamente
pessoal e nao-comercial (mesmo User-Agent que já se declara assim),
volume de acesso equivalente a 1 usuario abrindo a aba de vez em quando
(gate de 30min do research, so ~15 videos mais recentes por chamada),
sem republicar nem redistribuir o conteudo. Nao generalizar esse padrao
pra outras fontes sem a mesma decisao explicita."""

import re
from datetime import datetime, timezone

import feedparser

# canal oficial da Genial Investimentos no YouTube (confirmado via busca +
# leitura do feed real em 2026-09-24 - "Genial Investimentos", descrição
# bate, videos do dia batem com o site) - se a Genial trocar de canal um
# dia, so' trocar esse ID, nada mais no projeto depende dele diretamente
_CHANNEL_ID = "UCYSOMA4Yx1CJvrdI8epLfnA"
_FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={_CHANNEL_ID}"

_NOME_CASA = "Genial (Lives)"

# ordem importa: checagens mais especificas primeiro. Heuristica sobre o
# TITULO do video (unico dado estruturado disponivel no feed publico) -
# pode classificar errado o "sub-tipo" do programa em casos ambiguos
# (titulos variam bastante, ex: "Resumo" sozinho vs "Resumo da Manha"),
# mas o titulo/link/data reais NUNCA sao alterados - so' o rotulo do
# programa e' uma inferencia. Videos que nao batem em nenhum padrao (Day
# Trade AO VIVO, #shorts, Quizz etc.) sao ignorados de proposito.
_PADROES_PROGRAMA = [
    (re.compile(r"copom"), "Reunião do Copom"),
    (re.compile(r"morning\s*call"), "Morning Call"),
    (re.compile(r"fechamento"), "Fechamento de Mercado"),
    (re.compile(r"estrategia\s*em\s*acao"), "Estratégia em Ação"),
    (re.compile(r"ze\s*marcio"), "Conversa com Zé Márcio"),
    (re.compile(r"genial\s*analisa"), "Podcast Genial Analisa"),
    (re.compile(r"resumo"), "Resumo da Manhã"),
]


def _sem_acento(texto: str) -> str:
    trocas = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüç", "aaaaaeeeeiiiiooooouuuuc")
    return texto.lower().translate(trocas)


def _identificar_programa(titulo: str) -> str | None:
    titulo_norm = _sem_acento(titulo)
    for padrao, rotulo in _PADROES_PROGRAMA:
        if padrao.search(titulo_norm):
            return rotulo
    return None


def _publicado_em_iso(entry) -> str | None:
    """Timestamp COMPLETO (ISO, UTC) de publicacao do video - usado so'
    pelo feed editorial do NEWS (fase 3) pra posicionar o Morning Call/
    lives cronologicamente ENTRE as noticias (ver
    ui/news_tab.py:_chave_ordenacao_live). 'data' (so' o dia, ja
    existente, usado pelo resto do projeto - radar, retencao, filtro por
    dia) continua exatamente igual, intocado. None se o feed nao trouxer
    o campo estruturado (nunca inventa hora)."""
    bruto = entry.get("published_parsed")
    if not bruto:
        return None
    return datetime(*bruto[:6], tzinfo=timezone.utc).isoformat()


def obter_relatorios() -> list | None:
    """Metadados dos vídeos recentes do canal que batem com algum
    programa conhecido (ver _PADROES_PROGRAMA). None se o feed falhar
    (canal indisponível/erro de rede) - lista vazia (não None) se o feed
    respondeu mas nenhum vídeo recente bateu com nenhum programa (normal
    em dias sem Copom/podcast, por exemplo). NÃO checa robots.txt (ver
    ATENÇÃO no topo do módulo - exceção deliberada, pedido explícito)."""
    try:
        feed = feedparser.parse(_FEED_URL)
    except Exception:
        return None
    if feed.bozo and not feed.entries:
        return None

    relatorios = []
    for entry in feed.entries:
        titulo = entry.get("title") or ""
        programa = _identificar_programa(titulo)
        if programa is None:
            continue
        video_id = entry.get("yt_videoid")
        publicado = entry.get("published") or ""
        relatorios.append({
            "casa": _NOME_CASA,
            "titulo": titulo,
            "data": publicado[:10] if publicado else "",
            "publicado_em": _publicado_em_iso(entry),
            "autor": programa,
            "tipo": "LIVE",
            "setor": "",
            "tickers": [],
            "link": f"https://www.youtube.com/watch?v={video_id}" if video_id else entry.get("link", ""),
        })
    return relatorios


def _extrair_video_id(link: str) -> str | None:
    m = re.search(r"[?&]v=([\w-]{11})", link)
    return m.group(1) if m else None


def obter_texto_transcricao(link: str) -> tuple:
    """Extrator de texto pro link de um video (usado no lugar do 'baixa a
    pagina publica' generico - ver CASAS['genial_lives']['extrator_texto']
    em data/research/__init__.py). Busca a legenda automatica em
    portugues gerada pelo proprio YouTube (nunca baixa audio/video, nao
    faz transcricao propria) e junta os segmentos num texto corrido.
    Retorna (texto, motivo_falha) - texto=None se o video nao tiver
    legenda em pt disponivel ou a lib falhar."""
    video_id = _extrair_video_id(link)
    if not video_id:
        return None, "link sem id de vídeo reconhecível"
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound, TranscriptsDisabled, VideoUnavailable,
        )
    except ImportError:
        return None, "biblioteca youtube-transcript-api não instalada"

    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=["pt", "pt-BR"])
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as e:
        return None, f"legenda indisponível: {type(e).__name__}"
    except Exception as e:
        return None, f"erro ao buscar legenda: {e}"

    texto = " ".join(seg.text for seg in transcript).strip()
    if len(texto) < 200:
        return None, "legenda muito curta (provavelmente vídeo sem fala relevante)"
    return texto, None


def testar_conexao() -> tuple:
    """So' testa se o feed do canal responde - usado pelo painel
    DIAGNOSTICO DE FONTES. Retorna (ok, detalhe)."""
    try:
        feed = feedparser.parse(_FEED_URL)
    except Exception as e:
        return False, f"erro: {e}"
    if feed.bozo and not feed.entries:
        return False, "feed não retornou entradas válidas"
    return True, f"OK ({len(feed.entries)} vídeos recentes no feed)"
