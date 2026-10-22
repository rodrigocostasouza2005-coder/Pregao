# -*- coding: utf-8 -*-
"""Testes de data/earnings/cvm_dre.py com dados REAIS (fixture baixada
de dados.cvm.gov.br em 2026-10-22, DRE consolidada da VALE S.A. -
CNPJ 33.592.510/0001-54, ver tests/fixtures/earnings/
cvm_itr_dre_con_vale3_2026.csv). Nenhum teste aqui faz chamada de rede -
_baixar_csv_do_zip e' sempre mockado pra devolver a fixture."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from data.earnings import cvm_dre

_FIXTURE = Path(__file__).parent / "fixtures" / "earnings" / "cvm_itr_dre_con_vale3_2026.csv"


@pytest.fixture
def _df_fixture():
    return pd.read_csv(_FIXTURE, sep=";", encoding="latin1")


@pytest.fixture(autouse=True)
def _limpa_cache():
    cvm_dre._dre_itr_ano.clear()
    yield
    cvm_dre._dre_itr_ano.clear()


def test_vale_q2_2026_receita_e_lucro_reais(_df_fixture):
    """Numeros conferidos manualmente contra o CSV real da CVM (2026-10-22):
    receita do 2T2026 isolado = R$53.012 milhoes; mesmo trimestre de
    2025 (YoY, PENÚLTIMO) = R$49.807 milhoes."""
    with patch.object(cvm_dre, "obter_cnpj", return_value="33.592.510/0001-54"), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=_df_fixture):
        nota = cvm_dre.obter_dre_trimestral("VALE3", 2026, 2)
    assert nota is not None
    assert nota["empresa"] == "VALE S.A."
    assert nota["contas"]["receita_liquida"]["atual"] == pytest.approx(53012000.0)
    assert nota["contas"]["receita_liquida"]["ano_anterior"] == pytest.approx(49807000.0)
    assert nota["contas"]["lucro_liquido_controladora"]["atual"] == pytest.approx(6847000.0)
    assert nota["contas"]["lucro_liquido_controladora"]["ano_anterior"] == pytest.approx(12081000.0)


def test_vale_q1_2026_so_tem_1_linha_por_conta_e_bate_com_q2(_df_fixture):
    """1T nao tem acumulado x isolado (o acumulado JA' e' o trimestre) -
    e serve de comparador QoQ real pro 2T (receita 2T > 1T, lucro 2T < 1T,
    valores conferidos no CSV)."""
    with patch.object(cvm_dre, "obter_cnpj", return_value="33.592.510/0001-54"), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=_df_fixture):
        nota_q1 = cvm_dre.obter_dre_trimestral("VALE3", 2026, 1)
    assert nota_q1["contas"]["receita_liquida"]["atual"] == pytest.approx(48680000.0)
    assert nota_q1["contas"]["lucro_liquido_controladora"]["atual"] == pytest.approx(9953000.0)


def test_ticker_sem_cnpj_mapeado_devolve_none():
    with patch.object(cvm_dre, "obter_cnpj", return_value=None):
        assert cvm_dre.obter_dre_trimestral("XXXX3", 2026, 2) is None


def test_fonte_cvm_indisponivel_devolve_none():
    with patch.object(cvm_dre, "obter_cnpj", return_value="33.592.510/0001-54"), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=None):
        assert cvm_dre.obter_dre_trimestral("VALE3", 2026, 2) is None


def test_trimestre_4_nao_suportado_devolve_none():
    with patch.object(cvm_dre, "obter_cnpj", return_value="33.592.510/0001-54"):
        assert cvm_dre.obter_dre_trimestral("VALE3", 2026, 4) is None


def test_ticker_sem_registro_no_ano_devolve_none(_df_fixture):
    with patch.object(cvm_dre, "obter_cnpj", return_value="00.000.000/0000-00"), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=_df_fixture):
        assert cvm_dre.obter_dre_trimestral("NADA3", 2026, 2) is None


def test_conta_so_com_linha_acumulada_fica_none_nunca_estimado():
    """Sintetico (nao e' o caso da Vale, que desagrega tudo): se a
    empresa so' reportar o SEMESTRE (sem linha de trimestre isolado),
    o valor fica None - nunca deriva por subtracao."""
    df = pd.DataFrame([{
        "CNPJ_CIA": "11.111.111/0001-11", "DT_REFER": "2026-06-30", "DENOM_CIA": "EMPRESA TESTE",
        "ORDEM_EXERC": "ÚLTIMO", "DT_INI_EXERC": "2026-01-01", "DT_FIM_EXERC": "2026-06-30",
        "CD_CONTA": "3.01", "VL_CONTA": 1000.0, "MOEDA": "REAL", "ESCALA_MOEDA": "MIL",
    }])
    with patch.object(cvm_dre, "obter_cnpj", return_value="11.111.111/0001-11"), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=df):
        nota = cvm_dre.obter_dre_trimestral("TEST3", 2026, 2)
    assert nota["contas"]["receita_liquida"]["atual"] is None


def test_registra_tentativa_de_sucesso_e_falha(_df_fixture):
    with patch("data.earnings.cvm_dre.registrar_tentativa") as mock_reg:
        with patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=_df_fixture):
            cvm_dre._dre_itr_ano(2026)
        assert mock_reg.call_args.kwargs.get("execucao_ok") is True

    cvm_dre._dre_itr_ano.clear()
    with patch("data.earnings.cvm_dre.registrar_tentativa") as mock_reg:
        with patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=None):
            cvm_dre._dre_itr_ano(2026)
        assert mock_reg.call_args.kwargs.get("execucao_ok") is False
