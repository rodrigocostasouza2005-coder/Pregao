# -*- coding: utf-8 -*-
"""Testes da camada analítica nova de MACRO (ui/macro_tab.py:_leitura_macro,
missão "camada analítica" 2026-11-18): auditoria desta missão confirmou
que MERCADO (ui/visao_geral.py "LEITURA DO PREGÃO" + ui/mercado_tab.py
"LEITURA RÁPIDA"), NOTÍCIAS (data/news.py "LEITURA DE MERCADO" por
matéria) e RADAR (data/radar.py: FATO/CALCULO_INTERNO/DADO_INSUFICIENTE +
campo 'relevancia') já tinham camada interpretativa real - MACRO era a
única das 5 áreas pedidas sem nenhuma, só números/gráficos crus.

_leitura_macro reaproveita os MESMOS dados já buscados pelos outros
painéis desta aba (obter_ipca/obter_selic_meta/obter_cenario_global,
mockados aqui - nunca uma chamada de rede real) + o catálogo editorial
já revisado (data/radar_setorial.CATALOGO, via setores_sensiveis) pra
responder "o que mudou no cenário?" e "quais ativos podem ser
afetados?", com rótulo explícito [FATO]/[LEITURA] (mesmo padrão de
ui/mercado_tab.py:_nota_contextual). Zero IA, zero correlação inventada
- confere aqui que a seção NUNCA aparece quando nenhuma série mostrou
mudança real nem quando o maior mover do cenário global não tem
correspondência no catálogo setorial.

Chama a função direto em "bare mode" (fora de ScriptRunContext real),
mesmo padrão de tests/test_macro_bloomberg_20261106.py: patch.object
(mt.st, "markdown", ...) pra capturar o HTML sem sessão Streamlit real."""
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.macro_tab as mt

_PREFS = {"formato_numerico": "BR", "tema": "AMBAR"}


def _render(fn, *args, **kwargs):
    htmls = []
    with patch.object(mt.st, "markdown", side_effect=lambda h, **k: htmls.append(h)), \
         patch.object(mt.st, "container") as mock_container:
        mock_container.return_value.__enter__ = lambda self: self
        mock_container.return_value.__exit__ = lambda self, *a: False
        fn(*args, **kwargs)
    return "".join(htmls)


def _ipca_df(valores):
    return pd.DataFrame({
        "data": pd.date_range("2026-09-01", periods=len(valores), freq="MS"),
        "ipca_12m_pct": valores,
    })


def _selic_df_estavel(valor=13.75, dias=30):
    return pd.DataFrame({
        "data": pd.date_range("2026-10-01", periods=dias, freq="D"),
        "selic_meta_pct": [valor] * dias,
    })


def _selic_df_com_mudanca():
    """15 dias a 14.0%, depois 10 dias a 13.75% - mudança real dentro da
    janela consultada, com data de mudança identificável."""
    datas = pd.date_range("2026-10-01", periods=25, freq="D")
    valores = [14.0] * 15 + [13.75] * 10
    return pd.DataFrame({"data": datas, "selic_meta_pct": valores})


def test_sem_mudanca_em_nenhum_indicador_nao_mostra_secao():
    """Nenhuma série mudou dentro da janela consultada e cenário global
    sem dado -> seção inteira ausente (estado vazio honesto, nunca um
    texto genérico só pra não parecer vazia)."""
    with patch.object(mt, "obter_ipca", return_value=_ipca_df([4.50, 4.50])), \
         patch.object(mt, "obter_selic_meta", return_value=_selic_df_estavel()), \
         patch.object(mt, "obter_cenario_global", return_value=[]):
        html = _render(mt._leitura_macro, _PREFS)
    assert html == ""
    assert "LEITURA MACRO" not in html


def test_ipca_com_variacao_mostra_fato_com_numeros_reais():
    with patch.object(mt, "obter_ipca", return_value=_ipca_df([4.50, 4.80])), \
         patch.object(mt, "obter_selic_meta", return_value=_selic_df_estavel()), \
         patch.object(mt, "obter_cenario_global", return_value=[]):
        html = _render(mt._leitura_macro, _PREFS)
    assert "LEITURA MACRO" in html
    assert "[FATO]" in html
    assert "IPCA 12 meses subiu de 4,50% para 4,80%" in html
    assert "+0,30 p.p." in html


