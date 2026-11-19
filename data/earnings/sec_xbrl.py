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

import time

import streamlit as st
import requests

from data.coletores_status import registrar_tentativa

_HEADERS = {"User-Agent": "Pregao App - uso pessoal/nao comercial - contato via github"}
_TIMEOUT = 30
_URL_TICKERS = "https://www.sec.gov/files/company_tickers.json"
_URL_CONCEPT = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{tag}.json"

_TTL_TICKERS = 24 * 60 * 60
_TTL_CONCEITO = 6 * 60 * 60
# TTL curto SO' pro caso de FALHA do mapa ticker->CIK (ver _mapa_ticker_cik
# e docstring de _ultima_falha_mapa_ticker_cik) - fix real 2026-11-19:
# auditoria SAUDE DOS DADOS achou o coletor "SEC EDGAR (XBRL)" com 50
# falhas seguidas desde 2026-10-29 (~2x/dia), NUNCA 1 sucesso. Antes,
# sucesso e falha do mapa ticker->CIK compartilhavam o MESMO
# @st.cache_data(ttl=_TTL_TICKERS=24h): uma falha (retornando {}) ficava
# cacheada pelas MESMAS 24h de uma resposta boa, entao, mesmo quando a
# SEC voltava a responder minutos depois, o app continuava servindo {}
# cacheado por ate 24h - agravando artificialmente o tempo de
# recuperacao do coletor. Nao achei um valor ja padronizado de "TTL de
# falha" em nenhum outro coletor do projeto (cvm.py/ibovespa.py resolvem
# um problema PARECIDO mas diferente - reusar o ULTIMO VALOR BOM numa
# falha TRANSITORIA; aqui replico esse padrao tambem via
# _ultimo_mapa_ticker_cik_valido, mas ele sozinho nao ajuda enquanto
# NUNCA houve sucesso, que e' o caso real). 5min e' um valor novo,
# escolhido no mesmo espirito de outros TTLs curtos do projeto (90s pra
# cotacao, 20min pra noticias): curto o bastante pra nao prender uma
# recuperacao real por horas, longo o bastante pra nao martelar a SEC a
# cada rerun do Streamlit enquanto a fonte estiver fora do ar.
_TTL_FALHA_TICKERS = 5 * 60

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
    """(dados, diagnostico) - dados=None e diagnostico com a CAUSA REAL
    da falha quando a chamada nao da' um JSON valido: timeout, erro de
    conexao, HTTP != 2xx (com status e inicio do corpo da resposta) ou
    corpo que nao e' JSON valido. (diagnostico=None, dados=<json>) no
    sucesso.

    Fix real (auditoria SAUDE DOS DADOS 2026-11-19): antes, QUALQUER
    excecao (timeout, DNS, HTTP 403/429, JSON malformado) virava so' um
    `None` generico - quem chamava nunca sabia SE a SEC bloqueou por
    rate-limit/User-Agent, se a rede caiu, ou se o formato do arquivo
    mudou; o painel de SAUDE DOS DADOS so' mostrava 'sem resposta
    valida' pros 2 coletores que usam isto (_mapa_ticker_cik abaixo e
    _serie_conceito), sem nenhuma pista pra diagnosticar de verdade."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    except requests.exceptions.Timeout as e:
        return None, f"timeout (>{_TIMEOUT}s) ao buscar {url}: {e}"
    except requests.exceptions.ConnectionError as e:
        return None, f"erro de conexao ao buscar {url}: {e}"
    except requests.exceptions.RequestException as e:
        return None, f"falha de requisicao ao buscar {url}: {e!r}"
    if not r.ok:
        return None, f"HTTP {r.status_code} ao buscar {url}: corpo={(r.text or '')[:200]!r}"
    try:
        return r.json(), None
    except ValueError as e:
        return None, f"corpo nao-JSON de {url} (HTTP {r.status_code}): {e}; corpo={(r.text or '')[:200]!r}"


class _FalhaMapaTickerCik(Exception):
    """Sinaliza uma falha real na busca do mapa ticker->CIK - nunca
    propaga pra fora do modulo (obter_cik/_mapa_ticker_cik sempre
    degradam com seguranca pra None/{}); existe so' pra IMPEDIR que
    @st.cache_data cacheie um resultado de falha (ver
    _buscar_mapa_ticker_cik_ok/_mapa_ticker_cik abaixo - Streamlit so'
    guarda em cache o retorno de uma chamada que termina SEM excecao)."""


@st.cache_resource(show_spinner=False)
def _ultimo_mapa_ticker_cik_valido() -> dict:
    """Ultimo {ticker: cik} que o company_tickers.json devolveu com
    sucesso - st.cache_resource = sem TTL, sobrevive entre reruns/
    chamadas no mesmo processo do servidor (mesmo padrao de data/cvm.py:
    _ultimo_mapa_ticker_valido / data/ibovespa.py:_ultima_composicao_
    valida - MESMA classe de bug: uma falha TRANSITORIA bem no momento
    em que o cache de sucesso expira nao pode "trancar" o app sem o
    ultimo dado bom que ja existia). {} ate' a 1a coleta bem-sucedida
    desta sessao do servidor - e' exatamente o caso real de hoje (0
    sucessos desde 2026-10-29), por isso o fix principal de velocidade
    de recuperacao e' o TTL curto de falha (_TTL_FALHA_TICKERS), nao
    este fallback sozinho."""
    return {}


@st.cache_resource(show_spinner=False)
def _ultima_falha_mapa_ticker_cik() -> dict:
    """{'quando': float|None (time.monotonic()), 'erro': str|None} -
    registro da ultima falha do mapa ticker->CIK, usado SO' pra aplicar
    um TTL curto (_TTL_FALHA_TICKERS) especificamente ao caminho de
    FALHA (ver _mapa_ticker_cik). st.cache_resource = sem TTL proprio; o
    cooldown de falha e' controlado manualmente comparando 'quando' com
    time.monotonic() agora, independente do @st.cache_data(ttl=24h) que
    cobre so' o caminho de SUCESSO (_buscar_mapa_ticker_cik_ok)."""
    return {"quando": None, "erro": None}


