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
    "ticker", "resumo_executivo", "visao_especialistas", "evidencias",
    "divergencias", "pontos_atencao", "conclusao", "confianca", "pareceres_analistas", "sinal_comite",
}


def _resultado(especialista_id, disponivel=True, resumo="ok", evidencias=None, motivo=None, dados=None):
    return {
        "id": especialista_id, "execucao_id": "x", "disponivel": disponivel, "resumo": resumo,
        "evidencias": evidencias or [], "motivo_indisponivel": motivo, "duracao_ms": 10,
        "erro_tecnico": None, "dados": dados,
    }


def test_consolidar_dict_vazio_ainda_tem_as_8_secoes():
    consolidado = consolidacao.consolidar({}, ticker="PETR4")
    assert set(consolidado.keys()) == _SECOES_OBRIGATORIAS
    assert consolidado["confianca"]["categoria"] == consolidacao.CONFIANCA_INSUFICIENTE
    assert consolidado["ticker"] == "PETR4"


def test_consolidar_com_resultados_tem_as_8_secoes():
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
                "receita_liquida": {"yoy_pct_serie": [8.0, 12.0]},
                "roic_pct": {"serie": [3.5]}},
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
    assert len(pareceres["analistas"]) == 5
    ids_pareceres = {item["id"] for item in pareceres["analistas"]}
    assert {"model_builder", "valuation_reviewer", "valuation_comparables"} <= ids_pareceres
    assert pareceres["preco_alvo_consenso"]["mediana"] == 26.25
    assert pareceres["preco_alvo_consenso"]["upside_pct"] == 31.25
    assert [c["casa"] for c in pareceres["casas_research"]] == ["BTG Pactual", "Monte Bravo"]
    assert pareceres["casas_research"][0]["tese"] == ["ganho de market share"]
    assert pareceres["casas_research"][0]["contras"] == ["câmbio volátil"]
    assert pareceres["casas_research"][0]["preco_alvo"] == 25.0
    assert pareceres["analistas"][2]["preco_alvo"] == 30.0
    assert pareceres["analistas"][2]["upside_pct"] == 50.0
    assert pareceres["analistas"][2]["preco_alvo_rotulo"].startswith("Estimativa mecânica")
    assert [x["recomendacao"] for x in pareceres["analistas"][:3]] == ["COMPRA", "COMPRA", "COMPRA"]
    assert next(x for x in pareceres["analistas"] if x["id"] == "model_builder")["recomendacao"] == "INSUFICIENTE"
    assert next(x for x in pareceres["analistas"] if x["id"] == "valuation_reviewer")["recomendacao"] == "INSUFICIENTE"
    assert "Leitura construtiva" in pareceres["analistas"][0]["tese"]
    assert "Leitura construtiva" in pareceres["analistas"][1]["tese"]
    assert any("ROIC trimestral positivo" in x for x in pareceres["analistas"][0]["pros"])
    assert consolidado["sinal_comite"]["sinal"] in {"COMPRA", "VENDA", "NEUTRO", "INSUFICIENTE"}
    assert consolidado["sinal_comite"]["preco_alvo_modelo"] == 30.0
    assert consolidado["sinal_comite"]["preco_alvo_consenso"] == 26.25


def test_consolidar_sem_research_nao_inventa_preco_alvo():
    consolidado = consolidacao.consolidar({})
    pareceres = consolidado["pareceres_analistas"]
    assert pareceres["preco_alvo_consenso"]["mediana"] is None
    assert all(a["preco_alvo"] is None for a in pareceres["analistas"])
    assert pareceres["casas_research"] == []


