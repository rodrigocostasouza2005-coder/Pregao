# -*- coding: utf-8 -*-
"""Consolidação determinística dos resultados de especialistas (ver
executor.py) nas 7 seções pedidas pelo Rodrigo. ZERO chamada de IA nova
aqui - é composição/agregação sobre o que os especialistas já devolveram
(cada um, por sua vez, pode ou não ter usado IA internamente - isso já é
responsabilidade dele, não deste módulo).

Reaproveita a normalização de recomendação já existente em
data/research/comparador.py (_normalizar_recomendacao) pra comparar
recomendação entre especialistas diferentes - nunca duplica essa lógica.

Rótulos de tipo de evidência (FATO/CALCULO_INTERNO/ESTIMATIVA_TERCEIRO/
HIPOTESE_ANALISTA/DADO_INSUFICIENTE) são os MESMOS já usados em
data/radar.py - importados, nunca reinventados com nomes novos."""

from data.radar import TIPO_CALCULO, TIPO_FATO, TIPO_INSUFICIENTE
from data.research.comparador import _normalizar_recomendacao

CONFIANCA_ALTA = "ALTA"
CONFIANCA_MEDIA = "MEDIA"
CONFIANCA_BAIXA = "BAIXA"
CONFIANCA_INSUFICIENTE = "INSUFICIENTE"


# ============================================================
# 1. Resumo executivo
# ============================================================

def _resumo_executivo(resultados: dict, ticker: str = None) -> str:
    disponiveis = sorted(id_ for id_, r in resultados.items() if r.get("disponivel"))
    indisponiveis = sorted(id_ for id_, r in resultados.items() if not r.get("disponivel"))

    partes = [f"Análise consolidada para {ticker}." if ticker else "Análise consolidada."]
    partes.append(f"{len(disponiveis)} de {len(resultados)} especialista(s) acionado(s) responderam com dado disponível.")
    if indisponiveis:
        partes.append(f"Indisponível nesta rodada: {', '.join(indisponiveis)}.")
    return " ".join(partes)


# ============================================================
# 2. Visão por especialista (tudo, exceto erro_tecnico - nunca exposto)
# ============================================================

def _visao_especialistas(resultados: dict) -> dict:
    return {
        id_: {k: v for k, v in r.items() if k != "erro_tecnico"}
        for id_, r in resultados.items()
    }


# ============================================================
# 3. Evidências consolidadas
# ============================================================

def _evidencias(resultados: dict) -> list:
    evidencias = []
    for especialista_id, r in sorted(resultados.items()):
        for e in (r.get("evidencias") or []):
            evidencias.append({**e, "especialista": especialista_id})
    return evidencias


# ============================================================
# 4. Divergências - cross-check entre comparador e memoria_research
# (mesmo tipo de dado: recomendação/preço-alvo por casa) - reaproveita a
# normalização de recomendação de data/research/comparador.py, nunca
# duplicada aqui.
# ============================================================

def _divergencia_cross_comparador_memoria(resultados: dict) -> dict | None:
    comparador = resultados.get("comparador") or {}
    memoria = resultados.get("memoria_research") or {}
    dados_comparador = comparador.get("dados") or {}
    dados_memoria = memoria.get("dados") or {}

    tabela = dados_comparador.get("tabela_comparativa") or []
    publicacoes_memoria = dados_memoria.get("resultados") or []
    if not tabela or not publicacoes_memoria:
        return None

    # mais recente primeiro por casa (buscar() já ordena por data desc
    # dentro do mesmo nível de origem) - guarda só a 1a (mais recente) por casa.
    por_casa_memoria = {}
    for pub in publicacoes_memoria:
        casa = pub.get("casa")
        if casa and casa not in por_casa_memoria:
            por_casa_memoria[casa] = pub

    divergencias = []
    for linha in tabela:
        casa = linha["casa"]
        pub = por_casa_memoria.get(casa)
        if not pub:
            continue

        categoria_comparador = linha.get("recomendacao_categoria")
        categoria_memoria = _normalizar_recomendacao(pub.get("recomendacao"))
        if categoria_comparador and categoria_memoria and categoria_comparador != categoria_memoria:
            divergencias.append({
                "casa": casa, "tipo": "qualitativa", "campo": "recomendacao",
                "comparador": linha.get("recomendacao_original"), "memoria_research": pub.get("recomendacao"),
            })

        preco_comparador, preco_memoria = linha.get("preco_alvo"), pub.get("preco_alvo")
        if (
            isinstance(preco_comparador, (int, float)) and not isinstance(preco_comparador, bool)
            and isinstance(preco_memoria, (int, float)) and not isinstance(preco_memoria, bool)
            and preco_comparador != preco_memoria
        ):
            divergencias.append({
                "casa": casa, "tipo": "numerica", "campo": "preco_alvo",
                "comparador": preco_comparador, "memoria_research": preco_memoria,
            })

    return {"n_casas_comparadas": len(tabela), "divergencias": divergencias}