@st.cache_data(ttl=_TTL_TICKERS, show_spinner=False)
def _buscar_mapa_ticker_cik_ok() -> dict:
    """{ticker: cik} a partir do arquivo oficial da SEC - SO' o caminho
    de SUCESSO fica cacheado aqui, pelas _TTL_TICKERS=24h de costume
    (cadastro de tickers muda raramente). Uma falha real levanta
    _FalhaMapaTickerCik em vez de devolver {}: como @st.cache_data nunca
    guarda o retorno de uma chamada que terminou com excecao, uma falha
    AQUI nunca fica presa nessas mesmas 24h - quem chama
    (_mapa_ticker_cik) trata a excecao com seu proprio cooldown curto
    (_TTL_FALHA_TICKERS) e registra a tentativa.

    Instrumentado (auditoria SAUDE DOS DADOS 2026-10-26: "SEC EDGAR
    (XBRL)" aparecia NUNCA_EXECUTADO sem nenhuma evidencia, mesmo
    distinguindo "fonte indisponivel" de "nunca rodou") - antes, so'
    _serie_conceito() chamava registrar_tentativa, e so' e' alcancada
    quando obter_cik(ticker) ja' encontrou um CIK; pra ticker fora do
    universo SEC (ex: ticker B3 sem CIK, caso normal/esperado, nao
    falha) a funcao retornava None ANTES de qualquer tentativa ser
    registrada - o mapa ticker->CIK em si nunca tinha NENHUMA linha no
    painel, mesmo padrao de gap ja' corrigido pro mapa ticker->CNPJ da
    CVM (ver data/cvm.py:_mapa_ticker_cnpj, "CVM (FCA)")."""
    dados, diagnostico = _get_json(_URL_TICKERS)
    if diagnostico:
        raise _FalhaMapaTickerCik(f"mapa ticker->CIK (company_tickers.json): {diagnostico}")
    if not isinstance(dados, dict) or "data" not in dados:
        raise _FalhaMapaTickerCik(
            "mapa ticker->CIK (company_tickers.json) sem resposta válida (formato inesperado: "
            f"esperava dict com chave 'data', recebeu {type(dados).__name__})"
        )
    # formato: {"fields": [...], "data": [[cik, name, ticker, exchange], ...]}
    campos = dados.get("fields", [])
    try:
        idx_cik, idx_ticker = campos.index("cik"), campos.index("ticker")
    except ValueError:
        raise _FalhaMapaTickerCik(
            f"mapa ticker->CIK sem colunas 'cik'/'ticker' esperadas (colunas recebidas: {campos!r})"
        )
    mapa = {
        str(linha[idx_ticker]).upper(): int(linha[idx_cik])
        for linha in dados.get("data", [])
        if len(linha) > max(idx_cik, idx_ticker)
    }
    if not mapa:
        raise _FalhaMapaTickerCik("mapa ticker->CIK vazio (company_tickers.json respondeu mas sem nenhuma linha valida)")
    registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=True,
                         registros_novos=len(mapa), categoria="Earnings")
    cache_bom = _ultimo_mapa_ticker_cik_valido()
    cache_bom.clear()
    cache_bom.update(mapa)
    _ultima_falha_mapa_ticker_cik().update({"quando": None, "erro": None})
    return mapa


