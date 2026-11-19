# Harness visual LOCAL (sem login/auth/Supabase/rede real) para validar o
# painel novo "Perfil da empresa - resumo do negocio e momento atual"
# dentro do COMITE DE ANALISE (missao perfil-empresa-ui-20261118, pedido
# literal do Rodrigo: "...gostaria de um resumo da historia e do momento
# que ela esta passando"). Mesmo padrao de
# docs/evidencias/validacao-visual-real-20261117/harness_coordenador.py
# (chama _render_consolidado direto, com um "consolidado" mockado
# REALISTA) + o truque de harness_dcf.py pra forcar o expander novo a
# abrir expandido (expanded=True so' aqui no harness, nunca em
# ui/coordenador_tab.py) - sem isso a screenshot mostraria o painel
# fechado, sem conteudo.
#
# obter_perfil_empresa (data/empresa_perfil.py) e' mockada com dados
# REPRESENTATIVOS de PETR4 (nunca dado real de producao) - o shape e'
# exatamente o que a funcao real devolve (ver docstring do modulo).
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.coordenador_tab as coord

st.set_page_config(page_title="harness comite - perfil da empresa", layout="wide")
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

# Monkeypatch SO' do harness: forca TODOS os expanders a abrir
# expandidos, pra screenshot mostrar o conteudo do painel novo (e dos
# outros expanders da pagina) sem depender de clique real num app
# headless (mesmo truque de harness_dcf.py).
_orig_expander = st.expander


def _expander_sempre_aberto(*args, **kwargs):
    kwargs["expanded"] = True
    return _orig_expander(*args, **kwargs)


st.expander = _expander_sempre_aberto

AGORA = datetime.now(timezone.utc)

