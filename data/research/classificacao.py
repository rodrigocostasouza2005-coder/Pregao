# -*- coding: utf-8 -*-
"""Identificacao de ticker(s) mencionados no CORPO de um relatorio de
research + classificacao por setor (Agente C, Frente 1 itens 2/3,
2026-11-12, missao de processamento/inteligencia sobre research).

Por que existe: ate agora, 'tickers' de um item/publicacao de research
(research_itens.tickers, research_premissas.tickers) vem SO do METADADO
que o coletor de cada casa atribui (ex: a XP categoriza o relatorio sob
'PETR4' na pagina dela) - nunca do que o TEXTO do relatorio de fato
menciona. Isso faz mencao cruzada passar batido (ex: um relatorio
categorizado so' sob VALE3 que tambem comenta CSNA3/GGBR4 de passagem -
hoje nenhum filtro por ticker nesses dois acha esse relatorio). Ver
data/research/resumir.py:_gerar_resumo - e' a UNICA janela em que o texto
original ainda existe em memoria (store.py nunca persiste o texto
completo, so' metadado+resumo - ver docstring de store.py), entao e' ali
que identificar_tickers_no_texto precisa ser chamado; depois disso o
texto se perde pra sempre (by design, nao e' um bug a corrigir).

Setor reaproveita a MESMA curadoria manual ja usada pela aba MERCADO
(config.IBOVESPA_SETORES) - nunca uma classificacao nova/paralela. Ticker
sem entrada ali volta None (nunca "Outros" aqui - esse fallback e'
especifico da aba MERCADO/treemap, nao faz sentido pra um relatorio de
research onde "nao sabemos o setor" deveria ficar explicito como None,
nao escondido num balde generico).

Zero IA, zero rede, zero Supabase - funcoes puras sobre o texto/lista de
tickers dados e sobre dicionarios estaticos ja existentes em config.py.

============================================================
API PUBLICA:
    identificar_tickers_no_texto(texto: str) -> list[str]
    classificar_setor(ticker: str) -> str | None
    classificar_setores(tickers: list[str]) -> dict[str, str | None]
    classificar_documento(tickers_metadado: list[str] | None,
                           texto: str | None = None) -> dict
============================================================
"""

import re

from config import ATIVOS_CADASTRO_US, IBOVESPA_SETORES, TICKER_ALIASES

# Universo ESTATICO conhecido pra validar candidatos a ticker achados no
# texto por regex - nunca aceita qualquer sequencia que bata o padrao
# "4 letras + 1 ou 2 digitos" como ticker de verdade (evitaria falso
# positivo tipo uma sigla de 4 letras seguida de um numero de pagina ou
# nota de rodape coincidindo com o formato). So' reconhece ticker que JA
# esta cadastrado em algum lugar do app (mesma uniao de fontes que
# ui/busca.py usa pro autocomplete): IBOVESPA_SETORES (universo B3
# curado) + TICKER_ALIASES (BDRs com alias) + ATIVOS_CADASTRO_US (grupo-
# piloto EUA). Nao inclui a composicao OFICIAL da B3 (data/ibovespa.py:
# obter_composicao_oficial) de proposito: aquela funcao bate rede e usa
# st.cache_data (exige sessao Streamlit) - esta lista precisa ser pura e
# instantanea pra rodar dentro de _gerar_resumo sem custo extra. Papel
# fora do Ibovespa e sem alias cadastrado nao e' reconhecido no corpo do
# texto por esta funcao (limitacao conhecida e documentada, nao silenciosa
# - ver testes).
_UNIVERSO_CONHECIDO = frozenset(IBOVESPA_SETORES) | frozenset(TICKER_ALIASES) | frozenset(ATIVOS_CADASTRO_US)

# Ticker B3: 4 letras + 1 ou 2 digitos (ex: PETR4, SANB11). \b dos dois
# lados evita casar o meio de uma palavra maior.
_REGEX_TICKER = re.compile(r"\b([A-Z]{4}\d{1,2})\b")


def identificar_tickers_no_texto(texto: str | None) -> list[str]:
    """Tickers conhecidos (ver _UNIVERSO_CONHECIDO) encontrados no CORPO
    do texto - ordenado, deduplicado. [] se texto vazio/None ou se nenhum
    candidato do regex bater contra o universo conhecido (nunca inventa
    ticker nem aceita uma sequencia so' porque tem o formato certo)."""
    if not texto:
        return []
    candidatos = set(_REGEX_TICKER.findall(texto.upper()))
    return sorted(candidatos & _UNIVERSO_CONHECIDO)


def classificar_setor(ticker: str | None) -> str | None:
    """Setor economico curado (config.IBOVESPA_SETORES) pra 1 ticker.
    None se o ticker for vazio ou nao tiver entrada na curadoria (nunca
    um setor generico 'Outros' aqui - ver nota no docstring do modulo)."""
    if not ticker:
        return None
    return IBOVESPA_SETORES.get(ticker.strip().upper())


def classificar_setores(tickers: list[str] | None) -> dict:
    """{ticker: setor_ou_None} pra cada ticker da lista (ja' normalizado
    upper/strip) - conveniencia pra nao chamar classificar_setor em loop
    na UI. {} se a lista for vazia/None."""
    if not tickers:
        return {}
    return {t.strip().upper(): classificar_setor(t) for t in tickers if t}


def classificar_documento(tickers_metadado: list[str] | None, texto: str | None = None) -> dict:
    """Visao combinada de tickers (metadado da fonte + achados no CORPO
    do texto, quando o texto e' passado) e setor de cada um - pensada pra
    UI (Agente D) ou pra ser chamada dentro de _gerar_resumo enquanto o
    texto ainda existe em memoria.

    Retorno (chaves sempre presentes, nunca omitidas mesmo quando vazias):
    {
        "tickers_metadado": list[str],       # normalizado, ordenado
        "tickers_no_corpo": list[str],       # [] se texto=None (nao
                                              # tentou procurar, diferente
                                              # de "procurou e nao achou")
        "tickers_novos_no_corpo": list[str], # no_corpo - metadado (a
                                              # mencao cruzada que hoje
                                              # passa batido - item 2 do
                                              # pedido)
        "tickers_todos": list[str],          # uniao, ordenado
        "setor_por_ticker": dict,            # {ticker: setor|None}
        "setores_identificados": list[str],  # unicos, nao-None, ordenado
    }"""
    metadado = sorted({t.strip().upper() for t in (tickers_metadado or []) if t})
    no_corpo = identificar_tickers_no_texto(texto) if texto is not None else []
    novos_no_corpo = sorted(set(no_corpo) - set(metadado))
    todos = sorted(set(metadado) | set(no_corpo))
    setor_por_ticker = classificar_setores(todos)
    setores_identificados = sorted({s for s in setor_por_ticker.values() if s})
    return {
        "tickers_metadado": metadado,
        "tickers_no_corpo": no_corpo,
        "tickers_novos_no_corpo": novos_no_corpo,
        "tickers_todos": todos,
        "setor_por_ticker": setor_por_ticker,
        "setores_identificados": setores_identificados,
    }
