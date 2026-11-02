# -*- coding: utf-8 -*-
"""Nota estruturada de resultado trimestral (Modulo 2 - Earnings
Reviewer), a partir dos numeros normalizados de cvm_dre.py (Brasil) e
sec_xbrl.py (internacional). So' afirma o que os dois modulos realmente
devolveram - NUNCA inventa consenso de mercado, guidance, preco-alvo,
ROIC ou qualquer indicador que a fonte nao tenha fornecido (ver
LIMITACOES em cada nota, sempre presente e nunca vazia por engano).

--- Fatos vs interpretacao -----------------------------------------------

Toda frase derivada (ex: "margem bruta caiu") e' FATO (conta por conta,
rastreavel). Qualquer leitura de causa/efeito ganha o prefixo
[INTERPRETACAO] (mesma convencao de jobs/morning_call.py - nunca
confundida com fato) e so' e' gerada a partir de combinacoes de deltas
JA CALCULADOS, nunca de texto livre/especulacao nao suportada pelos
numeros desta nota.

--- Versionamento da tese ------------------------------------------------

Cada nota gerada e' um registro NOVO na tabela `earnings_reviews` (ver
sql/earnings_reviews.sql) - nunca um UPDATE sobre a nota anterior do
mesmo ticker/periodo. `comparar_com_versao_anterior` le' a ULTIMA nota
JA PERSISTIDA pro mesmo ticker (periodo diferente) e sinaliza so' o que
mudou de direcao (alta<->queda) nos indicadores YoY - nunca reescreve
nem apaga o registro anterior."""

from datetime import date, datetime, timezone

import config
from data.coletores_status import registrar_tentativa
from data.earnings import cvm_balanco, cvm_dfc, cvm_dre, sec_xbrl
from data.supabase_client import obter_cliente

_NOME_COLETOR = "EARNINGS REVIEWER (persistencia)"

_TABELA = "earnings_reviews"

# Instituições financeiras/seguradoras usam plano de contas regulatório
# proprio (COSIF), nao o plano industrial/comercial que CONTAS_DRE
# (data/earnings/cvm_dre.py) assume - o MESMO codigo (ex: "3.01") tem
# outro significado nesse setor (vira "Receitas de Intermediacao
# Financeira", nao "receita liquida de vendas"). Antes desta checagem
# (2026-10-30), montar_nota_br calculava e devolvia disponivel=True com
# numeros REAIS mas com ROTULO ERRADO pra qualquer banco/seguradora - a
# docstring de cvm_dre.py ja dizia "ver reviewer.py, que sinaliza isso
# como limitacao explicita", mas esse guard nunca tinha sido implementado
# de verdade (achado durante a validacao com ITUB4 na evolucao da
# Conclusao de Investimento). Usa a classificacao setorial que o projeto
# ja mantem (config.IBOVESPA_SETORES) - nenhuma fonte nova.
SETORES_PLANO_CONTAS_INCOMPATIVEL = {"Bancos", "Bancos e Serviços Financeiros", "Seguros"}

LIMITACOES_PADRAO = (
    "Sem acesso a consenso de mercado, guidance da empresa ou relatorios "
    "pagos de research nesta integracao - so' numeros reportados nas "
    "fontes oficiais citadas em FONTES.",
    "Resultado por segmento nao coberto nesta versao.",
    "FCO/CAPEX/dividendos pagos sao sempre ACUMULADOS NO ANO (YTD) até o "
    "fim do trimestre - a CVM nunca desagrega esses itens por trimestre "
    "isolado (diferente da DRE); nunca derivamos um trimestre isolado "
    "por subtração entre acumulados (mesmo motivo que a DRE evita isso "
    "entre reapresentações).",
)

# Ver cvm_balanco.py (motivo: '2.03' em banco e' um PASSIVO, nao
# patrimonio - confirmado contra ITUB4 em 2026-11-01).
_MOTIVO_ROIC_BALANCO_INDISPONIVEL = (
    "ROIC indisponível neste trimestre: balanço patrimonial (patrimônio "
    "líquido/dívida/caixa) não pôde ser obtido para este ticker/período."
)
_MOTIVO_ROIC_ALIQUOTA_INDISPONIVEL = (
    "ROIC indisponível neste trimestre: alíquota efetiva de imposto não "
    "pôde ser calculada (resultado antes dos tributos ausente, zero ou "
    "negativo, ou imposto de renda/CSLL não reportado isoladamente) - "
    "nunca assumimos uma alíquota-padrão (ex: 34%) em vez do dado real."
)


def _variacao_pct(atual, anterior):
    """Variacao percentual de `anterior` pra `atual`. Usa abs(anterior)
    no denominador (nunca `anterior` puro) - bug real encontrado em
    revisao tecnica independente (2026-10-22): com base negativa (ex:
    prejuizo), `atual/anterior - 1` INVERTE a direcao - prejuizo
    encolhendo de -100 pra -50 (melhora real) dava -50% ("queda"), e
    prejuizo piorando de -50 pra -100 dava +100% ("alta"). Com
    abs(anterior), o sinal do resultado sempre bate com o sinal de
    (atual - anterior) - pra base positiva o valor numerico e' IDENTICO
    ao de antes (abs(anterior) == anterior), so' corrige o caso de base
    negativa."""
    if atual is None or anterior in (None, 0):
        return None
    return (atual - anterior) / abs(anterior) * 100


def _margem_pct(numerador, receita):
    if numerador is None or receita in (None, 0):
        return None
    return numerador / receita * 100


# Bug real encontrado na validação (2026-11-01, PETR4/WEGE3): VL_CONTA
# da CVM vem na unidade de ESCALA_MOEDA (quase sempre "MIL" - confirmado
# em PETR4/WEGE3/VALE3), nunca em reais absolutos. `metricas`/
# `margem_bruta_pct` ficam intocados (são ratios/percentuais ou já
# escalados pelo consumidor na tela de Revisão de Resultados - ver
# _fmt_moeda_earnings/_ESCALA_EARNINGS em ui/analises_tab.py) - mas os
# valores ABSOLUTOS novos desta seção (dívida líquida, FCO, CAPEX, FCF,
# dividendos pagos, EBITDA) são consumidos diretamente por `_fmt_reais`
# na Conclusão de Investimento, que espera reais absolutos (mesma
# convenção de `fluxo_caixa_livre`/`valor_mercado` do yfinance, já
# absolutos) - sem esta escala, mostravam/calculavam (inclusive no DCF)
# um valor 1000x menor que o real. Mesmo mapa de `_ESCALA_EARNINGS`
# (duplicado aqui de propósito - este módulo não deve depender de
# ui/analises_tab.py, mesmo princípio de `_baixar_csv_do_zip` duplicado
# entre os módulos de Earnings).
_ESCALA_MOEDA_MULTIPLICADOR = {"MIL": 1_000.0, "MILHAO": 1_000_000.0}


