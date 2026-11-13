# -*- coding: utf-8 -*-
"""data/market_researcher.py:sintese_qualitativa_research - camada
híbrida OPT-IN (missão "PREGÃO 2.1", 2026-11-13). Cobre: nenhuma casa
cobrindo -> zero chamada de IA (regra inegociável da missão); sem
GROQ_API_KEY -> zero chamada de rede, telemetria registra a falha;
sucesso com validação de 'casas_citadas' (rejeita casa inventada que não
esteja no payload real); resposta malformada degrada sem lançar
excecao."""
import json
from unittest.mock import patch

from data import market_researcher as mr

_COMPARACAO_2_CASAS = {
    "disponivel": True, "ticker": "WEGE3", "casas": ["Genial Analisa", "XP Investimentos"],
    "estado_atual_por_casa": {
        "Genial Analisa": {
            "categoria": "COMPRA",
            "atual": {
                "recomendacao": "COMPRA", "preco_alvo": 55.0, "data_publicacao": "2026-11-01",
                "link": "https://genial.example/wege3", "titulo": "WEGE3: tese de compra",
                "premissas": ["Crescimento de receita em motores elétricos", "Margem EBITDA estável"],
                "riscos": ["Câmbio desfavorável pode pressionar exportações"],
                "projecoes": {"receita": "crescimento de 10% a.a."},
            },
        },
        "XP Investimentos": {
            "categoria": "NEUTRO",
            "atual": {
                "recomendacao": "NEUTRO", "preco_alvo": 48.0, "data_publicacao": "2026-10-20",
                "link": "https://xp.example/wege3", "titulo": "WEGE3: valuation esticado",
                "premissas": ["Múltiplo já reflete o crescimento esperado"],
                "riscos": ["Concorrência em geração distribuída de energia"],
                "projecoes": {},
            },
        },
    },
    "dispersao_precos_alvo": {"amostra_insuficiente": False},
    "divergencia_recomendacao": {"divergente": True},
    "divergencia_premissas": {"premissas_divergentes": []},
}

_JSON_VALIDO = json.dumps({
    "sintese": "As casas monitoradas divergem sobre WEGE3: a Genial Analisa vê potencial de crescimento em "
               "motores elétricos, enquanto a XP Investimentos considera o valuation já esticado.",
    "convergencias": [],
    "divergencias": ["Genial Analisa recomenda COMPRA citando crescimento; XP Investimentos está NEUTRO por valuation esticado."],
    "pontos_atencao": ["Câmbio desfavorável (Genial Analisa)", "Concorrência em geração distribuída (XP Investimentos)"],
    "casas_citadas": ["Genial Analisa", "XP Investimentos"],
})


def _bypass_cache():
    """ia_cache.obter_resumo_com_cache chamaria o Supabase de verdade -
    pros testes, chama gerar_fn() direto (mesmo papel do cache MISS sem
    Supabase configurado, caminho já coberto por tests/test_ia_cache.py)."""
    return patch.object(mr.ia_cache, "obter_resumo_com_cache", side_effect=lambda chave, link, origem, gerar_fn: gerar_fn())


def test_sem_nenhuma_casa_cobrindo_nao_chama_ia():
    comparacao_vazia = {"disponivel": True, "ticker": "ABCD3", "casas": [], "motivo": "sem publicações"}
    with patch("data.research.comparador.comparar_ticker", return_value=comparacao_vazia), \
         patch.object(mr, "_chamar_groq_mr") as groq_mock, \
         patch.object(mr.ia_hibrida_telemetria, "registrar_execucao") as telemetria_mock:
        resultado = mr.sintese_qualitativa_research("ABCD3")
    groq_mock.assert_not_called()
    telemetria_mock.assert_not_called()
    assert resultado["disponivel"] is False
    assert "sem publicações" in resultado["motivo"]


def test_research_indisponivel_nao_chama_ia():
    with patch("data.research.comparador.comparar_ticker", return_value={"disponivel": False, "motivo": "banco indisponivel"}), \
         patch.object(mr, "_chamar_groq_mr") as groq_mock:
        resultado = mr.sintese_qualitativa_research("WEGE3")
    groq_mock.assert_not_called()
    assert resultado["disponivel"] is False


