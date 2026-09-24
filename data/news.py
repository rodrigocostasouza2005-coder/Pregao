# -*- coding: utf-8 -*-
"""Noticias por empresa via RSS do Google News (fase NOTICIAS).

So usamos o feed de busca do Google News (formato documentado, sem
scraping de HTML) - por isso, ao contrario de data/research/*, nao
precisa de impersonation de TLS nem checagem de robots.txt: e' um
endpoint de RSS publico pensado pra consumo automatizado.

Guardamos e mostramos so titulo, veiculo, data/hora e link - nunca o
texto da materia (mesma regra do modulo de research).

O score de confiabilidade (0-100, por regras simples, sem IA) e o selo
resultante sao so um indicador de contexto pro usuario formar a propria
opiniao - nao uma verificacao factual. A lista de fontes confiaveis e as
palavras-chave ficam aqui (nao em config.py) por pedido explicito: e'
detalhe de implementacao deste coletor, nao configuracao do app.
"""

import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import feedparser
import requests
import streamlit as st
import trafilatura
from googlenewsdecoder import gnewsdecoder

import config
from data import news_setores
from data.prices import obter_nome_yf

_TZ_SP = ZoneInfo("America/Sao_Paulo")
_HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
_TIMEOUT = 15
_TTL_COLETA = 20 * 60  # 20 min (dentro da janela de 15-30 min pedida)

_RSS_URL = "https://news.google.com/rss/search?q={termo}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

# --- TOP MERCADO: fontes -------------------------------------------------
# secao de negocios do Google News Brasil (headlines curadas pelo Google,
# nao e' busca) + busca pelos principais temas de mercado - testado nos
# dois formatos (curl real), ambos respondem
_URL_BUSINESS_BR = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=pt-BR&gl=BR&ceid=BR:pt-419"
_TEMAS_MERCADO = ["Ibovespa", "Copom", "Selic", "dólar", "IPCA", "fiscal", "Fed", "commodities"]
_TOP_MERCADO_QTD = 20

# --- TOP MERCADO INTERNACIONAL (PARTE D) ----------------------------------
# secao de negocios do Google News EUA + feeds diretos (link ja vem
# resolvido, sem obfuscacao do Google - nao precisam de <source> porque
# cada um so tem 1 veiculo, passado como veiculo_fixo em _montar_item_mercado).
# Bloomberg/WSJ/FT aparecem via Google News (nao tem feed proprio aqui,
# sao pagos - ver _VEICULOS_PROVAVEL_PAYWALL).
_URL_BUSINESS_US = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"
_FEEDS_DIRETOS_INTERNACIONAIS = {
    "CNBC": "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    "MarketWatch": "http://feeds.marketwatch.com/marketwatch/topstories/",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
}

# termos de mercado usados no score de IMPORTANCIA (ranking do TOP
# MERCADO) - lista diferente de _TERMOS_SENSACIONALISTAS/_TERMOS_RUMOR,
# aqui a presenca do termo SOMA pontos (indica pauta de mercado "quente"),
# nao tem relacao com confiabilidade. Termos em portugues e ingles, pra
# noticia internacional tambem pontuar (Parte D).
_PALAVRAS_MERCADO_SCORE = {
    "copom", "ibovespa", "dolar", "selic", "juros", "fiscal", "ipca", "fed",
    "petroleo", "minerio", "inflacao", "pib", "cambio", "banco central", "commodities",
    "inflation", "interest rate", "rate cut", "rate hike", "gdp", "earnings",
    "jobs report", "cpi", "nasdaq", "dow jones", "treasury", "oil", "gold",
}

# tickers da B3: 4 letras + 1-2 digitos (ex: PETR4, VALE3, BBAS3) -
# usado so pra destacar tickers citados na manchete no TOP MERCADO, nao
# pra validar se o ticker existe de verdade (isso e' com yfinance)
_TICKER_NA_MANCHETE = re.compile(r"\b[A-Z]{4}\d{1,2}\b")

# --- Score de confiabilidade: fontes e palavras-chave --------------------

# veiculos financeiros/economicos estabelecidos - casamento por substring
# (sem acento, minusculo) contra o nome do veiculo ja normalizado (ver
# _normalizar_veiculo abaixo)
_FONTES_CONFIAVEIS = {
    "valor", "infomoney", "estadao", "folha", "globo", "reuters", "bloomberg",
    "exame", "brazil journal", "money times", "e-investidor", "einvestidor",
    "pipeline", "neofeed",
    # internacionais (PARTE D)
    "cnbc", "marketwatch", "yahoo finance", "wall street journal", "wsj",
    "financial times", "associated press", "ap news",
}

# linguagem sensacionalista - alem dessas palavras, titulo com "!!" tambem conta
_TERMOS_SENSACIONALISTAS = ["urgente", "bomba", "explode", "explodiu", "desaba", "desabou"]

# termos que sinalizam informacao ainda nao confirmada
_TERMOS_RUMOR = ["fontes dizem", "rumor", "estuda", "pode"]

# selo reservado pra fase CVM (fato relevante confirmado oficialmente) -
# nenhuma regra abaixo atribui esse selo ainda, so o valor ja existe pra
# quando essa fase for implementada
SELO_CONFIRMADA = "CONFIRMADA"

# selo de relevancia (nao de confiabilidade): a empresa so aparece de
# passagem no titulo (ex: citada numa lista de altas do Ibovespa), nao e'
# o assunto principal da materia - ver _relevante()
SELO_MENCAO = "MENÇÃO"

# --- Paginas que nao sao noticia -------------------------------------------
# sites de dados (Investidor10, Status Invest etc) publicam noticia de
# verdade ("/noticias/...") mas tambem tem paginas fixas de cotacao/perfil
# do ativo, que o Google as vezes indexa junto na busca - o titulo dessas
# paginas segue um padrao bem reconhecivel (nao muda por materia), entao
# filtramos por padrao de titulo (nao da pra usar a URL: so temos o link
# ofuscado do Google News nesse ponto, resolver todo link seria caro).
# Lista de regex (aplicadas sem acento/minusculo) - adicionar novos
# padroes aqui conforme forem aparecendo.
_PADROES_PAGINA_NAO_NOTICIA = [
    re.compile(r"resultados,?\s+dividendos,?\s+cotacao\s+e\s+indicadores"),  # Investidor10
    re.compile(r"cotacao\s+e\s+indicadores\s+hoje"),
    re.compile(r"\bstatus\s+invest\b"),  # titulo de pagina de ativo do Status Invest
    re.compile(r"preco\s+da\s+acao\s+hoje"),
    re.compile(r"^[a-z]{4}\d{1,2}\s*[-–:]\s*.+\s*[-–:]\s*cotacao\b"),  # "TICKER - Nome - Cotação..."
]


