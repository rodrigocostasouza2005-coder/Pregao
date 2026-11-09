# Dados mockados REALISTAS (mesmos formatos de data/mercado.py,
# data/prices.py, data/news.py, data/radar.py/data/eventos.py) usados
# pelos 3 harnesses visuais desta pasta (mapa/visao/catalisadores de
# SETORES) - nenhuma chamada de rede real, nenhum dado inventado fora do
# formato ja existente. Setor escolhido pra visao/catalisadores: BANCOS
# (ja tem texto editorial real em data/radar_setorial.CATALOGO).
from datetime import date, datetime, timedelta, timezone

from data.eventos import STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_LABEL, STATUS_PRAZO_CVM

SETOR = "BANCOS"

# --- SETORES > Mapa Setorial (ui.mercado_tab._painel_setorial/_painel_treemap) ---

DESEMPENHO_SETORIAL = [
    {"setor": "Petróleo e Gás", "variacao_media_pct": 2.35, "n_papeis": 3},
    {"setor": "Bancos e Serviços Financeiros", "variacao_media_pct": 1.42, "n_papeis": 3},
    {"setor": "Energia Elétrica", "variacao_media_pct": 0.22, "n_papeis": 2},
    {"setor": "Mineração e Siderurgia", "variacao_media_pct": -0.58, "n_papeis": 2},
    {"setor": "Materiais Básicos", "variacao_media_pct": -0.95, "n_papeis": 1},
    {"setor": "Varejo", "variacao_media_pct": -1.87, "n_papeis": 2},
]

PANORAMA_IBOV = [
    {"ticker": "PETR4", "setor": "Petróleo e Gás", "preco": 36.52, "variacao_pct": 3.14, "volume_financeiro": 1_250_000_000.0},
    {"ticker": "PETR3", "setor": "Petróleo e Gás", "preco": 34.10, "variacao_pct": 2.80, "volume_financeiro": 300_000_000.0},
    {"ticker": "PRIO3", "setor": "Petróleo e Gás", "preco": 42.33, "variacao_pct": 1.95, "volume_financeiro": 180_000_000.0},
    {"ticker": "ITUB4", "setor": "Bancos e Serviços Financeiros", "preco": 34.21, "variacao_pct": 1.42, "volume_financeiro": 620_000_000.0},
    {"ticker": "BBDC4", "setor": "Bancos e Serviços Financeiros", "preco": 15.87, "variacao_pct": -0.63, "volume_financeiro": 410_000_000.0},
    {"ticker": "BBAS3", "setor": "Bancos e Serviços Financeiros", "preco": 27.44, "variacao_pct": 2.08, "volume_financeiro": 380_000_000.0},
    {"ticker": "ELET3", "setor": "Energia Elétrica", "preco": 44.60, "variacao_pct": 0.33, "volume_financeiro": 150_000_000.0},
    {"ticker": "EQTL3", "setor": "Energia Elétrica", "preco": 33.22, "variacao_pct": 0.10, "volume_financeiro": 60_000_000.0},
    {"ticker": "VALE3", "setor": "Mineração e Siderurgia", "preco": 71.80, "variacao_pct": -1.02, "volume_financeiro": 980_000_000.0},
    {"ticker": "CSNA3", "setor": "Mineração e Siderurgia", "preco": 12.44, "variacao_pct": -0.41, "volume_financeiro": 90_000_000.0},
    {"ticker": "WEGE3", "setor": "Materiais Básicos", "preco": 52.30, "variacao_pct": -0.95, "volume_financeiro": 110_000_000.0},
    {"ticker": "MGLU3", "setor": "Varejo", "preco": 2.11, "variacao_pct": -12.47, "volume_financeiro": 210_000_000.0},
    {"ticker": "LREN3", "setor": "Varejo", "preco": 17.90, "variacao_pct": -0.85, "volume_financeiro": 95_000_000.0},
]


def mock_desempenho_setorial(janela: str = "dia"):
    return DESEMPENHO_SETORIAL


def mock_panorama_ibovespa():
    return PANORAMA_IBOV


def mock_momento_panorama():
    return datetime.now(timezone.utc) - timedelta(minutes=4)


def mock_cotacao_indice(nome: str, symbol: str):
    return {"preco": 136_480.0, "variacao_pct": 1.18, "erro": None}


# --- SETORES > Visão por Setor (ui.setores_tab._tabela_empresas) ---

