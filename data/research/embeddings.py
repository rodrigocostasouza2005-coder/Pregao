# -*- coding: utf-8 -*-
"""Busca semantica (RAG) sobre a biblioteca PERMANENTE de premissas/
projecoes de research (research_premissas, ver sql/research_premissas.sql
e data/research/store.py) - Equity Research Library, Fase C (pedido do
Rodrigo, 2026-10-30).

Embeddings via Google Gemini (REST puro, so' `requests` - ja' dependencia
do projeto, ZERO SDK novo) porque Groq (unico provedor de IA ja usado no
projeto) nao tem endpoint de embeddings. Vetores (768 dims, ver
config.GEMINI_EMBEDDING_DIMENSAO) ficam numa tabela pgvector nova
(sql/research_embeddings.sql), SEM NUNCA persistir o texto completo do
relatorio original (mesmo principio de research_premissas) - so' uma
string curta e deterministica montada a partir dos campos JA EXTRAIDOS
(ver _texto_para_indexar).

API PUBLICA deste modulo (pensada pra outras partes do sistema chamarem -
ex: uma 3a etapa de integracao com o coordenador, feita depois por outra
pessoa):
    - buscar(...)            busca hibrida (estrutural + semantica + lexical)
    - indexar_pendentes(...) pipeline de indexacao incremental

Todo o resto (_gerar_embedding, _texto_para_indexar, _salvar_embedding,
_links_indexados, _embeddings_existentes, _buscar_por_similaridade) e'
INTERNO - detalhe de implementacao das duas funcoes publicas acima, nao
pensado pra ser chamado de fora deste modulo (prefixo `_`). Testes deste
arquivo chamam o que precisarem direto (mesmo padrao ja usado em
data/research/resumir.py/test_research_premissas.py - testar internals
sem rede/Supabase real e' uma pratica normal neste projeto).

Nunca gera nenhum texto narrativo via LLM aqui - so' matematica de
similaridade sobre vetores + filtro/dedup deterministico em Python. A
montagem de resposta legivel fica pra camada de UI (ui/research_tab.py),
que renderiza os campos estruturados direto - nunca sintetiza uma frase
nova "inventada" a partir do resultado."""

import time
from datetime import datetime, timezone

import requests

import config
from data.supabase_client import obter_cliente

from . import store

_TIMEOUT_SEG = 10
# 1 tentativa inicial + 2 retries = 3 tentativas no total.
_MAX_TENTATIVAS = 3
_BACKOFF_SEGUNDOS = [1, 2]

_AVISO_SEM_CREDENCIAL = (
    "busca semantica indisponivel - GEMINI_API_KEY nao configurada, "
    "mostrando so resultado estrutural/lexical"
)
_AVISO_FALHA_TECNICA = (
    "busca semantica indisponivel no momento (falha tecnica), "
    "mostrando so resultado estrutural/lexical"
)

_ORDEM_ORIGEM = {"ambos": 0, "semantico": 1, "lexical": 2, "estrutural": 3}


# ============================================================
# INTERNO - geracao de embedding (Gemini REST) e texto a indexar
# ============================================================

