# -*- coding: utf-8 -*-
"""DCF operacional de cinco anos, com drivers explícitos e auditáveis."""
from __future__ import annotations
from math import isfinite

ANOS = 5
ESCALARES = ("receita_base", "aliquota_impostos", "wacc", "g_terminal", "divida_liquida", "acoes")
VETORES = ("crescimento_receita", "margem_ebit", "da_sobre_receita", "capex_sobre_receita", "capital_giro_sobre_receita_incremental")


def _numero(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    n = float(valor)
    return n if isfinite(n) else None


def calcular_dcf_operacional(premissas: dict | None, preco_atual=None) -> dict:
    """FCF = EBIT*(1-imposto)+D&A-CAPEX-variação do capital de giro.

    Percentuais em decimal. Cada vetor contém cinco valores anuais.
    Capital de giro incide sobre a variação da receita; sinal positivo
    representa consumo de caixa. Nenhuma premissa é presumida.
    """
    p = premissas if isinstance(premissas, dict) else {}
    faltantes = [k for k in ESCALARES + VETORES if p.get(k) is None]
    if faltantes:
        return {"disponivel": False, "metodo": "DCF operacional de 5 anos + Gordon Growth",
                "motivo": "Premissas operacionais insuficientes; nenhuma taxa foi presumida.",
                "campos_faltantes": faltantes, "projecao": []}
    e = {k: _numero(p[k]) for k in ESCALARES}
    if any(v is None for v in e.values()):
        return {"disponivel": False, "metodo": "DCF operacional de 5 anos + Gordon Growth",
                "motivo": "Há premissas escalares não numéricas ou não finitas.",
                "campos_faltantes": [k for k,v in e.items() if v is None], "projecao": []}
    v = {}
    for k in VETORES:
        if not isinstance(p[k], (list, tuple)) or len(p[k]) != ANOS:
            return {"disponivel": False, "metodo": "DCF operacional de 5 anos + Gordon Growth",
                    "motivo": f"{k} precisa conter exatamente cinco valores anuais.",
                    "campos_faltantes": [k], "projecao": []}
        v[k] = [_numero(x) for x in p[k]]
        if any(x is None for x in v[k]):
            return {"disponivel": False, "metodo": "DCF operacional de 5 anos + Gordon Growth",
                    "motivo": f"{k} contém valor não numérico ou não finito.",
                    "campos_faltantes": [k], "projecao": []}
    if e["receita_base"] <= 0 or e["acoes"] <= 0:
        motivo = "Receita-base e quantidade de ações precisam ser positivas."
    elif not 0 <= e["aliquota_impostos"] < 1:
        motivo = "Alíquota de impostos deve estar entre 0% e 100%."
    elif e["wacc"] <= 0 or e["g_terminal"] < 0 or e["wacc"] <= e["g_terminal"]:
        motivo = "WACC precisa ser positivo e maior que o crescimento perpétuo."
    elif any(x <= -1 for x in v["crescimento_receita"]):
        motivo = "Crescimento da receita precisa ser maior que -100%."
    elif any(x < 0 for x in v["da_sobre_receita"] + v["capex_sobre_receita"]):
        motivo = "D&A e CAPEX sobre receita não podem ser negativos."
    else:
        motivo = None
    if motivo:
        return {"disponivel": False, "metodo": "DCF operacional de 5 anos + Gordon Growth",
                "motivo": motivo, "campos_faltantes": [], "projecao": []}

    receita, receita_anterior = e["receita_base"], e["receita_base"]
    projecao, vp_fluxos = [], 0.0
    for i in range(ANOS):
        receita *= 1 + v["crescimento_receita"][i]
        ebit = receita * v["margem_ebit"][i]
        nopat = ebit * (1 - e["aliquota_impostos"])
        da = receita * v["da_sobre_receita"][i]
        capex = receita * v["capex_sobre_receita"][i]
        delta_cg = (receita - receita_anterior) * v["capital_giro_sobre_receita_incremental"][i]
        fcf = nopat + da - capex - delta_cg
        vp = fcf / ((1 + e["wacc"]) ** (i + 1))
        vp_fluxos += vp
        projecao.append({"ano": i+1, "receita": receita, "crescimento_receita": v["crescimento_receita"][i],
                         "margem_ebit": v["margem_ebit"][i], "ebit": ebit,
                         "impostos_operacionais": ebit*e["aliquota_impostos"], "nopat": nopat,
                         "depreciacao_amortizacao": da, "capex": capex,
                         "variacao_capital_giro": delta_cg, "fcf": fcf, "valor_presente_fcf": vp})
        receita_anterior = receita
    fcf5 = projecao[-1]["fcf"]
    fcf_terminal = fcf5 * (1 + e["g_terminal"])
    if fcf_terminal <= 0:
        return {"disponivel": False, "metodo": "DCF operacional de 5 anos + Gordon Growth",
                "motivo": "FCF terminal precisa ser positivo para aplicar Gordon Growth.",
                "campos_faltantes": [], "projecao": projecao}
    vt = fcf_terminal / (e["wacc"] - e["g_terminal"])
    vp_terminal = vt / ((1 + e["wacc"]) ** ANOS)
    valor_empresa = vp_fluxos + vp_terminal
    patrimonio = valor_empresa - e["divida_liquida"]
    alvo = patrimonio / e["acoes"]
    preco = _numero(preco_atual)
    return {"disponivel": True, "metodo": "DCF operacional de 5 anos + Gordon Growth",
            "moeda": p.get("moeda") or "moeda da cotação", "preco_alvo": alvo,
            "upside_pct": (alvo/preco-1)*100 if preco is not None and preco > 0 else None,
            "valor_presente_fluxos": vp_fluxos, "fcf_terminal_base": fcf5,
            "valor_terminal": vt, "valor_presente_terminal": vp_terminal,
            "valor_empresa": valor_empresa, "divida_liquida": e["divida_liquida"],
            "valor_patrimonio": patrimonio, "acoes": e["acoes"], "projecao": projecao,
            "premissas": p, "fonte_premissas": p.get("fonte_premissas"),
            "data_base": p.get("data_base"),
            "observacao": "Premissas operacionais informadas pelo usuário; não são previsões automáticas."}
