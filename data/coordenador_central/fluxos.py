# -*- coding: utf-8 -*-
"""Fluxos de alto nível do Coordenador Central - o que a UI (ver
ui/coordenador_tab.py) chama. Cada fluxo grava 1 linha de execução
ANTES de rodar qualquer especialista e ATUALIZA ao final (nunca grava só
no fim - se o processo cair no meio, fica rastro de que começou, ver
data/coordenador_central/persistencia.py).

Fluxo A - analisar_ticker: visão agregada de 1 ticker.
Fluxo B - comparar_casas: comparação entre casas de research + as
publicações originais que sustentam cada posição.
Fluxo C - identificar_catalisadores: eventos que podem mover o papel.

Encadeamento real (Fluxo B): só aciona memoria_research se o comparador
já indicou que existe pelo menos 1 casa cobrindo o ticker - sem isso,
memoria_research(ticker=X) sempre devolveria zero resultado (mesma
fonte de dado do comparador) e só gastaria uma chamada sem benefício."""

import time

from data.coordenador_central import consolidacao, executor, persistencia


def _especialista_pulado(especialista_id: str, motivo: str) -> dict:
    """Resultado no mesmo formato de executor.py, mas sem rodar nada -
    usado quando um fluxo decide, com base no resultado de outro
    especialista, que não vale a pena acionar este (ver comparar_casas)."""
    return {
        "id": especialista_id, "execucao_id": None, "disponivel": True,
        "resumo": motivo, "evidencias": [], "motivo_indisponivel": None,
        "duracao_ms": 0, "erro_tecnico": None, "dados": None, "pulado": True,
    }


def _registrar_execucoes(analise_id: str, resultados: dict) -> bool:
    """Persiste apenas especialistas realmente acionados; itens pulados não
    entram na taxa de sucesso. False sinaliza perda de telemetria."""
    persistidos = True
    for especialista_id, resultado in resultados.items():
        if resultado.get("pulado"):
            continue
        ok = persistencia.registrar_execucao_especialista(analise_id, especialista_id, resultado)
        persistidos = bool(ok) and persistidos
    return persistidos


def _status_fluxo(resultados: dict, telemetria_ok: bool) -> str:
    """CONCLUIDA somente quando pelo menos um especialista foi acionado,
    todos responderam e a telemetria foi persistida; ausência de execução
    real ou indisponibilidade documentada vira PARCIAL."""
    acionados = [r for r in resultados.values() if not r.get("pulado")]
    todos_disponiveis = bool(acionados) and all(bool(r.get("disponivel")) for r in acionados)
    return "CONCLUIDA" if todos_disponiveis and telemetria_ok else "PARCIAL"


def _concluir_com_erro(analise_id: str, exc: Exception, duracao_ms: int = None) -> None:
    persistencia.concluir_analise(analise_id, "ERRO", None, erro=repr(exc), duracao_ms=duracao_ms)


def _concluir_fluxo(analise_id: str, consolidado: dict, resultados: dict, telemetria_ok: bool, duracao_ms: int) -> None:
    """Finaliza o fluxo e não anuncia CONCLUIDA se a gravação do resultado falhar."""
    status = _status_fluxo(resultados, telemetria_ok)
    consolidado["status_execucao"] = status
    persistida = persistencia.concluir_analise(analise_id, status, consolidado, duracao_ms=duracao_ms)
    consolidado["persistencia_analise_ok"] = bool(persistida)
    if not persistida:
        consolidado["status_execucao"] = "PARCIAL"


def _moeda_normalizada(valor) -> str | None:
    """Normaliza apenas aliases inequívocos; moeda desconhecida não é presumida."""
    texto = str(valor or "").strip().upper()
    aliases = {
        "BRL": "BRL", "REAL": "BRL", "REAIS": "BRL", "R$": "BRL",
        "USD": "USD", "US$": "USD", "DOLAR": "USD", "DÓLAR": "USD",
    }
    return aliases.get(texto)


