# -*- coding: utf-8 -*-
"""Teste do gap real corrigido na auditoria de arquitetura (Agente A,
2026-11-12): Monte Bravo, Nord Research e os 4 bancos globais (J.P.
Morgan/BofA/Morgan Stanley/Citi) sao casas ATIVAS de research
(data/research/__init__.py:CASAS) mas nao estavam cadastradas em
data/diagnostico.py (painel DIAGNOSTICO DE FONTES, aba CONFIG) -
nenhuma delas era testada por ali, mesmo tendo seu proprio
testar_conexao(). Este teste trava que as 6 continuam presentes (nunca
regride em silencio se alguem remover de novo sem querer).

Uso: python -m pytest tests/test_diagnostico_research_casas.py"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.diagnostico as diag_mod

_CASAS_ATIVAS_RESEARCH = (
    "Monte Bravo", "Nord Research", "J.P. Morgan Global Research",
    "BofA Institute", "Morgan Stanley Insights", "Citi Global Insights",
)


def test_todas_as_casas_ativas_de_research_tem_teste_especifico_cadastrado():
    faltantes = [nome for nome in _CASAS_ATIVAS_RESEARCH if nome not in diag_mod._TESTES_ESPECIFICOS]
    assert faltantes == [], f"casas sem teste especifico cadastrado: {faltantes}"


def test_todas_as_casas_ativas_de_research_tem_entrada_em_fontes():
    nomes_em_fontes = {f["nome"] for f in diag_mod.FONTES}
    faltantes = [nome for nome in _CASAS_ATIVAS_RESEARCH if nome not in nomes_em_fontes]
    assert faltantes == [], f"casas sem entrada em FONTES: {faltantes}"


def test_teste_especifico_de_cada_casa_e_o_proprio_testar_conexao_do_modulo():
    """O diagnostico tem que chamar a MESMA logica de verdade que o
    coletor real usa (nao um GET generico) - ver docstring de
    data.diagnostico.testar_fonte."""
    from data.research import bankofamerica, citi, jpmorgan, montebravo, morgan_stanley, nord

    mapeamento = {
        "Monte Bravo": montebravo.testar_conexao,
        "Nord Research": nord.testar_conexao,
        "J.P. Morgan Global Research": jpmorgan.testar_conexao,
        "BofA Institute": bankofamerica.testar_conexao,
        "Morgan Stanley Insights": morgan_stanley.testar_conexao,
        "Citi Global Insights": citi.testar_conexao,
    }
    for nome, funcao_esperada in mapeamento.items():
        assert diag_mod._TESTES_ESPECIFICOS[nome] is funcao_esperada


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
