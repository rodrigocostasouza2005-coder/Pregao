# Harness visual LOCAL (sem login/auth, sem Supabase real) para validar o
# redesign ESTRUTURAL de COORDENADOR CENTRAL (Agente D, 2026-11-12) - mesmo
# padrão já usado em docs/evidencias/validacao-independente-home-mercado-
# 20261106/harness_home.py: chama cada render_* direto, com as funções de
# dado do módulo monkeypatchadas com valores mockados REALISTAS (nunca
# inventados na UI de produção - só aqui, pra ter o que mostrar no
# screenshot sem precisar de Supabase real).
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.coordenador_tab as coord

ABA = sys.argv[1] if len(sys.argv) > 1 else "visao_geral"

st.set_page_config(page_title=f"harness coordenador - {ABA}", layout="wide")
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
st.markdown("<style>body{background:var(--bg);} .stApp{background:var(--bg);}</style>", unsafe_allow_html=True)

AGORA = datetime.now(timezone.utc)

_ESPECIALISTAS = [
    SimpleNamespace(id="market_researcher", nome="Market Researcher", descricao="Coleta e organiza indicadores financeiros e de mercado.", pre_requisitos=()),
    SimpleNamespace(id="earnings_reviewer", nome="Earnings Reviewer", descricao="Revisa resultados trimestrais e eventos recentes.", pre_requisitos=("market_researcher",)),
    SimpleNamespace(id="model_builder", nome="Model Builder", descricao="Monta o modelo DCF em 3 cenários a partir das premissas informadas.", pre_requisitos=("market_researcher",)),
    SimpleNamespace(id="valuation_reviewer", nome="Valuation Reviewer", descricao="Revisa o DCF do Model Builder e calcula sensibilidade.", pre_requisitos=("model_builder",)),
    SimpleNamespace(id="catalisadores", nome="Identificador de Catalisadores", descricao="Cruza calendário de eventos e notícias por ticker.", pre_requisitos=()),
]

_METRICAS = {
    "market_researcher": {"total_execucoes": 42, "taxa_sucesso_recente_pct": 100.0, "tempo_medio_ms": 3200, "taxa_sucesso_pct": 97.6, "ultima_execucao_em": (AGORA - timedelta(hours=2)).isoformat(), "ultimo_erro_tecnico": None},
    "earnings_reviewer": {"total_execucoes": 38, "taxa_sucesso_recente_pct": 90.0, "tempo_medio_ms": 2800, "taxa_sucesso_pct": 92.1, "ultima_execucao_em": (AGORA - timedelta(hours=3)).isoformat(), "ultimo_erro_tecnico": "timeout ao consultar fundamentos (yfinance)"},
    "model_builder": {"total_execucoes": 30, "taxa_sucesso_recente_pct": 100.0, "tempo_medio_ms": 1500, "taxa_sucesso_pct": 100.0, "ultima_execucao_em": (AGORA - timedelta(hours=2)).isoformat(), "ultimo_erro_tecnico": None},
    "valuation_reviewer": {"total_execucoes": 30, "taxa_sucesso_recente_pct": 80.0, "tempo_medio_ms": 1800, "taxa_sucesso_pct": 88.0, "ultima_execucao_em": (AGORA - timedelta(hours=2)).isoformat(), "ultimo_erro_tecnico": None},
    "catalisadores": {"total_execucoes": 0, "taxa_sucesso_recente_pct": 0.0, "tempo_medio_ms": None, "taxa_sucesso_pct": None, "ultima_execucao_em": None, "ultimo_erro_tecnico": None},
}

