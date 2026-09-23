# -*- coding: utf-8 -*-
"""Coletor da XP Investimentos (conteudos.xpi.com.br) via API publica do
WordPress (wp-json/wp/v2) - responde sem login.

O sandbox de desenvolvimento (Claude Code) tem o IP bloqueado pelo CDN da
XP - confirmado tanto com `requests` puro quanto com `curl_cffi`
impersonate="chrome" (mesmo Reference ID de bloqueio nos dois casos), ou
seja e' bloqueio por IP/geografia, diferente do caso da Genial (que era
so fingerprint de TLS, contornavel). Este coletor foi escrito a partir da
estrutura de campos verificada manualmente pelo Rodrigo direto no
navegador - NAO testado ao vivo neste ambiente. Testar em producao/local
antes de habilitar por padrao (por isso CASAS["xp"]["ativa_por_padrao"]
comeca False).

Tipos de post (custom post types do WordPress) usados - carteiras
recomendadas (carteira-*) ficam de fora de proposito, nao sao "relatorio":
- rel-acoes-fund: relatorios de acoes (analise fundamentalista)
- rel-artigo-aloc: estrategia/alocacao
- rel-acoes-tec: analise tecnica

Resumo: NUNCA contorna o paywall. O texto usado pro resumo e' so o trecho
de content.rendered ANTES do marcador "paywall-gateway" (ver
obter_texto_aberto) - nunca baixa a pagina publica do relatorio em si."""

import re

import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from .base import HEADERS, TIMEOUT, TTL_COLETA, permitido

BASE_URL = "https://conteudos.xpi.com.br"

# tipo do post no WordPress -> tipo interno usado pela UI (ver _TIPO_LABEL
# em ui/research_tab.py)
_TIPOS_POST = {
    "rel-acoes-fund": "ACOES",
    "rel-artigo-aloc": "ESTRATEGIA",
    "rel-acoes-tec": "ANALISE_TECNICA",
}

# WordPress marca cada post com uma classe "tag-<slug>" por tag - tickers
# tem 4 letras + 1 ou 2 digitos (ex: tag-ggps3, tag-vale3, tag-aapl34)
_TICKER_CLASSE = re.compile(r"^tag-([a-z]{4}\d{1,2})$")

_MARCADOR_PAYWALL = "paywall-gateway"


def _requisitar(path: str, params: dict):
    """GET na API do WordPress da XP, com timeout e checagem de robots.txt
    antes. None se bloqueado/erro - nunca lanca excecao pra quem chama."""
    url = f"{BASE_URL}{path}"
    if not permitido(url):
        return None
    try:
        r = cffi_requests.get(url, headers=HEADERS, params=params, impersonate="chrome", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _tickers_do_class_list(class_list) -> list:
    tickers = []
    for classe in class_list or []:
        m = _TICKER_CLASSE.match(classe)
        if m:
            tickers.append(m.group(1).upper())
    return tickers


def _limpar_html(texto: str) -> str:
    return BeautifulSoup(texto or "", "html.parser").get_text().strip()


def _autor(item: dict) -> str:
    autor = (item.get("custom_data") or {}).get("author") or {}
    nome = (autor.get("nome") or "").strip()
    cargo = (autor.get("cargo") or "").strip()
    if nome and cargo:
        return f"{nome} ({cargo})"
    return nome


def _item_relatorio(item: dict, tipo: str) -> dict:
    return {
        "casa": "XP Investimentos",
        "titulo": _limpar_html(item.get("title", {}).get("rendered")),
        "data": (item.get("date") or "")[:10],
        "autor": _autor(item),
        "tipo": tipo,
        "tickers": _tickers_do_class_list(item.get("class_list")),
        "link": item.get("link", ""),
    }


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def obter_relatorios() -> list | None:
    """Relatorios das categorias uteis (acoes, estrategia, analise
    tecnica), 20 mais recentes de cada. None so se TODAS as chamadas
    falharem; se so algumas falharem, retorna o que deu certo (degrada
    graciosamente, nunca trava nem inventa dado)."""
    relatorios = []
    for tipo_post, tipo in _TIPOS_POST.items():
        dados = _requisitar(f"/wp-json/wp/v2/{tipo_post}", params={"per_page": 20})
        if not dados:
            continue
        try:
            relatorios.extend(_item_relatorio(item, tipo) for item in dados)
        except Exception:
            continue
    return relatorios or None


def obter_texto_aberto(link: str) -> tuple:
    """Texto pro resumo por IA: reconsulta a API do WordPress pelo slug do
    link e usa SO o content.rendered ja cortado antes do paywall - nunca
    baixa a pagina publica do relatorio (evita capturar preview/paywall
    com estrutura diferente do que o corte espera). Retorna (texto,
    motivo_falha); texto=None se nao achar o post ou o trecho aberto for
    curto demais (provavelmente tudo pago)."""
    slug = link.rstrip("/").rsplit("/", 1)[-1]
    if not slug:
        return None, "link sem slug reconhecível"

    for tipo_post in _TIPOS_POST:
        dados = _requisitar(f"/wp-json/wp/v2/{tipo_post}", params={"slug": slug})
        if not dados:
            continue
        html = dados[0].get("content", {}).get("rendered", "")
        corte = html.find(_MARCADOR_PAYWALL)
        if corte != -1:
            html = html[:corte]
        texto = _limpar_html(html)
        if len(texto) < 200:
            return None, "conteúdo aberto muito curto (provavelmente exige assinatura)"
        return texto, None

    return None, "relatório não encontrado na API"
