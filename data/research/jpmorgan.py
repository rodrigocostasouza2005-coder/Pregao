# -*- coding: utf-8 -*-
"""Coletor do J.P. Morgan Global Research (conteúdo público, publicado em
jpmorgan.com/insights/global-research).

Investigação real (11/11/2026, deste ambiente - rede disponível): J.P.
Morgan Research institucional completo (ratings/preço-alvo por ativo) é
distribuído só a cliente autenticado via J.P. Morgan Markets - NÃO é o que
este coletor lê. O banco também publica, livre de login, uma seção com
marca própria "Global Research" (eyebrow "Global Research" em cada artigo,
título da página-índice "Global Research & Market Insights from J.P.
Morgan") com notas macro/temáticas (ex: eleições e mercados, yields
globais, IA/capex, imóveis) - mais perto de "research macro/temático
público" do que de uma nota de cobertura de ação individual. Este módulo
NUNCA finge que é a mesma coisa que o research institucional completo -
ver CASAS['jpmorgan']['nome'] e motivo_indisponivel de outras casas
registradas como disponivel=False pra contraste.

robots.txt de www.jpmorgan.com permite tudo relevante aqui (sem Disallow
pra /insights nem pro /sitemap.xml, que é explicitamente Allow). Descoberta
via sitemap real (https://www.jpmorgan.com/US/en/sitemap.xml, referenciado
no sitemapindex raiz) filtrando path "/insights/global-research/<algo>" -
diferente do resto do /insights (ex: /insights/banking, páginas
institucionais sem data), essas páginas têm `<p class="date">` e
`<h1 class="title">` renderizados no HTML estático (confirmado com 2
páginas reais, datas de 19/10/2026 e 06/11/2026 - nenhuma simulada).

Sem feed/RSS encontrado (confirmado: jpmorgan.com não expõe
/insights/global-research/feed nem Sitemap de seção separado) - a
descoberta usa o sitemap geral, com orçamento de tempo/itens (mesmo padrão
de data/research/nord.py, que tem a mesma limitação de 1 request por item
candidato)."""

import re
import time
from datetime import date
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from .base import HEADERS, permitido

SITEMAP_URL = "https://www.jpmorgan.com/US/en/sitemap.xml"
_NOME_CASA = "J.P. Morgan Global Research"
_SITEMAP_TIMEOUT = 15
_PAGINA_TIMEOUT = 10
_ORCAMENTO_TOTAL_S = 20
_MAX_ITENS = 8

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_CAMINHO_PREFIXO = "/insights/global-research/"
_TICKER = re.compile(r"\b([A-Z]{4}\d{1,2})\b")

_MESES_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_DATA_TEXTO = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})")

_ultimo_motivo_falha = None


def motivo_ultima_falha() -> str | None:
    return _ultimo_motivo_falha


def _parse_data_en(texto: str) -> date | None:
    m = _DATA_TEXTO.search(texto or "")
    if not m:
        return None
    mes = _MESES_EN.get(m.group(1).strip().lower())
    if not mes:
        return None
    try:
        return date(int(m.group(3)), mes, int(m.group(2)))
    except ValueError:
        return None


def _candidatos_do_sitemap(conteudo: bytes) -> list:
    """(lastmod, loc) das páginas de Global Research presentes no sitemap,
    mais recentes primeiro (pelo lastmod do próprio sitemap - só usado pra
    ordenar quem buscar primeiro, a DATA real do item vem da própria
    página, ver _item). [] se nada bater o filtro (nunca inventa
    candidato)."""
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
        resto = caminho[len(_CAMINHO_PREFIXO):].strip("/")
        if not resto:
            continue  # a própria página-índice, sem artigo
        lastmod_el = url.find("sm:lastmod", _NS)
        lastmod = lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else ""
        candidatos.append((lastmod, loc))
    candidatos.sort(key=lambda c: c[0], reverse=True)
    return candidatos