def _anexar_premissas_dcf(resultados: dict, premissas_usuario: dict | None) -> None:
    """Combina taxas manuais com dados observados e dívida líquida reportada.

    FCF e valor de mercado/cotação vêm dos fundamentos do yfinance. Para
    dívida líquida, prioriza o balanço consolidado da CVM (valores já
    convertidos pelo Earnings Reviewer para reais absolutos) quando a
    moeda reportada coincide com a moeda da cotação. Só usa EBITDA ×
    alavancagem do yfinance como fallback explícito quando a moeda também
    está confirmada. Nunca mistura moedas nem trata FCF YTD como TTM.
    """
    if not isinstance(premissas_usuario, dict):
        return
    analise = resultados.get("analise_ticker") or {}
    dados = analise.get("dados") or {}
    fundamentos = dados.get("fundamentos") or {}
    fcf = fundamentos.get("fluxo_caixa_livre")
    ebitda = fundamentos.get("ebitda")
    alavancagem = fundamentos.get("divida_liquida_ebitda")
    preco = fundamentos.get("preco")
    valor_mercado = fundamentos.get("valor_mercado")
    moeda_cotacao = fundamentos.get("moeda")
    moeda_fonte = fundamentos.get("moeda_fonte")
    moeda_base = _moeda_normalizada(moeda_cotacao)
    moeda_fundamentos = _moeda_normalizada(moeda_fonte)
    moeda_yfinance_compativel = bool(moeda_base and moeda_fundamentos and moeda_base == moeda_fundamentos)

    resultado_earnings = resultados.get("resultados_corporativos") or {}
    nota_earnings = resultado_earnings.get("dados") or {}
    bfc = nota_earnings.get("balanco_fluxo_caixa") or {}
    moeda_cvm = _moeda_normalizada(nota_earnings.get("moeda"))
    divida_cvm = bfc.get("divida_liquida_atual")
    cvm_compativel = bool(moeda_base and moeda_cvm and moeda_base == moeda_cvm)

    try:
        divida_liquida = None
        origem_divida = None
        fonte_divida = None
        if cvm_compativel and isinstance(divida_cvm, (int, float)) and not isinstance(divida_cvm, bool):
            divida_liquida = float(divida_cvm)
            origem_divida = "CVM — balanço patrimonial consolidado"
            fonte_divida = (
                f"CVM ITR {nota_earnings.get('periodo_label') or nota_earnings.get('dt_referencia') or 'período não informado'}"
            )
        elif moeda_yfinance_compativel and ebitda is not None and alavancagem is not None:
            divida_liquida = float(ebitda) * float(alavancagem)
            origem_divida = "Estimativa — EBITDA × dívida líquida/EBITDA"
            fonte_divida = "yfinance — fundamentos e indicador de alavancagem"
        acoes = (
            float(valor_mercado) / float(preco)
            if moeda_yfinance_compativel and valor_mercado is not None
            and preco is not None and float(preco) > 0 else None
        )
        campos = {
            "fcf_base": fcf if moeda_yfinance_compativel else None,
            "crescimento_fcf_otimista": float(premissas_usuario["crescimento_fcf_otimista"]) / 100,
            "crescimento_fcf_base": float(premissas_usuario["crescimento_fcf_base"]) / 100,
            "crescimento_fcf_pessimista": float(premissas_usuario["crescimento_fcf_pessimista"]) / 100,
            "wacc": float(premissas_usuario["wacc"]) / 100,
            "g_terminal": float(premissas_usuario["g_terminal"]) / 100,
            "divida_liquida": divida_liquida,
            "acoes": acoes,
            "moeda": moeda_cotacao,
            "origem_divida_liquida": origem_divida,
            "fonte_divida_liquida": fonte_divida,
            "motivo_bloqueio": None if moeda_yfinance_compativel else (
                f"Moeda de origem dos fundamentos ({moeda_fonte or 'não informada'}) não foi confirmada "
                f"como igual à moeda da cotação ({moeda_cotacao or 'não informada'}); conversão não é presumida."
            ),
            "fonte_premissas": (
                "FCF, valor de mercado, cotação e moeda: yfinance; "
                f"dívida líquida: {'estimativa — ' if origem_divida == 'Estimativa — EBITDA × dívida líquida/EBITDA' else ''}{fonte_divida or 'indisponível por falta de dado/moeda compatível'}; "
                "taxas de crescimento e WACC: premissas manuais do usuário."
            ),
            "data_base": str(
                nota_earnings.get("dt_referencia")
                if origem_divida == "CVM — balanço patrimonial consolidado"
                else fundamentos.get("consultado_em") or ""
            ),
        }
    except (KeyError, TypeError, ValueError, OverflowError):
        return
    dados["premissas_dcf"] = campos
    analise["dados"] = dados
    resultados["analise_ticker"] = analise


