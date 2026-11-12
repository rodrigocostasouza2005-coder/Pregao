# -*- coding: utf-8 -*-
"""Coletor do Jefferies Insights (conteúdo público, publicado em
jefferies.com/insights).

Investigação real (12/11/2026, deste ambiente - rede disponível): o
research institucional completo da Jefferies (cobertura de ações por
ativo, rating/preço-alvo, distribuído via Jefferies Live/portal de
clientes) é client-only - NUNCA coletado por este projeto. O banco
também publica, sem login, um hub editorial próprio em
jefferies.com/insights (WordPress público) com conteúdo temático real e
atual sobre mercados/setores/política (confirmado com páginas reais:
"What's Driving Healthcare Dealmaking Right Now?", datePublished
2026-11-10, e outros itens de 11/11 e 10/11/2026 no sitemap). Este
coletor NUNCA chama isso de "Jefferies Research" por esse motivo (mesma
distinção documentada pros bancos globais - ver docstring de
data/research/citi.py).

robots.txt de www.jefferies.com permite tudo relevante aqui. O site é
WordPress com sitemap padrão do plugin Yoast SEO - post-sitemap.xml
(confirmado real, ~230 URLs) traz os posts do tipo "post" do site, hoje
TODOS sob /insights/ (filtra por esse prefixo mesmo assim, por segurança
- se o WordPress um dia reusar esse post type pra outro conteúdo, o
filtro continua correto).

Cada página de post tem um bloco `application/ld+json` com `@graph`
(nó Article, com headline/datePublished/author real) e outro bloco
NewsArticle avulso com `articleSection` (ex: "Markets") - metadado
estruturado do próprio WordPress/Yoast, nunca inferido do texto solto;
usa o nó Article do @graph (tem author) e complementa `setor` com o
articleSection do NewsArticle quando presente."""

import json
import re
import time
from datetime import datetime
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests

from .base import HEADERS, permitido

SITEMAP_URL = "https://www.jefferies.com/post-sitemap.xml"
_NOME_CASA = "Jefferies Insights"
_SITEMAP_TIMEOUT = 15
_PAGINA_TIMEOUT = 10
_ORCAMENTO_TOTAL_S = 20
_MAX_ITENS = 8

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_CAMINHO_PREFIXO = "/insights/"
_TICKER = re.compile(r"\b([A-Z]{4}\d{1,2})\b")

_ultimo_motivo_falha = None


def motivo_ultima_falha() -> str | None:
    return _ultimo_motivo_falha


def _candidatos_do_sitemap(conteudo: bytes) -> list:
    """(lastmod, loc) dos posts do sitemap sob /insights/, mais recentes
    primeiro. [] se nada bater o filtro (nunca inventa candidato)."""
    root = ET.fromstring(conteudo)
    candidatos = []
    for url in root.findall("sm:url", _NS):
        loc_el = url.find("sm:loc", _NS)
        if loc_el is None or not loc_el.text:
            continue
        loc = loc_el.text.strip()
        if not urlparse(loc).path.startswith(_CAMINHO_PREFIXO):
            continue
        lastmod_el = url.find("sm:lastmod", _NS)
        lastmod = lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else ""
        candidatos.append((lastmod, loc))
    candidatos.sort(key=lambda c: c[0], reverse=True)
    return candidatos


def _nos_ld_json(html: str) -> list:
    nos = []
    for bloco in re.findall(r"<script[^>]*ld\+json[^>]*>(.*?)</script>", html, re.S):
        try:
            dados = json.loads(bloco)
        except json.JSONDecodeError:
            continue
        if isinstance(dados, dict) and isinstance(dados.get("@graph"), list):
            nos.extend(n for n in dados["@graph"] if isinstance(n, dict))
        elif isinstance(dados, dict):
            nos.append(dados)
    return nos