_ANALISES = [
    {"id": "a1b2c3d4e5f6", "solicitacao": "Análise de ticker — PETR4", "tipo_fluxo": "analise_ticker", "ticker": "PETR4", "iniciado_em": (AGORA - timedelta(hours=2)).isoformat(), "status": "CONCLUIDA", "duracao_ms": 8400, "erro": None},
    {"id": "b2c3d4e5f6a1", "solicitacao": "Comparar casas sobre VALE3", "tipo_fluxo": "comparar_casas", "ticker": "VALE3", "iniciado_em": (AGORA - timedelta(hours=5)).isoformat(), "status": "PARCIAL", "duracao_ms": 6100, "erro": "Valuation Reviewer indisponível nesta rodada"},
    {"id": "c3d4e5f6a1b2", "solicitacao": "Identificar catalisadores de WEGE3", "tipo_fluxo": "catalisadores", "ticker": "WEGE3", "iniciado_em": (AGORA - timedelta(days=1)).isoformat(), "status": "CONCLUIDA", "duracao_ms": 2300, "erro": None},
    {"id": "d4e5f6a1b2c3", "solicitacao": "Análise de ticker — ITUB4", "tipo_fluxo": "analise_ticker", "ticker": "ITUB4", "iniciado_em": (AGORA - timedelta(days=2)).isoformat(), "status": "ERRO", "duracao_ms": 1100, "erro": "Falha ao coletar fundamentos (fonte fora do ar)"},
]

_EXECUCOES_AGENDADAS = [
    {"tipo": "backoffice", "status": "OK", "iniciado_em": (AGORA - timedelta(hours=1)).isoformat(), "duracao_ms": 4200, "resumo": "12 ativos monitorados, 0 alertas novos"},
    {"tipo": "sintese", "status": "OK", "iniciado_em": (AGORA - timedelta(hours=6)).isoformat(), "duracao_ms": 15300, "resumo": "Edição publicada com sucesso"},
    {"tipo": "comite_noturno", "status": "ERRO", "iniciado_em": (AGORA - timedelta(hours=3)).isoformat(), "duracao_ms": 900, "erro": "Genial Analisa bloqueada (403)"},
]

_SINAL_COMITE = {
    "sinal": "COMPRA", "score": 7.2, "preco_atual": 36.52, "preco_atual_consultado_em": AGORA.isoformat(),
    "preco_alvo_modelo": 42.80, "preco_alvo_pl_setorial": 40.10, "preco_alvo_consenso": 41.50,
    "upside_modelo_pct": 17.2, "moeda_preco_alvo_modelo": "R$",
    "justificativa": "ROE acima da mediana setorial, FCF positivo e dívida líquida/EBITDA controlada sustentam viés comprador.",
}

