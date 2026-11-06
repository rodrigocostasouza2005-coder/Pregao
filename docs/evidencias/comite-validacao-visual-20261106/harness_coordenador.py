# Harness visual LOCAL (sem login/auth) - valida a reformulacao do
# COORDENADOR/COMITE (ui/coordenador_tab.py, mergeada em 573111c SEM
# validacao visual real) direto, sem depender de login/Supabase real.
# Mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py.
#
# Monta as 5 sub-abas reais (Visao Geral/Especialistas/Execucoes/
# Historico/Analisar) dentro de st.tabs, usando os MESMOS nomes de
# ui/navegacao.py, com dados mockados nas camadas de dados
# (data.coordenador_central.*) - a logica de consolidacao/apresentacao
# de ui/coordenador_tab.py roda de verdade, sem nenhum atalho.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.coordenador_tab as coord
from data.coordenador_central import execucoes_agendadas, persistencia, registro

st.set_page_config(page_title="harness coordenador", layout="wide")
with open(config.BASE_DIR / "style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

tema = config.TEMAS["AMBAR"]
_css_vars = (
    f":root {{"
    f"--bg:{tema['fundo']}; --painel-bg:{tema['painel']}; --borda:{tema['borda']}; "
    f"--destaque:{tema['destaque']}; --alta:{tema['alta']}; --baixa:{tema['baixa']}; "
    f"--neutro:{tema['neutro']}; --cinza:{tema['cinza']}; --ciano:{tema['ciano']}; "
    f"--padding-painel:0.4rem; --fonte-base:0.9rem;"
    f"}}"
)
st.markdown(f"<style>{_css_vars}</style>", unsafe_allow_html=True)
st.markdown(
    "<style>body{background:var(--bg);} .stApp{background:var(--bg);}</style>",
    unsafe_allow_html=True,
)


# ============================================================
# Dados mockados (camada data.coordenador_central.*)
# ============================================================

def _consolidado_completo() -> dict:
    """Mesmo dict de tests/test_coordenador_tab_consolidado_reorganizado.py
    (fixture real usada pra cobrir a reformulacao visual) - reaproveitado
    aqui pra garantir que o harness visual bate com o que o teste
    automatizado já cobre."""
    return {
        "resumo_executivo": "Análise consolidada para PETR4. 4 de 5 especialista(s) acionado(s) responderam com dado disponível.",
        "sinal_comite": {
            "sinal": "COMPRA", "score": 3, "confianca": "ALTA",
            "justificativa": "ROE, margem e FCF positivos; dívida controlada.",
            "preco_alvo_modelo": 42.50, "moeda_preco_alvo_modelo": "R$",
            "upside_modelo_pct": 15.3,
            "preco_alvo_pl_setorial": 39.0, "upside_pl_setorial_pct": 6.0,
            "preco_alvo_consenso": 40.0, "upside_consenso_pct": 8.1,
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


_ANALISE_FAKE = {
    "id": "fedcba987654", "solicitacao": "Analisar PETR4",
    "tipo_fluxo": "analise_ticker", "ticker": "PETR4",
    "iniciado_em": "2026-11-05T10:00:00Z", "status": "CONCLUIDA",
    "duracao_ms": 3456, "resultado": _consolidado_completo(),
}

_ANALISES_RECENTES = [
    _ANALISE_FAKE,
    {
        "id": "ab12cd34ef56", "solicitacao": "Comparar casas sobre VALE3",
        "tipo_fluxo": "comparar_casas", "ticker": "VALE3",
        "iniciado_em": "2026-11-04T18:20:00Z", "status": "PARCIAL",
        "duracao_ms": 9800, "resultado": None, "erro": None,
    },
    {
        "id": "99aa88bb77cc", "solicitacao": "Identificar catalisadores de WEGE3",
        "tipo_fluxo": "catalisadores", "ticker": "WEGE3",
        "iniciado_em": "2026-11-03T09:05:00Z", "status": "ERRO",
        "duracao_ms": 1200, "resultado": None, "erro": "timeout ao consultar fundamentos",
    },
]

_EXECUCOES_AGENDADAS = [
    {"tipo": "backoffice", "status": "OK", "iniciado_em": "2026-11-06T06:00:00Z", "duracao_ms": 45210, "resumo": "12 achados novos."},
    {"tipo": "sintese", "status": "OK", "iniciado_em": "2026-11-06T06:05:00Z", "duracao_ms": 18340, "resumo": "Síntese gerada para 8 tickers."},
    {"tipo": "comite_noturno", "status": "ERRO", "iniciado_em": "2026-11-06T02:00:00Z", "duracao_ms": 3200, "erro": "Supabase indisponível durante a rodada."},
]

_METRICAS_ESPECIALISTAS = {
    "comparador": {"total_execucoes": 42, "taxa_sucesso_recente_pct": 100.0, "tempo_medio_ms": 820, "taxa_sucesso_pct": 97.6, "ultima_execucao_em": "2026-11-06T06:05:00Z", "ultimo_erro_tecnico": None},
    "memoria_research": {"total_execucoes": 30, "taxa_sucesso_recente_pct": 60.0, "tempo_medio_ms": 1400, "taxa_sucesso_pct": 80.0, "ultima_execucao_em": "2026-11-05T22:10:00Z", "ultimo_erro_tecnico": "GEMINI_API_KEY ausente: busca semântica desabilitada nesta rodada, degradou para lexical."},
    "analise_ticker": {"total_execucoes": 55, "taxa_sucesso_recente_pct": 100.0, "tempo_medio_ms": 2100, "taxa_sucesso_pct": 98.2, "ultima_execucao_em": "2026-11-06T06:05:00Z", "ultimo_erro_tecnico": None},
    "noticias": {"total_execucoes": 55, "taxa_sucesso_recente_pct": 100.0, "tempo_medio_ms": 640, "taxa_sucesso_pct": 100.0, "ultima_execucao_em": "2026-11-06T06:05:00Z", "ultimo_erro_tecnico": None},
    "calendario": {"total_execucoes": 55, "taxa_sucesso_recente_pct": 100.0, "tempo_medio_ms": 310, "taxa_sucesso_pct": 100.0, "ultima_execucao_em": "2026-11-06T06:05:00Z", "ultimo_erro_tecnico": None},
    "catalisadores": {"total_execucoes": 20, "taxa_sucesso_recente_pct": 100.0, "tempo_medio_ms": 500, "taxa_sucesso_pct": 100.0, "ultima_execucao_em": "2026-11-03T09:05:00Z", "ultimo_erro_tecnico": None},
    "resultados_corporativos": {"total_execucoes": 0, "taxa_sucesso_recente_pct": 0.0, "tempo_medio_ms": "—", "taxa_sucesso_pct": "—", "ultima_execucao_em": None, "ultimo_erro_tecnico": None},
    "model_builder": {"total_execucoes": 12, "taxa_sucesso_recente_pct": 100.0, "tempo_medio_ms": 3100, "taxa_sucesso_pct": 100.0, "ultima_execucao_em": "2026-11-05T10:00:00Z", "ultimo_erro_tecnico": None},
    "valuation_reviewer": {"total_execucoes": 12, "taxa_sucesso_recente_pct": 100.0, "tempo_medio_ms": 2800, "taxa_sucesso_pct": 100.0, "ultima_execucao_em": "2026-11-05T10:00:00Z", "ultimo_erro_tecnico": None},
    "radar_x": {"total_execucoes": 0, "taxa_sucesso_recente_pct": 0.0, "tempo_medio_ms": "—", "taxa_sucesso_pct": "—", "ultima_execucao_em": None, "ultimo_erro_tecnico": "X_BEARER_TOKEN ausente (custo de API não aprovado)."},
}


with patch.object(execucoes_agendadas, "listar_ultimas_execucoes", return_value=_EXECUCOES_AGENDADAS), \
     patch.object(persistencia, "listar_analises_recentes", return_value=_ANALISES_RECENTES), \
     patch.object(persistencia, "obter_analise", return_value=_ANALISE_FAKE), \
     patch.object(persistencia, "metricas_especialistas", return_value=_METRICAS_ESPECIALISTAS):

    aba_vg, aba_esp, aba_exec, aba_hist, aba_analisar = st.tabs(
        ["Visão Geral", "Especialistas", "Execuções", "Histórico", "Analisar"]
    )
    with aba_vg:
        coord.render_visao_geral({})
    with aba_esp:
        coord.render_especialistas({})
    with aba_exec:
        coord.render_execucoes({})
    with aba_hist:
        coord.render_historico({})
    with aba_analisar:
        coord.render_analisar({})
