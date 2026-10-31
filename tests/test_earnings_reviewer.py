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


def _cliente_fake_sem_versao_anterior():
    """MagicMock cuja consulta de deduplicacao (_ultima_versao_mesmo_periodo)
    devolve resp.data == [] (nenhuma versao anterior) - caminho feliz
    de insert pra quem nao quer testar a deduplicacao em si."""
    cliente_fake = MagicMock()
    cliente_fake.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value \
        .order.return_value.limit.return_value.execute.return_value.data = []
    return cliente_fake


def test_salvar_versao_insere_sem_update():
    cliente_fake = _cliente_fake_sem_versao_anterior()
    with patch.object(reviewer, "obter_cliente", return_value=cliente_fake):
        ok = reviewer.salvar_versao({
            "disponivel": True, "ticker": "VALE3", "pais": "BR",
            "periodo_label": "2T2026", "gerado_em": "2026-10-22T00:00:00+00:00",
            "metricas": {"receita_liquida": {"atual": 1.0}},
        })
    assert ok is True
    cliente_fake.table.return_value.insert.assert_called_once()
    cliente_fake.table.return_value.update.assert_not_called()


def test_salvar_versao_reprocessar_mesmo_periodo_com_numeros_iguais_nao_duplica():
    """Bug real corrigido em revisao tecnica (2026-10-22): reprocessar o
    MESMO ticker/periodo 2x com os MESMOS numeros nao pode inserir 2
    linhas - so' e' uma versao NOVA de verdade quando os numeros mudam
    (re-apresentacao real)."""
    cliente_fake = MagicMock()
    metricas = {"receita_liquida": {"atual": 53012000.0, "yoy_anterior": 49807000.0}}
    cliente_fake.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value \
        .order.return_value.limit.return_value.execute.return_value.data = [
            {"conteudo": {"metricas": metricas, "gerado_em": "2026-10-21T00:00:00+00:00"}}
        ]
    with patch.object(reviewer, "obter_cliente", return_value=cliente_fake):
        ok = reviewer.salvar_versao({
            "disponivel": True, "ticker": "VALE3", "pais": "BR",
            "periodo_label": "2T2026", "gerado_em": "2026-10-22T00:00:00+00:00",
            "metricas": metricas,
        })
    assert ok is True
    cliente_fake.table.return_value.insert.assert_not_called()


def test_salvar_versao_reprocessar_com_numeros_diferentes_insere_nova_versao():
    """Re-apresentacao real (numeros mudaram) - TEM que inserir, nunca
    bloquear so' porque e' o mesmo ticker/periodo."""
    cliente_fake = MagicMock()
    cliente_fake.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value \
        .order.return_value.limit.return_value.execute.return_value.data = [
            {"conteudo": {"metricas": {"receita_liquida": {"atual": 48000000.0}}}}
        ]
    with patch.object(reviewer, "obter_cliente", return_value=cliente_fake):
        ok = reviewer.salvar_versao({
            "disponivel": True, "ticker": "VALE3", "pais": "BR",
            "periodo_label": "2T2026", "gerado_em": "2026-10-22T00:00:00+00:00",
            "metricas": {"receita_liquida": {"atual": 53012000.0}},  # numero diferente (re-apresentacao)
        })
    assert ok is True
    cliente_fake.table.return_value.insert.assert_called_once()


def test_salvar_versao_consulta_de_dedup_falhando_nao_bloqueia_o_insert():
    """Se a CONSULTA de deduplicacao falhar (rede/banco), nunca deve
    impedir o insert por isso - trata como 'sem versao anterior'."""
    cliente_fake = MagicMock()
    cliente_fake.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value \
        .order.return_value.limit.return_value.execute.side_effect = RuntimeError("banco fora do ar")
    with patch.object(reviewer, "obter_cliente", return_value=cliente_fake):
        ok = reviewer.salvar_versao({
            "disponivel": True, "ticker": "VALE3", "pais": "BR",
            "periodo_label": "2T2026", "gerado_em": "2026-10-22T00:00:00+00:00",
            "metricas": {"receita_liquida": {"atual": 1.0}},
        })
    assert ok is True
    cliente_fake.table.return_value.insert.assert_called_once()
    cliente_fake.table.return_value.update.assert_not_called()


def test_salvar_versao_supabase_indisponivel_devolve_false():
    with patch.object(reviewer, "obter_cliente", return_value=None):
        assert reviewer.salvar_versao({"disponivel": True, "ticker": "X", "pais": "BR",
                                        "periodo_label": "1T2026", "gerado_em": "x"}) is False


# ---------------------------------------------------------------------
# BUG REAL (revisao tecnica independente, 2026-10-22): variacao percentual
# com base NEGATIVA (prejuizo) invertia a direcao - atual/anterior-1 com
# anterior<0 faz o sinal do resultado nao bater com o sinal de
# (atual - anterior). Corrigido em _variacao_pct (denominador abs(anterior)).
# ---------------------------------------------------------------------

