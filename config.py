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

# --- Composicao aproximada do Ibovespa, por setor (aba MERCADO) --------
# Lista curada manualmente com blue chips de alta liquidez - NAO e' a
# composicao oficial completa (~86 papeis, rebalanceada trimestralmente
# pela B3) nem se pretende substituir a fonte oficial. Existe pra dar uma
# visao setorial/de mercado ampla sem depender de scraping do site da B3.
# Atualize esta lista conforme rebalanceamentos (https://www.b3.com.br,
# composicao da carteira teorica do IBOV) - e' so' um dict, adicionar ou
# remover ticker/setor nao exige mexer em nenhum outro arquivo.
IBOVESPA_COMPOSICAO = {
    "PETR4": "Petróleo e Gás", "PETR3": "Petróleo e Gás", "PRIO3": "Petróleo e Gás",
    "RRRP3": "Petróleo e Gás", "UGPA3": "Petróleo e Gás", "CSAN3": "Petróleo e Gás",
    "VALE3": "Mineração e Siderurgia", "GGBR4": "Mineração e Siderurgia",
    "CSNA3": "Mineração e Siderurgia", "USIM5": "Mineração e Siderurgia",
    "GOAU4": "Mineração e Siderurgia",
    "ITUB4": "Bancos", "BBDC4": "Bancos", "BBAS3": "Bancos", "SANB11": "Bancos",
    "BPAC11": "Bancos", "B3SA3": "Bancos e Serviços Financeiros",
    "MGLU3": "Varejo", "LREN3": "Varejo", "RENT3": "Varejo", "ASAI3": "Varejo",
    "CRFB3": "Varejo", "ARZZ3": "Varejo", "PCAR3": "Varejo",
    "ELET3": "Energia Elétrica", "ELET6": "Energia Elétrica", "EQTL3": "Energia Elétrica",
    "CMIG4": "Energia Elétrica", "CPLE6": "Energia Elétrica", "ENEV3": "Energia Elétrica",
    "SBSP3": "Saneamento", "CPFE3": "Energia Elétrica", "AURE3": "Energia Elétrica",
    "VIVT3": "Telecomunicações", "TIMS3": "Telecomunicações",
    "JBSS3": "Agro e Alimentos", "MRFG3": "Agro e Alimentos", "BRFS3": "Agro e Alimentos",
    "SMTO3": "Agro e Alimentos", "BEEF3": "Agro e Alimentos",
    "SUZB3": "Papel e Celulose", "KLBN11": "Papel e Celulose",
    "WEGE3": "Bens de Capital e Industrial", "EMBR3": "Bens de Capital e Industrial",
    "RAIL3": "Transporte e Logística", "CCRO3": "Transporte e Logística",
    "ECOR3": "Transporte e Logística", "AZUL4": "Transporte e Logística",
    "ABEV3": "Bebidas",
    "HAPV3": "Saúde", "RDOR3": "Saúde", "RADL3": "Saúde", "FLRY3": "Saúde", "HYPE3": "Saúde",
    "NTCO3": "Higiene e Beleza",
    "TOTS3": "Tecnologia", "LWSA3": "Tecnologia", "POSI3": "Tecnologia",
    "CYRE3": "Construção Civil", "EZTC3": "Construção Civil", "MRVE3": "Construção Civil",
    "MULT3": "Shoppings e Imóveis", "IGTI11": "Shoppings e Imóveis",
    "CVCB3": "Turismo e Lazer",
}

# --- Principais indices globais (aba MERCADO, painel MERCADOS GLOBAIS) --
INDICES_GLOBAIS = {
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Dow Jones": "^DJI",
    "FTSE 100 (Londres)": "^FTSE",
    "DAX (Frankfurt)": "^GDAXI",
    "Nikkei 225 (Tóquio)": "^N225",
    "Hang Seng (Hong Kong)": "^HSI",
    "Xangai (SSE)": "000001.SS",
}

# --- Velocidade do letreiro animado da ticker tape (pixels por segundo) --
VELOCIDADES_TICKER_TAPE = {"LENTA": 25, "NORMAL": 50, "RAPIDA": 80}

# --- Janelas de retorno mostradas na linha compacta abaixo da cotacao ----
JANELAS_RETORNO = ["1D", "1S", "1M", "3M", "6M", "12M", "ANO"]

# --- Abas do app (chave interna = titulo exibido na navegacao) ----------
ABAS_DISPONIVEIS = ["EQUITY", "MACRO", "RESEARCH", "NEWS", "TOP MERCADO", "MERCADO", "CVM"]

# --- E-mails com acesso a paineis de admin (DIAGNOSTICO DE FONTES, SISTEMA) --
# repo publico: nao deixar e-mail pessoal fixo no codigo. Le
# st.secrets["admin"]["emails"] (lista); enquanto esse secret nao for
# configurado, cai pro fallback abaixo - o painel continua funcionando
# antes e depois da acao manual (ver AÇÕES MANUAIS PENDENTES em
# PROGRESSO.md pro bloco a colar em secrets.toml).
_EMAILS_ADMIN_PADRAO = ["rodrigo.costa.souza2005@gmail.com"]


def obter_emails_admin() -> list:
    try:
        import streamlit as st
        emails = st.secrets.get("admin", {}).get("emails")
        if emails:
            return list(emails)
    except Exception:
        pass
    return _EMAILS_ADMIN_PADRAO

# --- Groq: chave e modelo usados nos resumos por IA (research e news) --
# GROQ_MODELO_PADRAO e' o modelo verificado como disponivel na Groq nesta
# data; sobrescrevivel via st.secrets["groq"]["modelo"], util quando a
# Groq descontinuar de novo (ja aconteceu com o llama-3.1-8b-instant,
# trocado por este). reasoning_effort="low" nas chamadas: gpt-oss e'
# modelo de raciocinio, sem isso ele gasta boa parte do max_tokens
# "pensando" (campo message.reasoning) antes de responder e o resumo sai
# cortado no meio (visto na pratica no resumo de noticias).
GROQ_MODELO_PADRAO = "openai/gpt-oss-20b"
GROQ_REASONING_EFFORT = "low"
GROQ_MAX_TOKENS = 400


def obter_modelo_groq() -> str:
    return obter_credenciais_groq()[1]


def obter_credenciais_groq() -> tuple:
    """(api_key, modelo) do Groq, lidos num lugar so' - usado por
    data/research/resumir.py e data/news.py. api_key: st.secrets["groq"]
    ["api_key"], com fallback pra st.secrets["GROQ_API_KEY"] na raiz
    (configuracao de uma linha so, sem precisar da secao [groq]). modelo:
    st.secrets["groq"]["modelo"] ou GROQ_MODELO_PADRAO. api_key vem None
    se nao configurada em lugar nenhum - quem chama mostra "resumo
    indisponível (GROQ_API_KEY não configurada)" e segue sem quebrar."""
    try:
        import streamlit as st
        secao_groq = st.secrets.get("groq", {})
        api_key = secao_groq.get("api_key") or st.secrets.get("GROQ_API_KEY")
        modelo = secao_groq.get("modelo") or GROQ_MODELO_PADRAO
        return api_key, modelo
    except Exception:
        return None, GROQ_MODELO_PADRAO

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
    "abas_conhecidas": list(ABAS_DISPONIVEIS),  # ver app.py: migracao automatica de abas novas
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
