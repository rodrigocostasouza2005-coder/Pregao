# -*- coding: utf-8 -*-
"""Testes de data/earnings/cvm_dfc.py com dados REAIS (fixture baixada
de dados.cvm.gov.br em 2026-11-01, DFC método indireto consolidado da
VALE S.A. - CNPJ 33.592.510/0001-54, ver tests/fixtures/earnings/
cvm_itr_dfc_mi_con_vale3_2026.csv). Nenhum teste aqui faz chamada de
rede - _dfc_itr_ano é sempre mockado (via _baixar_csv_do_zip) pra
devolver a fixture."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from data.earnings import cvm_dfc

_FIXTURE_MI = Path(__file__).parent / "fixtures" / "earnings" / "cvm_itr_dfc_mi_con_vale3_2026.csv"


@pytest.fixture
def _mi_fixture():
    return pd.read_csv(_FIXTURE_MI, sep=";", encoding="latin1")


@pytest.fixture(autouse=True)
def _limpa_cache():
    cvm_dfc._dfc_itr_ano.clear()
    yield
    cvm_dfc._dfc_itr_ano.clear()


def _mock_zip_mi_only(mi_df):
    """MD nunca tem dado pra esse CNPJ (confirmado: VALE/PETR4/WEGE3 só
    reportam método indireto) - simula isso devolvendo None pro MD."""
    def _fake(url, nome_no_zip):
        if "DFC_MI" in nome_no_zip:
            return mi_df
        return None
    return _fake


def test_vale_q1_2026_fluxo_de_caixa_real(_mi_fixture):
    """Números conferidos manualmente contra o CSV real da CVM
    (2026-11-01): FCO acumulado (YTD, Q1=janeiro-março) R$9.777 milhões,
    CAPEX (soma das linhas 'Adições ao Imobilizado', valor negativo)
    R$6.244 milhões, dividendos pagos (linha 'Dividendos e juros sobre
    capital próprio pagos aos acionistas') R$14.465 milhões,
    depreciação/amortização R$4.435 milhões."""
    with patch.object(cvm_dfc, "obter_cnpj", return_value="33.592.510/0001-54"), \
         patch.object(cvm_dfc, "_baixar_csv_do_zip", side_effect=_mock_zip_mi_only(_mi_fixture)):
        fluxo = cvm_dfc.obter_fluxo_caixa_trimestral("VALE3", 2026, 1)
    assert fluxo is not None
    assert fluxo["metodo"] == "MI"
    assert fluxo["fco_ytd"] == pytest.approx(9777000.0)
    assert fluxo["capex_ytd"] == pytest.approx(6244000.0)
    assert fluxo["dividendos_pagos_ytd"] == pytest.approx(14465000.0)
    assert fluxo["depreciacao_amortizacao_ytd"] == pytest.approx(4435000.0)


def test_vale_q2_2026_fluxo_de_caixa_acumulado_maior_que_q1(_mi_fixture):
    """Q2 é acumulado Jan-Jun (YTD), nunca o trimestre isolado Abr-Jun -
    por isso o FCO/CAPEX do Q2 são estritamente maiores que o Q1 (mesmo
    ano, mais tempo acumulado), nunca derivados por subtração entre
    os dois (ver docstring do módulo)."""
    with patch.object(cvm_dfc, "obter_cnpj", return_value="33.592.510/0001-54"), \
         patch.object(cvm_dfc, "_baixar_csv_do_zip", side_effect=_mock_zip_mi_only(_mi_fixture)):
        fluxo_q2 = cvm_dfc.obter_fluxo_caixa_trimestral("VALE3", 2026, 2)
    assert fluxo_q2["fco_ytd"] == pytest.approx(22126000.0)
    assert fluxo_q2["capex_ytd"] == pytest.approx(12532000.0)
    assert fluxo_q2["dividendos_pagos_ytd"] == pytest.approx(14465000.0)
    assert fluxo_q2["depreciacao_amortizacao_ytd"] == pytest.approx(9038000.0)
    assert fluxo_q2["fco_ytd"] > 9777000.0
    assert fluxo_q2["capex_ytd"] > 6244000.0


def test_capex_so_soma_linhas_negativas_exclui_alienacao():
    """'Recursos Provenientes na Alienação de Ativos' casaria a mesma
    palavra 'ativo' em outra integração ingênua, mas aqui o filtro é
    por 'imobilizado'/'intang' + só valores NEGATIVOS (saída de caixa) -
    uma linha POSITIVA de alienação de imobilizado NUNCA entra na soma
    de CAPEX (que é aquisição, não venda)."""
    df = pd.DataFrame([
        {"CNPJ_CIA": "11.111.111/0001-11", "DT_REFER": "2026-03-31", "DENOM_CIA": "EMPRESA TESTE",
         "ORDEM_EXERC": "ÚLTIMO", "DT_INI_EXERC": "2026-01-01", "DT_FIM_EXERC": "2026-03-31",
         "CD_CONTA": "6.01", "DS_CONTA": "Caixa Líquido Atividades Operacionais", "VL_CONTA": 1000.0,
         "MOEDA": "REAL", "ESCALA_MOEDA": "MIL"},
        {"CNPJ_CIA": "11.111.111/0001-11", "DT_REFER": "2026-03-31", "DENOM_CIA": "EMPRESA TESTE",
         "ORDEM_EXERC": "ÚLTIMO", "DT_INI_EXERC": "2026-01-01", "DT_FIM_EXERC": "2026-03-31",
         "CD_CONTA": "6.02.01", "DS_CONTA": "Aquisições de ativos imobilizados", "VL_CONTA": -500.0,
         "MOEDA": "REAL", "ESCALA_MOEDA": "MIL"},
        {"CNPJ_CIA": "11.111.111/0001-11", "DT_REFER": "2026-03-31", "DENOM_CIA": "EMPRESA TESTE",
         "ORDEM_EXERC": "ÚLTIMO", "DT_INI_EXERC": "2026-01-01", "DT_FIM_EXERC": "2026-03-31",
         "CD_CONTA": "6.02.02", "DS_CONTA": "Recebimento pela venda de Ativo Imobilizado", "VL_CONTA": 200.0,
         "MOEDA": "REAL", "ESCALA_MOEDA": "MIL"},
    ])
    with patch.object(cvm_dfc, "obter_cnpj", return_value="11.111.111/0001-11"), \
         patch.object(cvm_dfc, "_baixar_csv_do_zip", side_effect=_mock_zip_mi_only(df)):
        fluxo = cvm_dfc.obter_fluxo_caixa_trimestral("TEST3", 2026, 1)
    assert fluxo["capex_ytd"] == pytest.approx(500.0)  # só a linha negativa, nunca 500-200=300


def test_fallback_mi_para_md_quando_mi_nao_tem_dado():
    """Quando MI não devolve dado pro CNPJ/período (ex: zip MI baixou
    mas o CNPJ não está nele), tenta MD - método no retorno confirma
    qual foi usado."""
    md = pd.DataFrame([{
        "CNPJ_CIA": "22.222.222/0001-22", "DT_REFER": "2026-03-31", "DENOM_CIA": "EMPRESA MD",
        "ORDEM_EXERC": "ÚLTIMO", "DT_INI_EXERC": "2026-01-01", "DT_FIM_EXERC": "2026-03-31",
        "CD_CONTA": "6.01", "DS_CONTA": "Caixa Líquido Atividades Operacionais", "VL_CONTA": 2000.0,
        "MOEDA": "REAL", "ESCALA_MOEDA": "MIL",
    }])

    def _fake(url, nome_no_zip):
        if "DFC_MD" in nome_no_zip:
            return md
        return pd.DataFrame(columns=["CNPJ_CIA", "DT_REFER", "ORDEM_EXERC", "CD_CONTA", "VL_CONTA"])

    with patch.object(cvm_dfc, "obter_cnpj", return_value="22.222.222/0001-22"), \
         patch.object(cvm_dfc, "_baixar_csv_do_zip", side_effect=_fake):
        fluxo = cvm_dfc.obter_fluxo_caixa_trimestral("TEST3", 2026, 1)
    assert fluxo is not None
    assert fluxo["metodo"] == "MD"
    assert fluxo["fco_ytd"] == pytest.approx(2000.0)
    assert fluxo["depreciacao_amortizacao_ytd"] is None  # MD não tem reconciliação, nunca inventa


def test_ticker_sem_cnpj_mapeado_devolve_none():
    with patch.object(cvm_dfc, "obter_cnpj", return_value=None):
        assert cvm_dfc.obter_fluxo_caixa_trimestral("XXXX3", 2026, 1) is None


def test_trimestre_4_nao_suportado_devolve_none():
    with patch.object(cvm_dfc, "obter_cnpj", return_value="33.592.510/0001-54"):
        assert cvm_dfc.obter_fluxo_caixa_trimestral("VALE3", 2026, 4) is None


def test_nenhum_metodo_tem_dado_devolve_none():
    with patch.object(cvm_dfc, "obter_cnpj", return_value="99.999.999/0001-99"), \
         patch.object(cvm_dfc, "_baixar_csv_do_zip", return_value=None):
        assert cvm_dfc.obter_fluxo_caixa_trimestral("NADA3", 2026, 1) is None


def test_registra_tentativa_de_sucesso_e_falha(_mi_fixture):
    with patch("data.earnings.cvm_dfc.registrar_tentativa") as mock_reg:
        with patch.object(cvm_dfc, "_baixar_csv_do_zip", return_value=_mi_fixture):
            cvm_dfc._dfc_itr_ano(2026, "MI")
        assert mock_reg.call_args.kwargs.get("execucao_ok") is True

    cvm_dfc._dfc_itr_ano.clear()
    with patch("data.earnings.cvm_dfc.registrar_tentativa") as mock_reg:
        with patch.object(cvm_dfc, "_baixar_csv_do_zip", return_value=None):
            cvm_dfc._dfc_itr_ano(2026, "MI")
        assert mock_reg.call_args.kwargs.get("execucao_ok") is False
