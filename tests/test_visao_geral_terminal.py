# -*- coding: utf-8 -*-
"""Redesign terminal de VISÃO GERAL (2026-10-27, inspirado em Bloomberg,
aprovado via prévia visual): cockpit fixo (sem workspace modular nesta
aba), indicadores densos, leitura do pregão condensada, gráfico+"para
investigar", grade de exploração (altas/baixas com barra de magnitude,
notícias, mapa setorial com flag de dispersão), desempenho+agenda/teses
de research. Cobre: REGISTRO_PAINEIS vazio (sem drag), cada painel
renderiza sem exceção (dados reais e vazios), teses de research só
aparecem com recomendação real salva, e render_visao_geral completo roda
sem exceção com tudo mockado."""
from unittest.mock import patch

import ui.visao_geral as vg

_PREFS = {"formato_numerico": "BR", "watchlist": [], "tema": "AMBAR"}

_ALTAS = [
    {"ticker": "PETR4", "preco": 36.5, "variacao_pct": 3.1, "setor": "Petróleo e Gás"},
    {"ticker": "PRIO3", "preco": 40.0, "variacao_pct": 1.2, "setor": "Petróleo e Gás"},
]
_BAIXAS = [{"ticker": "MGLU3", "preco": 2.1, "variacao_pct": -4.2, "setor": "Consumo"}]
_SETORES = [
    {"setor": "Petróleo e Gás", "variacao_media_pct": 2.1, "n_papeis": 5},
    {"setor": "Varejo", "variacao_media_pct": -4.3, "n_papeis": 2},
]
_NEGOCIADOS = [
    {"ticker": "PETR4", "preco": 36.5, "variacao_pct": 3.1, "setor": "Petróleo e Gás", "volume_financeiro": 4.2e9},
]
_COTACAO_OK = {"preco": 136000.0, "variacao_pct": 0.8, "erro": False}


def _ids():
    return [pid for pid, _, _ in vg.REGISTRO_PAINEIS]


def test_registro_paineis_vazio_sem_drag():
    # redesign terminal: todo o conteudo virou secao fixa - sem workspace
    # modular nesta aba (MERCADO > PAINEL continua com drag, intocado).
    assert _ids() == []


def test_altas_baixas_resumo_renderiza_sem_excecao():
    with patch.object(vg, "obter_altas_baixas", return_value=(_ALTAS, _BAIXAS)):
        vg._painel_altas_baixas_resumo(_PREFS)


def test_mapa_setorial_compacto_renderiza_flag_dispersao_sem_excecao():
    with patch.object(vg, "obter_desempenho_setorial", return_value=_SETORES):
        vg._painel_mapa_setorial_compacto(_PREFS)


def test_desempenho_tabela_renderiza_sem_excecao():
    with patch.object(vg, "obter_mais_negociados", return_value=_NEGOCIADOS):
        vg._painel_desempenho_tabela(_PREFS)


def test_indicadores_renderiza_sem_excecao():
    with patch.object(vg, "obter_composicao_oficial", return_value={"PETR4": {}}), \
         patch.object(vg, "obter_mercados_globais", return_value=[]), \
         patch.object(vg, "obter_cdi", return_value=None), \
         patch.object(vg, "obter_cotacao_indice", return_value=_COTACAO_OK), \
         patch.object(vg, "obter_cotacao", return_value=_COTACAO_OK):
        vg._painel_indicadores(_PREFS)


def test_paineis_vazios_nao_quebram():
    with patch.object(vg, "obter_altas_baixas", return_value=([], [])):
        vg._painel_altas_baixas_resumo(_PREFS)
    with patch.object(vg, "obter_desempenho_setorial", return_value=[]):
        vg._painel_mapa_setorial_compacto(_PREFS)
    with patch.object(vg, "obter_mais_negociados", return_value=[]):
        vg._painel_desempenho_tabela(_PREFS)


def test_teses_research_watchlist_sem_watchlist_retorna_vazio():
    assert vg._teses_research_watchlist({"watchlist": []}) == []


def test_teses_research_watchlist_so_inclui_item_com_recomendacao_real():
    relatorios = [
        {"casa": "Genial Analisa", "tickers": ["PETR4"], "recomendacao": "COMPRA", "preco_alvo": 44.0},
        {"casa": "XP", "tickers": ["VALE3"], "recomendacao": None, "preco_alvo": None},
    ]
    with patch.object(vg, "_casas_ativas", return_value=["genial"]), \
         patch.object(vg, "preparar_leitura", return_value=(relatorios, [], [], [])):
        itens = vg._teses_research_watchlist({"watchlist": ["PETR4", "VALE3"]})
    assert len(itens) == 1
    assert itens[0][0] == "PETR4"
    assert itens[0][1]["recomendacao"] == "COMPRA"


def test_painel_agenda_e_teses_renderiza_sem_excecao():
    with patch.object(vg, "_painel_proximos_watchlist", return_value=None), \
         patch.object(vg, "_teses_research_watchlist", return_value=[
             ("PETR4", {"casa": "Genial Analisa", "recomendacao": "COMPRA", "preco_alvo": 44.0}),
         ]):
        vg._painel_agenda_e_teses(_PREFS)


def test_render_visao_geral_completo_sem_excecao():
    """render_visao_geral (cockpit fixo de ponta a ponta), tudo mockado -
    garante que a composição inteira (indicadores/leitura do pregão/
    gráfico+investigar/grade de exploração/desempenho+agenda/globais+
    watchlist) roda sem exceção."""
    prefs = {"formato_numerico": "BR", "watchlist": [], "tema": "AMBAR"}
    with patch.object(vg, "obter_composicao_oficial", return_value={"PETR4": {}}), \
         patch.object(vg, "obter_mercados_globais", return_value=[]), \
         patch.object(vg, "obter_cdi", return_value=None), \
         patch.object(vg, "obter_cotacao_indice", return_value=_COTACAO_OK), \
         patch.object(vg, "obter_cotacao", return_value=_COTACAO_OK), \
         patch.object(vg, "obter_altas_baixas", return_value=(_ALTAS, _BAIXAS)), \
         patch.object(vg, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(vg, "obter_desempenho_setorial", return_value=_SETORES), \
         patch.object(vg, "obter_mais_negociados", return_value=_NEGOCIADOS), \
         patch.object(vg, "_painel_proximos_watchlist", return_value=None), \
         patch.object(vg, "_teses_research_watchlist", return_value=[]), \
         patch.object(vg, "_proximo_evento_watchlist", return_value=None), \
         patch.object(vg, "obter_sintese_mercado", return_value={"ok": False, "motivo": "teste"}), \
         patch.object(vg, "obter_historico", return_value=None), \
         patch.object(vg, "_painel_globais", return_value=None), \
         patch.object(vg, "obter_cotacoes_lote", return_value={}):
        vg.render_visao_geral(prefs, persistir_fn=None)
