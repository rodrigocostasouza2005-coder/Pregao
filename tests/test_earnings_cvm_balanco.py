# -*- coding: utf-8 -*-
"""Testes de data/earnings/cvm_balanco.py com dados REAIS (fixtures
baixadas de dados.cvm.gov.br em 2026-11-01, Balanço Patrimonial
consolidado da VALE S.A. - CNPJ 33.592.510/0001-54, ver
tests/fixtures/earnings/cvm_itr_bpa_con_vale3_2026.csv e
cvm_itr_bpp_con_vale3_2026.csv - mesma empresa já usada em
test_earnings_cvm_dre.py). Nenhum teste aqui faz chamada de rede -
_baixar_csv_do_zip é sempre mockado pra devolver a fixture."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from data.earnings import cvm_balanco

_FIXTURE_BPA = Path(__file__).parent / "fixtures" / "earnings" / "cvm_itr_bpa_con_vale3_2026.csv"
_FIXTURE_BPP = Path(__file__).parent / "fixtures" / "earnings" / "cvm_itr_bpp_con_vale3_2026.csv"


@pytest.fixture
def _bpa_fixture():
    return pd.read_csv(_FIXTURE_BPA, sep=";", encoding="latin1")


@pytest.fixture
def _bpp_fixture():
    return pd.read_csv(_FIXTURE_BPP, sep=";", encoding="latin1")


@pytest.fixture(autouse=True)
def _limpa_cache():
    cvm_balanco._bpa_itr_ano.clear()
    cvm_balanco._bpp_itr_ano.clear()
    yield
    cvm_balanco._bpa_itr_ano.clear()
    cvm_balanco._bpp_itr_ano.clear()


def _mock_zip(bpa_df, bpp_df):
    def _fake(url, nome_no_zip):
        if "BPA" in nome_no_zip:
            return bpa_df
        if "BPP" in nome_no_zip:
            return bpp_df
        return None
    return _fake


def test_vale_q1_2026_balanco_real(_bpa_fixture, _bpp_fixture):
    """Números conferidos manualmente contra o CSV real da CVM
    (2026-11-01): caixa R$26.540 milhões, dívida CP R$3.954 milhões,
    dívida LP R$94.366 milhões, patrimônio líquido R$195.915 milhões -
    todos ORDEM_EXERC='ÚLTIMO' (saldo real do trimestre, não o
    comparativo 'PENÚLTIMO')."""
    with patch.object(cvm_balanco, "obter_cnpj", return_value="33.592.510/0001-54"), \
         patch.object(cvm_balanco, "_baixar_csv_do_zip", side_effect=_mock_zip(_bpa_fixture, _bpp_fixture)):
        balanco = cvm_balanco.obter_balanco_trimestral("VALE3", 2026, 1)
    assert balanco is not None
    assert balanco["empresa"] == "VALE S.A."
    assert balanco["caixa_equivalentes"] == pytest.approx(26540000.0)
    assert balanco["divida_curto_prazo"] == pytest.approx(3954000.0)
    assert balanco["divida_longo_prazo"] == pytest.approx(94366000.0)
    assert balanco["divida_total"] == pytest.approx(98320000.0)
    assert balanco["patrimonio_liquido"] == pytest.approx(195915000.0)


def test_vale_q2_2026_balanco_real_diferente_do_q1(_bpa_fixture, _bpp_fixture):
    """Mesmo CNPJ, trimestre diferente - valores REAIS diferentes do Q1
    (bug real encontrado na validação, 2026-11-01: sem filtrar por
    ORDEM_EXERC='ÚLTIMO', .iloc[0] pegava a linha 'PENÚLTIMO', que é o
    MESMO saldo comparativo de 31/12/2025 em Q1 e Q2 - este teste
    garante que os dois trimestres NÃO saem iguais)."""
    with patch.object(cvm_balanco, "obter_cnpj", return_value="33.592.510/0001-54"), \
         patch.object(cvm_balanco, "_baixar_csv_do_zip", side_effect=_mock_zip(_bpa_fixture, _bpp_fixture)):
        balanco_q2 = cvm_balanco.obter_balanco_trimestral("VALE3", 2026, 2)
    assert balanco_q2["caixa_equivalentes"] == pytest.approx(28871000.0)
    assert balanco_q2["divida_curto_prazo"] == pytest.approx(6534000.0)
    assert balanco_q2["divida_longo_prazo"] == pytest.approx(91500000.0)
    assert balanco_q2["patrimonio_liquido"] == pytest.approx(201467000.0)
    # garante que não é o mesmo valor do Q1 (regressão do bug ORDEM_EXERC)
    assert balanco_q2["caixa_equivalentes"] != pytest.approx(26540000.0)
    assert balanco_q2["patrimonio_liquido"] != pytest.approx(195915000.0)


def test_ticker_sem_cnpj_mapeado_devolve_none():
    with patch.object(cvm_balanco, "obter_cnpj", return_value=None):
        assert cvm_balanco.obter_balanco_trimestral("XXXX3", 2026, 1) is None


def test_fonte_cvm_indisponivel_devolve_none():
    with patch.object(cvm_balanco, "obter_cnpj", return_value="33.592.510/0001-54"), \
         patch.object(cvm_balanco, "_baixar_csv_do_zip", return_value=None):
        assert cvm_balanco.obter_balanco_trimestral("VALE3", 2026, 1) is None


def test_trimestre_4_nao_suportado_devolve_none():
    with patch.object(cvm_balanco, "obter_cnpj", return_value="33.592.510/0001-54"):
        assert cvm_balanco.obter_balanco_trimestral("VALE3", 2026, 4) is None


def test_conta_ausente_fica_none_nunca_zero():
    """Sintético: se a empresa não reportar '2.01.04' (dívida CP), o
    campo fica None - nunca 0.0 (que seria indistinguível de 'sem
    dívida de curto prazo', um fato diferente de 'dado ausente')."""
    bpa = pd.DataFrame([{
        "CNPJ_CIA": "11.111.111/0001-11", "DT_REFER": "2026-03-31", "DENOM_CIA": "EMPRESA TESTE",
        "ORDEM_EXERC": "ÚLTIMO", "CD_CONTA": "1.01.01", "VL_CONTA": 500.0,
        "MOEDA": "REAL", "ESCALA_MOEDA": "MIL",
    }])
    bpp = pd.DataFrame([{
        "CNPJ_CIA": "11.111.111/0001-11", "DT_REFER": "2026-03-31", "DENOM_CIA": "EMPRESA TESTE",
        "ORDEM_EXERC": "ÚLTIMO", "CD_CONTA": "2.03", "VL_CONTA": 1000.0,
        "MOEDA": "REAL", "ESCALA_MOEDA": "MIL",
    }])
    with patch.object(cvm_balanco, "obter_cnpj", return_value="11.111.111/0001-11"), \
         patch.object(cvm_balanco, "_baixar_csv_do_zip", side_effect=_mock_zip(bpa, bpp)):
        balanco = cvm_balanco.obter_balanco_trimestral("TEST3", 2026, 1)
    assert balanco["divida_curto_prazo"] is None
    assert balanco["divida_longo_prazo"] is None
    assert balanco["divida_total"] is None
    assert balanco["patrimonio_liquido"] == pytest.approx(1000.0)


def test_registra_tentativa_de_sucesso_e_falha(_bpa_fixture):
    with patch("data.earnings.cvm_balanco.registrar_tentativa") as mock_reg:
        with patch.object(cvm_balanco, "_baixar_csv_do_zip", return_value=_bpa_fixture):
            cvm_balanco._bpa_itr_ano(2026)
        assert mock_reg.call_args.kwargs.get("execucao_ok") is True

    cvm_balanco._bpa_itr_ano.clear()
    with patch("data.earnings.cvm_balanco.registrar_tentativa") as mock_reg:
        with patch.object(cvm_balanco, "_baixar_csv_do_zip", return_value=None):
            cvm_balanco._bpa_itr_ano(2026)
        assert mock_reg.call_args.kwargs.get("execucao_ok") is False
