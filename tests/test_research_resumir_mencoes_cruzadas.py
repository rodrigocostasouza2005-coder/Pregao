# -*- coding: utf-8 -*-
"""Integracao: data/research/resumir.py:_gerar_resumo precisa enriquecer
`tickers` (so' metadado da fonte) com qualquer ticker conhecido
encontrado no CORPO do texto original (data/research/classificacao.py)
ANTES de gravar na biblioteca PERMANENTE (store.salvar_premissas) - esta
e' a UNICA janela em que o texto original existe em memoria (nunca
persistido, ver docstring de store.py). Agente C, 2026-11-12, item 2 do
pedido de processamento (mencoes cruzadas que hoje passam batido).

Uso: pytest tests/test_research_resumir_mencoes_cruzadas.py"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.resumir as resumir_mod
from data.research.resumir import obter_resumo

_TEXTO_COM_MENCAO_CRUZADA = (
    "A Vale (VALE3) apresentou resultados solidos no trimestre, com analistas "
    "tambem comentando o desempenho correlato da siderurgica CSNA3 no mesmo periodo."
)


def _mock_dados_estruturados(modelo="modelo-teste"):
    return {
        "modelo": modelo, "preco_alvo": 70.0, "recomendacao": "COMPRA",
        "tipo_documento": "ATUALIZACAO_RESULTADOS", "premissas": ["crescimento de producao"],
        "projecoes": {"receita": "alta de 10%"}, "riscos": ["preco de minerio"],
    }


def test_tickers_do_corpo_sao_unidos_ao_metadado_na_premissa_salva():
    chamadas_premissas = []
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=(_TEXTO_COM_MENCAO_CRUZADA, None)), \
         patch.object(resumir_mod, "resumir_com_groq",
                       return_value=("A Vale reportou resultados solidos no trimestre.", None, _mock_dados_estruturados())), \
         patch.object(resumir_mod.store, "salvar_resumo"), \
         patch.object(resumir_mod.store, "salvar_premissas",
                       side_effect=lambda *a, **k: chamadas_premissas.append(k)), \
         patch.object(resumir_mod.ia_cache, "obter_cliente", return_value=None):
        obter_resumo(
            "https://exemplo.com/vale", "Vale resultados", casa="X", tipo="ACOES",
            tickers=["VALE3"],
        )

    assert len(chamadas_premissas) == 1
    tickers_salvos = chamadas_premissas[0]["tickers"]
    assert tickers_salvos == ["CSNA3", "VALE3"]  # metadado + achado no corpo, ordenado


def test_sem_mencao_cruzada_no_corpo_mantem_so_metadado():
    chamadas_premissas = []
    texto_sem_mencao = "A empresa reportou lucro recorde no trimestre, sem citar nenhum outro papel."
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=(texto_sem_mencao, None)), \
         patch.object(resumir_mod, "resumir_com_groq",
                       return_value=("A empresa reportou lucro recorde.", None, _mock_dados_estruturados())), \
         patch.object(resumir_mod.store, "salvar_resumo"), \
         patch.object(resumir_mod.store, "salvar_premissas",
                       side_effect=lambda *a, **k: chamadas_premissas.append(k)), \
         patch.object(resumir_mod.ia_cache, "obter_cliente", return_value=None):
        obter_resumo(
            "https://exemplo.com/petr", "Petrobras resultados", casa="X", tipo="ACOES",
            tickers=["PETR4"],
        )

    assert len(chamadas_premissas) == 1
    assert chamadas_premissas[0]["tickers"] == ["PETR4"]


def test_nunca_remove_ticker_do_metadado_mesmo_ausente_no_corpo():
    """Enriquecimento e' SO' uniao (metadado ∪ corpo) - nunca some com um
    ticker que o coletor da casa ja' atribuiu, mesmo que o corpo do texto
    nao mencione esse ticker literalmente (ex: titulo generico)."""
    chamadas_premissas = []
    texto_generico = "A companhia divulgou seus resultados trimestrais com cautela do mercado."
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=(texto_generico, None)), \
         patch.object(resumir_mod, "resumir_com_groq",
                       return_value=("Resultados trimestrais divulgados com cautela.", None, _mock_dados_estruturados())), \
         patch.object(resumir_mod.store, "salvar_resumo"), \
         patch.object(resumir_mod.store, "salvar_premissas",
                       side_effect=lambda *a, **k: chamadas_premissas.append(k)), \
         patch.object(resumir_mod.ia_cache, "obter_cliente", return_value=None):
        obter_resumo(
            "https://exemplo.com/weg", "WEG resultados", casa="X", tipo="ACOES",
            tickers=["WEGE3"],
        )

    assert chamadas_premissas[0]["tickers"] == ["WEGE3"]


def test_tipo_sem_dados_estruturados_nunca_chama_salvar_premissas():
    """tipo fora de _TIPOS_COM_DADOS_ESTRUTURADOS (ex: NOTICIAS) nunca
    tenta enriquecer/gravar premissas - mesmo comportamento de antes
    desta mudanca, confirmado explicitamente."""
    chamadas_premissas = []
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=(_TEXTO_COM_MENCAO_CRUZADA, None)), \
         patch.object(resumir_mod, "resumir_com_groq",
                       return_value=("Resumo qualquer.", None, {"modelo": "modelo-teste"})), \
         patch.object(resumir_mod.store, "salvar_resumo"), \
         patch.object(resumir_mod.store, "salvar_premissas",
                       side_effect=lambda *a, **k: chamadas_premissas.append(k)), \
         patch.object(resumir_mod.ia_cache, "obter_cliente", return_value=None):
        obter_resumo(
            "https://exemplo.com/noticia", "Noticia qualquer", casa="X", tipo="NOTICIAS",
            tickers=["VALE3"],
        )

    assert chamadas_premissas == []


# ============================================================
# tipo LIVE (missao noturna 2026-11-12/13, frente LIVES GENIAL): uma
# live (Genial (Lives)/genial_lives.py) nunca passa pelo caminho ACOES
# (nunca tem tipo_documento/premissas/projecoes/riscos/preco_alvo/
# recomendacao extraidos - ver _TIPOS_COM_DADOS_ESTRUTURADOS em
# data/research/resumir.py), entao sem o OR explicito pra tipo=="LIVE"
# as empresas/ativos mencionados numa live nunca entravam na biblioteca
# PERMANENTE, mesmo quando a transcricao citava tickers reais - pedido
# explicito do relatorio de live ("Empresas/ativos mencionados").
# ============================================================

def test_live_com_mencao_no_corpo_grava_premissas_so_com_tickers():
    chamadas_premissas = []
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=(_TEXTO_COM_MENCAO_CRUZADA, None)), \
         patch.object(resumir_mod, "resumir_com_groq",
                       return_value=("A Vale foi comentada no programa.", None, {"modelo": "modelo-teste"})), \
         patch.object(resumir_mod.store, "salvar_resumo"), \
         patch.object(resumir_mod.store, "salvar_premissas",
                       side_effect=lambda *a, **k: chamadas_premissas.append(k)), \
         patch.object(resumir_mod.ia_cache, "obter_cliente", return_value=None):
        obter_resumo(
            "https://youtube.com/watch?v=abc123", "Morning Call 12/11", casa="Genial (Lives)", tipo="LIVE",
            tickers=[],  # genial_lives.py SEMPRE registra [] no metadado - so' o corpo tem os tickers
        )

    assert len(chamadas_premissas) == 1
    chamada = chamadas_premissas[0]
    assert chamada["tickers"] == ["CSNA3", "VALE3"], f"(tickers={chamada['tickers']})"
    assert chamada["tipo_documento"] is None
    assert chamada["premissas"] == [] and chamada["projecoes"] == {} and chamada["riscos"] == []
    assert chamada["preco_alvo"] is None and chamada["recomendacao"] is None


def test_live_sem_nenhum_ticker_identificado_nunca_grava_linha_vazia():
    chamadas_premissas = []
    texto_sem_ticker = "O programa comentou o cenario macro sem citar nenhuma empresa especifica."
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=(texto_sem_ticker, None)), \
         patch.object(resumir_mod, "resumir_com_groq",
                       return_value=("Comentario macro geral.", None, {"modelo": "modelo-teste"})), \
         patch.object(resumir_mod.store, "salvar_resumo"), \
         patch.object(resumir_mod.store, "salvar_premissas",
                       side_effect=lambda *a, **k: chamadas_premissas.append(k)), \
         patch.object(resumir_mod.ia_cache, "obter_cliente", return_value=None):
        obter_resumo(
            "https://youtube.com/watch?v=def456", "Resumo da Manha 12/11", casa="Genial (Lives)", tipo="LIVE",
            tickers=[],
        )

    assert chamadas_premissas == []
