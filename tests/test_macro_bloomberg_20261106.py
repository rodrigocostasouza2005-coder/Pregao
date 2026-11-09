# -*- coding: utf-8 -*-
"""Testes da reformulação visual Bloomberg âmbar de MACRO (ui/macro_tab.py:
render_macro/render_macro_juros/render_macro_cambio_commodities/
render_macro_calendario, 2026-11-06) - troca de montagem manual de sinal
("alta" if valor >= 0 else "baixa" + "+" na mão, padrão citado como
duplicado na docstring de ui/design_system.py) pelos helpers
classe_sinal/numero_financeiro_html/variacao_html, mesma identidade visual
já aplicada em MERCADO/ANÁLISES/WATCHLIST. ZERO dado novo: só mocka as
mesmas funções de data/macro.py já usadas antes - nunca inventa número.

Chama as funções direto em "bare mode" (fora de ScriptRunContext real),
mesmo padrão seguro já usado em tests/test_secoes_watchlist_redesign.py e
tests/test_cotacao_em_cache_sinalizada.py."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

import ui.macro_tab as mt

_PREFS = {"formato_numerico": "BR", "tema": "AMBAR"}


def _render(fn, *args, **kwargs):
    """Chama fn (uma das funções de ui/macro_tab.py) capturando todo HTML
    passado a st.markdown, igual ao padrão de test_secoes_watchlist_redesign.py."""
    htmls = []
    with patch.object(mt.st, "markdown", side_effect=lambda h, **k: htmls.append(h)):
        fn(*args, **kwargs)
    return "".join(htmls)


# ============================================================
# 1. _painel_resumo (MACRO > Indicadores, abertura fixa): números
#    grandes (Selic/CDI/IPCA/Juro real) e a tabela Focus usam
#    numero_financeiro_html (tabular-nums) em vez do "%" concatenado na mão.
# ============================================================

def _serie(valor, dias=2):
    return pd.DataFrame({
        "data": pd.date_range("2026-11-01", periods=dias, freq="D"),
        "valor": [valor] * dias,
    })


def test_1_painel_resumo_usa_tabular_nums_nos_numeros_grandes():
    selic_df = pd.DataFrame({"data": pd.date_range("2026-11-01", periods=2), "selic_meta_pct": [13.75, 13.75]})
    cdi_df = pd.DataFrame({"data": pd.date_range("2026-11-01", periods=2), "cdi_anualizado_pct": [13.65, 13.65]})
    ipca_df = pd.DataFrame({"data": pd.date_range("2026-11-01", periods=2), "ipca_12m_pct": [4.5, 4.5]})
    focus_vazio = pd.DataFrame()
    with patch.object(mt, "obter_selic_meta", return_value=selic_df), \
         patch.object(mt, "obter_cdi", return_value=cdi_df), \
         patch.object(mt, "obter_ipca", return_value=ipca_df), \
         patch.object(mt, "obter_focus_ipca", return_value=focus_vazio), \
         patch.object(mt, "obter_focus_selic", return_value=focus_vazio), \
         patch.object(mt.st, "warning") as mock_warning:
        html = _render(mt._painel_resumo, _PREFS)
    assert "class='ds-numero'>13,75%</span>" in html  # Selic meta
    assert "class='ds-numero'>13,65%</span>" in html  # CDI
    assert "class='ds-numero'>4,50%</span>" in html  # IPCA 12m
    mock_warning.assert_called_once()  # Focus indisponível nos 2 indicadores


def test_1b_painel_resumo_focus_tabela_usa_tabular_nums():
    base_df = pd.DataFrame({"data": pd.date_range("2026-11-01", periods=1), "selic_meta_pct": [13.75]})
    focus_ipca = pd.DataFrame({
        "ano_referencia": [2026], "mediana_pct": [4.52],
        "data_calculo": pd.to_datetime(["2026-11-05"]),
    })
    with patch.object(mt, "obter_selic_meta", return_value=base_df), \
         patch.object(mt, "obter_cdi", return_value=base_df.rename(columns={"selic_meta_pct": "cdi_anualizado_pct"})), \
         patch.object(mt, "obter_ipca", return_value=base_df.rename(columns={"selic_meta_pct": "ipca_12m_pct"})), \
         patch.object(mt, "obter_focus_ipca", return_value=focus_ipca), \
         patch.object(mt, "obter_focus_selic", return_value=pd.DataFrame()):
        html = _render(mt._painel_resumo, _PREFS)
    assert "class='ds-numero'>4,52%</span>" in html
    assert "text-align:right;" in html  # coluna numerica alinhada a direita


# ============================================================
# 2. _painel_cenario_global: classe_sinal/variacao_html em vez do
#    ternário "alta"/"baixa" + "+" na mão (padrão citado na docstring
#    da fundação do design system como duplicado neste exato arquivo).
# ============================================================

def test_2_cenario_global_colore_por_sinal_via_design_system():
    dados = [
        {"nome": "Ouro", "preco": 2650.30, "variacao_pct": 1.25},
        {"nome": "Brent", "preco": 74.10, "variacao_pct": -0.8},
    ]
    with patch.object(mt, "obter_cenario_global", return_value=dados), \
         patch.object(mt.st, "caption"):
        html = _render(mt._painel_cenario_global, _PREFS)
    assert "class='ds-numero alta'>+1,25%</span>" in html
    assert "class='ds-numero baixa'>-0,80%</span>" in html
    assert "class='ds-numero'>2.650,30</span>" in html  # preco tabular-nums, sem cor de sinal


# ============================================================
# 3. render_macro_cambio_commodities: variação ao vivo colorida (alta/
#    baixa); cotação EM CACHE nunca herda cor de sinal (regressão real já
#    coberta por tests/test_cotacao_em_cache_sinalizada.py - aqui confere
#    também o caso "alta" ao vivo, que o teste antigo não cobria).
# ============================================================

def test_3_cambio_ao_vivo_mostra_cor_de_sinal():
    cot_dolar = {"nome": "DOLAR", "preco": 5.4321, "variacao_pct": 0.65, "erro": None}

    def _fake_cotacao(nome, simbolo):
        return cot_dolar if simbolo.endswith("=X") else {"erro": "sem dado"}

    with patch.object(mt, "_cotacao_cambio", side_effect=_fake_cotacao), \
         patch.object(mt, "obter_cenario_global", return_value=[]), \
         patch.object(mt.st, "caption"):
        html = _render(mt.render_macro_cambio_commodities, _PREFS)
    assert "class='ds-numero alta'>+0,65%</span>" in html
    assert "class='ds-numero'>5,4321</span>" in html


def test_3b_cambio_em_cache_nunca_tem_cor_de_sinal():
    """Regressão (mesmo bug que tests/test_cotacao_em_cache_sinalizada.py
    já cobria via AppTest): cotação em cache não pode ficar colorida como
    se fosse um movimento real desta tentativa."""
    coletado = (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat()
    cot_cache = {
        "nome": "DOLAR", "preco": 5.02, "variacao_pct": 0.2, "erro": None,
        "_fallback_cache": True, "_coletado_em": coletado,
    }

    def _fake_cotacao(nome, simbolo):
        return cot_cache if simbolo.endswith("=X") else {"erro": "sem dado"}

    with patch.object(mt, "_cotacao_cambio", side_effect=_fake_cotacao), \
         patch.object(mt, "obter_cenario_global", return_value=[]), \
         patch.object(mt.st, "caption"):
        html = _render(mt.render_macro_cambio_commodities, _PREFS)
    assert "class='ds-numero alta'" not in html and "class='ds-numero baixa'" not in html
    assert "EM CACHE" in html
    assert "class='ds-numero'>+0,20%</span>" in html  # ainda tabular-nums, so' sem cor


# ============================================================
# 4. render_macro_calendario: destaque "Meta Selic X% a.a." (Copom) usa
#    numero_financeiro_html em vez do "%" concatenado na mão.
# ============================================================

def test_4_copom_destaque_usa_tabular_nums():
    copom = {"valor": 13.75, "vigente_desde": date(2026, 9, 17), "reuniao": 281}
    with patch.object(mt, "_copom_vigente", return_value=copom), \
         patch.object(mt, "obter_focus_ipca", return_value=pd.DataFrame()), \
         patch.object(mt, "obter_focus_selic", return_value=pd.DataFrame()):
        html = _render(mt.render_macro_calendario, _PREFS)
    assert "Meta Selic <span class='ds-numero'>13,75%</span> a.a." in html