def _e_pagina_de_cotacao(titulo: str) -> bool:
    """True se o titulo bate com o padrao de pagina fixa de cotacao/perfil
    de ativo (nao e' materia jornalistica) - ver _PADROES_PAGINA_NAO_NOTICIA."""
    t = _sem_acento(titulo)
    return any(p.search(t) for p in _PADROES_PAGINA_NAO_NOTICIA)


# --- Paginas "ao vivo" / live blog -----------------------------------------
# cobertura continua de pregao ("Ibovespa Hoje Ao Vivo", "Bolsa em Tempo
# Real") nao e' uma materia sobre uma empresa especifica - o titulo so cita
# tickers de passagem, no resumo do dia. Filtrada da aba NEWS por ticker (so
# gera ruido - ver _montar_item); no TOP MERCADO vira uma tag "AO VIVO" em
# vez de filtrada (ver _montar_item_mercado/ui/top_mercado_tab.py).
_PADROES_AO_VIVO = [
    re.compile(r"\bao\s+vivo\b"),
    re.compile(r"\btempo\s+real\b"),
]


def _e_pagina_ao_vivo(titulo: str) -> bool:
    t = _sem_acento(titulo)
    return any(p.search(t) for p in _PADROES_AO_VIVO)


# --- Retencao: noticia e' conteudo perecivel, nao guarda historico longo --
_RETENCAO_DIAS = 5


def _dentro_da_retencao(data_iso: str) -> bool:
    """True se `data_iso` tiver menos de _RETENCAO_DIAS dias. Data invalida
    ou vazia conta como "dentro" (nunca inventa exclusao por falta de
    dado - so filtra o que sabe de fato que esta velho)."""
    if not data_iso:
        return True
    try:
        dt = datetime.fromisoformat(data_iso)
    except Exception:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_TZ_SP)
    return (datetime.now(_TZ_SP) - dt) < timedelta(days=_RETENCAO_DIAS)

# --- Normalizacao de nome de veiculo: dominio -> nome de exibicao --------
# so pras excecoes onde o titulo que o Google News da pro veiculo vem cru
# (o proprio dominio, ex: "suno.com.br") ou junta palavras que so um mapa
# manual resolve direito (ex: "financenews.com.br" -> "Finance News").
# Fora daqui, ou usamos o titulo que o Google ja manda formatado
# ("InfoMoney", "Estadão"...), ou derivamos algo razoavel do dominio.
_VEICULO_POR_DOMINIO = {
    "suno.com.br": "Suno",
    "seudinheiro.com": "Seu Dinheiro",
    "investidor10.com.br": "Investidor10",
    "moneytimes.com.br": "Money Times",
    "infomoney.com.br": "InfoMoney",
    "estadao.com.br": "Estadão",
    "einvestidor.estadao.com.br": "E-Investidor",
    "valor.globo.com": "Valor Econômico",
    "oglobo.globo.com": "O Globo",
    "g1.globo.com": "G1",
    "folha.uol.com.br": "Folha de S.Paulo",
    "uol.com.br": "UOL",
    "exame.com": "Exame",
    "braziljournal.com": "Brazil Journal",
    "neofeed.com.br": "NeoFeed",
    "pipelinevalor.globo.com": "Pipeline",
    "reuters.com": "Reuters",
    "bloomberglinea.com.br": "Bloomberg Línea",
    "cnnbrasil.com.br": "CNN Brasil",
    "financenews.com.br": "Finance News",
    # internacionais (PARTE D)
    "cnbc.com": "CNBC",
    "marketwatch.com": "MarketWatch",
    "finance.yahoo.com": "Yahoo Finance",
    "bloomberg.com": "Bloomberg",
    "wsj.com": "Wall Street Journal",
    "ft.com": "Financial Times",
    "apnews.com": "AP News",
}

# --- Normalizacao de titulo: stopwords e sinonimos ------------------------
# stopwords de baixo sinal, removidas so na comparacao de similaridade
# (nunca no titulo exibido)
_STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "em", "no", "na",
    "nos", "nas", "um", "uma", "uns", "umas", "para", "por", "com", "sem",
    "sobre", "entre", "que", "e", "ou", "ao", "aos", "mais", "menos",
    "como", "seu", "sua", "seus", "suas", "este", "esta", "isso", "sera",
    "foi", "ser", "tem", "ter", "ha", "apos", "ate", "num", "numa", "pelo",
    "pela", "pelos", "pelas", "outro", "outra", "outros", "outras",
}

# veiculos diferentes escolhem verbos diferentes pro mesmo fato ("compra"
# vs "adquire", "dispara" vs "sobe") - canonizar pra um token comum deixa
# a comparacao de similaridade mais tolerante a isso, sem precisar de IA
_SINONIMOS = {
    "compra": "adquire", "comprou": "adquire", "compram": "adquire", "adquiriu": "adquire",
    "vende": "aliena", "vendeu": "aliena", "alienou": "aliena",
    "dispara": "sobe", "disparou": "sobe", "subiu": "sobe", "avanca": "sobe", "avancou": "sobe",
    "desaba": "cai", "desabou": "cai", "caiu": "cai", "despenca": "cai", "despencou": "cai",
    "recua": "cai", "recuou": "cai",
    "lucro": "resultado", "lucros": "resultado", "prejuizo": "resultado",
    "anunciou": "anuncia", "revela": "anuncia", "divulga": "anuncia", "divulgou": "anuncia",
}

_LIMIAR_SIMILARIDADE = 0.55  # sobreposicao de tokens (ver _similaridade) pra agrupar 2 noticias como o mesmo fato
_JANELA_DIAS_GRUPO = 4  # so agrupa noticias dentro dessa distancia de dias uma da outra


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _tokenizar(texto: str) -> list:
    brutos = re.findall(r"[a-z0-9]+", _sem_acento(texto))
    return [_SINONIMOS.get(t, t) for t in brutos]


def _tokens_similaridade(titulo: str, ticker: str) -> set:
    """Bag-of-words pra comparar titulos: sem acento/pontuacao, sinonimos
    canonizados, sem stopword, sem palavras curtas (<3) e sem o proprio
    ticker (aparece em todo titulo da busca, nao ajuda a discriminar)."""
    tokens = _tokenizar(titulo)
    ticker_lower = ticker.lower()
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS and t != ticker_lower}