def test_ipca_variacao_insignificante_nao_gera_fato():
    """Diferença de arredondamento (<0,01 p.p.) nunca é reportada como
    'mudança' - nunca infla uma variação que não é real."""
    with patch.object(mt, "obter_ipca", return_value=_ipca_df([4.500, 4.503])), \
         patch.object(mt, "obter_selic_meta", return_value=_selic_df_estavel()), \
         patch.object(mt, "obter_cenario_global", return_value=[]):
        html = _render(mt._leitura_macro, _PREFS)
    assert "IPCA 12 meses" not in html


def test_selic_mudou_mostra_fato_e_leitura_dos_setores_sensiveis():
    with patch.object(mt, "obter_ipca", return_value=None), \
         patch.object(mt, "obter_selic_meta", return_value=_selic_df_com_mudanca()), \
         patch.object(mt, "obter_cenario_global", return_value=[]), \
         patch.object(mt, "setores_sensiveis_a_juros", return_value=["Bancos", "Construção Civil"]):
        html = _render(mt._leitura_macro, _PREFS)
    assert "Selic meta mudou de 14,00% para 13,75% em 16/10/2026" in html
    assert "[LEITURA]" in html
    assert "Bancos" in html and "Construção Civil" in html


def test_selic_sem_mudanca_na_janela_nao_gera_fato_nem_leitura():
    with patch.object(mt, "obter_ipca", return_value=None), \
         patch.object(mt, "obter_selic_meta", return_value=_selic_df_estavel()), \
         patch.object(mt, "obter_cenario_global", return_value=[]):
        html = _render(mt._leitura_macro, _PREFS)
    assert "Selic meta mudou" not in html


def test_cenario_global_maior_mover_com_catalogo_mostra_fato_e_leitura():
    dados = [
        {"nome": "Ouro", "preco": 2650.3, "variacao_pct": 0.4},
        {"nome": "Brent", "preco": 70.1, "variacao_pct": -3.2},
        {"nome": "VIX", "preco": 18.2, "variacao_pct": 1.1},
    ]
    with patch.object(mt, "obter_ipca", return_value=None), \
         patch.object(mt, "obter_selic_meta", return_value=_selic_df_estavel()), \
         patch.object(mt, "obter_cenario_global", return_value=dados), \
         patch.object(mt, "setores_sensiveis", return_value=["Petróleo e Gás"]):
        html = _render(mt._leitura_macro, _PREFS)
    assert "Maior variação do dia no cenário global: Brent (-3,20%)" in html
    assert "[LEITURA]" in html
    assert "Petróleo e Gás" in html


def test_cenario_global_maior_mover_sem_correspondencia_no_catalogo_so_mostra_fato():
    """'Ouro'/'VIX'/'Treasuries 10A' não têm entrada no catálogo setorial
    - a LEITURA correspondente nunca aparece pra eles (nunca inventa uma
    correlação que o catálogo não sustenta)."""
    dados = [{"nome": "Ouro", "preco": 2650.3, "variacao_pct": 2.5}]
    with patch.object(mt, "obter_ipca", return_value=None), \
         patch.object(mt, "obter_selic_meta", return_value=_selic_df_estavel()), \
         patch.object(mt, "obter_cenario_global", return_value=dados):
        html = _render(mt._leitura_macro, _PREFS)
    assert "Maior variação do dia no cenário global: Ouro (+2,50%)" in html
    assert "[LEITURA]" not in html


def test_setores_sensiveis_generaliza_por_termos_arbitrarios():
    """setores_sensiveis(*termos) é a generalização usada tanto por
    setores_sensiveis_a_juros quanto pela LEITURA MACRO pra commodities -
    confere que ela de fato varre o catálogo por qualquer termo dado."""
    setores_petroleo = mt.setores_sensiveis("petróleo", "brent")
    assert isinstance(setores_petroleo, list)
    assert len(setores_petroleo) > 0  # catálogo real tem >= 1 setor citando petróleo/Brent


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
