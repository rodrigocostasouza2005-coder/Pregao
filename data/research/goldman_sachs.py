# -*- coding: utf-8 -*-
"""Coletor do Goldman Sachs Insights (conteúdo público, publicado em
goldmansachs.com/insights).

Investigação real (12/11/2026, deste ambiente - rede disponível): o
research institucional completo da Goldman Sachs (rating/preço-alvo por
ativo, distribuído via Goldman Sachs Marquee/GS Research) é client-only -
NUNCA coletado por este projeto. O banco também publica, sem login, um hub
editorial próprio ("Insights", goldmansachs.com/insights/articles) com
conteúdo macro/temático/setorial real e atual (confirmado com páginas
reais: "Why the ECB Is Unlikely to Keep Rates Higher Than 3%",
datePublished 2026-09-25, e outros itens de 2026-11-10/09/06 no sitemap) -
mais parecido com uma versão editorial/pública de análise de mercado do
que com cobertura formal de 1 ação (mesma distinção documentada pros
bancos globais adicionados em 11/11/2026 - ver docstring de
data/research/citi.py). Este coletor NUNCA chama isso de "Goldman Sachs
Research" por esse motivo.

robots.txt de www.goldmansachs.com permite tudo relevante aqui
("Allow: /" cobre /insights/ e /sitemap.xml). O sitemap raiz
(goldmansachs.com/sitemap.xml) é um ÍNDICE (<sitemapindex>) com 1 única
entrada real, sitemap-1.xml (~1.5MB, confirmado com a resposta real deste
ambiente) - este módulo segue esse índice (não assume a URL fixa do
sitemap filho, pra não quebrar se o site trocar o nome do arquivo). Filtra
só o path "/insights/articles/" (exclui ~3700 outras ocorrências de
"insights" no sitemap completo, quase todas de
"/community-transformation/.../insights/" - blog de responsabilidade
social/filantropia do banco, NÃO mercado).

Cada página de artigo tem um bloco `application/ld+json` real
(@type NewsArticle, com headline/datePublished) - metadado estruturado do
próprio banco, mesmo padrão de citi.py/nord.py, nunca inferido do texto
solto."""

import json
import re
import time
from datetime import datetime
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests

from .base import HEADERS, permitido

SITEMAP_INDEX_URL = "https://www.goldmansachs.com/sitemap.xml"
_NOME_CASA = "Goldman Sachs Insights"
_SITEMAP_TIMEOUT = 25  # sitemap filho real tem ~1.5MB, o maior deste módulo
_PAGINA_TIMEOUT = 10
_ORCAMENTO_TOTAL_S = 20
_MAX_ITENS = 8

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_CAMINHO_PREFIXO = "/insights/articles/"
_TICKER = re.compile(r"\b([A-Z]{4}\d{1,2})\b")

_ultimo_motivo_falha = None


def motivo_ultima_falha() -> str | None:
    return _ultimo_motivo_falha


def _sitemaps_filhos(conteudo: bytes) -> list:
    """URLs de sitemap filho declaradas num <sitemapindex>. [] se a
    resposta não for um índice (ex: o site passar a publicar um único
    <urlset> direto) - nesse caso quem chama trata a própria resposta
    como o sitemap final."""
    root = ET.fromstring(conteudo)
    filhos = []
    for sm in root.findall("sm:sitemap", _NS):
        loc_el = sm.find("sm:loc", _NS)
        if loc_el is not None and loc_el.text:
            filhos.append(loc_el.text.strip())
    return filhos


def _candidatos_do_urlset(conteudo: bytes) -> list:
    """(lastmod, loc) dos itens de /insights/articles/ num <urlset>, mais
    recentes primeiro. [] se nada bater o filtro (nunca inventa
    candidato)."""
    root = ET.fromstring(conteudo)
    candidatos = []
    for url in root.findall("sm:url", _NS):
        loc_el = url.find("sm:loc", _NS)
        if loc_el is None or not loc_el.text:
            continue
        loc = loc_el.text.strip()
        caminho = urlparse(loc).path
        if caminho.rstrip("/") == _CAMINHO_PREFIXO.rstrip("/"):
            continue  # página-índice "/insights/articles"
        if not caminho.startswith(_CAMINHO_PREFIXO):
            continue
        lastmod_el = url.find("sm:lastmod", _NS)
        lastmod = lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else ""
        candidatos.append((lastmod, loc))
    candidatos.sort(key=lambda c: c[0], reverse=True)
    return candidatos


def _no_artigo(dados) -> dict | None:
    if isinstance(dados, dict) and str(dados.get("@type", "")).lower() in ("newsarticle", "article"):
        return dados
    return None