def test_especialista_pulado_nao_reduz_confianca_nem_conta_como_acionado():
    resultados = {
        "comparador": _resultado("comparador", evidencias=[{"fonte": "casa"}]),
        "noticias": _resultado("noticias", disponivel=False, resumo=None, motivo="fonte indisponível"),
        "memoria_research": {**_resultado("memoria_research", resumo="não necessário"), "pulado": True},
    }
    consolidado = consolidacao.consolidar(resultados, ticker="WEGE3")
    assert consolidado["confianca"]["categoria"] == consolidacao.CONFIANCA_MEDIA
    assert "1 de 2 especialista(s) acionado(s)" in consolidado["resumo_executivo"]
    assert any("1 de 2 especialista(s) acionado(s)" in linha for linha in consolidado["conclusao"])


def test_especialista_pulado_sozinho_nao_cria_confianca():
    resultados = {
        "memoria_research": {**_resultado("memoria_research", resumo="não necessário"), "pulado": True},
    }
    consolidado = consolidacao.consolidar(resultados)
    assert consolidado["confianca"]["categoria"] == consolidacao.CONFIANCA_INSUFICIENTE
    assert "0 especialista(s) acionado(s)" in consolidado["resumo_executivo"]


def test_model_builder_e_valuation_reviewer_aparecem_com_pareceres_distintos():
    resultados = {
        "model_builder": _resultado("model_builder", dados={
            "disponivel": True, "metodo": "DCF de 5 anos",
            "fonte_premissas": "CVM + premissas manuais",
            "cenarios": {"pessimista": {"preco_alvo": 20.0}, "base": {"preco_alvo": 30.0}, "otimista": {"preco_alvo": 40.0}},
            "sensibilidade": {"disponivel": True, "linhas": []},
        }),
        "valuation_reviewer": _resultado("valuation_reviewer", dados={
            "disponivel": True, "aprovado": True,
            "precos_alvo_revisados": {"pessimista": 20.0, "base": 30.0, "otimista": 40.0},
            "achados": [], "limitacoes": [],
        }),
    }
    consolidado = consolidacao.consolidar(resultados, ticker="PETR4")
    pareceres = consolidado["pareceres_analistas"]["analistas"]
    por_id = {item["id"]: item for item in pareceres}
    assert "model_builder" in por_id
    assert "valuation_reviewer" in por_id
    assert por_id["model_builder"]["cenarios"]["base"]["preco_alvo"] == 30.0
    assert por_id["valuation_reviewer"]["recomendacao"] == "APROVADO"


def test_valuation_reviewer_expoe_dcf_e_achados_reais_para_a_ui():
    """Achado real (auditoria 2026-11-11): ui/coordenador_tab.py:
    _render_parecer_valuation_reviewer sempre lê analista["dcf"], mas
    montar_pareceres nunca preenchia essa chave para o parecer do
    Valuation Reviewer - a aba sempre caía no ramo "DCF indisponível",
    mesmo quando o Model Builder tinha DCF completo, e os achados reais
    da auditoria (revisar_valuation) eram descartados sem nunca aparecer
    na UI. Este teste fixa o contrato: dcf.cenarios/premissas reaproveitam
    o Model Builder, e achados de auditoria viram pontos contrários."""
    resultados = {
        "model_builder": _resultado("model_builder", dados={
            "disponivel": True, "metodo": "DCF de 5 anos",
            "fonte_premissas": "CVM + premissas manuais", "data_base": "2026-09-30",
            "moeda": "R$",
            "cenarios": {
                "pessimista": {"preco_alvo": 20.0, "upside_pct": -20.0},
                "base": {"preco_alvo": 30.0, "upside_pct": 20.0},
                "otimista": {"preco_alvo": 40.0, "upside_pct": 60.0},
            },
            "premissas": {"wacc": 0.12, "g_terminal": 0.03},
            "sensibilidade": {"disponivel": True, "linhas": []},
        }),
        "valuation_reviewer": _resultado("valuation_reviewer", dados={
            "disponivel": True, "aprovado": False,
            "precos_alvo_revisados": {"pessimista": 20.0, "base": 30.0, "otimista": 40.0},
            "achados": [{"tipo": "RASTREABILIDADE", "descricao": "Data-base do modelo não identificada."}],
            "limitacoes": ["Revisão determinística; não substitui validação humana."],
        }),
    }
    consolidado = consolidacao.consolidar(resultados, ticker="PETR4")
    reviewer = next(a for a in consolidado["pareceres_analistas"]["analistas"] if a["id"] == "valuation_reviewer")
    assert reviewer["recomendacao"] == "COM RESSALVAS"
    assert reviewer["dcf"]["disponivel"] is True
    assert reviewer["dcf"]["cenarios"]["base"]["preco_alvo"] == 30.0
    assert reviewer["dcf"]["premissas"]["wacc"] == 0.12
    assert reviewer["upside_pct"] == 20.0
    assert any("RASTREABILIDADE" in c for c in reviewer["contras"])
    assert reviewer["limitacoes"] == ["Revisão determinística; não substitui validação humana."]