def _item(html: str, loc: str) -> dict | None:
    """Metadado real extraído dos blocos ld+json da página (ver
    docstring do módulo) - None se não houver um nó Article/NewsArticle
    com headline+datePublished (nunca inventa)."""
    nos = _nos_ld_json(html)
    artigo = next((n for n in nos if str(n.get("@type", "")).lower() == "article"), None)
    news = next((n for n in nos if str(n.get("@type", "")).lower() == "newsarticle"), None)
    base_no = artigo or news
    if base_no is None:
        return None
    titulo = (base_no.get("headline") or "").strip()
    publicado_bruto = base_no.get("datePublished")
    if not titulo or not publicado_bruto:
        return None
    try:
        publicado = datetime.fromisoformat(str(publicado_bruto).replace("Z", "+00:00"))
    except ValueError:
        return None
    autores = base_no.get("author") or []
    if isinstance(autores, dict):
        autores = [autores]
    autor = ", ".join(a.get("name", "") for a in autores if isinstance(a, dict) and a.get("name")).strip()
    setor = (news or {}).get("articleSection") or ""
    tickers = sorted(set(_TICKER.findall(titulo.upper())))
    return {
        "casa": _NOME_CASA,
        "titulo": titulo,
        "data": publicado.date().isoformat(),
        "publicado_em": publicado.isoformat(),
        "autor": autor,
        "tipo": "ACOES" if tickers else "MACRO",
        "setor": setor,
        "tickers": tickers,
        "link": loc,
    }


def testar_conexao(timeout: float = 5) -> tuple:
    """Só testa se o sitemap responde - usado pelo painel DIAGNÓSTICO DE
    FONTES. Retorna (ok, detalhe)."""
    if not permitido(SITEMAP_URL):
        return False, "bloqueado pelo robots.txt"
    try:
        r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=timeout)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    return True, f"OK ({len(r.content)} bytes)"


def obter_relatorios() -> list | None:
    """Artigos públicos recentes do Jefferies Insights. None se o
    sitemap falhar ou nenhum candidato puder ser lido; [] se o sitemap
    respondeu sem nenhum item sob /insights/ no momento."""
    global _ultimo_motivo_falha
    if not permitido(SITEMAP_URL):
        _ultimo_motivo_falha = "sitemap bloqueado pelo robots.txt"
        return None
    try:
        r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=_SITEMAP_TIMEOUT)
    except Exception as exc:
        _ultimo_motivo_falha = f"sitemap indisponível: {type(exc).__name__}"
        print(f"[jefferies] {_ultimo_motivo_falha}: {exc}")
        return None
    if r.status_code != 200:
        tipo = (r.headers.get("content-type") or "").split(";")[0]
        _ultimo_motivo_falha = f"sitemap respondeu HTTP {r.status_code} ({tipo})"
        print(f"[jefferies] {_ultimo_motivo_falha}")
        return None
    try:
        candidatos = _candidatos_do_sitemap(r.content)
    except ET.ParseError as exc:
        _ultimo_motivo_falha = f"sitemap não é XML válido: {exc}"
        print(f"[jefferies] {_ultimo_motivo_falha}")
        return None
    if not candidatos:
        _ultimo_motivo_falha = None
        return []

    itens, tentativas, limite = [], 0, time.monotonic() + _ORCAMENTO_TOTAL_S
    for _, link in candidatos[:_MAX_ITENS]:
        if time.monotonic() > limite:
            print(f"[jefferies] orçamento de tempo esgotado após {tentativas} tentativa(s)")
            break
        if not permitido(link):
            continue
        tentativas += 1
        try:
            resp = requests.get(link, headers=HEADERS, timeout=_PAGINA_TIMEOUT)
            if resp.status_code != 200:
                print(f"[jefferies] página respondeu HTTP {resp.status_code}: {link}")
                continue
            item = _item(resp.text, link)
        except Exception as exc:
            print(f"[jefferies] falha ao buscar página ({type(exc).__name__}): {link}")
            continue
        if item:
            itens.append(item)

    if tentativas > 0 and not itens:
        _ultimo_motivo_falha = f"{tentativas} candidato(s) no sitemap, nenhuma página individual respondeu com o ld+json esperado"
        print(f"[jefferies] {_ultimo_motivo_falha}")
        return None
    _ultimo_motivo_falha = None
    return itens