def _em_reais_absolutos(valor, escala_moeda):
    if valor is None:
        return None
    return valor * _ESCALA_MOEDA_MULTIPLICADOR.get((escala_moeda or "").upper(), 1.0)


# ---------------------------------------------------------------------
# ROIC REAL (2026-11-01) - NOPAT = EBIT isolado do trimestre * (1 -
# aliquota efetiva REAL, calculada a partir do imposto de renda/CSLL
# realmente reportado no MESMO trimestre isolado, nunca uma aliquota-
# padrao tipo 34% fixa, que seria estimativa, nao dado reportado).
# Capital investido = patrimonio liquido + divida total - caixa e
# equivalentes, todos do balanco (cvm_balanco.py) no FIM do trimestre.
# ROIC aqui e' POR TRIMESTRE ISOLADO, NAO ANUALIZADO - documentado
# explicitamente na nota (anualizar via x4 seria uma aproximacao que
# ignora sazonalidade real, decidido nao fazer por padrao).
# ---------------------------------------------------------------------

def _aliquota_efetiva(imposto_isolado, resultado_antes_tributos_isolado):
    """None se resultado antes dos tributos for None/zero/negativo (sem
    base para aliquota com significado economico) ou se o imposto nao
    tiver sido reportado isoladamente. `imposto_isolado` vem NEGATIVO no
    arquivo da CVM (despesa) - aliquota = -imposto/resultado, entre 0 e 1
    no caso comum; pode sair negativa (credito fiscal liquido) ou >1
    (caso raro, item nao-recorrente grande) - nunca forcada a um range,
    e' o calculo real, documentado como esta' nas LIMITACOES quando sair
    fora do range usual."""
    if imposto_isolado is None or resultado_antes_tributos_isolado in (None, 0) or resultado_antes_tributos_isolado < 0:
        return None
    return -imposto_isolado / resultado_antes_tributos_isolado


def _roic_pct(ebit_isolado, aliquota_efetiva, patrimonio_liquido, divida_total, caixa_equivalentes):
    """None se faltar EBIT, aliquota, ou qualquer componente do capital
    investido, ou se o capital investido calculado for <= 0 (ROIC sem
    significado economico nesse caso - empresa com patrimonio liquido
    negativo, por exemplo)."""
    if ebit_isolado is None or aliquota_efetiva is None:
        return None
    if patrimonio_liquido is None or divida_total is None or caixa_equivalentes is None:
        return None
    capital_investido = patrimonio_liquido + divida_total - caixa_equivalentes
    if capital_investido <= 0:
        return None
    nopat = ebit_isolado * (1 - aliquota_efetiva)
    return nopat / capital_investido * 100


def _ebit_acumulado_no_ano(ticker: str, ano: int, trimestre: int):
    """Soma o EBIT ISOLADO (cvm_dre.obter_dre_trimestral) de cada
    trimestre civil de 1 até `trimestre` - usado pra ter um EBIT na
    MESMA base acumulada (YTD) da depreciação/amortização do DFC (que a
    CVM só reporta acumulada, nunca isolada - ver cvm_dfc.py), permitindo
    um EBITDA histórico com numerador e "add-back" na mesma janela de
    tempo. None se QUALQUER trimestre do range faltar EBIT isolado -
    nunca soma parcial disfarçada de total."""
    total = 0.0
    for tri in range(1, trimestre + 1):
        nota_tri = cvm_dre.obter_dre_trimestral(ticker, ano, tri)
        if nota_tri is None:
            return None
        ebit_tri = nota_tri["contas"].get("ebit", {}).get("atual")
        if ebit_tri is None:
            return None
        total += ebit_tri
    return total


# ---------------------------------------------------------------------
# EDUCAÇÃO FINANCEIRA CONTEXTUAL (2026-10-27) - nota determinística
# (zero IA, zero consulta nova) que ensina o CONCEITO geral "crescimento
# de receita != crescimento de lucro" ancorado nos números REAIS desta
# nota (nunca um texto genérico desvinculado do resultado reportado).
# Rotulada [O QUE ISSO SIGNIFICA] - visualmente e semanticamente
# diferente de [INTERPRETAÇÃO] (que é uma leitura do PRÓPRIO resultado
# desta empresa) e de FATO (número rastreável): aqui o objetivo é
# ensinar um conceito de educação financeira, nunca recomendar compra/
# venda nem substituir a leitura em FATO/INTERPRETAÇÃO já existente.
# ---------------------------------------------------------------------
_LIMIAR_DIVERGENCIA_RECEITA_LUCRO_PP = 3.0


def _nota_educativa_receita_vs_lucro(metricas: dict) -> list:
    """[] quando faltar receita líquida OU lucro líquido consolidado YoY
    (nunca estima o que falta), ou quando a diferença entre as duas
    variações for pequena (<3 p.p. - didaticamente não compensa chamar
    ruído de padrão relevante; crescimento "proporcional" não precisa
    de nota educativa)."""
    receita = metricas.get("receita_liquida", {}).get("yoy_variacao_pct")
    lucro = metricas.get("lucro_liquido_consolidado", {}).get("yoy_variacao_pct")
    if receita is None or lucro is None:
        return []
    diferenca = lucro - receita
    if abs(diferenca) < _LIMIAR_DIVERGENCIA_RECEITA_LUCRO_PP:
        return []
    if lucro > receita:
        texto = (
            f"[O QUE ISSO SIGNIFICA] o lucro líquido cresceu mais rápido ({lucro:+.1f}%) do que a "
            f"receita líquida ({receita:+.1f}%) na comparação anual. Em geral isso indica que a empresa "
            "ficou mais eficiente (custos/despesas cresceram menos que a receita) ou se beneficiou de um "
            "evento não recorrente (ex: venda de ativo, crédito fiscal, efeito cambial) - esta nota não "
            "calcula qual dos dois foi o motivo; ver detalhamento completo na fonte original."
        )
    else:
        texto = (
            f"[O QUE ISSO SIGNIFICA] a receita líquida cresceu mais rápido ({receita:+.1f}%) do que o "
            f"lucro líquido ({lucro:+.1f}%) na comparação anual. Em geral isso indica compressão de "
            "margem (custos/despesas cresceram mais que a receita) - pode ser repasse de custo não feito "
            "ao cliente, investimento em crescimento, despesa não recorrente ou efeito cambial; esta nota "
            "não calcula qual dos motivos foi responsável; ver detalhamento completo na fonte original."
        )
    return [texto]


