# -*- coding: utf-8 -*-
"""Testes de data/earnings/sec_xbrl.py com dados REAIS (fixtures
baixadas de data.sec.gov em 2026-10-22, conceitos XBRL da Apple Inc,
CIK 320193, trimestre fiscal Q3 2026 - ver tests/fixtures/earnings/
sec_aapl_*.json). Nenhum teste faz chamada de rede - _serie_conceito e'
sempre mockado pra devolver a fixture certa por tag."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from data.earnings import sec_xbrl

_DIR = Path(__file__).parent / "fixtures" / "earnings"

_INICIO, _FIM = "2026-03-29", "2026-06-27"           # Q3 fiscal 2026 (real)
_INICIO_ANT, _FIM_ANT = "2025-03-30", "2025-06-28"   # mesmo trimestre fiscal, ano anterior


def _carregar(tag: str) -> list:
    with open(_DIR / f"sec_aapl_{tag}.json", encoding="utf-8") as f:
        return json.load(f)["units"]["USD"]


def _fake_serie_conceito(cik, tag):
    caminho = _DIR / f"sec_aapl_{tag}.json"
    if not caminho.exists():
        return None
    return _carregar(tag)


@pytest.fixture(autouse=True)
def _mock_fonte():
    with patch.object(sec_xbrl, "obter_cik", return_value=320193), \
         patch.object(sec_xbrl, "_serie_conceito", side_effect=_fake_serie_conceito):
        yield


def test_aapl_receita_e_lucro_q3_fiscal_2026_reais():
    """Conferido manualmente contra a API real da SEC (2026-10-22):
    receita Q3 fiscal 2026 = US$109.417bi; mesmo trimestre fiscal 2025
    (YoY) = US$94.036bi. Lucro liquido: US$29.789bi vs US$23.434bi."""
    dados = sec_xbrl.obter_metricas_trimestre("AAPL", _INICIO, _FIM, _INICIO_ANT, _FIM_ANT)
    assert dados is not None
    assert dados["metricas"]["receita_liquida"]["atual"] == pytest.approx(109417000000.0)
    assert dados["metricas"]["receita_liquida"]["ano_anterior"] == pytest.approx(94036000000.0)
    assert dados["metricas"]["receita_liquida"]["tag_usada"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert dados["metricas"]["lucro_liquido_consolidado"]["atual"] == pytest.approx(29789000000.0)
    assert dados["metricas"]["lucro_liquido_consolidado"]["ano_anterior"] == pytest.approx(23434000000.0)


def test_aapl_resultado_bruto_e_custo_reais():
    dados = sec_xbrl.obter_metricas_trimestre("AAPL", _INICIO, _FIM, _INICIO_ANT, _FIM_ANT)
    assert dados["metricas"]["resultado_bruto"]["atual"] == pytest.approx(54770000000.0)
    assert dados["metricas"]["custo_vendas"]["atual"] == pytest.approx(54647000000.0)


def test_aapl_ebit_e_resultado_antes_tributos_reais():
    """Gap de cobertura encontrado em revisao tecnica independente
    (2026-10-22): estas 2 metricas (de 6 em TAGS_POR_METRICA) nunca
    tinham fixture/teste - resolviam sempre None nos testes anteriores
    sem ningum notar, mesmo a tag funcionando de verdade na API real.
    Conferido contra data.sec.gov ao vivo em 2026-10-22."""
    dados = sec_xbrl.obter_metricas_trimestre("AAPL", _INICIO, _FIM, _INICIO_ANT, _FIM_ANT)
    assert dados["metricas"]["ebit"]["atual"] == pytest.approx(35695000000.0)
    assert dados["metricas"]["ebit"]["tag_usada"] == "OperatingIncomeLoss"
    assert dados["metricas"]["resultado_antes_tributos"]["atual"] == pytest.approx(36267000000.0)


def test_ticker_sem_cik_devolve_none():
    with patch.object(sec_xbrl, "obter_cik", return_value=None):
        assert sec_xbrl.obter_metricas_trimestre("ZZZZ", _INICIO, _FIM, _INICIO_ANT, _FIM_ANT) is None


def test_periodo_sem_ponto_exato_fica_none_nunca_interpolado():
    dados = sec_xbrl.obter_metricas_trimestre("AAPL", "2026-01-01", "2026-01-31", "2025-01-01", "2025-01-31")
    for metrica, valores in dados["metricas"].items():
        assert valores["atual"] is None, metrica
        assert valores["ano_anterior"] is None, metrica


def test_conceito_sem_tag_disponivel_fica_none():
    with patch.object(sec_xbrl, "_serie_conceito", return_value=None):
        dados = sec_xbrl.obter_metricas_trimestre("AAPL", _INICIO, _FIM, _INICIO_ANT, _FIM_ANT)
    assert all(v["atual"] is None and v["tag_usada"] is None for v in dados["metricas"].values())


def test_mapa_ticker_cik_fonte_indisponivel_devolve_dict_vazio():
    sec_xbrl._mapa_ticker_cik.clear()
    with patch.object(sec_xbrl, "_get_json", return_value=None):
        assert sec_xbrl._mapa_ticker_cik() == {}
    sec_xbrl._mapa_ticker_cik.clear()


# ---------------------------------------------------------------------
# Regressão (auditoria SAÚDE DOS DADOS 2026-10-26): "SEC EDGAR (XBRL)"
# aparecia NUNCA_EXECUTADO sem nenhuma evidência real - só _serie_conceito
# chamava registrar_tentativa, e só é alcançada quando obter_cik(ticker)
# já encontrou um CIK; o próprio mapa ticker->CIK (_mapa_ticker_cik, esta
# função) nunca registrava tentativa nenhuma, sucesso ou falha. Mesmo gap
# já corrigido pro mapa ticker->CNPJ da CVM (ver data/cvm.py:
# _mapa_ticker_cnpj, "CVM (FCA)").
# ---------------------------------------------------------------------

def test_mapa_ticker_cik_fonte_indisponivel_registra_tentativa_de_falha():
    sec_xbrl._mapa_ticker_cik.clear()
    chamadas = []
    with patch.object(sec_xbrl, "_get_json", return_value=None), \
         patch.object(sec_xbrl, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k))):
        sec_xbrl._mapa_ticker_cik()
    sec_xbrl._mapa_ticker_cik.clear()
    assert len(chamadas) == 1
    args, kwargs = chamadas[0]
    assert args[0] == "SEC EDGAR (XBRL)"
    assert kwargs["execucao_ok"] is False
    assert kwargs["erro"]


def test_mapa_ticker_cik_sucesso_registra_tentativa_com_registros_novos():
    sec_xbrl._mapa_ticker_cik.clear()
    chamadas = []
    resposta = {"fields": ["cik", "name", "ticker", "exchange"],
                "data": [[320193, "Apple Inc", "AAPL", "Nasdaq"]]}
    with patch.object(sec_xbrl, "_get_json", return_value=resposta), \
         patch.object(sec_xbrl, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k))):
        mapa = sec_xbrl._mapa_ticker_cik()
    sec_xbrl._mapa_ticker_cik.clear()
    assert mapa == {"AAPL": 320193}
    assert len(chamadas) == 1
    args, kwargs = chamadas[0]
    assert args[0] == "SEC EDGAR (XBRL)"
    assert kwargs["execucao_ok"] is True
    assert kwargs["registros_novos"] == 1


def test_mapa_ticker_cik_formato_inesperado_registra_tentativa_de_falha():
    """Mesma proteção já existente (colunas 'cik'/'ticker' ausentes) -
    antes devolvia {} silenciosamente, sem nenhum rastro no painel."""
    sec_xbrl._mapa_ticker_cik.clear()
    chamadas = []
    resposta = {"fields": ["name", "ticker", "exchange"], "data": []}
    with patch.object(sec_xbrl, "_get_json", return_value=resposta), \
         patch.object(sec_xbrl, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k))):
        assert sec_xbrl._mapa_ticker_cik() == {}
    sec_xbrl._mapa_ticker_cik.clear()
    assert chamadas and chamadas[0][1]["execucao_ok"] is False