COTACOES_BANCOS = {
    "ITUB4": {"preco": 34.21, "variacao_pct": 1.42, "erro": None},
    "ITUB3": {"preco": 30.10, "variacao_pct": 1.10, "erro": None},
    "BBDC4": {"preco": 15.87, "variacao_pct": -0.63, "erro": None},
    "BBDC3": {"preco": 14.92, "variacao_pct": -0.71, "erro": None},
    "BBAS3": {"preco": 27.44, "variacao_pct": 2.08, "erro": None},
    "SANB11": {"preco": 29.30, "variacao_pct": 0.0, "erro": None},
    "SANB3": {"preco": 14.60, "variacao_pct": 0.14, "erro": None},
    "SANB4": {"preco": 15.02, "variacao_pct": -0.10, "erro": None},
    "BPAC11": {"preco": 32.18, "variacao_pct": 3.67, "erro": None},
    "BPAN4": {"preco": 7.85, "variacao_pct": -2.11, "erro": None},
    "ABCB4": {"preco": 21.40, "variacao_pct": 0.47, "erro": None},
    "BRSR6": {"preco": 13.05, "variacao_pct": -1.21, "erro": None},
}


def mock_cotacoes_lote(tickers):
    return {t: COTACOES_BANCOS.get(t, {"erro": "sem dado"}) for t in tickers}


# --- SETORES > Visão por Setor / Catalisadores: notícias (TOP MERCADO) ---

def _iso(horas_atras: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=horas_atras)).isoformat()


NOTICIAS_BANCOS = [
    {
        "titulo": "Itaú Unibanco supera estimativas e eleva guidance de crédito para 2027",
        "link": "https://exemplo.com/itau-resultado", "data": _iso(1.5),
        "selo": "CONFIRMADA", "score": 9, "regras": ["veículo confiável", "3 veículos"],
        "fontes_count": 3, "importancia": 9,
        "criterio_ranking": ["3 fontes", "recente", "veículo confiável", "tema de mercado"],
        "regiao": "BR", "ticker": "ITUB4",
    },
    {
        "titulo": "Banco do Brasil anuncia programa de recompra de ações",
        "link": "https://exemplo.com/bb-recompra", "data": _iso(4.0),
        "selo": "CONFIRMADA", "score": 8, "regras": ["veículo confiável", "2 veículos"],
        "fontes_count": 2, "importancia": 8,
        "criterio_ranking": ["2 fontes", "veículo confiável"],
        "regiao": "BR", "ticker": "BBAS3",
    },
    {
        "titulo": "Bradesco pode revisar política de dividendos após resultado do 3T, dizem analistas",
        "link": "https://exemplo.com/bradesco-dividendos", "data": _iso(9.0),
        "selo": "PROVÁVEL", "score": 6, "regras": ["2 veículos"],
        "fontes_count": 2, "importancia": 6,
        "criterio_ranking": ["2 fontes"],
        "regiao": "BR", "ticker": "BBDC4",
    },
    {
        "titulo": "BTG Pactual eleva recomendação para bancos médios",
        "link": "https://exemplo.com/btg-bancos-medios", "data": _iso(20.0),
        "selo": "NÃO CONFIRMADA", "score": 3, "regras": ["1 veículo"],
        "fontes_count": 1, "importancia": 3,
        "criterio_ranking": ["1 fonte"],
        "regiao": "BR", "tickers": ["ABCB4", "BRSR6"],
    },
]


def mock_top_mercado_tudo(setor: str = "TODOS"):
    return NOTICIAS_BANCOS


# --- SETORES > Catalisadores (ui.radar_tab._secao_catalisadores) ---

CATALISADORES_BANCOS = [
    {
        "ticker": "ITUB4", "categoria": "Resultado trimestral (3T)", "status": STATUS_CONFIRMADO,
        "status_label": STATUS_LABEL[STATUS_CONFIRMADO], "data": date.today() + timedelta(days=5),
        "fonte_url": "https://ri.itau.com.br", "fonte_label": "RI Itaú",
    },
    {
        "ticker": "BBAS3", "categoria": "Pagamento de dividendos", "status": STATUS_ESTIMADO,
        "status_label": STATUS_LABEL[STATUS_ESTIMADO], "data": date.today() + timedelta(days=12),
        "fonte_url": None, "fonte_label": "Estimativa por histórico de pagamentos",
    },
    {
        "ticker": "BBDC4", "categoria": "Resultado trimestral (3T)", "status": STATUS_PRAZO_CVM,
        "status_label": STATUS_LABEL[STATUS_PRAZO_CVM], "data": date.today() + timedelta(days=30),
        "fonte_url": None, "fonte_label": None,
    },
    {
        "ticker": "SANB11", "categoria": "Pagamento de dividendos", "status": STATUS_CONFIRMADO,
        "status_label": STATUS_LABEL[STATUS_CONFIRMADO], "data": date.today() + timedelta(days=18),
        "fonte_url": "https://ri.santander.com.br", "fonte_label": "RI Santander",
    },
]


def mock_catalisadores(tickers):
    tickers = set(tickers)
    return [c for c in CATALISADORES_BANCOS if c["ticker"] in tickers]