def _montar_metricas_br(contas: dict) -> dict:
    metricas = {}
    for rotulo, valores in contas.items():
        metricas[rotulo] = {
            "atual": valores.get("atual"),
            "yoy_anterior": valores.get("ano_anterior"),
            "yoy_variacao_pct": _variacao_pct(valores.get("atual"), valores.get("ano_anterior")),
        }
    return metricas


# ---------------------------------------------------------------------
# BALANÇO + FLUXO DE CAIXA (2026-11-01) - fecha a lacuna deixada pela
# Fase 1 (ROIC/dívida líquida histórica/FCO/FCF/CAPEX/dividendos
# históricos documentados como "fora de escopo, só DRE" em
# LIMITACOES_PADRAO antigo). Isolado numa função própria (chamada de
# dentro de montar_nota_br, DEPOIS do guard de instituição financeira
# já ter decidido disponivel=True) pra manter montar_nota_br legível -
# cada fonte (balanço/DFC) falha sozinha, nunca derruba a nota inteira
# nem a DRE já calculada.
# ---------------------------------------------------------------------

def _ebit_acumulado_no_ano_absoluto(ticker: str, ano: int, trimestre: int):
    """Mesma soma de _ebit_acumulado_no_ano, mas escalando CADA
    trimestre isolado pela escala_moeda DAQUELE trimestre (nota própria,
    via cvm_dre.obter_dre_trimestral) antes de somar - nunca soma valores
    em escalas potencialmente diferentes entre trimestres/reapresentações."""
    total = 0.0
    for tri in range(1, trimestre + 1):
        nota_tri = cvm_dre.obter_dre_trimestral(ticker, ano, tri)
        if nota_tri is None:
            return None
        ebit_tri = nota_tri["contas"].get("ebit", {}).get("atual")
        if ebit_tri is None:
            return None
        total += _em_reais_absolutos(ebit_tri, nota_tri.get("escala_moeda"))
    return total


