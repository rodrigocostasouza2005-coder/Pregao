# -*- coding: utf-8 -*-
"""Coletor do Morgan Stanley Insights (conteúdo público, publicado em
morganstanley.com/insights/articles).

Investigação real (11/11/2026, deste ambiente - rede disponível): o
research institucional completo da Morgan Stanley (Morgan Stanley
Research, com rating/preço-alvo por ativo) é distribuído só a cliente
autenticado - NÃO é o que este coletor lê. O banco também mantém, público
e sem login, um hub editorial ("Ideas"/"Insights" - a URL antiga
morganstanley.com/ideas hoje redireciona pra /insights) com artigos que às
vezes resumem achados do próprio Morgan Stanley Research em linguagem
pública (confirmado com texto real: um artigo trazia no
og:description "Morgan Stanley Research assesses..."). Este coletor NUNCA
finge que é a nota de research completa - é conteúdo editorial público
derivado dela.

robots.txt de www.morganstanley.com (grupo "User-agent: *") não desallow
"/insights/articles/"; o Sitemap oficial é
https://www.morganstanley.com/sitemapindex.xml, que lista
https://www.morganstanley.com/sitemap.xml com ~4600 URLs reais e lastmod
atualizado (confirmado: itens de 09/11/2026 no sitemap, mesma semana da
sondagem). Filtra só o path "/insights/articles/<slug>" (exclui podcasts/
vídeos/press-releases, que vivem em outros prefixos do mesmo sitemap e não
têm o metadado de data usado aqui).

Sem RSS encontrado pra essa seção - descoberta via sitemap geral (mesma
limitação de 1 request por item candidato que data/research/nord.py e
data/research/jpmorgan.py já têm, por isso o mesmo padrão de orçamento de
tempo/itens). Data real vem da meta tag `content_publishedAt` (formato
ISO, presente nas páginas testadas) - nunca inferida do slug/lastmod do
sitemap."""

import re
from datetime import datetime
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests  # noqa: F401 - mantido pra tests/test_research_morgan_stanley.py
# poder patchar ms_mod.requests.get (mesmo objeto global usado por
# base.coletar_via_sitemap/testar_conexao_url).
from bs4 import BeautifulSoup

from .base import coletar_via_sitemap, permitido, testar_conexao_url

SITEMAP_URL = "https://www.morganstanley.com/sitemap.xml"
_NOME_CASA = "Morgan Stanley Insights"
_SITEMAP_TIMEOUT = 20  # sitemap real tem ~850KB, mais pesado que os outros
_PAGINA_TIMEOUT = 10
_ORCAMENTO_TOTAL_S = 20
_MAX_ITENS = 8

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_CAMINHO_PREFIXO = "/insights/articles/"
_TICKER = re.compile(r"\b([A-Z]{4}\d{1,2})\b")

_ultimo_motivo_falha = None


def motivo_ultima_falha() -> str | None:
    return _ultimo_motivo_falha


def _candidatos_do_sitemap(conteudo: bytes) -> list:
    """(lastmod, loc) dos artigos de Insights no sitemap, mais recentes
    primeiro (pelo lastmod do sitemap - só pra ordenar quem buscar
    primeiro; a DATA real do item vem de dentro da própria página, ver
    _item). [] se nada bater o filtro."""
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
        if caminho.rstrip("/") == _CAMINHO_PREFIXO.rstrip("/"):
            continue  # a própria página-índice
        lastmod_el = url.find("sm:lastmod", _NS)
        lastmod = lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else ""
        candidatos.append((lastmod, loc))
    candidatos.sort(key=lambda c: c[0], reverse=True)
    return candidatos


def _data_publicada(html: str) -> datetime | None:
    m = re.search(r'name="content_publishedAt"\s+content="([^"]+)"', html)
    if not m:
        return None
    try:
        return datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
    except ValueError:
        return None


def _item(html: str, loc: str) -> dict | None:
    """Metadado real da página (título + meta content_publishedAt, ver
    docstring do módulo) - None se faltar título ou data confiável (nunca
    inventa)."""
    publicado = _data_publicada(html)
    if publicado is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    titulo_el = soup.find("title")
    titulo = titulo_el.get_text(" ", strip=True) if titulo_el else ""
    titulo = re.sub(r"\s*\|\s*Morgan Stanley\s*$", "", titulo).strip()
    if not titulo:
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
    """Artigos públicos recentes do Morgan Stanley Insights. None se o
    sitemap falhar ou nenhum candidato puder ser lido; [] se o sitemap
    respondeu sem nenhum artigo de Insights no momento.

    Orquestracao extraida pra base.coletar_via_sitemap (auditoria de
    arquitetura 2026-11-12, mesmo padrao de jpmorgan.py/bankofamerica.py/
    citi.py/nord.py)."""
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
        descricao_esperada="com o metadado esperado",
        log_prefixo="morgan_stanley",
    )
    _ultimo_motivo_falha = motivo
    return itens
