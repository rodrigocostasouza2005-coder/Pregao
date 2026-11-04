# -*- coding: utf-8 -*-
"""Motor quantitativo inicial do Comitê de Investimentos.

Transforma fundamentos, série CVM, comparação setorial e research
estruturado em um sinal rastreável: COMPRA, NEUTRO, VENDA ou
INSUFICIENTE. Não usa XP/Genial como dependência e não inventa dados.
É uma regra determinística auditável, não uma previsão probabilística.
"""

from math import isfinite


def _numero(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    valor = float(valor)
    return valor if isfinite(valor) else None


def _normalizar_recomendacao(valor):
    texto = str(valor or "").strip().upper()
    if any(x in texto for x in ("COMPRA", "BUY", "OUTPERFORM", "OVERWEIGHT")):
        return "COMPRA"
    if any(x in texto for x in ("VENDA", "SELL", "UNDERPERFORM", "UNDERWEIGHT")):
        return "VENDA"
    if any(x in texto for x in ("NEUTRO", "NEUTRAL", "HOLD", "MANTER", "MARKET PERFORM")):
        return "NEUTRO"
    return None


def _adicionar(criterios, grupo, pontos, justificativa, fonte):
    criterios.append({
        "grupo": grupo, "pontos": pontos,
        "justificativa": justificativa, "fonte": fonte,
    })


def calcular_sinal_comite(analise: dict) -> dict:
    """Calcula sinal com guardrails de cobertura e frescor.

    Pontuação: rentabilidade, alavancagem, geração de caixa, crescimento,
    valuation relativo e research independente. Compra >= +4; venda <= -4;
    faixa intermediária = neutro. Sem pelo menos 3 dimensões observáveis
    (e preço válido), retorna INSUFICIENTE. Fundamento desatualizado impede
    sinal direcional.
    """
    analise = analise or {}
    fundamentos = analise.get("fundamentos") or {}
    historico = analise.get("fundamentos_historicos") or {}
    setorial = analise.get("comparativo_setorial") or {}
    cobertura = analise.get("cobertura_research") or {}
    criterios = []
    dimensoes = set()

    preco = _numero(fundamentos.get("preco"))
    if preco is None or preco <= 0:
        return {
            "sinal": "INSUFICIENTE", "score": None, "confianca": "INSUFICIENTE",
            "justificativa": "Cotação válida não disponível; o comitê não emite sinal direcional.",
            "criterios": [], "dimensoes_avaliadas": 0,
            "aviso": "Aguarde a atualização de preço e fundamentos.",
        }

    roe = _numero(fundamentos.get("roe"))
    margem = _numero(fundamentos.get("margem_liquida"))
    divida = _numero(fundamentos.get("divida_liquida_ebitda"))
    fcf = _numero(fundamentos.get("fluxo_caixa_livre"))
    pl = _numero(fundamentos.get("pl"))
    if roe is not None:
        dimensoes.add("rentabilidade")
        pontos = 2 if roe >= 18 else (1 if roe >= 12 else (-2 if roe < 5 else 0))
        _adicionar(criterios, "Rentabilidade", pontos,
                   f"ROE de {roe:.1f}%: " + ("forte retorno sobre patrimônio" if pontos > 0 else "rentabilidade fraca" if pontos < 0 else "faixa intermediária"),
                   "Fundamentos atuais")
    if margem is not None:
        dimensoes.add("margem")
        pontos = 1 if margem >= 15 else (-2 if margem < 0 else (-1 if margem < 5 else 0))
        _adicionar(criterios, "Margem", pontos,
                   f"Margem líquida de {margem:.1f}%: " + ("margem robusta" if pontos > 0 else "margem pressionada" if pontos < 0 else "sem sinal forte"),
                   "Fundamentos atuais")
    if divida is not None:
        dimensoes.add("alavancagem")
        pontos = 1 if divida <= 1 else (-3 if divida > 4 else (-2 if divida > 3 else 0))
        _adicionar(criterios, "Alavancagem", pontos,
                   f"Dívida líquida/EBITDA de {divida:.2f}x: " + ("baixa alavancagem" if pontos > 0 else "alavancagem elevada" if pontos < 0 else "alavancagem administrável"),
                   "Fundamentos atuais")
    if fcf is not None:
        dimensoes.add("caixa")
        pontos = 1 if fcf > 0 else (-2 if fcf < 0 else 0)
        _adicionar(criterios, "Geração de caixa", pontos,
                   "Fluxo de caixa livre positivo" if pontos > 0 else "Fluxo de caixa livre negativo" if pontos < 0 else "Fluxo de caixa livre nulo",
                   "Fundamentos atuais")

    receita = (historico.get("receita_liquida") or {}).get("yoy_pct_serie") or []
    receita_validada = [_numero(x) for x in receita]
    receita_validada = [x for x in receita_validada if x is not None]
    if receita_validada:
        dimensoes.add("crescimento")
        ultimo = receita_validada[-1]
        pontos = 2 if ultimo >= 10 else (1 if ultimo > 0 else (-2 if ultimo < -5 else 0))
        _adicionar(criterios, "Crescimento", pontos,
                   f"Receita líquida: {ultimo:+.1f}% YoY no último trimestre disponível",
                   "Série trimestral CVM")

    pl_setor = _numero(setorial.get("pl_mediana"))
    if pl is not None and pl > 0 and pl_setor is not None and pl_setor > 0:
        dimensoes.add("valuation")
        relacao = pl / pl_setor
        pontos = 1 if relacao <= 0.8 else (-2 if relacao >= 1.8 else (-1 if relacao >= 1.4 else 0))
        _adicionar(criterios, "Valuation relativo", pontos,
                   f"P/L {pl:.1f}x versus mediana setorial {pl_setor:.1f}x ({relacao:.2f}x a mediana)",
                   "Fundamentos atuais + comparação setorial")

    # Só considera casas independentes efetivamente coletadas. XP e Genial
    # ficam explicitamente fora do universo decisório por indisponibilidade.
    casas_excluidas = ("GENIAL", "XP")
    recomendacoes = {}
    for item in cobertura.get("cobertura") or []:
        casa = str(item.get("casa") or "").upper()
        rec = _normalizar_recomendacao(item.get("recomendacao"))
        if casa and not any(nome in casa for nome in casas_excluidas) and rec:
            recomendacoes.setdefault(casa, rec)
    if len(recomendacoes) >= 2:
        dimensoes.add("research")
        contagem = {sinal: sum(1 for r in recomendacoes.values() if r == sinal)
                    for sinal in ("COMPRA", "NEUTRO", "VENDA")}
        maior = max(contagem.values())
        lideres = [s for s, n in contagem.items() if n == maior]
        pontos = 2 if lideres == ["COMPRA"] else (-2 if lideres == ["VENDA"] else 0)
        _adicionar(criterios, "Research independente", pontos,
                   f"{len(recomendacoes)} casas independentes: " +
                   ", ".join(f"{casa}={rec}" for casa, rec in sorted(recomendacoes.items())),
                   "Publicações estruturadas armazenadas")
    
    score = sum(c["pontos"] for c in criterios)
    desatualizado = bool(fundamentos.get("desatualizado"))
    if len(dimensoes) < 3:
        sinal = "INSUFICIENTE"
        justificativa = f"Apenas {len(dimensoes)} dimensões independentes puderam ser avaliadas; mínimo exigido: 3."
    elif desatualizado:
        sinal = "NEUTRO"
        justificativa = "Fundamentos sinalizados como desatualizados; o comitê bloqueia uma conclusão direcional até a atualização."
    elif score >= 4:
        sinal = "COMPRA"
        justificativa = f"Saldo quantitativo positivo ({score:+d}) em {len(dimensoes)} dimensões avaliadas."
    elif score <= -4:
        sinal = "VENDA"
        justificativa = f"Saldo quantitativo negativo ({score:+d}) em {len(dimensoes)} dimensões avaliadas."
    else:
        sinal = "NEUTRO"
        justificativa = f"Pontuação de {score:+d}: evidências sem assimetria suficiente para sinal direcional."

    if sinal == "INSUFICIENTE":
        confianca = "INSUFICIENTE"
    elif desatualizado or len(dimensoes) == 3:
        confianca = "BAIXA"
    elif len(dimensoes) >= 5 and historico.get("disponivel") is True:
        confianca = "ALTA"
    else:
        confianca = "MÉDIA"

    favoraveis = [c["justificativa"] for c in criterios if c["pontos"] > 0]
    contrarios = [c["justificativa"] for c in criterios if c["pontos"] < 0]
    return {
        "sinal": sinal, "score": score, "confianca": confianca,
        "justificativa": justificativa, "criterios": criterios,
        "dimensoes_avaliadas": len(dimensoes),
        "favoraveis": favoraveis, "contrarios": contrarios,
        "aviso": "Sinal quantitativo inicial e auditável; não é recomendação personalizada nem probabilidade de retorno. Revise as evidências e os riscos antes de operar.",
    }