def _similaridade(a: set, b: set) -> float:
    """Coeficiente de sobreposicao (intersecao / menor conjunto) em vez de
    Jaccard puro: mais tolerante quando um veiculo escreve o titulo bem
    mais detalhado que outro sobre o mesmo fato."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _nome_curto(ticker: str, nome_empresa: str) -> str:
    """Primeira palavra do nome COMUM da empresa (sem acento) - prioriza
    config.TICKER_NOME (excecoes cadastradas pro app inteiro, ex:
    'PETR4'->'Petrobras') sobre o longName do yfinance: pra' alguns
    papeis (Petrobras e' o caso confirmado) o longName e' o nome legal
    completo ('Petróleo Brasileiro S.A. - Petrobras'), cuja primeira
    palavra ('Petróleo') nunca aparece no noticiario, que sempre usa o
    nome comum. So cai pro longName quando nao ha excecao cadastrada."""
    nome = config.TICKER_NOME.get(ticker) or nome_empresa or ""
    return _sem_acento(nome).split()[0] if nome else ""


def _relevante(ticker: str, nome_empresa: str, titulo: str) -> bool:
    """A empresa precisa aparecer pelo nome ou pelo ticker no TITULO (nao
    so em algum lugar da materia) pra contar como noticia dela - senao e'
    so uma mencao de passagem (ex: citada numa lista de altas do dia)."""
    tokens = set(_tokenizar(titulo))
    if ticker.lower() in tokens:
        return True
    primeiro_nome = _nome_curto(ticker, nome_empresa)
    return bool(primeiro_nome) and primeiro_nome in tokens


def _dominio_raiz(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _normalizar_veiculo(fonte: dict) -> str:
    """Nome de exibicao do veiculo: mapa de dominio (excecoes conhecidas)
    > titulo que o Google ja manda formatado > nome derivado do dominio."""
    href = (fonte.get("href") or "").strip()
    titulo_bruto = (fonte.get("title") or "").strip()
    dominio = _dominio_raiz(href) if href else ""

    if dominio in _VEICULO_POR_DOMINIO:
        return _VEICULO_POR_DOMINIO[dominio]
    if titulo_bruto and "." not in titulo_bruto:
        return titulo_bruto
    if dominio:
        return dominio.split(".")[0].capitalize()
    return titulo_bruto or "Desconhecido"


def _e_fonte_confiavel(veiculo: str) -> bool:
    veiculo_normalizado = _sem_acento(veiculo)
    return any(f in veiculo_normalizado for f in _FONTES_CONFIAVEIS)


def eh_fonte_confiavel(veiculo: str) -> bool:
    """Versao publica de _e_fonte_confiavel, pra UI usar (ex: ordenar
    veiculos com as fontes confiaveis primeiro no card de detalhes)."""
    return _e_fonte_confiavel(veiculo)


def _calcular_score(titulos: list, veiculos: list) -> tuple:
    """Score 0-100 por regras (sem IA) + lista das regras que contaram,
    pra interface mostrar o motivo no tooltip do selo."""
    score = 50
    regras = []
    texto = _sem_acento(" ".join(titulos))

    confiaveis = sorted({v for v in veiculos if _e_fonte_confiavel(v)})
    if confiaveis:
        score += 25
        regras.append(f"veículo confiável: {', '.join(confiaveis)}")

    n_fontes = len(set(veiculos))
    if n_fontes > 1:
        score += min((n_fontes - 1) * 10, 25)
        regras.append(f"{n_fontes} fontes independentes reportando o mesmo fato")

    sensacionalistas = [t for t in _TERMOS_SENSACIONALISTAS if t in texto]
    excesso_exclamacao = texto.count("!") >= 2
    if sensacionalistas or excesso_exclamacao:
        score -= 20
        motivo = ", ".join(sensacionalistas) or "excesso de exclamação"
        regras.append(f"linguagem sensacionalista: {motivo}")

    rumores = [t for t in _TERMOS_RUMOR if t in texto]
    if rumores:
        score -= 15
        regras.append(f"termo de rumor: '{rumores[0]}'")

    return max(0, min(100, score)), regras


def _selo(score: int) -> str:
    if score >= 70:
        return "PROVÁVEL"
    if score >= 40:
        return "NÃO CONFIRMADA"
    return "SUSPEITA"


# --- Coleta ----------------------------------------------------------------


def _buscar_feed_de_url(url: str):
    """Baixa e faz parse de um RSS do Google News (busca ou secao fixa).
    None so em falha real de requisicao (timeout, HTTP erro, XML
    ilegivel) - nunca inventa noticia. Uma busca que respondeu bem mas
    nao achou nada retorna lista vazia, nao None: sao coisas diferentes
    pra interface ("fonte indisponivel" vs "nenhuma noticia encontrada")."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
    except Exception:
        return None
    feed = feedparser.parse(r.content)
    if feed.bozo and not feed.entries:
        return None
    return feed.entries


def _buscar_feed(termo: str):
    return _buscar_feed_de_url(_RSS_URL.format(termo=quote(termo)))


def _extrair_veiculo_e_titulo(entry) -> tuple:
    """O Google News manda o veiculo na tag <source> (feedparser expoe em
    entry.source.title/.href); quando falta, o titulo normalmente vem
    como 'Manchete - Veiculo' e a gente separa na marca."""
    titulo = (entry.get("title") or "").strip()
    fonte = entry.get("source") or {}
    titulo_bruto_fonte = (fonte.get("title") or "").strip()
    veiculo = _normalizar_veiculo(fonte)

    sufixo = titulo_bruto_fonte or veiculo
    if sufixo and titulo.endswith(f" - {sufixo}"):
        titulo = titulo[: -(len(sufixo) + 3)].strip()
    elif not fonte and " - " in titulo:
        titulo, veiculo_bruto = (t.strip() for t in titulo.rsplit(" - ", 1))
        veiculo = _normalizar_veiculo({"title": veiculo_bruto})

    return titulo, veiculo


def _extrair_data(entry):
    """entry.published_parsed vem normalizado em UTC pelo feedparser;
    convertemos pro fuso de exibicao do app (America/Sao_Paulo)."""
    bruto = entry.get("published_parsed")
    if not bruto:
        return None
    return datetime(*bruto[:6], tzinfo=timezone.utc).astimezone(_TZ_SP)


def _montar_item(entry, ticker: str, nome_empresa: str):
    titulo, veiculo = _extrair_veiculo_e_titulo(entry)
    data = _extrair_data(entry)
    link = entry.get("link") or ""
    if not titulo or not link or data is None or _e_pagina_de_cotacao(titulo) or _e_pagina_ao_vivo(titulo):
        return None
    return {
        "titulo": titulo,
        "veiculo": veiculo,
        "link": link,
        "data": data,
        "relevante": _relevante(ticker, nome_empresa, titulo),
        "_tokens_sim": _tokens_similaridade(titulo, ticker),
    }


# nomes proprios candidatos (heuristica sem NER) sao usados so' pra UNIR
# grupos que citam a mesma entidade mesmo com titulos bem diferentes no
# resto (ver _mesmo_grupo) - termos genericos que aparecem em quase toda
# manchete de mercado (Ibovespa, Selic, Brasil...) tem que ficar de fora,
# senao viram falso-link entre materias sem relacao nenhuma
_ENTIDADE_IGNORAR = _PALAVRAS_MERCADO_SCORE | {
    "brasil", "brasileiro", "brasileira", "governo", "ministerio", "justica",
    "policia", "federal", "segunda", "terca", "quarta", "quinta", "sexta",
    "sabado", "domingo", "janeiro", "fevereiro", "marco", "abril", "maio",
    "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    "operacao", "operacoes", "caso", "processo", "investigacao",
}

# janela curta pra unir grupos so' por entidade em comum (nome proprio) -
# mais apertada que _JANELA_DIAS_GRUPO de proposito: entidade em comum
# sozinha e' um sinal mais fraco que similaridade de texto, entao so vale
# a pena confiar nele pra materias bem recentes uma da outra (mesmo caso
# sendo atualizado ao longo do dia, nao uma coincidencia de nome ao longo
# de semanas)
_JANELA_HORAS_ENTIDADE = 24


def _extrair_entidades(titulo: str) -> set:
    """Nomes proprios candidatos no titulo: sequencias de 2+ palavras
    capitalizadas consecutivas (ex: "Banco Genial", "Carbono Oculto") ou
    uma palavra capitalizada isolada com 5+ letras que nao seja um termo
    generico (ex: "Master") - separadores de palavra incluem pontuacao E
    hifen ("Ex-Banco" vira "Ex"+"Banco" duas palavras, nao um token colado
    - senao "Ex-Banco Genial" nunca bateria com "Banco Genial" sozinho).
    Pra sequencias de 3+ palavras, tambem gera as sub-janelas de 2 palavras
    (ex: "Caso Banco Genial" gera "banco genial" alem do trio inteiro) -
    senao um prefixo generico tipo "Caso"/"Processo" impede o match com
    outra materia que citou so' "Banco Genial". Sem acento pra comparar
    igual a resto do modulo. So' serve pra UNIR grupos (ver _mesmo_grupo)
    - nunca mostrado pro usuario."""
    palavras = [p for p in re.split(r"[^\wÀ-ÿ]+", titulo) if p]
    entidades = set()
    buffer = []

    def _fechar_buffer():
        if len(buffer) >= 2:
            for i in range(len(buffer) - 1):
                candidato = _sem_acento(" ".join(buffer[i:i + 2]))
                if candidato not in _ENTIDADE_IGNORAR:
                    entidades.add(candidato)
            if len(buffer) > 2:
                candidato = _sem_acento(" ".join(buffer))
                if candidato not in _ENTIDADE_IGNORAR:
                    entidades.add(candidato)
        elif len(buffer) == 1 and len(buffer[0]) >= 5:
            candidato = _sem_acento(buffer[0])
            if candidato not in _ENTIDADE_IGNORAR:
                entidades.add(candidato)

    for p in palavras:
        if p[0].isupper() and len(p) >= 3:
            buffer.append(p)
        else:
            _fechar_buffer()
            buffer = []
    _fechar_buffer()
    return entidades


def _mesmo_grupo(g: dict, item: dict, entidades_item: set) -> bool:
    """Decide se `item` entra no grupo `g` - 3 regras, na ordem:
    1. titulo identico (sem acento) SEMPRE junta, mesmo fora da janela de
       dias normal (a mesma manchete republicada semanas depois ainda e'
       a mesma materia).
    2. entidade principal (nome proprio) em comum dentro de
       _JANELA_HORAS_ENTIDADE - pega o mesmo caso sendo reportado com
       angulos/palavras bem diferentes (ex: "Banco Genial" e "Carbono
       Oculto" na mesma investigacao).
    3. regra padrao: similaridade de tokens dentro de _JANELA_DIAS_GRUPO,
       comparando contra TODOS os itens ja no grupo (nao so' o que abriu
       o grupo) - corrige grupos que iam se fragmentando conforme o
       titulo ia mudando aos poucos ao longo do dia (cada novo item so
       precisava bater com QUALQUER membro existente, nao com o
       original)."""
    if _sem_acento(g["titulo"]) == _sem_acento(item["titulo"]):
        return True

    dias_diff = abs((g["_data"] - item["data"]).days)
    horas_diff = abs((g["_data"] - item["data"]).total_seconds()) / 3600
    if horas_diff <= _JANELA_HORAS_ENTIDADE and g["_entidades"] & entidades_item:
        return True

    if dias_diff <= _JANELA_DIAS_GRUPO and any(
        _similaridade(tokens, item["_tokens_sim"]) >= _LIMIAR_SIMILARIDADE
        for tokens in g["_tokens_sim_todos"]
    ):
        return True

    return False


def _agrupar(itens: list) -> list:
    """Agrupa noticias que sao o mesmo fato reportado por veiculos
    diferentes ("reportada por N fontes"), mesmo com manchetes escritas
    de jeitos bem diferentes (ver _mesmo_grupo). Titulo/link do grupo =
    o item mais recente que abriu o grupo. relevante do grupo = relevante
    de QUALQUER item nele."""
    itens = sorted(itens, key=lambda i: i["data"], reverse=True)
    grupos = []
    for item in itens:
        entidades_item = _extrair_entidades(item["titulo"])
        grupo = next((g for g in grupos if _mesmo_grupo(g, item, entidades_item)), None)
        if grupo:
            grupo["fontes"].append({"veiculo": item["veiculo"], "link": item["link"]})
            grupo["titulos"].append(item["titulo"])
            grupo["relevante"] = grupo["relevante"] or item["relevante"]
            grupo["ao_vivo"] = grupo["ao_vivo"] or item.get("ao_vivo", False)
            grupo["_tokens_sim_todos"].append(item["_tokens_sim"])
            grupo["_entidades"] |= entidades_item
        else:
            grupos.append({
                "titulo": item["titulo"],
                "titulos": [item["titulo"]],
                "fontes": [{"veiculo": item["veiculo"], "link": item["link"]}],
                "data": item["data"],
                "link": item["link"],
                "relevante": item["relevante"],
                "ao_vivo": item.get("ao_vivo", False),
                "_tokens_sim_todos": [item["_tokens_sim"]],
                "_entidades": entidades_item,
                "_data": item["data"],
            })
    return grupos


@st.cache_data(ttl=_TTL_COLETA, show_spinner=False)
def obter_noticias(ticker: str):
    """Noticias de uma empresa (nome + ticker), agrupadas e com score de
    confiabilidade. None se a fonte falhar; [] se a fonte respondeu mas
    nao ha noticia nenhuma pro papel. Um grupo so entra no resultado se o
    ticker ou o nome da empresa aparecer no titulo de PELO MENOS um dos
    itens do grupo (ver _relevante) - senao e' ruido da busca (o Google
    News as vezes devolve materia que so cita a empresa de passagem no
    corpo do texto, nunca no titulo de nenhuma fonte) e nao e' noticia
    dessa empresa; nao mostramos mais isso com selo MENÇÃO, so deixamos
    de fora (antes gerava falso positivo tipo o card explicar "citada de
    passagem no título" quando o titulo mostrado nem citava a empresa).
    "fontes" carrega (veiculo, link) de cada materia do grupo - usado pra
    tentar resumir (ver obter_resumo_grupo), o "link" solto no topo e' so
    o da materia mais recente (o que a manchete do grupo mostra e abre).
    Filtra tambem noticias com mais de _RETENCAO_DIAS dias."""
    nome = obter_nome_yf(ticker)
    termo = f'"{nome}" {ticker}' if nome else ticker

    entries = _buscar_feed(termo)
    if entries is None:
        return None

    itens = [i for i in (_montar_item(e, ticker, nome) for e in entries) if i]
    if not itens:
        return []

    resultado = []
    for grupo in _agrupar(itens):
        if not grupo["relevante"]:
            continue
        if not _dentro_da_retencao(grupo["data"].isoformat()):
            continue
        veiculos = [f["veiculo"] for f in grupo["fontes"]]
        score, regras = _calcular_score(grupo["titulos"], veiculos)
        resultado.append({
            "ticker": ticker,
            "titulo": grupo["titulo"],
            "titulos": grupo["titulos"],
            "veiculos": sorted(set(veiculos)),
            "fontes": grupo["fontes"],
            "fontes_count": len(set(veiculos)),
            "data": grupo["data"].isoformat(),
            "link": grupo["link"],
            "score": score,
            "selo": _selo(score),
            "regras": regras,
            "tickers": sorted({t for titulo in grupo["titulos"] for t in _tickers_no_titulo(titulo)}),
        })

    resultado.sort(key=lambda n: n["data"], reverse=True)
    return resultado


def _mesclar_entre_tickers(noticias: list) -> list:
    """obter_noticias(ticker) ja agrupa DENTRO de um ticker (mesma busca);
    isso funde noticias de tickers DIFERENTES que sao o mesmo fato (ex:
    materia que cita duas empresas da watchlist, capturada nas buscas das
    duas) - mesma logica de similaridade de _agrupar, agora entre
    resultados ja processados. Quando um fato acaba envolvendo mais de um
    ticker, troca 'ticker' (singular) por 'tickers' (lista - mesmo formato
    que o TOP MERCADO usa, a UI ja sabe desenhar como tags)."""
    noticias = sorted(noticias, key=lambda n: n["data"], reverse=True)
    fundidas = []
    for n in noticias:
        tokens_n = _tokens_similaridade(n["titulo"], "")
        data_n = datetime.fromisoformat(n["data"])
        alvo = next(
            (f for f in fundidas
             if abs((f["_data_dt"] - data_n).days) <= _JANELA_DIAS_GRUPO
             and _similaridade(f["_tokens_sim"], tokens_n) >= _LIMIAR_SIMILARIDADE),
            None,
        )
        if alvo:
            tickers_fundidos = set(alvo.get("tickers") or ([alvo["ticker"]] if alvo.get("ticker") else []))
            tickers_fundidos |= {n["ticker"]} if n.get("ticker") else set(n.get("tickers") or [])
            alvo["tickers"] = sorted(tickers_fundidos)
            alvo.pop("ticker", None)
            veiculos_vistos = {f2["veiculo"] for f2 in alvo["fontes"]}
            for f2 in n["fontes"]:
                if f2["veiculo"] not in veiculos_vistos:
                    alvo["fontes"].append(f2)
                    veiculos_vistos.add(f2["veiculo"])
            alvo["veiculos"] = sorted(veiculos_vistos)
            alvo["fontes_count"] = len(veiculos_vistos)
            titulos_vistos = set(alvo.get("titulos") or [alvo["titulo"]])
            for t in (n.get("titulos") or [n["titulo"]]):
                titulos_vistos.add(t)
            alvo["titulos"] = sorted(titulos_vistos)
        else:
            item = dict(n)
            item["_tokens_sim"] = tokens_n
            item["_data_dt"] = data_n
            fundidas.append(item)
    for f in fundidas:
        del f["_tokens_sim"]
        del f["_data_dt"]
    return fundidas


def obter_noticias_watchlist(tickers: list) -> tuple:
    """Agrega obter_noticias de varios tickers, fundindo fatos que
    aparecem em mais de um (ver _mesclar_entre_tickers). Retorna
    (noticias, falhas) - falhas e' a lista de tickers cuja fonte nao
    respondeu, pra interface avisar sem esconder o resto do feed."""
    todas = []
    falhas = []
    for ticker in tickers:
        r = obter_noticias(ticker)
        if r is None:
            falhas.append(ticker)
            continue
        todas.extend(r)
    todas = _mesclar_entre_tickers(todas)
    todas.sort(key=lambda n: n["data"], reverse=True)
    return todas, falhas


# --- TOP MERCADO: ranking de importancia ----------------------------------


def _tickers_no_titulo(titulo: str) -> list:
    return sorted(set(_TICKER_NA_MANCHETE.findall(titulo)))


def _montar_item_mercado(entry, veiculo_fixo: str = None):
    """Como _montar_item, mas sem ticker/empresa especifica - nao ha
    filtro de relevancia aqui (todo item do TOP MERCADO e' "relevante"
    por definicao, nao existe SELO_MENCAO nesse contexto).

    veiculo_fixo: pros feeds diretos (CNBC/MarketWatch/Yahoo Finance -
    Parte D), que nao tem a tag <source> do Google News. Sem isso,
    _extrair_veiculo_e_titulo cairia no fallback de separar o titulo em
    ' - ' pra achar o veiculo, o que quebraria manchetes normais que
    tem esse padrao no meio do texto (comum em ingles)."""
    if veiculo_fixo:
        titulo = (entry.get("title") or "").strip()
        veiculo = veiculo_fixo
    else:
        titulo, veiculo = _extrair_veiculo_e_titulo(entry)
    data = _extrair_data(entry)
    link = entry.get("link") or ""
    if not titulo or not link or data is None or _e_pagina_de_cotacao(titulo):
        return None
    return {
        "titulo": titulo,
        "veiculo": veiculo,
        "link": link,
        "data": data,
        "relevante": True,
        "ao_vivo": _e_pagina_ao_vivo(titulo),
        "_tokens_sim": _tokens_similaridade(titulo, ""),
    }


def _calcular_importancia(titulos: list, veiculos: list, data_mais_recente) -> tuple:
    """Score de IMPORTANCIA pro ranking do TOP MERCADO - diferente do
    score de confiabilidade (_calcular_score). Nao existe fonte publica
    de "noticia mais lida", entao isso e' uma ESTIMATIVA por regras:
    numero de fontes cobrindo o fato (peso maior), recencia (decai
    linear ate zerar em 24h), veiculos confiaveis e presenca de termos
    de mercado no titulo. regras[] documenta o calculo pro tooltip da
    interface - sempre deixar claro que e' estimativa, nao medicao real
    de audiencia."""
    regras = []

    n_fontes = len(set(veiculos))
    pontos_fontes = n_fontes * 15
    regras.append(f"{n_fontes} fonte(s) cobrindo o fato (+{pontos_fontes})")

    horas = max(0.0, (datetime.now(_TZ_SP) - data_mais_recente).total_seconds() / 3600)
    pontos_recencia = round(max(0.0, 1 - horas / 24) * 25, 1)
    regras.append(f"recência: {horas:.1f}h atrás (+{pontos_recencia:g})")

    confiaveis = sorted({v for v in veiculos if _e_fonte_confiavel(v)})
    pontos_confiaveis = min(len(confiaveis) * 8, 20)
    if confiaveis:
        regras.append(f"veículo(s) confiável(is): {', '.join(confiaveis)} (+{pontos_confiaveis})")

    texto = _sem_acento(" ".join(titulos))
    temas = sorted({t for t in _PALAVRAS_MERCADO_SCORE if t in texto})
    pontos_temas = min(len(temas) * 6, 20)
    if temas:
        regras.append(f"tema(s) de mercado: {', '.join(temas)} (+{pontos_temas})")

    total = round(pontos_fontes + pontos_recencia + pontos_confiaveis + pontos_temas, 1)
    return total, regras


def _coletar_em_paralelo(tarefas: list) -> list:
    """tarefas: lista de (url, veiculo_fixo). Busca todas em paralelo
    (ThreadPoolExecutor leve - sao so downloads HTTP, nao CPU-bound) em
    vez de sequencial: o TOP MERCADO bate em ~8-10 fontes independentes
    (_TEMAS_MERCADO + feeds diretos), sequencial isso somava alguns
    segundos so' de rede. Cada fonte ja tem timeout proprio
    (_buscar_feed_de_url) e falha isolada (None, nunca lanca excecao) -
    o paralelismo so' economiza tempo de espera, nao muda o resultado.
    Retorna lista de (feed_ou_None, veiculo_fixo) na mesma ordem."""
    if not tarefas:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(tarefas))) as executor:
        feeds = list(executor.map(lambda t: _buscar_feed_de_url(t[0]), tarefas))
    return list(zip(feeds, (t[1] for t in tarefas)))