def _gerar_embedding(texto: str) -> list | None:
    """Gera o vetor de embedding (768 dims) de um texto via Gemini REST
    puro (ver config.obter_credenciais_gemini). NUNCA lanca excecao pra
    fora: qualquer falha (credencial ausente, rede, timeout, HTTP de
    erro, JSON malformado) retorna None - log tecnico via print (mesmo
    padrao simples de jobs/coordenador.py e
    data/research/resumir.py:_log_erro_ia), nunca expoe detalhe tecnico
    pra UI.

    Retry limitado (ate 2 tentativas extras, backoff 1s depois 2s) SO'
    pra HTTP 429 (rate limit) ou erro de rede transitorio (timeout/
    conexao, qualquer requests.exceptions.RequestException na chamada em
    si) - NUNCA pra erro 4xx/5xx que nao seja 429 (ex: 400 payload
    invalido, 401/403 credencial invalida): tentar de novo nesses casos
    so' desperdicaria chamadas sem nenhuma chance real de sucesso."""
    if not texto or not texto.strip():
        return None

    api_key, modelo = config.obter_credenciais_gemini()
    if not api_key:
        print("[research-embeddings] GEMINI_API_KEY nao configurada - embedding nao gerado")
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:embedContent"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "content": {"parts": [{"text": texto}]},
        "output_dimensionality": config.GEMINI_EMBEDDING_DIMENSAO,
    }

    ultimo_erro = None
    for tentativa in range(_MAX_TENTATIVAS):
        tem_proxima_tentativa = tentativa < _MAX_TENTATIVAS - 1
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=_TIMEOUT_SEG)
        except requests.exceptions.RequestException as e:
            # erro de rede/timeout - transitorio, elegivel a retry.
            ultimo_erro = f"erro de rede: {e}"
            if tem_proxima_tentativa:
                time.sleep(_BACKOFF_SEGUNDOS[tentativa])
                continue
            break

        if r.status_code == 429:
            ultimo_erro = "rate limit (HTTP 429)"
            if tem_proxima_tentativa:
                time.sleep(_BACKOFF_SEGUNDOS[tentativa])
                continue
            break

        if r.status_code >= 400:
            # 4xx/5xx que NAO e' rate limit (ex: 400/401/403) - nunca
            # tenta de novo, e' credencial/payload invalido, nao transitorio.
            ultimo_erro = f"HTTP {r.status_code}: {r.text[:200]}"
            break

        try:
            valores = r.json()["embedding"]["values"]
        except Exception as e:
            ultimo_erro = f"resposta malformada: {e}"
            break

        if not isinstance(valores, list) or not valores:
            ultimo_erro = "resposta sem vetor de embedding valido"
            break

        return valores

    print(f"[research-embeddings] falha ao gerar embedding (modelo={modelo}): {ultimo_erro}")
    return None


def _texto_para_indexar(linha_premissa: dict) -> str:
    """Monta uma string curta e DETERMINISTICA pra indexar (texto base do
    embedding) SO' a partir dos campos JA EXTRAIDOS de uma linha de
    research_premissas (casa/titulo/tickers/tipo_documento/premissas/
    projecoes/recomendacao/preco_alvo) - NUNCA busca nem inclui o texto
    do relatorio original (research_premissas nunca guarda isso, ver
    sql/research_premissas.sql).

    Pura/sem rede. Determinismo (mesma linha sempre gera o MESMO texto -
    inclusive ordenando as chaves de projecoes, que e' um dict) e'
    essencial pra indexar_pendentes conseguir comparar texto_para_indexar
    ATUAL contra o texto_indexado JA SALVO e decidir se precisa reindexar
    ou pode pular (sem isso, qualquer reordenacao incidental de dict
    pareceria uma mudanca real e gastaria cota da API sem necessidade)."""
    partes = []

    casa = linha_premissa.get("casa")
    titulo = linha_premissa.get("titulo")
    tickers = linha_premissa.get("tickers") or []
    tipo_documento = linha_premissa.get("tipo_documento")
    premissas = linha_premissa.get("premissas") or []
    projecoes = linha_premissa.get("projecoes") or {}
    recomendacao = linha_premissa.get("recomendacao")
    preco_alvo = linha_premissa.get("preco_alvo")

    if casa:
        partes.append(f"Casa: {casa}")
    if titulo:
        partes.append(f"Titulo: {titulo}")
    if tickers:
        partes.append(f"Tickers: {', '.join(tickers)}")
    if tipo_documento:
        partes.append(f"Tipo de documento: {tipo_documento}")
    if premissas:
        partes.append("Premissas: " + "; ".join(premissas))
    if projecoes:
        projecoes_txt = "; ".join(f"{k}: {v}" for k, v in sorted(projecoes.items()))
        partes.append(f"Projecoes: {projecoes_txt}")
    if recomendacao:
        partes.append(f"Recomendacao: {recomendacao}")
    if preco_alvo is not None:
        partes.append(f"Preco-alvo: {preco_alvo}")

    return "\n".join(partes)


# ============================================================
# INTERNO - persistencia (research_embeddings) e RPC de similaridade
# ============================================================