def analisar_ticker(ticker: str, premissas_dcf: dict | None = None) -> dict:
    """Fluxo A: fundamentos/catalisadores/cobertura (analise_ticker) +
    comparação entre casas (comparador) + publicações originais
    (memoria_research) + notícias + catalisadores de calendário - tudo
    em paralelo via executor.executar_varios.
    premissas_dcf é opcional e nunca recebe defaults silenciosos."""
    ticker = (ticker or "").strip().upper()
    analise_id = persistencia.iniciar_analise(f"Analisar {ticker}", "analise_ticker", ticker)
    inicio = time.monotonic()
    try:
        resultados = executor.executar_varios(
            ["analise_ticker", "comparador", "memoria_research", "noticias", "catalisadores", "resultados_corporativos"], ticker=ticker,
        )
        _anexar_premissas_dcf(resultados, premissas_dcf)
        dados_analise = (resultados.get('analise_ticker') or {}).get('dados') or {}
        fundamentos = dados_analise.get('fundamentos') or {}
        premissas_modelo = dados_analise.get('premissas_dcf')
        resultado_model_builder = executor.executar_especialista('model_builder', ticker=ticker, premissas_dcf=premissas_modelo, preco_atual=fundamentos.get('preco'))
        resultado_valor = executor.executar_especialista('valuation_reviewer', ticker=ticker, model_builder=resultado_model_builder.get('dados') or {})
        if premissas_dcf is None:
            # Nenhuma premissa de DCF foi fornecida a ESTA chamada (nem
            # pelo job noturno - jobs/comite_noturno.py nunca passa
            # premissas_dcf -, nem pela UI quando o analista não marca
            # "Calcular DCF" em ui/coordenador_tab.py:render_analisar).
            # O motor (data/coordenador_central/dcf.py) corretamente se
            # recusa a inventar WACC/crescimento, então model_builder e
            # valuation_reviewer SEMPRE voltam disponivel=False neste
            # caminho - não por falha, mas por design. Sem este marcador,
            # _status_fluxo (abaixo) rebaixava TODA análise sem DCF
            # manual para PARCIAL, inclusive numa noite perfeita do
            # comitê noturno, por um motivo esperado e correto, não uma
            # falha real. "pulado" é o mesmo padrão já usado acima
            # (_especialista_pulado/comparar_casas) para memoria_research
            # sem cobertura: não conta como "acionado" no status do
            # fluxo nem na telemetria agregada de metricas_especialistas
            # (ver persistencia.py) - os dados/motivo originais (ex.:
            # "Premissas DCF explícitas não fornecidas...") continuam
            # intactos e visíveis no resultado consolidado; só muda a
            # classificação do fluxo. Quando o usuário FORNECE premissas
            # (mesmo que incompletas/bloqueadas por moeda incompatível),
            # premissas_dcf não é None aqui e o resultado continua
            # contando de verdade para PARCIAL - só o caminho "nunca
            # pedi DCF" é tratado como skip.
            resultado_model_builder = {**resultado_model_builder, "pulado": True}
            resultado_valor = {**resultado_valor, "pulado": True}
        resultados['model_builder'] = resultado_model_builder
        resultados['valuation_reviewer'] = resultado_valor
        telemetria_ok = _registrar_execucoes(analise_id, resultados)
        consolidado = consolidacao.consolidar(resultados, ticker=ticker)
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        _concluir_fluxo(analise_id, consolidado, resultados, telemetria_ok, duracao_ms)
        consolidado["_analise_id"] = analise_id
        consolidado["_duracao_ms"] = duracao_ms
        return consolidado
    except Exception as exc:
        _concluir_com_erro(analise_id, exc, int((time.monotonic() - inicio) * 1000))
        raise


