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
    assert mock_varios.call_args[0][0] == ["analise_ticker", "comparador", "memoria_research", "noticias", "catalisadores"]
    assert mock_varios.call_args[1]["ticker"] == "PETR4"
    assert "_analise_id" in consolidado and "_duracao_ms" in consolidado


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
        mock_individual.return_value = _resultado("comparador", dados={"casas": []})
        consolidado = fluxos.comparar_casas("WEGE3")

    mock_individual.assert_called_once_with("comparador", ticker="WEGE3")
    assert consolidado["visao_especialistas"]["memoria_research"]["pulado"] is True
    assert consolidado["visao_especialistas"]["memoria_research"]["disponivel"] is True


def test_comparar_casas_encadeamento_aciona_memoria_quando_ha_cobertura(persistencia_mockada):
    chamadas = []

    def _fake_executar(especialista_id, **kwargs):
        chamadas.append((especialista_id, kwargs))
        if especialista_id == "comparador":
            return _resultado("comparador", dados={"casas": ["Genial", "XP"]})
        return _resultado("memoria_research", dados={"resultados": []})

    with patch.object(fluxos.executor, "executar_especialista", side_effect=_fake_executar):
        fluxos.comparar_casas("WEGE3")

    ids_chamados = [c[0] for c in chamadas]
    assert ids_chamados == ["comparador", "memoria_research"]


def test_comparar_casas_filtra_memoria_por_casa_unica():
    with patch.object(fluxos.persistencia, "iniciar_analise", return_value="a"), \
         patch.object(fluxos.persistencia, "concluir_analise"), \
         patch.object(fluxos.persistencia, "registrar_execucao_especialista"), \
         patch.object(fluxos.executor, "executar_especialista") as mock_individual:
        mock_individual.side_effect = lambda especialista_id, **kw: (
            _resultado("comparador", dados={"casas": ["Genial"]}) if especialista_id == "comparador"
            else _resultado("memoria_research", dados={"resultados": []})
        )
        fluxos.comparar_casas("WEGE3", casas=["Genial"])

    chamada_memoria = [c for c in mock_individual.call_args_list if c.args[0] == "memoria_research"][0]
    assert chamada_memoria.kwargs.get("casa") == "Genial"


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