def _coletar_pool_brasil(setor: str) -> tuple:
    """Retorna (entries_por_link, alguma_fonte_ok). entries_por_link
    mapeia link -> (entry, veiculo_fixo) - veiculo_fixo=None aqui porque
    todo mundo nesse pool vem do Google News (tem <source>)."""
    entries_por_link = {}
    alguma_fonte_ok = False

    tarefas = [(_URL_BUSINESS_BR, None)]
    tarefas += [(_RSS_URL.format(termo=quote(tema)), None) for tema in _TEMAS_MERCADO]
    if setor != "TODOS":
        tarefas.append((_RSS_URL.format(termo=quote(news_setores.termo_busca(setor))), None))

    for feed, veiculo_fixo in _coletar_em_paralelo(tarefas):
        if feed is None:
            continue
        alguma_fonte_ok = True
        for e in feed:
            entries_por_link.setdefault(e.get("link"), (e, veiculo_fixo))

    return entries_por_link, alguma_fonte_ok


def _coletar_pool_internacional(setor: str) -> tuple:
    """Como _coletar_pool_brasil, mas fontes internacionais (Parte D):
    secao de negocios do Google News EUA + feeds diretos de CNBC/
    MarketWatch/Yahoo Finance (esses tem veiculo_fixo, ver
    _montar_item_mercado) + busca por setor quando setor != TODOS."""
    entries_por_link = {}
    alguma_fonte_ok = False

    tarefas = [(_URL_BUSINESS_US, None)]
    tarefas += [(url, veiculo) for veiculo, url in _FEEDS_DIRETOS_INTERNACIONAIS.items()]
    if setor != "TODOS":
        tarefas.append((_RSS_URL.format(termo=quote(news_setores.termo_busca(setor))), None))

    for feed, veiculo_fixo in _coletar_em_paralelo(tarefas):
        if feed is None:
            continue
        alguma_fonte_ok = True
        for e in feed:
            entries_por_link.setdefault(e.get("link"), (e, veiculo_fixo))

    return entries_por_link, alguma_fonte_ok