def _montar_balanco_fluxo_caixa(ticker: str, ano: int, trimestre: int, metricas: dict) -> tuple[dict, list]:
    """Retorna (bloco, limitacoes_extras). `bloco` tem chaves sempre
    presentes (None quando indisponível) - nunca uma chave ausente, pra
    quem consome não precisar de .get() com fallback silencioso.

    TODOS os valores monetários ABSOLUTOS do bloco (dívida líquida, FCO,
    CAPEX, FCF, dividendos pagos, EBITDA) já vêm em REAIS ABSOLUTOS
    (escala aplicada aqui, cada fonte usando a PRÓPRIA escala_moeda que
    ela reportou - balanço/DFC podem, em tese, divergir entre si ou do
    DRE) - mesma convenção de `fluxo_caixa_livre`/`valor_mercado` do
    yfinance usados no resto da Conclusão de Investimento. `roic_pct`/
    `aliquota_efetiva_pct` são RATIOS (%), nunca precisam de escala (o
    fator cancela no numerador/denominador) - calculados a partir do
    EBIT/alíquota ainda na escala original da CVM, sem conversão."""
    limitacoes: list = []
    bloco = {
        "divida_liquida_atual": None, "divida_liquida_ano_anterior": None,
        "divida_liquida_yoy_variacao_pct": None,
        "fco_ytd": None, "capex_ytd": None, "fcf_ytd": None, "dividendos_pagos_ytd": None,
        "fco_ytd_ano_anterior": None, "capex_ytd_ano_anterior": None,
        "fcf_ytd_ano_anterior": None, "dividendos_pagos_ytd_ano_anterior": None,
        "fco_ytd_yoy_variacao_pct": None, "capex_ytd_yoy_variacao_pct": None,
        "fcf_ytd_yoy_variacao_pct": None, "dividendos_pagos_ytd_yoy_variacao_pct": None,
        "metodo_dfc": None,
        "ebitda_ytd": None, "ebitda_ytd_ano_anterior": None, "ebitda_ytd_yoy_variacao_pct": None,
        "roic_pct": None, "aliquota_efetiva_pct": None,
    }

    try:
        balanco = cvm_balanco.obter_balanco_trimestral(ticker, ano, trimestre)
    except Exception as exc:
        print(f"[reviewer] balanço indisponível pra {ticker} {trimestre}T{ano}: {exc!r}")
        balanco = None
    try:
        balanco_ant = cvm_balanco.obter_balanco_trimestral(ticker, ano - 1, trimestre)
    except Exception as exc:
        print(f"[reviewer] balanço (ano anterior) indisponível pra {ticker} {trimestre}T{ano - 1}: {exc!r}")
        balanco_ant = None

    if balanco is None:
        limitacoes.append(_MOTIVO_ROIC_BALANCO_INDISPONIVEL)
        limitacoes.append("Dívida líquida histórica indisponível: balanço patrimonial não pôde ser obtido para este trimestre.")
    else:
        escala_bpp = balanco.get("escala_moeda")
        divida_total_abs = _em_reais_absolutos(balanco.get("divida_total"), escala_bpp)
        caixa_abs = _em_reais_absolutos(balanco.get("caixa_equivalentes"), escala_bpp)
        if divida_total_abs is not None and caixa_abs is not None:
            bloco["divida_liquida_atual"] = divida_total_abs - caixa_abs
        if balanco_ant:
            escala_bpp_ant = balanco_ant.get("escala_moeda")
            divida_total_ant_abs = _em_reais_absolutos(balanco_ant.get("divida_total"), escala_bpp_ant)
            caixa_ant_abs = _em_reais_absolutos(balanco_ant.get("caixa_equivalentes"), escala_bpp_ant)
            if divida_total_ant_abs is not None and caixa_ant_abs is not None:
                bloco["divida_liquida_ano_anterior"] = divida_total_ant_abs - caixa_ant_abs
        bloco["divida_liquida_yoy_variacao_pct"] = _variacao_pct(
            bloco["divida_liquida_atual"], bloco["divida_liquida_ano_anterior"],
        )

        ebit_isolado = metricas.get("ebit", {}).get("atual")
        imposto_isolado = metricas.get("impostos_sobre_lucro", {}).get("atual")
        resultado_antes_tributos = metricas.get("resultado_antes_tributos", {}).get("atual")
        aliquota = _aliquota_efetiva(imposto_isolado, resultado_antes_tributos)
        if aliquota is None:
            limitacoes.append(_MOTIVO_ROIC_ALIQUOTA_INDISPONIVEL)
        else:
            bloco["aliquota_efetiva_pct"] = aliquota * 100
            bloco["roic_pct"] = _roic_pct(
                ebit_isolado, aliquota,
                balanco.get("patrimonio_liquido"), balanco.get("divida_total"), balanco.get("caixa_equivalentes"),
            )
            if bloco["roic_pct"] is None:
                limitacoes.append(_MOTIVO_ROIC_BALANCO_INDISPONIVEL)

    try:
        fluxo = cvm_dfc.obter_fluxo_caixa_trimestral(ticker, ano, trimestre)
    except Exception as exc:
        print(f"[reviewer] fluxo de caixa indisponível pra {ticker} {trimestre}T{ano}: {exc!r}")
        fluxo = None

    if fluxo is None:
        limitacoes.append("FCO/CAPEX/dividendos pagos indisponíveis: Demonstração de Fluxo de Caixa não pôde ser obtida para este trimestre.")
    else:
        escala_dfc = fluxo.get("escala_moeda")
        bloco["metodo_dfc"] = fluxo.get("metodo")
        bloco["fco_ytd"] = _em_reais_absolutos(fluxo.get("fco_ytd"), escala_dfc)
        bloco["fco_ytd_ano_anterior"] = _em_reais_absolutos(fluxo.get("fco_ytd_ano_anterior"), escala_dfc)
        bloco["capex_ytd"] = _em_reais_absolutos(fluxo.get("capex_ytd"), escala_dfc)
        bloco["capex_ytd_ano_anterior"] = _em_reais_absolutos(fluxo.get("capex_ytd_ano_anterior"), escala_dfc)
        bloco["dividendos_pagos_ytd"] = _em_reais_absolutos(fluxo.get("dividendos_pagos_ytd"), escala_dfc)
        bloco["dividendos_pagos_ytd_ano_anterior"] = _em_reais_absolutos(
            fluxo.get("dividendos_pagos_ytd_ano_anterior"), escala_dfc,
        )
        if bloco["fco_ytd"] is not None and bloco["capex_ytd"] is not None:
            bloco["fcf_ytd"] = bloco["fco_ytd"] - bloco["capex_ytd"]
        if bloco["fco_ytd_ano_anterior"] is not None and bloco["capex_ytd_ano_anterior"] is not None:
            bloco["fcf_ytd_ano_anterior"] = bloco["fco_ytd_ano_anterior"] - bloco["capex_ytd_ano_anterior"]
        bloco["fco_ytd_yoy_variacao_pct"] = _variacao_pct(bloco["fco_ytd"], bloco["fco_ytd_ano_anterior"])
        bloco["capex_ytd_yoy_variacao_pct"] = _variacao_pct(bloco["capex_ytd"], bloco["capex_ytd_ano_anterior"])
        bloco["fcf_ytd_yoy_variacao_pct"] = _variacao_pct(bloco["fcf_ytd"], bloco["fcf_ytd_ano_anterior"])
        bloco["dividendos_pagos_ytd_yoy_variacao_pct"] = _variacao_pct(
            bloco["dividendos_pagos_ytd"], bloco["dividendos_pagos_ytd_ano_anterior"],
        )
        if bloco["capex_ytd"] is None:
            limitacoes.append("CAPEX (YTD) indisponível: nenhuma linha de aquisição de imobilizado/intangível identificada no fluxo de investimento desta empresa/período.")
        if bloco["dividendos_pagos_ytd"] is None:
            limitacoes.append("Dividendos pagos (YTD) indisponíveis: nenhuma linha de dividendos identificada no fluxo de financiamento desta empresa/período.")

        depreciacao_ytd_abs = _em_reais_absolutos(fluxo.get("depreciacao_amortizacao_ytd"), escala_dfc)
        if depreciacao_ytd_abs is None:
            limitacoes.append("EBITDA histórico indisponível: depreciação/amortização só é visível no método indireto (DFC-MI) - esta empresa/período usa o método direto, ou a linha não foi identificada.")
        else:
            ebit_ytd_abs = _ebit_acumulado_no_ano_absoluto(ticker, ano, trimestre)
            if ebit_ytd_abs is None:
                limitacoes.append("EBITDA histórico indisponível: EBIT isolado de pelo menos 1 trimestre deste ano não foi reportado pela empresa (ver limitação de trimestre isolado).")
            else:
                bloco["ebitda_ytd"] = ebit_ytd_abs + depreciacao_ytd_abs

        depreciacao_ytd_ant_abs = _em_reais_absolutos(fluxo.get("depreciacao_amortizacao_ytd_ano_anterior"), escala_dfc)
        if depreciacao_ytd_ant_abs is not None:
            ebit_ytd_ant_abs = _ebit_acumulado_no_ano_absoluto(ticker, ano - 1, trimestre)
            if ebit_ytd_ant_abs is not None:
                bloco["ebitda_ytd_ano_anterior"] = ebit_ytd_ant_abs + depreciacao_ytd_ant_abs

        bloco["ebitda_ytd_yoy_variacao_pct"] = _variacao_pct(bloco["ebitda_ytd"], bloco["ebitda_ytd_ano_anterior"])

    return bloco, limitacoes


