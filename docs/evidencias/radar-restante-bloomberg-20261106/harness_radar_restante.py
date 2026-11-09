# Harness visual LOCAL (sem login/auth/Supabase) - valida visualmente as 4
# subabas de RADAR que faltavam no passe "Bloomberg ambar" de 2026-11-06
# (Alertas, Oportunidades, Acompanhamento, Preferencias), mockando so' as
# funcoes de data/radar.py, data/radar_quedas.py e data/posicoes.py - mesmo
# padrao de docs/evidencias/responsividade-bloomberg-20261106/harness_radar.py
# (que ja' cobre Alertas/Carteiras; este aqui cobre as 4 rotas restantes,
# incluindo Alertas de novo so' pra comparacao lado a lado no mesmo lote de
# screenshots desta missao).
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.radar_tab as radar_tab
from data import posicoes as posicoes_mod
from data import radar
from data import radar_quedas as rq
from data.eventos import STATUS_CONFIRMADO, STATUS_ESTIMADO

st.set_page_config(page_title="harness radar restante", layout="wide")
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

WATCHLIST = ["PETR4", "VALE3", "ITUB4"]
PREFS = {"formato_numerico": "BR", "tema": "AMBAR", "watchlist": WATCHLIST,
         "radar_quedas_email_ativo": False}
USUARIO = {"sub": "demo-user", "email": "demo@exemplo.com"}

AGORA = datetime.now(timezone.utc)

# ---- Alertas (reaproveita o mesmo mock de dado do harness_radar.py) -------
VERIFICADO_RECENTE = (AGORA - timedelta(hours=2)).isoformat()
VERIFICADO_VELHO = (AGORA - timedelta(hours=200)).isoformat()
_RESUMO_FONTES = {
    rq.CASA_ITAU: {"ativos": 3, "verificado_em": VERIFICADO_RECENTE, "desatualizada": False,
                   "carteiras": ["Top 5"], "data_publicacao": "2026-11-01"},
    rq.CASA_SAFRA: {"ativos": 2, "verificado_em": VERIFICADO_VELHO, "desatualizada": True,
                     "carteiras": ["Carteira Recomendada"], "data_publicacao": "2026-10-15"},
}
_PAINEL = [
    {"ticker": "PETR4", "empresa": "Petrobras", "casas": [rq.CASA_ITAU], "carteiras": ["Top 5"],
     "preco": 34.10, "fechamento_anterior": 36.52, "variacao_pct": -6.63,
     "distancia_gatilho_pp": None, "estado": "ALERTA"},
    {"ticker": "MGLU3", "empresa": "Magazine Luiza", "casas": [rq.CASA_SAFRA], "carteiras": ["Carteira Recomendada"],
     "preco": 2.02, "fechamento_anterior": 2.11, "variacao_pct": -2.84,
     "distancia_gatilho_pp": -1.16, "estado": "ATENCAO"},
    {"ticker": "VALE3", "empresa": "Vale", "casas": [rq.CASA_ITAU], "carteiras": ["Top 5"],
     "preco": 71.80, "fechamento_anterior": 71.00, "variacao_pct": 1.13,
     "distancia_gatilho_pp": 5.13, "estado": "NORMAL"},
]
_ALERTAS = [
    {"ticker": "PETR4", "empresa": "Petrobras", "variacao_pct": -6.63, "fechamento_anterior": 36.52,
     "preco_atual": 34.10, "casas": [rq.CASA_ITAU], "carteiras": ["Top 5"],
     "fontes": ["https://exemplo.com/itau"], "status": "ENVIADO",
     "pregao": AGORA.date().isoformat(), "alertado_em": AGORA.isoformat()},
    {"ticker": "MGLU3", "empresa": "Magazine Luiza", "variacao_pct": -4.90, "fechamento_anterior": 2.20,
     "preco_atual": 2.09, "casas": [rq.CASA_SAFRA], "carteiras": ["Carteira Recomendada"],
     "fontes": ["https://exemplo.com/safra"], "status": "PENDENTE_ENVIO",
     "pregao": (AGORA - timedelta(days=1)).date().isoformat(), "alertado_em": (AGORA - timedelta(days=1)).isoformat()},
]


def _alertas_periodo(dias):
    return _ALERTAS


rq.resumo_fontes_vigentes = lambda: _RESUMO_FONTES
rq.painel_monitorados = lambda: _PAINEL
rq.alertas_periodo = _alertas_periodo