def test_variacao_pct_prejuizo_encolhendo_e_melhora_nunca_queda():
    """Prejuizo de -100 pra -50 (reduziu a METADE, resultado MELHOROU) -
    tem que sair POSITIVO (ALTA), nunca negativo/QUEDA."""
    pct = reviewer._variacao_pct(-50.0, -100.0)
    assert pct == pytest.approx(50.0)
    assert reviewer._direcao(pct) == "ALTA"


def test_variacao_pct_prejuizo_piorando_e_queda_nunca_alta():
    """Prejuizo de -50 pra -100 (DOBROU, resultado PIOROU) - tem que sair
    NEGATIVO (QUEDA), nunca positivo/ALTA."""
    pct = reviewer._variacao_pct(-100.0, -50.0)
    assert pct == pytest.approx(-100.0)
    assert reviewer._direcao(pct) == "QUEDA"


def test_variacao_pct_lucro_para_prejuizo_e_sempre_queda():
    pct = reviewer._variacao_pct(-50.0, 100.0)
    assert pct == pytest.approx(-150.0)
    assert reviewer._direcao(pct) == "QUEDA"


def test_variacao_pct_prejuizo_para_lucro_e_sempre_alta():
    pct = reviewer._variacao_pct(50.0, -100.0)
    assert reviewer._direcao(pct) == "ALTA"


def test_variacao_pct_base_positiva_fica_numericamente_identica_de_antes():
    """Garante que a correcao NAO mudou o resultado pro caso comum (base
    positiva) - mesma formula de antes nesse caso (abs(anterior)==anterior)."""
    assert reviewer._variacao_pct(110.0, 100.0) == pytest.approx(10.0)
    assert reviewer._variacao_pct(90.0, 100.0) == pytest.approx(-10.0)


def test_educacao_financeira_vazia_sem_receita_ou_lucro():
    assert reviewer._nota_educativa_receita_vs_lucro({}) == []
    metricas = {"receita_liquida": {"yoy_variacao_pct": 5.0}}
    assert reviewer._nota_educativa_receita_vs_lucro(metricas) == []


def test_educacao_financeira_vazia_quando_diferenca_pequena():
    metricas = {
        "receita_liquida": {"yoy_variacao_pct": 5.0},
        "lucro_liquido_consolidado": {"yoy_variacao_pct": 6.5},
    }
    assert reviewer._nota_educativa_receita_vs_lucro(metricas) == []


def test_educacao_financeira_lucro_crescendo_mais_que_receita():
    metricas = {
        "receita_liquida": {"yoy_variacao_pct": 5.0},
        "lucro_liquido_consolidado": {"yoy_variacao_pct": 20.0},
    }
    notas = reviewer._nota_educativa_receita_vs_lucro(metricas)
    assert len(notas) == 1
    assert notas[0].startswith("[O QUE ISSO SIGNIFICA]")
    assert "lucro líquido cresceu mais rápido" in notas[0]


def test_educacao_financeira_receita_crescendo_mais_que_lucro():
    metricas = {
        "receita_liquida": {"yoy_variacao_pct": 20.0},
        "lucro_liquido_consolidado": {"yoy_variacao_pct": 5.0},
    }
    notas = reviewer._nota_educativa_receita_vs_lucro(metricas)
    assert len(notas) == 1
    assert "receita líquida cresceu mais rápido" in notas[0]


# ---------------------------------------------------------------------
# GUARD DE INSTITUIÇÃO FINANCEIRA/SEGURADORA (2026-10-30) - achado real
# na validação com ITUB4: antes desta checagem, montar_nota_br calculava
# e devolvia disponivel=True com números REAIS mas rótulo semanticamente
# errado (plano de contas COSIF, não industrial/comercial). Zero chamada
# à CVM precisa ser mockada aqui - o guard dispara antes do download.
# ---------------------------------------------------------------------

def test_montar_nota_br_banco_nunca_calcula_dre_com_plano_de_contas_errado():
    nota = reviewer.montar_nota_br("ITUB4", 2026, 2)
    assert nota["disponivel"] is False
    assert "plano de contas" in nota["motivo"]
    assert "COSIF" in nota["motivo"]


def test_montar_nota_br_seguradora_tambem_bloqueada():
    nota = reviewer.montar_nota_br("BBSE3", 2026, 2)
    assert nota["disponivel"] is False
    assert "plano de contas" in nota["motivo"]


def test_montar_nota_br_empresa_industrial_nao_e_bloqueada_pelo_guard():
    # ticker fora de config.IBOVESPA_SETORES (ou com setor não-financeiro)
    # segue o fluxo normal - aqui só confirmamos que o guard não dispara
    # pra WEGE3 (Bens de Capital e Industrial), deixando a consulta real
    # seguir (que então falha por falta de mock de CNPJ, não pelo guard).
    nota = reviewer.montar_nota_br("WEGE3", 2026, 2)
    assert "plano de contas" not in (nota.get("motivo") or "")