def montar_nota_br(ticker: str, ano: int, trimestre: int) -> dict:
    """Nota de UMA empresa brasileira pro trimestre pedido. `disponivel`
    e' False (com `motivo`) quando cvm_dre nao devolveu dado pra esse
    ticker/periodo - `motivo`, nesse caso, e' a causa ESPECIFICA que
    cvm_dre.obter_dre_trimestral devolveu (MOTIVO_SEM_CNPJ,
    MOTIVO_FONTE_INDISPONIVEL, MOTIVO_SEM_REGISTRO_TRIMESTRE ou
    MOTIVO_TRIMESTRE_NAO_SUPORTADO - nunca mais uma frase generica com
    "ou" escondendo qual das causas ocorreu, bug real corrigido
    2026-11-02), OU quando o ticker e' de instituicao financeira/
    seguradora (ver SETORES_PLANO_CONTAS_INCOMPATIVEL acima) - nunca gera
    nota com numero inventado ou com rotulo semanticamente errado."""
    setor = config.IBOVESPA_SETORES.get(ticker.upper())
    if setor in SETORES_PLANO_CONTAS_INCOMPATIVEL:
        return {
            "ticker": ticker.upper(), "pais": "BR", "disponivel": False,
            "motivo": f"instituição financeira/seguradora ({setor}) usa plano de contas "
                      "regulatório próprio (COSIF) - os códigos do plano industrial/comercial "
                      "usados nesta integração (CONTAS_DRE) têm outro significado nesse setor "
                      "(ex: '3.01' não é receita líquida de vendas) - dado não calculado para "
                      "evitar rótulo incorreto.",
        }
    # Causa ESPECÍFICA da falha, propagada sem reescrita (bug real
    # corrigido 2026-11-02 - caso BEEF3/Minerva usado na investigação
    # original): antes desta correção, as 3 causas de
    # cvm_dre.obter_dre_trimestral colapsavam na mesma mensagem genérica
    # com "ou" - o usuário nunca sabia qual delas ocorreu de verdade.
    atual, motivo_dre = cvm_dre.obter_dre_trimestral(ticker, ano, trimestre)
    if atual is None:
        return {
            "ticker": ticker.upper(), "pais": "BR", "disponivel": False,
            "motivo": motivo_dre or "DRE indisponível nesta checagem.",
        }

    metricas = _montar_metricas_br(atual["contas"])

    qoq_trimestre = trimestre - 1
    qoq, _motivo_qoq = (
        cvm_dre.obter_dre_trimestral(ticker, ano, qoq_trimestre) if qoq_trimestre >= 1 else (None, None)
    )
    limitacoes = list(LIMITACOES_PADRAO)
    if qoq is not None:
        for rotulo in metricas:
            valor_qoq = qoq["contas"].get(rotulo, {}).get("atual")
            metricas[rotulo]["qoq_anterior"] = valor_qoq
            metricas[rotulo]["qoq_variacao_pct"] = _variacao_pct(metricas[rotulo]["atual"], valor_qoq)
    else:
        for rotulo in metricas:
            metricas[rotulo]["qoq_anterior"] = None
            metricas[rotulo]["qoq_variacao_pct"] = None
        limitacoes.append(
            f"Comparação trimestre-a-trimestre (QoQ) indisponível para o {trimestre}º "
            "trimestre: o trimestre imediatamente anterior exigiria dados do 4º "
            "trimestre do ano anterior (DFP anual, sem trimestre isolado nesta integração)."
            if trimestre == 1 else
            "Comparação QoQ indisponível para esta empresa/trimestre (fonte CVM não "
            "reportou linha de trimestre isolado para a conta)."
        )

    for rotulo, valores in metricas.items():
        if valores["atual"] is None:
            limitacoes.append(
                f"'{rotulo}': empresa não reportou o trimestre isolado desta conta "
                "(só o acumulado do ano) - valor omitido em vez de estimado."
            )

    receita = metricas.get("receita_liquida", {}).get("atual")
    receita_ant = metricas.get("receita_liquida", {}).get("yoy_anterior")
    margem_bruta = _margem_pct(metricas.get("resultado_bruto", {}).get("atual"), receita)
    margem_bruta_ant = _margem_pct(metricas.get("resultado_bruto", {}).get("yoy_anterior"), receita_ant)

    interpretacoes = []
    if margem_bruta is not None and margem_bruta_ant is not None:
        delta_margem = margem_bruta - margem_bruta_ant
        if abs(delta_margem) >= 1:
            direcao = "piora" if delta_margem < 0 else "melhora"
            interpretacoes.append(
                f"[INTERPRETAÇÃO] margem bruta variou {delta_margem:+.1f} p.p. "
                f"na comparação anual ({direcao} de rentabilidade bruta); não distingue "
                "aqui se a causa é preço, volume ou custo - ver fatores na fonte original."
            )

    balanco_fluxo_caixa, limitacoes_bfc = _montar_balanco_fluxo_caixa(
        ticker, ano, trimestre, metricas,
    )
    limitacoes.extend(limitacoes_bfc)

    return {
        "ticker": ticker.upper(), "empresa": atual["empresa"], "pais": "BR",
        "disponivel": True, "periodo_label": f"{trimestre}T{ano}",
        "dt_referencia": atual["dt_referencia"], "moeda": atual["moeda"],
        "escala_moeda": atual["escala_moeda"], "metricas": metricas,
        "margem_bruta_pct": margem_bruta, "margem_bruta_yoy_anterior_pct": margem_bruta_ant,
        "interpretacoes": interpretacoes, "educacao_financeira": _nota_educativa_receita_vs_lucro(metricas),
        "balanco_fluxo_caixa": balanco_fluxo_caixa,
        "limitacoes": limitacoes,
        "fontes": [{"nome": atual["fonte_nome"], "url": atual["fonte_url"],
                     "coletado_em": datetime.now(timezone.utc).isoformat()}],
        "gerado_em": datetime.now(timezone.utc).isoformat(),
    }