# ============================================================
# Perfil da empresa mockado (shape real de
# data/empresa_perfil.py:obter_perfil_empresa) - texto representativo
# de PETR4, nunca dado vazio, pra evidencia visual mostrar conteudo de
# verdade.
# ============================================================
_PERFIL_PETR4 = {
    "ticker": "PETR4",
    "gerado_em": AGORA.isoformat(),
    "identificacao": {
        "setor": "Energy", "industria": "Oil & Gas Integrated", "pais": "Brazil",
        "website": "https://petrobras.com.br", "funcionarios": 45000,
        "resumo_negocio": (
            "Petrobras é uma das maiores produtoras de petróleo e gás do Brasil, atuando em toda a "
            "cadeia de exploração, produção, refino, transporte, distribuição e comercialização de "
            "petróleo, gás natural e derivados, com forte presença no pré-sal e operações relevantes "
            "no exterior."
        ),
        "fonte": "yfinance (tk.info)", "consultado_em": (AGORA - timedelta(hours=1)).isoformat(), "disponivel": True,
    },
    "indicadores_fundamentalistas": {"moeda": "R$", "roe": 18.4, "margem_liquida": 21.0},
    "research": {
        "disponivel": True, "motivo": None, "casas": ["BTG", "XP", "Genial"],
        "indicadores_adicionais": None, "dispersao_precos_alvo": None,
        "divergencia_recomendacao": None, "divergencia_premissas": None, "evolucao_historica": None,
    },
    "noticias_recentes": [
        {"titulo": "Petrobras anuncia novo plano de investimentos para o pré-sal até 2030",
         "data": (AGORA - timedelta(days=2)).strftime("%Y-%m-%d"), "link": "https://exemplo.com/petr4-1",
         "selo": "CONFIRMADA", "veiculos": ["Valor Econômico"]},
        {"titulo": "Petrobras eleva produção de óleo no 4T26 e supera guidance",
         "data": (AGORA - timedelta(days=5)).strftime("%Y-%m-%d"), "link": "https://exemplo.com/petr4-2",
         "selo": "PROVÁVEL", "veiculos": ["InfoMoney"]},
        {"titulo": "Governo discute nova política de preços para combustíveis",
         "data": (AGORA - timedelta(days=9)).strftime("%Y-%m-%d"), "link": "https://exemplo.com/petr4-3",
         "selo": "MENÇÃO", "veiculos": ["Reuters Brasil"]},
    ],
    "noticias_disponivel": True,
    "perguntas": {
        "o_que_a_empresa_faz": {
            "pergunta": "O que a empresa faz?", "fonte_primaria": "yfinance (resumo institucional)",
            "dado": (
                "Petrobras é uma das maiores produtoras de petróleo e gás do Brasil, atuando em toda a "
                "cadeia de exploração, produção, refino, transporte, distribuição e comercialização de "
                "petróleo, gás natural e derivados, com forte presença no pré-sal e operações relevantes "
                "no exterior."
            ),
            "evidencias": [], "disponivel": True, "motivo_indisponivel": None,
        },
        "como_ganha_dinheiro": {
            "pergunta": "Como a empresa ganha dinheiro?", "fonte_primaria": "yfinance (resumo institucional)",
            "dado": "mesmo resumo institucional acima", "evidencias": [], "disponivel": True,
            "motivo_indisponivel": None,
        },
        "perspectivas": {
            "pergunta": "Quais são as perspectivas para a empresa?",
            "fonte_primaria": "research (projeções de receita/margem/lucro por casa)",
            "dado": ["Projeção de crescimento de receita de 8% em 2027, puxado pelo aumento de produção no pré-sal."],
            "evidencias": [
                {"casa": "BTG", "texto": "Projeção de crescimento de receita de 8% em 2027, puxado pelo aumento de produção no pré-sal.",
                 "data_publicacao": (AGORA - timedelta(days=6)).strftime("%Y-%m-%d"), "link": "https://exemplo.com/btg-petr4"},
                {"casa": "XP", "texto": "Expectativa de manutenção de dividendos elevados no curto prazo, sustentada por geração de caixa robusta.",
                 "data_publicacao": (AGORA - timedelta(days=10)).strftime("%Y-%m-%d"), "link": "https://exemplo.com/xp-petr4"},
            ],
            "disponivel": True, "motivo_indisponivel": None,
        },
        "pressoes_de_margem": {
            "pergunta": "Quais são as pressões sobre a margem da empresa?",
            "fonte_primaria": "yfinance (margens atuais) + research",
            "dado": {"margens_atuais": {"margem_liquida_pct": 21.0}, "evidencias_research": [
                "Pressão de custo de insumos no refino afeta margem bruta no curto prazo.",
            ]},
            "evidencias": [
                {"casa": "Genial", "texto": "Pressão de custo de insumos no refino afeta margem bruta no curto prazo.",
                 "data_publicacao": (AGORA - timedelta(days=4)).strftime("%Y-%m-%d"), "link": None},
            ],
            "disponivel": True, "motivo_indisponivel": None,
        },
        "riscos": {
            "pergunta": "Quais são os principais riscos identificados para a empresa?",
            "fonte_primaria": "research (campo dedicado 'riscos' por casa)",
            "dado": ["Risco regulatório sobre política de preços de combustíveis.",
                     "Exposição à variação do petróleo Brent no mercado internacional."],
            "evidencias": [
                {"casa": "BTG", "texto": "Risco regulatório sobre política de preços de combustíveis.",
                 "data_publicacao": (AGORA - timedelta(days=6)).strftime("%Y-%m-%d"), "link": "https://exemplo.com/btg-petr4"},
                {"casa": "XP", "texto": "Exposição à variação do petróleo Brent no mercado internacional.",
                 "data_publicacao": (AGORA - timedelta(days=10)).strftime("%Y-%m-%d"), "link": "https://exemplo.com/xp-petr4"},
            ],
            "disponivel": True, "motivo_indisponivel": None,
        },
        "o_que_quebraria_a_tese": {
            "pergunta": "O que poderia invalidar/quebrar a tese de investimento?",
            "fonte_primaria": "research (riscos por casa + divergência entre casas)",
            "dado": {
                "riscos": ["Risco regulatório sobre política de preços de combustíveis."],
                "divergencia_entre_casas": [
                    {"premissa": "Manutenção da política de preços internacionais de combustíveis",
                     "casas_que_mencionam": ["BTG"], "casas_que_nao_mencionam": ["XP", "Genial"]},
                ],
            },
            "evidencias": [
                {"casa": "BTG", "texto": "Risco regulatório sobre política de preços de combustíveis.",
                 "data_publicacao": (AGORA - timedelta(days=6)).strftime("%Y-%m-%d"), "link": "https://exemplo.com/btg-petr4"},
            ],
            "disponivel": True, "motivo_indisponivel": None,
        },
        "posicao_competitiva": {
            "pergunta": "Qual é a posição competitiva da empresa no setor?",
            "fonte_primaria": "research (premissas/riscos por casa)",
            "dado": ["Petrobras é a maior empresa do setor de óleo e gás no Brasil, com liderança em refino."],
            "evidencias": [
                {"casa": "XP", "texto": "Petrobras é a maior empresa do setor de óleo e gás no Brasil, com liderança em refino.",
                 "data_publicacao": (AGORA - timedelta(days=10)).strftime("%Y-%m-%d"), "link": "https://exemplo.com/xp-petr4"},
            ],
            "disponivel": True, "motivo_indisponivel": None,
        },
        "vantagens_competitivas": {
            "pergunta": "Quais são as vantagens competitivas da empresa?",
            "fonte_primaria": "research (premissas/riscos por casa)",
            "dado": ["Vantagem de custo de extração no pré-sal frente a concorrentes internacionais."],
            "evidencias": [
                {"casa": "BTG", "texto": "Vantagem de custo de extração no pré-sal frente a concorrentes internacionais.",
                 "data_publicacao": (AGORA - timedelta(days=6)).strftime("%Y-%m-%d"), "link": "https://exemplo.com/btg-petr4"},
            ],
            "disponivel": True, "motivo_indisponivel": None,
        },
        "concorrentes": {
            "pergunta": "Quem são os concorrentes da empresa?",
            "fonte_primaria": "research (premissas/riscos por casa)",
            "dado": [], "evidencias": [], "disponivel": False,
            "motivo_indisponivel": (
                "nenhuma casa de research monitorada tem publicação com trecho explícito sobre este "
                "assunto na biblioteca permanente - pode ser que nenhum relatório aborde isso, ou que "
                "ainda não haja relatório coletado para este ticker"
            ),
        },
    },
}

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
        ],
        "casas_research": [
            {"casa": "XP", "titulo": "Petrobras: mantemos compra", "link": "https://exemplo.com/xp-petr4",
             "recomendacao": "COMPRA", "preco_alvo": 44.0, "upside_pct": 20.5,
             "data_publicacao": (AGORA - timedelta(days=10)).strftime("%Y-%m-%d"),
             "tese": ["Disciplina de capital"], "contras": ["Risco político"], "projecoes": {"ebitda_2027": "R$ 210 bi"}},
        ],
    },
    "conclusao": [
        "Comitê recomenda COMPRA com confiança ALTA — 4 de 4 especialistas concluíram com dados suficientes.",
    ],
    "pontos_atencao": [],
    "divergencias": {"cross_comparador_memoria": None},
    "evidencias": [],
    "visao_especialistas": {},
}


from unittest.mock import patch

with patch.object(coord, "obter_perfil_empresa", return_value=_PERFIL_PETR4), \
     patch.object(coord, "obter_nome_yf", return_value="Petrobras"):
    coord._injetar_css()
    st.markdown('<div class="painel-titulo">HISTÓRICO DE ANÁLISES</div>', unsafe_allow_html=True)
    coord._render_consolidado(_CONSOLIDADO)