# ---------------------------------------------------------------------
# SÉRIE HISTÓRICA + TENDÊNCIA (serie_historica_br / _tendencia)
# ---------------------------------------------------------------------

def test_tendencia_recuperacao_quando_delta_passa_do_limiar():
    assert reviewer._tendencia([-5.0, -1.0, 2.0]) == "RECUPERACAO"


def test_tendencia_deterioracao_quando_delta_negativo_passa_do_limiar():
    assert reviewer._tendencia([8.0, 3.0, 1.0]) == "DETERIORACAO"


def test_tendencia_estabilidade_dentro_da_banda():
    assert reviewer._tendencia([5.0, 6.0, 6.5]) == "ESTABILIDADE"


def test_tendencia_none_com_menos_de_2_pontos():
    assert reviewer._tendencia([]) is None
    assert reviewer._tendencia([5.0]) is None


def _nota_disponivel(periodo_label, receita_yoy, ebit_yoy, lucro_yoy, margem_bruta_pct):
    return {
        "disponivel": True, "periodo_label": periodo_label,
        "metricas": {
            "receita_liquida": {"yoy_variacao_pct": receita_yoy},
            "ebit": {"yoy_variacao_pct": ebit_yoy},
            "lucro_liquido_consolidado": {"yoy_variacao_pct": lucro_yoy},
        },
        "margem_bruta_pct": margem_bruta_pct,
        "fontes": [{"nome": "CVM - dados.cvm.gov.br (ITR, DRE consolidada)"}],
    }


def test_serie_historica_br_calcula_tendencia_a_partir_de_notas_reais_disponiveis():
    notas_por_periodo = {
        (2026, 1): _nota_disponivel("1T2026", -4.0, -3.0, -2.0, 30.0),
        (2026, 2): _nota_disponivel("2T2026", 0.0, 0.0, 0.0, 31.0),
        (2026, 3): _nota_disponivel("3T2026", 5.0, 4.0, 3.0, 33.5),
    }
    with patch.object(reviewer, "trimestres_candidatos_br", return_value=[(2026, 3), (2026, 2), (2026, 1)]), \
         patch.object(reviewer, "montar_nota_br", side_effect=lambda t, a, tri: notas_por_periodo[(a, tri)]):
        serie = reviewer.serie_historica_br("WEGE3", n_trimestres=3)

    assert serie["disponivel"] is True
    assert serie["periodos"] == ["1T2026", "2T2026", "3T2026"]
    assert serie["receita_liquida"]["tendencia"] == "RECUPERACAO"
    assert serie["margem_bruta_pct"]["tendencia"] == "RECUPERACAO"


def test_serie_historica_br_pula_trimestre_sem_dado_sem_interpolar():
    notas_por_periodo = {
        (2026, 1): {"disponivel": False, "motivo": "DRE indisponivel"},
        (2026, 2): _nota_disponivel("2T2026", 1.0, 1.0, 1.0, 30.0),
        (2026, 3): _nota_disponivel("3T2026", 6.0, 5.0, 4.0, 34.0),
    }
    with patch.object(reviewer, "trimestres_candidatos_br", return_value=[(2026, 3), (2026, 2), (2026, 1)]), \
         patch.object(reviewer, "montar_nota_br", side_effect=lambda t, a, tri: notas_por_periodo[(a, tri)]):
        serie = reviewer.serie_historica_br("WEGE3", n_trimestres=3)

    assert serie["disponivel"] is True
    assert serie["periodos"] == ["2T2026", "3T2026"]  # 1T2026 pulado, nunca interpolado
    assert serie["receita_liquida"]["yoy_pct_serie"] == [1.0, 6.0]


def test_serie_historica_br_sem_nenhum_trimestre_disponivel():
    with patch.object(reviewer, "trimestres_candidatos_br", return_value=[(2026, 3), (2026, 2), (2026, 1)]), \
         patch.object(reviewer, "montar_nota_br",
                      return_value={"disponivel": False, "motivo": "DRE indisponivel"}):
        serie = reviewer.serie_historica_br("XPTO3", n_trimestres=3)

    assert serie["disponivel"] is False
    assert "DRE" in serie["motivo"] or "disponível" in serie["motivo"]


def test_serie_historica_br_bloqueada_para_banco_sem_tentar_outros_trimestres():
    chamadas = []

    def _fake_montar(t, a, tri):
        chamadas.append((a, tri))
        return {"disponivel": False, "motivo": "instituição financeira/seguradora (Bancos) usa plano "
                                                "de contas regulatório próprio (COSIF) - x"}

    with patch.object(reviewer, "trimestres_candidatos_br", return_value=[(2026, 3), (2026, 2), (2026, 1)]), \
         patch.object(reviewer, "montar_nota_br", side_effect=_fake_montar):
        serie = reviewer.serie_historica_br("ITUB4", n_trimestres=3)

    assert serie["disponivel"] is False
    assert "COSIF" in serie["motivo"]
    assert len(chamadas) == 1  # não repete a consulta pros outros trimestres - mesmo motivo bloquearia todos
