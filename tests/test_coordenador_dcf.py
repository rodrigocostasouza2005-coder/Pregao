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
