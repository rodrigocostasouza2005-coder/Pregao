"""Regressão: o painel DESEMPENHO SETORIAL derrubava a aba MERCADO com
KeyError: 'dia' (produção, 29/10/2026) - _seletor_janela devolve a chave
interna ("dia"/"semana"/"mes") e o painel a usava como RÓTULO
(_JANELA_ROTULO_PARA_CHAVE[janela]). Renderiza o painel nas 3 janelas,
sem rede (dados e cotação mockados)."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.mercado_tab as mercado_tab_mod  # noqa: E402

_PREFS = {"formato_numerico": "BR", "watchlist": [], "tema": "AMBAR"}
_SETORES = [
    {"setor": "Bancos e Serviços Financeiros", "variacao_media_pct": 1.2},
    {"setor": "Higiene e Beleza", "variacao_media_pct": -3.1},
]


@pytest.mark.parametrize("janela", ["dia", "semana", "mes"])
def test_painel_setorial_renderiza_em_todas_as_janelas(janela):
    cotacao = {"erro": None, "variacao_pct": 0.4}
    with patch.object(mercado_tab_mod, "_seletor_janela", return_value=janela), \
         patch.object(mercado_tab_mod, "obter_desempenho_setorial", return_value=list(_SETORES)), \
         patch.object(mercado_tab_mod, "obter_cotacao_indice", return_value=cotacao) as cot:
        mercado_tab_mod._painel_setorial(_PREFS)
    # a comparação com o Ibovespa só existe na janela DIA
    assert cot.called is (janela == "dia")


def test_seletor_janela_devolve_chave_interna_conhecida():
    assert set(mercado_tab_mod._JANELA_ROTULO_PARA_CHAVE.values()) == {"dia", "semana", "mes"}