def _item(html: str, loc: str) -> dict | None:
    """Metadado real extraído do painel lateral do artigo (eyebrow/título/
    data, ver docstring do módulo) - None se a página não tiver esse bloco
    com os 3 campos minimos (nunca inventa título/data)."""
    soup = BeautifulSoup(html, "html.parser")
    painel = soup.select_one("aside.cmp-article-side-panel-content, section.cmp-article-side-panel-content")
    if painel is None:
        return None
    titulo_el = painel.select_one("h1.title")
    data_el = painel.select_one("p.date")
    if titulo_el is None or data_el is None:
        return None
    titulo = titulo_el.get_text(" ", strip=True)
    publicado = _parse_data_en(data_el.get_text(" ", strip=True))
    if not titulo or publicado is None:
        return None
    eyebrow_el = painel.select_one("p.eyebrow")
    categoria = eyebrow_el.get_text(" ", strip=True) if eyebrow_el else ""
    tickers = sorted(set(_TICKER.findall(titulo.upper())))
    return {
        "casa": _NOME_CASA,
        "titulo": titulo,
        "data": publicado.isoformat(),
        "autor": "",
        "tipo": "ACOES" if tickers else "MACRO",
        "setor": categoria,
        "tickers": tickers,
        "link": loc,
    }


def testar_conexao(timeout: float = 5) -> tuple:
    """So testa se o sitemap responde - usado pelo painel DIAGNOSTICO DE
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
    """Notas públicas recentes do J.P. Morgan Global Research. None se o
    sitemap falhar ou nenhum candidato puder ser lido; [] se o sitemap
    respondeu sem nenhuma página de Global Research no momento."""
    global _ultimo_motivo_falha
    if not permitido(SITEMAP_URL):
        _ultimo_motivo_falha = "sitemap bloqueado pelo robots.txt"
        return None
    try:
        r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=_SITEMAP_TIMEOUT)
    except Exception as exc:
        _ultimo_motivo_falha = f"sitemap indisponível: {type(exc).__name__}"
        print(f"[jpmorgan] {_ultimo_motivo_falha}: {exc}")
        return None
    if r.status_code != 200:
        tipo = (r.headers.get("content-type") or "").split(";")[0]
        _ultimo_motivo_falha = f"sitemap respondeu HTTP {r.status_code} ({tipo})"
        print(f"[jpmorgan] {_ultimo_motivo_falha}")
        return None
    try:
        candidatos = _candidatos_do_sitemap(r.content)
    except ET.ParseError as exc:
        _ultimo_motivo_falha = f"sitemap não é XML válido: {exc}"
        print(f"[jpmorgan] {_ultimo_motivo_falha}")
        return None
    if not candidatos:
        _ultimo_motivo_falha = None
        return []

    itens, tentativas, limite = [], 0, time.monotonic() + _ORCAMENTO_TOTAL_S
    for _, link in candidatos[:_MAX_ITENS]:
        if time.monotonic() > limite:
            print(f"[jpmorgan] orçamento de tempo esgotado após {tentativas} tentativa(s)")
            break
        if not permitido(link):
            continue
        tentativas += 1
        try:
            resp = requests.get(link, headers=HEADERS, timeout=_PAGINA_TIMEOUT)
            if resp.status_code != 200:
                print(f"[jpmorgan] página respondeu HTTP {resp.status_code}: {link}")
                continue
            item = _item(resp.text, link)
        except Exception as exc:
            print(f"[jpmorgan] falha ao buscar página ({type(exc).__name__}): {link}")
            continue
        if item:
            itens.append(item)

    if tentativas > 0 and not itens:
        _ultimo_motivo_falha = f"{tentativas} candidato(s) no sitemap, nenhuma página individual respondeu com o bloco esperado"
        print(f"[jpmorgan] {_ultimo_motivo_falha}")
        return None
    _ultimo_motivo_falha = None
    return itens
