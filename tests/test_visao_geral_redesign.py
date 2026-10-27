# -*- coding: utf-8 -*-
"""Redesign de VISÃO GERAL seguindo referência visual (2026-10-27,
2a rodada - composição em GRADE, não lista empilhada): MERCADO AGORA +
duas linhas fixas lado a lado (altas/baixas+notícias+mapa setorial /
desempenho+agenda) ficam FORA do REGISTRO_PAINEIS (mesmo padrão do
TERMÔMETRO em MERCADO > PAINEL - não são mais arrastáveis
individualmente, trade-off aceito explicitamente). Cobre: os ids saíram
do registro, cada painel renderiza sem exceção, e render_visao_geral
completo roda sem exceção com tudo mockado."""
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
_COTACAO_OK = {"preco": 136000.0, "variacao_pct": 0.8, "erro": False}


def _ids():
    return [pid for pid, _, _ in vg.REGISTRO_PAINEIS]


def test_secoes_fixas_saem_do_registro_arrastavel():
    """mercado_agora/altas_baixas_resumo/noticias_resumo/
    mapa_setorial_compacto/desempenho_tabela/agenda_watchlist viram
    seções fixas (render_visao_geral) - não ficam mais no workspace
    modular arrastável, senão duplicariam (fixo + draggable)."""
    ids = _ids()
    for pid in [
        "mercado_agora", "altas_baixas_resumo", "noticias_resumo",
        "mapa_setorial_compacto", "desempenho_tabela", "agenda_watchlist",
    ]:
        assert pid not in ids


def test_ids_antigos_de_painel_tambem_fora():
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


def test_render_visao_geral_completo_sem_excecao():
    """render_visao_geral (grade fixa + workspace modular) de ponta a
    ponta, tudo mockado - garante que a composição nova não quebra a
    integração com o restante do REGISTRO_PAINEIS (ibov_grafico/
    leitura_rapida/analista_*/globais/watchlist_compacta)."""
    prefs = {
        "formato_numerico": "BR", "watchlist": [], "tema": "AMBAR",
        "ordem_paineis": {}, "paineis_visiveis": {}, "tamanho_paineis": {}, "layout_paineis_livre": {},
    }
    with patch("ui.visao_geral.obter_composicao_oficial", return_value={"PETR4": {}}), \
         patch("ui.visao_geral.obter_mercados_globais", return_value=[]), \
         patch("ui.visao_geral.obter_cdi", return_value=None), \
         patch("ui.visao_geral.obter_cotacao_indice", return_value=_COTACAO_OK), \
         patch("ui.visao_geral.obter_cotacao", return_value=_COTACAO_OK), \
         patch("ui.visao_geral.obter_altas_baixas", return_value=(_ALTAS, _BAIXAS)), \
         patch("ui.visao_geral.obter_top_mercado_tudo", return_value=[]), \
         patch("ui.visao_geral.obter_desempenho_setorial", return_value=_SETORES), \
         patch("ui.visao_geral.obter_mais_negociados", return_value=_NEGOCIADOS), \
         patch("ui.visao_geral._painel_proximos_watchlist", return_value=None), \
         patch("ui.visao_geral.obter_sintese_mercado", return_value={"ok": False, "motivo": "teste"}), \
         patch("ui.visao_geral.obter_historico", return_value=None), \
         patch("ui.visao_geral.obter_cotacoes_lote", return_value={}):
        vg.render_visao_geral(prefs, persistir_fn=None)
