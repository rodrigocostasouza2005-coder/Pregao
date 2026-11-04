# -*- coding: utf-8 -*-
"""Pareceres dos analistas do Comitê Central.

Cada parecer deriva exclusivamente de dados estruturados já coletados pelos
especialistas. Preço-alvo de research é sempre atribuído à casa que publicou;
o consenso nunca é apresentado como target próprio do Pregão. Ausência de
dados permanece explícita.
"""

from data.research.sinal import calcular_sinal_comite


def _numero(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def _variacao(metricas, chave):
    return _numero((metricas.get(chave) or {}).get("yoy_variacao_pct"))


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

    return {
        "id": "market_researcher", "nome": "Analista de Empresas",
        "especialidade": "Fundamentos, qualidade do negócio, crescimento e riscos",
        "vies": vies,
        "tese": " ".join(fatos) if fatos else "Fundamentos estruturados não disponíveis nesta rodada.",
        "pros": positivos, "contras": negativos,
        "preco_alvo": None, "preco_alvo_rotulo": "Não calculado por este analista nesta versão.",
        "preco_atual": preco,
        "fontes": ["Market Researcher", "Valuation Radar", "Earnings Reviewer/CVM"],
    }


def _parecer_earnings(nota):
    if not nota.get("disponivel"):
        return {
            "id": "earnings_reviewer", "nome": "Analista de Resultados",
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
    return {
        "id": "earnings_reviewer", "nome": "Analista de Resultados",
        "especialidade": "DRE, balanço, fluxo de caixa e evolução trimestral",
        "vies": vies,
        "tese": f"Resultado {nota.get('periodo_label') or 'mais recente'}: " + (" ".join(fatos) if fatos else "métricas comparáveis insuficientes."),
        "pros": positivos, "contras": negativos, "preco_alvo": None,
        "preco_alvo_rotulo": "Não faz parte do escopo do Earnings Reviewer.",
        "periodo": nota.get("periodo_label"),
        "fontes": nota.get("fontes") or [],
        "limitacoes": nota.get("limitacoes") or [],
    }


def _parecer_valuation(dados, comparador):
    fundamentos = dados.get("fundamentos") or {}
    dispersao = comparador.get("dispersao_precos_alvo") or {}
    preco = _numero(fundamentos.get("preco"))
    mediana = _numero(dispersao.get("mediana"))
    minimo = _numero(dispersao.get("minimo"))
    maximo = _numero(dispersao.get("maximo"))
    upside = ((mediana / preco) - 1) * 100 if mediana is not None and preco is not None and preco > 0 else None
    if mediana is None:
        vies = "SEM PREÇO-ALVO PUBLICADO"
        tese = "Não há amostra numérica suficiente de preços-alvo publicados pelas casas monitoradas."
    elif upside is None:
        vies = "PREÇO ATUAL INDISPONÍVEL"
        tese = f"Mediana dos preços-alvo publicados: R$ {mediana:.2f}; cotação atual indisponível para calcular potencial."
    elif upside > 10:
        vies = "POTENCIAL POSITIVO"
        tese = f"Mediana dos preços-alvo publicados: R$ {mediana:.2f}, potencial indicativo de {upside:+.1f}% ante cotação de R$ {preco:.2f}."
    elif upside < -10:
        vies = "POTENCIAL NEGATIVO"
        tese = f"Mediana dos preços-alvo publicados: R$ {mediana:.2f}, potencial indicativo de {upside:+.1f}% ante cotação de R$ {preco:.2f}."
    else:
        vies = "POTENCIAL LIMITADO"
        tese = f"Mediana dos preços-alvo publicados: R$ {mediana:.2f}, potencial indicativo de {upside:+.1f}% ante cotação de R$ {preco:.2f}."
    return {
        "id": "valuation_reviewer", "nome": "Analista de Valuation",
        "especialidade": "Múltiplos, comparáveis e preço-alvo de research",
        "vies": vies, "tese": tese,
        "pros": [f"Menor preço-alvo publicado: R$ {minimo:.2f}." ] if minimo is not None else [],
        "contras": [f"Maior preço-alvo publicado: R$ {maximo:.2f}." ] if maximo is not None else [],
        "preco_alvo": mediana,
        "preco_alvo_rotulo": "Mediana das casas monitoradas; não é target proprietário do Pregão.",
        "preco_atual": preco, "upside_pct": upside,
        "faixa_precos_alvo": {"minimo": minimo, "maximo": maximo},
        "n_casas_com_preco_alvo": dispersao.get("n_casas_com_preco_alvo"),
    }


def _pareceres_research(comparador, preco_atual):
    saida = []
    for linha in comparador.get("tabela_comparativa") or []:
        casa = linha.get("casa")
        if not casa or "GENIAL" in str(casa).upper() or "XP" in str(casa).upper():
            continue
        alvo = _numero(linha.get("preco_alvo"))
        upside = ((alvo / preco_atual) - 1) * 100 if alvo is not None and preco_atual is not None and preco_atual > 0 else None
        categoria = str(linha.get("recomendacao_categoria") or "").upper()
        recomendacao = {
            "OTIMISTA": "COMPRA", "NEUTRO": "NEUTRO", "CAUTELOSO": "VENDA",
        }.get(categoria, linha.get("recomendacao_original") or "SEM RECOMENDAÇÃO")
        saida.append({
            "casa": casa, "recomendacao": recomendacao,
            "preco_alvo": alvo, "upside_pct": upside,
            "data_publicacao": linha.get("data_publicacao"),
            "titulo": linha.get("titulo"), "link": linha.get("link"),
            "premissas": {
                "receita": linha.get("projecao_receita"),
                "margem_ebitda": linha.get("projecao_ebitda_margem"),
                "lucro": linha.get("projecao_lucro"),
            },
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

    analistas = [
        _parecer_market(analise),
        _parecer_earnings(earnings),
        _parecer_valuation(analise, comparador),
    ]
    research = _pareceres_research(comparador, preco)
    dispersao = comparador.get("dispersao_precos_alvo") or {}
    return {
        "ticker": ticker,
        "analistas": analistas,
        "casas_research": research,
        "preco_alvo_consenso": {
            "mediana": _numero(dispersao.get("mediana")),
            "minimo": _numero(dispersao.get("minimo")),
            "maximo": _numero(dispersao.get("maximo")),
            "n_casas": dispersao.get("n_casas_com_preco_alvo", 0),
            "preco_atual": preco,
            "upside_pct": (((_numero(dispersao.get("mediana")) / preco) - 1) * 100
                           if _numero(dispersao.get("mediana")) is not None and preco is not None and preco > 0 else None),
            "rotulo": "Consenso de preços-alvo publicados; não é estimativa proprietária.",
        },
    }


def montar_sinal_comite(resultados):
    analise = (resultados.get("analise_ticker") or {}).get("dados") or {}
    return calcular_sinal_comite(analise)