def _salvar_embedding(link: str, embedding: list, texto_indexado: str, modelo: str) -> bool:
    """Upsert por link na tabela research_embeddings (ver
    sql/research_embeddings.sql) - mesmo padrao try/except de
    data/research/store.py. True se salvou, False se o banco estiver
    fora do ar ou a escrita falhar (nunca lanca excecao)."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        cliente.table("research_embeddings").upsert(
            {
                "link": link,
                "embedding": embedding,
                "texto_indexado": texto_indexado,
                "modelo_embedding": modelo,
                "atualizado_em": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="link",
        ).execute()
        return True
    except Exception:
        return False


def _embeddings_existentes() -> dict | None:
    """{link: {'texto_indexado':..., 'modelo_embedding':...}} de tudo que
    ja esta em research_embeddings - usado por indexar_pendentes pra
    decidir reindexar (ou nao) cada link, e por _links_indexados.
    None se o banco estiver fora do ar (distinto de dict vazio)."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = cliente.table("research_embeddings").select("link, texto_indexado, modelo_embedding").execute()
        return {
            r["link"]: {"texto_indexado": r.get("texto_indexado"), "modelo_embedding": r.get("modelo_embedding")}
            for r in resp.data
        }
    except Exception:
        return None


def _links_indexados() -> set | None:
    """Todos os links ja presentes em research_embeddings (pra saber o
    que falta indexar) - None se o banco estiver fora do ar, distinto de
    set vazio (nenhum link indexado ainda, mas o banco respondeu)."""
    existentes = _embeddings_existentes()
    if existentes is None:
        return None
    return set(existentes.keys())


