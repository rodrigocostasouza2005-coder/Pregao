# -*- coding: utf-8 -*-
"""Coletor da Monte Bravo (montebravo.com.br) - análises de empresas e
carta mensal publicadas no blog oficial, lidas pelo feed RSS público do
WordPress (https://www.montebravo.com.br/feed/).

Sondagem real (22/10/2026 19:11 UTC, runner do GitHub Actions - o sandbox
de desenvolvimento não tem rede para o site): robots.txt "User-agent: * /
Disallow:" (tudo permitido), HTTP 200 application/rss+xml, 10 itens, o
mais recente "Monte Bravo Analisa — Resultado WEG 3T26" (22/10/2026, com
recomendação e preço-alvo). Na mesma sondagem, os feeds de Itaú, Safra,
Rico e Ativa deram 403, Ágora/Inter 404, BB Investalk devolveu HTML em vez
de feed e Toro só tem conteúdo educativo de trading (ver
docs/research-fontes-20261022.md).

O feed mistura research com sala de imprensa e eventos: só entram itens
publicados na seção /blog/analise/ do site OU com categoria de análise /
carta mensal (filtro em _eh_research). Data vem do pubDate do feed
(convertida para Brasília); item sem data é descartado - nunca inventa
data. Link canônico sem parâmetros de rastreamento; dedup por link."""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo

import feedparser
import requests

from .base import HEADERS, permitido

FEED_URL = "https://www.montebravo.com.br/feed/"
_NOME_CASA = "Monte Bravo"
_TZ_SP = ZoneInfo("America/Sao_Paulo")
_TIMEOUT = 15
_TICKER = re.compile(r"\b([A-Z]{4}(?:3|4|5|6|11))\b")
_CATEGORIAS_RESEARCH = ("analise", "carta mensal")

_ultimo_motivo_falha = None


def motivo_ultima_falha() -> str | None:
    return _ultimo_motivo_falha


def _sem_acento(texto: str) -> str:
    trocas = str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc")
    return (texto or "").lower().translate(trocas)


def _link_canonico(link: str) -> str:
    partes = urlparse((link or "").strip())
    return urlunparse((partes.scheme, partes.netloc.lower(), partes.path, "", "", ""))


def _eh_research(entry) -> bool:
    caminho = urlparse(entry.get("link") or "").path
    if caminho.startswith("/blog/analise/"):
        return True
    categorias = [_sem_acento(t.get("term")) for t in entry.get("tags") or []]
    return any(c.startswith(alvo) for c in categorias for alvo in _CATEGORIAS_RESEARCH)


def _publicado_utc(entry) -> datetime | None:
    bruto = entry.get("published_parsed")
    return datetime(*bruto[:6], tzinfo=timezone.utc) if bruto else None


def _item(entry) -> dict | None:
    titulo = (entry.get("title") or "").strip()
    link = _link_canonico(entry.get("link"))
    publicado = _publicado_utc(entry)
    if not titulo or not link.startswith("https://www.montebravo.com.br/") or publicado is None:
        return None
    corpo = " ".join(c.get("value") or "" for c in entry.get("content") or [])
    texto = f"{titulo} {entry.get('summary') or ''} {corpo}"
    tickers = sorted(set(_TICKER.findall(texto)))
    categorias = [t.get("term") for t in entry.get("tags") or [] if t.get("term")]
    return {
        "casa": _NOME_CASA,
        "titulo": titulo,
        "data": publicado.astimezone(_TZ_SP).strftime("%Y-%m-%d"),
        "publicado_em": publicado.isoformat(),
        "autor": (entry.get("author") or _NOME_CASA).strip(),
        "tipo": "ACOES" if tickers or "empresas" in _sem_acento(" ".join(categorias)) else "MACRO",
        "setor": categorias[0] if categorias else "",
        "tickers": tickers,
        "link": link,
    }


def parse_feed(conteudo: bytes) -> list | None:
    """Itens de research do feed (formato comum das casas). None se o
    conteúdo não for um feed RSS válido (página de erro/bloqueio/HTML)."""
    feed = feedparser.parse(conteudo)
    if not feed.entries and (feed.bozo or not feed.feed.get("title")):
        return None
    vistos, itens = set(), []
    for entry in feed.entries:
        try:
            if not _eh_research(entry):
                continue
            item = _item(entry)
        except Exception:
            continue
        if item and item["link"] not in vistos:
            vistos.add(item["link"])
            itens.append(item)
    return itens


def obter_relatorios() -> list | None:
    """Análises recentes da Monte Bravo. None se o feed falhar (rede, HTTP,
    conteúdo que não é feed); [] se o feed respondeu sem nenhum item de
    research (só imprensa/eventos)."""
    global _ultimo_motivo_falha
    if not permitido(FEED_URL):
        _ultimo_motivo_falha = "bloqueado pelo robots.txt"
        return None
    try:
        r = requests.get(FEED_URL, headers=HEADERS, timeout=_TIMEOUT)
    except Exception as exc:
        _ultimo_motivo_falha = f"feed indisponível: {type(exc).__name__}"
        print(f"[montebravo] {_ultimo_motivo_falha}: {exc}")
        return None
    tipo = (r.headers.get("content-type") or "").split(";")[0]
    if r.status_code != 200:
        _ultimo_motivo_falha = f"feed respondeu HTTP {r.status_code} ({tipo})"
        print(f"[montebravo] {_ultimo_motivo_falha}")
        return None
    itens = parse_feed(r.content)
    if itens is None:
        _ultimo_motivo_falha = f"resposta não é um feed RSS válido ({tipo})"
        print(f"[montebravo] {_ultimo_motivo_falha}")
        return None
    _ultimo_motivo_falha = None
    return itens
