# Harness visual LOCAL (sem login/auth) de ANÁLISES > Visão 360
# (ui/visao_360_tab.py:render_visao_360), missão visao-360-redesign-20261126.
#
# Mesmo padrão dos harnesses anteriores deste diretório (ver
# docs/evidencias/validacao-visual-real-20261117/harness_mercado_fix.py):
# carrega style.css + as variáveis CSS do tema AMBAR igual app.py faz, mocka
# TODAS as fontes de rede/Supabase com dado realista e renderiza a tela de
# verdade, pra inspeção com Playwright em larguras diferentes.
#
# Por que harness e não o app inteiro: app.py exige login Google real e
# credenciais de produção (Supabase/Groq), que o worktree de uma sessão de
# agente não tem. O que está sendo validado aqui é LAYOUT/CSS/overflow da
# tela redesenhada - e o markup renderizado é exatamente o mesmo do app.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.coordenador_tab as coord
import ui.news_tab as news
import ui.visao_360_tab as v360

st.set_page_config(page_title="harness visao 360", layout="wide")
with open(config.BASE_DIR / "style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

tema = config.TEMAS["AMBAR"]
st.markdown(
    f"<style>:root {{"
    f"--bg:{tema['fundo']}; --grafite:{tema['grafite']}; --painel-bg:{tema['painel']}; "
    f"--borda:{tema['borda']}; --destaque:{tema['destaque']}; --alta:{tema['alta']}; "
    f"--baixa:{tema['baixa']}; --neutro:{tema['neutro']}; --cinza:{tema['cinza']}; "
    f"--ciano:{tema['ciano']}; --padding-painel:0.4rem; --fonte-base:0.9rem;}}</style>"
    "<style>body{background:var(--bg);} .stApp{background:var(--bg);}</style>",
    unsafe_allow_html=True,
)

PREFS = dict(config.PREFS_PADRAO)
PREFS["watchlist"] = ["PETR4", "VALE3", "ITUB4", "WEGE3", "BBAS3", "PRIO3"]

_COT = {
    "ticker": "PETR4", "preco": 38.52, "fechamento_anterior": 37.91,
    "cotacao_em": "2026-11-26T18:02:00+00:00",
    "tipo_cotacao": "ATRASADA (Yahoo Finance; atraso pode variar)",
    "variacao": 0.61, "variacao_pct": 1.61, "maxima_dia": 38.94, "minima_dia": 37.80,
    "volume": 48_120_300, "maxima_52s": 42.18, "minima_52s": 30.04, "erro": None,
}

_LINHA = {
    "ticker": "PETR4", "setor": "Petróleo e Gás", "moeda": "R$", "moeda_fonte": "BRL",
    "preco": 38.52, "preco_erro": None, "consultado_em": "2026-11-26T18:02:00+00:00",
    "pl": 6.21, "pvp": 1.12, "dividend_yield": 12.44, "roe": 24.31, "margem_liquida": 18.02,
    "divida_liquida_ebitda": 1.21, "valor_mercado": 503_400_000_000.0,
    "ebitda": 151_200_000_000.0, "ev_ebitda": 4.52, "divida_liquida": 182_600_000_000.0,
    "fluxo_caixa_livre": 94_200_000_000.0, "desatualizado": False,
    "alerta_qualidade": ["dívida líquida/EBITDA elevada (4.2x)"],
}

_INDICADORES = {
    "valor_mercado": 503_400_000_000.0, "moeda_fonte": "BRL", "pl": 6.21, "pvp": 1.12,
    "dividend_yield": 12.44, "beta": 1.08, "roe": 24.31, "margem_liquida": 18.02,
    "margem_operacional": 27.46, "margem_ebitda": 41.23,
    "divida_liquida": 182_600_000_000.0, "divida_liquida_ebitda": 1.21,
    "ebitda": 151_200_000_000.0, "fluxo_caixa_livre": 94_200_000_000.0,
}

from datetime import date, datetime, timezone  # noqa: E402

_CONTEXTO = {
    "ticker": "PETR4", "gerado_em": datetime.now(timezone.utc),
    "catalisadores": [
        {"ticker": "PETR4", "categoria": "Resultado trimestral", "data": date(2026, 12, 12),
         "confirmado": True, "status_label": "confirmado em fato relevante"},
        {"ticker": "PETR4", "categoria": "Proventos (data com)", "data": date(2027, 1, 8),
         "confirmado": False, "status_label": "estimado/prazo regulatório"},
    ],
    "mudancas": [
        {"ticker": "PETR4", "categoria": "Fato relevante", "data_evento": date(2026, 11, 20),
         "descricao": "Companhia comunica revisão do plano de investimentos 2027-2031, com corte "
                      "de capex em exploração e produção.",
         "fonte_url": "https://exemplo.cvm/fato", "fonte_label": "CVM — fato relevante"},
    ],
    "riscos": ["dívida líquida/EBITDA elevada (4.2x)"],
    "interpretacao": None,
}

_EVID = [
    {"casa": "Genial", "texto": "Preço do Brent acima de US$ 78 sustenta geração de caixa no 4T.",
     "data_publicacao": "2026-11-18", "link": "https://exemplo.casa/genial"},
    {"casa": "BTG", "texto": "Risco de interferência em política de preços segue como principal "
                             "fator de desconto do múltiplo.",
     "data_publicacao": "2026-11-14", "link": None},
]

_PERFIL = {
    "identificacao": {"setor": "Petróleo e Gás", "industria": "Oil & Gas Integrated",
                      "pais": "Brasil", "disponivel": True},
    "noticias_disponivel": True,
    "noticias_recentes": [
        {"titulo": "Petrobras aprova plano de negócios com corte de capex",
         "data": "2026-11-25", "selo": "CONFIRMADA", "link": "https://exemplo.news/1"},
    ],
    "perguntas": {
        "o_que_a_empresa_faz": {
            "dado": "Companhia integrada de energia: explora, produz, refina e comercializa "
                    "petróleo e gás natural, com operação concentrada no pré-sal brasileiro e "
                    "exportação relevante de óleo bruto para Ásia e Europa.",
            "disponivel": True, "motivo_indisponivel": None},
        "perspectivas": {"disponivel": True, "evidencias": _EVID, "motivo_indisponivel": None},
        "pressoes_de_margem": {
            "disponivel": False,
            "motivo_indisponivel": "Nenhum relatório monitorado tratou de pressão de margem para "
                                   "este ticker nos últimos 90 dias."},
        "riscos": {"disponivel": True, "evidencias": _EVID[1:], "motivo_indisponivel": None},
        "o_que_quebraria_a_tese": {
            "disponivel": True, "evidencias": _EVID[1:],
            "dado": {"divergencia_entre_casas": [
                {"premissa": "preço do Brent acima de US$ 75 em 2027",
                 "casas_que_mencionam": ["Genial"], "casas_que_nao_mencionam": ["BTG", "Safra"]},
            ]},
            "motivo_indisponivel": None},
        "posicao_competitiva": {"disponivel": True, "evidencias": _EVID[:1],
                                "motivo_indisponivel": None},
        "vantagens_competitivas": {
            "disponivel": False,
            "motivo_indisponivel": "Nenhuma publicação monitorada descreveu vantagens "
                                   "competitivas deste ticker."},
        "concorrentes": {"disponivel": False,
                         "motivo_indisponivel": "Comparáveis não citados nas publicações monitoradas."},
    },
    "research": {
        "disponivel": True,
        "casas": ["Genial", "BTG", "Safra"],
        "dispersao_precos_alvo": {"minimo": 42.0, "mediana": 46.5, "maximo": 52.0,
                                  "moeda": "BRL", "amostra_insuficiente": False,
                                  "resumo": "3 casas com preço-alvo publicado nos últimos 90 dias."},
        "divergencia_recomendacao": {"numerica": True, "qualitativa": False,
                                     "n_casas_com_preco_alvo": 3,
                                     "casa_mais_otimista": "Genial", "casa_mais_cautelosa": "BTG",
                                     "criterio_otimismo": "maior preço-alvo publicado"},
        "evolucao_historica": {"Genial": {"mudou_recomendacao_ou_alvo_hoje": True}},
    },
}

_MODEL_BUILDER = {
    "id": "model_builder", "nome": "Model Builder — Modelagem e DCF",
    "recomendacao": "MODELADO", "especialidade": "Modelagem financeira e fluxo de caixa descontado",
    "metodo": "DCF de 5 anos + Gordon Growth, líquido de dívida.",
    "vies": "CONSTRUTIVO", "moeda": "R$", "data_base": "2026-11-24",
    "tese": "Modelo construído com premissas explícitas do Comitê.",
    "fontes": ["yfinance", "CVM/ITR"],
    "premissas": {"fcf_base": 94_200_000_000.0, "divida_liquida": 182_600_000_000.0,
                  "acoes": 13_044_000_000.0, "wacc": 0.124, "g_terminal": 0.035,
                  "crescimento_fcf_pessimista": 0.01, "crescimento_fcf_base": 0.035,
                  "crescimento_fcf_otimista": 0.06,
                  "origem_divida_liquida": "yfinance — totalDebt - totalCash"},
    "cenarios": {
        "pessimista": {"preco_alvo": 41.8, "upside_pct": 8.5, "crescimento_fcf": 0.01,
                       "wacc": 0.124, "g_terminal": 0.035, "valor_empresa": 7.3e11,
                       "valor_patrimonio": 5.45e11},
        "base": {"preco_alvo": 52.0, "upside_pct": 35.0, "crescimento_fcf": 0.035,
                 "wacc": 0.124, "g_terminal": 0.035, "valor_empresa": 8.6e11,
                 "valor_patrimonio": 6.78e11},
        "otimista": {"preco_alvo": 63.4, "upside_pct": 64.6, "crescimento_fcf": 0.06,
                     "wacc": 0.124, "g_terminal": 0.035, "valor_empresa": 1.01e12,
                     "valor_patrimonio": 8.27e11},
    },
    "sensibilidade": {"disponivel": False, "motivo": "não calculada nesta execução."},
}

_ANALISTAS = [
    {"id": "market_researcher", "nome": "Market Researcher — Analista de Empresas",
     "recomendacao": "COMPRA", "vies": "CONSTRUTIVO",
     "especialidade": "Fundamentos, qualidade do negócio, crescimento e riscos",
     "metodo": "Síntese heurística dos sinais observáveis, sem gerar fatos por IA.",
     "tese": "Múltiplos descontados contra o próprio histórico, com geração de caixa robusta e "
             "dívida sob controle; o desconto parece ligado a risco de governança, não a "
             "deterioração operacional.",
     "pros": ["ROE de 24,3% acima da mediana do setor", "FCF de R$ 94,2 bi no TTM"],
     "contras": ["Dividend yield depende de política de distribuição sujeita a mudança"],
     "fontes": ["Market Researcher", "Valuation Radar", "Earnings Reviewer/CVM"],
     "indicadores": {"moeda": "R$", "roe_pct": 24.31, "margem_liquida_pct": 18.02,
                     "divida_liquida_ebitda_x": 1.21, "fluxo_caixa_livre": 94_200_000_000.0,
                     "pl_x": 6.21, "pl_mediana_setor_x": 8.90,
                     "roic_trimestral_pct": 4.12, "receita_liquida_yoy_pct": 6.8}},
    {"id": "earnings_reviewer", "nome": "Earnings Reviewer — Analista de Resultados",
     "recomendacao": "NEUTRO", "vies": "NEUTRO",
     "especialidade": "DRE, balanço, fluxo de caixa e evolução trimestral",
     "metodo": "Leitura determinística das demonstrações da CVM (ITR).",
     "tese": "Receita líquida cresce 6,8% YoY com margem estável; capex em queda sustenta o FCF.",
     "pros": ["Margem bruta estável por 4 trimestres"],
     "contras": ["EBIT do 4T não isolado pela CVM"],
     "limitacoes": ["Série trimestral cobre apenas empresas brasileiras."],
     "fontes": ["CVM/ITR"]},
    _MODEL_BUILDER,
    {"id": "valuation_comparables", "nome": "Valuation — Comparáveis", "recomendacao": "COMPRA",
     "vies": "CONSTRUTIVO", "especialidade": "Múltiplos relativos contra pares do setor",
     "metodo": "P/L e EV/EBITDA contra a mediana do setor (universo Ibovespa).",
     "tese": "Negocia a 6,2x lucro contra mediana setorial de 8,9x.",
     "pros": ["Desconto de 30% no P/L relativo"], "contras": []},
    {"id": "valuation_reviewer", "nome": "Valuation Reviewer — Revisão independente",
     "recomendacao": "COM RESSALVAS", "vies": "CAUTELOSO",
     "especialidade": "Revisão independente do DCF do Model Builder",
     "metodo": "Reexecução do motor com as mesmas premissas.",
     "tese": "Cenários consistentes, com ressalva na taxa de crescimento perpétuo.",
     "achados": [{"tipo": "PREMISSA", "descricao": "g terminal de 3,5% acima da inflação de longo "
                                                   "prazo implícita nas NTN-B."}],
     "limitacoes": ["Sensibilidade não recalculada nesta execução."],
     "preco_alvo": 52.0, "upside_pct": 35.0, "preco_atual": 38.52,
     "dcf": {"disponivel": False, "motivo": "Revisão usa os cenários do Model Builder.",
             "campos_faltantes": []}},
]

_CONSOLIDADO = {
    "ticker": "PETR4",
    "sinal_comite": {
        "sinal": "COMPRA", "score": 7, "preco_atual": 38.52,
        "justificativa": "Pontuação positiva em ROE, margem, FCF e P/L relativo; dívida dentro do "
                         "limite tolerado pelo modelo.",
        "preco_alvo_modelo": 52.0, "upside_modelo_pct": 35.0,
        "preco_alvo_pl_setorial": 44.2, "preco_alvo_consenso": 46.5,
        "moeda_preco_alvo_modelo": "R$", "preco_atual_consultado_em": "2026-11-24T12:00:00+00:00",
    },
    "confianca": {"categoria": "BAIXA",
                  "justificativa": "Apenas 2 dos 5 especialistas trouxeram evidência externa "
                                   "datada; série histórica cobre 4 trimestres."},
    "resumo_executivo": "O Comitê recomenda COMPRA para PETR4 com base em múltiplos descontados e "
                        "geração de caixa, mas a confiança é baixa: a cobertura de research externa "
                        "é rasa e o DCF depende de premissas não confirmadas por terceiros.",
    "pareceres_analistas": {
        "analistas": _ANALISTAS,
        "casas_research": [
            {"casa": "Genial", "recomendacao": "COMPRA", "preco_alvo": 52.0, "upside_pct": 35.0,
             "data_publicacao": "2026-11-18", "titulo": "Petrobras: pré-sal sustenta o caixa",
             "link": "https://exemplo.casa/genial",
             "tese": ["Brent acima de US$ 78"], "contras": ["Risco regulatório"],
             "projecoes": {"receita_2027": "R$ 520 bi"}},
            {"casa": "BTG", "recomendacao": "NEUTRO", "preco_alvo": 42.0, "upside_pct": 9.0,
             "data_publicacao": "2026-11-14", "titulo": "Petrobras: desconto justificado",
             "link": None, "tese": [], "contras": ["Interferência em preços"], "projecoes": {}},
        ],
        "preco_alvo_consenso": {"mediana": 46.5, "upside_pct": 20.7, "n_casas": 3},
    },
    "divergencias": {
        "entre_analistas_comite": {
            "divergente": True, "n_analistas_comparados": 3,
            "resumo": "Market Researcher e Valuation (Comparáveis) indicam COMPRA; Earnings "
                      "Reviewer fica NEUTRO por falta de EBIT isolado no 4T.",
        },
        "cross_comparador_memoria": {"divergencias": [
            {"casa": "Safra", "tipo": "preco_alvo", "campo": "preco_alvo",
             "comparador": "48.0", "memoria_research": "45.0"},
        ]},
    },
    "pontos_atencao": [
        "Dividend yield de 12,4% depende de política de distribuição revisável a cada trimestre.",
        "Premissa de crescimento perpétuo acima da inflação implícita de longo prazo.",
    ],
    "conclusao": [
        "[FATO] Receita líquida cresceu 6,8% YoY no trimestre mais recente reportado à CVM.",
        "[CÁLCULO INTERNO] P/L de 6,2x contra mediana setorial de 8,9x.",
        "[DADO INSUFICIENTE] EV/EBIT não calculado: EBIT trimestral isolado não cobre o 4T.",
    ],
    "evidencias": [
        {"especialista": "market_researcher", "fonte": "Valuation Radar", "data": "2026-11-24",
         "titulo": "Múltiplos atuais do ticker (yfinance)"},
        {"especialista": "earnings_reviewer", "fonte": "CVM/ITR", "data": "2026-11-10",
         "titulo": "Demonstrações do 3T26"},
    ],
    "visao_especialistas": {
        "market_researcher": {"disponivel": True, "resumo": "Fundamentos coletados."},
        "earnings_reviewer": {"disponivel": True, "resumo": "Série trimestral de 4 pontos."},
    },
}

_ANALISES = [
    {"id": "a1", "status": "CONCLUIDA", "iniciado_em": "2026-11-24T12:00:00+00:00",
     "resultado": _CONSOLIDADO},
    {"id": "a0", "status": "CONCLUIDA", "iniciado_em": "2026-10-30T12:00:00+00:00",
     "resultado": {"sinal_comite": {"sinal": "NEUTRO"}, "confianca": {"categoria": "MEDIA"}}},
    {"id": "aerr", "status": "ERRO", "iniciado_em": "2026-10-02T12:00:00+00:00", "resultado": None},
]

_RELATORIO_CASAS = {
    "disponivel": True,
    "resumo_executivo": "3 casas monitoradas com publicação estruturada nos últimos 90 dias.",
    "tabela_comparativa": [
        {"casa": "Genial", "data_publicacao": "2026-11-18", "tipo_documento": "Relatório de empresa",
         "recomendacao_original": "COMPRA", "recomendacao_categoria": "COMPRA", "preco_alvo": 52.0,
         "projecao_receita": "R$ 520 bi (2027)", "projecao_ebitda_margem": "41%",
         "projecao_lucro": "R$ 92 bi"},
        {"casa": "BTG", "data_publicacao": "2026-11-14", "tipo_documento": "Nota setorial",
         "recomendacao_original": "NEUTRO", "recomendacao_categoria": "NEUTRO", "preco_alvo": 42.0,
         "projecao_receita": "—", "projecao_ebitda_margem": "39%", "projecao_lucro": "—"},
        {"casa": "Safra", "data_publicacao": "2026-11-05", "tipo_documento": "Carta mensal",
         "recomendacao_original": "COMPRA", "recomendacao_categoria": "COMPRA", "preco_alvo": 48.0,
         "projecao_receita": "R$ 505 bi (2027)", "projecao_ebitda_margem": "—",
         "projecao_lucro": "R$ 88 bi"},
    ],
    "consenso": {"categoria_mais_comum": "COMPRA", "contagem_por_categoria": {"COMPRA": 2, "NEUTRO": 1},
                 "n_casas_com_recomendacao_classificada": 3, "n_casas_total": 3,
                 "amostra_insuficiente": False},
    "dispersao_precos_alvo": {"minimo": 42.0, "maximo": 52.0, "media": 47.3, "mediana": 48.0,
                              "amostra_insuficiente": False,
                              "resumo": "Dispersão de 23,8% entre o menor e o maior preço-alvo."},
    "divergencias_premissas": {
        "recomendacao": {"numerica": True, "qualitativa": True, "casa_mais_otimista": "Genial",
                         "casa_mais_cautelosa": "BTG", "criterio_otimismo": "maior preço-alvo"},
        "premissas": {"premissas_divergentes": [], "amostra_insuficiente": False},
    },
    "revisoes_recentes": {},
    "riscos": {"disponivel": False, "motivo": "Nenhum risco estruturado extraído."},
    "indicadores_adicionais": {"disponivel": True, "roe": 24.31, "roic_disponivel": False,
                               "roic_motivo": "alíquota efetiva não isolada no trimestre",
                               "riscos_mercado": []},
    "pontos_atencao": [],
    "fontes_evidencias": [
        {"casa": "Genial", "data_publicacao": "2026-11-18",
         "titulo": "Petrobras: pré-sal sustenta o caixa", "link": "https://exemplo.casa/genial"},
        {"casa": "BTG", "data_publicacao": "2026-11-14",
         "titulo": "Petrobras: desconto justificado", "link": "https://exemplo.casa/btg"},
    ],
}

# Shape REAL de data/news.py:obter_noticias (ticker/titulo/titulos/veiculos/
# fontes/fontes_count/data/link/score/selo/regras/cvm_confirmacao/tickers) -
# a lista densa de ui/news_tab.py lê score e regras (tooltip do selo), então
# um mock sem essas chaves estoura KeyError dentro do @st.fragment e o
# Streamlit desenha o traceback no lugar da lista (foi o que aconteceu na
# 1ª rodada de captura; o erro era do mock, não da tela).
_NOTICIAS = [
    {"ticker": "PETR4",
     "titulo": "Petrobras aprova plano de negócios 2027-2031 com corte de capex em E&P",
     "titulos": ["Petrobras aprova plano de negócios 2027-2031"],
     "veiculos": ["Valor", "InfoMoney", "Broadcast", "Reuters"],
     "fontes": [{"veiculo": "Valor", "link": "https://exemplo.news/1"},
                {"veiculo": "InfoMoney", "link": "https://exemplo.news/1b"}],
     "fontes_count": 4, "data": "2026-11-26T11:20:00+00:00", "link": "https://exemplo.news/1",
     "score": 92, "selo": "CONFIRMADA", "regras": ["veículo de alta confiabilidade", "4 veículos"],
     "cvm_confirmacao": {"documento": "Fato relevante"}, "tickers": ["PETR4"]},
    {"ticker": "PETR4", "titulo": "Brent recua com estoques americanos acima do esperado",
     "titulos": ["Brent recua com estoques americanos acima do esperado"],
     "veiculos": ["Reuters"], "fontes": [{"veiculo": "Reuters", "link": "https://exemplo.news/2"}],
     "fontes_count": 1, "data": "2026-11-26T09:05:00+00:00", "link": "https://exemplo.news/2",
     # "NÃO CONFIRMADA" COM acento: é a chave real de ui/news_tab.py:
     # _SELO_ABREV ("N.CONF"). Sem o acento o selo cai no texto completo e
     # estoura a coluna estreita da lista (visto na 1ª captura - de novo,
     # defeito do mock, não da tela).
     "score": 48, "selo": "NÃO CONFIRMADA", "regras": ["apenas 1 veículo"],
     "cvm_confirmacao": None, "tickers": ["PETR4"]},
    {"ticker": "PETR4", "titulo": "Conselho aprova distribuição extraordinária de dividendos",
     "titulos": ["Conselho aprova distribuição extraordinária de dividendos"],
     "veiculos": ["Broadcast", "Valor", "Estadão"],
     "fontes": [{"veiculo": "Broadcast", "link": "https://exemplo.news/3"}],
     "fontes_count": 3, "data": "2026-11-25T18:40:00+00:00", "link": "https://exemplo.news/3",
     "score": 85, "selo": "CONFIRMADA", "regras": ["3 veículos", "linguagem factual"],
     "cvm_confirmacao": None, "tickers": ["PETR4"]},
]


# A "fita" de ticker da tela real (app.py, rota analises/panorama) faz parte
# do que está sendo validado - reproduzida aqui com o mesmo container/chave.
with st.container(key="v360_fita_ticker"):
    ticker = st.segmented_control(
        "Ticker", PREFS["watchlist"], default="PETR4",
        label_visibility="collapsed", key="ticker_selecionado",
    ) or "PETR4"

with patch.object(v360, "obter_cotacao", return_value=_COT), \
     patch.object(v360, "obter_indicadores", return_value=_INDICADORES), \
     patch.object(v360, "linha_valuation", return_value=_LINHA), \
     patch.object(v360, "_contexto_cacheado", return_value=_CONTEXTO), \
     patch.object(v360, "listar_analises_por_ticker", return_value=_ANALISES), \
     patch.object(v360, "obter_analise", return_value=_ANALISES[0]), \
     patch.object(v360, "comparativo_casas_cacheado", return_value=_RELATORIO_CASAS), \
     patch.object(coord, "obter_perfil_empresa", return_value=_PERFIL), \
     patch.object(coord, "obter_nome_yf", return_value="Petróleo Brasileiro S.A. — Petrobras"), \
     patch.object(news, "obter_noticias", return_value=_NOTICIAS), \
     patch.object(news, "obter_resumos_prontos", return_value={}):
    v360.render_visao_360(ticker, PREFS)
