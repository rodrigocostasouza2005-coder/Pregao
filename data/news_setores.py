# -*- coding: utf-8 -*-
"""Classificacao de noticias do TOP MERCADO por setor da B3.

Cada setor e' definido por palavras-chave (portugues e ingles, pra pegar
tambem manchetes traduzidas/de veiculo estrangeiro - ver Parte D) e pelos
tickers principais do setor. Um grupo de noticia pode cair em mais de um
setor (ex: uma materia sobre "juros e bancos" bate em BANCOS mesmo sem
citar ticker nenhum). Dicionario pensado pra ser facil de editar/estender
- so adicionar palavra ou ticker na lista certa.
"""

import unicodedata

SETORES = {
    "BANCOS": {
        "palavras": [
            "banco", "bancario", "bancaria", "bancos", "banking", "bank",
            "fintech", "correspondente bancario",
        ],
        "tickers": [
            "ITUB4", "ITUB3", "BBDC4", "BBDC3", "BBAS3", "SANB11", "SANB3",
            "SANB4", "BPAC11", "BPAN4", "ABCB4", "BRSR6", "BMGB4", "BSLI3",
        ],
    },
    "PETRÓLEO & GÁS": {
        "palavras": [
            "petroleo", "petrobras", "gas natural", "oil", "gas", "opep",
            "barril", "combustivel", "refino", "pre-sal", "diesel",
            "gasolina", "upstream", "downstream",
        ],
        "tickers": ["PETR4", "PETR3", "PRIO3", "RRRP3", "RECV3", "VBBR3", "UGPA3", "CSAN3", "ENAT3"],
    },
    "MINERAÇÃO & SIDERURGIA": {
        "palavras": [
            "minerio", "mineradora", "mineracao", "siderurgia", "siderurgica",
            "aco", "steel", "mining", "iron ore", "ferro",
        ],
        "tickers": ["VALE3", "CSNA3", "GGBR4", "GGBR3", "GOAU4", "USIM5", "USIM3", "CMIN3", "BRAP4"],
    },
    "VAREJO": {
        "palavras": [
            "varejo", "varejista", "retail", "loja", "lojas", "e-commerce",
            "ecommerce", "consumo", "shopping",
        ],
        "tickers": ["MGLU3", "LREN3", "AMER3", "PCAR3", "ARZZ3", "CEAB3", "ALPA4", "GUAR3", "SOMA3", "VIVA3", "PETZ3"],
    },
    "ENERGIA ELÉTRICA": {
        "palavras": [
            "energia eletrica", "eletrica", "eletricidade", "power",
            "transmissao de energia", "geracao de energia", "distribuidora de energia",
        ],
        "tickers": ["ELET3", "ELET6", "CMIG4", "CPFE3", "EQTL3", "ENGI11", "TAEE11", "CPLE6", "AURE3", "NEOE3", "EGIE3"],
    },
    "SANEAMENTO": {
        "palavras": [
            "saneamento", "agua e esgoto", "water utilities", "esgoto",
            "abastecimento de agua",
        ],
        "tickers": ["SBSP3", "SAPR11", "SAPR4", "CSMG3", "AMBP3"],
    },
    "AGRO & ALIMENTOS": {
        "palavras": [
            "agro", "agronegocio", "agricultura", "alimentos", "food",
            "grain", "soja", "milho", "carne", "frigorifico", "acucar",
            "etanol", "fertilizante",
        ],
        "tickers": ["JBSS3", "MRFG3", "BRFS3", "SLCE3", "AGRO3", "SMTO3", "BEEF3", "RAIZ4", "CAML3"],
    },
    "IMOBILIÁRIO": {
        "palavras": [
            "imobiliario", "real estate", "construtora", "incorporadora",
            "fundo imobiliario", "imoveis", "construcao civil",
        ],
        "tickers": ["CYRE3", "EZTC3", "MRVE3", "DIRR3", "EVEN3", "TRIS3", "TEND3", "PLPL3", "CURY3"],
    },
    "SAÚDE": {
        "palavras": [
            "saude", "hospital", "health", "healthcare", "farmaceutica",
            "plano de saude", "medicina", "laboratorio",
        ],
        "tickers": ["RDOR3", "HAPV3", "FLRY3", "QUAL3", "HYPE3", "ONCO3", "MATD3", "PNVL3"],
    },
    "TECNOLOGIA & TELECOM": {
        "palavras": [
            "tecnologia", "telecom", "telecomunicacoes", "technology",
            "software", "telefonia", "internet", "tech",
        ],
        "tickers": ["VIVT3", "TIMS3", "TOTS3", "LWSA3", "POSI3", "INTB3", "CASH3", "DESK3"],
    },
    "TRANSPORTE & LOGÍSTICA": {
        "palavras": [
            "transporte", "logistica", "logistics", "aviacao", "rodovia",
            "ferrovia", "porto", "aeroporto", "concessionaria de rodovias",
        ],
        "tickers": ["RAIL3", "CCRO3", "AZUL4", "GOLL4", "STBP3", "RENT3", "MOVI3", "ECOR3", "JSLG3"],
    },
}

NOMES_SETORES = list(SETORES.keys())


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def classificar_setores(titulo: str, tickers_citados: list) -> list:
    """Setores cujo criterio (palavra-chave OU ticker) bate com o titulo/
    tickers do grupo - pode retornar mais de um (ex: materia sobre juros
    e bancos bate em BANCOS mesmo citando so a palavra "banco")."""
    texto = _sem_acento(titulo)
    tickers_set = set(tickers_citados or [])
    encontrados = []
    for nome, cfg in SETORES.items():
        bate_palavra = any(_sem_acento(p) in texto for p in cfg["palavras"])
        bate_ticker = bool(tickers_set & set(cfg["tickers"]))
        if bate_palavra or bate_ticker:
            encontrados.append(nome)
    return encontrados


def termo_busca(setor: str) -> str:
    """Query OR com as palavras-chave do setor, pra busca dedicada no
    Google News (usada so quando o filtro de setor esta ativo - amplia a
    cobertura alem do que a secao de negocios + temas gerais ja trazem).
    Limitada as primeiras 5 palavras pra nao estourar o tamanho da URL."""
    palavras = SETORES[setor]["palavras"][:5]
    return " OR ".join(f'"{p}"' for p in palavras)
