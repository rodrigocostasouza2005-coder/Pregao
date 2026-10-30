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

from data.coletores_status import registrar_tentativa
from data.earnings import cvm_dre, sec_xbrl
from data.supabase_client import obter_cliente

_NOME_COLETOR = "EARNINGS REVIEWER (persistencia)"

_TABELA = "earnings_reviews"

LIMITACOES_PADRAO = (
    "Sem acesso a consenso de mercado, guidance da empresa ou relatorios "
    "pagos de research nesta integracao - so' numeros reportados nas "
    "fontes oficiais citadas em FONTES.",
    "ROIC e indicadores de retorno sobre capital nao calculados nesta "
    "versao (exigem dados de balanco/capital investido fora do escopo "
    "atual, so' DRE).",
    "Resultado por segmento nao coberto nesta versao.",
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


def montar_nota_br(ticker: str, ano: int, trimestre: int) -> dict:
    """Nota de UMA empresa brasileira pro trimestre pedido. `disponivel`
    e' False (com `motivo`) quando cvm_dre nao devolveu nada pra esse
    ticker/periodo - nunca gera nota com numero inventado nesse caso."""
    atual = cvm_dre.obter_dre_trimestral(ticker, ano, trimestre)
    if atual is None:
        return {
            "ticker": ticker.upper(), "pais": "BR", "disponivel": False,
            "motivo": "DRE indisponivel (ticker sem CNPJ mapeado na CVM, "
                      "fonte fora do ar, ou sem registro desse trimestre).",
        }

    metricas = _montar_metricas_br(atual["contas"])

    qoq_trimestre = trimestre - 1
    qoq = cvm_dre.obter_dre_trimestral(ticker, ano, qoq_trimestre) if qoq_trimestre >= 1 else None
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

    return {
        "ticker": ticker.upper(), "empresa": atual["empresa"], "pais": "BR",
        "disponivel": True, "periodo_label": f"{trimestre}T{ano}",
        "dt_referencia": atual["dt_referencia"], "moeda": atual["moeda"],
        "escala_moeda": atual["escala_moeda"], "metricas": metricas,
        "margem_bruta_pct": margem_bruta, "margem_bruta_yoy_anterior_pct": margem_bruta_ant,
        "interpretacoes": interpretacoes, "educacao_financeira": _nota_educativa_receita_vs_lucro(metricas),
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
