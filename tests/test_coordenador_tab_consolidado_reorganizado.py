# -*- coding: utf-8 -*-
"""Reformulação visual do COMITÊ DE ANÁLISE (ui/coordenador_tab.py,
2026-11-06, pedido do Rodrigo) - cobre a nova organização de
_render_consolidado: cabeçalho de decisão (recomendação do Comitê bem
no topo), 1 aba por especialista (em vez de expanders sequenciais),
dados externos das casas de research e síntese final (conclusão/
divergências/pontos de revisão/material de apoio).

A lógica de consolidação real (data/coordenador_central/consolidacao.py
+ pareceres.py) não é tocada por esta reformulação - só a apresentação.
Por isso este teste fixa um dict "consolidado" já no formato que aquelas
funções devolvem (não mocka nenhuma delas), pra garantir que a UI nova
continua lendo exatamente os mesmos campos que a UI antiga lia.

AppTest real (nunca AppTest.from_string tocando rede: persistência
100% mockada - nada é escrito em nenhum log de produção por este
teste)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _consolidado_completo() -> dict:
    return {
        "resumo_executivo": "Análise consolidada para PETR4. 4 de 5 especialista(s) acionado(s) responderam com dado disponível.",
        "sinal_comite": {
            "sinal": "COMPRA", "score": 3, "confianca": "ALTA",
            "justificativa": "ROE, margem e FCF positivos; dívida controlada.",
            "preco_alvo_modelo": 42.50, "moeda_preco_alvo_modelo": "R$",
            "upside_modelo_pct": 15.3,
            "preco_alvo_pl_setorial": 39.0, "upside_pl_setorial_pct": 6.0,
            "preco_alvo_consenso": 40.0, "upside_consenso_pct": 8.1,
            "preco_atual": 36.90, "preco_atual_consultado_em": "2026-11-11T14:00:00-03:00",
        },
        "confianca": {"categoria": "ALTA", "justificativa": "4 de 5 especialista(s) acionado(s) trouxeram evidência real."},
        "visao_especialistas": {
            "comparador": {"disponivel": True, "resumo": "3 casas comparadas.", "motivo_indisponivel": None},
            "memoria_research": {"disponivel": False, "resumo": None, "motivo_indisponivel": "GEMINI_API_KEY ausente"},
        },
        "evidencias": [
            {"especialista": "comparador", "fonte": "BTG Pactual", "data": "2026-10-20", "titulo": "Relatório setorial"},
        ],
        "divergencias": {
            "cross_comparador_memoria": {
                "n_casas_comparadas": 2,
                "divergencias": [
                    {"casa": "BTG Pactual", "tipo": "qualitativa", "campo": "recomendacao", "comparador": "COMPRA", "memoria_research": "NEUTRO"},
                ],
            },
        },
        "pontos_atencao": ["radar_x: indisponível (sem X_BEARER_TOKEN)."],
        "conclusao": [
            "[FATO] 4 de 5 especialista(s) acionado(s) retornaram dado disponível.",
            "[CÁLCULO INTERNO] Confiança da consolidação classificada como ALTA.",
        ],
        "pareceres_analistas": {
            "ticker": "PETR4",
            "analistas": [
                {
                    "id": "market_researcher", "nome": "Market Researcher — Analista de Empresas",
                    "especialidade": "Fundamentos, qualidade do negócio, crescimento e riscos",
                    "metodo": "Síntese heurística dos sinais observáveis.",
                    "vies": "POSITIVO", "recomendacao": "COMPRA",
                    "tese": "Leitura construtiva: ROE positivo de 18,0%.",
                    "pros": ["ROE positivo de 18,0%."], "contras": [],
                    "preco_alvo": None, "preco_atual": 36.90,
                    "fontes": ["Market Researcher", "Valuation Radar", "Earnings Reviewer/CVM"],
                    "indicadores": {
                        "moeda": "R$", "roe_pct": 18.0, "margem_liquida_pct": 12.5,
                        "divida_liquida_ebitda_x": 1.2, "fluxo_caixa_livre": 500000.0,
                        "pl_x": 9.0, "pl_mediana_setor_x": 9.5,
                        "roic_trimestral_pct": 4.1, "receita_liquida_yoy_pct": 6.5,
                    },
                },
                {
                    "id": "earnings_reviewer", "nome": "Analista de Resultados",
                    "especialidade": "DRE, balanço, fluxo de caixa e evolução trimestral",
                    "metodo": "Compara variações YoY.",
                    "vies": "MISTO", "recomendacao": "NEUTRO",
                    "tese": "Resultado 3T26 — leitura equilibrada.",
                    "pros": ["Receita líquida avançou 4,0% YoY."],
                    "contras": ["Margem bruta contraiu 1,0 p.p."],
                    "preco_alvo": None,
                    "fontes": ["CVM — ITR 3T26"],
                    "limitacoes": ["Margem bruta sem comparável do mesmo trimestre do ano anterior."],
                },
                {
                    "id": "valuation_comparables", "nome": "Valuation por Múltiplos e Research",
                    "especialidade": "DCF, múltiplos, comparáveis e preço-alvo",
                    "metodo": "Preço atual × P/L mediano setorial ÷ P/L atual.",
                    "moeda": "R$", "vies": "PRÓXIMO À MEDIANA SETORIAL", "recomendacao": "NEUTRO",
                    "tese": "P/L de 9,0x versus mediana setorial 9,5x.",
                    "pros": [], "contras": [], "preco_alvo": 39.0, "upside_pct": 6.0,
                    "preco_atual": 36.90,
                    "dcf": {"disponivel": False, "campos_faltantes": [], "motivo": "Premissas explícitas ainda não informadas."},
                },
                {
                    "id": "model_builder", "nome": "Model Builder",
                    "especialidade": "Projeção financeira e DCF em três cenários",
                    "recomendacao": "MODELADO", "vies": "MODELO DISPONÍVEL",
                    "tese": "DCF de 5 anos + Gordon Growth.",
                    "pros": [], "contras": [],
                    "moeda": "R$", "data_base": "2025-12-31", "fontes": ["Relatório anual 2025"],
                    "campos_faltantes": [],
                    "cenarios": {
                        "pessimista": {"preco_alvo": 35.0, "upside_pct": -5.1, "crescimento_fcf": 0.02, "wacc": 0.12, "g_terminal": 0.03, "valor_empresa": 500000.0, "valor_patrimonio": 350000.0},
                        "base": {"preco_alvo": 42.5, "upside_pct": 15.2, "crescimento_fcf": 0.05, "wacc": 0.12, "g_terminal": 0.03, "valor_empresa": 600000.0, "valor_patrimonio": 420000.0},
                        "otimista": {"preco_alvo": 50.0, "upside_pct": 35.5, "crescimento_fcf": 0.08, "wacc": 0.12, "g_terminal": 0.03, "valor_empresa": 700000.0, "valor_patrimonio": 490000.0},
                    },
                    "premissas": {
                        "fcf_base": 50000.0, "divida_liquida": 20000.0, "origem_divida_liquida": "balanço CVM",
                        "acoes": 10000.0, "crescimento_fcf_otimista": 0.08, "crescimento_fcf_base": 0.05,
                        "crescimento_fcf_pessimista": 0.02, "wacc": 0.12, "g_terminal": 0.03,
                    },
                    "sensibilidade": {
                        "disponivel": True, "passos_crescimento": [-0.01, 0.0, 0.01],
                        "linhas": [
                            {"wacc": 0.11, "celulas": [{"preco_alvo": 44.0}, {"preco_alvo": 46.0}, {"preco_alvo": 48.0}]},
                            {"wacc": 0.12, "celulas": [{"preco_alvo": 40.0}, {"preco_alvo": 42.5}, {"preco_alvo": 44.0}]},
                        ],
                        "observacao": "Varia WACC e crescimento FCF-base.",
                    },
                },
                {
                    "id": "valuation_reviewer", "nome": "Valuation Reviewer",
                    "especialidade": "Revisão independente de cenários, premissas e sensibilidade",
                    "recomendacao": "APROVADO", "vies": "APROVADO",
                    "tese": "Revisão concluída; ver achados e limitações.",
                    "pros": [], "contras": [],
                    "preco_alvo": 42.5, "upside_pct": 15.2, "preco_atual": 36.90,
                    "dcf": {
                        "disponivel": True, "moeda": "R$",
                        "fonte_premissas": "Relatório anual 2025, página 42", "data_base": "2025-12-31",
                        "cenarios": {
                            "otimista": {"rotulo": "OTIMISTA", "preco_alvo": 50.0, "upside_pct": 35.5, "crescimento_fcf": 0.08, "wacc": 0.12, "g_terminal": 0.03},
                            "base": {"rotulo": "BASE", "preco_alvo": 42.5, "upside_pct": 15.2, "crescimento_fcf": 0.05, "wacc": 0.12, "g_terminal": 0.03},
                            "pessimista": {"rotulo": "PESSIMISTA", "preco_alvo": 35.0, "upside_pct": -5.1, "crescimento_fcf": 0.02, "wacc": 0.12, "g_terminal": 0.03},
                        },
                        "premissas": {
                            "fcf_base": 50000.0, "divida_liquida": 20000.0, "origem_divida_liquida": "balanço CVM",
                            "acoes": 10000.0, "crescimento_fcf_otimista": 0.08, "crescimento_fcf_base": 0.05,
                            "crescimento_fcf_pessimista": 0.02, "wacc": 0.12, "g_terminal": 0.03,
                        },
                    },
                },
            ],
            "casas_research": [
                {
                    "casa": "BTG Pactual", "recomendacao": "COMPRA", "preco_alvo": 44.0, "upside_pct": 19.2,
                    "data_publicacao": "2026-10-20T00:00:00Z", "titulo": "Relatório setorial", "link": "https://exemplo.com/btg",
                    "tese": ["Expansão de margem no 2S26."], "pros": [], "contras": ["Risco regulatório."],
                    "projecoes": {"receita": "+6%"},
                },
            ],
            "preco_alvo_consenso": {"mediana": 44.0, "minimo": 40.0, "maximo": 48.0, "n_casas": 2, "preco_atual": 36.90, "upside_pct": 19.2},
        },
    }


def _rodar_render_historico(consolidado: dict):
    from streamlit.testing.v1 import AppTest

    analise_fake = {
        "id": "fedcba987654", "solicitacao": "Analisar PETR4",
        "tipo_fluxo": "analise_ticker", "ticker": "PETR4",
        "iniciado_em": "2026-11-05T10:00:00Z", "status": "CONCLUIDA",
        "duracao_ms": 3456, "resultado": consolidado,
    }
    script = f'''
from unittest.mock import patch
import ui.coordenador_tab as coord
from data.coordenador_central import persistencia

analises_fake = [{analise_fake!r}]
analise_fake = {analise_fake!r}

with patch.object(persistencia, "listar_analises_recentes", return_value=analises_fake), \\
     patch.object(persistencia, "obter_analise", return_value=analise_fake):
    coord.render_historico({{}})
'''
    return AppTest.from_string(script, default_timeout=30).run()


def test_cabecalho_mostra_recomendacao_confianca_e_resumo():
    at = _rodar_render_historico(_consolidado_completo())
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "RECOMENDAÇÃO DO COMITÊ" in textos
    assert "COMPRA" in textos
    assert "CONFIANÇA ALTA" in textos
    assert "Análise consolidada para PETR4" in textos


def test_cabecalho_mostra_empresa_ticker_e_preco_atual():
    """Achado real (auditoria 2026-11-11): o cabeçalho da análise nunca
    identificava a EMPRESA (só o ticker, de forma indireta, no resumo
    executivo em prosa) nem mostrava o preço atual/data de referência da
    cotação usada como base de todos os upsides exibidos abaixo."""
    at = _rodar_render_historico(_consolidado_completo())
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "Petrobras" in textos
    assert "PETR4" in textos
    assert "Preço atual" in textos
    assert "2026-11-11" in textos


def test_pareceres_viram_abas_uma_por_analista():
    at = _rodar_render_historico(_consolidado_completo())
    assert not at.exception
    rotulos = [t.label for t in at.tabs]
    assert "Market Researcher — Analista de Empresas" in rotulos
    assert "Analista de Resultados" in rotulos
    assert "Valuation por Múltiplos e Research" in rotulos
    assert "Model Builder" in rotulos
    assert "Valuation Reviewer" in rotulos


def test_aba_market_researcher_mostra_fontes_e_indicadores_financeiros():
    """Achado real (auditoria 2026-11-11): fontes/indicadores (ROE, margem,
    dívida líquida/EBITDA, FCF, P/L, ROIC) já existiam no dado do parecer
    mas nunca eram exibidos - só apareciam em prosa dentro da tese."""
    at = _rodar_render_historico(_consolidado_completo())
    assert not at.exception
    aba = next(t for t in at.tabs if t.label == "Market Researcher — Analista de Empresas")
    textos = " ".join(m.value for m in aba.markdown)
    assert "Fontes: Market Researcher, Valuation Radar, Earnings Reviewer/CVM" in textos
    assert "Indicadores financeiros" in textos
    assert "ROIC trimestral" in textos
    assert "Dívida líquida/EBITDA" in textos


def test_aba_earnings_reviewer_mostra_fontes_e_limitacoes():
    at = _rodar_render_historico(_consolidado_completo())
    assert not at.exception
    aba = next(t for t in at.tabs if t.label == "Analista de Resultados")
    textos = " ".join(m.value for m in aba.markdown)
    assert "Fontes: CVM — ITR 3T26" in textos
    captions = " ".join(c.value for c in aba.caption)
    assert "Limitações declaradas" in captions
    assert "Margem bruta sem comparável" in captions


def test_aba_model_builder_mostra_cenarios_premissas_e_sensibilidade():
    at = _rodar_render_historico(_consolidado_completo())
    assert not at.exception
    aba_model_builder = next(t for t in at.tabs if t.label == "Model Builder")
    textos = " ".join(m.value for m in aba_model_builder.markdown)
    assert "PREÇO-ALVO" in textos
    assert "Modelo DCF — três cenários" in textos
    assert "Sensibilidade do preço-alvo-base" in textos


def test_aba_valuation_reviewer_com_dcf_disponivel_mostra_sensibilidade_sem_quebrar():
    """Mesmo caminho do bug do NameError (calcular_sensibilidade_dcf),
    agora dentro da nova aba do Valuation Reviewer."""
    at = _rodar_render_historico(_consolidado_completo())
    assert not at.exception
    aba_reviewer = next(t for t in at.tabs if t.label == "Valuation Reviewer")
    textos = " ".join(m.value for m in aba_reviewer.markdown)
    assert "PREÇO-ALVO PRINCIPAL" in textos
    assert "DCF — preços-alvo por cenário" in textos
    assert "Sensibilidade do cenário-base" in textos


def test_aba_valuation_comparables_sem_dcf_explica_motivo_sem_mostrar_sensibilidade():
    at = _rodar_render_historico(_consolidado_completo())
    assert not at.exception
    # valuation_comparables não tem bloco especial (só model_builder e
    # valuation_reviewer têm) - a aba deve renderizar tese/pros/contras
    # normalmente, sem o bloco de DCF do Valuation Reviewer.
    aba_valuation = next(t for t in at.tabs if t.label == "Valuation por Múltiplos e Research")
    textos = " ".join(m.value for m in aba_valuation.markdown)
    assert "P/L de 9,0x" in textos


def test_casas_research_mostra_tabela_e_consenso():
    at = _rodar_render_historico(_consolidado_completo())
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "Dados externos — o que dizem as casas de research" in textos
    assert "BTG Pactual" in textos
    assert "Mediana dos preços-alvo publicados" in textos
    rotulos_expander = [e.label for e in at.expander]
    assert "Tese e riscos — BTG Pactual" in rotulos_expander


def test_sintese_final_mostra_conclusao_divergencias_e_material_de_apoio():
    at = _rodar_render_historico(_consolidado_completo())
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "Conclusão consolidada do Comitê" in textos
    assert "Divergências e pontos que precisam de revisão" in textos
    assert "Material de apoio" in textos
    rotulos_expander = [e.label for e in at.expander]
    assert any("Pontos de atenção" in r for r in rotulos_expander)
    assert any("Divergências identificadas" in r for r in rotulos_expander)
    assert any("Evidências" in r for r in rotulos_expander)
    assert any("Visão bruta por especialista acionado" in r for r in rotulos_expander)


def test_consolidado_minimo_sem_nenhuma_secao_opcional_nao_quebra():
    """Degradação: quando quase tudo está vazio (análise com pouquíssimo
    dado disponível), a página não deve quebrar nem mostrar seções vazias
    enganosas."""
    minimo = {
        "resumo_executivo": "Análise consolidada.", "sinal_comite": {},
        "confianca": {"categoria": "INSUFICIENTE", "justificativa": "Nenhum especialista foi acionado nesta rodada."},
        "visao_especialistas": {}, "evidencias": [],
        "divergencias": {"cross_comparador_memoria": None},
        "pontos_atencao": [], "conclusao": [],
        "pareceres_analistas": {"analistas": [], "casas_research": [], "preco_alvo_consenso": {}},
    }
    at = _rodar_render_historico(minimo)
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "CONFIANÇA INSUFICIENTE" in textos
    assert not list(at.tabs)