def test_sem_groq_api_key_nao_chama_rede_e_registra_falha_na_telemetria():
    with patch("data.research.comparador.comparar_ticker", return_value=_COMPARACAO_2_CASAS), \
         patch.object(mr.config, "obter_credenciais_groq", return_value=(None, "modelo-principal")), \
         patch.object(mr, "_chamar_groq_mr") as groq_mock, \
         patch.object(mr.ia_hibrida_telemetria, "registrar_execucao") as telemetria_mock, \
         _bypass_cache():
        resultado = mr.sintese_qualitativa_research("WEGE3")
    groq_mock.assert_not_called()
    assert resultado["disponivel"] is False
    assert "GROQ_API_KEY" in resultado["motivo"]
    telemetria_mock.assert_called_once()
    assert telemetria_mock.call_args.kwargs["sucesso"] is False
    assert telemetria_mock.call_args.kwargs["origem"] == "market_researcher_sintese_research"


def test_sucesso_sintetiza_e_registra_telemetria_com_fontes_reais():
    with patch("data.research.comparador.comparar_ticker", return_value=_COMPARACAO_2_CASAS), \
         patch.object(mr.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(mr.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(mr, "_chamar_groq_mr", return_value=(_JSON_VALIDO, None)), \
         patch.object(mr.ia_hibrida_telemetria, "registrar_execucao") as telemetria_mock, \
         _bypass_cache():
        resultado = mr.sintese_qualitativa_research("WEGE3")

    assert resultado["disponivel"] is True
    assert resultado["modelo"] == "modelo-principal"
    assert resultado["casas_consideradas"] == ["Genial Analisa", "XP Investimentos"]
    assert "Genial Analisa" in resultado["sintese"]
    assert len(resultado["divergencias"]) == 1
    telemetria_mock.assert_called_once()
    kwargs = telemetria_mock.call_args.kwargs
    assert kwargs["sucesso"] is True
    assert kwargs["modelo"] == "modelo-principal"
    assert kwargs["ticker"] == "WEGE3"
    assert len(kwargs["fontes"]) == 2
    assert all(f["casa"] in {"Genial Analisa", "XP Investimentos"} for f in kwargs["fontes"])


def test_casa_citada_inventada_pela_ia_e_descartada():
    resposta_com_casa_inventada = json.dumps({
        "sintese": "Síntese válida.",
        "convergencias": [], "divergencias": [], "pontos_atencao": [],
        "casas_citadas": ["Genial Analisa", "Casa Que Não Existe"],
    })
    with patch("data.research.comparador.comparar_ticker", return_value=_COMPARACAO_2_CASAS), \
         patch.object(mr.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(mr.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(mr, "_chamar_groq_mr", return_value=(resposta_com_casa_inventada, None)), \
         patch.object(mr.ia_hibrida_telemetria, "registrar_execucao"), \
         _bypass_cache():
        resultado = mr.sintese_qualitativa_research("WEGE3")
    assert resultado["disponivel"] is True
    assert resultado["casas_citadas"] == ["Genial Analisa"]  # casa inventada nunca sobrevive à validação


def test_resposta_malformada_nunca_lanca_excecao():
    with patch("data.research.comparador.comparar_ticker", return_value=_COMPARACAO_2_CASAS), \
         patch.object(mr.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(mr.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(mr, "_chamar_groq_mr", return_value=("isto não é json", None)), \
         patch.object(mr.ia_hibrida_telemetria, "registrar_execucao") as telemetria_mock, \
         _bypass_cache():
        resultado = mr.sintese_qualitativa_research("WEGE3")
    assert resultado["disponivel"] is False
    assert "formato inesperado" in resultado["motivo"]
    assert telemetria_mock.call_args.kwargs["sucesso"] is False


def test_comparar_ticker_lanca_excecao_nunca_propaga():
    with patch("data.research.comparador.comparar_ticker", side_effect=RuntimeError("falha de rede")):
        resultado = mr.sintese_qualitativa_research("WEGE3")
    assert resultado["disponivel"] is False