def _item(html: str, loc: str) -> dict | None:
    """Metadado real extraído do bloco ld+json da página (ver docstring
    do módulo) - None se a página não tiver um nó NewsArticle com
    headline+datePublished (nunca inventa)."""
    blocos = re.findall(r"<script[^>]*ld\+json[^>]*>(.*?)</script>", html, re.S)
    node = None
    for bloco in blocos:
        try:
            dados = json.loads(bloco)
        except json.JSONDecodeError:
            continue
        node = _no_artigo(dados)
        if node:
            break
    if node is None:
        return None
    titulo = (node.get("headline") or "").strip()
    publicado_bruto = node.get("datePublished")
    if not titulo or not publicado_bruto:
        return None
    try:
        publicado = datetime.fromisoformat(str(publicado_bruto).replace("Z", "+00:00"))
    except ValueError:
        return None
    topicos = node.get("topics") or node.get("keywords") or []
    if isinstance(topicos, str):
        topicos = [topicos]
    tickers = sorted(set(_TICKER.findall(titulo.upper())))
    return {
        "casa": _NOME_CASA,
        "titulo": titulo,
        "data": publicado.date().isoformat(),
        "publicado_em": publicado.isoformat(),
        "autor": "",
        "tipo": "ACOES" if tickers else "MACRO",
        "setor": topicos[0] if topicos else "",
        "tickers": tickers,
        "link": loc,
    }


def testar_conexao(timeout: float = 5) -> tuple:
    """Só testa se o índice de sitemap responde - usado pelo painel
    DIAGNÓSTICO DE FONTES. Retorna (ok, detalhe)."""
    if not permitido(SITEMAP_INDEX_URL):
        return False, "bloqueado pelo robots.txt"
    try:
        r = requests.get(SITEMAP_INDEX_URL, headers=HEADERS, timeout=timeout)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    return True, f"OK ({len(r.content)} bytes)"


def _candidatos(conteudo_indice: bytes) -> list | None:
    """Resolve o(s) sitemap(s) filho(s) do índice e devolve os
    candidatos filtrados já ordenados. None só se o XML do índice (ou de
    algum filho necessário) estiver malformado."""
    try:
        filhos = _sitemaps_filhos(conteudo_indice)
    except ET.ParseError:
        return None

    if not filhos:
        try:
            return _candidatos_do_urlset(conteudo_indice)
        except ET.ParseError:
            return None

    candidatos, limite = [], time.monotonic() + _SITEMAP_TIMEOUT
    for filho in filhos:
        if time.monotonic() > limite:
            print(f"[goldman_sachs] orçamento de tempo esgotado buscando sitemaps filhos")
            break
        if not permitido(filho):
            continue
        try:
            rf = requests.get(filho, headers=HEADERS, timeout=_SITEMAP_TIMEOUT)
            if rf.status_code != 200:
                print(f"[goldman_sachs] sitemap filho respondeu HTTP {rf.status_code}: {filho}")
                continue
            candidatos.extend(_candidatos_do_urlset(rf.content))
        except ET.ParseError as exc:
            print(f"[goldman_sachs] sitemap filho não é XML válido ({filho}): {exc}")
            continue
        except Exception as exc:
            print(f"[goldman_sachs] falha ao buscar sitemap filho ({type(exc).__name__}): {filho}")
            continue
    candidatos.sort(key=lambda c: c[0], reverse=True)
    return candidatos


def obter_relatorios() -> list | None:
    """Artigos públicos recentes do Goldman Sachs Insights. None se o
    índice/sitemap falhar ou nenhum candidato puder ser lido; [] se o
    sitemap respondeu sem nenhum item de /insights/articles/ no momento."""
    global _ultimo_motivo_falha
    if not permitido(SITEMAP_INDEX_URL):
        _ultimo_motivo_falha = "sitemap bloqueado pelo robots.txt"
        return None
    try:
        r = requests.get(SITEMAP_INDEX_URL, headers=HEADERS, timeout=_SITEMAP_TIMEOUT)
    except Exception as exc:
        _ultimo_motivo_falha = f"sitemap indisponível: {type(exc).__name__}"
        print(f"[goldman_sachs] {_ultimo_motivo_falha}: {exc}")
        return None
    if r.status_code != 200:
        tipo = (r.headers.get("content-type") or "").split(";")[0]
        _ultimo_motivo_falha = f"sitemap respondeu HTTP {r.status_code} ({tipo})"
        print(f"[goldman_sachs] {_ultimo_motivo_falha}")
        return None

    candidatos = _candidatos(r.content)
    if candidatos is None:
        _ultimo_motivo_falha = "sitemap não é XML válido"
        print(f"[goldman_sachs] {_ultimo_motivo_falha}")
        return None
    if not candidatos:
        _ultimo_motivo_falha = None
        return []

    itens, tentativas, limite = [], 0, time.monotonic() + _ORCAMENTO_TOTAL_S
    for _, link in candidatos[:_MAX_ITENS]:
        if time.monotonic() > limite:
            print(f"[goldman_sachs] orçamento de tempo esgotado após {tentativas} tentativa(s)")
            break
        if not permitido(link):
            continue
        tentativas += 1
        try:
            resp = requests.get(link, headers=HEADERS, timeout=_PAGINA_TIMEOUT)
            if resp.status_code != 200:
                print(f"[goldman_sachs] página respondeu HTTP {resp.status_code}: {link}")
                continue
            item = _item(resp.text, link)
        except Exception as exc:
            print(f"[goldman_sachs] falha ao buscar página ({type(exc).__name__}): {link}")
            continue
        if item:
            itens.append(item)

    if tentativas > 0 and not itens:
        _ultimo_motivo_falha = f"{tentativas} candidato(s) no sitemap, nenhuma página individual respondeu com o ld+json esperado"
        print(f"[goldman_sachs] {_ultimo_motivo_falha}")
        return None
    _ultimo_motivo_falha = None
    return itens