_CONSOLIDADO = {
    "ticker": "PETR4",
    "sinal_comite": _SINAL_COMITE,
    "confianca": {"categoria": "ALTA", "justificativa": "4 de 4 especialistas concluíram com dados suficientes."},
    "resumo_executivo": "Petrobras mantém geração de caixa robusta e múltiplo descontado frente aos pares; upside modelado de 17,2% sobre a cotação atual.",
    "status_execucao": "CONCLUIDA",
    "_duracao_ms": 8400,
    "pareceres_analistas": {
        "ticker": "PETR4",
        "preco_alvo_consenso": {"mediana": 41.0, "upside_pct": 12.3, "n_casas": 3},
        "analistas": [
            {
                "id": "market_researcher", "nome": "Market Researcher", "especialidade": "Fundamentos e indicadores de mercado",
                "metodo": "Indicadores extraídos de yfinance/CVM, sem projeção própria.",
                "fontes": ["yfinance", "CVM"], "recomendacao": "COMPRA", "vies": "COMPRADOR",
                "tese": "ROE e margem líquida acima da mediana do setor, com dívida controlada.",
                "pros": ["ROE de 18,4%, acima da mediana do setor (12,1%)", "FCF positivo nos últimos 4 trimestres"],
                "contras": ["Exposição a variação do petróleo Brent"], "limitacoes": [],
                "indicadores": {"moeda": "R$", "roe_pct": 18.4, "margem_liquida_pct": 21.0, "divida_liquida_ebitda_x": 1.1,
                                 "fluxo_caixa_livre": 42_000_000_000, "pl_x": 5.8, "pl_mediana_setor_x": 7.2,
                                 "roic_trimestral_pct": 9.1, "receita_liquida_yoy_pct": 6.4},
            },
            {
                "id": "earnings_reviewer", "nome": "Earnings Reviewer", "especialidade": "Resultados trimestrais",
                "metodo": "Comparação YoY/QoQ dos últimos releases de resultado.",
                "fontes": ["Releases trimestrais B3"], "recomendacao": "NEUTRO", "vies": "MISTO",
                "tese": "Resultado do 3T26 em linha com o consenso, sem catalisador novo relevante.",
                "pros": ["Receita líquida cresceu 6,4% YoY"], "contras": ["Margem EBITDA estável, sem expansão"],
                "limitacoes": ["Não inclui eventos subsequentes após a data-base do release."],
            },
            {
                "id": "model_builder", "nome": "Model Builder", "especialidade": "Modelagem DCF",
                "metodo": "DCF de 5 anos + Gordon Growth, 3 cenários.",
                "fontes": ["Fundamentos coletados", "Premissas informadas pelo analista"], "recomendacao": "MODELADO", "vies": "—",
                "tese": "Cenário-base aponta upside de 17,2% sobre a cotação atual.",
                "pros": [], "contras": [], "limitacoes": [],
                "cenarios": {
                    "base": {"preco_alvo": 42.80, "upside_pct": 17.2, "crescimento_fcf": 0.04, "wacc": 0.11, "g_terminal": 0.03, "valor_empresa": 480_000_000_000, "valor_patrimonio": 390_000_000_000},
                    "otimista": {"preco_alvo": 48.10, "upside_pct": 31.7, "crescimento_fcf": 0.07, "wacc": 0.10, "g_terminal": 0.035, "valor_empresa": 520_000_000_000, "valor_patrimonio": 430_000_000_000},
                    "pessimista": {"preco_alvo": 37.50, "upside_pct": 2.7, "crescimento_fcf": 0.01, "wacc": 0.125, "g_terminal": 0.025, "valor_empresa": 440_000_000_000, "valor_patrimonio": 350_000_000_000},
                },
                "premissas": {"fcf_base": 42_000_000_000, "divida_liquida": 180_000_000_000, "origem_divida_liquida": "balanço 3T26",
                               "acoes": 12_980_000_000, "crescimento_fcf_pessimista": 0.01, "crescimento_fcf_base": 0.04,
                               "crescimento_fcf_otimista": 0.07, "wacc": 0.11, "g_terminal": 0.03},
                "sensibilidade": {"disponivel": False, "motivo": "não calculada neste mock."},
                "moeda": "R$",
            },
            {
                "id": "valuation_reviewer", "nome": "Valuation Reviewer", "especialidade": "Revisão de valuation",
                "metodo": "Revisão independente do DCF do Model Builder.",
                "fontes": ["Mesmas premissas do Model Builder"], "recomendacao": "APROVADO", "vies": "COMPRADOR",
                "tese": "Premissas de WACC e crescimento compatíveis com o setor; DCF validado.",
                "pros": ["Premissas dentro do intervalo histórico do setor"], "contras": [],
                "limitacoes": ["Sensibilidade não recalculada neste mock."],
                "dcf": {"disponivel": True, "moeda": "R$", "fonte_premissas": "Model Builder", "data_base": "2026-09-30",
                        "premissas": {"fcf_base": 42_000_000_000, "divida_liquida": 180_000_000_000, "acoes": 12_980_000_000,
                                      "crescimento_fcf_otimista": 0.07, "crescimento_fcf_base": 0.04, "crescimento_fcf_pessimista": 0.01,
                                      "wacc": 0.11, "g_terminal": 0.03},
                        "cenarios": {"otimista": {"rotulo": "OTIMISTA", "preco_alvo": 48.10, "upside_pct": 31.7, "crescimento_fcf": 0.07, "wacc": 0.10, "g_terminal": 0.035},
                                     "base": {"rotulo": "BASE", "preco_alvo": 42.80, "upside_pct": 17.2, "crescimento_fcf": 0.04, "wacc": 0.11, "g_terminal": 0.03},
                                     "pessimista": {"rotulo": "PESSIMISTA", "preco_alvo": 37.50, "upside_pct": 2.7, "crescimento_fcf": 0.01, "wacc": 0.125, "g_terminal": 0.025}}},
                "preco_alvo": 42.80, "upside_pct": 17.2,
            },
        ],
        "casas_research": [
            {"casa": "XP", "titulo": "Petrobras: mantemos compra", "link": "https://exemplo.com/xp-petr4", "recomendacao": "COMPRA", "preco_alvo": 44.0, "upside_pct": 20.5, "data_publicacao": "2026-11-05", "tese": ["Disciplina de capital"], "contras": ["Risco político"], "projecoes": {"ebitda_2027": "R$ 210 bi"}},
            {"casa": "Genial", "titulo": "PETR4: valuation ainda descontado", "link": "https://exemplo.com/genial-petr4", "recomendacao": "COMPRA", "preco_alvo": 40.0, "upside_pct": 9.5, "data_publicacao": "2026-10-28", "tese": ["Dividendos elevados"], "contras": [], "projecoes": {}},
            {"casa": "BTG Pactual", "titulo": "Petrobras: neutros no curto prazo", "link": "https://exemplo.com/btg-petr4", "recomendacao": "NEUTRO", "preco_alvo": 39.5, "upside_pct": 8.2, "data_publicacao": "2026-10-20", "tese": [], "contras": ["Possível revisão de guidance"], "projecoes": {}},
        ],
    },
    "conclusao": [
        "Comitê recomenda COMPRA com confiança ALTA — 4 de 4 especialistas concluíram com dados suficientes.",
        "Upside modelado (17,2%) é inferior ao consenso das casas (20,5% na mais otimista), diferença atribuível a premissas de WACC mais conservadoras.",
    ],
    "pontos_atencao": ["Earnings Reviewer ficou NEUTRO — resultado do 3T26 sem catalisador novo relevante."],
    "divergencias": {"cross_comparador_memoria": {"divergencias": [
        {"casa": "BTG Pactual", "tipo": "recomendação", "campo": "recomendacao", "comparador": "NEUTRO", "memoria_research": "COMPRA"},
    ]}},
    "evidencias": [
        {"especialista": "market_researcher", "fonte": "yfinance", "data": "2026-11-11", "titulo": "Indicadores fundamentalistas coletados"},
        {"especialista": "earnings_reviewer", "fonte": "Release 3T26", "data": "2026-11-05", "titulo": "Resultado trimestral revisado"},
    ],
    "visao_especialistas": {
        "market_researcher": {"disponivel": True, "resumo": "Indicadores coletados com sucesso."},
        "catalisadores": {"disponivel": False, "motivo_indisponivel": "não acionado nesta análise"},
    },
}