def _processar_pool(entries_por_link: dict, setor: str, regiao: str) -> list:
    """Monta os itens, agrupa (dedup), calcula score/importancia/setor e
    filtra pelo setor pedido - parte comum entre BRASIL, INTERNACIONAL e
    TUDO. 'regiao' ('BR'/'INT') so' fica marcada em cada resultado, pra
    interface poder mostrar a tag quando os dois pools estiverem juntos."""
    itens = [i for i in (_montar_item_mercado(e, vf) for e, vf in entries_por_link.values()) if i]
    if not itens:
        return []

    resultado = []
    for grupo in _agrupar(itens):
        if not _dentro_da_retencao(grupo["data"].isoformat()):
            continue
        veiculos = [f["veiculo"] for f in grupo["fontes"]]
        tickers = sorted({t for titulo in grupo["titulos"] for t in _tickers_no_titulo(titulo)})
        setores_grupo = news_setores.classificar_setores(" ".join(grupo["titulos"]), tickers)
        if setor != "TODOS" and setor not in setores_grupo:
            continue

        score_confianca, regras_confianca = _calcular_score(grupo["titulos"], veiculos)
        importancia, criterio_ranking = _calcular_importancia(grupo["titulos"], veiculos, grupo["data"])
        resultado.append({
            "titulo": grupo["titulo"],
            "titulos": grupo["titulos"],
            "veiculos": sorted(set(veiculos)),
            "fontes": grupo["fontes"],
            "fontes_count": len(set(veiculos)),
            "data": grupo["data"].isoformat(),
            "link": grupo["link"],
            "score": score_confianca,
            "selo": _selo(score_confianca),
            "regras": regras_confianca,
            "importancia": importancia,
            "criterio_ranking": criterio_ranking,
            "tickers": tickers,
            "setores": setores_grupo,
            "regiao": regiao,
            "ao_vivo": grupo.get("ao_vivo", False),
        })
    return resultado


