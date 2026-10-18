# -*- coding: utf-8 -*-
"""Radar setorial do Morning Call: 4 setores por edição, cada um com um
bloco didático curto (O que aconteceu / Por que importa / Empresas e
ativos relacionados / O que acompanhar).

Três etapas separadas, cada uma testável sem rede:

1. SELEÇÃO (plano_do_dia): ordem determinística dos setores do catálogo
   para a data da edição. Mesma data -> mesma ordem, sempre. A variação
   entre dias vem de um histórico RECALCULADO, não gravado: o plano de
   cada dia útil desde EPOCA é refeito em memória (função pura da data e
   do catálogo) e o setor que está há mais tempo sem aparecer vem
   primeiro; empate decidido por um hash estável da data. Nenhuma escrita
   em banco - consultar o histórico é chamar historico_planos().
2. EVIDÊNCIA (evidencias_do_setor): notícias do setor vindas do mesmo
   coletor do app (data/news.py:obter_top_mercado(setor), a aba TOP
   MERCADO filtrada por setor), validadas aqui: título, veículo, data
   dentro da janela da edição e link http(s). Setor sem evidência
   suficiente sai da edição com o motivo registrado e o próximo da ordem
   entra no lugar - nunca um bloco preenchido sem fonte.
3. REDAÇÃO (redigir_bloco): sem IA e sem número inventado. "O que
   aconteceu" só cita manchetes publicadas, com veículo e data (fato);
   "Por que importa" e "O que acompanhar" vêm do catálogo abaixo -
   contexto didático fixo, sem números e sem recomendação de compra ou
   venda, marcado como contexto no PDF.
"""
import hashlib
import re
import unicodedata
from datetime import date, datetime, timedelta
from functools import lru_cache
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

TZ_SP = ZoneInfo("America/Sao_Paulo")

QTD_SETORES = 4
EPOCA = date(2026, 1, 5)  # segunda-feira; início do histórico recalculado
MAX_TENTATIVAS = 11  # setores consultados no máximo por edição (o catálogo inteiro)
MIN_FONTES = 2  # notícias válidas de veículos diferentes
MAX_FATOS = 3
PALAVRAS_MIN, PALAVRAS_MAX = 100, 150

