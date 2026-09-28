# -*- coding: utf-8 -*-
"""Composição oficial da carteira teórica do Ibovespa, via API pública
da B3 (mesmo endpoint usado pelo site oficial deles, sem autenticação -
descoberto inspecionando as chamadas de rede da página de composição do
índice em b3.com.br). Substitui a lista estática curada
(config.IBOVESPA_SETORES) como fonte da lista de tickers - agora é a
composição real (~76 papéis, rebalanceada a cada quadrimestre pela B3),
não mais uma aproximação de blue chips escolhida à mão.

Cache de 24h: a carteira teórica só muda em rebalanceamento (poucas
vezes por ano); não faz sentido bater na B3 a cada rerun.

Fallback: se a B3 falhar (rede fora, bloqueio de IP em produção -
diferente de Genial/XP, que usam bot-detection real, esta é uma API
JSON pública comum, então o risco é menor, mas não é garantido),
obter_composicao_oficial() retorna {} e quem chama cai pra
config.IBOVESPA_SETORES.keys() (lista curada antiga) como universo de
tickers - nunca quebra o app, só perde a composição real até a B3
voltar. Setor econômico continua vindo da curadoria manual
(config.IBOVESPA_SETORES) - a B3 não retorna classificação setorial
neste endpoint; ticker novo sem setor mapeado cai em "Outros" (não
inventa setor)."""

import base64
import json

import streamlit as st
from curl_cffi import requests as cffi_requests

_URL_BASE = "https://sistemaswebb3-listados.b3.com.br/indexProxy/indexCall/GetPortfolioDay/{}"
_HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
_TTL = 24 * 3600


def _montar_url() -> str:
    payload = {"language": "pt-br", "pageNumber": 1, "pageSize": 200, "index": "IBOV", "segment": "1"}
    b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    return _URL_BASE.format(b64)


@st.cache_data(ttl=_TTL, show_spinner=False)
def obter_composicao_oficial() -> dict:
    """{ticker: {"nome": str, "peso_pct": float}} da carteira teórica
    atual do Ibovespa, direto da B3. {} se a requisição falhar por
    qualquer motivo - quem chama trata como "sem dado novo" e cai pro
    fallback estático (config.IBOVESPA_SETORES), nunca mostra papel
    inventado."""
    try:
        r = cffi_requests.get(_montar_url(), headers=_HEADERS, impersonate="chrome", timeout=15)
        if r.status_code != 200:
            return {}
        dados = r.json()
        resultado = {}
        for item in dados.get("results", []):
            ticker = (item.get("cod") or "").strip()
            if not ticker:
                continue
            try:
                peso = float((item.get("part") or "0").replace(",", "."))
            except ValueError:
                peso = 0.0
            resultado[ticker] = {"nome": (item.get("asset") or "").strip(), "peso_pct": peso}
        return resultado
    except Exception:
        return {}