def test_valuation_reviewer_sem_model_builder_disponivel_declara_dcf_indisponivel():
    resultados = {
        "valuation_reviewer": _resultado("valuation_reviewer", dados={
            "disponivel": False, "motivo": "Model Builder não entregou um DCF válido; revisão independente bloqueada.",
            "achados": [], "limitacoes": [],
        }),
    }
    consolidado = consolidacao.consolidar(resultados, ticker="PETR4")
    reviewer = next(a for a in consolidado["pareceres_analistas"]["analistas"] if a["id"] == "valuation_reviewer")
    assert reviewer["recomendacao"] == "INSUFICIENTE"
    assert reviewer["dcf"]["disponivel"] is False


def test_sinal_comite_usa_preco_alvo_e_upside_do_model_builder():
    resultados = {
        "analise_ticker": _resultado("analise_ticker", dados={
            "ticker": "PETR4", "fundamentos": {"preco": 25.0, "moeda": "BRL"},
        }),
        "model_builder": _resultado("model_builder", dados={
            "disponivel": True,
            "cenarios": {
                "pessimista": {"preco_alvo": 20.0, "upside_pct": -20.0},
                "base": {"preco_alvo": 30.0, "upside_pct": 20.0},
                "otimista": {"preco_alvo": 40.0, "upside_pct": 60.0},
            },
        }),
        "valuation_reviewer": _resultado("valuation_reviewer", dados={
            "disponivel": True, "aprovado": True,
            "precos_alvo_revisados": {"pessimista": 20.0, "base": 30.0, "otimista": 40.0},
            "achados": [], "limitacoes": [],
        }),
    }
    sinal = consolidacao.consolidar(resultados, ticker="PETR4")["sinal_comite"]
    assert sinal["preco_alvo_modelo"] == 30.0
    assert sinal["upside_modelo_pct"] == 20.0


def test_sinal_comite_expoe_preco_atual_e_data_de_referencia():
    """Achado real (auditoria 2026-11-11): o cabeçalho da análise
    (ui/coordenador_tab.py:_render_cabecalho_decisao) não mostrava o
    preço atual nem a data de referência da cotação em lugar nenhum,
    apesar do dado já existir em fundamentos (data/radar.py:linha_valuation).
    sinal_comite agora propaga os dois - consolidacao.py nunca recalcula
    preço, só repassa o que já veio de analise_ticker."""
    resultados = {
        "analise_ticker": _resultado("analise_ticker", dados={
            "fundamentos": {"preco": 36.9, "moeda": "R$", "consultado_em": "2026-11-11T14:00:00-03:00"},
        }),
    }
    sinal = consolidacao.consolidar(resultados, ticker="PETR4")["sinal_comite"]
    assert sinal["preco_atual"] == 36.9
    assert sinal["preco_atual_consultado_em"] == "2026-11-11T14:00:00-03:00"


def test_sinal_comite_sem_fundamentos_declara_preco_atual_ausente():
    sinal = consolidacao.consolidar({}, ticker="PETR4")["sinal_comite"]
    assert sinal["preco_atual"] is None
    assert sinal["preco_atual_consultado_em"] is None


