# -*- coding: utf-8 -*-
"""Auditoria estrutural do inventario de coletores; sem rede ou banco."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import data.saude_dados as saude

def _coletor(nome="TESTE", **overrides):
    item = {"nome": nome, "fonte": "fonte de teste", "categoria": "Teste", "frequencia_esperada": "sob demanda", "instrumentado": True, "idade_maxima_horas": 12}
    item.update(overrides)
    return item

def test_inventario_atual_sem_problemas_estruturais():
    assert saude.auditar_registro_coletores() == []

def test_detecta_nome_duplicado_sem_diferenciar_maiusculas():
    problemas = saude.auditar_registro_coletores([_coletor("News"), _coletor(" news ")])
    assert any(p["codigo"] == "NOME_DUPLICADO" for p in problemas)

def test_detecta_metadado_obrigatorio_ausente():
    item = _coletor()
    del item["fonte"]
    problemas = saude.auditar_registro_coletores([item])
    assert any(p["codigo"] == "METADADO_AUSENTE" and "fonte" in p["detalhe"] for p in problemas)

def test_detecta_idade_maxima_invalida():
    problemas = saude.auditar_registro_coletores([_coletor(idade_maxima_horas=0)])
    assert any(p["codigo"] == "IDADE_MAXIMA_INVALIDA" for p in problemas)

def test_detecta_coletor_critico_removido():
    problemas = saude.auditar_registro_coletores([])
    ausentes = {p["coletor"] for p in problemas if p["codigo"] == "COLETOR_CRITICO_AUSENTE"}
    assert {"NEWS", "NEWS (Brasil)", "NEWS (Internacional)", "NEWS (watchlist)", "MERCADO", "CALENDARIO"} <= ausentes
