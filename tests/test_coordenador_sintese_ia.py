# -*- coding: utf-8 -*-
"""data/coordenador_central/sintese_ia.py:sintetizar_leitura_comite -
camada híbrida OPT-IN (missão "PREGÃO 2.1", 2026-11-13). Cobre: menos de
2 pareceres com recomendação -> zero chamada de IA (nada pra confrontar);
sem GROQ_API_KEY -> zero chamada de rede; sucesso filtra
'especialistas_citados' pra só ids reais (nunca aceita um id inventado);
resposta malformada degrada sem lançar excecao; a IA NUNCA recalcula a
categoria de confiança já decidida (só a repassa no payload)."""
import json
from unittest.mock import patch

from data.coordenador_central import sintese_ia as si

_CONSOLIDADO_DIVERGENTE = {
    "ticker": "PETR4",
    "pareceres_analistas": {
        "analistas": [
            {"id": "market_researcher", "nome": "Market Researcher", "recomendacao": "COMPRA",
             "preco_alvo": None, "preco_atual": 38.0, "tese": "ROE forte e dívida controlada.",
             "pros": ["ROE de 18%"], "contras": []},
            {"id": "valuation_comparables", "nome": "Valuation", "recomendacao": "VENDA",
             "preco_alvo": 32.0, "preco_atual": 38.0, "tese": "P/L acima da mediana setorial.",
             "pros": [], "contras": ["P/L 1.6x a mediana do setor"]},
        ],
    },
    "divergencias": {"entre_analistas_comite": {"divergente": True, "resumo": "market_researcher=COMPRA; valuation_comparables=VENDA"}},
    "confianca": {"categoria": "MEDIA", "justificativa": "2 de 2 especialistas trouxeram evidência real."},
    "sinal_comite": {"preco_atual": 38.0, "preco_alvo_consenso": 34.0, "preco_alvo_modelo": None, "upside_modelo_pct": None},
    "pontos_atencao": [],
}

_JSON_VALIDO = json.dumps({
    "leitura": "O Market Researcher recomenda COMPRA apoiado no ROE forte e dívida controlada, enquanto o "
               "Valuation Reviewer recomenda VENDA por o P/L estar 1.6x acima da mediana setorial - a "
               "divergência vem de pesos diferentes dados a fundamentos versus múltiplo relativo.",
    "fator_decisivo": "P/L 1.6x a mediana do setor (valuation_comparables) contra ROE de 18% (market_researcher).",
    "especialistas_citados": ["market_researcher", "valuation_comparables"],
})


def _bypass_cache():
    return patch.object(si.ia_cache, "obter_resumo_com_cache", side_effect=lambda chave, link, origem, gerar_fn: gerar_fn())


def test_menos_de_2_pareceres_nao_chama_ia():
    consolidado_1_parecer = {
        "ticker": "PETR4",
        "pareceres_analistas": {"analistas": [{"id": "market_researcher", "recomendacao": "COMPRA"}]},
        "divergencias": {}, "confianca": {"categoria": "BAIXA"}, "sinal_comite": {},
    }
    with patch.object(si, "_chamar_groq_coord") as groq_mock:
        resultado = si.sintetizar_leitura_comite(consolidado_1_parecer)
    groq_mock.assert_not_called()
    assert resultado["disponivel"] is False


def test_sem_groq_api_key_nao_chama_rede():
    with patch.object(si.config, "obter_credenciais_groq", return_value=(None, "modelo-principal")), \
         patch.object(si, "_chamar_groq_coord") as groq_mock, \
         patch.object(si.ia_hibrida_telemetria, "registrar_execucao") as telemetria_mock, \
         _bypass_cache():
        resultado = si.sintetizar_leitura_comite(_CONSOLIDADO_DIVERGENTE)
    groq_mock.assert_not_called()
    assert resultado["disponivel"] is False
    assert "GROQ_API_KEY" in resultado["motivo"]
    assert telemetria_mock.call_args.kwargs["sucesso"] is False


def test_sucesso_explica_divergencia_citando_especialistas_reais():
    with patch.object(si.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(si.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(si, "_chamar_groq_coord", return_value=(_JSON_VALIDO, None)), \
         patch.object(si.ia_hibrida_telemetria, "registrar_execucao") as telemetria_mock, \
         _bypass_cache():
        resultado = si.sintetizar_leitura_comite(_CONSOLIDADO_DIVERGENTE)

    assert resultado["disponivel"] is True
    assert resultado["modelo"] == "modelo-principal"
    assert set(resultado["especialistas_citados"]) == {"market_researcher", "valuation_comparables"}
    assert "ROE" in resultado["leitura"]
    telemetria_mock.assert_called_once()
    kwargs = telemetria_mock.call_args.kwargs
    assert kwargs["sucesso"] is True
    assert kwargs["ticker"] == "PETR4"
    assert kwargs["origem"] == "coordenador_sintese_divergencia"
    assert {f["especialista_id"] for f in kwargs["fontes"]} == {"market_researcher", "valuation_comparables"}


def test_especialista_citado_inventado_e_descartado():
    resposta_com_id_inventado = json.dumps({
        "leitura": "Leitura válida.", "fator_decisivo": "",
        "especialistas_citados": ["market_researcher", "especialista_que_nao_existe"],
    })
    with patch.object(si.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(si.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(si, "_chamar_groq_coord", return_value=(resposta_com_id_inventado, None)), \
         patch.object(si.ia_hibrida_telemetria, "registrar_execucao"), \
         _bypass_cache():
        resultado = si.sintetizar_leitura_comite(_CONSOLIDADO_DIVERGENTE)
    assert resultado["disponivel"] is True
    assert resultado["especialistas_citados"] == ["market_researcher"]


def test_resposta_malformada_nunca_lanca_excecao():
    with patch.object(si.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(si.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(si, "_chamar_groq_coord", return_value=("não é json válido", None)), \
         patch.object(si.ia_hibrida_telemetria, "registrar_execucao") as telemetria_mock, \
         _bypass_cache():
        resultado = si.sintetizar_leitura_comite(_CONSOLIDADO_DIVERGENTE)
    assert resultado["disponivel"] is False
    assert telemetria_mock.call_args.kwargs["sucesso"] is False


def test_payload_repassa_confianca_sem_recalcular():
    """A IA recebe a categoria de confiança JÁ DECIDIDA - este módulo
    nunca a recalcula, só a inclui no payload pra IA explicar o
    raciocínio por trás dela."""
    payload = si._montar_payload_sintese_comite(_CONSOLIDADO_DIVERGENTE)
    assert payload["confianca_ja_decidida"]["categoria"] == "MEDIA"
    assert payload["numeros_ja_calculados"]["preco_alvo_consenso"] == 34.0