# ============================================================
# Divergência entre os PRÓPRIOS pareceres do Comitê - diferente da
# cross_comparador_memoria (que compara 2 fontes EXTERNAS sobre a
# mesma casa). Aqui o conflito é entre os especialistas internos
# (market_researcher/earnings_reviewer/valuation_comparables) a
# partir dos MESMOS dados de entrada.
# ============================================================

# Fundamentos desenhados pra produzir um conflito real: indicadores
# operacionais fortes (ROE/margem/dívida/FCF positivos) levam o Market
# Researcher a COMPRA, mas o P/L muito acima da mediana setorial (30x
# vs 10x) leva o Valuation por Múltiplos a VENDA - mesmo ticket, duas
# leituras opostas.
_FUNDAMENTOS_DIVERGENTES = {
    "preco": 20.0, "roe": 25.0, "margem_liquida": 20.0,
    "divida_liquida_ebitda": 0.5, "fluxo_caixa_livre": 500.0, "pl": 30.0,
}
_SETORIAL_DIVERGENTE = {"pl_mediana": 10.0}

# Mesmos indicadores, mas com P/L alinhado ao setor (múltiplo barato
# relativo) - Market Researcher e Valuation concordam em COMPRA.
_FUNDAMENTOS_CONCORDANTES = {
    "preco": 20.0, "roe": 25.0, "margem_liquida": 20.0,
    "divida_liquida_ebitda": 0.5, "fluxo_caixa_livre": 500.0, "pl": 10.0,
}
_SETORIAL_CONCORDANTE = {"pl_mediana": 18.0}


def test_divergencia_entre_analistas_do_comite_quando_recomendacoes_comparaveis_discordam():
    resultados = {
        "analise_ticker": _resultado("analise_ticker", dados={
            "fundamentos": _FUNDAMENTOS_DIVERGENTES,
            "comparativo_setorial": _SETORIAL_DIVERGENTE,
        }),
    }
    consolidado = consolidacao.consolidar(resultados, ticker="PETR4")
    pareceres = {a["id"]: a.get("recomendacao") for a in consolidado["pareceres_analistas"]["analistas"]}
    assert pareceres["market_researcher"] == "COMPRA"
    assert pareceres["valuation_comparables"] == "VENDA"

    divergencia = consolidado["divergencias"]["entre_analistas_comite"]
    assert divergencia is not None
    assert divergencia["divergente"] is True
    assert divergencia["categorias"]["market_researcher"] == "COMPRA"
    assert divergencia["categorias"]["valuation_comparables"] == "VENDA"
    assert any("comitê" in p and "DIVERGEM" in p for p in consolidado["pontos_atencao"])
    assert any("divergem entre si" in linha for linha in consolidado["conclusao"])


def test_sem_divergencia_entre_analistas_do_comite_quando_recomendacoes_concordam():
    resultados = {
        "analise_ticker": _resultado("analise_ticker", dados={
            "fundamentos": _FUNDAMENTOS_CONCORDANTES,
            "comparativo_setorial": _SETORIAL_CONCORDANTE,
        }),
    }
    consolidado = consolidacao.consolidar(resultados, ticker="PETR4")
    divergencia = consolidado["divergencias"]["entre_analistas_comite"]
    assert divergencia is not None
    assert divergencia["divergente"] is False
    assert not any("comitê" in p and "DIVERGEM" in p for p in consolidado["pontos_atencao"])
    assert not any("divergem entre si" in linha for linha in consolidado["conclusao"])


def test_divergencia_entre_analistas_do_comite_none_quando_menos_de_dois_comparaveis():
    # Sem nenhum dado de entrada, market_researcher e valuation_comparables
    # caem em "SEM BASE SUFICIENTE"/"VALUATION INSUFICIENTE" (recomendacao
    # INSUFICIENTE, fora da escala comparável) e earnings_reviewer nem
    # chega a ter a chave "recomendacao" (nota indisponível) - 0 analistas
    # comparáveis, nunca "concordam por falta de dado".
    consolidado = consolidacao.consolidar({}, ticker="PETR4")
    assert consolidado["divergencias"]["entre_analistas_comite"] is None


