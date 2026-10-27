# -*- coding: utf-8 -*-
"""Painel LEITURA RAPIDA reaproveitado de ui/mercado_tab.py pra dentro de
ui/visao_geral.py (2026-10-27) - o pedido real do Rodrigo era esse painel
ficar em VISAO GERAL, nao em MERCADO > PAINEL (os outros 3 painéis do PR
#182 - metricas/grafico/noticias - ja tinham equivalente aqui antes).

st.markdown/st.columns funcionam em "bare mode" (fora de ScriptRunContext
real) sem lancar excecao - mesmo padrao de tests/test_analista_mercado_ui.py."""
from unittest.mock import patch

import ui.visao_geral as vg

_PREFS = {"formato_numerico": "BR", "watchlist": []}


def test_leitura_rapida_registrada_em_visao_geral():
    ids = [pid for pid, _, _ in vg.REGISTRO_PAINEIS]
    assert "leitura_rapida" in ids


def test_leitura_rapida_renderiza_sem_excecao_com_dados_mockados():
    mapa = {pid: fn for pid, _, fn in vg.REGISTRO_PAINEIS}
    painel = mapa["leitura_rapida"]
    with patch("ui.mercado_tab.obter_cotacao_indice",
               return_value={"preco": 136000.0, "variacao_pct": 0.8, "erro": False}), \
         patch("ui.mercado_tab.obter_altas_baixas",
               return_value=([{"ticker": "PETR4", "variacao_pct": 3.1}], [])), \
         patch("ui.mercado_tab.obter_desempenho_setorial",
               return_value=[{"setor": "Varejo", "variacao_media_pct": -1.2, "n_papeis": 4}]), \
         patch("ui.mercado_tab.obter_composicao_oficial", return_value={"PETR4": {}}), \
         patch("ui.mercado_tab.rotulo_cotacao_em_cache", return_value=None):
        painel(_PREFS)  # nao deve lancar excecao
