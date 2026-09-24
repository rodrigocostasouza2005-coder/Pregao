# -*- coding: utf-8 -*-
"""Coletor da Genial Analisa (https://analisa.genialinvestimentos.com.br).

A home e renderizada em Next.js (SSR): os dados vem prontos no JSON
__NEXT_DATA__ embutido no HTML, entao NAO fazemos parsing de HTML - so
carregamos esse JSON e navegamos nele. Guardamos apenas metadados
(titulo, data, autor, setor, ticker, link); nunca o texto do relatorio.

Observado na pratica: o dominio fica atras de um WAF (Akamai) que derruba
(timeout, sem resposta) requests feitas com a stack TLS padrao do
`requests`/urllib3 - tanto com `requests` quanto com `curl` puro. A causa
e' fingerprint de TLS (JA3), nao o conteudo da requisicao: usar
`curl_cffi` com `impersonate="chrome"` (que replica o handshake TLS de um
Chrome de verdade) resolve, e a partir dai a resposta e' um HTML estatico
comum, sem nenhum desafio JS pra resolver.

Diagnostico de producao (Streamlit Cloud, 2026-09-23) mostrou um sintoma
diferente do WAF: "HTTP/2 stream reset by server" - a conexao chega no
servidor (diferente do sandbox de dev, que bloqueia o dominio inteiro
antes disso) mas e' derrubada especificamente no HTTP/2. _tentar_buscar
tenta uma sequencia de combinacoes (comecando por forcar HTTP/1.1) ate
uma funcionar, e imprime qual funcionou/falhou - aparece nos Logs do
Streamlit Cloud e no painel DIAGNOSTICO DE FONTES (CONFIG)."""

import json
import re
import time

import streamlit as st
from curl_cffi import requests as cffi_requests
from curl_cffi.const import CurlHttpVersion

from .base import HEADERS, TIMEOUT, TTL_COLETA, permitido

BASE_URL = "https://analisa.genialinvestimentos.com.br"

# ordem de tentativa: HTTP/1.1 primeiro (suspeita principal do reset de
# stream HTTP/2), depois o comportamento original (HTTP/2 via chrome),
# depois outros perfis de impersonate com HTTP/1.1 forcado
_TENTATIVAS = [
    {"impersonate": "chrome", "http_version": CurlHttpVersion.V1_1},
    {"impersonate": "chrome"},
    {"impersonate": "chrome124", "http_version": CurlHttpVersion.V1_1},
    {"impersonate": "safari17_0", "http_version": CurlHttpVersion.V1_1},
]

# orcamento total pra TODAS as tentativas juntas - sem isso, se o dominio
# nao responder nada (timeout puro, nao um erro rapido), as 4 tentativas
# podiam somar bem mais que TIMEOUT*4 (achado na auditoria de
# performance: um teste real bateu no timeout do proprio AppTest por
# causa disso). Uma vez estourado, para na tentativa atual e desiste.
_ORCAMENTO_TOTAL_S = 20


def _tentar_buscar(url: str, orcamento_s: float = _ORCAMENTO_TOTAL_S):
    """Tenta baixar `url` com cada combinacao de _TENTATIVAS ate uma dar
    certo (200 com corpo) ou o orcamento total (`orcamento_s`, default
    _ORCAMENTO_TOTAL_S) estourar. Retorna (Response, rotulo) ou (None,
    None) se todas falharem/o tempo acabar. print() de cada tentativa -
    visivel nos Logs do Streamlit Cloud."""
    limite = time.monotonic() + orcamento_s
    for tentativa in _TENTATIVAS:
        if time.monotonic() > limite:
            print("[genial] orçamento de tempo esgotado, parando tentativas")
            break
        rotulo = f"impersonate={tentativa.get('impersonate')} http={tentativa.get('http_version', 'auto')}"
        try:
            r = cffi_requests.get(url, headers=HEADERS, timeout=TIMEOUT, **tentativa)
            if r.status_code == 200 and r.text:
                print(f"[genial] conexao OK ({rotulo})")
                return r, rotulo
            print(f"[genial] tentativa falhou ({rotulo}): HTTP {r.status_code}")
        except Exception as e:
            print(f"[genial] tentativa falhou ({rotulo}): {e}")
    return None, None


