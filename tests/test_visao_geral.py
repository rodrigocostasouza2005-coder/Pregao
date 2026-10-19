# -*- coding: utf-8 -*-
"""Regressao da auditoria 360 (docs/auditoria-redesign-360.md): o painel
MINHA WATCHLIST da VISAO GERAL mostrava o ticker com a mesma cor/peso
visual (var(--destaque), font-weight:600) ja' usada em outras telas pra
sinalizar "isto e' clicavel" (ex: ranking de MERCADO, ui/mercado_tab.py),
mas era so' <span> dentro de uma tabela HTML - sem nenhum destino real
(falsa affordance). Corrigido pra um st.button real, mesmo mecanismo
on_click=_ir_para_equity ja' usado no ranking.

st.columns/st.button/st.markdown funcionam em "bare mode" (fora de um
ScriptRunContext real) sem lancar excecao - mesmo padrao dos outros
testes de UI deste projeto (ver tests/test_mercado_ranking_ui.py)."""
from unittest.mock import patch

import ui.visao_geral as vg_mod

_PREFS = {"formato_numerico": "BR", "watchlist": ["PETR4", "VALE3"]}


def test_watchlist_vazia_mostra_mensagem_sem_crash():
    htmls = []
    with patch.object(vg_mod.st, "markdown", side_effect=lambda html, **k: htmls.append(html)):
        vg_mod._painel_watchlist_compacta({"formato_numerico": "BR", "watchlist": []})
    assert any("Adicione tickers" in h for h in htmls)


def test_cada_ticker_da_watchlist_e_um_botao_real_com_on_click_para_equity():
    cotacoes = {
        "PETR4": {"erro": None, "preco": 38.5, "variacao_pct": 1.2},
        "VALE3": {"erro": "sem dado"},
    }
    chamadas_button = []

    def _espiao_button(label, **kwargs):
        chamadas_button.append((label, kwargs))
        return False

    with patch.object(vg_mod, "obter_cotacoes_lote", return_value=cotacoes), \
         patch.object(vg_mod.st, "button", side_effect=_espiao_button):
        vg_mod._painel_watchlist_compacta(_PREFS)

    assert len(chamadas_button) == 2
    rotulos = [label for label, _k in chamadas_button]
    assert rotulos == ["PETR4", "VALE3"]
    for label, kwargs in chamadas_button:
        assert kwargs.get("on_click") is vg_mod._ir_para_equity
        assert kwargs.get("args") == (label, _PREFS)


def test_ticker_sem_cotacao_mostra_traco_sem_crash():
    htmls = []
    with patch.object(vg_mod, "obter_cotacoes_lote", return_value={"PETR4": {"erro": "sem dado"}, "VALE3": {"erro": "sem dado"}}), \
         patch.object(vg_mod.st, "button", return_value=False), \
         patch.object(vg_mod.st, "markdown", side_effect=lambda html, **k: htmls.append(html)):
        vg_mod._painel_watchlist_compacta(_PREFS)
    assert any("—" in h for h in htmls)
