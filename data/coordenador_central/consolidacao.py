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

from math import isfinite

from data.radar import TIPO_CALCULO, TIPO_FATO, TIPO_INSUFICIENTE
from data.research.comparador import _normalizar_recomendacao
from data.coordenador_central.pareceres import montar_pareceres, montar_sinal_comite

CONFIANCA_ALTA = "ALTA"
CONFIANCA_MEDIA = "MEDIA"
CONFIANCA_BAIXA = "BAIXA"
CONFIANCA_INSUFICIENTE = "INSUFICIENTE"

# Rótulo de EXIBIÇÃO pro usuário final - os TIPO_* importados acima são
# constantes internas em CAIXA_COM_UNDERSCORE (ex: "CALCULO_INTERNO"),
# nunca pensadas pra aparecer cruas na tela. Mesmo texto já usado em
# ui/analises_tab.py:_ROTULO_EVIDENCIA (não importado de lá de propósito -
# data/ não deve depender de ui/; mantido em sincronia manualmente, são só
# 3 strings). Achado real na validação visual (2026-11-01): a conclusão
# do Coordenador mostrava "[CALCULO_INTERNO]" cru em vez de "[CÁLCULO
# INTERNO]" - inconsistente com o resto do app.
_ROTULO_EXIBICAO = {
    TIPO_FATO: "FATO",
    TIPO_CALCULO: "CÁLCULO INTERNO",
    TIPO_INSUFICIENTE: "DADO INSUFICIENTE",
}


def _rotulo(tipo: str) -> str:
    return _ROTULO_EXIBICAO.get(tipo, tipo)


