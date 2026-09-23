# -*- coding: utf-8 -*-
"""Configuracoes globais do PREGAO: tickers padrao, temas, preferencias, paths."""

from pathlib import Path

# --- Paths -------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# --- Watchlist padrao (usuario sem preferencias salvas / banco fora do ar)
TICKERS_PADRAO = ["PETR4", "VALE3", "ITUB4"]

# --- Mapa ticker -> nome da empresa: SO excecoes onde o longName do
# yfinance (fonte principal, ver data/prices.py) nao da conta - o "S.A."
# nao esta no final ("Petroleo Brasileiro S.A. - Petrobras") ou o
# yfinance simplesmente nao retorna nada pro ticker. Todo o resto vem
# automatico do yfinance, sem precisar cadastrar aqui.
TICKER_NOME = {
    "PETR4": "Petrobras",
    "PETR3": "Petrobras",
    "B3SA3": "B3",
}

# --- Temas visuais (estetica terminal financeiro) -----------------------
# cada tema define as mesmas chaves; viram variaveis CSS (:root) em runtime
TEMAS = {
    "AMBAR": {
        "fundo": "#000000", "painel": "#0A0A0A", "borda": "#333333",
        "destaque": "#FFA028", "alta": "#00D26A", "baixa": "#FF3B3B",
        "neutro": "#E6E6E6", "cinza": "#8C8C8C", "ciano": "#3FC1FF",
    },
    "FOSFORO": {
        "fundo": "#000000", "painel": "#0A0A0A", "borda": "#1F3320",
        "destaque": "#33FF66", "alta": "#33FF66", "baixa": "#FF3B3B",
        "neutro": "#CFFFDA", "cinza": "#6FA37B", "ciano": "#33FF66",
    },
    "AZUL": {
        "fundo": "#00111A", "painel": "#001826", "borda": "#123044",
        "destaque": "#4FC3F7", "alta": "#00D26A", "baixa": "#FF3B3B",
        "neutro": "#DCEEFB", "cinza": "#5C8AA3", "ciano": "#4FC3F7",
    },
    "CLARO": {
        "fundo": "#F5F5F0", "painel": "#FFFFFF", "borda": "#CCCCCC",
        "destaque": "#B36B00", "alta": "#0A8F4C", "baixa": "#C4291C",
        "neutro": "#111111", "cinza": "#555555", "ciano": "#0072B2",
    },
}

DENSIDADES = {"COMPACTA": "0.4rem", "CONFORTAVEL": "1rem"}
FONTES = {"P": "0.78rem", "M": "0.9rem", "G": "1.05rem"}

# --- Intervalo de atualizacao automatica dos paineis de cotacao (segundos)
INTERVALOS_ATUALIZACAO = {"30S": 30, "1MIN": 60, "5MIN": 300}

# --- Indices/moedas da ticker tape: rotulo -> simbolo do yfinance -------
INDICES_TICKER_TAPE = {
    "IBOVESPA": "^BVSP",
    "DOLAR": "USDBRL=X",
}
SIMBOLO_IBOVESPA = "^BVSP"  # usado na comparacao de desempenho no grafico

# --- Velocidade do letreiro animado da ticker tape (pixels por segundo) --
VELOCIDADES_TICKER_TAPE = {"LENTA": 25, "NORMAL": 50, "RAPIDA": 80}

# --- Janelas de retorno mostradas na linha compacta abaixo da cotacao ----
JANELAS_RETORNO = ["1D", "1S", "1M", "3M", "6M", "12M", "ANO"]

# --- Abas do app (chave interna = titulo exibido na navegacao) ----------
ABAS_DISPONIVEIS = ["EQUITY", "MACRO", "RESEARCH", "NEWS", "CVM"]

# --- E-mails com acesso ao painel DIAGNOSTICO DE FONTES (aba CONFIG) ----
EMAILS_DIAGNOSTICO = ["rodrigo.costa.souza2005@gmail.com"]

# --- Groq: modelo usado nos resumos por IA (research hoje, news quando
# plugar) - GROQ_MODELO_PADRAO e' o modelo verificado como disponivel na
# Groq nesta data; obter_modelo_groq() permite trocar sem mexer em codigo
# via st.secrets["groq"]["modelo"], util quando a Groq descontinuar de
# novo (ja aconteceu com o llama-3.1-8b-instant, trocado por este).
GROQ_MODELO_PADRAO = "openai/gpt-oss-20b"


def obter_modelo_groq() -> str:
    try:
        import streamlit as st
        modelo = st.secrets.get("groq", {}).get("modelo")
        if modelo:
            return modelo
    except Exception:
        pass
    return GROQ_MODELO_PADRAO

# --- Preferencias padrao (usuario novo ou banco fora do ar) -------------
PREFS_PADRAO = {
    "tema": "AMBAR",
    "densidade": "COMPACTA",
    "fonte": "M",
    "grafico_tipo": "CANDLE",
    "grafico_periodo_padrao": "6M",
    "mm20": True,
    "mm50": True,
    "mm200": False,
    "abas_visiveis": list(ABAS_DISPONIVEIS),
    "formato_numerico": "BR",
    "watchlist": list(TICKERS_PADRAO),
    "atualizacao_intervalo": 60,
    "ticker_tape_modo": "ANIMADO",
    "ticker_tape_velocidade": "NORMAL",
    "research_casas_ativas": ["genial"],
}

# --- Periodos intradiarios (candles de minutos, tratados a parte em
# data/prices.py:obter_historico_intraday - nao usam buffer/recorte por
# dias, o mecanismo dos periodos diarios/semanais abaixo) ---------------
PERIODOS_INTRADIARIOS = ["1D", "1S"]

# --- Periodos disponiveis no grafico de candles -------------------------
# rotulo -> (period do yfinance, interval do yfinance)
PERIODOS_GRAFICO = {
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "1A": ("1y", "1d"),
    "5A": ("5y", "1wk"),
}

# rotulo -> (period maior buscado no yfinance, so pra ter historico
# suficiente e calcular MM20/MM50/MM200 desde o inicio do periodo exibido)
PERIODOS_BUFFER = {
    "1M": ("2y", "1d"),
    "3M": ("2y", "1d"),
    "6M": ("2y", "1d"),
    "1A": ("3y", "1d"),
    "5A": ("10y", "1wk"),
}


def formatar_numero(valor: float, casas: int = 2, formato: str = "BR") -> str:
    """Formata numero como 1.234,56 (BR) ou 1,234.56 (US)."""
    texto = f"{valor:,.{casas}f}"
    if formato == "BR":
        texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return texto


def formatar_valor_mercado(valor, formato: str = "BR") -> str:
    """Valor de mercado compacto: 'R$ 660,6 bi' / 'R$ 45,2 mi'. '-' se None."""
    if valor is None:
        return "—"
    if valor >= 1_000_000_000:
        return f"R$ {formatar_numero(valor / 1_000_000_000, 1, formato)} bi"
    if valor >= 1_000_000:
        return f"R$ {formatar_numero(valor / 1_000_000, 1, formato)} mi"
    return f"R$ {formatar_numero(valor, 0, formato)}"
