# -*- coding: utf-8 -*-
"""Coletor da Nord Research (nordinvestimentos.com.br) - análises de
resultado trimestral por ticker B3, publicadas no blog oficial.

Sondagem real (24/10/2026, deste ambiente - rede disponível hoje):
robots.txt "User-agent: * / Allow: /" (tudo permitido, com sitemaps
listados), diferente de toda outra casa do projeto o blog NÃO tem feed
RSS (`/feed/` e `/blog/feed/` devolvem HTTP 404) - a descoberta é via
`/blog/sitemap.xml` (público, listado no próprio robots.txt), que tem
~7700 URLs reais (confirmado com o arquivo completo, 1.17MB). A maioria é
conteúdo educacional/opinião ("X vale a pena investir", web-stories,
vídeos, páginas de tag/autor) - só entram no filtro os posts com ticker
B3 no slug E "resultado(s)" no slug (ex:
`petrobras-petr4-resultados-1t26`), a categoria mais claramente "research
de ações" confirmada com texto real (post da Petrobras 1T26 trazia
recomendação explícita no corpo - "reforçamos nossa recomendação neutra
para PETR" - assinado por analista nomeado, Fabiano Vaz). Os ~760 posts
que batem esse filtro no sitemap completo vão de 1T24 a 2T26 (cadência
trimestral real, não um achado isolado).

Cada página de post é renderizada no servidor (HTML estático tem o texto
real, não é SPA client-side como BB Investalk - diferença confirmada) e
traz um bloco `application/ld+json` com `@graph` contendo um nó
`"@type": "Blogposting"` com headline/datePublished/author/url -
metadado estruturado da própria Nord, não inferido do texto solto.

Sem RSS, a descoberta exige 1 request pro sitemap + 1 request por post
candidato (diferente de montebravo.py/genial.py, que pegam tudo em 1
request) - por isso o número de posts buscados por ciclo é limitado
(ver _MAX_ITENS) e há um orçamento total de tempo (ver _ORCAMENTO_TOTAL_S),
mesmo padrão de genial.py pra nunca deixar 1 casa lenta estourar o
orçamento de coleta de TODAS as casas (data/research/base.py:
TEMPO_MAX_COLETA_S).

Preço-alvo/recomendação NÃO são extraídos aqui - isso já é feito sob
demanda por data/research/resumir.py (extração por IA, só quando
explícito no texto, mesmo pipeline que toda outra casa usa); este módulo
só entrega metadado (ver _item)."""

import json
import re
from datetime import datetime
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests  # noqa: F401 - mantido pra tests/test_research_nord.py poder
# patchar nord_mod.requests.get (mesmo objeto global usado por
# base.coletar_via_sitemap/testar_conexao_url).

from .base import coletar_via_sitemap, permitido, testar_conexao_url

SITEMAP_URL = "https://www.nordinvestimentos.com.br/blog/sitemap.xml"
_NOME_CASA = "Nord Research"
_SITEMAP_TIMEOUT = 15
_POST_TIMEOUT = 10
_ORCAMENTO_TOTAL_S = 20  # idem genial.py - orçamento pra TODAS as tentativas desta casa
_MAX_ITENS = 8  # limite de posts buscados por ciclo (1 request HTML por item, ver docstring)

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_CAMINHOS_IGNORADOS = ("/blog/web-stories/", "/blog/videos/", "/blog/autores/", "/blog/tags/")
_TICKER = re.compile(r"(?<![a-z0-9])([a-z]{4}(?:3|4|5|6|11))(?![a-z0-9])")
_RESULTADO = re.compile(r"resultados?")

_ultimo_motivo_falha = None


def motivo_ultima_falha() -> str | None:
    return _ultimo_motivo_falha