def _ir():
    if ABA == "visao_geral":
        coord.render_visao_geral({})
    elif ABA == "especialistas":
        coord.render_especialistas({})
    elif ABA == "execucoes":
        coord.render_execucoes({})
    elif ABA == "historico":
        coord._injetar_css()
        st.markdown('<div class="painel-titulo">HISTÓRICO DE ANÁLISES</div>', unsafe_allow_html=True)
        st.markdown(
            "**Solicitação:** Análise de ticker — PETR4  \n"
            "**Fluxo:** analise_ticker · **Ticker:** PETR4  \n"
            f"**Início:** {_ANALISES[0]['iniciado_em'][:10]} · **Duração:** 8.4s · " + coord._badge_status("CONCLUIDA"),
            unsafe_allow_html=True,
        )
        coord._render_consolidado(_CONSOLIDADO)
    else:
        raise SystemExit(f"aba desconhecida: {ABA}")


from unittest.mock import patch

with patch.object(coord, "listar_especialistas", return_value=_ESPECIALISTAS), \
     patch.object(coord.persistencia, "metricas_especialistas", return_value=_METRICAS), \
     patch.object(coord.persistencia, "listar_analises_recentes", return_value=_ANALISES), \
     patch.object(coord.execucoes_agendadas, "listar_ultimas_execucoes", return_value=_EXECUCOES_AGENDADAS), \
     patch.object(coord, "obter_nome_yf", return_value=None):
    _ir()