@st.cache_data(ttl=_TTL_COLETA, show_spinner=False)
def obter_top_mercado(setor: str = "TODOS"):
    """As _TOP_MERCADO_QTD noticias mais "importantes" do momento no
    Brasil (ver _calcular_importancia) - secao de negocios do Google News
    Brasil + busca pelos principais temas de mercado. None so se TODAS as
    fontes falharem (nenhuma fonte parcial derruba o ranking - so fica
    com menos material pra rankear). setor != "TODOS": ver
    _coletar_pool_brasil/news_setores.classificar_setores."""
    entries_por_link, alguma_fonte_ok = _coletar_pool_brasil(setor)
    if not alguma_fonte_ok:
        return None
    resultado = _processar_pool(entries_por_link, setor, "BR")
    resultado.sort(key=lambda n: n["importancia"], reverse=True)
    return resultado[:_TOP_MERCADO_QTD]


@st.cache_data(ttl=_TTL_COLETA, show_spinner=False)
def obter_top_mercado_internacional(setor: str = "TODOS"):
    """Como obter_top_mercado, mas fontes internacionais (Google News EUA
    + CNBC/MarketWatch/Yahoo Finance - Parte D). Bloomberg/WSJ/FT
    costumam aparecer via Google News mas sao pagos (ver
    _VEICULOS_PROVAVEL_PAYWALL) - se um grupo so tiver fonte dessas, o
    resumo fica indisponivel e mostra so titulo+link. O resumo, quando
    sai, e' sempre em portugues (o prompt do Groq ja pede isso,
    independente do idioma do texto original)."""
    entries_por_link, alguma_fonte_ok = _coletar_pool_internacional(setor)
    if not alguma_fonte_ok:
        return None
    resultado = _processar_pool(entries_por_link, setor, "INT")
    resultado.sort(key=lambda n: n["importancia"], reverse=True)
    return resultado[:_TOP_MERCADO_QTD]