def test_confianca_rebaixada_de_alta_para_media_quando_comite_diverge():
    resultados = {
        "analise_ticker": _resultado("analise_ticker", dados={
            "fundamentos": _FUNDAMENTOS_DIVERGENTES,
            "comparativo_setorial": _SETORIAL_DIVERGENTE,
        }),
        "comparador": _resultado("comparador", evidencias=[{"fonte": "x"}]),
        "memoria_research": _resultado("memoria_research", evidencias=[{"fonte": "y"}]),
        "noticias": _resultado("noticias", evidencias=[{"fonte": "z"}]),
    }
    # Confirma a premissa do teste: sem o rebaixamento por divergência,
    # este cenário (3 de 4 acionados com evidência real) classificaria ALTA.
    confianca_sem_divergencia = consolidacao._confianca(resultados, divergencia_comite=None)
    assert confianca_sem_divergencia["categoria"] == consolidacao.CONFIANCA_ALTA

    consolidado = consolidacao.consolidar(resultados, ticker="PETR4")
    assert consolidado["divergencias"]["entre_analistas_comite"]["divergente"] is True
    assert consolidado["confianca"]["categoria"] == consolidacao.CONFIANCA_MEDIA
    assert "Rebaixada de ALTA para MEDIA" in consolidado["confianca"]["justificativa"]
    assert "%" not in consolidado["confianca"]["justificativa"]


def test_confianca_nao_rebaixa_quando_comite_concorda_mesmo_com_muita_evidencia():
    resultados = {
        "analise_ticker": _resultado("analise_ticker", dados={
            "fundamentos": _FUNDAMENTOS_CONCORDANTES,
            "comparativo_setorial": _SETORIAL_CONCORDANTE,
        }),
        "comparador": _resultado("comparador", evidencias=[{"fonte": "x"}]),
        "memoria_research": _resultado("memoria_research", evidencias=[{"fonte": "y"}]),
        "noticias": _resultado("noticias", evidencias=[{"fonte": "z"}]),
    }
    consolidado = consolidacao.consolidar(resultados, ticker="PETR4")
    assert consolidado["divergencias"]["entre_analistas_comite"]["divergente"] is False
    assert consolidado["confianca"]["categoria"] == consolidacao.CONFIANCA_ALTA
    assert "Rebaixada" not in consolidado["confianca"]["justificativa"]


def test_model_builder_e_valuation_reviewer_nunca_entram_na_divergencia_entre_analistas():
    """model_builder (MODELADO/INSUFICIENTE) e valuation_reviewer (APROVADO/
    COM RESSALVAS/INSUFICIENTE) respondem perguntas diferentes de
    market_researcher/earnings_reviewer/valuation_comparables (COMPRA/
    VENDA/NEUTRO) - nunca podem ser contados como "divergência de
    recomendação" só por estarem fora dessa escala."""
    resultados = {
        "model_builder": _resultado("model_builder", dados={
            "disponivel": True, "metodo": "DCF de 5 anos",
            "fonte_premissas": "CVM + premissas manuais",
            "cenarios": {"pessimista": {"preco_alvo": 20.0}, "base": {"preco_alvo": 30.0}, "otimista": {"preco_alvo": 40.0}},
            "sensibilidade": {"disponivel": True, "linhas": []},
        }),
        "valuation_reviewer": _resultado("valuation_reviewer", dados={
            "disponivel": True, "aprovado": True,
            "precos_alvo_revisados": {"pessimista": 20.0, "base": 30.0, "otimista": 40.0},
            "achados": [], "limitacoes": [],
        }),
    }
    consolidado = consolidacao.consolidar(resultados, ticker="PETR4")
    assert consolidado["divergencias"]["entre_analistas_comite"] is None
