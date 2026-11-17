# Harness visual LOCAL (sem login/auth, sem Supabase real) para capturar
# evidencia visual da area RESEARCH (ui/research_tab.py) - mesmo padrao dos
# demais harnesses desta missao (docs/evidencias/agente-d-redesign-
# estrutural-20261112/harness_coordenador.py etc): chama render_casas_analise
# direto, com as funcoes de dado do modulo monkeypatchadas com valores
# mockados REALISTAS (nunca inventados na UI de produção - so aqui, pra ter
# o que mostrar no screenshot sem precisar de Supabase/Groq real).
#
# Nao havia harness salvo pra RESEARCH antes desta missao (so screenshots
# soltos em docs/evidencias/research-area-20261023/, sem o .py) - criado
# agora seguindo o padrao ja estabelecido.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.research_tab as research

st.set_page_config(page_title="harness research - casas de analise", layout="wide")
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
        "casa": "XP", "tipo": "ESTRATEGIA", "titulo": "Carteira recomendada de novembro: rotação para setores cíclicos",
        "link": "https://exemplo.com/xp-carteira-novembro", "data": "2026-11-13", "autor": "Mesa de Research XP",
        "tickers": ["VALE3", "WEGE3"], "recomendacao": None, "preco_alvo": None, "resumo": None,
    },
    {
        "casa": "Genial", "tipo": "ACOES", "titulo": "WEGE3: resultado em linha, sem catalisador novo no curto prazo",
        "link": "https://exemplo.com/genial-wege3-3t26", "data": "2026-11-10", "autor": "Equipe Genial Analisa",
        "tickers": ["WEGE3"], "recomendacao": "MANTER", "preco_alvo": 52.0,
        "resumo": "RESUMO:\nResultado do 3T26 da WEG veio em linha com o consenso, com margem EBITDA estável "
                   "em 19,8%. Mantemos recomendação NEUTRA (MANTER) com preço-alvo de R$ 52,00.",
    },
    {
        "casa": "XP", "tipo": "MACRO", "titulo": "Cenário macro: Copom deve manter Selic em 12,25% até fevereiro",
        "link": "https://exemplo.com/xp-macro-copom-fev", "data": "2026-11-08", "autor": "Economia XP",
        "tickers": [], "recomendacao": None, "preco_alvo": None, "resumo": None,
    },
    {
        "casa": "Genial", "tipo": "LIVE", "titulo": "Morning Call — 14/11/2026",
        "link": "https://exemplo.com/genial-live-20261114", "data": "2026-11-14", "autor": "Genial Analisa",
        "tickers": ["PETR4", "VALE3"], "recomendacao": None, "preco_alvo": None, "resumo": None,
    },
]

_STATUS_CASAS = [
    {
        "nome": "Genial", "fonte": "Genial Analisa (site)", "coleta_automatica_cloud": False,
        "disponivel": False, "motivo_indisponivel": "bloqueio externo persistente (Cloudflare)",
        "codigo_estado": "DADOS_DESATUALIZADOS", "rotulo_estado": "Dados desatualizados",
        "ultimo_sucesso_em": "2026-11-10T09:00:00+00:00", "registros_novos_ultima_coleta": 0,
    },
    {
        "nome": "XP", "fonte": "XP Investimentos (site)", "coleta_automatica_cloud": False,
        "disponivel": False, "motivo_indisponivel": "bloqueio externo persistente (login obrigatório)",
        "codigo_estado": "FONTE_INDISPONIVEL", "rotulo_estado": "Fonte indisponível",
        "ultimo_sucesso_em": "2026-10-29T14:20:00+00:00", "registros_novos_ultima_coleta": 0,
    },
    {
        "nome": "Genial (Lives)", "fonte": "Genial Analisa (Morning Call/vídeos)", "coleta_automatica_cloud": False,
        "disponivel": False, "motivo_indisponivel": "bloqueio externo persistente (Cloudflare)",
        "codigo_estado": "DADOS_DESATUALIZADOS", "rotulo_estado": "Dados desatualizados",
        "ultimo_sucesso_em": "2026-11-14T08:10:00+00:00", "registros_novos_ultima_coleta": 0,
    },
]


def _cobertura_mock(ticker: str) -> dict:
    if ticker == "PETR4":
        return {
            "cobertura": [{"casa": "Genial", "data": "2026-11-15", "recomendacao": "COMPRA",
                           "link": "https://exemplo.com/genial-petr4-3t26", "titulo": "Petrobras: mantemos COMPRA"}],
            "divergencia": False, "sem_cobertura": ["XP"],
        }
    return {"cobertura": [], "divergencia": False, "sem_cobertura": []}


with patch.object(research, "preparar_leitura", return_value=(_RELATORIOS, [], [], None)), \
     patch.object(research, "ultimas_coletas_formatadas", return_value="Genial há 2h · XP há 17d"), \
     patch.object(research, "obter_status_casas", return_value=_STATUS_CASAS), \
     patch.object(research, "cobertura_cruzada_casas", side_effect=_cobertura_mock), \
     patch.object(research, "_premissas_por_tickers_cacheado", return_value=[]), \
     patch.object(research, "obter_noticias", return_value=[]):
    research.render_casas_analise(PREFS)