def _numero(valor):
    """Normaliza um valor numerico finito; ausencia/invalidez vira None."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if isfinite(numero) else None


# ============================================================
# 1. Resumo executivo
# ============================================================

def _resumo_executivo(resultados: dict, ticker: str = None) -> str:
    acionados = {id_: r for id_, r in resultados.items() if not r.get("pulado")}
    disponiveis = sorted(id_ for id_, r in acionados.items() if r.get("disponivel"))
    indisponiveis = sorted(id_ for id_, r in acionados.items() if not r.get("disponivel"))

    partes = [f"Análise consolidada para {ticker}." if ticker else "Análise consolidada."]
    partes.append(f"{len(disponiveis)} de {len(acionados)} especialista(s) acionado(s) responderam com dado disponível.")
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
    acionados = [r for r in resultados.values() if not r.get("pulado")]
    n_total = len(acionados)
    n_disponiveis = sum(1 for r in acionados if r.get("disponivel"))

    if n_disponiveis == 0:
        return [f"[{_rotulo(TIPO_INSUFICIENTE)}] Nenhum especialista acionado retornou dado disponível - não há base para qualquer conclusão."]

    linhas = [f"[{_rotulo(TIPO_FATO)}] {n_disponiveis} de {n_total} especialista(s) acionado(s) retornaram dado disponível."]

    if divergencia_cross and divergencia_cross.get("divergencias"):
        linhas.append(
            f"[{_rotulo(TIPO_FATO)}] Divergência identificada entre o comparador de casas e a memória de research em "
            f"{len(divergencia_cross['divergencias'])} ponto(s) (ver seção 'divergencias') - este módulo não "
            "infere qual fonte está correta."
        )

    if confianca["categoria"] == CONFIANCA_INSUFICIENTE:
        linhas.append(f"[{_rotulo(TIPO_INSUFICIENTE)}] Evidência insuficiente para uma conclusão de investimento - ver 'pontos_atencao'.")
    else:
        linhas.append(
            f"[{_rotulo(TIPO_CALCULO)}] Confiança da consolidação classificada como {confianca['categoria']} com base na "
            "proporção de especialistas acionados que trouxeram evidência real (ver 'confianca')."
        )
    return linhas


# ============================================================
# 7. Confiança - categórico, NUNCA número de probabilidade sem
# calibração (proibido explicitamente pelo Rodrigo).
# ============================================================

def _confianca(resultados: dict) -> dict:
    acionados = [r for r in resultados.values() if not r.get("pulado")]
    n_total = len(acionados)
    if n_total == 0:
        return {"categoria": CONFIANCA_INSUFICIENTE, "justificativa": "Nenhum especialista foi acionado nesta rodada."}

    n_com_evidencia = sum(1 for r in acionados if r.get("disponivel") and r.get("evidencias"))
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
    de executor.py) nas 7 seções pedidas + o `ticker` da análise (chave
    de conveniência pro cabeçalho da UI - ver ui/coordenador_tab.py,
    achado real 2026-11-11: o ticker só existia dentro de
    pareceres_analistas, a análise consolidada nunca identificava a
    empresa no próprio topo). Sempre devolve essas 8 chaves, mesmo quando
    `resultados` está vazio (todas as seções degradam pra um estado
    explícito de "sem dado", nunca omitidas)."""
    divergencia_cross = _divergencia_cross_comparador_memoria(resultados)
    confianca = _confianca(resultados)
    pareceres = montar_pareceres(resultados, ticker=ticker)
    sinal_comite = montar_sinal_comite(resultados)
    analista_valuation = next(
        (a for a in pareceres.get("analistas", []) if a.get("id") == "valuation_comparables"), {}
    )
    analista_modelo = next(
        (a for a in pareceres.get("analistas", []) if a.get("id") == "model_builder"), {}
    )
    alvo_consenso = pareceres.get("preco_alvo_consenso") or {}
    cenario_base_modelo = (analista_modelo.get("cenarios") or {}).get("base") or {}
    # O DCF do Model Builder tem prioridade. Sem DCF, preserva-se no
    # campo legado a estimativa mecânica por P/L setorial do parecer de
    # valuation, sempre acompanhada do rótulo que impede tratá-la como DCF.
    alvo_modelo = cenario_base_modelo.get("preco_alvo")
    upside_modelo = cenario_base_modelo.get("upside_pct")
    metodo_modelo = analista_modelo.get("preco_alvo_rotulo")
    if alvo_modelo is None:
        alvo_modelo = analista_valuation.get("preco_alvo")
        upside_modelo = analista_valuation.get("upside_pct")
        metodo_modelo = analista_valuation.get("preco_alvo_rotulo")
    sinal_comite["preco_alvo_modelo"] = (
        alvo_modelo if alvo_modelo is not None else analista_modelo.get("preco_alvo")
    )
    fundamentos_sinal = ((resultados.get("analise_ticker") or {}).get("dados") or {}).get("fundamentos") or {}
    sinal_comite["moeda_preco_alvo_modelo"] = fundamentos_sinal.get("moeda") or "R$"
    sinal_comite["upside_modelo_pct"] = _numero(upside_modelo if upside_modelo is not None else analista_modelo.get("upside_pct"))
    sinal_comite["metodo_preco_alvo_modelo"] = metodo_modelo
    sinal_comite["preco_alvo_pl_setorial"] = analista_valuation.get("preco_alvo_pl_setorial")
    sinal_comite["upside_pl_setorial_pct"] = analista_valuation.get("upside_pl_setorial_pct")
    sinal_comite["preco_alvo_consenso"] = alvo_consenso.get("mediana")
    sinal_comite["upside_consenso_pct"] = alvo_consenso.get("upside_pct")
    # Preço atual + data de referência da cotação (data/radar.py:linha_valuation)
    # - campo pedido explicitamente pro cabeçalho da análise (ui/coordenador_tab.py);
    # já existia em fundamentos_sinal, só nunca tinha sido propagado pro
    # consolidado (achado real, auditoria 2026-11-11).
    sinal_comite["preco_atual"] = _numero(fundamentos_sinal.get("preco"))
    sinal_comite["preco_atual_consultado_em"] = fundamentos_sinal.get("consultado_em")
    return {
        "ticker": ticker,
        "resumo_executivo": _resumo_executivo(resultados, ticker),
        "visao_especialistas": _visao_especialistas(resultados),
        "evidencias": _evidencias(resultados),
        "divergencias": {"cross_comparador_memoria": divergencia_cross},
        "pontos_atencao": _pontos_atencao(resultados),
        "conclusao": _conclusao(resultados, divergencia_cross, confianca),
        "confianca": confianca,
        "pareceres_analistas": pareceres,
        "sinal_comite": sinal_comite,
    }