def montar_nota_internacional(ticker: str, inicio: str, fim: str, inicio_ano_anterior: str, fim_ano_anterior: str) -> dict:
    """Nota de UMA empresa internacional pro trimestre [inicio,fim] (ISO
    yyyy-mm-dd) - quem chama precisa saber o calendario fiscal da
    empresa (nao detectado automaticamente nesta versao, ver LIMITACOES).
    `disponivel=False` quando sec_xbrl nao achar CIK/dado - nunca inventa."""
    dados = sec_xbrl.obter_metricas_trimestre(ticker, inicio, fim, inicio_ano_anterior, fim_ano_anterior)
    if dados is None:
        return {
            "ticker": ticker.upper(), "pais": "US", "disponivel": False,
            "motivo": "CIK não encontrado para este ticker no mapa oficial da SEC "
                      "(sec.gov/files/company_tickers.json) ou fonte indisponível.",
        }

    metricas = {}
    tags_usadas = []
    for rotulo, valores in dados["metricas"].items():
        metricas[rotulo] = {
            "atual": valores["atual"], "yoy_anterior": valores["ano_anterior"],
            "yoy_variacao_pct": _variacao_pct(valores["atual"], valores["ano_anterior"]),
        }
        if valores.get("tag_usada"):
            tags_usadas.append((rotulo, valores["tag_usada"]))

    limitacoes = list(LIMITACOES_PADRAO)
    limitacoes.append(
        "Comparação trimestre-a-trimestre (QoQ) não calculada nesta nota - "
        "esta chamada recebeu só o período atual e o mesmo período do ano "
        "anterior (YoY); para QoQ, chamar com o trimestre imediatamente anterior."
    )
    for rotulo, valores in metricas.items():
        if valores["atual"] is None:
            limitacoes.append(f"'{rotulo}': nenhuma tag XBRL conhecida teve dado exato para este período.")

    receita = metricas.get("receita_liquida", {}).get("atual")
    receita_ant = metricas.get("receita_liquida", {}).get("yoy_anterior")
    margem_bruta = _margem_pct(metricas.get("resultado_bruto", {}).get("atual"), receita)
    margem_bruta_ant = _margem_pct(metricas.get("resultado_bruto", {}).get("yoy_anterior"), receita_ant)

    interpretacoes = []
    if margem_bruta is not None and margem_bruta_ant is not None:
        delta_margem = margem_bruta - margem_bruta_ant
        if abs(delta_margem) >= 1:
            direcao = "piora" if delta_margem < 0 else "melhora"
            interpretacoes.append(
                f"[INTERPRETAÇÃO] margem bruta variou {delta_margem:+.1f} p.p. "
                f"na comparação anual ({direcao} de rentabilidade bruta); não distingue "
                "aqui se a causa é preço, volume ou custo - ver fatores na fonte original."
            )

    fontes = [{
        "nome": f"{dados['fonte_nome']} (tag: {tag})",
        "url": dados["fonte_url"].replace("<tag>", tag),
        "coletado_em": datetime.now(timezone.utc).isoformat(),
    } for _, tag in tags_usadas] or [{
        "nome": dados["fonte_nome"], "url": dados["fonte_url"],
        "coletado_em": datetime.now(timezone.utc).isoformat(),
    }]

    return {
        "ticker": ticker.upper(), "pais": "US", "disponivel": True,
        "periodo_label": f"{inicio} a {fim}", "moeda": dados["moeda"],
        "metricas": metricas, "margem_bruta_pct": margem_bruta,
        "margem_bruta_yoy_anterior_pct": margem_bruta_ant,
        "interpretacoes": interpretacoes, "educacao_financeira": _nota_educativa_receita_vs_lucro(metricas),
        "limitacoes": limitacoes,
        "fontes": fontes, "gerado_em": datetime.now(timezone.utc).isoformat(),
    }


def _direcao(variacao_pct):
    if variacao_pct is None:
        return None
    if variacao_pct > 0.5:
        return "ALTA"
    if variacao_pct < -0.5:
        return "QUEDA"
    return "ESTÁVEL"


def comparar_com_versao_anterior(nota_atual: dict, nota_anterior: dict | None) -> list:
    """Compara a direcao YoY de cada metrica entre duas notas do MESMO
    ticker - so' sinaliza METRICAS QUE MUDARAM DE DIRECAO (alta<->queda),
    nunca reescreve a nota anterior. [] se nao houver nota anterior
    (primeira analise deste ticker) ou nenhuma mudanca de direcao."""
    if not nota_anterior or not nota_anterior.get("disponivel") or not nota_atual.get("disponivel"):
        return []
    mudancas = []
    for rotulo, valores in nota_atual.get("metricas", {}).items():
        direcao_atual = _direcao(valores.get("yoy_variacao_pct"))
        direcao_anterior = _direcao(nota_anterior.get("metricas", {}).get(rotulo, {}).get("yoy_variacao_pct"))
        if direcao_atual and direcao_anterior and direcao_atual != direcao_anterior:
            mudancas.append({
                "metrica": rotulo, "direcao_anterior": direcao_anterior, "direcao_atual": direcao_atual,
                "periodo_anterior": nota_anterior.get("periodo_label"),
                "periodo_atual": nota_atual.get("periodo_label"),
            })
    return mudancas


def _ultima_versao_mesmo_periodo(ticker: str, pais: str, periodo_label: str, cliente) -> dict | None:
    """Conteudo da versao mais recente JA PERSISTIDA pro MESMO ticker+
    pais+periodo_label (ex: reprocessar o 2T2026 da Vale 2x no mesmo
    dia) - None se nao houver nenhuma ou a consulta falhar (tratado como
    'sem versao anterior', nunca bloqueia o insert por isso)."""
    try:
        resp = (
            cliente.table(_TABELA).select("conteudo")
            .eq("ticker", ticker.upper()).eq("pais", pais).eq("periodo_label", periodo_label)
            .order("gerado_em", desc=True).limit(1)
            .execute()
        )
        linhas = resp.data or []
        return linhas[0]["conteudo"] if linhas else None
    except Exception:
        return None