@st.cache_data(ttl=_TTL_COLETA, show_spinner=False)
def obter_top_mercado_tudo(setor: str = "TODOS"):
    """BRASIL + INTERNACIONAL ranqueados juntos (nao e' so concatenar os
    2 top-20 separados: processa os 2 pools - inteiros, antes do corte -
    e so' entao ordena e corta o total). Cada pool e' agrupado
    separadamente (nao junto): titulo em portugues e em ingles sobre o
    mesmo fato nunca teriam palavras em comum pro agrupador reconhecer
    mesmo assim, entao nao ha' vantagem em juntar antes - so' risco de
    comparar mais itens a toa. None so se os dois pools falharem."""
    br_entries, br_ok = _coletar_pool_brasil(setor)
    intl_entries, intl_ok = _coletar_pool_internacional(setor)
    if not br_ok and not intl_ok:
        return None

    resultado = []
    if br_ok:
        resultado += _processar_pool(br_entries, setor, "BR")
    if intl_ok:
        resultado += _processar_pool(intl_entries, setor, "INT")

    resultado.sort(key=lambda n: n["importancia"], reverse=True)
    return resultado[:_TOP_MERCADO_QTD]


# --- Resumo por grupo (sob demanda / automatico p/ watchlist nas ultimas 24h) --

_TTL_RESUMO = 24 * 60 * 60  # 24h - "por enquanto" em memoria (st.cache_data);
# quando gravarmos no Supabase (junto com o research, ver data/research/store.py),
# obter_resumo_grupo() e' o unico ponto que precisa trocar (checar a tabela antes
# de chamar Groq, salvar o resultado no lugar do cache) - a assinatura ja e'
# pura (titulo + fontes -> resultado), da pra embrulhar sem mexer em quem chama.

# veiculos com paywall conhecido pra materia comum (nao institucional) -
# tentamos essas por ultimo dentro do grupo, ja que costumam falhar
_VEICULOS_PROVAVEL_PAYWALL = {"valor", "estadao", "folha", "bloomberg", "wall street journal", "wsj", "financial times"}

# 5-8 linhas estruturadas precisam de mais espaco que o formato antigo
# (2-3 linhas livres) - budget proprio, maior que config.GROQ_MAX_TOKENS
# (compartilhado com o research, que usa um formato mais enxuto)
_MAX_TOKENS_RESUMO_NEWS = 700

_PROMPT_SISTEMA_RESUMO = (
    "Você resume notícias do mercado financeiro brasileiro em português, em "
    "5 a 8 linhas curtas, SEMPRE com suas próprias palavras - nunca copie "
    "frases literais do texto original. O texto fornecido foi extraído "
    "automaticamente de uma página web e pode conter trechos de menu, anúncio "
    "ou navegação misturados - ignore esse ruído e resuma só o conteúdo "
    "jornalístico. Formato fixo, uma linha por item, começando exatamente "
    "assim:\n"
    "O QUE ACONTECEU: ...\n"
    "NÚMEROS: ...\n"
    "IMPACTO: ...\n"
    "PRÓXIMOS PASSOS: ...\n"
    "Se algum campo não tiver informação no texto, escreva 'não informado' "
    "nesse campo - nunca invente números, datas ou fatos que não estejam no "
    "texto fornecido. Se não houver conteúdo jornalístico suficiente pra "
    "resumir, responda exatamente: SEM_CONTEUDO"
)