def _candidatos_do_sitemap(conteudo: bytes) -> list:
    """(lastmod, loc) dos posts do sitemap que batem ticker-B3 + 'resultado(s)'
    no slug, mais recentes primeiro. [] se o sitemap não tiver nenhum
    (nunca inventa candidato)."""
    root = ET.fromstring(conteudo)
    candidatos = []
    for url in root.findall("sm:url", _NS):
        loc_el = url.find("sm:loc", _NS)
        if loc_el is None or not loc_el.text:
            continue
        loc = loc_el.text.strip()
        caminho = urlparse(loc).path
        if not caminho.startswith("/blog/"):
            continue
        if any(caminho.startswith(p) for p in _CAMINHOS_IGNORADOS):
            continue
        slug = caminho.rstrip("/").rsplit("/", 1)[-1]
        if not _TICKER.search(slug) or not _RESULTADO.search(slug):
            continue
        lastmod_el = url.find("sm:lastmod", _NS)
        lastmod = lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else ""
        candidatos.append((lastmod, loc))
    candidatos.sort(key=lambda c: c[0], reverse=True)
    return candidatos


def _no_blogposting(ld_json: dict) -> dict | None:
    for node in ld_json.get("@graph", []):
        if str(node.get("@type", "")).lower() == "blogposting":
            return node
    return None


def _item(html: str, loc: str) -> dict | None:
    """Metadado do post a partir do bloco ld+json real da página (ver
    docstring do módulo) - None se a página não tiver esse bloco ou ele
    não tiver os campos minimos (nunca inventa título/data)."""
    blocos = re.findall(r"<script[^>]*ld\+json[^>]*>(.*?)</script>", html, re.S)
    node = None
    for bloco in blocos:
        try:
            node = _no_blogposting(json.loads(bloco))
        except (json.JSONDecodeError, AttributeError):
            continue
        if node:
            break
    if node is None:
        return None
    titulo = (node.get("headline") or "").strip()
    publicado_bruto = node.get("datePublished")
    link = (node.get("url") or loc).strip()
    if not titulo or not publicado_bruto or not link:
        return None
    try:
        publicado = datetime.fromisoformat(publicado_bruto)
    except ValueError:
        return None
    slug = urlparse(link).path.rstrip("/").rsplit("/", 1)[-1]
    tickers = sorted({t.upper() for t in _TICKER.findall(slug)})
    autor = ((node.get("author") or {}).get("name") or "").strip()
    return {
        "casa": _NOME_CASA,
        "titulo": titulo,
        "data": publicado.date().isoformat(),
        "publicado_em": publicado.isoformat(),
        "autor": autor,
        "tipo": "ACOES",
        "setor": "",
        "tickers": tickers,
        "link": link,
    }


def testar_conexao(timeout: float = 5) -> tuple:
    """So testa se o sitemap responde - usado pelo painel DIAGNOSTICO DE
    FONTES. Retorna (ok, detalhe).

    Gap real corrigido (auditoria de arquitetura 2026-11-12): nord.py era
    a UNICA das 5 casas "sitemap + N paginas" sem este `testar_conexao` -
    nao existia na copia original desta casa (24/10/2026) e passou
    despercebido porque data/diagnostico.py tambem nao tinha NENHUMA das
    5 casas cadastrada (ver FONTES/_TESTES_ESPECIFICOS la', corrigido na
    mesma auditoria) - o painel DIAGNOSTICO DE FONTES nunca teria notado
    a falta."""
    return testar_conexao_url(SITEMAP_URL, permitido, timeout)


def obter_relatorios() -> list | None:
    """Análises de resultado trimestral por ticker B3 recentes da Nord.
    None se o sitemap falhar ou nenhum dos candidatos encontrados puder
    ser lido; [] se o sitemap respondeu mas não há nenhum post de
    resultado no momento (normal fora de temporada de balanços).

    Orquestracao extraida pra base.coletar_via_sitemap (auditoria de
    arquitetura 2026-11-12, mesmo padrao de jpmorgan.py/bankofamerica.py/
    citi.py/morgan_stanley.py)."""
    global _ultimo_motivo_falha
    itens, motivo = coletar_via_sitemap(
        sitemap_url=SITEMAP_URL,
        candidatos_do_sitemap=_candidatos_do_sitemap,
        parser_item=_item,
        permitido_fn=permitido,
        sitemap_timeout=_SITEMAP_TIMEOUT,
        pagina_timeout=_POST_TIMEOUT,
        orcamento_total_s=_ORCAMENTO_TOTAL_S,
        max_itens=_MAX_ITENS,
        descricao_esperada="",
        log_prefixo="nord",
    )
    _ultimo_motivo_falha = motivo
    return itens
