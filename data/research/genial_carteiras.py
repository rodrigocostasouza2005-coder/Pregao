# -*- coding: utf-8 -*-
"""Coletor de carteiras mensais publicadas pela Genial Analisa.

Usa somente a página pública oficial de Carteira Recomendada de Ações.
Não confunde recomendações genéricas por setor com composição de carteiras.
Falhas de fonte, mês incorreto ou parsing parcial são rejeitados.
"""
import re
from datetime import date, datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from .base import HEADERS, TIMEOUT, permitido

BASE_URL = "https://analisa.genialinvestimentos.com.br"
LISTAGEM_URL = BASE_URL + "/carteiras-recomendadas/renda-variavel/"
MESES = {
    1: "janeiro", 2: "fevereiro", 3: "marco", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}
TICKER_RE = re.compile(r"^([A-Z]{4}\d{1,2})\s*[·|–—-]")
CARTEIRA_RE = re.compile(r"^Carteira\s+(Ibovespa\s+10\+|Ibovespa\s+5\+|Small Caps\s+8\+|Dividendos\s+5\+)", re.I)
MIN_CARTEIRAS = 3
MIN_RECOMENDACOES = 20


def _get(url):
    if not permitido(url):
        return None
    try:
        response = cffi_requests.get(
            url, headers=HEADERS, timeout=TIMEOUT,
            impersonate="chrome", http_version=__import__(
                "curl_cffi.const", fromlist=["CurlHttpVersion"]
            ).CurlHttpVersion.V1_1,
        )
        if response.status_code == 200 and response.text:
            return response.text
    except Exception as exc:
        print(f"[radar_genial] falha ao buscar {url}: {exc}")
    return None


def _url_artigo_mes(html, hoje):
    soup = BeautifulSoup(html, "html.parser")
    mes = MESES[hoje.month]
    ano = str(hoje.year)
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, a["href"])
        slug = href.lower()
        if "carteira-recomendada-de-acoes" in slug and mes in slug and ano in slug:
            links.append(href)
    # A listagem pode repetir o mesmo link em cards e menu.
    return links[0] if links else None


def parsear_artigo(html, url, hoje=None):
    """Extrai tickers de títulos de ações dentro de seções de carteiras.

    O parser exige pelo menos três carteiras e vinte posições para não
    ativar snapshots vazios ou claramente incompletos.
    """
    hoje = hoje or date.today()
    soup = BeautifulSoup(html, "html.parser")
    titulo = soup.find(["h1"])
    titulo_texto = titulo.get_text(" ", strip=True) if titulo else ""
    mes_nome = MESES[hoje.month].capitalize()
    if mes_nome.casefold() not in titulo_texto.casefold() or str(hoje.year) not in titulo_texto:
        return None

    # Data de publicação precisa ser explícita e pertencer ao mês vigente.
    texto = soup.get_text(" ", strip=True)
    data_match = re.search(r"Publicado em\s+(\d{2}) de ([A-Za-zçÇ]+) de (\d{4})", texto, re.I)
    if not data_match:
        data_match = re.search(r"Publicado em\s+(\d{2}) de ([A-Za-zçÇ]+) de (\d{4})", html, re.I)
    if data_match:
        dia, mes_extenso, ano = data_match.groups()
        mapa_meses = {v.casefold(): k for k, v in MESES.items()}
        mes_publicacao = mapa_meses.get(mes_extenso.casefold())
        if not mes_publicacao or int(ano) != hoje.year or mes_publicacao != hoje.month:
            return None
        data_publicacao = f"{ano}-{mes_publicacao:02d}-{int(dia):02d}"
    else:
        # Não aceitar artigo atual sem data verificável.
        return None

    carteiras = []
    carteira_atual = None
    for heading in soup.find_all(["h2", "h3", "h4"]):
        heading_text = heading.get_text(" ", strip=True)
        if heading.name == "h2":
            match = CARTEIRA_RE.match(heading_text)
            carteira_atual = match.group(1) if match else None
            if carteira_atual and carteira_atual not in carteiras:
                carteiras.append(carteira_atual)
            continue
        if not carteira_atual or heading.name not in ("h3", "h4"):
            continue
        ticker_match = TICKER_RE.match(heading_text.upper())
        if not ticker_match:
            continue
        ticker = ticker_match.group(1)
        yield_item = {
            "casa": "Genial Analisa",
            "carteira": carteira_atual,
            "ticker": ticker,
            "empresa": heading_text.split("·", 1)[1].strip() if "·" in heading_text else "",
            "recomendacao": "CARTEIRA MENSAL",
            "preco_alvo": None,
            "data_publicacao": data_publicacao,
            "validade_ate": None,
            "fonte_url": url,
            "verificado_em": datetime.now(timezone.utc).isoformat(),
            "status_coleta": "COLETADO",
        }
        yield yield_item

    # This generator is consumed by coletar_carteiras; validate as a list there.
    # The structural checks are applied by parsear_lista below.


def parsear_lista(html, url, hoje=None):
    itens = list(parsear_artigo(html, url, hoje=hoje))
    carteiras = {item["carteira"] for item in itens}
    tickers = {(item["carteira"], item["ticker"]) for item in itens}
    if len(carteiras) < MIN_CARTEIRAS or len(tickers) < MIN_RECOMENDACOES:
        return None
    return itens


def coletar_carteiras(hoje=None):
    """Retorna snapshot mensal validado; None indica fonte inválida/indisponível."""
    hoje = hoje or date.today()
    html_listagem = _get(LISTAGEM_URL)
    if not html_listagem:
        return None
    url_artigo = _url_artigo_mes(html_listagem, hoje)
    if not url_artigo:
        print("[radar_genial] artigo mensal vigente não encontrado na listagem oficial")
        return None
    html_artigo = _get(url_artigo)
    if not html_artigo:
        return None
    itens = parsear_lista(html_artigo, url_artigo, hoje=hoje)
    if not itens:
        print("[radar_genial] artigo mensal rejeitado: data, carteiras ou composição incompletas")
        return None
    return itens
