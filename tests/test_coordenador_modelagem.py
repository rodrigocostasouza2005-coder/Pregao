# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.coordenador_central import modelagem

def test_model_builder_sem_premissas_nao_inventa():
    resultado = modelagem.modelar_empresa('PETR4', None, preco_atual=30)
    assert resultado['disponivel'] is False
    assert resultado['campos_faltantes'] == ['premissas_dcf']
    assert resultado['cenarios'] == {}

def _premissas():
    return {
        "fcf_base": 1000.0, "wacc": 0.10, "g_terminal": 0.03,
        "divida_liquida": 100.0, "acoes": 100.0,
        "crescimento_fcf_otimista": 0.12, "crescimento_fcf_base": 0.08,
        "crescimento_fcf_pessimista": 0.02, "moeda": "BRL",
        "fonte_premissas": "CVM/yfinance + premissas manuais",
        "data_base": "2026-09-30",
    }


def test_model_builder_entrega_tres_cenarios_e_sensibilidade():
    resultado = modelagem.modelar_empresa("PETR4", _premissas(), preco_atual=30.0)
    assert resultado["disponivel"] is True
    assert set(resultado["cenarios"]) == {"otimista", "base", "pessimista"}
    assert resultado["sensibilidade"]["disponivel"] is True


def test_model_builder_bloqueia_moeda_incompativel():
    premissas = _premissas()
    premissas["motivo_bloqueio"] = "Moeda USD difere da cotação BRL."
    resultado = modelagem.modelar_empresa("PETR4", premissas, preco_atual=30.0)
    assert resultado["disponivel"] is False
    assert "Moeda" in resultado["motivo"]


def test_valuation_reviewer_revisa_saida_do_model_builder():
    modelo = modelagem.modelar_empresa("PETR4", _premissas(), preco_atual=30.0)
    revisao = modelagem.revisar_valuation("PETR4", modelo)
    assert revisao["disponivel"] is True
    assert revisao["aprovado"] is True
    assert revisao["precos_alvo_revisados"]["base"] == modelo["cenarios"]["base"]["preco_alvo"]


def test_valuation_reviewer_nao_revisa_modelo_indisponivel():
    revisao = modelagem.revisar_valuation("PETR4", {"disponivel": False, "motivo": "sem premissas"})
    assert revisao["disponivel"] is False
    assert "Model Builder" in revisao["motivo"]