# Catálogo configurável. A chave é o nome do setor em
# data/news_setores.SETORES (é por ele que o coletor filtra as notícias);
# "termos" são palavras inteiras exigidas no título (mais estritas que as
# do classificador do app, que casa por substring); "empresas" são as
# principais do setor no Ibovespa (config.IBOVESPA_SETORES); "nomes" são
# nomes de empresa que também são palavras comuns, comparados com maiúscula. Textos sem
# números e sem recomendação: explicam o mecanismo, não o preço.
CATALOGO = {
    "BANCOS": {
        "nome": "Bancos",
        "consulta": (
            '("bancos" OR "Itaú" OR "Bradesco" OR "Banco do Brasil" OR "Santander" OR '
            '"crédito bancário")'
        ),
        "termos": (
            "bancos", "bancario", "bancaria", "bancarios", "credito", "inadimplencia", "spread",
            "itau", "bradesco", "santander", "btg", "nubank", "banco do brasil",
        ),
        # "Bancos centrais preveem juros mais altos" entrou como Bancos no
        # exemplo real: autoridade monetária não é o setor bancário
        "exclui": ("banco central", "bancos centrais"),
        "empresas": ("ITUB4", "BBDC4", "BBAS3", "SANB11", "BPAC11"),
        "importa": ("Bancos têm o maior peso setorial do Ibovespa. Juros, inadimplência e demanda por "
                    "crédito definem quanto eles lucram, e o setor costuma refletir rapidamente "
                    "mudanças na expectativa para a Selic. Em ciclos de juros altos, a margem tende a melhorar, mas o "
                    "risco de calote também cresce."),
        "acompanhar": "Decisões e comunicados do Copom, dados de crédito e inadimplência do Banco "
                      "Central e balanços trimestrais dos grandes bancos.",
    },
    "PETRÓLEO & GÁS": {
        "nome": "Petróleo e gás",
        "consulta": '("Petrobras" OR "petróleo" OR "Brent" OR "Opep" OR "combustíveis" OR "PetroReconcavo")',
        "termos": (
            "petroleo", "petrobras", "petrolifera", "petroliferas", "barril", "brent", "opep", "pre-sal",
            "diesel", "gasolina", "combustivel", "combustiveis", "refino", "refinaria",
            "petroreconcavo", "brava energia",
        ),
        "nomes": ("PRIO", "Prio"),
        "empresas": ("PETR4", "PETR3", "PRIO3", "BRAV3", "VBBR3"),
        "importa": ("O preço internacional do petróleo e a política de preços da Petrobras afetam a "
                    "receita das produtoras, a inflação de combustíveis e o peso do setor no "
                    "Ibovespa, onde a Petrobras é uma das maiores empresas. Para as produtoras privadas, o que "
                    "pesa mais é o volume extraído e o custo de cada barril."),
        "acompanhar": "Cotação do Brent, reuniões da Opep+, reajustes de combustíveis e dados de "
                      "produção divulgados pela ANP e pelas empresas.",
    },
    "MINERAÇÃO & SIDERURGIA": {
        "nome": "Mineração e siderurgia",
        "consulta": '("Vale" OR "minério de ferro" OR "siderurgia" OR "Gerdau" OR "Usiminas" OR "CSN")',
        "termos": (
            "minerio", "mineradora", "mineradoras", "mineracao", "siderurgia", "siderurgica",
            "siderurgicas", "aco", "usiminas", "gerdau", "csn", "cmin",
        ),
        "nomes": ("Vale",),
        "empresas": ("VALE3", "GGBR4", "CSNA3", "USIM5", "CMIN3"),
        "importa": ("A demanda chinesa por minério de ferro e aço move a receita da Vale e das "
                    "siderúrgicas. Como a Vale tem grande peso no Ibovespa, o setor influencia o "
                    "índice como um todo. As siderúrgicas também disputam espaço com o aço importado, o que "
                    "torna tarifas e medidas comerciais relevantes para o resultado."),
        "acompanhar": "Preço do minério de ferro, indicadores de atividade e de construção na China, "
                      "relatórios de produção e medidas de defesa comercial sobre o aço.",
    },
    "VAREJO": {
        "nome": "Varejo",
        "consulta": (
            '("varejo" OR "varejistas" OR "Magazine Luiza" OR "Renner" OR "Assaí" OR '
            '"vendas no varejo")'
        ),
        "termos": (
            "varejo", "varejista", "varejistas", "magazine luiza", "magalu", "renner", "assai",
            "casas bahia", "c&a", "azzas", "e-commerce",
        ),
        "empresas": ("MGLU3", "LREN3", "ASAI3", "AZZA3", "CEAB3"),
        "importa": ("O varejo depende da renda das famílias e do custo do crédito ao consumidor. Por "
                    "isso, as ações do setor tendem a reagir a mudanças nas expectativas de juros e "
                    "de emprego. Margens costumam ser apertadas, então pequenas variações em vendas, "
                    "estoques e despesas financeiras fazem diferença no lucro."),
        "acompanhar": "Dados de vendas no varejo do IBGE, confiança do consumidor, mercado de trabalho "
                      "e a trajetória esperada da Selic.",
    },
    "ENERGIA ELÉTRICA": {
        "nome": "Energia elétrica",
        "consulta": (
            '("energia elétrica" OR "Aneel" OR "Eletrobras" OR "Axia" OR "Cemig" OR '
            '"bandeira tarifária")'
        ),
        "termos": (
            "energia eletrica", "eletricidade", "aneel", "hidreletrica", "hidreletricas",
            "transmissao de energia", "distribuidora de energia", "distribuidoras", "eletrobras",
            "axia", "cemig", "copel", "equatorial", "engie", "bandeira tarifaria", "conta de luz",
        ),
        "empresas": ("AXIA3", "EQTL3", "CMIG4", "CPLE3", "EGIE3"),
        "importa": ("Empresas de energia têm receita regulada e previsível. Por isso, chuvas, decisões "
                    "da Aneel e o nível dos juros, que muda o valor presente dessas receitas, pesam "
                    "no desempenho do setor. Muitas empresas pagam dividendos regulares, o que as aproxima, aos "
                    "olhos do investidor, de aplicações de renda fixa."),
        "acompanhar": "Bandeiras tarifárias, nível dos reservatórios, leilões e revisões tarifárias "
                      "da Aneel e a curva de juros longos.",
    },
    "SANEAMENTO": {
        "nome": "Saneamento",
        "consulta": '("saneamento" OR "Sabesp" OR "Copasa" OR "Sanepar")',
        "termos": ('saneamento', 'sabesp', 'copasa', 'sanepar', 'esgoto'),
        "empresas": ("SBSP3", "CSMG3", "SAPR11"),
        "importa": ("Saneamento é um setor regulado e intensivo em investimento. O marco legal e as "
                    "privatizações estaduais mudam o horizonte de crescimento, e os juros afetam o "
                    "custo de financiar as obras. Como as tarifas são reajustadas por regra, o "
                    "investimento executado e a regulação contam mais do que o ciclo da economia."),
        "acompanhar": "Leilões e privatizações estaduais, revisões tarifárias das agências "
                      "reguladoras e metas de universalização do marco legal.",
    },
    "AGRO & ALIMENTOS": {
        "nome": "Agronegócio e alimentos",
        "consulta": '("agronegócio" OR "safra" OR "soja" OR "frigoríficos" OR "JBS" OR "BRF")',
        "termos": (
            "agronegocio", "agricola", "safra", "soja", "milho", "frigorifico", "frigorificos",
            "acucar", "etanol", "fertilizante", "fertilizantes", "jbs", "brf", "marfrig", "minerva",
            "sao martinho", "slc",
        ),
        "empresas": ("JBSS32", "MBRF3", "SMTO3", "BEEF3", "SLCE3"),
        "importa": ("O agronegócio é exportador e sensível ao câmbio, ao clima e à demanda externa, em "
                    "especial da China. Preços de grãos e de proteínas afetam tanto as empresas quanto "
                    "a inflação de alimentos. Frigoríficos ainda dependem do ciclo do gado e de "
                    "habilitações sanitárias para exportar."),
        "acompanhar": "Estimativas de safra da Conab, preços internacionais de grãos, abertura e "
                      "fechamento de mercados para a carne brasileira e o câmbio.",
    },
    "IMOBILIÁRIO": {
        "nome": "Construção e imobiliário",
        "consulta": (
            '("construtoras" OR "incorporadoras" OR "mercado imobiliário" OR '
            '"Minha Casa, Minha Vida" OR "MRV" OR "Cyrela")'
        ),
        "termos": (
            "imobiliario", "imobiliaria", "imobiliarios", "imoveis", "construtora", "construtoras",
            "incorporadora", "incorporadoras", "minha casa", "mrv", "cyrela", "cury", "direcional",
            "eztec", ),
        "nomes": ("Tenda",),
        "empresas": ("CYRE3", "MRVE3", "CURY3", "DIRR3", "EZTC3"),
        "importa": ("Construtoras dependem do custo e da oferta de financiamento imobiliário. Juros "
                    "mais altos encarecem a compra do imóvel e o capital das empresas, e programas "
                    "habitacionais mudam a demanda na baixa renda. O setor também acompanha o custo de "
                    "materiais e de mão de obra, que afeta a margem das obras em andamento."),
        "acompanhar": "Prévias operacionais de lançamentos e vendas, regras do Minha Casa, Minha "
                      "Vida, captação da poupança e juros de longo prazo.",
    },
    "SAÚDE": {
        "nome": "Saúde",
        "consulta": (
            '("planos de saúde" OR "ANS" OR "Rede D\'Or" OR "Hapvida" OR "farmacêuticas" OR '
            '"Raia Drogasil")'
        ),
        "termos": (
            "plano de saude", "planos de saude", "operadora de saude", "operadoras de saude", "ans",
            "rede d'or", "hapvida", "fleury", "hypera", "raia drogasil", "dasa", "farmaceutica",
            "farmaceuticas", "hospitalar",
        ),
        "empresas": ("RDOR3", "HAPV3", "RADL3", "FLRY3", "HYPE3"),
        "importa": ("O setor de saúde combina demanda estável com custos que sobem acima da inflação. "
                    "Reajustes autorizados pela ANS e o uso dos planos definem a margem das "
                    "operadoras e dos hospitais. Fusões e aquisições têm sido frequentes, e a integração das "
                    "redes compradas costuma aparecer nos resultados."),
        "acompanhar": "Reajustes de planos definidos pela ANS, índices de sinistralidade nos balanços "
                      "e regras de preços de medicamentos.",
    },
    "TECNOLOGIA & TELECOM": {
        "nome": "Tecnologia e telecom",
        "consulta": '("telecom" OR "Anatel" OR "operadoras" OR "Vivo" OR "TIM" OR "Totvs")',
        "termos": (
            "telecom", "telecomunicacoes", "telefonia", "operadora", "operadoras", "5g", "anatel",
            "software", "totvs", "locaweb", "positivo",
        ),
        "nomes": ("Vivo", "TIM"),
        "empresas": ("VIVT3", "TIMS3", "TOTS3", "LWSA3"),
        "importa": ("Teles têm receita recorrente e investimento pesado em rede. Empresas de software "
                    "dependem do crescimento da base de clientes, e por isso costumam ser sensíveis "
                    "aos juros. Em ambos os casos, a disputa por clientes e a regulação definem quanto da "
                    "receita vira lucro."),
        "acompanhar": "Decisões da Anatel, leilões de espectro, consolidação entre operadoras e "
                      "indicadores de receita recorrente nos balanços.",
    },
    "TRANSPORTE & LOGÍSTICA": {
        "nome": "Transporte e logística",
        "consulta": (
            '("logística" OR "Rumo" OR "concessão de rodovias" OR "ferrovias" OR "aéreas" OR '
            '"Azul" OR "Gol")'
        ),
        "termos": (
            "logistica", "aviacao", "aereas", "companhias aereas", "rodovia", "rodovias",
            "ferrovia", "ferrovias", "porto", "portos", "aeroporto", "aeroportos", "concessao",
            "concessoes", "frete", "motiva", "ecorodovias", "localiza",
        ),
        "nomes": ("Azul", "Gol", "Rumo"),
        "empresas": ("RAIL3", "MOTV3", "ECOR3", "VAMO3", "RENT3"),
        "importa": ("Transporte é sensível ao preço do combustível, ao volume da economia e, no caso "
                    "das concessões, às regras contratuais e aos juros, que pesam em empresas muito "
                    "endividadas. A safra agrícola também influencia o volume transportado por "
                    "ferrovias e rodovias ao longo do ano."),
        "acompanhar": "Preço do diesel e do querosene de aviação, volumes de carga e passageiros, "
                      "novos leilões de concessão e o calendário de safra.",
    },
}


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto or ""))
                   if not unicodedata.combining(c)).lower()


