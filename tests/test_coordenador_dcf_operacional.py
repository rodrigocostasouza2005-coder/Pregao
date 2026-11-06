# -*- coding: utf-8 -*-
import pytest

from data.coordenador_central.dcf_operacional import (
    calcular_cenarios_dcf_operacional,
    calcular_dcf_operacional,
    calcular_sensibilidade_dcf_operacional,
)


def _premissas(**overrides):
    p = {
        "receita_base": 1000.0,
        "crescimento_receita": [0.10, 0.08, 0.06, 0.05, 0.04],
        "margem_ebit": [0.15, 0.16, 0.17, 0.17, 0.18],
        "aliquota_impostos": 0.30,
        "da_sobre_receita": [0.03] * 5,
        "capex_sobre_receita": [0.04] * 5,
        "capital_giro_sobre_receita_incremental": [0.10] * 5,
        "wacc": 0.12,
        "g_terminal": 0.03,
        "divida_liquida": 200.0,
        "acoes": 100.0,
        "moeda": "BRL",
        "fonte_premissas": "premissas manuais para teste",
        "data_base": "2026-11-04",
    }
    p.update(overrides)
    return p


def test_dcf_operacional_calcula_projecao_completa_e_preco_alvo():
    r = calcular_dcf_operacional(_premissas(), preco_atual=10.0)
    assert r["disponivel"] is True
    assert len(r["projecao"]) == 5
    ano1 = r["projecao"][0]
    receita = 1100.0
    ebit = receita * 0.15
    nopat = ebit * 0.70
    da = receita * 0.03
    capex = receita * 0.04
    delta_cg = (receita - 1000.0) * 0.10
    assert ano1["fcf"] == pytest.approx(nopat + da - capex - delta_cg)
    assert r["preco_alvo"] > 0
    assert r["upside_pct"] is not None
    assert r["projecao"][-1]["ano"] == 5


def test_dcf_operacional_nao_inventa_drivers_ausentes():
    r = calcular_dcf_operacional({"receita_base": 1000.0})
    assert r["disponivel"] is False
    assert "wacc" in r["campos_faltantes"]
    assert r["projecao"] == []


def test_dcf_operacional_exige_cinco_anos_por_driver():
    r = calcular_dcf_operacional(_premissas(crescimento_receita=[0.1, 0.1]))
    assert r["disponivel"] is False
    assert r["campos_faltantes"] == ["crescimento_receita"]


def test_dcf_operacional_bloqueia_wacc_menor_que_g_terminal():
    r = calcular_dcf_operacional(_premissas(wacc=0.03, g_terminal=0.03))
    assert r["disponivel"] is False
    assert "WACC" in r["motivo"]


def test_dcf_operacional_bloqueia_fcf_terminal_nao_positivo():
    r = calcular_dcf_operacional(_premissas(
        margem_ebit=[-0.50] * 5,
        capex_sobre_receita=[0.20] * 5,
        da_sobre_receita=[0.01] * 5,
    ))
    assert r["disponivel"] is False
    assert "FCF terminal" in r["motivo"]
    assert len(r["projecao"]) == 5


def test_dcf_operacional_nao_aceita_nan_ou_booleano():
    r = calcular_dcf_operacional(_premissas(wacc=float("nan")))
    assert r["disponivel"] is False
    r = calcular_dcf_operacional(_premissas(acoes=True))
    assert r["disponivel"] is False


def test_dcf_operacional_calcula_margem_de_seguranca_quando_ha_preco_atual():
    r = calcular_dcf_operacional(_premissas(), preco_atual=10.0)
    assert r["margem_seguranca_pct"] == pytest.approx((1 - 10.0 / r["preco_alvo"]) * 100)


def test_dcf_operacional_margem_de_seguranca_ausente_sem_preco_atual():
    r = calcular_dcf_operacional(_premissas())
    assert r["margem_seguranca_pct"] is None


# ---------------------------------------------------------------------------
# Cenários (delta uniforme no crescimento de receita)
# ---------------------------------------------------------------------------

def test_cenarios_operacional_base_igual_ao_calculo_direto():
    base_direto = calcular_dcf_operacional(_premissas(), preco_atual=10.0)
    r = calcular_cenarios_dcf_operacional(_premissas(), preco_atual=10.0)
    assert r["disponivel"] is True
    assert r["cenarios"]["base"]["preco_alvo"] == pytest.approx(base_direto["preco_alvo"])


def test_cenarios_operacional_otimista_maior_que_pessimista():
    r = calcular_cenarios_dcf_operacional(
        _premissas(), delta_otimista_pp=3.0, delta_pessimista_pp=-3.0, preco_atual=10.0,
    )
    assert r["disponivel"] is True
    alvo_otimista = r["cenarios"]["otimista"]["preco_alvo"]
    alvo_base = r["cenarios"]["base"]["preco_alvo"]
    alvo_pessimista = r["cenarios"]["pessimista"]["preco_alvo"]
    assert alvo_otimista > alvo_base > alvo_pessimista


def test_cenarios_operacional_delta_zero_fica_igual_ao_base_nos_tres():
    r = calcular_cenarios_dcf_operacional(_premissas(), preco_atual=10.0)
    alvos = {c: r["cenarios"][c]["preco_alvo"] for c in ("otimista", "base", "pessimista")}
    assert alvos["otimista"] == pytest.approx(alvos["base"])
    assert alvos["pessimista"] == pytest.approx(alvos["base"])


def test_cenarios_operacional_nao_inventa_premissas_ausentes():
    r = calcular_cenarios_dcf_operacional({"receita_base": 1000.0})
    assert r["disponivel"] is False
    assert r["cenarios"] == {}


# ---------------------------------------------------------------------------
# Sensibilidade (WACC x crescimento terminal)
# ---------------------------------------------------------------------------

def test_sensibilidade_operacional_matriz_5x5_com_centro_igual_ao_base():
    r = calcular_sensibilidade_dcf_operacional(_premissas(), preco_atual=10.0)
    assert r["disponivel"] is True
    assert len(r["linhas"]) == 5
    linha_central = r["linhas"][2]
    assert linha_central["delta_wacc"] == 0.0
    assert len(linha_central["celulas"]) == 5
    celula_central = linha_central["celulas"][2]
    assert celula_central["delta_g"] == 0.0
    assert celula_central["preco_alvo"] == pytest.approx(r["preco_alvo_base"])


def test_sensibilidade_operacional_preco_alvo_cai_quando_wacc_sobe():
    r = calcular_sensibilidade_dcf_operacional(_premissas(), preco_atual=10.0)
    linha_wacc_menor = next(l for l in r["linhas"] if l["delta_wacc"] == -0.02)
    linha_wacc_maior = next(l for l in r["linhas"] if l["delta_wacc"] == 0.02)
    preco_wacc_menor = next(c for c in linha_wacc_menor["celulas"] if c["delta_g"] == 0.0)["preco_alvo"]
    preco_wacc_maior = next(c for c in linha_wacc_maior["celulas"] if c["delta_g"] == 0.0)["preco_alvo"]
    assert preco_wacc_menor > preco_wacc_maior


def test_sensibilidade_operacional_sem_premissas_nao_disponivel():
    r = calcular_sensibilidade_dcf_operacional({"receita_base": 1000.0})
    assert r["disponivel"] is False
    assert r["linhas"] == []