def salvar_versao(nota: dict) -> bool:
    """Insere a nota como registro NOVO (nunca update) em
    `earnings_reviews` - False se Supabase indisponivel ou a nota nao
    estiver disponivel (nunca persiste nota com disponivel=False).

    Deduplicacao (bug real encontrado em revisao tecnica independente,
    2026-10-22): sem isso, reprocessar o MESMO ticker/periodo 2x (ex:
    usuario reabre a pagina, ou um job futuro roda de novo sem checar)
    inseria uma linha NOVA idêntica a cada vez - a tabela e' append-only
    DE PROPOSITO (pra guardar re-apresentacoes reais da CVM/SEC), mas
    2 chamadas com os MESMOS numeros nao sao uma re-apresentacao, sao
    a MESMA versao reprocessada. Compara so' `metricas` (nunca o dict
    inteiro - `gerado_em`/`fontes[].coletado_em` sempre mudam entre
    chamadas, mesmo com numero identico) contra a ultima versao JA
    persistida do MESMO ticker+pais+periodo_label; numeros iguais ->
    nao insere de novo (devolve True - a versao JA esta' salva, do
    ponto de vista de quem chama nao e' uma falha)."""
    if not nota.get("disponivel"):
        return False
    cliente = obter_cliente()
    if cliente is None:
        registrar_tentativa(_NOME_COLETOR, _TABELA, execucao_ok=False, erro="Supabase indisponivel", categoria="Earnings")
        return False
    ultima_mesmo_periodo = _ultima_versao_mesmo_periodo(nota["ticker"], nota["pais"], nota["periodo_label"], cliente)
    if ultima_mesmo_periodo is not None and ultima_mesmo_periodo.get("metricas") == nota.get("metricas"):
        registrar_tentativa(_NOME_COLETOR, _TABELA, execucao_ok=True, registros_novos=0, categoria="Earnings")
        return True
    try:
        cliente.table(_TABELA).insert({
            "ticker": nota["ticker"], "pais": nota["pais"],
            "periodo_label": nota["periodo_label"], "gerado_em": nota["gerado_em"],
            "conteudo": nota,
        }).execute()
        registrar_tentativa(_NOME_COLETOR, _TABELA, execucao_ok=True, registros_novos=1, categoria="Earnings")
        return True
    except Exception as exc:
        registrar_tentativa(_NOME_COLETOR, _TABELA, execucao_ok=False, erro=f"insert em {_TABELA} falhou: {exc!r}", categoria="Earnings")
        return False


