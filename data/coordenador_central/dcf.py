# -*- coding: utf-8 -*-
"""DCF enxuto e auditável para o Model Builder.

O motor não escolhe WACC, crescimento ou premissas por conta própria.
Só calcula quando recebe premissas explícitas e rastreáveis do pipeline.
"""
from __future__ import annotations

from math import isfinite


CENARIOS = {
    "otimista": "OTIMISTA",
    "base": "BASE",
    "pessimista": "PESSIMISTA",
}


def _num(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    valor = float(valor)
    return valor if isfinite(valor) else None


def calcular_dcf(premissas: dict | None, preco_atual=None) -> dict:
    """Calcula valor justo por ação em 3 cenários.

    Contrato de entrada (valores na moeda do ativo, percentuais em decimal):
      fcf_base: FCF anual TTM reportado pela fonte (não anualizar novamente)
      crescimento_fcf_{otimista,base,pessimista}: crescimento anual
      wacc: custo médio ponderado de capital
      g_terminal: crescimento perpétuo
      divida_liquida: dívida líquida (caixa líquido pode ser negativo)
      acoes: ações implícitas (valor de mercado / cotação)
      fonte_premissas: fonte/documento que suporta as premissas
      data_base: data de referência dos dados

    Projeção explícita de 5 anos; Gordon Growth no valor terminal.
    """
    p = premissas if isinstance(premissas, dict) else {}
    if p.get("motivo_bloqueio"):
        return {
            "disponivel": False, "metodo": "DCF de 5 anos + Gordon Growth",
            "motivo": str(p["motivo_bloqueio"]), "campos_faltantes": [],
            "fonte_premissas": p.get("fonte_premissas"),
            "data_base": p.get("data_base"), "cenarios": {},
        }
    obrigatorias = (
        "fcf_base", "wacc", "g_terminal", "divida_liquida", "acoes",
        "crescimento_fcf_otimista", "crescimento_fcf_base",
        "crescimento_fcf_pessimista",
    )
    valores = {chave: _num(p.get(chave)) for chave in obrigatorias}
    faltantes = [chave for chave, valor in valores.items() if valor is None]
    fonte = p.get("fonte_premissas")
    data_base = p.get("data_base")
    if faltantes:
        return {
            "disponivel": False, "metodo": "DCF de 5 anos + Gordon Growth",
            "motivo": "Premissas insuficientes; nenhuma estimativa foi inventada.",
            "campos_faltantes": faltantes, "fonte_premissas": fonte,
            "data_base": data_base, "cenarios": {},
        }

    fcf = valores["fcf_base"]
    wacc = valores["wacc"]
    g = valores["g_terminal"]
    divida = valores["divida_liquida"]
    acoes = valores["acoes"]
    if fcf <= 0 or acoes <= 0:
        motivo = "FCF normalizado e número de ações precisam ser positivos."
    elif wacc <= 0 or g < 0 or wacc <= g:
        motivo = "WACC precisa ser positivo e maior que o crescimento perpétuo."
    elif any(valores[f"crescimento_fcf_{c}"] <= -1 for c in CENARIOS):
        motivo = "Crescimento anual do FCF precisa ser maior que -100%."
    else:
        motivo = None
    if motivo:
        return {
            "disponivel": False, "metodo": "DCF de 5 anos + Gordon Growth",
            "motivo": motivo, "campos_faltantes": [],
            "fonte_premissas": fonte, "data_base": data_base, "cenarios": {},
        }

    cenarios = {}
    for chave, rotulo in CENARIOS.items():
        crescimento = valores[f"crescimento_fcf_{chave}"]
        pv_fluxos = 0.0
        fcf_projetado = fcf
        projecao = []
        for ano in range(1, 6):
            fcf_projetado *= 1 + crescimento
            valor_presente = fcf_projetado / ((1 + wacc) ** ano)
            pv_fluxos += valor_presente
            projecao.append({
                "ano": ano, "fcf_projetado": fcf_projetado,
                "valor_presente": valor_presente,
            })
        fcf_terminal = fcf_projetado * (1 + g)
        valor_terminal = fcf_terminal / (wacc - g)
        vp_terminal = valor_terminal / ((1 + wacc) ** 5)
        valor_empresa = pv_fluxos + vp_terminal
        valor_patrimonio = valor_empresa - divida
        valor_por_acao = valor_patrimonio / acoes
        upside = (
            (valor_por_acao / float(preco_atual) - 1) * 100
            if _num(preco_atual) is not None and float(preco_atual) > 0 else None
        )
        cenarios[chave] = {
            "rotulo": rotulo, "crescimento_fcf": crescimento,
            "wacc": wacc, "g_terminal": g,
            "valor_presente_fluxos": pv_fluxos,
            "valor_terminal": valor_terminal,
            "valor_presente_terminal": vp_terminal,
            "valor_empresa": valor_empresa,
            "divida_liquida": divida,
            "valor_patrimonio": valor_patrimonio,
            "acoes": acoes, "preco_alvo": valor_por_acao,
            "upside_pct": upside, "projecao": projecao,
        }

    return {
        "disponivel": True, "metodo": "DCF de 5 anos + Gordon Growth",
        "moeda": p.get("moeda") or "moeda da cotação", "unidade_fcf": "mesma unidade monetária do valor de mercado e do FCF",
        "fonte_premissas": fonte, "data_base": data_base,
        "premissas": {
            **valores,
            "origem_divida_liquida": p.get("origem_divida_liquida"),
            "fonte_divida_liquida": p.get("fonte_divida_liquida"),
        },
        "cenarios": cenarios,
        "observacao": "DCF sensível às premissas; confira WACC, crescimento, dívida líquida e ações antes de usar.",
    }


def calcular_sensibilidade_dcf(
    premissas: dict | None,
    preco_atual=None,
    passos_wacc=(-0.02, -0.01, 0.0, 0.01, 0.02),
    passos_crescimento=(-0.02, -0.01, 0.0, 0.01, 0.02),
) -> dict:
    """Matriz 5x5 do preço-alvo-base sob variações de WACC e crescimento.

    As variações são pontos percentuais em decimal (ex.: 0.01 = 1 p.p.).
    Mantém FCF, dívida, ações e crescimento terminal constantes. Não
    substitui premissas nem altera o DCF principal.
    """
    if not isinstance(premissas, dict):
        return {"disponivel": False, "motivo": "Premissas DCF ausentes.", "linhas": []}
    original = calcular_dcf(premissas, preco_atual=preco_atual)
    if not original.get("disponivel"):
        return {"disponivel": False, "motivo": original.get("motivo"), "linhas": []}

    wacc_base = _num(premissas.get("wacc"))
    crescimento_base = _num(premissas.get("crescimento_fcf_base"))
    if wacc_base is None or crescimento_base is None:
        return {"disponivel": False, "motivo": "WACC ou crescimento-base ausente.", "linhas": []}

    linhas = []
    for delta_wacc in passos_wacc:
        wacc = wacc_base + float(delta_wacc)
        celulas = []
        for delta_crescimento in passos_crescimento:
            crescimento = crescimento_base + float(delta_crescimento)
            variacao = dict(premissas)
            variacao["wacc"] = wacc
            variacao["crescimento_fcf_base"] = crescimento
            calculo = calcular_dcf(variacao, preco_atual=preco_atual)
            base_cenario = ((calculo.get("cenarios") or {}).get("base") or {})
            celulas.append({
                "delta_crescimento": float(delta_crescimento),
                "crescimento_fcf": crescimento,
                "preco_alvo": base_cenario.get("preco_alvo"),
                "upside_pct": base_cenario.get("upside_pct"),
                "disponivel": bool(calculo.get("disponivel")),
                "motivo": calculo.get("motivo"),
            })
        linhas.append({
            "delta_wacc": float(delta_wacc),
            "wacc": wacc,
            "celulas": celulas,
        })
    return {
        "disponivel": True,
        "metodo": "Sensibilidade do cenário-base",
        "linhas": linhas,
        "passos_crescimento": [float(x) for x in passos_crescimento],
        "passos_wacc": [float(x) for x in passos_wacc],
        "observacao": "Varia uma premissa por vez em cada eixo; mantém FCF inicial, dívida líquida, ações e crescimento terminal constantes.",
    }