def _divergencias(resultados: dict) -> dict:
    return {"cross_comparador_memoria": _divergencia_cross_comparador_memoria(resultados)}


# ============================================================
# 5. Pontos de atenção - determinístico, nunca interpretação
# ============================================================

def _pontos_atencao(resultados: dict) -> list:
    avisos = []
    for especialista_id, r in sorted(resultados.items()):
        if r.get("pulado"):
            avisos.append(f"{especialista_id}: não acionado ({r.get('resumo') or 'decisão do fluxo'}).")
        elif not r.get("disponivel"):
            avisos.append(f"{especialista_id}: indisponível ({r.get('motivo_indisponivel') or 'motivo não especificado'}).")
        elif not r.get("evidencias"):
            avisos.append(f"{especialista_id}: respondeu sem evidência/dado concreto nesta rodada.")

    dados_comparador = (resultados.get("comparador") or {}).get("dados") or {}
    dispersao = dados_comparador.get("dispersao_precos_alvo")
    if dispersao and dispersao.get("amostra_insuficiente"):
        avisos.append(f"comparador: {dispersao.get('resumo')}")

    return avisos


# ============================================================
# 6. Conclusão - síntese curta e determinística, cada afirmação
# rotulada (FATO/CALCULO_INTERNO/DADO_INSUFICIENTE - ver data/radar.py).
# Nunca força uma conclusão quando os dados não permitem.
# ============================================================

def _conclusao(resultados: dict, divergencia_cross: dict | None, confianca: dict) -> list:
    n_total = len(resultados)
    n_disponiveis = sum(1 for r in resultados.values() if r.get("disponivel"))

    if n_disponiveis == 0:
        return [f"[{TIPO_INSUFICIENTE}] Nenhum especialista acionado retornou dado disponível - não há base para qualquer conclusão."]

    linhas = [f"[{TIPO_FATO}] {n_disponiveis} de {n_total} especialista(s) acionado(s) retornaram dado disponível."]

    if divergencia_cross and divergencia_cross.get("divergencias"):
        linhas.append(
            f"[{TIPO_FATO}] Divergência identificada entre o comparador de casas e a memória de research em "
            f"{len(divergencia_cross['divergencias'])} ponto(s) (ver seção 'divergencias') - este módulo não "
            "infere qual fonte está correta."
        )

    if confianca["categoria"] == CONFIANCA_INSUFICIENTE:
        linhas.append(f"[{TIPO_INSUFICIENTE}] Evidência insuficiente para uma conclusão de investimento - ver 'pontos_atencao'.")
    else:
        linhas.append(
            f"[{TIPO_CALCULO}] Confiança da consolidação classificada como {confianca['categoria']} com base na "
            "proporção de especialistas acionados que trouxeram evidência real (ver 'confianca')."
        )
    return linhas


# ============================================================
# 7. Confiança - categórico, NUNCA número de probabilidade sem
# calibração (proibido explicitamente pelo Rodrigo).
# ============================================================

def _confianca(resultados: dict) -> dict:
    n_total = len(resultados)
    if n_total == 0:
        return {"categoria": CONFIANCA_INSUFICIENTE, "justificativa": "Nenhum especialista foi acionado nesta rodada."}

    n_com_evidencia = sum(1 for r in resultados.values() if r.get("disponivel") and r.get("evidencias"))
    proporcao = n_com_evidencia / n_total

    if n_com_evidencia >= 2 and proporcao >= 0.75:
        categoria = CONFIANCA_ALTA
    elif proporcao >= 0.5:
        categoria = CONFIANCA_MEDIA
    elif n_com_evidencia >= 1:
        categoria = CONFIANCA_BAIXA
    else:
        categoria = CONFIANCA_INSUFICIENTE

    justificativa = f"{n_com_evidencia} de {n_total} especialista(s) acionado(s) trouxeram evidência real (não só resposta vazia)."
    return {"categoria": categoria, "justificativa": justificativa}


# ============================================================
# API pública
# ============================================================

def consolidar(resultados: dict, ticker: str = None) -> dict:
    """Consolida os resultados (dict especialista_id -> resultado padrão
    de executor.py) nas 7 seções pedidas. Sempre devolve as 7 chaves,
    mesmo quando `resultados` está vazio (todas as seções degradam pra
    um estado explícito de "sem dado", nunca omitidas)."""
    divergencia_cross = _divergencia_cross_comparador_memoria(resultados)
    confianca = _confianca(resultados)
    return {
        "resumo_executivo": _resumo_executivo(resultados, ticker),
        "visao_especialistas": _visao_especialistas(resultados),
        "evidencias": _evidencias(resultados),
        "divergencias": {"cross_comparador_memoria": divergencia_cross},
        "pontos_atencao": _pontos_atencao(resultados),
        "conclusao": _conclusao(resultados, divergencia_cross, confianca),
        "confianca": confianca,
    }