def obter_ultima_versao(ticker: str, pais: str, excluir_periodo: str | None = None) -> dict | None:
    """Ultima nota JA PERSISTIDA deste ticker (periodo diferente de
    `excluir_periodo`, se passado) - usada por comparar_com_versao_anterior.
    None se Supabase indisponivel ou nenhuma nota anterior existir."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        query = (
            cliente.table(_TABELA).select("conteudo,periodo_label,gerado_em")
            .eq("ticker", ticker.upper()).eq("pais", pais)
            .order("gerado_em", desc=True).limit(5)
        )
        resp = query.execute()
    except Exception:
        return None
    for linha in resp.data or []:
        if excluir_periodo is None or linha.get("periodo_label") != excluir_periodo:
            return linha.get("conteudo")
    return None


# ---------------------------------------------------------------------
# SÉRIE HISTÓRICA + TENDÊNCIA (2026-10-30, evolução da Conclusão de
# Investimento) - movido de ui/analises_tab.py (onde só servia pro
# seletor de trimestre da Revisão de Resultados) pra virar reutilizável
# por data/market_researcher.py também, sem a UI precisar saber nada de
# CVM/trimestre civil. ui/analises_tab.py importa estes mesmos nomes
# (com alias _trimestres_candidatos_br/_ultimo_trimestre_civil) em vez
# de redefinir - compatibilidade preservada pros testes existentes que
# chamam esses nomes direto no módulo da UI.
# ---------------------------------------------------------------------
FIM_TRIMESTRE_CIVIL = {1: (3, 31), 2: (6, 30), 3: (9, 30)}
INICIO_TRIMESTRE_CIVIL = {1: 1, 2: 4, 3: 7}


def trimestres_candidatos_br(hoje: date, n: int = 6) -> list:
    """Últimos `n` trimestres CIVIS (1-3, nunca o 4º - cvm_dre.py não
    calcula Q4 isolado, ver docstring do módulo) com data-fim <= hoje,
    do mais recente pro mais antigo. Só diz que o trimestre já FECHOU
    no calendário - quem diz se o número já foi PUBLICADO pela CVM é
    montar_nota_br (disponivel/motivo), nunca esta função."""
    candidatos = []
    ano = hoje.year
    limite = hoje.year - 6
    while len(candidatos) < n and ano > limite:
        for tri in (3, 2, 1):
            mes, dia = FIM_TRIMESTRE_CIVIL[tri]
            if date(ano, mes, dia) <= hoje:
                candidatos.append((ano, tri))
        ano -= 1
    return candidatos[:n]


def ultimo_trimestre_civil(hoje: date) -> tuple:
    """(início, fim) do trimestre civil mais recente já encerrado - só
    um PONTO DE PARTIDA editável pro seletor de empresas internacionais
    (o calendário fiscal real da empresa pode ser diferente do civil;
    montar_nota_internacional já documenta que detectar o calendário
    fiscal automaticamente está fora do escopo desta versão - por isso a
    UI pede confirmação em vez de assumir)."""
    ano, tri = trimestres_candidatos_br(hoje, n=1)[0]
    mes_fim, dia_fim = FIM_TRIMESTRE_CIVIL[tri]
    fim = date(ano, mes_fim, dia_fim)
    inicio = date(ano, INICIO_TRIMESTRE_CIVIL[tri], 1)
    return inicio, fim


_LIMIAR_TENDENCIA_PP = 3.0


def _tendencia(pontos: list) -> str | None:
    """pontos: valores em ordem CRESCENTE de tempo (mais antigo -> mais
    recente), já sem None. Regra explícita e auditável - nunca regressão
    nem média móvel: compara só o PRIMEIRO e o ÚLTIMO ponto da janela
    observada. Diferença >= _LIMIAR_TENDENCIA_PP p.p. de melhora vira
    'RECUPERACAO'; <= -_LIMIAR_TENDENCIA_PP vira 'DETERIORACAO'; dentro
    da banda vira 'ESTABILIDADE'. None com menos de 2 pontos válidos -
    não dá pra falar de tendência com 1 ponto só."""
    if len(pontos) < 2:
        return None
    delta = pontos[-1] - pontos[0]
    if delta >= _LIMIAR_TENDENCIA_PP:
        return "RECUPERACAO"
    if delta <= -_LIMIAR_TENDENCIA_PP:
        return "DETERIORACAO"
    return "ESTABILIDADE"


def serie_historica_br(ticker: str, n_trimestres: int = 4) -> dict:
    """Série REAL dos últimos `n_trimestres` civis já encerrados (via
    montar_nota_br, mesma fonte/mesmas regras da nota trimestral isolada
    - pula silenciosamente um trimestre sem DRE disponível, NUNCA
    interpola) + tendência explícita (ver _tendencia) de receita líquida,
    EBIT e lucro líquido consolidado (variação YoY), margem bruta
    (nível, em p.p.), ROIC (nível, % - trimestre isolado, NÃO anualizado),
    dívida líquida (nível em R$ + variação YoY; tendência usa o sinal
    INVERTIDO da variação, porque dívida subindo é deterioração, não
    recuperação - ver comentário no corpo da função) e, sempre em base
    ACUMULADA NO ANO/YTD (nunca trimestre isolado - a CVM não desagrega
    DFC, ver cvm_dfc.py): EBITDA, FCO, FCF, CAPEX e dividendos pagos
    (variação YoY). Pra CAPEX/dividendos, 'RECUPERACAO'/'DETERIORACAO' é
    só a DIREÇÃO do indicador (cresceu/caiu), não um julgamento de bom ou
    ruim - CAPEX maior pode ser investimento saudável ou gasto forçado,
    dividendo maior pode ser força de caixa ou falta de oportunidade de
    reinvestir; esta função não decide isso, só reporta a direção real.
    `disponivel`=False com `motivo` quando: a instituição é financeira/
    seguradora (plano de contas incompatível, ver montar_nota_br), ou
    nenhum trimestre tiver DRE disponível na CVM nesta janela. Só Brasil
    nesta versão - empresa internacional não tem calendário fiscal
    detectado automaticamente, não dá pra montar uma janela de
    trimestres civis confiável aqui (ver montar_nota_internacional)."""
    candidatos = trimestres_candidatos_br(date.today(), n=n_trimestres)
    notas = []
    bloqueio_setor = None
    for ano, tri in reversed(candidatos):  # mais antigo primeiro
        try:
            nota = montar_nota_br(ticker, ano, tri)
        except Exception:
            continue
        if nota.get("disponivel"):
            notas.append(nota)
        elif "plano de contas" in (nota.get("motivo") or ""):
            bloqueio_setor = nota["motivo"]
            break  # mesmo motivo bloquearia todos os trimestres - não repete a consulta

    if bloqueio_setor:
        return {"disponivel": False, "motivo": bloqueio_setor, "periodos": []}
    if not notas:
        return {
            "disponivel": False,
            "motivo": "nenhum trimestre com DRE disponível na CVM para este ticker nos "
                      "períodos civis verificados (empresa pode não ter CNPJ mapeado, ou a "
                      "fonte CVM não tem registro desse período).",
            "periodos": [],
        }

    def _serie(extrator):
        return [v for v in (extrator(n) for n in notas) if v is not None]

    receita_yoy = _serie(lambda n: n["metricas"].get("receita_liquida", {}).get("yoy_variacao_pct"))
    ebit_yoy = _serie(lambda n: n["metricas"].get("ebit", {}).get("yoy_variacao_pct"))
    lucro_yoy = _serie(lambda n: n["metricas"].get("lucro_liquido_consolidado", {}).get("yoy_variacao_pct"))
    margem_bruta_niveis = _serie(lambda n: n.get("margem_bruta_pct"))

    # Balanço/Fluxo de Caixa (2026-11-01) - cada campo pode faltar em
    # alguns trimestres mesmo com a DRE disponível (fontes diferentes,
    # cada uma falha sozinha - ver _montar_balanco_fluxo_caixa); _serie
    # já descarta None, então a série fica só com os pontos reais.
    bfc = lambda n: n.get("balanco_fluxo_caixa") or {}  # noqa: E731
    roic_niveis = _serie(lambda n: bfc(n).get("roic_pct"))
    divida_liquida_niveis = _serie(lambda n: bfc(n).get("divida_liquida_atual"))
    divida_liquida_yoy = _serie(lambda n: bfc(n).get("divida_liquida_yoy_variacao_pct"))
    # _tendencia() assume "valor sobe" = RECUPERACAO (convenção usada pra
    # receita/EBIT/lucro/margem, onde subir É melhora) - pra dívida
    # líquida é o INVERSO (dívida crescendo ano a ano é deterioração da
    # estrutura de capital, não recuperação). Aplicamos sobre a série de
    # VARIAÇÃO % (mesma escala de p.p. que o limiar _LIMIAR_TENDENCIA_PP
    # já assume - nunca sobre o nível em R$, que estaria em escala
    # totalmente diferente e tornaria o limiar sem sentido), com o sinal
    # invertido - documentado aqui, não um bug.
    divida_liquida_tendencia = _tendencia([-v for v in divida_liquida_yoy])
    ebitda_yoy = _serie(lambda n: bfc(n).get("ebitda_ytd_yoy_variacao_pct"))
    fco_yoy = _serie(lambda n: bfc(n).get("fco_ytd_yoy_variacao_pct"))
    fcf_yoy = _serie(lambda n: bfc(n).get("fcf_ytd_yoy_variacao_pct"))
    capex_yoy = _serie(lambda n: bfc(n).get("capex_ytd_yoy_variacao_pct"))
    dividendos_yoy = _serie(lambda n: bfc(n).get("dividendos_pagos_ytd_yoy_variacao_pct"))

    return {
        "disponivel": True,
        "periodos": [n["periodo_label"] for n in notas],
        "receita_liquida": {"yoy_pct_serie": receita_yoy, "tendencia": _tendencia(receita_yoy)},
        "ebit": {"yoy_pct_serie": ebit_yoy, "tendencia": _tendencia(ebit_yoy)},
        "lucro_liquido_consolidado": {"yoy_pct_serie": lucro_yoy, "tendencia": _tendencia(lucro_yoy)},
        "margem_bruta_pct": {"serie": margem_bruta_niveis, "tendencia": _tendencia(margem_bruta_niveis)},
        "roic_pct": {"serie": roic_niveis, "tendencia": _tendencia(roic_niveis)},
        "divida_liquida": {
            "serie": divida_liquida_niveis, "yoy_pct_serie": divida_liquida_yoy,
            "tendencia": divida_liquida_tendencia,
        },
        "ebitda_ytd": {"yoy_pct_serie": ebitda_yoy, "tendencia": _tendencia(ebitda_yoy)},
        "fco_ytd": {"yoy_pct_serie": fco_yoy, "tendencia": _tendencia(fco_yoy)},
        "fcf_ytd": {"yoy_pct_serie": fcf_yoy, "tendencia": _tendencia(fcf_yoy)},
        "capex_ytd": {"yoy_pct_serie": capex_yoy, "tendencia": _tendencia(capex_yoy)},
        "dividendos_pagos_ytd": {"yoy_pct_serie": dividendos_yoy, "tendencia": _tendencia(dividendos_yoy)},
        "ultima_nota": notas[-1],
    }
