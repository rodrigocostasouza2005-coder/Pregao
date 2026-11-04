# -*- coding: utf-8 -*-
"""Consolidação determinística (data/coordenador_central/consolidacao.py)
- 7 seções sempre presentes, divergência numérica vs qualitativa entre
comparador/memoria_research, confiança categórica (nunca número de
probabilidade), pontos de atenção honestos. Zero rede/Supabase/IA -
tudo em dicts já estruturados (mesmo formato que executor.py produz)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.coordenador_central import consolidacao

_SECOES_OBRIGATORIAS = {
    "resumo_executivo", "visao_especialistas", "evidencias",
    "divergencias", "pontos_atencao", "conclusao", "confianca", "pareceres_analistas", "sinal_comite",
}


def _resultado(especialista_id, disponivel=True, resumo="ok", evidencias=None, motivo=None, dados=None):
    return {
        "id": especialista_id, "execucao_id": "x", "disponivel": disponivel, "resumo": resumo,
        "evidencias": evidencias or [], "motivo_indisponivel": motivo, "duracao_ms": 10,
        "erro_tecnico": None, "dados": dados,
    }


def test_consolidar_dict_vazio_ainda_tem_as_7_secoes():
    consolidado = consolidacao.consolidar({}, ticker="PETR4")
    assert set(consolidado.keys()) == _SECOES_OBRIGATORIAS
    assert consolidado["confianca"]["categoria"] == consolidacao.CONFIANCA_INSUFICIENTE


def test_consolidar_com_resultados_tem_as_7_secoes():
    resultados = {
        "comparador": _resultado("comparador", evidencias=[{"fonte": "Genial", "data": "2026-10-01", "link": "l", "titulo": "t"}]),
        "noticias": _resultado("noticias", disponivel=False, resumo=None, motivo="fonte indisponível"),
    }
    consolidado = consolidacao.consolidar(resultados, ticker="PETR4")
    assert set(consolidado.keys()) == _SECOES_OBRIGATORIAS
    assert "PETR4" in consolidado["resumo_executivo"]
    assert "comparador" in consolidado["visao_especialistas"]
    assert len(consolidado["evidencias"]) == 1
    assert consolidado["evidencias"][0]["especialista"] == "comparador"


def test_erro_tecnico_nunca_aparece_na_visao_especialistas():
    resultados = {"x": {**_resultado("x"), "erro_tecnico": "detalhe tecnico sensivel"}}
    consolidado = consolidacao.consolidar(resultados)
    assert "erro_tecnico" not in consolidado["visao_especialistas"]["x"]


def test_pontos_atencao_lista_especialistas_indisponiveis():
    resultados = {"noticias": _resultado("noticias", disponivel=False, resumo=None, motivo="fonte indisponível")}
    consolidado = consolidacao.consolidar(resultados)
    assert any("noticias" in p and "indisponível" in p for p in consolidado["pontos_atencao"])


def test_pontos_atencao_especialista_pulado_por_encadeamento():
    resultados = {"memoria_research": {**_resultado("memoria_research", resumo="não acionado"), "pulado": True}}
    consolidado = consolidacao.consolidar(resultados)
    assert any("não acionado" in p for p in consolidado["pontos_atencao"])


def test_confianca_alta_com_maioria_de_especialistas_com_evidencia():
    resultados = {
        "a": _resultado("a", evidencias=[{"fonte": "x"}]),
        "b": _resultado("b", evidencias=[{"fonte": "y"}]),
        "c": _resultado("c", evidencias=[{"fonte": "z"}]),
    }
    consolidado = consolidacao.consolidar(resultados)
    assert consolidado["confianca"]["categoria"] == consolidacao.CONFIANCA_ALTA
    # nunca um número de probabilidade na justificativa
    assert "%" not in consolidado["confianca"]["justificativa"]


def test_confianca_insuficiente_quando_nenhum_especialista_tem_evidencia():
    resultados = {"a": _resultado("a", evidencias=[]), "b": _resultado("b", disponivel=False, resumo=None, motivo="indisponível")}
    consolidado = consolidacao.consolidar(resultados)
    assert consolidado["confianca"]["categoria"] == consolidacao.CONFIANCA_INSUFICIENTE


def test_conclusao_rotula_cada_linha_com_tipo_evidencia():
    resultados = {"a": _resultado("a", evidencias=[{"fonte": "x"}]), "b": _resultado("b", evidencias=[{"fonte": "y"}])}
    consolidado = consolidacao.consolidar(resultados)
    assert all(linha.startswith("[") for linha in consolidado["conclusao"])


def test_conclusao_nao_forca_conclusao_quando_dados_insuficientes():
    consolidado = consolidacao.consolidar({})
    assert any("DADO_INSUFICIENTE" in linha or "INSUFICIENTE" in linha for linha in consolidado["conclusao"])


# ============================================================
# Divergência cross-especialista: comparador vs memoria_research
# ============================================================

_TABELA_COMPARADOR = [
    {"casa": "Genial", "recomendacao_original": "COMPRA", "recomendacao_categoria": "OTIMISTA", "preco_alvo": 40.0},
    {"casa": "XP", "recomendacao_original": "VENDA", "recomendacao_categoria": "CAUTELOSO", "preco_alvo": 20.0},
]


def test_divergencia_qualitativa_entre_comparador_e_memoria():
    resultados = {
        "comparador": _resultado("comparador", dados={"tabela_comparativa": _TABELA_COMPARADOR}),
        "memoria_research": _resultado("memoria_research", dados={"resultados": [
            {"casa": "Genial", "recomendacao": "VENDA", "preco_alvo": 40.0},
        ]}),
    }
    consolidado = consolidacao.consolidar(resultados)
    cross = consolidado["divergencias"]["cross_comparador_memoria"]
    assert cross is not None
    divergentes = [d for d in cross["divergencias"] if d["casa"] == "Genial"]
    assert any(d["tipo"] == "qualitativa" for d in divergentes)


def test_divergencia_numerica_entre_comparador_e_memoria():
    resultados = {
        "comparador": _resultado("comparador", dados={"tabela_comparativa": _TABELA_COMPARADOR}),
        "memoria_research": _resultado("memoria_research", dados={"resultados": [
            {"casa": "XP", "recomendacao": "VENDA", "preco_alvo": 25.0},
        ]}),
    }
    consolidado = consolidacao.consolidar(resultados)
    cross = consolidado["divergencias"]["cross_comparador_memoria"]
    divergentes = [d for d in cross["divergencias"] if d["casa"] == "XP"]
    assert any(d["tipo"] == "numerica" and d["campo"] == "preco_alvo" for d in divergentes)


def test_sem_divergencia_quando_dados_concordam():
    resultados = {
        "comparador": _resultado("comparador", dados={"tabela_comparativa": _TABELA_COMPARADOR}),
        "memoria_research": _resultado("memoria_research", dados={"resultados": [
            {"casa": "Genial", "recomendacao": "COMPRA", "preco_alvo": 40.0},
            {"casa": "XP", "recomendacao": "VENDA", "preco_alvo": 20.0},
        ]}),
    }
    consolidado = consolidacao.consolidar(resultados)
    cross = consolidado["divergencias"]["cross_comparador_memoria"]
    assert cross["divergencias"] == []


def test_conclusao_usa_rotulo_de_exibicao_nunca_a_constante_crua():
    """Achado real na validação visual (2026-11-01): a conclusão mostrava
    "[CALCULO_INTERNO]" cru (constante interna de data/radar.py) em vez
    de "CÁLCULO INTERNO" (mesmo rótulo já usado em ui/analises_tab.py) -
    nenhuma constante TIPO_* (com underscore) pode vazar pro texto final."""
    resultados = {"noticias": _resultado("noticias", disponivel=True, evidencias=[{"fonte": "x"}])}
    consolidado = consolidacao.consolidar(resultados, ticker="PETR4")
    texto_conclusao = " ".join(consolidado["conclusao"])
    assert "CALCULO_INTERNO" not in texto_conclusao
    assert "DADO_INSUFICIENTE" not in texto_conclusao
    assert "CÁLCULO INTERNO" in texto_conclusao or "FATO" in texto_conclusao


def test_divergencia_none_quando_falta_um_dos_dois_especialistas():
    resultados = {"comparador": _resultado("comparador", dados={"tabela_comparativa": _TABELA_COMPARADOR})}
    consolidado = consolidacao.consolidar(resultados)
    assert consolidado["divergencias"]["cross_comparador_memoria"] is None


def test_consolidar_monta_pareceres_e_research_com_preco_alvo_atribuido():
    resultados = {
        "analise_ticker": _resultado("analise_ticker", dados={
            "fundamentos": {"preco": 20.0, "roe": 15.0, "margem_liquida": 12.0,
                            "divida_liquida_ebitda": 1.0, "fluxo_caixa_livre": 100.0, "pl": 12.0},
            "fundamentos_historicos": {"disponivel": True,
                "receita_liquida": {"yoy_pct_serie": [8.0, 12.0]}},
            "comparativo_setorial": {"pl_mediana": 18.0},
            "cobertura_research": {"cobertura": []},
        }),
        "comparador": _resultado("comparador", dados={
            "dispersao_precos_alvo": {"mediana": 25.0, "minimo": 22.0, "maximo": 28.0,
                                      "n_casas_com_preco_alvo": 2},
            "tabela_comparativa": [
                {"casa": "BTG Pactual", "recomendacao_categoria": "OTIMISTA",
                 "preco_alvo": 25.0, "data_publicacao": "2026-10-20",
                 "titulo": "Relatório teste", "link": "https://example.com/research"},
                {"casa": "XP Investimentos", "recomendacao_categoria": "CAUTELOSO",
                 "preco_alvo": 18.0},
                {"casa": "Genial Analisa", "recomendacao_categoria": "CAUTELOSO",
                 "preco_alvo": 10.0},
            ],
        }),
        "memoria_research": _resultado("memoria_research", dados={"resultados": [
            {"casa": "BTG Pactual", "preco_alvo": 25.0, "premissas": ["ganho de market share"],
             "riscos": ["câmbio volátil"], "projecoes": {"receita": "12% a.a."},
             "titulo": "Iniciação de cobertura", "link": "https://example.com/btg"},
            {"casa": "Monte Bravo", "preco_alvo": 27.5, "premissas": ["expansão de capacidade"],
             "riscos": ["execução do capex"], "projecoes": {"receita": "10% a.a."},
             "titulo": "Atualização", "link": "https://example.com/mb"},
        ]}),
        "resultados_corporativos": _resultado("resultados_corporativos", dados={
            "disponivel": True, "periodo_label": "3T2026",
            "metricas": {
                "receita_liquida": {"yoy_variacao_pct": 12.0},
                "ebit": {"yoy_variacao_pct": -3.0},
                "lucro_liquido_consolidado": {"yoy_variacao_pct": 8.0},
            },
            "margem_bruta_pct": 25.0, "margem_bruta_yoy_anterior_pct": 23.0,
            "balanco_fluxo_caixa": {"roic_pct": 4.0}, "fontes": [], "limitacoes": [],
        }),
    }
    consolidado = consolidacao.consolidar(resultados, ticker="PETR4")
    pareceres = consolidado["pareceres_analistas"]
    assert len(pareceres["analistas"]) == 3
    assert pareceres["preco_alvo_consenso"]["mediana"] == 26.25
    assert pareceres["preco_alvo_consenso"]["upside_pct"] == 31.25
    assert [c["casa"] for c in pareceres["casas_research"]] == ["BTG Pactual", "Monte Bravo"]
    assert pareceres["casas_research"][0]["tese"] == ["ganho de market share"]
    assert pareceres["casas_research"][0]["contras"] == ["câmbio volátil"]
    assert pareceres["casas_research"][0]["preco_alvo"] == 25.0
    assert pareceres["analistas"][2]["preco_alvo"] == 30.0
    assert pareceres["analistas"][2]["upside_pct"] == 50.0
    assert pareceres["analistas"][2]["preco_alvo_rotulo"].startswith("Estimativa mecânica")
    assert [x["recomendacao"] for x in pareceres["analistas"]] == ["COMPRA", "COMPRA", "COMPRA"]
    assert "Leitura construtiva" in pareceres["analistas"][0]["tese"]
    assert "Leitura construtiva" in pareceres["analistas"][1]["tese"]
    assert consolidado["sinal_comite"]["sinal"] in {"COMPRA", "VENDA", "NEUTRO", "INSUFICIENTE"}
    assert consolidado["sinal_comite"]["preco_alvo_modelo"] == 30.0
    assert consolidado["sinal_comite"]["preco_alvo_consenso"] == 26.25


def test_consolidar_sem_research_nao_inventa_preco_alvo():
    consolidado = consolidacao.consolidar({})
    pareceres = consolidado["pareceres_analistas"]
    assert pareceres["preco_alvo_consenso"]["mediana"] is None
    assert all(a["preco_alvo"] is None for a in pareceres["analistas"])
    assert pareceres["casas_research"] == []