_PROMPT_SISTEMA_RESUMO_MANCHETES = (
    "Você resume um fato do mercado financeiro brasileiro a partir SÓ das "
    "manchetes de várias fontes sobre o mesmo fato - não teve acesso ao "
    "texto completo de nenhuma matéria (todas bloquearam o download). Use as "
    "manchetes fornecidas pra montar um resumo curto (3 a 5 linhas), SEMPRE "
    "com suas próprias palavras, mesmo formato fixo:\n"
    "O QUE ACONTECEU: ...\n"
    "NÚMEROS: ...\n"
    "IMPACTO: ...\n"
    "PRÓXIMOS PASSOS: ...\n"
    "Como só tem as manchetes (não o texto completo), vá direto ao que elas "
    "revelam - escreva 'não informado' em qualquer campo sem base nas "
    "manchetes, nunca invente número ou fato que não esteja nelas. Se as "
    "manchetes não derem pra montar nem isso, responda exatamente: "
    "SEM_CONTEUDO"
)


def _provavel_paywall(veiculo: str) -> bool:
    v = _sem_acento(veiculo)
    return any(p in v for p in _VEICULOS_PROVAVEL_PAYWALL)


def ordenar_fontes_para_resumo(fontes: list) -> tuple:
    """Ordena as fontes de um grupo pra tentativa de resumo: veiculos sem
    paywall conhecido primeiro. Retorna tupla de (veiculo, link) - formato
    hashable, exigido pelo cache de obter_resumo_grupo."""
    sem_paywall = [f for f in fontes if not _provavel_paywall(f["veiculo"])]
    com_paywall = [f for f in fontes if _provavel_paywall(f["veiculo"])]
    return tuple((f["veiculo"], f["link"]) for f in sem_paywall + com_paywall)


def _resolver_link_real(link_google_news: str):
    """O link do RSS do Google News e' um redirect ofuscado (SPA propria
    do Google, sem redirect HTTP de verdade) - gnewsdecoder replica o
    fluxo de decodificacao interno do Google pra achar a URL real do
    veiculo. None se nao conseguir (formato mudou, timeout etc)."""
    try:
        resultado = gnewsdecoder(link_google_news, interval=1)
    except Exception:
        return None
    if not resultado or not resultado.get("success"):
        return None
    return resultado.get("decoded_url") or None


def _extrair_texto_artigo(link_google_news: str) -> tuple:
    """Resolve o link real e extrai o texto com trafilatura. Retorna
    (texto, link_real, motivo_falha) - texto=None se o link nao resolveu,
    o download falhou ou o conteudo veio curto demais (paywall/bloqueio -
    mesmo limiar de 200 chars usado no resumo do research)."""
    link_real = _resolver_link_real(link_google_news)
    if not link_real:
        return None, None, "não foi possível resolver o link original"
    try:
        baixado = trafilatura.fetch_url(link_real)
    except Exception as e:
        return None, link_real, f"erro ao baixar: {e}"
    if not baixado:
        return None, link_real, "erro ao baixar a página"
    texto = trafilatura.extract(baixado, include_comments=False, include_tables=False)
    if not texto or len(texto) < 200:
        return None, link_real, "conteúdo muito curto (provável paywall/bloqueio)"
    return texto, link_real, None


def _resumir_com_groq(texto: str, titulo: str) -> tuple:
    """Resume via Groq (free tier, mesma API usada no research - ver
    data/research/resumir.py - mas com prompt proprio: aqui e' noticia
    curta em 2-3 linhas, la e' relatorio de research em topicos fixos).
    Chave/modelo vem de config.obter_credenciais_groq() (lugar unico,
    compartilhado com research). Retorna (resumo, motivo_falha);
    motivo_falha='cota' em 429."""
    chave, modelo = config.obter_credenciais_groq()
    if not chave:
        return None, "GROQ_API_KEY não configurada em st.secrets"

    texto_truncado = texto[:6000]
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
            json={
                "model": modelo,
                "messages": [
                    {"role": "system", "content": _PROMPT_SISTEMA_RESUMO},
                    {"role": "user", "content": f"Título: {titulo}\n\nTexto extraído da página:\n{texto_truncado}"},
                ],
                "temperature": 0.3,
                "max_tokens": config.GROQ_MAX_TOKENS,
                # gpt-oss e' modelo de raciocinio: sem isso ele gasta boa parte
                # do max_tokens "pensando" (campo message.reasoning) antes de
                # responder, e o resumo sai cortado no meio - visto na pratica
                # (raciocinio consumindo ~60 tokens de um orcamento de 200)
                "reasoning_effort": config.GROQ_REASONING_EFFORT,
            },
            timeout=30,
        )
        if r.status_code == 429:
            return None, "cota"
        r.raise_for_status()
        resumo = r.json()["choices"][0]["message"]["content"].strip()
        if resumo == "SEM_CONTEUDO":
            return None, "conteúdo insuficiente pra resumir"
        return resumo, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=_TTL_RESUMO, show_spinner=False)
def obter_resumo_grupo(titulo: str, fontes_ordenadas: tuple) -> dict:
    """Resumo de um GRUPO de noticias (mesmo fato, possivelmente varias
    fontes) - tenta cada fonte do grupo, na ordem recebida (ver
    ordenar_fontes_para_resumo), ate uma dar certo: resolve o link real,
    extrai o texto com trafilatura e resume com Groq, sempre em palavras
    proprias. Se TODAS as fontes falharem (paywall, bloqueio, sem
    conteudo), retorna resumo=None - a interface mostra so "resumo
    indisponível" e o link da materia continua disponivel normalmente
    (e' o link que a manchete do grupo ja usa).

    Cache em memoria por 24h (cache_data padrao do Streamlit) - "por
    enquanto", ver nota de _TTL_RESUMO sobre migrar pra Supabase depois.

    motivo_indisponivel guarda o motivo ESPECIFICO da ULTIMA fonte
    tentada (decode falhou / erro ao baixar / conteúdo curto / cota da
    IA) - a interface mostra isso em vez de um "indisponível" generico,
    ajuda a diferenciar bloqueio do servidor de paywall de verdade."""
    ultimo_motivo = "nenhuma fonte disponível no grupo"
    for veiculo, link in fontes_ordenadas:
        texto, link_real, motivo_extracao = _extrair_texto_artigo(link)
        if texto is None:
            ultimo_motivo = motivo_extracao or ultimo_motivo
            continue
        resumo, motivo_groq = _resumir_com_groq(texto, titulo)
        if resumo:
            return {"resumo": resumo, "link_original": link_real, "motivo_indisponivel": None}
        if motivo_groq == "cota" or "GROQ_API_KEY" in (motivo_groq or ""):
            # falha do Groq em si (cota/config), nao da fonte - tentar as
            # proximas fontes do grupo so repetiria o mesmo erro a toa
            return {"resumo": None, "link_original": link_real, "motivo_indisponivel": motivo_groq}
        ultimo_motivo = motivo_groq or ultimo_motivo
    return {"resumo": None, "link_original": None, "motivo_indisponivel": ultimo_motivo}
