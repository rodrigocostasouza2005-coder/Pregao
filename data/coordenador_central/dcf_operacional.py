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
            "margem_seguranca_pct": (1 - preco/alvo)*100 if preco is not None and preco > 0 and alvo > 0 else None,
            "valor_presente_fluxos": vp_fluxos, "fcf_terminal_base": fcf5,
            "valor_terminal": vt, "valor_presente_terminal": vp_terminal,
            "valor_empresa": valor_empresa, "divida_liquida": e["divida_liquida"],
            "valor_patrimonio": patrimonio, "acoes": e["acoes"], "projecao": projecao,
            "premissas": p, "fonte_premissas": p.get("fonte_premissas"),
            "data_base": p.get("data_base"),
            "observacao": "Premissas operacionais informadas pelo usuário; não são previsões automáticas."}


# ============================================================================
# Extensões de apresentação (cenários + sensibilidade) - adicionadas sem
# alterar calcular_dcf_operacional acima. Ambas são composições puras sobre
# a função já testada: constroem variações explícitas das premissas
# recebidas e chamam calcular_dcf_operacional de novo pra cada variação -
# nenhuma taxa/premissa nova é inventada, só reaproveitada com um delta que
# quem chamou escolheu (default 0 = sem variação, nunca um número
# presumido).
# ============================================================================

CENARIOS_OPERACIONAL = {
    "otimista": "OTIMISTA",
    "base": "BASE",
    "pessimista": "PESSIMISTA",
}


def calcular_cenarios_dcf_operacional(
    premissas: dict | None,
    delta_otimista_pp: float = 0.0,
    delta_pessimista_pp: float = 0.0,
    preco_atual=None,
) -> dict:
    """Três cenários do DCF operacional, a partir das MESMAS premissas
    anuais recebidas - "base" é o cálculo normal; "otimista"/"pessimista"
    somam `delta_*_pp` (pontos percentuais, já em escala "pp" - ex.: 2.0 =
    +2 p.p.) ao crescimento de receita de TODOS os cinco anos, mantendo
    margem, D&A, CAPEX, capital de giro, WACC e crescimento terminal
    intactos. Os deltas são escolha explícita de quem chama (default 0.0 =
    cenário idêntico ao base) - nunca um otimismo/pessimismo inventado
    pelo motor.
    """
    p = premissas if isinstance(premissas, dict) else {}
    faltantes = [k for k in ESCALARES + VETORES if p.get(k) is None]
    if faltantes:
        return {
            "disponivel": False,
            "motivo": "Premissas operacionais insuficientes; nenhuma taxa foi presumida.",
            "campos_faltantes": faltantes, "cenarios": {},
        }
    deltas = {
        "pessimista": _numero(delta_pessimista_pp),
        "base": 0.0,
        "otimista": _numero(delta_otimista_pp),
    }
    if any(v is None for v in deltas.values()):
        return {"disponivel": False, "motivo": "Delta de cenário não numérico ou não finito.", "cenarios": {}}

    cenarios = {}
    algum_disponivel = False
    for chave, rotulo in CENARIOS_OPERACIONAL.items():
        delta = deltas[chave] / 100
        variacao = dict(p)
        crescimento_base = p.get("crescimento_receita")
        if isinstance(crescimento_base, (list, tuple)) and len(crescimento_base) == ANOS:
            variacao["crescimento_receita"] = [
                (_numero(x) + delta) if _numero(x) is not None else None for x in crescimento_base
            ]
        resultado = calcular_dcf_operacional(variacao, preco_atual=preco_atual)
        resultado["rotulo"] = rotulo
        resultado["delta_crescimento_pp"] = deltas[chave]
        cenarios[chave] = resultado
        algum_disponivel = algum_disponivel or bool(resultado.get("disponivel"))

    return {
        "disponivel": algum_disponivel,
        "metodo": "DCF operacional - 3 cenários (delta uniforme no crescimento de receita)",
        "cenarios": cenarios,
        "observacao": (
            "Otimista/pessimista somam o delta informado (p.p.) ao crescimento de receita de "
            "todos os anos; margem, D&A, CAPEX, capital de giro, WACC e g terminal não mudam "
            "entre cenários."
        ),
    }


def calcular_sensibilidade_dcf_operacional(
    premissas: dict | None,
    preco_atual=None,
    passos_wacc=(-0.02, -0.01, 0.0, 0.01, 0.02),
    passos_g=(-0.01, -0.005, 0.0, 0.005, 0.01),
) -> dict:
    """Matriz do preço-alvo sob variações de WACC (linhas) x crescimento
    terminal (colunas), mantendo receita-base e todos os vetores anuais
    constantes. Mesma lógica de calcular_sensibilidade_dcf (data/
    coordenador_central/dcf.py), adaptada ao motor operacional - varia uma
    premissa por vez a partir do valor que quem chamou informou, nunca
    substitui por um número presumido.
    """
    p = premissas if isinstance(premissas, dict) else {}
    base = calcular_dcf_operacional(p, preco_atual=preco_atual)
    if not base.get("disponivel"):
        return {"disponivel": False, "motivo": base.get("motivo") or "Premissas insuficientes.", "linhas": []}

    wacc_base = _numero(p.get("wacc"))
    g_base = _numero(p.get("g_terminal"))
    if wacc_base is None or g_base is None:
        return {"disponivel": False, "motivo": "WACC ou g terminal ausente.", "linhas": []}

    linhas = []
    for delta_wacc in passos_wacc:
        wacc = wacc_base + float(delta_wacc)
        celulas = []
        for delta_g in passos_g:
            g = g_base + float(delta_g)
            variacao = dict(p)
            variacao["wacc"] = wacc
            variacao["g_terminal"] = g
            calculo = calcular_dcf_operacional(variacao, preco_atual=preco_atual)
            celulas.append({
                "delta_g": float(delta_g), "g_terminal": g,
                "preco_alvo": calculo.get("preco_alvo"),
                "upside_pct": calculo.get("upside_pct"),
                "disponivel": bool(calculo.get("disponivel")),
                "motivo": calculo.get("motivo"),
            })
        linhas.append({"delta_wacc": float(delta_wacc), "wacc": wacc, "celulas": celulas})

    return {
        "disponivel": True,
        "metodo": "Sensibilidade do DCF operacional (WACC x crescimento terminal)",
        "linhas": linhas,
        "passos_g": [float(x) for x in passos_g],
        "passos_wacc": [float(x) for x in passos_wacc],
        "preco_alvo_base": base.get("preco_alvo"),
        "observacao": (
            "Varia WACC e crescimento terminal um em relação ao outro; mantém receita-base, "
            "margens, D&A, CAPEX, capital de giro, dívida líquida e ações constantes."
        ),
    }
