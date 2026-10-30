# -*- coding: utf-8 -*-
"""Relevancia e credibilidade (data/x_radar/relevancia.py, secao 5 do
pedido) - puramente deterministico, sem rede/IA. Cobre: motivo sempre
preenchido quando ha nota, credibilidade NUNCA inventada pra autor sem
historico (None, nao 0), nota nunca passa de 100."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.x_radar.relevancia import calcular_credibilidade, calcular_relevancia


def test_relevancia_zero_quando_classificacao_falhou():
    score, motivo = calcular_relevancia({"ok": False}, ticker_e_foco=True, horario_publicacao=None)
    assert score == 0
    assert "indisponivel" in motivo


def test_relevancia_soma_fatores_com_motivo_explicito():
    classificacao = {"ok": True, "categoria": "fato_confirmado", "catalisador": "M&A", "necessita_investigacao": True}
    score, motivo = calcular_relevancia(classificacao, ticker_e_foco=True, horario_publicacao=datetime.now(timezone.utc))
    # ticker_foco(30) + fato_confirmado(30) + catalisador(20) + atualidade(15) + investigacao(10) = 105 -> capado em 100
    assert score == 100
    assert "ticker monitorado" in motivo
    assert "catalisador" in motivo


def test_relevancia_zero_sem_nenhum_fator_tem_motivo_explicito_tambem():
    score, motivo = calcular_relevancia({"ok": True, "categoria": "sem_relevancia"}, ticker_e_foco=False, horario_publicacao=None)
    assert score == 0
    assert motivo  # nunca motivo vazio, mesmo com score 0


def test_relevancia_publicacao_antiga_nao_ganha_pontos_de_atualidade():
    classificacao = {"ok": True, "categoria": "opiniao_analista"}
    antiga = datetime.now(timezone.utc) - timedelta(days=10)
    score, motivo = calcular_relevancia(classificacao, ticker_e_foco=False, horario_publicacao=antiga)
    assert "publicado ha" not in motivo


def test_credibilidade_none_sem_historico_nunca_zero():
    score, motivo = calcular_credibilidade("@autor_novo", None)
    assert score is None
    assert motivo is None
    score2, motivo2 = calcular_credibilidade("@autor_novo", [])
    assert score2 is None
    assert motivo2 is None


def test_credibilidade_so_conta_estados_finais():
    historico = [{"estado": "detectado"}, {"estado": "em_verificacao"}]
    score, motivo = calcular_credibilidade("@autor", historico)
    assert score is None  # nenhum estado final ainda - sem dado suficiente


def test_credibilidade_calculada_com_estados_finais():
    historico = [
        {"estado": "confirmado"}, {"estado": "confirmado"}, {"estado": "refutado"},
        {"estado": "detectado"},  # nao conta pro denominador
    ]
    score, motivo = calcular_credibilidade("@autor", historico)
    assert score == 67  # 2/3 confirmados, arredondado
    assert "2/3" in motivo
