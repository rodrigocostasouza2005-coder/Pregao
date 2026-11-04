# -*- coding: utf-8 -*-
"""Fluxos de alto nível (data/coordenador_central/fluxos.py) - Fluxo A/
B/C. Cada teste mocka executor e persistencia (zero rede/Supabase/IA
real) e confirma: (1) a análise é registrada ANTES e DEPOIS de rodar os
especialistas, (2) o encadeamento real do Fluxo B (comparar_casas só
aciona memoria_research quando o comparador achou cobertura)."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.coordenador_central import fluxos


def _resultado(especialista_id, disponivel=True, dados=None, evidencias=None):
    return {
        "id": especialista_id, "execucao_id": "x", "disponivel": disponivel,
        "resumo": "ok", "evidencias": evidencias or [], "motivo_indisponivel": None,
        "duracao_ms": 10, "erro_tecnico": None, "dados": dados,
    }


@pytest.fixture
def persistencia_mockada():
    with patch.object(fluxos.persistencia, "iniciar_analise", return_value="analise-fake-1") as mock_iniciar, \
         patch.object(fluxos.persistencia, "concluir_analise") as mock_concluir, \
         patch.object(fluxos.persistencia, "registrar_execucao_especialista") as mock_registrar:
        yield {"iniciar": mock_iniciar, "concluir": mock_concluir, "registrar": mock_registrar}


def test_analisar_ticker_registra_inicio_antes_de_rodar_especialistas(persistencia_mockada):
    with patch.object(fluxos.executor, "executar_varios", return_value={
        "analise_ticker": _resultado("analise_ticker"),
        "comparador": _resultado("comparador"),
        "memoria_research": _resultado("memoria_research"),
        "noticias": _resultado("noticias"),
        "catalisadores": _resultado("catalisadores"),
    }) as mock_varios:
        consolidado = fluxos.analisar_ticker("petr4")

    persistencia_mockada["iniciar"].assert_called_once()
    assert persistencia_mockada["iniciar"].call_args[0][2] == "PETR4"
    persistencia_mockada["concluir"].assert_called_once()
    assert persistencia_mockada["concluir"].call_args[0][0] == "analise-fake-1"
    assert persistencia_mockada["concluir"].call_args[0][1] == "CONCLUIDA"
    mock_varios.assert_called_once()
    assert mock_varios.call_args[0][0] == ["analise_ticker", "comparador", "memoria_research", "noticias", "catalisadores", "resultados_corporativos"]
    assert mock_varios.call_args[1]["ticker"] == "PETR4"
    assert "_analise_id" in consolidado and "_duracao_ms" in consolidado


def test_analisar_ticker_marca_parcial_quando_especialista_indisponivel(persistencia_mockada):
    resultados = {
        "analise_ticker": _resultado("analise_ticker", disponivel=True),
        "comparador": _resultado("comparador", disponivel=False),
    }
    with patch.object(fluxos.executor, "executar_varios", return_value=resultados):
        consolidado = fluxos.analisar_ticker("PETR4")

    assert consolidado["status_execucao"] == "PARCIAL"
    chamada = persistencia_mockada["concluir"].call_args
    assert chamada.args[1] == "PARCIAL"
    assert chamada.kwargs["duracao_ms"] >= 0


def test_registro_nao_contabiliza_especialista_pulado():
    with patch.object(fluxos.persistencia, "registrar_execucao_especialista", return_value=True) as registrar:
        ok = fluxos._registrar_execucoes("a", {
            "comparador": _resultado("comparador"),
            "memoria_research": {**_resultado("memoria_research"), "pulado": True},
        })
    assert ok is True
    registrar.assert_called_once_with("a", "comparador", registrar.call_args.args[2])


def test_analisar_ticker_registra_erro_e_relanca_quando_executor_falha(persistencia_mockada):
    with patch.object(fluxos.executor, "executar_varios", side_effect=RuntimeError("falha geral")):
        with pytest.raises(RuntimeError):
            fluxos.analisar_ticker("PETR4")
    persistencia_mockada["concluir"].assert_called_once()
    assert persistencia_mockada["concluir"].call_args[0][1] == "ERRO"


def test_comparar_casas_encadeamento_pula_memoria_quando_sem_cobertura(persistencia_mockada):
    """Decisão real baseada no resultado do comparador: 0 casas
    encontradas -> memoria_research NUNCA é acionado."""
    with patch.object(fluxos.executor, "executar_especialista") as mock_individual:
        mock_individual.return_value = _resultado("comparador", dados={"tabela_comparativa": []})
        consolidado = fluxos.comparar_casas("WEGE3")

    mock_individual.assert_called_once_with("comparador", ticker="WEGE3")
    assert consolidado["visao_especialistas"]["memoria_research"]["pulado"] is True
    assert consolidado["visao_especialistas"]["memoria_research"]["disponivel"] is True


def test_comparar_casas_encadeamento_aciona_memoria_quando_ha_cobertura(persistencia_mockada):
    chamadas = []

    def _fake_executar(especialista_id, **kwargs):
        chamadas.append((especialista_id, kwargs))
        if especialista_id == "comparador":
            return _resultado("comparador", dados={"tabela_comparativa": [{"casa": "BTG Pactual"}]})
        return _resultado("memoria_research", dados={"resultados": []})

    with patch.object(fluxos.executor, "executar_especialista", side_effect=_fake_executar):
        fluxos.comparar_casas("WEGE3")

    ids_chamados = [c[0] for c in chamadas]
    assert ids_chamados == ["comparador", "memoria_research"]


def test_comparar_casas_filtra_memoria_por_casa_unica():
    """casas=["Genial"] (1 casa) repassa como LISTA pra memoria_research -
    embeddings.buscar/store.listar_premissas aceitam lista desde
    2026-11-01 (gap antigo de "só filtra com exatamente 1 casa" fechado),
    nunca mais desempacotado pra string solta."""
    with patch.object(fluxos.persistencia, "iniciar_analise", return_value="a"), \
         patch.object(fluxos.persistencia, "concluir_analise"), \
         patch.object(fluxos.persistencia, "registrar_execucao_especialista"), \
         patch.object(fluxos.executor, "executar_especialista") as mock_individual:
        mock_individual.side_effect = lambda especialista_id, **kw: (
            _resultado("comparador", dados={"tabela_comparativa": [{"casa": "BTG Pactual"}]}) if especialista_id == "comparador"
            else _resultado("memoria_research", dados={"resultados": []})
        )
        fluxos.comparar_casas("WEGE3", casas=["Genial"])

    chamada_memoria = [c for c in mock_individual.call_args_list if c.args[0] == "memoria_research"][0]
    assert chamada_memoria.kwargs.get("casa") == ["Genial"]


def test_comparar_casas_filtra_memoria_por_varias_casas():
    """Gap fechado (2026-11-01): mais de 1 casa agora filtra memoria_research
    de verdade, em vez de cair pra None/sem filtro."""
    with patch.object(fluxos.persistencia, "iniciar_analise", return_value="a"), \
         patch.object(fluxos.persistencia, "concluir_analise"), \
         patch.object(fluxos.persistencia, "registrar_execucao_especialista"), \
         patch.object(fluxos.executor, "executar_especialista") as mock_individual:
        mock_individual.side_effect = lambda especialista_id, **kw: (
            _resultado("comparador", dados={"tabela_comparativa": [{"casa": "BTG Pactual"}, {"casa": "Monte Bravo"}, {"casa": "Nord"}]}) if especialista_id == "comparador"
            else _resultado("memoria_research", dados={"resultados": []})
        )
        fluxos.comparar_casas("WEGE3", casas=["Genial", "XP"])

    chamada_memoria = [c for c in mock_individual.call_args_list if c.args[0] == "memoria_research"][0]
    assert chamada_memoria.kwargs.get("casa") == ["Genial", "XP"]


def test_comparar_casas_sem_filtro_de_casas_repassa_none():
    """casas=None (padrao) - nenhum filtro de casa pro memoria_research,
    comportamento original preservado."""
    with patch.object(fluxos.persistencia, "iniciar_analise", return_value="a"), \
         patch.object(fluxos.persistencia, "concluir_analise"), \
         patch.object(fluxos.persistencia, "registrar_execucao_especialista"), \
         patch.object(fluxos.executor, "executar_especialista") as mock_individual:
        mock_individual.side_effect = lambda especialista_id, **kw: (
            _resultado("comparador", dados={"casas": ["Genial"]}) if especialista_id == "comparador"
            else _resultado("memoria_research", dados={"resultados": []})
        )
        fluxos.comparar_casas("WEGE3")

    chamada_memoria = [c for c in mock_individual.call_args_list if c.args[0] == "memoria_research"][0]
    assert chamada_memoria.kwargs.get("casa") is None


def test_identificar_catalisadores_aciona_os_4_especialistas_em_paralelo(persistencia_mockada):
    with patch.object(fluxos.executor, "executar_varios", return_value={
        "catalisadores": _resultado("catalisadores"),
        "noticias": _resultado("noticias"),
        "calendario": _resultado("calendario"),
        "memoria_research": _resultado("memoria_research"),
    }) as mock_varios:
        consolidado = fluxos.identificar_catalisadores("WEGE3")

    assert mock_varios.call_args[0][0] == ["catalisadores", "noticias", "calendario", "memoria_research"]
    assert set(consolidado["visao_especialistas"].keys()) == {"catalisadores", "noticias", "calendario", "memoria_research"}



def _dados_dcf_base():
    return {
        "analise_ticker": {
            "dados": {
                "fundamentos": {
                    "fluxo_caixa_livre": 1_000_000.0,
                    "ebitda": 500_000.0,
                    "divida_liquida_ebitda": 2.0,
                    "preco": 20.0,
                    "valor_mercado": 10_000_000.0,
                    "moeda": "BRL",
                    "moeda_fonte": "BRL",
                    "consultado_em": "2026-11-04",
                }
            }
        },
        "resultados_corporativos": {
            "dados": {
                "disponivel": True,
                "moeda": "REAL",
                "periodo_label": "2T2026",
                "dt_referencia": "2026-06-30",
                "balanco_fluxo_caixa": {"divida_liquida_atual": 1_250_000.0},
            }
        },
    }


_PREMISSAS_DCF_TESTE = {
    "crescimento_fcf_otimista": 12,
    "crescimento_fcf_base": 8,
    "crescimento_fcf_pessimista": 2,
    "wacc": 12,
    "g_terminal": 4,
}


def test_dcf_prioriza_divida_liquida_reportada_no_balanco_cvm():
    resultados = _dados_dcf_base()
    fluxos._anexar_premissas_dcf(resultados, _PREMISSAS_DCF_TESTE)
    p = resultados["analise_ticker"]["dados"]["premissas_dcf"]
    assert p["divida_liquida"] == pytest.approx(1_250_000.0)
    assert p["origem_divida_liquida"] == "CVM — balanço patrimonial consolidado"
    assert p["fonte_divida_liquida"] == "CVM ITR 2T2026"
    assert p["data_base"] == "2026-06-30"
    assert p["fcf_base"] == pytest.approx(1_000_000.0)
    assert p["acoes"] == pytest.approx(500_000.0)
    assert "CVM ITR 2T2026" in p["fonte_premissas"]


def test_dcf_nao_mistura_divida_cvm_quando_moeda_nao_compativel():
    resultados = _dados_dcf_base()
    resultados["resultados_corporativos"]["dados"]["moeda"] = "USD"
    fluxos._anexar_premissas_dcf(resultados, _PREMISSAS_DCF_TESTE)
    p = resultados["analise_ticker"]["dados"]["premissas_dcf"]
    # Fallback de alavancagem só é permitido porque yfinance confirma BRL/BRL.
    assert p["divida_liquida"] == pytest.approx(1_000_000.0)
    assert p["origem_divida_liquida"] == "Estimativa — EBITDA × dívida líquida/EBITDA"
    assert "CVM" not in p["fonte_divida_liquida"]


def test_dcf_fallback_de_divida_yfinance_fica_identificado_quando_cvm_ausente():
    resultados = _dados_dcf_base()
    resultados["resultados_corporativos"]["dados"]["balanco_fluxo_caixa"]["divida_liquida_atual"] = None
    fluxos._anexar_premissas_dcf(resultados, _PREMISSAS_DCF_TESTE)
    p = resultados["analise_ticker"]["dados"]["premissas_dcf"]
    assert p["divida_liquida"] == pytest.approx(1_000_000.0)
    assert p["origem_divida_liquida"] == "Estimativa — EBITDA × dívida líquida/EBITDA"
    assert "estimativa" in p["fonte_premissas"].lower()


def test_dcf_bloqueia_moeda_desconhecida_sem_tentar_converter():
    resultados = _dados_dcf_base()
    resultados["analise_ticker"]["dados"]["fundamentos"]["moeda_fonte"] = "XXX"
    fluxos._anexar_premissas_dcf(resultados, _PREMISSAS_DCF_TESTE)
    p = resultados["analise_ticker"]["dados"]["premissas_dcf"]
    assert p["fcf_base"] is None
    assert p["acoes"] is None
    assert p["motivo_bloqueio"] is not None