def _dias_uteis(inicio, fim):
    dia = inicio
    while dia <= fim:
        if dia.weekday() < 5:
            yield dia
        dia += timedelta(days=1)


def _desempate(dia, setor):
    return hashlib.sha256(f"{dia.isoformat()}|{setor}".encode("utf-8")).hexdigest()


@lru_cache(maxsize=64)
def _planos(ate, setores, n):
    """{dia_util: tupla ordenada de setores} de EPOCA até `ate`. Ordem do
    dia: quem está há mais tempo sem aparecer entre os n primeiros vem
    antes (nunca apareceu = primeiro); empate pelo hash da data."""
    ultimo = {}
    planos = {}
    inicio = min(EPOCA, ate)
    for dia in _dias_uteis(inicio, ate):
        ordem = tuple(sorted(setores, key=lambda s: (ultimo.get(s, date.min), _desempate(dia, s))))
        planos[dia] = ordem
        for s in ordem[:n]:
            ultimo[s] = dia
    return planos


def plano_do_dia(dia, catalogo=None, n=QTD_SETORES):
    """Ordem completa dos setores para a edição de `dia` (os n primeiros
    são os planejados; os seguintes, os substitutos em ordem). Fim de
    semana usa o plano do último dia útil."""
    setores = tuple(sorted(catalogo or CATALOGO))
    while dia.weekday() >= 5:
        dia -= timedelta(days=1)
    return list(_planos(dia, setores, n)[dia])


