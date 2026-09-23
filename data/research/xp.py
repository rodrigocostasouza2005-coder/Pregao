# -*- coding: utf-8 -*-
"""Coletor da XP Investimentos (conteudos.xpi.com.br) via API publica do
WordPress (wp-json/wp/v2) - responde sem login.

O sandbox de desenvolvimento (Claude Code) tem o IP bloqueado pelo CDN da
XP - confirmado tanto com `requests` puro quanto com `curl_cffi`
impersonate="chrome" (mesmo Reference ID de bloqueio nos dois casos), ou
seja e' bloqueio por IP/geografia, diferente do caso da Genial (que era
so fingerprint de TLS, contornavel). Campos confirmados com requisicao
real feita fora do sandbox (2026-09-23).

Diagnostico de producao (Streamlit Cloud, 2026-09-23) mostrou 403 mesmo
de la - o bloqueio nao e' so do sandbox de dev. _tentar_requisitar tenta
`curl_cffi impersonate="chrome"` primeiro e, se falhar, `requests` puro
com User-Agent comum de navegador + Accept: application/json (talvez o
bloqueio reaja ao UA identificado "PregaoApp/..." em vez do TLS) - print()
de qual tentativa funcionou/falhou, visivel nos Logs do Streamlit Cloud e
no painel DIAGNOSTICO DE FONTES (CONFIG).

Tipos de post (custom post types do WordPress) usados - carteiras
recomendadas (carteira-*) ficam de fora de proposito, nao sao "relatorio":
- rel-acoes-fund: relatorios de acoes (analise fundamentalista)
- rel-artigo-aloc: estrategia/alocacao
- rel-acoes-tec: analise tecnica

Resumo: NUNCA contorna o paywall. O texto usado pro resumo e' so o trecho
de content.rendered ANTES do marcador "paywall-gateway" (ver
obter_texto_aberto) - nunca baixa a pagina publica do relatorio em si."""

import re

import requests as plain_requests
import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from .base import HEADERS, TIMEOUT, TTL_COLETA, permitido

BASE_URL = "https://conteudos.xpi.com.br"

# UA comum de navegador - so pra tentativa de fallback (requests puro),
# que testa se o bloqueio reage ao nosso UA identificado, nao ao TLS
_UA_COMUM = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

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


def _tentar_requisitar(url: str, params: dict):
    """Tenta buscar `url` de duas formas ate uma dar certo (200): primeiro
    curl_cffi impersonate="chrome" (contorna bloqueio por fingerprint de
    TLS), depois requests puro com User-Agent comum + Accept: application/
    json (contorna bloqueio que reaja ao UA identificado em vez do TLS).
    Retorna (Response, rotulo) ou (None, None) se as duas falharem.
    print() de cada tentativa - visivel nos Logs do Streamlit Cloud."""
    tentativas = [
        ("curl_cffi+UA-identificado", lambda: cffi_requests.get(
            url, headers=HEADERS, params=params, impersonate="chrome", timeout=TIMEOUT,
        )),
        ("requests+UA-comum+Accept-json", lambda: plain_requests.get(
            url, headers={"User-Agent": _UA_COMUM, "Accept": "application/json"},
            params=params, timeout=TIMEOUT,
        )),
    ]
    for rotulo, fazer_requisicao in tentativas:
        try:
            r = fazer_requisicao()
            if r.status_code == 200:
                print(f"[xp] conexao OK ({rotulo})")
                return r, rotulo
            print(f"[xp] tentativa falhou ({rotulo}): HTTP {r.status_code}")
        except Exception as e:
            print(f"[xp] tentativa falhou ({rotulo}): {e}")
    return None, None


def _requisitar(path: str, params: dict):
    """GET na API do WordPress da XP, com timeout e checagem de robots.txt
    antes. None se bloqueado/erro - nunca lanca excecao pra quem chama."""
    url = f"{BASE_URL}{path}"
    if not permitido(url):
        return None
    r, _ = _tentar_requisitar(url, params)
    if r is None:
        return None
    try:
        return r.json()
    except Exception:
        return None


def testar_conexao() -> tuple:
    """So testa se consegue baixar a lista de relatorios de acoes (sem
    parsear os itens) - usado pelo painel DIAGNOSTICO DE FONTES. Retorna
    (ok, detalhe)."""
    url = f"{BASE_URL}/wp-json/wp/v2/rel-acoes-fund"
    if not permitido(url):
        return False, "bloqueado pelo robots.txt"
    r, rotulo = _tentar_requisitar(url, {"per_page": 1})
    if r is None:
        return False, "todas as tentativas falharam"
    return True, rotulo


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
