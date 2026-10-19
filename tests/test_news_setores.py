# -*- coding: utf-8 -*-
"""Classificação de notícia por setor (data/news_setores.py)."""
from data.news_setores import classificar_setores


def test_palavra_inteira_nao_substring():
    """Antes, 'gas' casava com 'gastos' e 'aco' com 'acordo'."""
    assert "PETRÓLEO & GÁS" not in classificar_setores("Governo corta gastos e fecha acordo fiscal", [])
    assert "MINERAÇÃO & SIDERURGIA" not in classificar_setores("Governo corta gastos e fecha acordo fiscal", [])


def test_palavra_inteira_e_plural_continuam_casando():
    assert "PETRÓLEO & GÁS" in classificar_setores("Preço do gás natural sobe", [])
    assert "MINERAÇÃO & SIDERURGIA" in classificar_setores("Preço do aço sobe na China", [])
    assert "BANCOS" in classificar_setores("Bancos ampliam crédito", [])
    assert "VAREJO" in classificar_setores("Varejistas reforçam estoques", [])
    assert "IMOBILIÁRIO" in classificar_setores("Construtoras aceleram lançamentos", [])


def test_ticker_do_setor_classifica_mesmo_sem_palavra():
    assert classificar_setores("Ações sobem após balanço", ["VALE3"]) == ["MINERAÇÃO & SIDERURGIA"]
