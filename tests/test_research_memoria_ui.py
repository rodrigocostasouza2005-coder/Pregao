# -*- coding: utf-8 -*-
"""Regressão da subaba RESEARCH › Memória de Research
(ui/research_tab.py:render_memoria_research, Fase C - RAG, 2026-10-30).
Bare mode (sem ScriptRunContext) - render_memoria_research é @st.fragment,
precisa de .__wrapped__ (mesmo padrão de
tests/test_research_casas_analise_ui.py). Testa a renderização pura
(_opcoes_filtro_memoria/_badge_confianca_html/_card_resultado_memoria) e a
integração buscar()+render sem exceção em nenhum cenário (banco
indisponível, credencial ausente, zero resultado, resultado normal)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.research_tab as research_tab_mod

_PREFS = {"formato_numerico": "BR"}


# ============================================================
# núcleo puro
# ============================================================

def test_opcoes_filtro_memoria_ordena_e_dedup():
    premissas = [
        {"casa": "XP Investimentos", "tipo_documento": "VALUATION", "tickers": ["PETR4", "VALE3"]},
        {"casa": "Genial Analisa", "tipo_documento": "VALUATION", "tickers": ["PETR4"]},
        {"casa": None, "tipo_documento": None, "tickers": []},
    ]
    opcoes = research_tab_mod._opcoes_filtro_memoria(premissas)
    assert opcoes["casas"] == ["Genial Analisa", "XP Investimentos"]
    assert opcoes["tipos"] == ["VALUATION"]
    assert opcoes["tickers"] == ["PETR4", "VALE3"]


def test_badge_confianca_html_cobre_os_4_niveis():
    for nivel in ("ALTA", "MEDIA", "BAIXA", "SEM_EVIDENCIA"):
        html_badge = research_tab_mod._badge_confianca_html(nivel)
        assert "casas-badge" in html_badge


def test_card_resultado_memoria_traz_fonte_data_casa_e_link():
    item = {
        "link": "https://genial.com.br/r/1", "casa": "Genial Analisa",
        "titulo": "WEGE3 - Iniciação de cobertura", "data_publicacao": "2026-10-20",
        "tickers": ["WEGE3"], "tipo_documento": "INICIACAO_COBERTURA",
        "premissas": ["ganho de market share"], "projecoes": {"receita": "12% a.a."},
        "recomendacao": "COMPRA", "preco_alvo": 55.0, "origem_match": "ambos",
    }
    html_card = research_tab_mod._card_resultado_memoria(item, "BR")
    assert "https://genial.com.br/r/1" in html_card
    assert "Genial Analisa" in html_card
    assert "20/10/2026" in html_card
    assert "WEGE3" in html_card
    assert "ganho de market share" in html_card
    assert "COMPRA" in html_card
    assert "55,00" in html_card
    assert "semântica + palavra-chave" in html_card


def test_card_resultado_memoria_sem_recomendacao_nem_projecoes_nao_quebra():
    item = {"link": None, "casa": "Casa X", "titulo": None, "data_publicacao": None,
            "tickers": [], "tipo_documento": None, "premissas": [], "projecoes": {},
            "recomendacao": None, "preco_alvo": None, "origem_match": "lexical"}
    html_card = research_tab_mod._card_resultado_memoria(item, "BR")
    assert "sem título" in html_card


# ============================================================
# integração: render completo (bare mode) nunca lança exceção
# ============================================================

def _capturar_render(resultado_buscar, premissas_opcoes=None, api_key="chave", prefs=None):
    blocos = []

    def _markdown(texto, **_k):
        blocos.append(texto)

    def _texto_input(label, **_k):
        return ""

    def _selectbox(label, opcoes, **_k):
        return opcoes[0]

    def _pills(label, opcoes, **_k):
        return _k.get("default")

    with patch.object(research_tab_mod, "_premissas_para_opcoes_cacheado", return_value=premissas_opcoes or []), \
         patch.object(research_tab_mod.config, "obter_credenciais_gemini", return_value=(api_key, "modelo")), \
         patch.object(research_tab_mod.embeddings, "buscar", return_value=resultado_buscar), \
         patch.object(research_tab_mod.st, "markdown", side_effect=_markdown), \
         patch.object(research_tab_mod.st, "warning", side_effect=lambda t, **_k: blocos.append(f"WARNING:{t}")), \
         patch.object(research_tab_mod.st, "info", side_effect=lambda t, **_k: blocos.append(f"INFO:{t}")), \
         patch.object(research_tab_mod.st, "text_input", side_effect=_texto_input), \
         patch.object(research_tab_mod.st, "selectbox", side_effect=_selectbox), \
         patch.object(research_tab_mod.st, "pills", side_effect=_pills), \
         patch.object(research_tab_mod.st, "columns", return_value=(MagicMock(), MagicMock(), MagicMock())), \
         patch.object(research_tab_mod.st, "container") as container_mock:
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        for col in [research_tab_mod.st.columns(3)]:
            pass
        research_tab_mod.render_memoria_research.__wrapped__(prefs or _PREFS)
    return "\n".join(blocos)


def test_render_nunca_lanca_excecao_banco_indisponivel():
    resultado = {"resultados": [], "confianca": "SEM_EVIDENCIA", "aviso": "banco de research indisponivel no momento"}
    texto = _capturar_render(resultado)
    assert "WARNING:banco de research indisponivel no momento" in texto


def test_render_nunca_lanca_excecao_credencial_ausente():
    resultado = {"resultados": [], "confianca": "SEM_EVIDENCIA", "aviso": None}
    texto = _capturar_render(resultado, api_key=None)
    assert "GEMINI_API_KEY" in texto


def test_render_nunca_lanca_excecao_zero_resultado():
    resultado = {"resultados": [], "confianca": "SEM_EVIDENCIA", "aviso": None}
    texto = _capturar_render(resultado)
    assert "INFO:Nenhuma evidência encontrada" in texto


def test_render_resultado_normal_mostra_cards():
    resultado = {
        "confianca": "ALTA", "aviso": None,
        "resultados": [{
            "link": "https://genial.com.br/r/1", "casa": "Genial Analisa", "titulo": "WEGE3",
            "data_publicacao": "2026-10-20", "tickers": ["WEGE3"], "tipo_documento": "INICIACAO_COBERTURA",
            "premissas": ["ganho de market share"], "projecoes": {}, "recomendacao": "COMPRA",
            "preco_alvo": 55.0, "origem_match": "ambos",
        }],
    }
    texto = _capturar_render(resultado)
    assert "WEGE3" in texto
    assert "Genial Analisa" in texto
    assert "CONFIANÇA ALTA" in texto


def test_render_nenhuma_excecao_mesmo_com_premissas_opcoes_vazias():
    resultado = {"resultados": [], "confianca": "SEM_EVIDENCIA", "aviso": None}
    assert _capturar_render(resultado, premissas_opcoes=[]) is not None
