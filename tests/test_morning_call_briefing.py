# -*- coding: utf-8 -*-
"""data/morning_call_briefing.py: alertas de confiabilidade (leitura
filtrada do painel SAÚDE DOS DADOS já existente) e detecção de tickers
novos desde a última edição publicada (comparação textual simples) -
ver missão "Morning Call: briefing profissional"."""
from unittest.mock import patch

from data import morning_call_briefing as mcb


def _item_saude(nome="NEWS (Brasil)", categoria="Noticias", alerta=True, rotulo="Fonte indisponivel"):
    return {"nome": nome, "categoria": categoria, "alerta": alerta, "rotulo_estado": rotulo}


# ---------------------------------------------------------------------
# alertas_confiabilidade
# ---------------------------------------------------------------------

def test_alertas_confiabilidade_filtra_por_categoria_relevante():
    painel = [
        _item_saude(categoria="Noticias", alerta=True),
        _item_saude(nome="EQUITY (fundamentos)", categoria="Fundamentos", alerta=True),
        _item_saude(nome="DRE (SEC)", categoria="Earnings", alerta=True),
    ]
    with patch("data.saude_dados.obter_painel_saude", return_value=painel):
        resultado = mcb.alertas_confiabilidade()
    assert len(resultado) == 1
    assert resultado[0]["categoria"] == "Noticias"


def test_alertas_confiabilidade_ignora_item_sem_alerta():
    painel = [_item_saude(categoria="Macro", alerta=False)]
    with patch("data.saude_dados.obter_painel_saude", return_value=painel):
        assert mcb.alertas_confiabilidade() == []


def test_alertas_confiabilidade_painel_vazio_nao_e_erro():
    with patch("data.saude_dados.obter_painel_saude", return_value=[]):
        assert mcb.alertas_confiabilidade() == []


def test_alertas_confiabilidade_falha_na_leitura_devolve_lista_vazia_sem_lancar():
    with patch("data.saude_dados.obter_painel_saude", side_effect=RuntimeError("Supabase fora do ar")):
        assert mcb.alertas_confiabilidade() == []


def test_alertas_confiabilidade_cobre_todas_as_categorias_relevantes():
    painel = [_item_saude(categoria=c, alerta=True) for c in
              ("Noticias", "Macro", "CVM", "Research", "Calendario", "Radar", "Morning Call")]
    with patch("data.saude_dados.obter_painel_saude", return_value=painel):
        resultado = mcb.alertas_confiabilidade()
    assert len(resultado) == 7


# ---------------------------------------------------------------------
# tickers_novos
# ---------------------------------------------------------------------

def test_tickers_novos_identifica_ticker_ausente_do_texto_anterior():
    edicao = {"market_makers": {"tickers": ("PETR4", "VALE3")}}
    ultima = {"conteudo": "Resumo de ontem. PETR4 subiu 2%. Nenhuma menção a outros papéis."}
    assert mcb.tickers_novos(edicao, ultima) == ["VALE3"]


def test_tickers_novos_vazio_quando_todos_ja_apareciam():
    edicao = {"market_makers": {"tickers": ("PETR4",)}}
    ultima = {"conteudo": "PETR4 caiu ontem."}
    assert mcb.tickers_novos(edicao, ultima) == []


def test_tickers_novos_sem_edicao_anterior_nao_declara_novidade():
    edicao = {"market_makers": {"tickers": ("PETR4",)}}
    assert mcb.tickers_novos(edicao, None) == []
    assert mcb.tickers_novos(edicao, {"conteudo": ""}) == []


def test_tickers_novos_sem_market_makers_nesta_edicao_devolve_vazio():
    assert mcb.tickers_novos({"market_makers": None}, {"conteudo": "qualquer coisa"}) == []
    assert mcb.tickers_novos({}, {"conteudo": "qualquer coisa"}) == []


def test_tickers_novos_nunca_casa_substring_de_outro_ticker():
    """PETR4 não pode "casar" dentro de PETR4F ou coisa parecida - o
    \\b nas duas pontas garante que só o ticker exato conta como já
    citado."""
    edicao = {"market_makers": {"tickers": ("PETR4",)}}
    ultima = {"conteudo": "O papel PETR4F (um ticker diferente) subiu."}
    assert mcb.tickers_novos(edicao, ultima) == ["PETR4"]