def historico_planos(ate, dias=10, catalogo=None, n=QTD_SETORES):
    """Os setores planejados (n primeiros) dos últimos `dias` dias úteis
    até `ate` - o histórico de seleções, consultável sem banco."""
    setores = tuple(sorted(catalogo or CATALOGO))
    while ate.weekday() >= 5:
        ate -= timedelta(days=1)
    planos = _planos(ate, setores, n)
    datas = sorted(planos)[-dias:]
    return [(d, list(planos[d][:n])) for d in datas]


# ------------------------------------------------------------------
# Evidência
# ------------------------------------------------------------------

# Contexto de mercado exigido no PRÓPRIO título, além do termo do setor.
# Achado do exemplo real de 18/10/2026: só com palavra-chave entraram
# "Tecnologia detecta mais de 80 tiros em Niterói" (Tecnologia), "Papa
# Leão 14 reza o Angelus após deixar hospital" (Saúde) e um edital social
# do Banco do Brasil (Bancos) - citam o setor, mas não são notícia dele.
CONTEXTO_MERCADO = (
    "acoes", "acao", "bolsa", "bolsas", "ibovespa", "b3", "lucro", "lucros", "prejuizo", "receita", "receitas",
    "balanco", "balancos", "resultado", "resultados", "trimestre", "dividendos", "jcp", "mercado", "investimento",
    "investimentos", "investidores", "credito", "juros", "selic", "preco", "precos", "tarifa", "tarifas",
    "tarifaria", "reajuste", "reajustes", "leilao", "leiloes", "concessao", "concessoes", "producao", "demanda",
    "exportacao", "exportacoes", "importacao", "importacoes", "vendas", "faturamento", "margem", "margens",
    "divida", "dividas", "debentures", "ipo", "aquisicao", "aquisicoes", "fusao", "privatizacao", "regulacao",
    "anatel", "aneel", "ans", "anp", "cvm", "cade", "valor de mercado", "recorde", "bilhao", "bilhoes",
    "safra", "cotacao", "barril", "inadimplencia", "spread", "provisao", "provisoes", "operacional", "guidance", "rebaixa", "eleva",
    "recomendacao", "rating", "oferta", "estoques", "custos", "inflacao", "%",
)


