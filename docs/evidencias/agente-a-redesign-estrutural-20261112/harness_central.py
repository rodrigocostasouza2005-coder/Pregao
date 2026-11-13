# Harness visual LOCAL (sem login/auth, sem Supabase real) para validar a
# CENTRAL DE INTELIGÊNCIAS nova (Agente A, 2026-11-12, ui/central_
# inteligencias_tab.py) - mesmo padrão dos demais harnesses desta missão.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.central_inteligencias_tab as central
from data import ia_cache
from data.coordenador_central import persistencia

st.set_page_config(page_title="harness central de inteligencias", layout="wide")
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

_METRICAS = {
    "comparador": {"total_execucoes": 42, "sucessos": 42, "taxa_sucesso_pct": 100.0,
                   "taxa_sucesso_recente_pct": 100.0, "n_execucoes_recentes_consideradas": 10,
                   "tempo_medio_ms": 410.2, "ultima_execucao_em": "2026-11-12T18:02:00+00:00",
                   "ultimo_erro_tecnico": None},
    "memoria_research": {"total_execucoes": 15, "sucessos": 11, "taxa_sucesso_pct": 73.3,
                          "taxa_sucesso_recente_pct": 70.0, "n_execucoes_recentes_consideradas": 10,
                          "tempo_medio_ms": 1820.0, "ultima_execucao_em": "2026-11-12T17:40:00+00:00",
                          "ultimo_erro_tecnico": "TimeoutError: especialista não respondeu em 30s"},
    "radar_x": {"total_execucoes": 0, "sucessos": 0, "taxa_sucesso_pct": 0.0,
                "taxa_sucesso_recente_pct": 0.0, "n_execucoes_recentes_consideradas": 0,
                "tempo_medio_ms": None, "ultima_execucao_em": None, "ultimo_erro_tecnico": None},
}
_ANALISES = [
    {"id": "a1b2c3d4", "solicitacao": "Analisar PETR4", "tipo_fluxo": "analise_ticker", "ticker": "PETR4",
     "status": "CONCLUIDA", "iniciado_em": "2026-11-12T18:00:00+00:00", "duracao_ms": 4210, "erro": None,
     "resultado": {"visao_especialistas": {
         "comparador": {"resumo": "3 casas cobrindo PETR4, preço-alvo médio R$ 44,00.",
                         "evidencias": [{"fonte": "Itaú Investimentos", "titulo": "Relatório setorial"}]},
         "analise_ticker": {"resumo": "Síntese agregada de PETR4: fundamentos disponíveis, 2 catalisadores na janela.",
                             "evidencias": [{"fonte": "CVM", "titulo": "Fato relevante"}]},
     }}},
    {"id": "e5f6a7b8", "solicitacao": "Comparar casas sobre VALE3", "tipo_fluxo": "comparar_casas", "ticker": "VALE3",
     "status": "ERRO", "iniciado_em": "2026-11-12T16:10:00+00:00", "duracao_ms": 980,
     "erro": "fontes indisponíveis", "resultado": {}},
]
_ESTATISTICAS_IA = [
    {"origem": "news", "modelo": "llama-3.3-70b-versatile", "total": 312, "concluidos": 309,
     "ultimo_atualizado_em": "2026-11-12T17:58:00+00:00"},
    {"origem": "research", "modelo": "llama-3.3-70b-versatile", "total": 87, "concluidos": 87,
     "ultimo_atualizado_em": "2026-11-12T16:30:00+00:00"},
]

with patch.object(persistencia, "metricas_especialistas", return_value=_METRICAS), \
     patch.object(persistencia, "listar_analises_recentes", return_value=_ANALISES), \
     patch.object(ia_cache, "estatisticas_modelos", return_value=_ESTATISTICAS_IA):
    central.render_central({})