def comparar_casas(ticker: str, casas: list = None) -> dict:
    """Fluxo B: comparador primeiro; memoria_research só é acionado se o
    comparador encontrou cobertura real (ver docstring do módulo -
    encadeamento). `casas` filtra memoria_research por 1, várias ou
    nenhuma casa (2026-11-01: embeddings.buscar/store.listar_premissas
    agora aceitam lista - gap antigo "só filtra com exatamente 1 casa"
    fechado, repassa `casas` inteira direto)."""
    ticker = (ticker or "").strip().upper()
    analise_id = persistencia.iniciar_analise(f"Comparar casas sobre {ticker}", "comparar_casas", ticker)
    inicio = time.monotonic()
    try:
        resultado_comparador = executor.executar_especialista("comparador", ticker=ticker)
        resultados = {"comparador": resultado_comparador}

        dados_comparador = resultado_comparador.get("dados") or {}
        # O contrato público de montar_relatorio_comparativo expõe as casas
        # em tabela_comparativa (não em "casas"). O fallback legado mantém
        # compatibilidade com extratores antigos.
        casas_encontradas = dados_comparador.get("casas") or [
            linha.get("casa") for linha in (dados_comparador.get("tabela_comparativa") or [])
            if linha.get("casa")
        ]
        if casas_encontradas:
            casa_filtro = list(casas) if casas else None
            resultados["memoria_research"] = executor.executar_especialista(
                "memoria_research", ticker=ticker, casa=casa_filtro,
            )
        else:
            resultados["memoria_research"] = _especialista_pulado(
                "memoria_research",
                "Não acionado: o comparador não encontrou nenhuma casa cobrindo este ticker na biblioteca "
                "permanente de research - buscar as publicações originais não traria nenhum resultado novo.",
            )

        telemetria_ok = _registrar_execucoes(analise_id, resultados)
        consolidado = consolidacao.consolidar(resultados, ticker=ticker)
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        _concluir_fluxo(analise_id, consolidado, resultados, telemetria_ok, duracao_ms)
        consolidado["_analise_id"] = analise_id
        consolidado["_duracao_ms"] = duracao_ms
        return consolidado
    except Exception as exc:
        _concluir_com_erro(analise_id, exc, int((time.monotonic() - inicio) * 1000))
        raise


def identificar_catalisadores(ticker: str) -> dict:
    """Fluxo C: catalisadores de calendário/proventos + notícias +
    próximo resultado esperado + publicações da memória de research que
    mencionem o ticker - tudo em paralelo."""
    ticker = (ticker or "").strip().upper()
    analise_id = persistencia.iniciar_analise(f"Identificar catalisadores de {ticker}", "catalisadores", ticker)
    inicio = time.monotonic()
    try:
        resultados = executor.executar_varios(
            ["catalisadores", "noticias", "calendario", "memoria_research"], ticker=ticker,
        )
        telemetria_ok = _registrar_execucoes(analise_id, resultados)
        consolidado = consolidacao.consolidar(resultados, ticker=ticker)
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        _concluir_fluxo(analise_id, consolidado, resultados, telemetria_ok, duracao_ms)
        consolidado["_analise_id"] = analise_id
        consolidado["_duracao_ms"] = duracao_ms
        return consolidado
    except Exception as exc:
        _concluir_com_erro(analise_id, exc, int((time.monotonic() - inicio) * 1000))
        raise
