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
obter_composicao_oficial() reaproveita a ÚLTIMA composição boa já
obtida nesta sessão do servidor (ver `_ultima_composicao_valida`) e só
retorna {} se NUNCA tiver conseguido buscar nenhuma - quem chama cai
pra config.IBOVESPA_SETORES.keys() (lista curada antiga) como universo
de tickers só nesse caso extremo; nunca quebra o app, nunca mostra
papel inventado. Setor econômico continua vindo da curadoria manual
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


@st.cache_resource(show_spinner=False)
def _ultima_composicao_valida() -> dict:
    """Ultima composicao oficial da B3 que veio sem erro (mesmo padrao de
    data/prices.py:_ultima_cotacao_indice_valida) - st.cache_resource =
    sem TTL, sobrevive entre reruns/chamadas no mesmo processo do
    servidor. Existe pra corrigir um bug real (auditoria 2026-10-10): sem
    isso, uma falha TRANSITORIA da B3 bem no momento em que o
    @st.cache_data(ttl=24h) de obter_composicao_oficial expira ficava
    "trancada" - a funcao retornava {} e o cache_data guardava esse {}
    pelas MESMAS 24h de uma resposta boa, entao obter_panorama_ibovespa
    (data/mercado.py) ficava no fallback estatico curado por ate 24h
    mesmo que a B3 voltasse a responder minutos depois - contradizia o
    proprio docstring da funcao ("só perde a composição real até a B3
    voltar")."""
    return {}


@st.cache_data(ttl=_TTL, show_spinner=False)
def obter_composicao_oficial() -> dict:
    """{ticker: {"nome": str, "peso_pct": float}} da carteira teórica
    atual do Ibovespa, direto da B3. Se a requisição falhar (ou vier
    vazia) por qualquer motivo, reaproveita a ultima composicao valida
    desta sessao do servidor (ver `_ultima_composicao_valida`) em vez de
    {} - só retorna {} se NUNCA tiver conseguido buscar nenhuma composicao
    real ainda (quem chama so' cai pro fallback estatico curado nesse
    caso extremo). Nunca mostra papel inventado: o que volta aqui e'
    sempre um resultado real de alguma coleta passada, nunca sintetizado."""
    cache = _ultima_composicao_valida()
    try:
        r = cffi_requests.get(_montar_url(), headers=_HEADERS, impersonate="chrome", timeout=15)
        if r.status_code != 200:
            return dict(cache)
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
        if not resultado:
            return dict(cache)
        cache.clear()
        cache.update(resultado)
        return resultado
    except Exception:
        return dict(cache)
