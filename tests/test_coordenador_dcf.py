# -*- coding: utf-8 -*-
"""Testes puros do DCF de três cenários."""
from data.coordenador_central.dcf import calcular_dcf


def _premissas(**sobrescritas):
    base = {
        "fcf_base": 1000.0,
        "crescimento_fcf_otimista": 0.12,
        "crescimento_fcf_base": 0.08,
        "crescimento_fcf_pessimista": 0.02,
        "wacc": 0.12,
        "g_terminal": 0.03,
        "divida_liquida": 500.0,
        "acoes": 100.0,
        "fonte_premissas": "teste",
        "data_base": "2026-11-04",
    }
    base.update(sobrescritas)
    return base


def test_dcf_calcula_tres_cenarios_e_ordena_alvos():
    resultado = calcular_dcf(_premissas(), preco_atual=20.0)
    assert resultado["disponivel"] is True
    cenarios = resultado["cenarios"]
    assert set(cenarios) == {"otimista", "base", "pessimista"}
    assert cenarios["otimista"]["preco_alvo"] > cenarios["base"]["preco_alvo"]
    assert cenarios["base"]["preco_alvo"] > cenarios["pessimista"]["preco_alvo"]
    assert cenarios["base"]["upside_pct"] is not None
    assert len(cenarios["base"]["projecao"]) == 5


def test_dcf_nao_inventa_premissas_ausentes():
    resultado = calcular_dcf({"fcf_base": 100.0}, preco_atual=10.0)
    assert resultado["disponivel"] is False
    assert "wacc" in resultado["campos_faltantes"]
    assert resultado["cenarios"] == {}


def test_dcf_bloqueia_wacc_menor_ou_igual_ao_crescimento_terminal():
    resultado = calcular_dcf(_premissas(wacc=0.03, g_terminal=0.03), preco_atual=10.0)
    assert resultado["disponivel"] is False
    assert "WACC" in resultado["motivo"]


def test_dcf_bloqueia_fcf_negativo_e_acoes_invalidas():
    assert calcular_dcf(_premissas(fcf_base=-10), 10)["disponivel"] is False
    assert calcular_dcf(_premissas(acoes=0), 10)["disponivel"] is False


def test_dcf_aceita_caixa_liquido_como_divida_negativa():
    resultado = calcular_dcf(_premissas(divida_liquida=-500), preco_atual=20)
    assert resultado["disponivel"] is True
    assert resultado["cenarios"]["base"]["valor_patrimonio"] > resultado["cenarios"]["base"]["valor_empresa"]



def test_fluxo_monta_premissas_somente_com_dados_observados_e_taxas_manuais():
    from data.coordenador_central.fluxos import _anexar_premissas_dcf

    resultados = {"analise_ticker": {"dados": {"fundamentos": {
        "fluxo_caixa_livre": 1000.0, "ebitda": 500.0,
        "divida_liquida_ebitda": 1.2, "valor_mercado": 10000.0,
        "preco": 20.0, "moeda": "BRL", "moeda_fonte": "BRL", "consultado_em": "2026-11-04",
    }}}}
    taxas = {
        "crescimento_fcf_otimista": 12, "crescimento_fcf_base": 8,
        "crescimento_fcf_pessimista": 2, "wacc": 12, "g_terminal": 3,
    }
    _anexar_premissas_dcf(resultados, taxas)
    premissas = resultados["analise_ticker"]["dados"]["premissas_dcf"]
    assert premissas["fcf_base"] == 1000.0
    assert premissas["divida_liquida"] == 600.0
    assert premissas["acoes"] == 500.0
    assert premissas["wacc"] == 0.12
    assert premissas["crescimento_fcf_base"] == 0.08


