# -*- coding: utf-8 -*-
"""Testes de data/earnings/reviewer.py - usa os mesmos dados REAIS de
test_earnings_cvm_dre.py (Vale) e test_earnings_sec_xbrl.py (Apple) pra
montar a nota estruturada ponta a ponta, e testa o versionamento de tese
(comparar_com_versao_anterior) e a persistencia append-only (salvar_versao)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.earnings import cvm_dre, reviewer, sec_xbrl

_DIR = Path(__file__).parent / "fixtures" / "earnings"
_VALE_CSV = pd.read_csv(_DIR / "cvm_itr_dre_con_vale3_2026.csv", sep=";", encoding="latin1")


def _fake_serie_conceito_aapl(cik, tag):
    caminho = _DIR / f"sec_aapl_{tag}.json"
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)["units"]["USD"]


@pytest.fixture(autouse=True)
def _limpa_cache():
    cvm_dre._dre_itr_ano.clear()
    yield
    cvm_dre._dre_itr_ano.clear()


# ---------------------------------------------------------------------
# PILOTO BR (Vale) - ponta a ponta com QoQ (1T real) e YoY (PENÚLTIMO real)
# ---------------------------------------------------------------------

def test_nota_br_vale_q2_2026_tem_yoy_e_qoq_reais():
    with patch.object(cvm_dre, "obter_cnpj", return_value="33.592.510/0001-54"), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=_VALE_CSV):
        nota = reviewer.montar_nota_br("VALE3", 2026, 2)

    assert nota["disponivel"] is True
    assert nota["periodo_label"] == "2T2026"
    receita = nota["metricas"]["receita_liquida"]
    assert receita["atual"] == pytest.approx(53012000.0)
    assert receita["yoy_anterior"] == pytest.approx(49807000.0)
    assert receita["yoy_variacao_pct"] == pytest.approx((53012000.0 / 49807000.0 - 1) * 100, rel=1e-3)
    assert receita["qoq_anterior"] == pytest.approx(48680000.0)  # 1T2026 real
    assert receita["qoq_variacao_pct"] == pytest.approx((53012000.0 / 48680000.0 - 1) * 100, rel=1e-3)
    # margem bruta real do 2T26 (30,52%) x 2T25 (30,89%) varia so' 0,37 p.p.
    # - abaixo do limiar de 1 p.p., por isso NENHUMA interpretacao e'
    # gerada aqui (ver limiar em reviewer.py) - toda [INTERPRETACAO] e'
    # marcada explicitamente quando existe (ver teste do piloto Apple)
    assert all(i.startswith("[INTERPRETAÇÃO]") for i in nota["interpretacoes"])
    assert nota["margem_bruta_pct"] == pytest.approx(16179000.0 / 53012000.0 * 100, rel=1e-3)
    assert nota["limitacoes"]  # nunca vazio - ver LIMITACOES_PADRAO


def test_nota_br_q1_sem_qoq_documenta_o_motivo():
    with patch.object(cvm_dre, "obter_cnpj", return_value="33.592.510/0001-54"), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=_VALE_CSV):
        nota = reviewer.montar_nota_br("VALE3", 2026, 1)
    assert nota["metricas"]["receita_liquida"]["qoq_anterior"] is None
    assert any("QoQ" in lim or "trimestre-a-trimestre" in lim for lim in nota["limitacoes"])


def test_nota_br_ticker_sem_dado_fica_indisponivel_com_motivo():
    with patch.object(cvm_dre, "obter_cnpj", return_value=None):
        nota = reviewer.montar_nota_br("ZZZZ3", 2026, 2)
    assert nota["disponivel"] is False
    assert nota["motivo"]


# ---------------------------------------------------------------------
# PILOTO INTERNACIONAL (Apple) - ponta a ponta, so' YoY (QoQ fora de
# escopo desta chamada - ver docstring de montar_nota_internacional)
# ---------------------------------------------------------------------

def test_nota_internacional_aapl_q3_fiscal_2026_real():
    with patch.object(sec_xbrl, "obter_cik", return_value=320193), \
         patch.object(sec_xbrl, "_serie_conceito", side_effect=_fake_serie_conceito_aapl):
        nota = reviewer.montar_nota_internacional(
            "AAPL", "2026-03-29", "2026-06-27", "2025-03-30", "2025-06-28")
    assert nota["disponivel"] is True
    assert nota["metricas"]["receita_liquida"]["atual"] == pytest.approx(109417000000.0)
    assert nota["metricas"]["receita_liquida"]["yoy_variacao_pct"] == pytest.approx(16.38, abs=0.1)
    # margem bruta melhorou (50.06% vs 46.49%) - deve gerar interpretacao marcada
    assert any("melhora" in i for i in nota["interpretacoes"])
    assert nota["fontes"] and all(f["url"].startswith("https://") for f in nota["fontes"])


def test_nota_internacional_sem_cik_fica_indisponivel():
    with patch.object(sec_xbrl, "obter_cik", return_value=None):
        nota = reviewer.montar_nota_internacional("ZZZZ", "2026-01-01", "2026-03-31", "2025-01-01", "2025-03-31")
    assert nota["disponivel"] is False


# ---------------------------------------------------------------------
# VERSIONAMENTO DE TESE - nunca reescreve, so' sinaliza mudanca de direcao
# ---------------------------------------------------------------------

def _nota(variacao_pct):
    return {"disponivel": True, "periodo_label": "1T2026",
            "metricas": {"receita_liquida": {"yoy_variacao_pct": variacao_pct}}}


def test_comparar_sem_nota_anterior_devolve_vazio():
    assert reviewer.comparar_com_versao_anterior(_nota(5.0), None) == []


def test_comparar_mesma_direcao_nao_sinaliza_mudanca():
    assert reviewer.comparar_com_versao_anterior(_nota(5.0), _nota(3.0)) == []


def test_comparar_alta_para_queda_sinaliza_mudanca():
    mudancas = reviewer.comparar_com_versao_anterior(_nota(-5.0), _nota(5.0))
    assert len(mudancas) == 1
    assert mudancas[0]["metrica"] == "receita_liquida"
    assert mudancas[0]["direcao_anterior"] == "ALTA"
    assert mudancas[0]["direcao_atual"] == "QUEDA"


def test_comparar_nota_atual_indisponivel_nunca_compara():
    nota_indisponivel = {"disponivel": False}
    assert reviewer.comparar_com_versao_anterior(nota_indisponivel, _nota(5.0)) == []


# ---------------------------------------------------------------------
# PERSISTENCIA - append-only, nunca grava nota indisponivel
# ---------------------------------------------------------------------

def test_salvar_versao_nunca_persiste_nota_indisponivel():
    with patch.object(reviewer, "obter_cliente") as mock_cliente:
        assert reviewer.salvar_versao({"disponivel": False}) is False
        mock_cliente.assert_not_called()


def test_salvar_versao_insere_sem_update(_df_fixture=None):
    cliente_fake = MagicMock()
    with patch.object(reviewer, "obter_cliente", return_value=cliente_fake):
        ok = reviewer.salvar_versao({
            "disponivel": True, "ticker": "VALE3", "pais": "BR",
            "periodo_label": "2T2026", "gerado_em": "2026-10-22T00:00:00+00:00",
        })
    assert ok is True
    cliente_fake.table.assert_called_once_with("earnings_reviews")
    cliente_fake.table.return_value.insert.assert_called_once()
    cliente_fake.table.return_value.update.assert_not_called()


def test_salvar_versao_supabase_indisponivel_devolve_false():
    with patch.object(reviewer, "obter_cliente", return_value=None):
        assert reviewer.salvar_versao({"disponivel": True, "ticker": "X", "pais": "BR",
                                        "periodo_label": "1T2026", "gerado_em": "x"}) is False
