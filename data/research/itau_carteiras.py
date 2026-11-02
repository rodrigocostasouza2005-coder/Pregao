# -*- coding: utf-8 -*-
"""Coletor público da carteira Top 5 do Itaú Investimentos.

Não confundir Itaú Investimentos com Itaú BBA Research. O coletor seleciona
a publicação mais recente que já existe (até o mês corrente), não presume
que o relatório do mês corrente foi publicado. Snapshots incompletos são
rejeitados para preservar a última carteira válida.
"""
import re
import unicodedata
from datetime import date, datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import HEADERS, TIMEOUT, permitido

BASE_URL = "https://hub-conteudo.cloud.itau.com.br"
LISTAGEM_URLS = (
    BASE_URL + "/investimentos/carteiras-recomendadas/",
    "https://www.itau.com.br/investimentos/carteiras-recomendadas/",
)
CASA = "Itaú Investimentos"
CARTEIRA = "Top 5"
MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
MESES_POR_NUMERO = {v: k for k, v in MESES.items()}
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


def _data_publicacao(url, hoje=None, titulo=""):
    """Extrai mês/ano do slug/título e rejeita publicações futuras."""
    hoje = hoje or date.today()
    texto = _normalizar(url) + " " + _normalizar(titulo)
    for nome_mes, numero in MESES.items():
        for ano_txt in re.findall(r"20\d{2}", texto):
            ano = int(ano_txt)
            if re.search(rf"{nome_mes}[-_/ ]*{ano}", texto) or re.search(rf"{ano}[-_/ ]*{nome_mes}", texto):
                data = date(ano, numero, 1)
                if data <= date(hoje.year, hoje.month, 1):
                    return data
    return None


def _artigos_disponiveis(html, base_url, hoje=None):
    soup = BeautifulSoup(html, "html.parser")
    candidatos = {}
    for link in soup.find_all("a", href=True):
        href = urljoin(base_url, link["href"])
        if "carteira-top-5" not in _normalizar(href):
            continue
        publicado = _data_publicacao(href, hoje, link.get_text(" ", strip=True))
        if publicado:
            candidatos[href] = publicado
    return sorted(candidatos.items(), key=lambda item: item[1], reverse=True)


def _url_artigo_mes(html, hoje, base_url=LISTAGEM_URLS[0]):
    """Compatibilidade: retorna a publicação mais recente já disponível."""
    artigos = _artigos_disponiveis(html, base_url, hoje)
    return artigos[0][0] if artigos else None


def parsear_artigo(html, url, hoje=None):
    """Retorna snapshot completo ou None; nunca aceita parser parcial."""
    hoje = hoje or date.today()
    soup = BeautifulSoup(html, "html.parser")
    titulo = soup.find("h1")
    titulo_texto = titulo.get_text(" ", strip=True) if titulo else ""
    publicado = _data_publicacao(url, hoje, titulo_texto)
    if not publicado:
        return None

    itens = []
    agora = datetime.now(timezone.utc).isoformat()
    for tabela in soup.find_all("table"):
        linhas = tabela.find_all("tr")
        cabecalho = [_normalizar(c.get_text(" ", strip=True)) for c in linhas[0].find_all(["th", "td"])] if linhas else []
        if not any(p in " ".join(cabecalho) for p in ("empresa", "companhia", "acoes")):
            continue
        idx_preco = next((i for i, nome in enumerate(cabecalho)
                          if "preco justo" in nome or "preco alvo" in nome), None)
        for linha in linhas[1:]:
            celulas = [c.get_text(" ", strip=True) for c in linha.find_all(["th", "td"])]
            combinado = " ".join(celulas).upper()
            tickers = TICKER_RE.findall(combinado)
            if not tickers:
                continue
            ticker = tickers[0]
            empresa = next((c.strip() for c in celulas if TICKER_RE.search(c.upper())), "")
            preco_alvo = None
            if idx_preco is not None and idx_preco < len(celulas):
                valor = re.sub(r"[^0-9,.]", "", celulas[idx_preco])
                if valor:
                    try:
                        preco_alvo = float(valor.replace(".", "").replace(",", "."))
                    except ValueError:
                        pass
            itens.append((ticker, empresa, preco_alvo))

    if len({item[0] for item in itens}) < MIN_TICKERS:
        for linha in soup.get_text("\n", strip=True).splitlines():
            match = EMPRESA_TICKER_RE.match(linha)
            if match:
                itens.append((match.group(2), match.group(1).strip(), None))

    unicos = {}
    for ticker, empresa, preco_alvo in itens:
        unicos[ticker] = {
            "casa": CASA, "carteira": CARTEIRA, "ticker": ticker,
            "empresa": empresa, "recomendacao": "CARTEIRA MENSAL",
            "preco_alvo": preco_alvo,
            "data_publicacao": publicado.isoformat(),
            "validade_ate": None, "fonte_url": url,
            "verificado_em": agora, "status_coleta": "COLETADO",
        }
    if len(unicos) < MIN_TICKERS:
        print(f"[radar_itau] artigo rejeitado: {len(unicos)} ticker(s), mínimo {MIN_TICKERS}; carteira anterior preservada")
        return None
    return list(unicos.values())


def coletar_carteiras(hoje=None):
    hoje = hoje or date.today()
    artigos = {}
    for listagem_url in LISTAGEM_URLS:
        html = _get(listagem_url)
        if not html:
            continue
        for url, publicado in _artigos_disponiveis(html, listagem_url, hoje):
            artigos[url] = publicado
    if not artigos:
        print("[radar_itau] nenhuma publicação Top 5 válida encontrada nas listagens oficiais")
        return None
    url = max(artigos, key=artigos.get)
    artigo = _get(url)
    if not artigo:
        return None
    itens = parsear_artigo(artigo, url, hoje=hoje)
    if not itens:
        print("[radar_itau] composição oficial não validada; snapshot anterior será preservado")
        return None
    return itens
