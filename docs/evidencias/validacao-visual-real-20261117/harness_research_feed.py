# Harness visual LOCAL (sem login/auth/Supabase/rede real) - Fase 4
# (revalidacao pos-reestruturacao, 2026-11-18): RESEARCH > Feed
# (ui/research_tab.py:render_research) - subaba "Feed" de RESEARCH, que
# agora tem 9 subabas no total (Morning Call absorvido, PR #329). Esta
# subaba NUNCA tinha screenshot salvo nesta pasta (a captura "fresco" da
# sessao anterior, 2026-11-17, foi de "Casas de Analise" - ver
# harness_research.py - subaba diferente). Reaproveita o MESMO mock de
# relatorios de harness_research.py (_RELATORIOS), mesmo padrao de todos
# os harnesses desta pasta: chama o PONTO DE ENTRADA real
# (render_research), com toda funcao de dado que bateria em
# Supabase/rede real monkeypatchada - zero dado real, zero chamada de
# rede/IA de verdade.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.research_tab as research

st.set_page_config(page_title="harness research - feed", layout="wide")
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

PREFS = dict(config.PREFS_PADRAO)
PREFS["watchlist"] = ["PETR4", "VALE3", "WEGE3"]
PREFS["research_casas_ativas"] = ["genial", "xp"]

# Mesmo conteudo de harness_research.py (_RELATORIOS) - todo item com
# "resumo" ja preenchido (nunca None), de proposito: evita qualquer
# tentativa real de _linha_relatorio/obter_resumo tentar resumir ao vivo
# (permitir_resumo_auto=True no painel da watchlist).
_RELATORIOS = [
    {
        "casa": "Genial", "tipo": "ACOES", "titulo": "Petrobras: mantemos recomendação de COMPRA após 3T26",
        "link": "https://exemplo.com/genial-petr4-3t26", "data": "2026-11-15", "autor": "Equipe Genial Analisa",
        "tickers": ["PETR4"], "recomendacao": "COMPRA", "preco_alvo": 44.0,
        "resumo": "RESUMO:\nA Petrobras reportou EBITDA acima do consenso no 3T26, com disciplina de capital "
                   "mantida e dívida líquida/EBITDA estável em 1,1x. Mantemos preço-alvo de R$ 44,00 e "
                   "recomendação de COMPRA, com upside de 20,5% sobre a cotação atual.",
    },
    {
        "casa": "Genial", "tipo": "ACOES", "titulo": "WEGE3: resultado em linha, sem catalisador novo no curto prazo",
        "link": "https://exemplo.com/genial-wege3-3t26", "data": "2026-11-10", "autor": "Equipe Genial Analisa",
        "tickers": ["WEGE3"], "recomendacao": "MANTER", "preco_alvo": 52.0,
        "resumo": "RESUMO:\nResultado do 3T26 da WEG veio em linha com o consenso, com margem EBITDA estável "
                   "em 19,8%. Mantemos recomendação NEUTRA (MANTER) com preço-alvo de R$ 52,00.",
    },
    {
        "casa": "XP", "tipo": "ACOES", "titulo": "VALE3: elevamos preço-alvo após guidance de cobre",
        "link": "https://exemplo.com/xp-vale3-cobre", "data": "2026-11-13", "autor": "Mesa de Research XP",
        "tickers": ["VALE3"], "recomendacao": "COMPRA", "preco_alvo": 78.0,
        "resumo": "RESUMO:\nA Vale elevou o guidance de produção de cobre para 2027, com ramp-up mais rápido em "
                   "Carajás. Elevamos preço-alvo para R$ 78,00, mantendo recomendação de COMPRA.",
    },
    {
        "casa": "XP", "tipo": "MACRO", "titulo": "Cenário macro: Copom deve manter Selic em 12,25% até fevereiro",
        "link": "https://exemplo.com/xp-macro-copom-fev", "data": "2026-11-08", "autor": "Economia XP",
        "tickers": [], "recomendacao": None, "preco_alvo": None,
        "resumo": "RESUMO:\nA mesa de economia da XP projeta manutenção da Selic em 12,25% na reunião de "
                   "fevereiro, citando inflação de serviços ainda acima da meta.",
    },
]

with patch.object(research, "_casas_ativas", return_value=["genial", "xp"]), \
     patch.object(research, "preparar_leitura", return_value=(_RELATORIOS, [], [], None)), \
     patch.object(research, "ultimas_coletas_formatadas", return_value="Genial há 2h · XP há 17d"), \
     patch.object(research, "obter_recomendacoes", return_value=[]), \
     patch.object(research, "obter_swing_trade", return_value=[]), \
     patch.object(research, "mudancas_hoje", return_value=[]), \
     patch.object(research, "processar_recomendacoes", return_value=[]), \
     patch.object(research, "_ultimo_snapshot_cacheado", return_value=None), \
     patch.object(research, "obter_resumo", return_value={"resumo": None, "motivo_indisponivel": "indisponivel"}), \
     patch.object(research, "obter_noticias", return_value=[]), \
     patch.object(research, "coletar_pendentes", return_value=[]):
    research.render_research(PREFS)
