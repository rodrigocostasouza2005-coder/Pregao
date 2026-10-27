# -*- coding: utf-8 -*-
"""Redesign de VISÃO GERAL (2026-10-27, seguindo referência visual do
Rodrigo): 3 painéis novos compactos (altas_baixas_resumo/
mapa_setorial_compacto/desempenho_tabela) que substituem, só nesta aba,
os painéis completos equivalentes (que continuam intocados em
MERCADO > PAINEL). Cobre: registro em REGISTRO_PAINEIS, renderização sem
exceção em bare mode com dados mockados, e que os ids antigos saíram do
registro (sem duplicar conteúdo entre PAINEL e VISÃO GERAL)."""
from unittest.mock import patch

import ui.visao_geral as vg

_PREFS = {"formato_numerico": "BR", "watchlist": [], "tema": "AMBAR"}

_ALTAS = [{"ticker": "PETR4", "preco": 36.5, "variacao_pct": 3.1, "setor": "Petróleo e Gás"}]
_BAIXAS = [{"ticker": "MGLU3", "preco": 2.1, "variacao_pct": -4.2, "setor": "Consumo"}]
_SETORES = [
    {"setor": "Petróleo e Gás", "variacao_media_pct": 2.1, "n_papeis": 5},
    {"setor": "Varejo", "variacao_media_pct": -1.3, "n_papeis": 4},
]
_NEGOCIADOS = [
    {"ticker": "PETR4", "preco": 36.5, "variacao_pct": 3.1, "setor": "Petróleo e Gás", "volume_financeiro": 4.2e9},
]


def _ids():
    return [pid for pid, _, _ in vg.REGISTRO_PAINEIS]


def test_paineis_novos_registrados():
    ids = _ids()
    for pid in ["altas_baixas_resumo", "mapa_setorial_compacto", "desempenho_tabela"]:
        assert pid in ids


def test_ids_antigos_saem_do_registro_nao_duplica_com_painel():
    ids = _ids()
    for pid in ["altas_baixas", "mais_negociados", "setorial"]:
        assert pid not in ids


def test_altas_baixas_resumo_renderiza_sem_excecao():
    with patch("ui.visao_geral.obter_altas_baixas", return_value=(_ALTAS, _BAIXAS)):
        vg._painel_altas_baixas_resumo(_PREFS)


def test_mapa_setorial_compacto_renderiza_sem_excecao():
    with patch("ui.visao_geral.obter_desempenho_setorial", return_value=_SETORES):
        vg._painel_mapa_setorial_compacto(_PREFS)


def test_desempenho_tabela_renderiza_sem_excecao():
    with patch("ui.visao_geral.obter_mais_negociados", return_value=_NEGOCIADOS):
        vg._painel_desempenho_tabela(_PREFS)


def test_paineis_vazios_nao_quebram():
    with patch("ui.visao_geral.obter_altas_baixas", return_value=([], [])):
        vg._painel_altas_baixas_resumo(_PREFS)
    with patch("ui.visao_geral.obter_desempenho_setorial", return_value=[]):
        vg._painel_mapa_setorial_compacto(_PREFS)
    with patch("ui.visao_geral.obter_mais_negociados", return_value=[]):
        vg._painel_desempenho_tabela(_PREFS)
