# -*- coding: utf-8 -*-
"""Testes do bloco balanco_fluxo_caixa de data/earnings/reviewer.py
(ROIC, dívida líquida histórica, EBITDA/FCO/FCF/CAPEX/dividendos
acumulados no ano) - complementa test_earnings_reviewer.py (que cobre
só DRE/YoY/QoQ/educação financeira/comparação de versões).

Ponta a ponta com dados REAIS (mesmas fixtures de test_earnings_cvm_dre.py/
test_earnings_cvm_balanco.py/test_earnings_cvm_dfc.py, VALE S.A. - CNPJ
33.592.510/0001-54), e testes unitários sincéticos de serie_historica_br
(mesmo padrão de test_earnings_reviewer.py: patch.object em
trimestres_candidatos_br/montar_nota_br, decoupled de date.today())."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from data.earnings import cvm_balanco, cvm_dfc, cvm_dre, reviewer

_DIR = Path(__file__).parent / "fixtures" / "earnings"
_VALE_DRE = pd.read_csv(_DIR / "cvm_itr_dre_con_vale3_2026.csv", sep=";", encoding="latin1")
_VALE_BPA = pd.read_csv(_DIR / "cvm_itr_bpa_con_vale3_2026.csv", sep=";", encoding="latin1")
_VALE_BPP = pd.read_csv(_DIR / "cvm_itr_bpp_con_vale3_2026.csv", sep=";", encoding="latin1")
_VALE_DFC_MI = pd.read_csv(_DIR / "cvm_itr_dfc_mi_con_vale3_2026.csv", sep=";", encoding="latin1")
_CNPJ_VALE = "33.592.510/0001-54"


def _fake_balanco_zip(url, nome_no_zip):
    if "BPA" in nome_no_zip:
        return _VALE_BPA
    if "BPP" in nome_no_zip:
        return _VALE_BPP
    return None


def _fake_dfc_zip(url, nome_no_zip):
    if "DFC_MI" in nome_no_zip:
        return _VALE_DFC_MI
    return None


@pytest.fixture(autouse=True)
def _limpa_caches():
    cvm_dre._dre_itr_ano.clear()
    cvm_balanco._bpa_itr_ano.clear()
    cvm_balanco._bpp_itr_ano.clear()
    cvm_dfc._dfc_itr_ano.clear()
    yield
    cvm_dre._dre_itr_ano.clear()
    cvm_balanco._bpa_itr_ano.clear()
    cvm_balanco._bpp_itr_ano.clear()
    cvm_dfc._dfc_itr_ano.clear()


def _montar_nota_vale(ano, trimestre):
    with patch.object(cvm_dre, "obter_cnpj", return_value=_CNPJ_VALE), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=_VALE_DRE), \
         patch.object(cvm_balanco, "obter_cnpj", return_value=_CNPJ_VALE), \
         patch.object(cvm_balanco, "_baixar_csv_do_zip", side_effect=_fake_balanco_zip), \
         patch.object(cvm_dfc, "obter_cnpj", return_value=_CNPJ_VALE), \
         patch.object(cvm_dfc, "_baixar_csv_do_zip", side_effect=_fake_dfc_zip):
        return reviewer.montar_nota_br("VALE3", ano, trimestre)


# ---------------------------------------------------------------------
# PONTA A PONTA (VALE3 real) - números conferidos manualmente contra os
# CSVs reais da CVM (2026-11-01), mesma metodologia de test_earnings_
# reviewer.py e test_earnings_cvm_dre.py/cvm_balanco.py/cvm_dfc.py.
# ---------------------------------------------------------------------

def test_vale_q2_2026_roic_e_aliquota_efetiva_reais():
    """EBIT isolado do 2T26 (R$11.342 milhões) * (1 - alíquota efetiva
    real do trimestre, calculada a partir do imposto reportado R$1.853
    milhões / resultado antes tributos R$8.894 milhões = 20,83%) /
    capital investido (PL R$201.467mi + dívida R$98.034mi - caixa
    R$28.871mi = R$270.630mi) ≈ 3,32% - NUNCA uma alíquota-padrão fixa."""
    nota = _montar_nota_vale(2026, 2)
    bfc = nota["balanco_fluxo_caixa"]
    assert bfc["aliquota_efetiva_pct"] == pytest.approx(20.834270294580616, rel=1e-6)
    assert bfc["roic_pct"] == pytest.approx(3.3178055142403524, rel=1e-6)


def test_vale_q1_2026_divida_liquida_fco_capex_dividendos_reais():
    """Dívida líquida (fim do 1T26): (CP R$3.954mi + LP R$94.366mi) -
    caixa R$26.540mi = R$71.780mi. FCO/CAPEX/dividendos sempre YTD
    (ver cvm_dfc.py) - FCO R$9.777mi, CAPEX (soma de linhas 'imobilizado'
    negativas) R$6.244mi, FCF = FCO-CAPEX = R$3.533mi, dividendos pagos
    R$14.465mi, EBITDA YTD = EBIT YTD (R$12.668mi, 1T=isolado=YTD) +
    depreciação YTD (R$4.435mi) = R$17.103mi - TODOS em reais ABSOLUTOS
    (×1.000, escala_moeda='MIL' da VALE - bug real encontrado e corrigido
    na auditoria 2026-11-01: sem a escala, esses valores ficavam 1000x
    menores que o real, inclusive no cálculo do DCF)."""
    nota = _montar_nota_vale(2026, 1)
    bfc = nota["balanco_fluxo_caixa"]
    assert bfc["divida_liquida_atual"] == pytest.approx(71780000.0 * 1000)
    assert bfc["fco_ytd"] == pytest.approx(9777000.0 * 1000)
    assert bfc["capex_ytd"] == pytest.approx(6244000.0 * 1000)
    assert bfc["fcf_ytd"] == pytest.approx(3533000.0 * 1000)
    assert bfc["dividendos_pagos_ytd"] == pytest.approx(14465000.0 * 1000)
    assert bfc["ebitda_ytd"] == pytest.approx(17103000.0 * 1000)
    assert bfc["metodo_dfc"] == "MI"


def test_vale_q2_2026_ebitda_ytd_soma_2_trimestres_de_ebit():
    """EBITDA YTD do 2T26 soma EBIT ISOLADO do 1T26 (R$12.668mi) + 2T26
    (R$11.342mi) = R$24.010mi - que por coincidência bate EXATAMENTE
    com o '3.05 ÚLTIMO' acumulado Jan-Jun que a própria CVM reporta
    (confirmação independente de que _ebit_acumulado_no_ano_absoluto
    soma corretamente) - + depreciação YTD do 2T26 (R$9.038mi) =
    R$33.048mi, em reais absolutos (×1.000)."""
    nota = _montar_nota_vale(2026, 2)
    assert nota["balanco_fluxo_caixa"]["ebitda_ytd"] == pytest.approx(33048000.0 * 1000)


def test_vale_q2_2026_sem_dado_do_ano_anterior_fica_none_no_balanco():
    """Fixture só tem 2026 - balanço/comparação YoY de dívida líquida e
    EBITDA do 'ano anterior' (que exigiria o zip de 2025) ficam None,
    nunca um valor adivinhado/zero."""
    nota = _montar_nota_vale(2026, 2)
    bfc = nota["balanco_fluxo_caixa"]
    assert bfc["divida_liquida_ano_anterior"] is None
    assert bfc["divida_liquida_yoy_variacao_pct"] is None
    assert bfc["ebitda_ytd_ano_anterior"] is None
    # mas FCO/CAPEX/dividendos YoY SIM existem - vêm do PENÚLTIMO
    # dentro do MESMO zip de 2026 (ver cvm_dfc.py), não exigem zip de 2025
    assert bfc["fco_ytd_ano_anterior"] is not None
    assert bfc["fco_ytd_yoy_variacao_pct"] is not None


def test_escala_mil_aplicada_ebit_isolado_nao_fica_1000x_menor():
    """Bug real encontrado em auditoria (2026-11-01): antes da correção,
    _montar_balanco_fluxo_caixa não aplicava escala_moeda ('MIL') aos
    valores absolutos - R$9.777 milhões de FCO virava '9777000.0' (nove
    milhões, não nove bilhões) ao ser formatado como se já fosse real
    absoluto. divida_liquida_atual precisa ser >= R$1 milhão real pra um
    balanço do tamanho da VALE (nunca um valor na casa de R$10 mil, que
    seria o sintoma do bug sem a escala)."""
    nota = _montar_nota_vale(2026, 1)
    bfc = nota["balanco_fluxo_caixa"]
    assert bfc["divida_liquida_atual"] > 1_000_000.0
    assert bfc["fco_ytd"] > 1_000_000.0
    assert bfc["ebitda_ytd"] > 1_000_000.0


def test_banco_bloqueado_nunca_calcula_balanco_fluxo_caixa():
    """ITUB4 (Bancos) é bloqueado pelo guard de plano de contas ANTES
    de chegar em _montar_balanco_fluxo_caixa - nota fica disponivel=False
    e nem tenta consultar Balanço/DFC (não há a chave balanco_fluxo_caixa
    nem ela aparece parcialmente calculada com rótulo errado)."""
    with patch.object(cvm_balanco, "obter_balanco_trimestral") as mock_balanco, \
         patch.object(cvm_dfc, "obter_fluxo_caixa_trimestral") as mock_dfc:
        nota = reviewer.montar_nota_br("ITUB4", 2026, 2)
    assert nota["disponivel"] is False
    assert "balanco_fluxo_caixa" not in nota
    mock_balanco.assert_not_called()
    mock_dfc.assert_not_called()


def test_balanco_indisponivel_gera_limitacao_de_roic_e_divida():
    """Quando o balanço não pode ser obtido (fonte fora do ar), ROIC e
    dívida líquida ficam None com uma LIMITAÇÃO explícita cada - nunca
    um valor calculado parcialmente."""
    with patch.object(cvm_dre, "obter_cnpj", return_value=_CNPJ_VALE), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=_VALE_DRE), \
         patch.object(cvm_balanco, "obter_balanco_trimestral", return_value=None), \
         patch.object(cvm_dfc, "obter_fluxo_caixa_trimestral", return_value=None):
        nota = reviewer.montar_nota_br("VALE3", 2026, 2)
    bfc = nota["balanco_fluxo_caixa"]
    assert bfc["roic_pct"] is None
    assert bfc["divida_liquida_atual"] is None
    assert any("ROIC" in lim for lim in nota["limitacoes"])
    assert any("Dívida líquida" in lim for lim in nota["limitacoes"])


def test_aliquota_nao_disponivel_bloqueia_roic_sem_assumir_padrao():
    """Resultado antes dos tributos negativo (prejuízo) - alíquota
    efetiva não tem significado econômico, ROIC fica None com limitação
    explícita, NUNCA cai pra uma alíquota-padrão tipo 34%."""
    dre_sintetico = pd.DataFrame([
        {"CNPJ_CIA": _CNPJ_VALE, "DT_REFER": "2026-06-30", "DENOM_CIA": "VALE S.A.",
         "ORDEM_EXERC": "ÚLTIMO", "DT_INI_EXERC": "2026-04-01", "DT_FIM_EXERC": "2026-06-30",
         "CD_CONTA": cod, "VL_CONTA": valor, "MOEDA": "REAL", "ESCALA_MOEDA": "MIL"}
        for cod, valor in [
            ("3.01", 1000.0), ("3.02", -500.0), ("3.03", 500.0), ("3.05", -100.0),
            ("3.07", -200.0), ("3.08", 50.0), ("3.11", -150.0), ("3.11.01", -150.0),
        ]
    ])
    with patch.object(cvm_dre, "obter_cnpj", return_value=_CNPJ_VALE), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=dre_sintetico), \
         patch.object(cvm_balanco, "obter_balanco_trimestral",
                       return_value={"patrimonio_liquido": 1000.0, "divida_total": 500.0, "caixa_equivalentes": 100.0}), \
         patch.object(cvm_dfc, "obter_fluxo_caixa_trimestral", return_value=None):
        nota = reviewer.montar_nota_br("VALE3", 2026, 2)
    bfc = nota["balanco_fluxo_caixa"]
    assert bfc["aliquota_efetiva_pct"] is None
    assert bfc["roic_pct"] is None
    assert any("alíquota" in lim.lower() for lim in nota["limitacoes"])


def test_capital_investido_negativo_bloqueia_roic():
    """Patrimônio líquido muito negativo deixa capital investido <= 0 -
    ROIC sem significado econômico nesse caso, None (nunca um percentual
    com denominador negativo, que inverteria o sinal de forma confusa)."""
    dre_sintetico = pd.DataFrame([
        {"CNPJ_CIA": _CNPJ_VALE, "DT_REFER": "2026-06-30", "DENOM_CIA": "VALE S.A.",
         "ORDEM_EXERC": "ÚLTIMO", "DT_INI_EXERC": "2026-04-01", "DT_FIM_EXERC": "2026-06-30",
         "CD_CONTA": cod, "VL_CONTA": valor, "MOEDA": "REAL", "ESCALA_MOEDA": "MIL"}
        for cod, valor in [
            ("3.01", 1000.0), ("3.02", -500.0), ("3.03", 500.0), ("3.05", 100.0),
            ("3.07", 100.0), ("3.08", -30.0), ("3.11", 70.0), ("3.11.01", 70.0),
        ]
    ])
    with patch.object(cvm_dre, "obter_cnpj", return_value=_CNPJ_VALE), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=dre_sintetico), \
         patch.object(cvm_balanco, "obter_balanco_trimestral",
                       return_value={"patrimonio_liquido": -5000.0, "divida_total": 100.0, "caixa_equivalentes": 50.0}), \
         patch.object(cvm_dfc, "obter_fluxo_caixa_trimestral", return_value=None):
        nota = reviewer.montar_nota_br("VALE3", 2026, 2)
    assert nota["balanco_fluxo_caixa"]["roic_pct"] is None


# ---------------------------------------------------------------------
# UNITÁRIO de serie_historica_br (mesmo padrão de test_earnings_
# reviewer.py: sintético, decoupled de date.today()) - cobre os campos
# NOVOS da série (roic_pct/divida_liquida/ebitda_ytd/fco_ytd/fcf_ytd/
# capex_ytd/dividendos_pagos_ytd), incluindo a tendência INVERTIDA de
# dívida líquida (subir = DETERIORACAO, não RECUPERACAO).
# ---------------------------------------------------------------------

def _nota_com_bfc(periodo_label, roic_pct, divida_liquida, divida_liquida_yoy, ebitda_yoy, capex_yoy, dividendos_yoy):
    return {
        "disponivel": True, "periodo_label": periodo_label,
        "metricas": {
            "receita_liquida": {"yoy_variacao_pct": 0.0},
            "ebit": {"yoy_variacao_pct": 0.0},
            "lucro_liquido_consolidado": {"yoy_variacao_pct": 0.0},
        },
        "margem_bruta_pct": 30.0,
        "balanco_fluxo_caixa": {
            "roic_pct": roic_pct, "divida_liquida_atual": divida_liquida,
            "divida_liquida_yoy_variacao_pct": divida_liquida_yoy,
            "ebitda_ytd_yoy_variacao_pct": ebitda_yoy,
            "fco_ytd_yoy_variacao_pct": 0.0, "fcf_ytd_yoy_variacao_pct": 0.0,
            "capex_ytd_yoy_variacao_pct": capex_yoy,
            "dividendos_pagos_ytd_yoy_variacao_pct": dividendos_yoy,
        },
    }


def test_serie_historica_br_roic_tendencia_recuperacao():
    notas = {
        (2026, 1): _nota_com_bfc("1T2026", 5.0, 1000.0, None, None, None, None),
        (2026, 2): _nota_com_bfc("2T2026", 10.0, 1000.0, None, None, None, None),
    }
    with patch.object(reviewer, "trimestres_candidatos_br", return_value=[(2026, 2), (2026, 1)]), \
         patch.object(reviewer, "montar_nota_br", side_effect=lambda t, a, tri: notas[(a, tri)]):
        serie = reviewer.serie_historica_br("WEGE3", n_trimestres=2)
    assert serie["roic_pct"]["serie"] == [5.0, 10.0]
    assert serie["roic_pct"]["tendencia"] == "RECUPERACAO"


def test_serie_historica_br_divida_liquida_subindo_e_deterioracao_nunca_recuperacao():
    """Achado real documentado no código (2026-11-01): _tendencia() por
    padrão trata 'valor sobe' como melhora (RECUPERACAO) - pra dívida
    líquida é o INVERSO. Dívida crescendo 10% a.a. ano após ano deve
    virar DETERIORACAO, nunca RECUPERACAO."""
    notas = {
        (2026, 1): _nota_com_bfc("1T2026", None, 1000.0, 2.0, None, None, None),
        (2026, 2): _nota_com_bfc("2T2026", None, 1100.0, 10.0, None, None, None),
    }
    with patch.object(reviewer, "trimestres_candidatos_br", return_value=[(2026, 2), (2026, 1)]), \
         patch.object(reviewer, "montar_nota_br", side_effect=lambda t, a, tri: notas[(a, tri)]):
        serie = reviewer.serie_historica_br("WEGE3", n_trimestres=2)
    assert serie["divida_liquida"]["tendencia"] == "DETERIORACAO"


def test_serie_historica_br_divida_liquida_caindo_e_recuperacao():
    notas = {
        (2026, 1): _nota_com_bfc("1T2026", None, 1000.0, 10.0, None, None, None),
        (2026, 2): _nota_com_bfc("2T2026", None, 900.0, 2.0, None, None, None),
    }
    with patch.object(reviewer, "trimestres_candidatos_br", return_value=[(2026, 2), (2026, 1)]), \
         patch.object(reviewer, "montar_nota_br", side_effect=lambda t, a, tri: notas[(a, tri)]):
        serie = reviewer.serie_historica_br("WEGE3", n_trimestres=2)
    assert serie["divida_liquida"]["tendencia"] == "RECUPERACAO"


def test_serie_historica_br_capex_e_dividendos_sao_so_direcao_nao_julgamento():
    """CAPEX/dividendos não têm 'bom' ou 'ruim' universal - a série só
    reporta a DIREÇÃO real (RECUPERACAO=subiu, DETERIORACAO=caiu),
    mesma convenção de receita/EBIT/lucro (nunca um rótulo de valor)."""
    notas = {
        (2026, 1): _nota_com_bfc("1T2026", None, None, None, None, -5.0, -5.0),
        (2026, 2): _nota_com_bfc("2T2026", None, None, None, None, 15.0, 15.0),
    }
    with patch.object(reviewer, "trimestres_candidatos_br", return_value=[(2026, 2), (2026, 1)]), \
         patch.object(reviewer, "montar_nota_br", side_effect=lambda t, a, tri: notas[(a, tri)]):
        serie = reviewer.serie_historica_br("WEGE3", n_trimestres=2)
    assert serie["capex_ytd"]["tendencia"] == "RECUPERACAO"
    assert serie["dividendos_pagos_ytd"]["tendencia"] == "RECUPERACAO"


def test_serie_historica_br_sem_bfc_fica_none_sem_quebrar():
    """Nota sem a chave 'balanco_fluxo_caixa' (ex: formato antigo, ou
    bloco indisponível por completo) não quebra serie_historica_br -
    campos novos ficam com série vazia e tendência None."""
    notas = {
        (2026, 1): {
            "disponivel": True, "periodo_label": "1T2026",
            "metricas": {"receita_liquida": {"yoy_variacao_pct": 1.0},
                         "ebit": {"yoy_variacao_pct": 1.0},
                         "lucro_liquido_consolidado": {"yoy_variacao_pct": 1.0}},
            "margem_bruta_pct": 30.0,
        },
    }
    with patch.object(reviewer, "trimestres_candidatos_br", return_value=[(2026, 1)]), \
         patch.object(reviewer, "montar_nota_br", side_effect=lambda t, a, tri: notas[(a, tri)]):
        serie = reviewer.serie_historica_br("WEGE3", n_trimestres=1)
    assert serie["disponivel"] is True
    assert serie["roic_pct"]["serie"] == []
    assert serie["roic_pct"]["tendencia"] is None