def testar_conexao(orcamento_s: float = 5) -> tuple:
    """So testa se consegue baixar a home (sem parsear __NEXT_DATA__) -
    usado pelo painel DIAGNOSTICO DE FONTES. Orcamento default bem menor
    que o da coleta real (_ORCAMENTO_TOTAL_S=20): e' so' um teste de
    reachability, nao vale a pena travar o painel por 20s numa fonte que
    ja se sabe bloqueada. Retorna (ok, detalhe)."""
    if not permitido(BASE_URL):
        return False, "bloqueado pelo robots.txt"
    r, rotulo = _tentar_buscar(BASE_URL, orcamento_s=orcamento_s)
    if r is None:
        return False, "todas as tentativas falharam"
    return True, rotulo

# tipos de secao na home (campo "type" do __NEXT_DATA__) - estavel e em
# ingles, ao contrario do "titulo" (localizado, mais fragil de casar)
_TIPO_SECAO_RECOMENDACOES = "CARROSSEL_PRINCIPAIS_RECOMENDACOES_SETOR"
_TIPO_SECAO_RELATORIOS = "CARROSSEL_RELATORIOS"  # aparece 2x: acoes e mercado
_TIPO_SECAO_ECONOMIA = "MACROECONOMIA"
_TIPO_SECAO_SWING_TRADE = "SWING_TRADE_E_BANNER"
_TIPO_SECAO_NEWSLETTER = "CARROSSEL_NEWSLETTER"

_TICKER_NO_LINK = re.compile(r"^/acoes/([A-Z0-9]{4,6})(?:/|$)")


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def _buscar_next_data() -> dict | None:
    """Cacheado (nao so as 3 funcoes publicas que consomem isso): sem
    isso, obter_relatorios/obter_recomendacoes/obter_swing_trade batiam
    na home da Genial 3x separadas a cada render da aba RESEARCH, mesmo
    sendo a mesma pagina - achado na auditoria de performance."""
    if not permitido(BASE_URL):
        return None
    r, _ = _tentar_buscar(BASE_URL)
    if r is None:
        return None
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _secoes(data: dict) -> list:
    return data["props"]["pageProps"]["page"]["sections"]


def _url_absoluta(link: str) -> str:
    return link if link.startswith("http") else BASE_URL + link


def _ticker_do_link(link: str) -> list:
    m = _TICKER_NO_LINK.match(link)
    return [m.group(1)] if m else []


def _normalizar_data(texto: str) -> str:
    """Datas na Genial vem em dois formatos diferentes conforme a secao:
    'DD/MM/YYYY' (relatorios) ou 'YYYY-MM-DD HH:MM:SS' (newsletter/swing
    trade). Normaliza tudo pra 'YYYY-MM-DD' (ordena certo como string, e
    a UI formata pra exibicao). Retorna '' se nao reconhecer o formato -
    nunca inventa uma data."""
    texto = (texto or "").strip()
    if not texto:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}", texto):
        return texto[:10]
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", texto)
    if m:
        dia, mes, ano = m.groups()
        return f"{ano}-{mes}-{dia}"
    return ""


