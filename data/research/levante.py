# -*- coding: utf-8 -*-
"""Coletor da Levante Ideias de Investimentos (levanteideias.com.br) -
casa de research independente (CVM/APIMEC, analistas CNPI nomeados nos
relatórios), lida pelo feed RSS público do WordPress
(https://www.levanteideias.com.br/feed/).

Investigação real (12/11/2026, deste ambiente - rede disponível):
robots.txt "User-agent: * / Allow: /" (tudo permitido, com
Sitemap: declarado), HTTP 200 com corpo RSS 2.0 válido (apesar do
content-type do servidor vir como "text/html" em vez de
"application/rss+xml" - inconsistência do próprio servidor, não motivo
pra descartar: o corpo é XML real, confirmado parseável). Os itens reais
capturados têm ticker B3 na categoria (ex: RAIZ4, CSNA3, AZZA3) e/ou a
categoria "research"/"insideresearch"/"EECI" - e o `content:encoded` de
amostra real inclui o disclaimer formal de analista CNPI da "INSIDE
RESEARCH LTDA." (empresa do Grupo Levante), com nome e número de
registro do analista responsável - confirma que é research sell-side de
verdade, não apenas blog de notícias.

Filtra por ticker B3 OU por uma das categorias de research conhecidas
(_CATEGORIAS_RESEARCH) - item sem nenhum dos dois é mais provavelmente
conteúdo institucional/educacional, fica fora (mesmo princípio de
montebravo.py/nord.py: nunca assume que TODO item do blog é research).
Autor vem de `dc:creator` (campo real do feed, ex: "Mauricio Silva",
"Equipe Levante"); tickers extraídos das categorias (nunca do texto
livre, pra não confundir com menção incidental). Data vem do pubDate do
feed (preservada em UTC, igual ao campo `publicado_em`); item sem data é
descartado - nunca inventa data. Link canônico sem parâmetros de
rastreamento; dedup por link."""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

import feedparser
import requests

from .base import HEADERS, permitido

FEED_URL = "https://www.levanteideias.com.br/feed/"
_NOME_CASA = "Levante Ideias de Investimentos"
_TIMEOUT = 15
_TICKER = re.compile(r"^([A-Z]{4}\d{1,2})$")
_CATEGORIAS_RESEARCH = ("research", "insideresearch", "eeci", "e eu com isso")

_ultimo_motivo_falha = None


def motivo_ultima_falha() -> str | None:
    return _ultimo_motivo_falha


def _sem_acento(texto: str) -> str:
    trocas = str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc")
    return (texto or "").lower().translate(trocas)


def _link_canonico(link: str) -> str:
    partes = urlparse((link or "").strip())
    return urlunparse((partes.scheme, partes.netloc.lower(), partes.path, "", "", ""))


def _categorias(entry) -> list:
    return [(t.get("term") or "").strip() for t in entry.get("tags") or [] if t.get("term")]


def _tickers(categorias: list) -> list:
    return sorted({c.upper() for c in categorias if _TICKER.match(c.upper())})


def _eh_research(categorias: list, tickers: list) -> bool:
    if tickers:
        return True
    normalizadas = [_sem_acento(c) for c in categorias]
    return any(alvo in normalizadas for alvo in _CATEGORIAS_RESEARCH)


def _publicado_utc(entry) -> datetime | None:
    bruto = entry.get("published_parsed")
    return datetime(*bruto[:6], tzinfo=timezone.utc) if bruto else None


def _item(entry) -> dict | None:
    titulo = (entry.get("title") or "").strip()
    link = _link_canonico(entry.get("link"))
    publicado = _publicado_utc(entry)
    if not titulo or not link.startswith("https://levanteideias.com.br/") or publicado is None:
        return None
    categorias = _categorias(entry)
    tickers = _tickers(categorias)
    if not _eh_research(categorias, tickers):
        return None
    return {
        "casa": _NOME_CASA,
        "titulo": titulo,
        "data": publicado.date().isoformat(),
        "publicado_em": publicado.isoformat(),
        "autor": (entry.get("author") or "").strip(),
        "tipo": "ACOES" if tickers else "MACRO",
        "setor": "",
        "tickers": tickers,
        "link": link,
    }


def parse_feed(conteudo: bytes) -> list | None:
    """Itens de research do feed (formato comum das casas). None se o
    conteúdo não for um feed RSS válido (página de erro/bloqueio/HTML
    sem canal)."""
    feed = feedparser.parse(conteudo)
    if not feed.entries and (feed.bozo or not feed.feed.get("title")):
        return None
    vistos, itens = set(), []
    for entry in feed.entries:
        try:
            item = _item(entry)
        except Exception:
            continue
        if item and item["link"] not in vistos:
            vistos.add(item["link"])
            itens.append(item)
    return itens


def testar_conexao(timeout: float = 5) -> tuple:
    """Só testa se o feed responde - usado pelo painel DIAGNÓSTICO DE
    FONTES. Retorna (ok, detalhe)."""
    if not permitido(FEED_URL):
        return False, "bloqueado pelo robots.txt"
    try:
        r = requests.get(FEED_URL, headers=HEADERS, timeout=timeout)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    return True, f"OK ({len(r.content)} bytes)"


def obter_relatorios() -> list | None:
    """Análises recentes da Levante (research com ticker B3 ou tag de
    research conhecida). None se o feed falhar (rede, HTTP, conteúdo que
    não é feed); [] se o feed respondeu sem nenhum item de research (só
    conteúdo institucional/educacional)."""
    global _ultimo_motivo_falha
    if not permitido(FEED_URL):
        _ultimo_motivo_falha = "bloqueado pelo robots.txt"
        return None
    try:
        r = requests.get(FEED_URL, headers=HEADERS, timeout=_TIMEOUT)
    except Exception as exc:
        _ultimo_motivo_falha = f"feed indisponível: {type(exc).__name__}"
        print(f"[levante] {_ultimo_motivo_falha}: {exc}")
        return None
    tipo = (r.headers.get("content-type") or "").split(";")[0]
    if r.status_code != 200:
        _ultimo_motivo_falha = f"feed respondeu HTTP {r.status_code} ({tipo})"
        print(f"[levante] {_ultimo_motivo_falha}")
        return None
    itens = parse_feed(r.content)
    if itens is None:
        _ultimo_motivo_falha = f"resposta não é um feed RSS válido ({tipo})"
        print(f"[levante] {_ultimo_motivo_falha}")
        return None
    _ultimo_motivo_falha = None
    return itens
