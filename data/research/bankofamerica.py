# -*- coding: utf-8 -*-
"""Coletor do BofA Institute (institute.bankofamerica.com) - análises
econômicas/de consumo publicadas pelo instituto público do banco.

Investigação real (11/11/2026, deste ambiente - rede disponível): "BofA
Global Research" (o research institucional sell-side, com rating/
preço-alvo por ação) é distribuído só a cliente autenticado via o portal
de research do próprio banco - NÃO é o que este coletor lê, e este módulo
NUNCA chama o conteúdo abaixo de "BofA Research"/"research de ações" por
esse motivo (ver CASA abaixo - nome deliberadamente "BofA Institute", não
"Bank of America Research"). O "Bank of America Institute" é uma
publicação pública e separada (sem login), com análises macro/de consumo a
partir de dados agregados do próprio banco (ex: "Consumer Checkpoint",
"Economic Insights") - instituição e publicação reais, não uma invenção
nem uma republicação de terceiro.

robots.txt de institute.bankofamerica.com ("User-agent: *", sem Disallow
relevante) permite tudo além de /cgi-bin/ e /tmp/; expõe um sitemap.xml
próprio (declarado no robots.txt) com ~170 URLs reais e `lastmod` (não
"ultima recoleta" - é o lastmod oficial do site), confirmado com itens de
06/11/2026 na sondagem. Filtra só o path "/economic-insights/<slug>.html"
(a categoria mais claramente analítica/recorrente, com nome de publicação
e texto real sobre gasto do consumidor/emprego/inflação - exclui páginas
de hub como "/economic-insights.html" e outras seções do instituto ainda
não investigadas, ex: /transformation/, /sustainability/).

DATA: as páginas testadas não têm uma data de publicação visível no HTML
nem em meta tag confiável - por isso a 'data' usada aqui é o `lastmod` do
próprio sitemap (data real e pública, mas é "última atualização da
página", não necessariamente o dia exato da publicação original; nunca
inventada, só documentada com essa ressalva explícita, igual
itau_carteiras.py já faz pra uma limitação equivalente).

Sem RSS encontrado - descoberta via sitemap (mesmo padrão de orçamento de
tempo/itens de nord.py/jpmorgan.py/morgan_stanley.py, 1 request por item
candidato)."""

import re
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests  # noqa: F401 - mantido pra tests/test_research_bankofamerica.py
# poder patchar boa_mod.requests.get (mesmo objeto global usado por
# base.coletar_via_sitemap/testar_conexao_url).
from bs4 import BeautifulSoup

from .base import coletar_via_sitemap, permitido, testar_conexao_url

SITEMAP_URL = "https://institute.bankofamerica.com/content/institute/bank-of-america-institute.sitemap.xml"
_NOME_CASA = "BofA Institute"
_SITEMAP_TIMEOUT = 15
_PAGINA_TIMEOUT = 10
_ORCAMENTO_TOTAL_S = 20
_MAX_ITENS = 8

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_CAMINHO_PREFIXO = "/economic-insights/"
_TICKER = re.compile(r"\b([A-Z]{4}\d{1,2})\b")

_ultimo_motivo_falha = None


def motivo_ultima_falha() -> str | None:
    return _ultimo_motivo_falha


def _candidatos_do_sitemap(conteudo: bytes) -> list:
    """(lastmod, loc) dos artigos de Economic Insights no sitemap, mais
    recentes primeiro - lastmod aqui É a data usada no item final (ver
    docstring do módulo), não só critério de ordenação. [] se nada bater
    o filtro (nunca inventa candidato)."""
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
        lastmod = (lastmod_el.text or "").strip() if lastmod_el is not None else ""
        if not lastmod:
            continue  # sem data real não entra - nunca inventa
        candidatos.append((lastmod, loc))
    candidatos.sort(key=lambda c: c[0], reverse=True)
    return candidatos


def _item(html: str, loc: str, lastmod: str) -> dict | None:
    """Metadado real da página (título, ver docstring do módulo pra
    proveniência da data) - None se não tiver título (nunca inventa)."""
    soup = BeautifulSoup(html, "html.parser")
    titulo_el = soup.find("title")
    titulo = titulo_el.get_text(" ", strip=True) if titulo_el else ""
    if not titulo:
        return None
    tickers = sorted(set(_TICKER.findall(titulo.upper())))
    return {
        "casa": _NOME_CASA,
        "titulo": titulo,
        "data": lastmod[:10],
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
    """Análises públicas recentes do BofA Institute. None se o sitemap
    falhar ou nenhum candidato puder ser lido; [] se o sitemap respondeu
    sem nenhum item de Economic Insights no momento.

    Orquestracao extraida pra base.coletar_via_sitemap (auditoria de
    arquitetura 2026-11-12, mesmo padrao de jpmorgan.py/citi.py/
    morgan_stanley.py/nord.py) - so' `_candidatos_do_sitemap`/`_item`
    continuam especificos desta casa (esta usa `lastmod` como a DATA
    real do item, ver docstring do modulo - por isso
    `passar_lastmod_ao_parser=True`)."""
    global _ultimo_motivo_falha
    itens, motivo = coletar_via_sitemap(
        sitemap_url=SITEMAP_URL,
        candidatos_do_sitemap=_candidatos_do_sitemap,
        parser_item=_item,
        permitido_fn=permitido,
        passar_lastmod_ao_parser=True,
        sitemap_timeout=_SITEMAP_TIMEOUT,
        pagina_timeout=_PAGINA_TIMEOUT,
        orcamento_total_s=_ORCAMENTO_TOTAL_S,
        max_itens=_MAX_ITENS,
        descricao_esperada="com o metadado esperado",
        log_prefixo="bankofamerica",
    )
    _ultimo_motivo_falha = motivo
    return itens
