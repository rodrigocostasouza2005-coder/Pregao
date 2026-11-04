# -*- coding: utf-8 -*-
"""Especialistas independentes de modelagem e revisão de valuation.

Wrappers determinísticos: reaproveitam os motores DCF existentes e não
criam premissas, preços, moedas ou fontes ausentes.
"""
from __future__ import annotations

from data.coordenador_central.dcf import calcular_dcf, calcular_sensibilidade_dcf


def modelar_empresa(ticker: str = None, premissas_dcf: dict | None = None, preco_atual=None, **_kwargs) -> dict:
    ticker = (ticker or "").strip().upper()
    if not isinstance(premissas_dcf, dict):
        return {"disponivel": False, "ticker": ticker, "motivo": "Premissas DCF explícitas não fornecidas; Model Builder não estima taxas automaticamente.", "campos_faltantes": ["premissas_dcf"], "cenarios": {}, "sensibilidade": None}
    calculo = calcular_dcf(premissas_dcf, preco_atual=preco_atual)
    sensibilidade = calcular_sensibilidade_dcf(premissas_dcf, preco_atual=preco_atual) if calculo.get("disponivel") else {"disponivel": False, "motivo": calculo.get("motivo"), "linhas": []}
    return {
        "disponivel": bool(calculo.get("disponivel")),
        "ticker": ticker,
        "metodo": calculo.get("metodo"),
        "moeda": calculo.get("moeda") or premissas_dcf.get("moeda"),
        "preco_atual": preco_atual,
        "cenarios": calculo.get("cenarios") or {},
        "premissas": calculo.get("premissas") or premissas_dcf,
        "fonte_premissas": calculo.get("fonte_premissas") or premissas_dcf.get("fonte_premissas"),
        "data_base": calculo.get("data_base") or premissas_dcf.get("data_base"),
        "sensibilidade": sensibilidade,
        "motivo": calculo.get("motivo"),
        "campos_faltantes": calculo.get("campos_faltantes") or [],
    }


def revisar_valuation(ticker: str = None, model_builder: dict | None = None, **_kwargs) -> dict:
    ticker = (ticker or "").strip().upper()
    modelo = model_builder if isinstance(model_builder, dict) else {}
    if not modelo.get("disponivel"):
        return {"disponivel": False, "ticker": ticker, "motivo": "Model Builder não entregou um DCF válido; revisão independente bloqueada.", "achados": [], "limitacoes": [modelo.get("motivo") or "Modelo indisponível."]}
    cenarios = modelo.get("cenarios") or {}
    chaves = ("pessimista", "base", "otimista")
    alvos = {k: (cenarios.get(k) or {}).get("preco_alvo") for k in chaves}
    ausentes = [k for k, v in alvos.items() if not isinstance(v, (int, float)) or isinstance(v, bool)]
    if ausentes:
        return {"disponivel": False, "ticker": ticker, "motivo": "Cenários sem preço-alvo numérico: " + ", ".join(ausentes), "achados": [], "limitacoes": ["Revisão não substitui premissas ausentes."]}
    ordem = alvos["pessimista"] <= alvos["base"] <= alvos["otimista"]
    achados = []
    if not ordem:
        achados.append({"tipo": "INCONSISTENCIA", "descricao": "Os preços-alvo não respeitam a ordem pessimista ≤ base ≤ otimista."})
    if not modelo.get("fonte_premissas"):
        achados.append({"tipo": "RASTREABILIDADE", "descricao": "Fonte das premissas não identificada."})
    if not modelo.get("data_base"):
        achados.append({"tipo": "RASTREABILIDADE", "descricao": "Data-base do modelo não identificada."})
    sens = modelo.get("sensibilidade") or {}
    if not sens.get("disponivel"):
        achados.append({"tipo": "SENSIBILIDADE", "descricao": "Matriz de sensibilidade indisponível."})
    return {
        "disponivel": True, "ticker": ticker, "aprovado": ordem and not any(a["tipo"] == "RASTREABILIDADE" for a in achados),
        "precos_alvo_revisados": alvos, "moeda": modelo.get("moeda"),
        "achados": achados,
        "limitacoes": ["Revisão determinística; não substitui validação humana das premissas e dos documentos de origem."],
        "fonte_premissas": modelo.get("fonte_premissas"), "data_base": modelo.get("data_base"),
    }


def extrair_model_builder(bruto: dict) -> dict:
    disponivel = bool(bruto.get("disponivel"))
    evidencias = []
    if bruto.get("fonte_premissas"):
        evidencias.append({"fonte": bruto["fonte_premissas"], "data": bruto.get("data_base"), "link": None, "titulo": "Premissas do DCF"})
    resumo = "DCF calculado em três cenários." if disponivel else bruto.get("motivo") or "Modelagem indisponível."
    return {"disponivel": disponivel, "resumo": resumo, "evidencias": evidencias, "motivo_indisponivel": None if disponivel else resumo, "dados": bruto}


def extrair_valuation_reviewer(bruto: dict) -> dict:
    disponivel = bool(bruto.get("disponivel"))
    evidencias = [{"fonte": bruto.get("fonte_premissas"), "data": bruto.get("data_base"), "link": None, "titulo": "Revisão independente do DCF"}] if bruto.get("fonte_premissas") else []
    resumo = ("Revisão concluída: " + ("aprovado." if bruto.get("aprovado") else "com ressalvas.")) if disponivel else bruto.get("motivo") or "Revisão indisponível."
    return {"disponivel": disponivel, "resumo": resumo, "evidencias": evidencias, "motivo_indisponivel": None if disponivel else resumo, "dados": bruto}