def _tem_termo(texto, termos):
    for termo in termos:
        t = _sem_acento(termo)
        if t == "%":
            if "%" in texto:
                return True
        elif re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", texto):
            return True
    return False


def _tem_nome(titulo, nomes):
    """Nomes de empresa que também são palavras comuns ("Vale", "Gol",
    "TIM", "Azul", "Rumo") - comparados com maiúscula, no título original;
    "Vale a pena" e "Vale + infinitivo" não contam."""
    for nome in nomes:
        # "Vale a pena", "Vale manter/investir..." são o verbo, não a empresa
        if re.search(rf"(?<![\w-]){re.escape(nome)}(?![\w-])(?! a pena)(?! [a-zà-ú]+(?:ar|er|ir)\b)",
                     str(titulo or "")):
            return True
    return False


_TICKER_ACAO = re.compile(r"\b[A-Z]{4}(?:3|4|5|6|11|32|33|34)\b")


def _tickers_do_titulo(titulo):
    """Só tickers de AÇÃO escritos no próprio título - não os tickers do
    grupo inteiro de notícias (no exemplo real, uma manchete sobre o plano
    fiscal de um candidato herdou PETR4/VALE3/WINZ26 dos outros títulos do
    grupo e caiu em Petróleo)."""
    return sorted(set(_TICKER_ACAO.findall(str(titulo or ""))))


