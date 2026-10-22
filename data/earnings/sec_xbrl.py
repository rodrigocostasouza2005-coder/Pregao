# -*- coding: utf-8 -*-
"""Conceitos XBRL (taxonomia us-gaap) de empresas internacionais via SEC
EDGAR (data.sec.gov) - API oficial, gratuita, sem autenticacao. Mesmo
papel que data/earnings/cvm_dre.py faz pra empresas brasileiras, mas pra
fora: o "companyconcept" da' a serie historica de 1 conceito (ex:
NetIncomeLoss) de 1 empresa (CIK), com start/end/val por filing - inclui
o TRIMESTRE ISOLADO de verdade (10-Q reporta o periodo discreto, "start"/
"end" de ~90 dias), diferente da CVM onde isso e' opcional por empresa -
ver docstring de cvm_dre.py.

--- CIK e mapeamento de ticker ------------------------------------------

A SEC exige o CIK (identificador interno), nao o ticker, no endpoint de
companyconcept. O mapa ticker->CIK oficial e' o arquivo
https://www.sec.gov/files/company_tickers.json (~800KB, atualizado
diariamente) - cacheado 24h, mesmo raciocinio do mapa ticker->CNPJ de
data/cvm.py.

--- Migracao de tag XBRL entre anos --------------------------------------

Empresas mudam a tag us-gaap usada pra receita ao longo dos anos (ex:
Apple usava 'Revenues' até 2018, depois 'RevenueFromContractWith
CustomerExcludingAssessedTax' - confirmado consultando a API real,
2026-10-22). _TAGS_POR_METRICA lista mais de 1 tag por metrica, em
ORDEM DE PREFERENCIA - a 1a que devolver serie com dado no periodo
pedido vence; nunca mistura 2 tags na MESMA serie (evitaria comparar
definicoes diferentes sem sinalizar)."""

import streamlit as st
import requests

from data.coletores_status import registrar_tentativa

_HEADERS = {"User-Agent": "Pregao App - uso pessoal/nao comercial - contato via github"}
_TIMEOUT = 30
_URL_TICKERS = "https://www.sec.gov/files/company_tickers.json"
_URL_CONCEPT = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{tag}.json"

_TTL_TICKERS = 24 * 60 * 60
_TTL_CONCEITO = 6 * 60 * 60

_NOME_COLETOR = "SEC EDGAR (XBRL)"
_FONTE_COLETOR = "data.sec.gov (companyconcept, us-gaap)"

# metrica interna -> tags us-gaap em ordem de preferencia (1a com dado
# no periodo pedido vence - ver docstring do modulo)
TAGS_POR_METRICA = {
    "receita_liquida": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"),
    "custo_vendas": ("CostOfGoodsAndServicesSold", "CostOfRevenue"),
    "resultado_bruto": ("GrossProfit",),
    "ebit": ("OperatingIncomeLoss",),
    "resultado_antes_tributos": ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",),
    "lucro_liquido_consolidado": ("NetIncomeLoss",),
}


def _get_json(url: str):
    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


@st.cache_data(ttl=_TTL_TICKERS, show_spinner=False)
def _mapa_ticker_cik() -> dict:
    """{ticker: cik} a partir do arquivo oficial da SEC. {} se a fonte
    falhar - nunca derruba quem chama, so' faz obter_cik devolver None."""
    dados = _get_json(_URL_TICKERS)
    if not isinstance(dados, dict) or "data" not in dados:
        return {}
    # formato: {"fields": [...], "data": [[cik, name, ticker, exchange], ...]}
    campos = dados.get("fields", [])
    try:
        idx_cik, idx_ticker = campos.index("cik"), campos.index("ticker")
    except ValueError:
        return {}
    return {
        str(linha[idx_ticker]).upper(): int(linha[idx_cik])
        for linha in dados.get("data", [])
        if len(linha) > max(idx_cik, idx_ticker)
    }


def obter_cik(ticker: str) -> int | None:
    return _mapa_ticker_cik().get(ticker.upper())


@st.cache_data(ttl=_TTL_CONCEITO, show_spinner="consultando XBRL da SEC…")
def _serie_conceito(cik: int, tag: str):
    """Serie bruta (lista de {start,end,val,form,fy,fp,filed,...}) de 1
    conceito us-gaap pra 1 empresa - None se a fonte falhar/conceito nao
    existir pra essa empresa (migracao de tag, ver docstring)."""
    dados = _get_json(_URL_CONCEPT.format(cik=cik, tag=tag))
    if not isinstance(dados, dict) or "units" not in dados or "USD" not in dados.get("units", {}):
        registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=False,
                             erro=f"conceito {tag} indisponivel pro CIK {cik} (migracao de tag ou fonte fora do ar)",
                             categoria="Earnings")
        return None
    registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=True,
                         registros_novos=len(dados["units"]["USD"]), categoria="Earnings")
    return dados["units"]["USD"]


def _valor_trimestre_isolado(serie: list, inicio: str, fim: str):
    """Ponto da serie cujo (start,end) bate EXATAMENTE com o trimestre
    pedido (10-Q/10-K, forma de 'end' no formato ISO yyyy-mm-dd) - usa o
    filing mais recente quando ha' mais de 1 (revisao). None se nao
    houver ponto com esse periodo exato - nunca interpola nem assume."""
    candidatos = [p for p in serie if p.get("start") == inicio and p.get("end") == fim]
    if not candidatos:
        return None
    mais_recente = max(candidatos, key=lambda p: p.get("filed", ""))
    return float(mais_recente["val"]), mais_recente


def obter_metricas_trimestre(ticker: str, inicio: str, fim: str, inicio_ano_anterior: str, fim_ano_anterior: str) -> dict | None:
    """Metricas de TAGS_POR_METRICA pro trimestre [inicio,fim] (ISO
    yyyy-mm-dd) + mesmo trimestre do ano anterior [inicio_ano_anterior,
    fim_ano_anterior] - quem chama (reviewer.py) calcula essas datas a
    partir do calendario fiscal da empresa. None se o ticker nao tiver
    CIK mapeado. Cada metrica fica {"atual": float|None, "ano_anterior":
    float|None, "tag_usada": str|None} - None quando NENHUMA tag da
    preferencia tiver dado pro periodo exato (nunca inventa)."""
    cik = obter_cik(ticker)
    if not cik:
        return None
    metricas = {}
    for metrica, tags in TAGS_POR_METRICA.items():
        atual = ano_anterior = None
        tag_usada = None
        for tag in tags:
            serie = _serie_conceito(cik, tag)
            if not serie:
                continue
            r_atual = _valor_trimestre_isolado(serie, inicio, fim)
            r_ant = _valor_trimestre_isolado(serie, inicio_ano_anterior, fim_ano_anterior)
            if r_atual is not None or r_ant is not None:
                atual = r_atual[0] if r_atual else None
                ano_anterior = r_ant[0] if r_ant else None
                tag_usada = tag
                break
        metricas[metrica] = {"atual": atual, "ano_anterior": ano_anterior, "tag_usada": tag_usada}
    return {
        "ticker": ticker.upper(), "cik": cik, "periodo": {"inicio": inicio, "fim": fim},
        "periodo_ano_anterior": {"inicio": inicio_ano_anterior, "fim": fim_ano_anterior},
        "metricas": metricas, "moeda": "USD",
        "fonte_url": f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/<tag>.json",
        "fonte_nome": "SEC EDGAR - data.sec.gov (XBRL companyconcept, us-gaap)",
    }