def test_fluxo_nao_inventa_dados_base_quando_fundamentos_faltam():
    from data.coordenador_central.fluxos import _anexar_premissas_dcf

    resultados = {"analise_ticker": {"dados": {"fundamentos": {"preco": 10.0}}}}
    taxas = {
        "crescimento_fcf_otimista": 12, "crescimento_fcf_base": 8,
        "crescimento_fcf_pessimista": 2, "wacc": 12, "g_terminal": 3,
    }
    _anexar_premissas_dcf(resultados, taxas)
    premissas = resultados["analise_ticker"]["dados"]["premissas_dcf"]
    resultado = calcular_dcf(premissas, preco_atual=10)
    assert resultado["disponivel"] is False
    assert "Moeda de origem" in resultado["motivo"]



def test_pareceres_nao_atribuem_dcf_ao_reviewer_sem_execucao_do_model_builder():
    from data.coordenador_central.pareceres import montar_pareceres

    premissas = _premissas()
    premissas["moeda"] = "BRL"
    resultado = montar_pareceres({
        "analise_ticker": {"dados": {
            "fundamentos": {"preco": 20.0, "pl": 10.0},
            "premissas_dcf": premissas,
        }},
    }, ticker="TEST3")
    model_builder = next(a for a in resultado["analistas"] if a["id"] == "model_builder")
    reviewer = next(a for a in resultado["analistas"] if a["id"] == "valuation_reviewer")
    # O parecer não executa especialistas implicitamente nem apresenta
    # um DCF como revisado quando o fluxo não acionou Model Builder.
    assert model_builder["recomendacao"] == "INSUFICIENTE"
    assert reviewer["recomendacao"] == "INSUFICIENTE"
    assert reviewer["preco_alvo"] is None



def test_fluxo_bloqueia_calculo_quando_moeda_da_cotacao_e_fonte_divergem():
    from data.coordenador_central.fluxos import _anexar_premissas_dcf

    resultados = {"analise_ticker": {"dados": {"fundamentos": {
        "fluxo_caixa_livre": 1000.0, "ebitda": 500.0,
        "divida_liquida_ebitda": 1.2, "valor_mercado": 10000.0,
        "preco": 20.0, "moeda": "BRL", "moeda_fonte": "USD",
    }}}}
    taxas = {
        "crescimento_fcf_otimista": 12, "crescimento_fcf_base": 8,
        "crescimento_fcf_pessimista": 2, "wacc": 12, "g_terminal": 3,
    }
    _anexar_premissas_dcf(resultados, taxas)
    premissas = resultados["analise_ticker"]["dados"]["premissas_dcf"]
    resultado = calcular_dcf(premissas, preco_atual=20)
    assert resultado["disponivel"] is False
    assert "Moeda" in resultado["motivo"]


def test_sensibilidade_dcf_matriz_5x5_e_centro_igual_ao_cenario_base():
    from data.coordenador_central.dcf import calcular_sensibilidade_dcf

    premissas = _premissas()
    resultado = calcular_sensibilidade_dcf(premissas, preco_atual=20)
    assert resultado["disponivel"] is True
    assert len(resultado["linhas"]) == 5
    assert all(len(linha["celulas"]) == 5 for linha in resultado["linhas"])
    centro = resultado["linhas"][2]["celulas"][2]["preco_alvo"]
    base = calcular_dcf(premissas, preco_atual=20)["cenarios"]["base"]["preco_alvo"]
    assert centro == base


def test_sensibilidade_dcf_bloqueia_premissas_invalidas_sem_inventar():
    from data.coordenador_central.dcf import calcular_sensibilidade_dcf

    resultado = calcular_sensibilidade_dcf(_premissas(wacc=0.02, g_terminal=0.03), preco_atual=20)
    assert resultado["disponivel"] is False
    assert resultado["linhas"] == []



def test_dcf_preserva_origem_e_fonte_da_divida_para_auditoria():
    premissas = _premissas(
        origem_divida_liquida="CVM — balanço patrimonial consolidado",
        fonte_divida_liquida="CVM ITR 2T2026",
    )
    resultado = calcular_dcf(premissas, preco_atual=20.0)
    assert resultado["disponivel"] is True
    assert resultado["premissas"]["origem_divida_liquida"] == "CVM — balanço patrimonial consolidado"
    assert resultado["premissas"]["fonte_divida_liquida"] == "CVM ITR 2T2026"
