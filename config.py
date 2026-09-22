# -*- coding: utf-8 -*-
"""Configuracoes globais do PREGAO: tickers padrao, temas, preferencias, paths."""

from pathlib import Path

# --- Paths -------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# --- Watchlist padrao (usuario sem preferencias salvas / banco fora do ar)
TICKERS_PADRAO = ["PETR4", "VALE3", "ITUB4"]

# --- Mapa ticker -> nome da empresa (usado nas Fases 3/4/5 tambem) -----
TICKER_NOME = {
    "PETR4": "Petrobras",
    "PETR3": "Petrobras",
    "VALE3": "Vale",
    "ITUB4": "Itaú Unibanco",
    "BBDC4": "Bradesco",
    "BBAS3": "Banco do Brasil",
    "ABEV3": "Ambev",
    "SBFG3": "Grupo SBF",
    "WEGE3": "WEG",
    "MGLU3": "Magazine Luiza",
    "B3SA3": "B3",
    "RENT3": "Localiza",
    "SUZB3": "Suzano",
    "PRIO3": "PRIO",
    "RAIL3": "Rumo",
    "EQTL3": "Equatorial Energia",
    "GGBR4": "Gerdau",
    "JBSS3": "JBS",
    "LREN3": "Lojas Renner",
    "CSAN3": "Cosan",
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

# --- Abas do app (chave interna = titulo exibido na navegacao) ----------
ABAS_DISPONIVEIS = ["EQUITY", "MACRO", "RESEARCH", "NEWS", "CVM"]

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
}

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