def _item_relatorio(item: dict, tipo: str) -> dict:
    autores = ", ".join(a["nome"].strip() for a in (item.get("analistas") or []) if a.get("nome"))
    return {
        "casa": "Genial Analisa",
        "titulo": item["titulo"],
        "data": _normalizar_data(item.get("data", "")),
        "autor": autores,
        "tipo": tipo,
        "setor": item.get("subCategoria") or item.get("categoria") or "",
        "tickers": _ticker_do_link(item["link"]),
        "link": _url_absoluta(item["link"]),
    }


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def obter_relatorios() -> list | None:
    """Relatorios de acoes, mercado/estrategia (Expresso Bolsa Semanal,
    Estrategia em Acao, Carta dos Estrategistas), economia (Copom, FOMC,
    Carta Macro) e Bom Dia Genial - todos no formato comum (casa, titulo,
    data, autor, tipo, setor, tickers, link). None se a home falhar."""
    data = _buscar_next_data()
    if data is None:
        return None
    try:
        relatorios = []

        for secao in _secoes(data):
            if secao.get("type") != _TIPO_SECAO_RELATORIOS:
                continue
            for item in secao.get("content", {}).get("items", []):
                # as duas secoes de CARROSSEL_RELATORIOS (acoes e mercado)
                # sao distinguidas pela categoria de cada item, nao pelo
                # titulo da secao (localizado, mais fragil)
                tipo = "ACOES" if item.get("categoria") == "Ações" else "ESTRATEGIA"
                relatorios.append(_item_relatorio(item, tipo))

        for secao in _secoes(data):
            if secao.get("type") != _TIPO_SECAO_ECONOMIA:
                continue
            for item in secao.get("content", {}).get("items", []):
                relatorios.append(_item_relatorio(item, "MACRO"))

        for secao in _secoes(data):
            if secao.get("type") != _TIPO_SECAO_NEWSLETTER:
                continue
            for item in secao.get("content", {}).get("items", []):
                relatorios.append({
                    "casa": "Genial Analisa",
                    "titulo": item["titulo"],
                    "data": _normalizar_data(item.get("data", "")),
                    "autor": "",
                    "tipo": "NEWSLETTER",
                    "setor": "",
                    "tickers": [],
                    "link": _url_absoluta(item["link"]),
                })

        return relatorios or None
    except Exception:
        return None


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def obter_recomendacoes() -> list | None:
    """Principais recomendacoes por setor: ticker, empresa, setor,
    recomendacao (COMPRA/MANTER/VENDA), preco-alvo, potencial (%), link.
    None se a home falhar ou a secao nao existir."""
    data = _buscar_next_data()
    if data is None:
        return None
    try:
        for secao in _secoes(data):
            if secao.get("type") != _TIPO_SECAO_RECOMENDACOES:
                continue
            itens = secao.get("content") or []
            return [
                {
                    "ticker": it["url"].rsplit("/", 1)[-1],
                    "empresa": (it.get("empresaNome") or "").strip(),
                    "setor": it.get("setor", ""),
                    "recomendacao": it.get("recomendacao", ""),
                    "preco_alvo": it.get("preco"),
                    "potencial_pct": it.get("potencial"),
                    "link": _url_absoluta(it["url"]),
                }
                for it in itens
            ] or None
        return None
    except Exception:
        return None


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def obter_swing_trade() -> list | None:
    """Oportunidades de swing trade: ticker, empresa, recomendacao,
    status ('em aberto' / encerrado), data, link. None se a home falhar
    ou a secao nao existir."""
    data = _buscar_next_data()
    if data is None:
        return None
    try:
        for secao in _secoes(data):
            if secao.get("type") != _TIPO_SECAO_SWING_TRADE:
                continue
            itens = secao.get("content") or []
            return [
                {
                    "ticker": it.get("ticker", ""),
                    "empresa": ((it.get("empresa") or {}).get("nome") or "").strip(),
                    "recomendacao": (it.get("informacoesTicker") or {}).get("recomendacao", ""),
                    "status": (it.get("informacoesTicker") or {}).get("status", ""),
                    "data": _normalizar_data(it.get("date", "")),
                    "link": _url_absoluta(it["link"]),
                }
                for it in itens
            ] or None
        return None
    except Exception:
        return None