def _menciona_setor(titulo, setor, tickers=()):
    """O título cita o setor (termo forte do catálogo, palavra inteira, ou
    ticker do setor escrito no título) E tem contexto de mercado.
    `tickers` é ignorado de propósito - ver _tickers_do_titulo."""
    cfg = CATALOGO[setor]
    texto = _sem_acento(titulo)
    for trecho in cfg.get("exclui", ()):
        texto = texto.replace(_sem_acento(trecho), " ")
    cita = (_tem_termo(texto, cfg["termos"]) or _tem_nome(titulo, cfg.get("nomes", ()))
            or bool(set(_tickers_do_titulo(titulo)) & set(cfg["empresas"])))
    return cita and _tem_termo(texto, CONTEXTO_MERCADO)


def validar_fonte(item, inicio, agora):
    """Fonte verificável: título, veículo, data dentro de [inicio, agora+1h]
    e link http(s) com domínio. Devolve (ok, motivo)."""
    if not str(item.get("titulo") or "").strip():
        return False, "sem título"
    veiculos = item.get("veiculos") or ([item["veiculo"]] if item.get("veiculo") else [])
    if not veiculos or not str(veiculos[0]).strip():
        return False, "sem veículo"
    link = str(item.get("link") or "")
    partes = urlparse(link)
    if partes.scheme not in ("http", "https") or not partes.netloc:
        return False, "link inválido"
    try:
        momento = datetime.fromisoformat(str(item.get("data")))
    except (TypeError, ValueError):
        return False, "sem data"
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=TZ_SP)
    if momento < inicio:
        return False, "fora da janela da edição"
    if momento > agora + timedelta(hours=1):
        return False, "data no futuro"
    return True, None


def _fonte(item):
    veiculos = item.get("veiculos") or [item.get("veiculo")]
    momento = datetime.fromisoformat(str(item["data"]))
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=TZ_SP)
    return {"titulo": str(item["titulo"]).strip(), "veiculo": str(veiculos[0]).strip(),
            "data": momento.astimezone(TZ_SP), "link": str(item["link"]),
            "tickers": _tickers_do_titulo(item["titulo"]), "importancia": item.get("importancia") or 0}


# Publicação legal paga ("Edital de Leilão ITAÚ UNIBANCO S/A", visto no
# exemplo real de 18/10/2026): aviso, não notícia sobre o setor.
_AVISO_LEGAL = re.compile(r"^\s*(edital|aviso|ata|convoca[cç][aã]o|fato relevante:?\s*$)\b", re.IGNORECASE)


def evidencias_do_setor(setor, itens, inicio, agora, confiavel=None, mesmo_fato=None, fora_de_pauta=None):
    """(fontes, motivo) - fontes validadas do setor, sem duplicata do
    mesmo fato, mais importantes primeiro. motivo != None quando a
    evidência é insuficiente: menos de MIN_FONTES de veículos diferentes
    ou nenhum veículo da lista de confiáveis do app."""
    confiavel = confiavel or (lambda _v: True)
    mesmo_fato = mesmo_fato or (lambda a, b: a["titulo"] == b["titulo"])
    fora_de_pauta = fora_de_pauta or (lambda _t: False)
    candidatos = []
    for item in sorted(itens or [], key=lambda i: -(i.get("importancia") or 0)):
        ok, _motivo = validar_fonte(item, inicio, agora)
        if not ok or fora_de_pauta(item.get("titulo")) or _AVISO_LEGAL.match(str(item.get("titulo") or "")):
            continue
        if not _menciona_setor(item.get("titulo"), setor, item.get("tickers")):
            continue
        fonte = _fonte(item)
        if any(mesmo_fato(fonte, f) for f in candidatos):
            continue
        candidatos.append(fonte)
    # veículos da lista de confiáveis primeiro, depois importância
    candidatos.sort(key=lambda f: (not confiavel(f["veiculo"]), -f["importancia"]))
    veiculos = {f["veiculo"] for f in candidatos}
    if len(candidatos) < MIN_FONTES or len(veiculos) < MIN_FONTES:
        return candidatos, (f"evidência insuficiente: {len(candidatos)} notícia(s) válida(s) de "
                            f"{len(veiculos)} veículo(s) na janela da edição")
    if not any(confiavel(v) for v in veiculos):
        return candidatos, "evidência insuficiente: nenhum veículo da lista de fontes confiáveis"
    return candidatos, None


# ------------------------------------------------------------------
# Redação
# ------------------------------------------------------------------

