# -*- coding: utf-8 -*-
"""Coletor do Citi Global Insights (conteúdo público, publicado em
citigroup.com/global/insights).

Investigação real (11/11/2026, deste ambiente - rede disponível): "Citi
Research" institucional (ratings/preço-alvo por ativo, Citi Velocity/ICG)
é distribuído só a cliente autenticado - NÃO é o que este coletor lê. O
banco também publica, público e sem login, um hub editorial próprio
("Insights") com conteúdo de mercado/estratégia frequentemente assinado
por analistas nomeados no próprio texto (ex: "Beata Manthey and David
Groman assess..." numa nota real de 10/11/2026 sobre renda variável) -
mais parecido com uma versão editorial/pública de notas de mercado do que
com cobertura formal de 1 ação. Este coletor NUNCA chama isso de "Citi
Research" por esse motivo (ver CASA abaixo).

robots.txt de www.citigroup.com ("User-agent: *") só proíbe /login,
/*&JFP_TOKEN= e /citi/ - "Allow: /" cobre o resto, incluindo
/global/insights/. Sitemap oficial declarado no próprio robots.txt
(https://www.citigroup.com/global/sitemap.xml), ~3600 URLs reais com
`lastmod`, confirmado com itens de 10/11/2026 (mesmo dia da sondagem) -
cadência bem mais alta que as outras casas novas deste módulo. Filtra só
path "/global/insights/<slug>" (exclui "/global/news/perspectives/", que
no sitemap é conteúdo de marca/carreira sobre a própria Citi, não
mercado).

Cada página tem um bloco `application/ld+json` real (array de nós
schema.org, inclui um nó "NewsArticle" com headline/datePublished) -
metadado estruturado da própria Citi, não inferido do texto solto (mesmo
princípio de data/research/nord.py, que usa um ld+json equivalente da
Nord). Sem RSS encontrado - descoberta via sitemap, mesmo orçamento de
tempo/itens que as demais casas novas deste módulo."""

import json
import re
from datetime import datetime
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests  # noqa: F401 - mantido pra tests/test_research_citi.py poder
# patchar citi_mod.requests.get (mesmo objeto global usado por
# base.coletar_via_sitemap/testar_conexao_url).

from .base import coletar_via_sitemap, permitido, testar_conexao_url

SITEMAP_URL = "https://www.citigroup.com/global/sitemap.xml"
_NOME_CASA = "Citi Global Insights"
_SITEMAP_TIMEOUT = 20  # sitemap real tem ~1.3MB, mais pesado que os outros
_PAGINA_TIMEOUT = 10
_ORCAMENTO_TOTAL_S = 20
_MAX_ITENS = 8

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_CAMINHO_PREFIXO = "/global/insights/"
_TICKER = re.compile(r"\b([A-Z]{4}\d{1,2})\b")
_TIPOS_ARTIGO = {"newsarticle", "article", "blogposting"}

_ultimo_motivo_falha = None


def motivo_ultima_falha() -> str | None:
    return _ultimo_motivo_falha


def _candidatos_do_sitemap(conteudo: bytes) -> list:
    """(lastmod, loc) dos itens de Insights no sitemap, mais recentes
    primeiro (lastmod só ordena quem buscar primeiro - a DATA real do
    item vem do ld+json da própria página, ver _item). [] se nada bater o
    filtro."""
    root = ET.fromstring(conteudo)
    candidatos = []
    for url in root.findall("sm:url", _NS):
        loc_el = url.find("sm:loc", _NS)
        if loc_el is None or not loc_el.text:
            continue
        loc = loc_el.text.strip()
        caminho = urlparse(loc).path
        if not caminho.startswith(_CAMINHO_PREFIXO):
            continue
        if caminho.rstrip("/") in (_CAMINHO_PREFIXO.rstrip("/"), _CAMINHO_PREFIXO.rstrip("/") + "/research"):
            continue  # página-índice ("/global/insights" ou "/global/insights/research")
        lastmod_el = url.find("sm:lastmod", _NS)
        lastmod = lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else ""
        candidatos.append((lastmod, loc))
    candidatos.sort(key=lambda c: c[0], reverse=True)
    return candidatos


def _no_artigo(nodes: list) -> dict | None:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if str(node.get("@type", "")).lower() in _TIPOS_ARTIGO:
            return node
    return None


def _item(html: str, loc: str) -> dict | None:
    """Metadado real extraído do bloco ld+json da página (ver docstring do
    módulo) - None se a página não tiver um nó de artigo com headline+
    datePublished (nunca inventa)."""
    blocos = re.findall(r"<script[^>]*ld\+json[^>]*>(.*?)</script>", html, re.S)
    node = None
    for bloco in blocos:
        try:
            dados = json.loads(bloco)
        except json.JSONDecodeError:
            continue
        if isinstance(dados, list):
            node = _no_artigo(dados)
        elif isinstance(dados, dict):
            node = _no_artigo(dados.get("@graph") or [dados])
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
    tickers = sorted(set(_TICKER.findall(titulo.upper())))
    return {
        "casa": _NOME_CASA,
        "titulo": titulo,
        "data": publicado.date().isoformat(),
        "publicado_em": publicado.isoformat(),
        "autor": "",
        "tipo": "ACOES" if tickers else "MACRO",
        "setor": "",
        "tickers": tickers,
        "link": loc,
    }


def testar_conexao(timeout: float = 5) -> tuple:
    """So testa se o sitemap responde - usado pelo painel DIAGNOSTICO DE
    FONTES. Retorna (ok, detalhe)."""
    return testar_conexao_url(SITEMAP_URL, permitido, timeout)


def obter_relatorios() -> list | None:
    """Notas públicas recentes do Citi Global Insights. None se o sitemap
    falhar ou nenhum candidato puder ser lido; [] se o sitemap respondeu
    sem nenhum item de Insights no momento.

    Orquestracao extraida pra base.coletar_via_sitemap (auditoria de
    arquitetura 2026-11-12, mesmo padrao de jpmorgan.py/bankofamerica.py/
    morgan_stanley.py/nord.py)."""
    global _ultimo_motivo_falha
    itens, motivo = coletar_via_sitemap(
        sitemap_url=SITEMAP_URL,
        candidatos_do_sitemap=_candidatos_do_sitemap,
        parser_item=_item,
        permitido_fn=permitido,
        sitemap_timeout=_SITEMAP_TIMEOUT,
        pagina_timeout=_PAGINA_TIMEOUT,
        orcamento_total_s=_ORCAMENTO_TOTAL_S,
        max_itens=_MAX_ITENS,
        descricao_esperada="com o ld+json esperado",
        log_prefixo="citi",
    )
    _ultimo_motivo_falha = motivo
    return itens
