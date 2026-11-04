# -*- coding: utf-8 -*-
"""Pareceres dos analistas do Comitê Central.

Cada parecer deriva exclusivamente de dados estruturados já coletados pelos
especialistas. Preço-alvo de research é sempre atribuído à casa que publicou;
o consenso nunca é apresentado como target próprio do Pregão. Ausência de
dados permanece explícita.
"""

from statistics import median

from data.research.sinal import calcular_sinal_comite


def _numero(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def _variacao(metricas, chave):
    return _numero((metricas.get(chave) or {}).get("yoy_variacao_pct"))


def _montar_tese(vies, positivos, negativos, fatos):
    if vies == "POSITIVO":
        abertura = "Leitura construtiva: "
    elif vies == "NEGATIVO":
        abertura = "Leitura cautelosa: "
    elif vies == "MISTO":
        abertura = "Leitura equilibrada, com sinais conflitantes: "
    else:
        return "Dados disponíveis não permitem formar uma tese consistente nesta rodada."
    base = "; ".join(positivos[:3] if vies == "POSITIVO" else negativos[:3] if vies == "NEGATIVO" else fatos[:3])
    texto = abertura + (base or "há fatos observáveis, mas sem direção predominante.")
    if positivos and negativos:
        texto += " O contraponto relevante é: " + "; ".join(negativos[:2] if vies == "POSITIVO" else positivos[:2]) + "."
    return texto


def _adicionar_direcao(lista, nome, valor, unidade="%"):
    if valor is None:
        return
    if valor > 0:
        lista.append(f"{nome}: {valor:+.1f}{unidade} na comparação anual.")
    elif valor < 0:
        lista.append(f"{nome}: {valor:+.1f}{unidade} na comparação anual.")


def _parecer_market(dados):
    fundamentos = dados.get("fundamentos") or {}
    historico = dados.get("fundamentos_historicos") or {}
    setorial = dados.get("comparativo_setorial") or {}
    positivos, negativos, fatos = [], [], []

    roe = _numero(fundamentos.get("roe"))
    margem = _numero(fundamentos.get("margem_liquida"))
    divida = _numero(fundamentos.get("divida_liquida_ebitda"))
    fcf = _numero(fundamentos.get("fluxo_caixa_livre"))
    preco = _numero(fundamentos.get("preco"))

    if roe is not None:
        fatos.append(f"ROE de {roe:.1f}%.")
        (positivos if roe > 0 else negativos).append(
            f"ROE positivo de {roe:.1f}%." if roe > 0 else f"ROE negativo de {roe:.1f}%."
        )
    if margem is not None:
        fatos.append(f"Margem líquida de {margem:.1f}%.")
        (positivos if margem > 0 else negativos).append(
            f"Margem líquida positiva de {margem:.1f}%." if margem > 0 else f"Margem líquida negativa de {margem:.1f}%."
        )
    if divida is not None:
        fatos.append(f"Dívida líquida/EBITDA de {divida:.2f}x.")
        if divida <= 1:
            positivos.append(f"Alavancagem baixa: {divida:.2f}x dívida líquida/EBITDA.")
        elif divida > 3:
            negativos.append(f"Alavancagem elevada: {divida:.2f}x dívida líquida/EBITDA.")
    if fcf is not None:
        fatos.append("Fluxo de caixa livre positivo." if fcf > 0 else "Fluxo de caixa livre negativo." if fcf < 0 else "Fluxo de caixa livre nulo.")
        (positivos if fcf > 0 else negativos if fcf < 0 else fatos).append(
            "Geração de caixa livre positiva." if fcf > 0 else "Consumo de caixa livre." if fcf < 0 else "FCF sem saldo positivo ou negativo."
        )
    receita = ((historico.get("receita_liquida") or {}).get("yoy_pct_serie") or [])
    receita_validada = [_numero(x) for x in receita]
    receita_validada = [x for x in receita_validada if x is not None]
    if receita_validada:
        ultimo = receita_validada[-1]
        fatos.append(f"Receita líquida cresceu {ultimo:+.1f}% YoY no último trimestre disponível.")
        (positivos if ultimo > 0 else negativos if ultimo < 0 else fatos).append(
            f"Receita líquida em {ultimo:+.1f}% YoY."
        )

    pl = _numero(fundamentos.get("pl"))
    pl_setor = _numero(setorial.get("pl_mediana"))
    if pl is not None and pl > 0 and pl_setor is not None and pl_setor > 0:
        rel = pl / pl_setor
        fatos.append(f"P/L de {pl:.1f}x contra mediana setorial de {pl_setor:.1f}x.")
        if rel <= 0.8:
            positivos.append(f"P/L {rel:.2f}x a mediana dos pares (desconto relativo).")
        elif rel >= 1.4:
            negativos.append(f"P/L {rel:.2f}x a mediana dos pares (prêmio relativo).")

    riscos = dados.get("riscos_indicadores") or []
    for risco in riscos:
        if isinstance(risco, str) and risco.strip():
            negativos.append(risco.strip())
    catalisadores = dados.get("catalisadores") or []
    for item in catalisadores:
        if isinstance(item, dict):
            label = item.get("categoria") or item.get("titulo")
            if label:
                fatos.append(f"Catalisador identificado: {label}.")

    if len(positivos) + len(negativos) < 2:
        vies = "SEM BASE SUFICIENTE"
    elif len(positivos) > len(negativos):
        vies = "POSITIVO"
    elif len(negativos) > len(positivos):
        vies = "NEGATIVO"
    else:
        vies = "MISTO"

    recomendacao = {"POSITIVO": "COMPRA", "NEGATIVO": "VENDA", "MISTO": "NEUTRO"}.get(vies, "INSUFICIENTE")
    return {
        "id": "market_researcher", "nome": "Market Researcher — Analista de Empresas",
        "recomendacao": recomendacao,
        "especialidade": "Fundamentos, qualidade do negócio, crescimento e riscos",
        "metodo": "Síntese heurística dos sinais observáveis; compara fatores positivos e negativos, sem gerar fatos por IA.",
        "vies": vies,
        "tese": _montar_tese(vies, positivos, negativos, fatos),
        "pros": positivos, "contras": negativos,
        "preco_alvo": None, "preco_alvo_rotulo": "Não calculado por este analista nesta versão.",
        "preco_atual": preco,
        "fontes": ["Market Researcher", "Valuation Radar", "Earnings Reviewer/CVM"],
    }


def _parecer_earnings(nota):
    if not nota.get("disponivel"):
        return {
            "id": "earnings_reviewer", "nome": "Earnings Reviewer — Analista de Resultados",
            "especialidade": "DRE, balanço, fluxo de caixa e evolução trimestral",
            "vies": "SEM BASE SUFICIENTE",
            "tese": nota.get("motivo") or "Nota de resultados indisponível.",
            "pros": [], "contras": [], "preco_alvo": None,
            "preco_alvo_rotulo": "Não faz parte do escopo do Earnings Reviewer.",
            "periodo": nota.get("periodo_label"),
        }
    metricas = nota.get("metricas") or {}
    positivos, negativos, fatos = [], [], []
    for chave, rotulo in (
        ("receita_liquida", "Receita líquida"),
        ("ebit", "EBIT"),
        ("lucro_liquido_consolidado", "Lucro líquido"),
    ):
        valor = _variacao(metricas, chave)
        if valor is not None:
            fatos.append(f"{rotulo}: {valor:+.1f}% YoY.")
            (positivos if valor > 0 else negativos if valor < 0 else fatos).append(
                f"{rotulo} avançou {valor:+.1f}% YoY." if valor > 0 else f"{rotulo} recuou {valor:+.1f}% YoY." if valor < 0 else f"{rotulo} estável na comparação anual."
            )
    margem = _numero(nota.get("margem_bruta_pct"))
    margem_ant = _numero(nota.get("margem_bruta_yoy_anterior_pct"))
    if margem is not None and margem_ant is not None:
        delta = margem - margem_ant
        fatos.append(f"Margem bruta em {margem:.1f}% ({delta:+.1f} p.p. YoY).")
        (positivos if delta > 0 else negativos if delta < 0 else fatos).append(
            f"Margem bruta expandiu {delta:+.1f} p.p." if delta > 0 else f"Margem bruta contraiu {delta:+.1f} p.p." if delta < 0 else "Margem bruta estável."
        )
    bfc = nota.get("balanco_fluxo_caixa") or {}
    roic = _numero(bfc.get("roic_pct"))
    if roic is not None:
        fatos.append(f"ROIC trimestral não anualizado de {roic:.1f}%.")
        if roic > 0:
            positivos.append(f"ROIC trimestral positivo de {roic:.1f}% (não anualizado).")
        elif roic < 0:
            negativos.append(f"ROIC trimestral negativo de {roic:.1f}% (não anualizado).")
    if len(positivos) + len(negativos) < 2:
        vies = "SEM BASE SUFICIENTE"
    elif len(positivos) > len(negativos):
        vies = "POSITIVO"
    elif len(negativos) > len(positivos):
        vies = "NEGATIVO"
    else:
        vies = "MISTO"
    recomendacao = {"POSITIVO": "COMPRA", "NEGATIVO": "VENDA", "MISTO": "NEUTRO"}.get(vies, "INSUFICIENTE")
    return {
        "id": "earnings_reviewer", "nome": "Analista de Resultados",
        "recomendacao": recomendacao,
        "especialidade": "DRE, balanço, fluxo de caixa e evolução trimestral",
        "metodo": "Compara variações YoY de receita, EBIT, lucro, margem bruta e ROIC quando disponíveis.",
        "vies": vies,
        "tese": f"Resultado {nota.get('periodo_label') or 'mais recente'} — " + _montar_tese(vies, positivos, negativos, fatos),
        "pros": positivos, "contras": negativos, "preco_alvo": None,
        "preco_alvo_rotulo": "Não faz parte do escopo do Earnings Reviewer.",
        "periodo": nota.get("periodo_label"),
        "fontes": nota.get("fontes") or [],
        "limitacoes": nota.get("limitacoes") or [],
    }


def _parecer_valuation(dados, comparador, research=None):
    fundamentos = dados.get("fundamentos") or {}
    setorial = dados.get("comparativo_setorial") or {}
    research = research or []
    alvos_externos = [_numero(item.get("preco_alvo")) for item in research]
    alvos_externos = [x for x in alvos_externos if x is not None and x > 0]
    mediana_research = median(alvos_externos) if len(alvos_externos) >= 2 else None
    minimo = min(alvos_externos) if alvos_externos else None
    maximo = max(alvos_externos) if alvos_externos else None
    dispersao = {"n_casas_com_preco_alvo": len(alvos_externos)}
    preco = _numero(fundamentos.get("preco"))
    pl = _numero(fundamentos.get("pl"))
    pl_setor = _numero(setorial.get("pl_mediana"))

    # Estimativa relativa simples: mantém o lucro por ação implícito
    # constante e aplica a mediana setorial de P/L. Não é DCF nem target
    # de research; só existe com preço, P/L positivo e amostra setorial.
    alvo_proprio = (preco * pl_setor / pl) if (
        preco is not None and preco > 0 and pl is not None and pl > 0
        and pl_setor is not None and pl_setor > 0
    ) else None
    upside_proprio = ((alvo_proprio / preco) - 1) * 100 if alvo_proprio is not None else None
    upside_research = ((mediana_research / preco) - 1) * 100 if (
        mediana_research is not None and preco is not None and preco > 0
    ) else None

    pros, contras = [], []
    if upside_proprio is not None:
        if upside_proprio >= 10:
            vies = "DESCONTO RELATIVO"
            pros.append(f"Preço implícito pelo P/L mediano do setor sugere potencial de {upside_proprio:+.1f}%.")
        elif upside_proprio <= -10:
            vies = "PRÊMIO RELATIVO"
            contras.append(f"Preço implícito pelo P/L mediano do setor sugere risco de ajuste de {upside_proprio:+.1f}%.")
        else:
            vies = "PRÓXIMO À MEDIANA SETORIAL"
            pros.append("Múltiplo próximo à mediana setorial, sem desconto ou prêmio expressivo.")
    else:
        vies = "VALUATION INSUFICIENTE"
    if upside_research is not None:
        (pros if upside_research > 0 else contras if upside_research < 0 else pros).append(
            f"Mediana dos alvos publicados implica potencial de {upside_research:+.1f}%."
        )
    if minimo is not None and maximo is not None:
        fatos = [f"Faixa dos preços-alvo externos: R$ {minimo:.2f} a R$ {maximo:.2f}."]
    else:
        fatos = ["Faixa de preços-alvo externos indisponível."]
    tese = (
        f"Preço atual R$ {preco:.2f}; P/L {pl:.1f}x versus mediana setorial {pl_setor:.1f}x. "
        if preco is not None and pl is not None and pl_setor is not None
        else "Múltiplos insuficientes para comparação setorial. "
    ) + " ".join(fatos)
    recomendacao = ("COMPRA" if upside_proprio is not None and upside_proprio >= 10
                    else "VENDA" if upside_proprio is not None and upside_proprio <= -10
                    else "NEUTRO" if upside_proprio is not None else "INSUFICIENTE")
    return {
        "id": "valuation_reviewer", "nome": "Valuation Reviewer / Model Builder",
        "recomendacao": recomendacao,
        "especialidade": "Múltiplos, comparáveis e preço-alvo",
        "metodo": "Preço atual × P/L mediano setorial ÷ P/L atual; sinal relativo usa limiar de ±10%.",
        "vies": vies, "tese": tese,
        "pros": pros, "contras": contras,
        "preco_alvo": alvo_proprio,
        "preco_alvo_rotulo": "Estimativa mecânica: P/L atual da empresa substituído pela mediana setorial; não é DCF nem preço-alvo de research.",
        "preco_atual": preco, "upside_pct": upside_proprio,
        "preco_alvo_consenso_research": mediana_research,
        "upside_consenso_research_pct": upside_research,
        "faixa_precos_alvo_research": {"minimo": minimo, "maximo": maximo},
        "n_casas_com_preco_alvo": dispersao.get("n_casas_com_preco_alvo"),
    }


def _pareceres_research(comparador, memoria, preco_atual):
    por_casa = {}
    for pub in memoria.get("resultados") or []:
        casa = pub.get("casa")
        if casa and casa not in por_casa:
            por_casa[casa] = pub

    saida = []
    linhas = comparador.get("tabela_comparativa") or []
    casas_vistas = set()
    for linha in linhas:
        casa = linha.get("casa")
        if not casa or "GENIAL" in str(casa).upper() or "XP" in str(casa).upper():
            continue
        casas_vistas.add(casa)
        pub = por_casa.get(casa) or {}
        alvo = _numero(linha.get("preco_alvo"))
        if alvo is None:
            alvo = _numero(pub.get("preco_alvo"))
        upside = ((alvo / preco_atual) - 1) * 100 if alvo is not None and preco_atual is not None and preco_atual > 0 else None
        categoria = str(linha.get("recomendacao_categoria") or "").upper()
        recomendacao = {
            "OTIMISTA": "COMPRA", "NEUTRO": "NEUTRO", "CAUTELOSO": "VENDA",
        }.get(categoria, linha.get("recomendacao_original") or pub.get("recomendacao") or "SEM RECOMENDAÇÃO")
        premissas = pub.get("premissas") or []
        riscos = pub.get("riscos") or []
        projecoes = pub.get("projecoes") or {
            "receita": linha.get("projecao_receita"),
            "margem_ebitda": linha.get("projecao_ebitda_margem"),
            "lucro": linha.get("projecao_lucro"),
        }
        saida.append({
            "casa": casa, "recomendacao": recomendacao,
            "preco_alvo": alvo, "upside_pct": upside,
            "data_publicacao": linha.get("data_publicacao") or pub.get("data_publicacao"),
            "titulo": linha.get("titulo") or pub.get("titulo"),
            "link": linha.get("link") or pub.get("link"),
            "tese": premissas,
            "pros": [], "contras": riscos,
            "projecoes": projecoes,
        })

    # A memória permanente pode ter uma casa que ainda não apareceu na
    # tabela resumida do comparador; preserva a publicação com atribuição.
    for casa, pub in por_casa.items():
        if casa in casas_vistas or not casa or "GENIAL" in str(casa).upper() or "XP" in str(casa).upper():
            continue
        alvo = _numero(pub.get("preco_alvo"))
        upside = ((alvo / preco_atual) - 1) * 100 if alvo is not None and preco_atual is not None and preco_atual > 0 else None
        saida.append({
            "casa": casa, "recomendacao": pub.get("recomendacao") or "SEM RECOMENDAÇÃO",
            "preco_alvo": alvo, "upside_pct": upside,
            "data_publicacao": pub.get("data_publicacao"), "titulo": pub.get("titulo"),
            "link": pub.get("link"), "tese": pub.get("premissas") or [],
            "pros": [], "contras": pub.get("riscos") or [],
            "projecoes": pub.get("projecoes") or {},
        })
    return saida


def montar_pareceres(resultados, ticker=None):
    """Monta pareceres independentes e um resumo de preço-alvo, sem
    fabricar target quando nenhuma fonte publicou valor numérico."""
    resultados = resultados or {}
    analise = (resultados.get("analise_ticker") or {}).get("dados") or {}
    earnings = (resultados.get("resultados_corporativos") or {}).get("dados") or {}
    comparador = (resultados.get("comparador") or {}).get("dados") or {}
    fundamentos = analise.get("fundamentos") or {}
    preco = _numero(fundamentos.get("preco"))

    memoria = (resultados.get("memoria_research") or {}).get("dados") or {}
    research = _pareceres_research(comparador, memoria, preco)
    analistas = [
        _parecer_market(analise),
        _parecer_earnings(earnings),
        _parecer_valuation(analise, comparador, research),
    ]
    alvos = [_numero(item.get("preco_alvo")) for item in research]
    alvos = [x for x in alvos if x is not None and x > 0]
    mediana = median(alvos) if len(alvos) >= 2 else None
    minimo = min(alvos) if alvos else None
    maximo = max(alvos) if alvos else None
    return {
        "ticker": ticker,
        "analistas": analistas,
        "casas_research": research,
        "preco_alvo_consenso": {
            "mediana": mediana,
            "minimo": minimo,
            "maximo": maximo,
            "n_casas": len(alvos),
            "preco_atual": preco,
            "upside_pct": (((mediana / preco) - 1) * 100
                           if mediana is not None and preco is not None and preco > 0 else None),
            "rotulo": "Consenso de preços-alvo publicados; não é estimativa proprietária.",
        },
    }


def montar_sinal_comite(resultados):
    analise = (resultados.get("analise_ticker") or {}).get("dados") or {}
    return calcular_sinal_comite(analise)