def _buscar_por_similaridade(embedding_consulta: list, links_candidatos: list = None, limite: int = 8) -> list | None:
    """Chama a RPC match_research_embeddings (ver
    sql/research_embeddings.sql) pra busca por similaridade de cosseno.
    links_candidatos (opcional) restringe a busca a um subconjunto ja
    filtrado estruturalmente (por ticker/casa/data) - None busca na
    tabela inteira. Retorna lista de {'link':..., 'similaridade':...}
    ordenada por similaridade (vem assim da RPC), ou None se o banco/RPC
    estiver fora do ar ou nao existir ainda (projeto sem a migration
    sql/research_embeddings.sql rodada, ou sem pgvector disponivel -
    nunca lanca excecao, quem chama (buscar) trata None como 'busca
    semantica indisponivel')."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = cliente.rpc(
            "match_research_embeddings",
            {
                "query_embedding": embedding_consulta,
                "match_count": limite,
                "filtro_links": links_candidatos if links_candidatos else None,
            },
        ).execute()
        return resp.data
    except Exception:
        return None


# ============================================================
# PUBLICO - pipeline de indexacao incremental
# ============================================================

def indexar_pendentes(limite: int = 30) -> dict:
    """Pipeline de indexacao: le todos os links de research_premissas
    (store.listar_premissas - importado, nunca reimplementado), compara
    com o que ja esta em research_embeddings e processa ate `limite`
    links por chamada (respeita o rate limit do free tier do Gemini -
    NUNCA processa tudo de uma vez). Retorna
    {'processados': N, 'falhas': M, 'pendentes_restantes': K}.

    Incremental DE VERDADE (nao so' 'novo vs ja indexado'): um link que
    JA tem embedding salvo so' e' REPROCESSADO (gera embedding novo,
    gasta cota da API) quando pelo menos UM dos dois mudou desde a
    ultima indexacao:
      - o texto_para_indexar ATUAL e' diferente do texto_indexado salvo
        (ex: research_premissas daquele link foi atualizada - nova
        premissa/projecao extraida depois); OU
      - o modelo de embedding configurado agora (config.
        obter_credenciais_gemini) e' diferente do modelo_embedding salvo
        na linha (embeddings gerados por modelos diferentes NAO sao
        comparaveis entre si na busca por similaridade - trocar de
        modelo precisa reindexar mesmo com texto identico).
    Link com texto E modelo iguais aos ja salvos pula a chamada de
    embedding inteira (sem bater na API de novo pra um dado que nao
    mudou).

    Isolado por item: uma falha individual (embedding=None, upsert que
    falhou num unico link) nunca derruba o lote inteiro - loga e
    continua pro proximo.

    NAO e' chamado por jobs/coordenador.py (outra frente de trabalho vai
    integrar isso depois) - fica pronto e testado aqui, isolado."""
    premissas = store.listar_premissas()
    if premissas is None:
        return {"processados": 0, "falhas": 0, "pendentes_restantes": 0}

    existentes = _embeddings_existentes()
    if existentes is None:
        return {"processados": 0, "falhas": 0, "pendentes_restantes": len(premissas)}

    _, modelo_atual = config.obter_credenciais_gemini()

    a_processar = []
    for linha in premissas:
        link = linha.get("link")
        if not link:
            continue
        texto_atual = _texto_para_indexar(linha)
        salvo = existentes.get(link)
        if (
            salvo is not None
            and salvo.get("texto_indexado") == texto_atual
            and salvo.get("modelo_embedding") == modelo_atual
        ):
            continue  # ja indexado, texto E modelo sem mudanca - pula
        a_processar.append((link, texto_atual))

    lote = a_processar[:limite]

    processados = 0
    falhas = 0
    for link, texto in lote:
        embedding = _gerar_embedding(texto)
        if embedding is None:
            falhas += 1
            continue
        if _salvar_embedding(link, embedding, texto, modelo_atual):
            processados += 1
        else:
            falhas += 1

    return {
        "processados": processados,
        "falhas": falhas,
        "pendentes_restantes": max(len(a_processar) - len(lote), 0),
    }


# ============================================================
# PUBLICO - busca hibrida (estrutural + semantica + lexical)
# ============================================================

def _campos_resultado(item: dict, origem_match: str) -> dict:
    """Monta 1 item de resultado de buscar() - rastreabilidade garantida:
    link/casa/data_publicacao SEMPRE presentes (mesmo que None quando a
    propria linha de origem nao tiver - research_premissas.link e' NOT
    NULL/UNIQUE e casa e' NOT NULL, so' data_publicacao pode faltar,
    ver sql/research_premissas.sql), nunca omitidos do dict."""
    return {
        "link": item.get("link"),
        "casa": item.get("casa"),
        "titulo": item.get("titulo"),
        "data_publicacao": item.get("data_publicacao"),
        "tickers": item.get("tickers") or [],
        "tipo_documento": item.get("tipo_documento"),
        "premissas": item.get("premissas") or [],
        "projecoes": item.get("projecoes") or {},
        "recomendacao": item.get("recomendacao"),
        "preco_alvo": item.get("preco_alvo"),
        "origem_match": origem_match,
    }


def buscar(
    pergunta: str = None,
    ticker: str = None,
    casa=None,
    tipo_documento: str = None,
    data_inicio: str = None,
    data_fim: str = None,
    top_k: int = 8,
) -> dict:
    """Busca hibrida (estrutural + semantica + lexical) na biblioteca
    PERMANENTE de research (research_premissas). Retorno 100%
    ESTRUTURADO e DETERMINISTICO - NUNCA gera texto narrativo via LLM
    aqui (o vetor de embedding da pergunta e' so' matematica de
    similaridade, nao geracao de conteudo):

        {'resultados': [...], 'confianca': 'ALTA'|'MEDIA'|'BAIXA'|
         'SEM_EVIDENCIA', 'aviso': str|None}

    `casa` aceita 3 formas (2026-11-01, expansao multi-casa - pedido do
    Rodrigo): `None` (todas as casas, comportamento padrao), `str` (1
    casa exata, EXATAMENTE o comportamento original - retrocompativel
    com qualquer chamador existente), ou `list[str]`/`tuple[str]` (filtra
    por qualquer uma das casas da lista, via `store.listar_premissas`).
    Repassado direto pra store.listar_premissas, que faz a distincao de
    tipo - este modulo nao duplica essa logica.

    Cada item de resultados traz link/casa/titulo/data_publicacao/
    tickers/tipo_documento/premissas/projecoes/recomendacao/preco_alvo/
    origem_match - link+casa+data_publicacao SEMPRE presentes (chave da
    rastreabilidade: toda citacao da MEMORIA DE RESEARCH na UI precisa
    apontar pra uma publicacao real e identificavel, nunca uma sintese
    sem fonte). Com `casa` sendo uma lista, cada resultado continua
    identificando a SUA PROPRIA casa de origem (campo `casa` do item) -
    nunca uma resposta "combinada" sem fonte clara por item.

    Passos:
      1. Filtro ESTRUTURAL primeiro (store.listar_premissas por
         ticker/casa, depois tipo_documento/periodo em Python sobre o
         resultado) - define o universo de candidatos.
      2. Se `pergunta` foi dada: gera embedding da pergunta e busca por
         similaridade (_buscar_por_similaridade), restrita aos links do
         filtro estrutural.
      3. Busca LEXICAL complementar (substring simples em titulo/
         premissas dos itens ja filtrados estruturalmente) - pega
         correspondencia exata de palavra-chave que a busca semantica
         pode perder.
      4. Combina semantico+lexical (origem_match: 'semantico'/'lexical'/
         'ambos'), dedup por link, ordena (mais recente primeiro dentro
         do mesmo nivel de origem) e corta em top_k.
      5. confianca='SEM_EVIDENCIA' (resultados=[]) quando nao ha
         NENHUMA evidencia - NUNCA inventa resposta. Qualquer degradacao
         (Gemini sem credencial, banco fora do ar, RPC indisponivel)
         vira aviso explicativo, mas a busca estrutural/lexical SEMPRE
         continua funcionando - uma falha na parte semantica nunca
         impede o restante do resultado."""
    avisos = []

    tickers_filtro = [ticker] if ticker else None
    base = store.listar_premissas(tickers=tickers_filtro, casa=casa)
    if base is None:
        return {
            "resultados": [],
            "confianca": "SEM_EVIDENCIA",
            "aviso": "banco de research indisponivel no momento",
        }

    if tipo_documento:
        base = [i for i in base if i.get("tipo_documento") == tipo_documento]
    if data_inicio:
        base = [i for i in base if (i.get("data_publicacao") or "") >= data_inicio]
    if data_fim:
        base = [i for i in base if (i.get("data_publicacao") or "") <= data_fim]

    if not base:
        return {"resultados": [], "confianca": "SEM_EVIDENCIA", "aviso": None}

    por_link = {item["link"]: item for item in base if item.get("link")}
    links_universo = list(por_link.keys())
    pergunta_norm = (pergunta or "").strip()

    if not pergunta_norm:
        # sem pergunta em linguagem natural: so' navegacao pelos filtros
        # estruturais - deterministico, sem ambiguidade nenhuma de
        # interpretacao, por isso confianca ALTA.
        ordenados = sorted(links_universo, key=lambda l: por_link[l].get("data_publicacao") or "", reverse=True)
        resultados = [_campos_resultado(por_link[l], "estrutural") for l in ordenados[:top_k]]
        return {"resultados": resultados, "confianca": "ALTA", "aviso": None}

    origem_por_link = {}

    # 2. busca semantica
    api_key, _ = config.obter_credenciais_gemini()
    if not api_key:
        avisos.append(_AVISO_SEM_CREDENCIAL)
    else:
        embedding_pergunta = _gerar_embedding(pergunta_norm)
        if embedding_pergunta is None:
            avisos.append(_AVISO_FALHA_TECNICA)
        else:
            resultado_semantico = _buscar_por_similaridade(
                embedding_pergunta, links_candidatos=links_universo, limite=max(top_k * 2, top_k)
            )
            if resultado_semantico is None:
                avisos.append(_AVISO_FALHA_TECNICA)
            else:
                for r in resultado_semantico:
                    link = r.get("link")
                    if link in por_link:
                        origem_por_link[link] = "semantico"

    # 3. busca lexical complementar (titulo + premissas, substring simples)
    termo = pergunta_norm.casefold()
    for item in base:
        haystack = " ".join([item.get("titulo") or "", " ".join(item.get("premissas") or [])]).casefold()
        if termo and termo in haystack:
            link = item.get("link")
            if not link:
                continue
            origem_por_link[link] = "ambos" if link in origem_por_link else "lexical"

    if not origem_por_link:
        aviso = " ".join(avisos) if avisos else None
        return {"resultados": [], "confianca": "SEM_EVIDENCIA", "aviso": aviso}

    # 4. combinar - ordena por data desc primeiro (sort estavel), depois
    # por origem (ambos > semantico > lexical) preservando a ordem de
    # data dentro de cada grupo.
    links_match = list(origem_por_link.keys())
    links_match.sort(key=lambda l: por_link[l].get("data_publicacao") or "", reverse=True)
    links_match.sort(key=lambda l: _ORDEM_ORIGEM.get(origem_por_link[l], 9))

    top_links = links_match[:top_k]
    resultados = [_campos_resultado(por_link[l], origem_por_link[l]) for l in top_links]

    origens_top = {origem_por_link[l] for l in top_links}
    if "ambos" in origens_top:
        confianca = "ALTA"
    elif "semantico" in origens_top:
        confianca = "MEDIA"
    else:
        confianca = "BAIXA"

    aviso = " ".join(avisos) if avisos else None
    return {"resultados": resultados, "confianca": confianca, "aviso": aviso}