# ---- Oportunidades ----------------------------------------------------
_MUDANCAS_TESE = [
    {"ticker": "PETR4", "categoria": "Mudança de recomendação", "tipo_evidencia": radar.TIPO_FATO,
     "descricao": "Itaú BBA eleva PETR4 de neutro para compra, preço-alvo R$ 42,00.",
     "relevancia": "Casa com carteira monitorada pelo Radar - impacto direto na cobertura.",
     "data_evento": date.today() - timedelta(days=1), "horario_coleta": AGORA,
     "potencial_pct_fonte": 18.4, "potencial_pct_calculado": None,
     "fonte_label": "Itaú BBA", "fonte_url": "https://exemplo.com/itau-petr4"},
    {"ticker": "VALE3", "categoria": "Revisão de preço-alvo", "tipo_evidencia": radar.TIPO_CALCULO,
     "descricao": "Potencial recalculado a partir do novo preço-alvo divulgado pela Safra.",
     "relevancia": "Ajuste de 7% no preço-alvo frente à revisão anterior.",
     "data_evento": date.today() - timedelta(days=3), "horario_coleta": None,
     "potencial_pct_fonte": None, "potencial_pct_calculado": 9.8,
     "fonte_label": "Safra Corretora", "fonte_url": "https://exemplo.com/safra-vale3"},
]
_CATALISADORES = [
    {"ticker": "ITUB4", "categoria": "Resultado trimestral", "status": STATUS_CONFIRMADO,
     "status_label": "CONFIRMADO", "data": date.today() + timedelta(days=5),
     "fonte_url": "https://exemplo.com/calendario-itub4", "fonte_label": "Calendário B3"},
    {"ticker": "PETR4", "categoria": "Pagamento de proventos", "status": STATUS_ESTIMADO,
     "status_label": "ESTIMADO", "data": date.today() + timedelta(days=12),
     "fonte_url": None, "fonte_label": "Estimativa interna"},
]
_EVIDENCIAS = [
    {"_tipo_item": "noticia", "_payload": {
        "data": AGORA.isoformat(), "titulo": "Petrobras anuncia novo plano de investimentos para 2027-2031",
        "tickers": ["PETR4"], "link": "https://exemplo.com/noticia-petr4"}},
    {"_tipo_item": "documento", "_payload": {
        "data": (AGORA - timedelta(days=2)).isoformat(), "assunto": "Fato Relevante - Aquisição de ativo logístico",
        "ticker": "VALE3", "link": "https://exemplo.com/cvm-vale3"}},
]

radar.mudancas_tese = lambda tickers, janela="7 DIAS": _MUDANCAS_TESE
radar.catalisadores = lambda tickers, dias_passado=7, dias_futuro=60: _CATALISADORES
radar.evidencias_recentes = lambda tickers, limite=12: _EVIDENCIAS

# ---- Acompanhamento (historico da watchlist + risco da carteira) ------
_POSICOES = [
    {"ticker": "PETR4", "quantidade": 200, "preco_medio": 32.50, "data_referencia": "2026-09-10"},
    {"ticker": "VALE3", "quantidade": 100, "preco_medio": 68.00, "data_referencia": "2026-08-22"},
]
_RISCO_CARTEIRA = {
    "carteira_cadastrada": True,
    "valor_total": 200 * 34.10 + 100 * 71.80,
    "posicoes": [
        {"ticker": "PETR4", "quantidade": 200, "preco_medio": 32.50, "preco_atual": 34.10,
         "valor_atual": 200 * 34.10, "lucro_pct": (34.10 - 32.50) / 32.50 * 100},
        {"ticker": "VALE3", "quantidade": 100, "preco_medio": 68.00, "preco_atual": 71.80,
         "valor_atual": 100 * 71.80, "lucro_pct": (71.80 - 68.00) / 68.00 * 100},
    ],
    "tickers_sem_preco": [],
    "tickers_sem_historico": [],
    "concentracao_ativo": [
        {"nome": "PETR4", "valor": 200 * 34.10, "peso_pct": 200 * 34.10 / (200 * 34.10 + 100 * 71.80) * 100},
        {"nome": "VALE3", "valor": 100 * 71.80, "peso_pct": 100 * 71.80 / (200 * 34.10 + 100 * 71.80) * 100},
    ],
    "concentracao_setor": [
        {"nome": "Petróleo, Gás e Biocombustíveis", "valor": 200 * 34.10,
         "peso_pct": 200 * 34.10 / (200 * 34.10 + 100 * 71.80) * 100},
        {"nome": "Materiais Básicos", "valor": 100 * 71.80,
         "peso_pct": 100 * 71.80 / (200 * 34.10 + 100 * 71.80) * 100},
    ],
    "limiar_concentracao_pct": 25,
    "correlacao": {"PETR4": {"PETR4": 1.0, "VALE3": 0.42}, "VALE3": {"PETR4": 0.42, "VALE3": 1.0}},
    "periodo_historico": "6M",
    "volatilidade_anual_pct": 38.6,
    "drawdown_pct": -14.2,
    "maior_queda_diaria_pct": -6.63,
    "cenario_beta": {
        "beta_carteira": 1.08,
        "impacto_pct": {-10: -10.8, -20: -21.6},
        "tickers_sem_beta": [],
    },
    "watchlist_tamanho": len(WATCHLIST),
}

posicoes_mod.obter_posicoes = lambda sub: _POSICOES
radar.risco_carteira = lambda sub, prefs: _RISCO_CARTEIRA


def _persistir_ok():
    return True


secao = st.query_params.get("secao", "alertas")
if secao == "oportunidades":
    radar_tab.render_radar_oportunidades(PREFS)
elif secao == "acompanhamento":
    radar_tab.render_radar_acompanhamento(PREFS, USUARIO)
elif secao == "preferencias":
    radar_tab.render_preferencias(PREFS, USUARIO, _persistir_ok)
else:
    radar_tab.render_radar_alertas(PREFS)
