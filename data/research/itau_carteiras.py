# -*- coding: utf-8 -*-
"""Coletor da carteira pública Top 5 do Itaú Investimentos.

Importante: esta fonte é publicada pelo Itaú Investimentos. Não rotular como
"Itaú BBA Research": são produtos distintos, ainda que o site informe que Itaú
BBA é uma marca do Itaú Unibanco. Só extrai composição/metadados necessários
ao Radar; não reproduz o texto editorial do relatório.
"""
import re
import unicodedata
from datetime import date, datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import HEADERS, TIMEOUT, permitido

BASE_URL = "https://www.itau.com.br"
LISTAGEM_URL = BASE_URL + "/investimentos/carteiras-recomendadas/"
CASA = "Itaú Investimentos"
CARTEIRA = "Top 5"
MESES = {
    1: "janeiro", 2: "fevereiro", 3: "marco", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}
TICKER_RE = re.compile(r"\b([A-Z]{4}\d{1,2})\b")
EMPRESA_TICKER_RE = re.compile(r"^\s*(.+?)\s*\(([A-Z]{4}\d{1,2})\)")
MIN_TICKERS = 5


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in texto if not unicodedata.combining(c)).casefold()


def _get(url):
    if not permitido(url):
        print(f"[radar_itau] coleta bloqueada por robots.txt: {url}")
        return None
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT * 2)
        if response.status_code != 200 or not response.text or len(response.text) < 500:
            print(f"[radar_itau] resposta inválida HTTP {response.status_code}: {url}")
            return None
        return response.text
    except Exception as exc:
        print(f"[radar_itau] falha de conexão: {type(exc).__name__}: {exc} ({url})")
        return None


def _url_artigo_mes(html, hoje):
    soup = BeautifulSoup(html, "html.parser")
    mes = _normalizar(MESES[hoje.month])
    ano = str(hoje.year)
    for link in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, link["href"])
        slug = _normalizar(href)
        if "carteira-top-5" in slug and mes in slug and ano in slug:
            return href
    return None


def parsear_artigo(html, url, hoje=None):
    """Retorna snapshot completo ou None; nunca aceita parser parcial."""
    hoje = hoje or date.today()
    soup = BeautifulSoup(html, "html.parser")
    titulo = soup.find("h1")
    titulo_texto = _normalizar(titulo.get_text(" ", strip=True) if titulo else "")
    if _normalizar(MESES[hoje.month]) not in titulo_texto or str(hoje.year) not in titulo_texto:
        return None

    # A página oficial publica a composição em tabela; limitar extração às
    # tabelas que contenham cabeçalho de empresa/companhia e ticker.
    itens = []
    agora = datetime.now(timezone.utc).isoformat()
    for tabela in soup.find_all("table"):
        linhas = tabela.find_all("tr")
        cabecalho = _normalizar(" ".join(c.get_text(" ", strip=True) for c in (linhas[0].find_all(["th", "td"]) if linhas else [])))
        if not any(p in cabecalho for p in ("empresa", "companhia", "acoes")):
            continue
        for linha in linhas[1:]:
            celulas = [c.get_text(" ", strip=True) for c in linha.find_all(["th", "td"])]
            if not celulas:
                continue
            combinado = " ".join(celulas).upper()
            tickers = TICKER_RE.findall(combinado)
            if not tickers:
                continue
            ticker = tickers[0]
            empresa = next((c.strip() for c in celulas if c.strip() and not TICKER_RE.fullmatch(c.strip().upper())), "")
            itens.append({
                "casa": CASA,
                "carteira": CARTEIRA,
                "ticker": ticker,
                "empresa": empresa,
                "recomendacao": "CARTEIRA MENSAL",
                "preco_alvo": None,
                "data_publicacao": f"{hoje.year}-{hoje.month:02d}-01",
                "validade_ate": None,
                "fonte_url": url,
                "verificado_em": agora,
                "status_coleta": "COLETADO",
            })
    # Alguns componentes do site são renderizados como texto acessível no
    # HTML, não como elemento <table>. Fallback conservador para linhas
    # com o formato "Embraer (EMBJ3) | ...": só aceita ticker entre
    # parênteses, exatamente como a tabela oficial expõe a composição.
    if len({item["ticker"] for item in itens}) < MIN_TICKERS:
        for linha_texto in soup.get_text("\\n", strip=True).splitlines():
            match = EMPRESA_TICKER_RE.match(linha_texto)
            if not match:
                continue
            empresa, ticker = match.groups()
            itens.append({
                "casa": CASA,
                "carteira": CARTEIRA,
                "ticker": ticker,
                "empresa": empresa.strip(),
                "recomendacao": "CARTEIRA MENSAL",
                "preco_alvo": None,
                "data_publicacao": f"{hoje.year}-{hoje.month:02d}-01",
                "validade_ate": None,
                "fonte_url": url,
                "verificado_em": agora,
                "status_coleta": "COLETADO",
            })
    # Deduplicar por ticker e rejeitar qualquer extração parcial.
    unicos = {}
    for item in itens:
        unicos[item["ticker"]] = item
    if len(unicos) < MIN_TICKERS:
        print(f"[radar_itau] artigo rejeitado: {len(unicos)} ticker(s), mínimo {MIN_TICKERS}; layout pode ter mudado")
        return None
    return list(unicos.values())


def coletar_carteiras(hoje=None):
    hoje = hoje or date.today()
    html = _get(LISTAGEM_URL)
    if not html:
        return None
    url = _url_artigo_mes(html, hoje)
    if not url:
        print(f"[radar_itau] carteira Top 5 de {MESES[hoje.month]}/{hoje.year} não encontrada na página oficial")
        return None
    artigo = _get(url)
    if not artigo:
        return None
    itens = parsear_artigo(artigo, url, hoje=hoje)
    if not itens:
        print("[radar_itau] composição oficial não validada; snapshot anterior será preservado")
        return None
    return itens