def _palavras(texto):
    return len(re.findall(r"\S+", texto))


def _frase_fato(fonte):
    titulo = fonte["titulo"].rstrip(" .")
    return f"{fonte['veiculo']} ({fonte['data'].strftime('%d/%m')}): “{titulo}”."


def _escolher_fontes(fontes):
    """Até MAX_FATOS fontes, de veículos diferentes primeiro."""
    escolhidas, vistos = [], set()
    for f in fontes:
        if f["veiculo"] not in vistos:
            escolhidas.append(f)
            vistos.add(f["veiculo"])
    for f in fontes:
        if f not in escolhidas:
            escolhidas.append(f)
    return escolhidas[:MAX_FATOS]


def redigir_bloco(setor, fontes):
    """Bloco do setor a partir de fontes JÁ validadas. Mantém entre
    PALAVRAS_MIN e PALAVRAS_MAX palavras ajustando quantas manchetes entram
    (nunca acrescenta texto que não seja da fonte ou do catálogo)."""
    cfg = CATALOGO[setor]
    escolhidas = _escolher_fontes(fontes)

    def _empresas(publicadas):
        # só tickers escritos nas manchetes QUE SAEM no bloco (no exemplo
        # real apareciam tickers de notícias candidatas não publicadas)
        citadas = sorted({t for f in publicadas for t in _tickers_do_titulo(f["titulo"])})
        do_setor = [t for t in cfg["empresas"] if t not in citadas]
        partes = []
        if citadas:
            partes.append("Citadas nas notícias: " + ", ".join(citadas) + ".")
        partes.append("Principais do setor no Ibovespa: " + ", ".join(do_setor or cfg["empresas"]) + ".")
        return " ".join(partes)

    def _montar(qtd):
        fatos = [_frase_fato(f) for f in escolhidas[:qtd]]
        empresas = _empresas(escolhidas[:qtd])
        total = _palavras(" ".join(fatos + [cfg["importa"], empresas, cfg["acompanhar"]]))
        return fatos, empresas, total

    qtd = len(escolhidas)
    fatos, empresas, total = _montar(qtd)
    while total > PALAVRAS_MAX and qtd > MIN_FONTES:
        qtd -= 1
        fatos, empresas, total = _montar(qtd)
    return {
        "setor": setor,
        "nome": cfg["nome"],
        "o_que_aconteceu": fatos,
        "por_que_importa": cfg["importa"],
        "empresas": empresas,
        "acompanhar": cfg["acompanhar"],
        "fontes": escolhidas[:qtd],
        "palavras": total,
    }


def montar_radar(agora, buscar, inicio, confiavel=None, mesmo_fato=None, fora_de_pauta=None,
                 n=QTD_SETORES, catalogo=None):
    """Radar da edição: segue plano_do_dia, consulta `buscar(setor)` (lista
    de notícias do coletor) até ter n setores com evidência suficiente ou
    esgotar MAX_TENTATIVAS. Devolve {"setores", "excluidos", "plano",
    "historico"} - "excluidos" registra cada setor pulado e o motivo."""
    ordem = plano_do_dia(agora.date(), catalogo, n)
    setores, excluidos = [], []
    for setor in ordem[:MAX_TENTATIVAS]:
        if len(setores) == n:
            break
        try:
            itens = buscar(setor)
        except Exception as exc:
            excluidos.append({"setor": setor, "nome": CATALOGO[setor]["nome"],
                              "motivo": f"coleta falhou: {type(exc).__name__}"})
            continue
        if itens is None:
            excluidos.append({"setor": setor, "nome": CATALOGO[setor]["nome"], "motivo": "coleta falhou"})
            continue
        fontes, motivo = evidencias_do_setor(setor, itens, inicio, agora, confiavel, mesmo_fato, fora_de_pauta)
        if motivo:
            excluidos.append({"setor": setor, "nome": CATALOGO[setor]["nome"], "motivo": motivo})
            continue
        setores.append(redigir_bloco(setor, fontes))
    return {"setores": setores, "excluidos": excluidos, "plano": ordem[:n],
            "historico": historico_planos(agora.date(), 5, catalogo, n)}
