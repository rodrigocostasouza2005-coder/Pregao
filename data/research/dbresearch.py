# -*- coding: utf-8 -*-
"""Coletor do Deutsche Bank Research Institute (conteúdo público,
publicado em dbresearch.com, seção "Research Institute").

Investigação real (12/11/2026, deste ambiente - rede disponível): o
research institucional completo do Deutsche Bank (cobertura de ações por
ativo, rating/preço-alvo, distribuído via DB Research/Autobahn) é
client-only - NUNCA coletado por este projeto. O banco também publica,
sem login, uma seção própria chamada "Research Institute"
(dbresearch.com/PROD/IE-PROD/<Tópico>__Research_Institute/<alias>.alias)
com conteúdo macro/temático real e atual, assinado por nomes reais do
research global do banco (ex: "Jim Reid on AI and bond vigilantes",
"CPI Reaction" - confirmado com a página real de Macro, itens de 11 e
12/11/2026). Este coletor NUNCA chama isso de "Deutsche Bank Research"
(nome reservado pro produto institucional pago) - usa "Deutsche Bank
Research Institute", nome real da própria seção do site.

robots.txt de www.dbresearch.com tem "User-agent: * / Allow: /" explícito
(só restringe paths técnicos como /MAIL/*, /REPO/*, /api/* - nenhum deles
usado aqui); o arquivo lista dezenas de user-agents de bot nomeados
(inclusive crawlers de IA, ex: ClaudeBot/GPTBot) com Disallow específico,
mas nenhum bate o User-Agent deste projeto - pelas regras padrão de
robots.txt, um agente sem correspondência nomeada cai no grupo "*", que
permite tudo aqui (confirmado com requisição real bem-sucedida deste
ambiente, sem nenhum bloqueio).

Sem sitemap.xml funcional (confirmado HTTP 404, página de erro "Seite
nicht gefunden"); a descoberta é direto pela página-índice do tópico
Macro (RI_MAC.alias), que lista os itens mais recentes num widget HTML
customizado (não é uma <table> nem ld+json) - cada item é um <article>
com blocos cuja CLASSE tem um prefixo hash que muda por requisição (ex:
"RWTAB17945201728400-date"), mas o SUFIXO é estável
("-date"/"-title"/"-attachment"/"-teaser") - a extração usa esse sufixo
via seletor CSS do BeautifulSoup (`[class$="-date"]` etc.), nunca o
prefixo hash. Data real em texto "November 12, 2026" (inglês, parseada
via datetime.strptime); sem data válida, o item é descartado (nunca
inventa).

Só a página de Macro (RI_MAC.alias) é coletada nesta rodada - as demais
páginas de tópico (Geopolitics, Germany, Corporate Landscape) usam o
MESMO widget e podem ser adicionadas depois sem mudar o parser, mas não
foram incluídas pra manter 1 única requisição por ciclo (diferente de
citi.py/nord.py: aqui a PRÓPRIA página-índice já traz título+data+link
de vários itens, sem precisar de 1 request por item)."""

import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from .base import HEADERS, permitido

LISTAGEM_URL = "https://www.dbresearch.com/PROD/IE-PROD/Macro__Research_Institute/RI_MAC.alias"
_NOME_CASA = "Deutsche Bank Research Institute"
_TIMEOUT = 15
_MAX_ITENS = 10
_TICKER = re.compile(r"\b([A-Z]{4}\d{1,2})\b")

_ultimo_motivo_falha = None


def motivo_ultima_falha() -> str | None:
    return _ultimo_motivo_falha


def _texto(el) -> str:
    return el.get_text(strip=True) if el is not None else ""


def _item(article) -> dict | None:
    """Metadado real extraído de 1 <article> da página de listagem (ver
    docstring do módulo) - None se faltar título/data/link válidos
    (nunca inventa)."""
    titulo_el = article.select_one('[class$="-title"] a')
    link_el = titulo_el or article.select_one('[class$="-attachment"] a')
    data_el = article.select_one('[class$="-date"]')
    if titulo_el is None or link_el is None or data_el is None:
        return None
    href = (link_el.get("href") or "").strip()
    titulo = _texto(titulo_el)
    if not href or not titulo:
        return None
    try:
        publicado = datetime.strptime(_texto(data_el), "%B %d, %Y")
    except ValueError:
        return None
    link = href if href.startswith("http") else f"https://www.dbresearch.com{href}"
    tickers = sorted(set(_TICKER.findall(titulo.upper())))
    return {
        "casa": _NOME_CASA,
        "titulo": titulo,
        "data": publicado.date().isoformat(),
        "publicado_em": publicado.date().isoformat(),
        "autor": "",
        "tipo": "ACOES" if tickers else "MACRO",
        "setor": "Macro",
        "tickers": tickers,
        "link": link,
    }


def testar_conexao(timeout: float = 5) -> tuple:
    """Só testa se a página de listagem responde - usado pelo painel
    DIAGNÓSTICO DE FONTES. Retorna (ok, detalhe)."""
    if not permitido(LISTAGEM_URL):
        return False, "bloqueado pelo robots.txt"
    try:
        r = requests.get(LISTAGEM_URL, headers=HEADERS, timeout=timeout)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    return True, f"OK ({len(r.content)} bytes)"


def parse_listagem(html: str) -> list | None:
    """Itens extraídos do HTML da página de listagem (ver docstring do
    módulo). None se não houver nenhum <article> reconhecido (página de
    erro/bloqueio/estrutura mudou); [] se houver <article>s mas nenhum
    com título/data/link válidos."""
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.find_all("article")[:_MAX_ITENS]
    if not articles:
        return None
    itens = []
    for article in articles:
        item = _item(article)
        if item:
            itens.append(item)
    return itens


def obter_relatorios() -> list | None:
    """Itens públicos recentes do Deutsche Bank Research Institute
    (seção Macro). None se a página de listagem falhar, não responder ou
    não tiver nenhum <article> reconhecido; [] se os <article>s
    encontrados não tiverem título/data/link válidos."""
    global _ultimo_motivo_falha
    if not permitido(LISTAGEM_URL):
        _ultimo_motivo_falha = "página de listagem bloqueada pelo robots.txt"
        return None
    try:
        r = requests.get(LISTAGEM_URL, headers=HEADERS, timeout=_TIMEOUT)
    except Exception as exc:
        _ultimo_motivo_falha = f"página de listagem indisponível: {type(exc).__name__}"
        print(f"[dbresearch] {_ultimo_motivo_falha}: {exc}")
        return None
    if r.status_code != 200:
        tipo = (r.headers.get("content-type") or "").split(";")[0]
        _ultimo_motivo_falha = f"página de listagem respondeu HTTP {r.status_code} ({tipo})"
        print(f"[dbresearch] {_ultimo_motivo_falha}")
        return None

    itens = parse_listagem(r.text)
    if itens is None:
        _ultimo_motivo_falha = "página de listagem sem nenhum <article> reconhecido"
        print(f"[dbresearch] {_ultimo_motivo_falha}")
        return None
    _ultimo_motivo_falha = None
    return itens