def _mapa_ticker_cik() -> dict:
    """{ticker: cik} a partir do arquivo oficial da SEC. {} se a fonte
    nunca tiver respondido com sucesso ainda - nunca derruba quem chama,
    so' faz obter_cik devolver None.

    TTL diferenciado sucesso x falha (fix real 2026-11-19 - ver
    _TTL_FALHA_TICKERS): o caminho de SUCESSO fica cacheado por
    _TTL_TICKERS=24h (_buscar_mapa_ticker_cik_ok, @st.cache_data). O
    caminho de FALHA usa um cooldown BEM mais curto
    (_TTL_FALHA_TICKERS=5min, _ultima_falha_mapa_ticker_cik) - ANTES, os
    dois compartilhavam o MESMO @st.cache_data(ttl=24h) desta funcao, e
    uma falha (retornando {}) ficava cacheada pelas mesmas 24h de uma
    resposta boa, agravando artificialmente o tempo de recuperacao do
    coletor (achado real: 50 falhas seguidas desde 2026-10-29, nunca 1
    sucesso - a cada falha, o app ficava ate 24h sem nem TENTAR de novo,
    mesmo que a SEC tivesse voltado a responder minutos depois)."""
    falha = _ultima_falha_mapa_ticker_cik()
    quando = falha.get("quando")
    if quando is not None and (time.monotonic() - quando) < _TTL_FALHA_TICKERS:
        # ainda dentro do cooldown de falha - nao tenta de novo (evita
        # martelar a SEC a cada rerun do Streamlit) nem registra nova
        # tentativa (seria ruido identico a' ja' registrada); devolve o
        # ultimo valor bom conhecido (ou {} se nunca teve nenhum).
        return dict(_ultimo_mapa_ticker_cik_valido())
    try:
        return _buscar_mapa_ticker_cik_ok()
    except _FalhaMapaTickerCik as e:
        registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=False,
                             erro=str(e), categoria="Earnings")
        _ultima_falha_mapa_ticker_cik().update({"quando": time.monotonic(), "erro": str(e)})
        return dict(_ultimo_mapa_ticker_cik_valido())


def obter_cik(ticker: str) -> int | None:
    return _mapa_ticker_cik().get(ticker.upper())


@st.cache_data(ttl=_TTL_CONCEITO, show_spinner="consultando XBRL da SEC…")
def _serie_conceito(cik: int, tag: str):
    """Serie bruta (lista de {start,end,val,form,fy,fp,filed,...}) de 1
    conceito us-gaap pra 1 empresa - None se a fonte falhar/conceito nao
    existir pra essa empresa (migracao de tag, ver docstring)."""
    dados, diagnostico = _get_json(_URL_CONCEPT.format(cik=cik, tag=tag))
    if diagnostico:
        registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=False,
                             erro=f"conceito {tag} (CIK {cik}): {diagnostico}",
                             categoria="Earnings")
        return None
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
