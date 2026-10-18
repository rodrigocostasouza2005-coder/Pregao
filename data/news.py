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

import json
import logging
import time
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
from bs4 import BeautifulSoup

try:
    from googlenewsdecoder import gnewsdecoder
except Exception:
    # Dependencia transitiva (selectolax) pode ficar incompativel em
    # produçao sem aviso previo (ex: API legada removida numa versao
    # nova) - decoder vira opcional, News cai pro link original do
    # Google News em vez de derrubar o app inteiro no import.
    gnewsdecoder = None

import config
from data import ia_cache, news_setores
from data.coletores_status import registrar_tentativa
from data.cvm import documento_confirmador
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

# sufixo numerico real de ticker B3 (acao ON=3/PN=4/PNA-C=5-8, units/ETFs/
# FIIs=11, BDRs=32-39) - sem isso, _TICKER_NA_MANCHETE tambem casava
# codigo de contrato futuro (ex: WDOV26, WINV26 - 4 letras + ano com 2
# digitos, mesma forma de um ticker) e mostrava como se fosse uma acao
# nas tags do card/dialog da noticia (achado real, 2026-10-08).
# "54": bug real corrigido (auditoria 2026-10-10) - a AZUL trocou de
# AZUL4 pra AZUL54 em 23/12/2025 (ver data/news_setores.py, tickers de
# TRANSPORTE & LOGISTICA, e PROGRESSO.md) mas esse conjunto nunca foi
# atualizado; sem o "54", uma manchete tipo "AZUL54 sobe 5%..." (sem
# palavra-chave de setor) nunca reconhecia AZUL54 como ticker valido -
# a materia desaparecia silenciosamente ao filtrar por TRANSPORTE &
# LOGISTICA e a tag do ticker nunca aparecia no card.
_SUFIXOS_TICKER_VALIDOS = {"3", "4", "5", "6", "7", "8", "9", "11", "32", "33", "34", "35", "36", "37", "38", "39", "54"}

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

# titulo que e' SO' "Nome da Empresa (TICKER)" - pagina de perfil/cotacao
# do ativo, nunca uma materia de verdade (achado real testando ALPA4: o
# Google News as vezes indexa a propria pagina de cotacao de um agregador
# como se fosse uma "noticia"). O nome antes do ticker precisa ser CURTO
# (ate 4 palavras) pra nao filtrar por engano uma manchete de verdade que
# so' comece com o nome da empresa e va bem mais longe (ex: "Mercado
# Livre (MELI34) vai vender remedios..." tem muito mais texto depois -
# nao bate nesse padrao, que exige o titulo TERMINAR logo apos o ticker).
_PADRAO_SO_NOME_E_TICKER = re.compile(r"^([a-zà-ÿ&.,\s-]{2,40})\s*\([a-z]{4}\d{1,2}\)\s*$")


def _e_pagina_de_cotacao(titulo: str) -> bool:
    """True se o titulo bate com o padrao de pagina fixa de cotacao/perfil
    de ativo (nao e' materia jornalistica) - ver _PADROES_PAGINA_NAO_NOTICIA
    e _PADRAO_SO_NOME_E_TICKER."""
    t = _sem_acento(titulo)
    if any(p.search(t) for p in _PADROES_PAGINA_NAO_NOTICIA):
        return True
    m = _PADRAO_SO_NOME_E_TICKER.match(t)
    return bool(m) and len(m.group(1).split()) <= 4


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
    """Primeira palavra do nome COMUM da empresa (sem acento/pontuacao) -
    prioriza config.TICKER_NOME (excecoes cadastradas pro app inteiro, ex:
    'PETR4'->'Petrobras') sobre o longName do yfinance: pra' alguns
    papeis (Petrobras e' o caso confirmado) o longName e' o nome legal
    completo ('Petróleo Brasileiro S.A. - Petrobras'), cuja primeira
    palavra ('Petróleo') nunca aparece no noticiario, que sempre usa o
    nome comum. So cai pro longName quando nao ha excecao cadastrada.

    Usa a MESMA extracao de tokens de _tokenizar (regex [a-z0-9]+, nao
    so' .split() por espaco) - sem isso, um nome com pontuacao colada na
    primeira palavra (ex: longName 'MercadoLibre, Inc.' vindo do yfinance
    pra' BDR de empresa estrangeira - ver MELI34) gerava 'mercadolibre,'
    COM a virgula, que nunca bate com nenhum token de titulo de noticia
    de verdade (a regex do tokenizer separa a virgula) - _relevante()
    sempre retornava False pra esses casos, por mais que a empresa
    estivesse claramente no titulo."""
    nome = config.TICKER_NOME.get(ticker) or nome_empresa or ""
    tokens = _tokenizar(nome)
    return tokens[0] if tokens else ""


def _relevante(ticker: str, nome_empresa: str, titulo: str, aliases: tuple = ()) -> bool:
    """A empresa precisa aparecer pelo nome ou pelo ticker no TITULO (nao
    so em algum lugar da materia) pra contar como noticia dela - senao e'
    so uma mencao de passagem (ex: citada numa lista de altas do dia).

    aliases (config.TICKER_ALIASES): nomes/tickers extras que contam como
    a mesma empresa - existe pra BDR de empresa estrangeira (ex: MELI34),
    onde a cobertura de imprensa nunca usa o nome legal do yfinance nem o
    ticker local, e sim o ticker/nome originais (MELI, MercadoLibre) OU o
    nome em portugues do mercado local (Mercado Livre - 2 palavras, que
    NUNCA bate com o nome_curto de 1 palavra so' derivado do yfinance).
    Cada alias precisa ter TODAS as suas palavras no titulo pra contar
    (nao so' uma palavra solta) - evita alias curto demais virar falso
    positivo."""
    tokens = set(_tokenizar(titulo))
    if ticker.lower() in tokens:
        return True
    primeiro_nome = _nome_curto(ticker, nome_empresa)
    if primeiro_nome and primeiro_nome in tokens:
        return True
    for alias in aliases:
        tokens_alias = set(_tokenizar(alias))
        if tokens_alias and tokens_alias.issubset(tokens):
            return True
    return False


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
    # Google News falha ocasionalmente por timeout/limite temporario.
    # Repetimos apenas erros transitórios; erro permanente ou XML inválido
    # continua sendo reportado como indisponibilidade, sem fabricar notícias.
    for tentativa in range(3):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=(5, 20))
            r.raise_for_status()
            break
        except requests.RequestException as e:
            status = getattr(getattr(e, "response", None), "status_code", 0)
            transitorio = (
                isinstance(e, (requests.Timeout, requests.ConnectionError))
                or status in (429, 500, 502, 503, 504)
            )
            if not transitorio or tentativa == 2:
                return None
            time.sleep(1 + tentativa)
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


def _montar_item(entry, ticker: str, nome_empresa: str, aliases: tuple = ()):
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
        "relevante": _relevante(ticker, nome_empresa, titulo, aliases),
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


@st.cache_data(ttl=_TTL_COLETA, show_spinner="buscando notícias…")
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
    Filtra tambem noticias com mais de _RETENCAO_DIAS dias.

    Busca por MULTIPLOS termos quando o ticker tem aliases cadastrados
    (config.TICKER_ALIASES - BDR de empresa estrangeira, ver MELI34): uma
    busca por termo (nome do yfinance+ticker, e' o padrao de sempre, MAIS
    uma por alias), os resultados sao consolidados (deduplicados por
    link) antes de seguir pro agrupamento/filtro de relevancia normais -
    sem isso, cobertura que so' usa o ticker/nome originais (ex: "MELI"
    ou "Mercado Livre" pra' MELI34) nunca aparecia, porque a busca so'
    tentava o nome legal em ingles do yfinance + o ticker da B3, que quase
    nunca aparecem assim no noticiario de verdade.

    Registro de SAUDE DOS DADOS (achado real, auditoria missao coletores
    2026-10-13, continuacao - BACKLOG.md "NEWS - obter_noticias fora da
    watchlist agregada sem instrumentacao"): obter_noticias_watchlist ja'
    registra "NEWS (watchlist)" agregando TODOS os tickers de uma
    execucao, mas ui/research_tab.py, ui/calendario_tab.py e a visao de
    ticker unico de ui/news_tab.py chamam esta funcao DIRETO, sem passar
    por aquele agregador - se a busca por ticker quebrasse isolada bem no
    momento em que so' esses 3 consumidores estao ativos (watchlist nunca
    chamada na mesma execucao), SAUDE DOS DADOS nao captava a falha.
    Nome separado ("NEWS (ticker unico)", mesmo criterio de
    obter_top_mercado/obter_top_mercado_internacional acima: cada
    registram sua propria fonte mesmo quando tambem sao chamados por um
    agregador que registra a parte - redundancia aceita de proposito, o
    upsert por nome so' reflete a tentativa mais recente)."""
    nome = obter_nome_yf(ticker)
    aliases = tuple(config.TICKER_ALIASES.get(ticker, []))
    termos = [f'"{nome}" {ticker}' if nome else ticker]
    termos += [f'{alias} {ticker}' for alias in aliases]

    entries_por_link = {}
    alguma_busca_respondeu = False
    for termo in termos:
        entries = _buscar_feed(termo)
        if entries is None:
            continue
        alguma_busca_respondeu = True
        for e in entries:
            link = e.get("link") or ""
            if link and link not in entries_por_link:
                entries_por_link[link] = e

    if not alguma_busca_respondeu:
        registrar_tentativa("NEWS (ticker único)", "Google News (busca por ticker)", execucao_ok=False,
                             erro=f"busca falhou para {ticker}", categoria="Noticias")
        return None

    itens = [i for i in (_montar_item(e, ticker, nome, aliases) for e in entries_por_link.values()) if i]
    if not itens:
        registrar_tentativa("NEWS (ticker único)", "Google News (busca por ticker)", execucao_ok=True,
                             registros_novos=0, categoria="Noticias")
        return []

    resultado = []
    for grupo in _agrupar(itens):
        if not grupo["relevante"]:
            continue
        if not _dentro_da_retencao(grupo["data"].isoformat()):
            continue
        veiculos = [f["veiculo"] for f in grupo["fontes"]]
        score, regras = _calcular_score(grupo["titulos"], veiculos)
        data_iso = grupo["data"].isoformat()
        selo = _selo(score)
        # selo CONFIRMADA: existe um Fato Relevante/Comunicado ao Mercado
        # oficial da CVM do MESMO ticker, com assunto parecido (sobreposicao
        # de palavras) e data proxima (ate 2 dias) - ver
        # data/cvm.py:documento_confirmador. Sobrescreve o selo baseado em
        # regras porque uma confirmacao oficial da CVM e' um sinal mais
        # forte que qualquer heuristica de veiculo/linguagem. None (fonte
        # da CVM fora do ar ou sem match) nunca rebaixa o selo - so' promove.
        confirmacao_cvm = documento_confirmador(ticker, grupo["titulo"], data_iso)
        if confirmacao_cvm:
            selo = SELO_CONFIRMADA
            regras = regras + [
                f"confirmado por documento oficial da CVM: {confirmacao_cvm['tipo_label']} "
                f"({confirmacao_cvm['assunto'][:70]})"
            ]
        resultado.append({
            "ticker": ticker,
            "titulo": grupo["titulo"],
            "titulos": grupo["titulos"],
            "veiculos": sorted(set(veiculos)),
            "fontes": grupo["fontes"],
            "fontes_count": len(set(veiculos)),
            "data": data_iso,
            "link": grupo["link"],
            "score": score,
            "selo": selo,
            "regras": regras,
            "cvm_confirmacao": confirmacao_cvm,
            "tickers": sorted({t for titulo in grupo["titulos"] for t in _tickers_no_titulo(titulo)}),
        })

    resultado.sort(key=lambda n: n["data"], reverse=True)
    registrar_tentativa("NEWS (ticker único)", "Google News (busca por ticker)", execucao_ok=True,
                         registros_novos=len(resultado), categoria="Noticias")
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
        try:
            r = obter_noticias(ticker)
            if r is None:
                falhas.append(ticker)
                continue
            todas.extend(r)
        except Exception:
            # Falha isolada: um ticker nao pode impedir as noticias dos demais.
            falhas.append(ticker)
            logging.exception("Falha ao coletar noticias para %s", ticker)
    todas = _mesclar_entre_tickers(todas)
    todas.sort(key=lambda n: n["data"], reverse=True)
    # registro de SAUDE DOS DADOS (achado real, auditoria missao coletores
    # 2026-10-13): antes desta instrumentacao, a linha "NEWS" do painel so'
    # refletia obter_top_mercado_tudo (pool BRASIL+INTERNACIONAL) - se a
    # busca POR TICKER (usada pela aba NOTICIAS de verdade, a que o
    # usuario abre) quebrasse isoladamente (ex: Google muda o formato de
    # 'search?q=' mas mantem a secao de negocios funcionando), o painel
    # continuava mostrando "NEWS: Coleta OK" com a aba principal vazia -
    # exatamente o falso-positivo por omissao de instrumentacao que o
    # projeto proibe. Nome separado ("NEWS (watchlist)") de proposito: e'
    # uma fonte/caminho de codigo diferente de obter_top_mercado_tudo, nao
    # deve compartilhar status com ele. So' registra quando ha pelo menos
    # 1 ticker (watchlist vazia nao e' "falha", e' nada pra buscar).
    if tickers:
        if len(falhas) == len(tickers):
            registrar_tentativa("NEWS (watchlist)", "Google News (busca por ticker)", execucao_ok=False,
                                 erro=f"busca falhou pros {len(tickers)} ticker(s) da watchlist", categoria="Noticias")
        else:
            registrar_tentativa("NEWS (watchlist)", "Google News (busca por ticker)", execucao_ok=True,
                                 parcial=bool(falhas), registros_novos=len(todas), categoria="Noticias")
    return todas, falhas


# --- TOP MERCADO: ranking de importancia ----------------------------------


def _tickers_no_titulo(titulo: str) -> list:
    candidatos = _TICKER_NA_MANCHETE.findall(titulo)
    validos = {c for c in candidatos if re.match(r"[A-Z]{4}(\d+)$", c).group(1) in _SUFIXOS_TICKER_VALIDOS}
    return sorted(validos)


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


@st.cache_data(ttl=_TTL_COLETA, show_spinner="buscando notícias do mercado…")
def obter_top_mercado(setor: str = "TODOS"):
    """As _TOP_MERCADO_QTD noticias mais "importantes" do momento no
    Brasil (ver _calcular_importancia) - secao de negocios do Google News
    Brasil + busca pelos principais temas de mercado. None so se TODAS as
    fontes falharem (nenhuma fonte parcial derruba o ranking - so fica
    com menos material pra rankear). setor != "TODOS": ver
    _coletar_pool_brasil/news_setores.classificar_setores."""
    entries_por_link, alguma_fonte_ok = _coletar_pool_brasil(setor)
    if not alguma_fonte_ok:
        # registro de SAUDE DOS DADOS (bug real corrigido, auditoria
        # missao coletores 2026-10-13, continuacao): so' obter_top_
        # mercado_tudo chamava registrar_tentativa - quando o usuario
        # filtra TOP MERCADO por "BRASIL" (ui/top_mercado_tab.py), esta
        # funcao e' chamada DIRETO, sem passar por obter_top_mercado_
        # tudo. Se o pool BR falhar isolado nesse filtro, a UI avisava
        # certo mas SAUDE DOS DADOS continuava "NEWS: Coleta OK" com
        # base na ultima execucao bem-sucedida de "TUDO" - mesmo
        # mecanismo do bug ja corrigido em obter_noticias_watchlist, so'
        # que neste caminho de codigo (filtro de regiao), nao o de
        # ticker.
        registrar_tentativa("NEWS (Brasil)", "Google News (BR)", execucao_ok=False,
                             erro="pool Brasil falhou", categoria="Noticias")
        return None
    resultado = _processar_pool(entries_por_link, setor, "BR")
    resultado.sort(key=lambda n: n["importancia"], reverse=True)
    resultado = resultado[:_TOP_MERCADO_QTD]
    registrar_tentativa("NEWS (Brasil)", "Google News (BR)", execucao_ok=True,
                         registros_novos=len(resultado), categoria="Noticias")
    return resultado


@st.cache_data(ttl=_TTL_COLETA, show_spinner="buscando notícias internacionais…")
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
        # registro de SAUDE DOS DADOS - mesmo achado/motivo de
        # obter_top_mercado acima, so' que pro filtro "INTERNACIONAL".
        registrar_tentativa("NEWS (Internacional)", "Google News (INTL)", execucao_ok=False,
                             erro="pool Internacional falhou", categoria="Noticias")
        return None
    resultado = _processar_pool(entries_por_link, setor, "INT")
    resultado.sort(key=lambda n: n["importancia"], reverse=True)
    resultado = resultado[:_TOP_MERCADO_QTD]
    registrar_tentativa("NEWS (Internacional)", "Google News (INTL)", execucao_ok=True,
                         registros_novos=len(resultado), categoria="Noticias")
    return resultado


@st.cache_data(ttl=_TTL_COLETA, show_spinner="buscando notícias…")
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
    # Registra cada fonte separadamente mesmo na coleta agregada. Sem isso,
    # uma falha isolada do Brasil ou do pool internacional ficava escondida
    # dentro do status unico NEWS (BR+INTL), dificultando diagnostico.
    registrar_tentativa(
        "NEWS (Brasil)", "Google News (BR)", execucao_ok=br_ok,
        registros_novos=len(br_entries) if br_ok else 0,
        erro=None if br_ok else "pool Brasil falhou", categoria="Noticias",
    )
    registrar_tentativa(
        "NEWS (Internacional)", "Google News (INTL)", execucao_ok=intl_ok,
        registros_novos=len(intl_entries) if intl_ok else 0,
        erro=None if intl_ok else "pool Internacional falhou", categoria="Noticias",
    )
    if not br_ok and not intl_ok:
        # registro de SAUDE DOS DADOS (nao faz parte da logica de news em
        # si - ver data/saude_dados.py/coletores_status.py) - so' numa
        # execucao real (cache miss), nunca bloqueia o retorno
        registrar_tentativa("NEWS", "Google News (BR+INTL)", execucao_ok=False,
                             erro="pool Brasil e Internacional falharam", categoria="Noticias")
        return None

    resultado = []
    if br_ok:
        resultado += _processar_pool(br_entries, setor, "BR")
    if intl_ok:
        resultado += _processar_pool(intl_entries, setor, "INT")

    resultado.sort(key=lambda n: n["importancia"], reverse=True)
    resultado = resultado[:_TOP_MERCADO_QTD]
    registrar_tentativa("NEWS", "Google News (BR+INTL)", execucao_ok=True,
                         parcial=not (br_ok and intl_ok), registros_novos=len(resultado),
                         categoria="Noticias")
    return resultado


# --- Resumo por grupo (sob demanda / automatico p/ watchlist nas ultimas 24h) --
#
# 2026-10-05: migrado do cache em memoria (st.cache_data, por processo)
# pro cache GLOBAL no Supabase (data/ia_cache.py, tabela
# resumos_ia_cache) - exatamente o plano ja' anotado aqui antes: a
# funcao de geracao (_gerar_resumo_grupo) ficou pura (titulo+fontes ->
# resultado), so' embrulhada por obter_resumo_grupo sem mudar quem
# chama (ui/news_tab.py).

# veiculos com paywall conhecido pra materia comum (nao institucional) -
# tentamos essas por ultimo dentro do grupo, ja que costumam falhar
_VEICULOS_PROVAVEL_PAYWALL = {"valor", "estadao", "folha", "bloomberg", "wall street journal", "wsj", "financial times"}

# FASE C (2026-10-09, modal editorial de NEWS): formato antigo era 4 campos
# fixos numa linha cada ("O QUE ACONTECEU: ...") - lia como log de debug e
# sempre sobrava campo vazio ("NÚMEROS: não informado") quando a fonte não
# dava pra preencher os 4. Formato novo tem 2 blocos com marcador próprio
# (RESUMO:/LEITURA DE MERCADO:, ver _separar_secoes_resumo) - RESUMO é
# prosa editorial em paragrafos curtos (proporcional ao conteudo real, nunca
# infla pra preencher), LEITURA DE MERCADO e' OMITIDA pelo proprio modelo
# quando nao ha' base (nunca "não informado") em vez de um campo vazio pra
# UI filtrar depois. Budget de tokens maior que o formato antigo (paragrafos
# por extenso gastam mais que 1 linha por campo) - ainda proprio do NEWS,
# maior que config.GROQ_MAX_TOKENS (compartilhado com o research, que usa
# um formato mais enxuto).
_MAX_TOKENS_RESUMO_NEWS = 900

# marcadores do formato novo - usados tanto no prompt quanto no parser
# (_separar_secoes_resumo) - precisam casar exatamente
_MARCADOR_RESUMO = "RESUMO:"
_MARCADOR_LEITURA = "LEITURA DE MERCADO:"

# regras de fidelidade (nunca invente numero/citacao/causalidade/
# recomendacao/previsao que a fonte nao afirme) sao as MESMAS do formato
# antigo (2026-10-08, auditoria pos-FASE 4) - so' a FORMA de apresentar
# mudou (paragrafos corridos em vez de campos rotulados); o reforco
# explicito sobre IMPACTO/PRÓXIMOS PASSOS (so' reacao/evento que a fonte
# relatou como JA' acontecido, nunca previsao) continua, agora embutido nas
# regras do bloco RESUMO em vez de serem campos proprios.
#
# v3 (2026-10-15, reformulacao editorial completa - ver _resumo_e_generico
# e _VERSAO_CHAVE_NEWS): o formato RESUMO/LEITURA DE MERCADO continua
# (fica o parser de _separar_secoes_resumo intacto), mas o conteudo
# esperado DENTRO do bloco RESUMO agora segue 4 angulos de prioridade
# (o que aconteceu/contexto/impacto potencial/o que acompanhar) SEM forcar
# os 4 pra toda materia - uma nota curta so' precisa do primeiro. Lista
# explicita de frases proibidas (achado real: o modelo recorria a
# generalidades tipo "o mercado segue atento" quando o texto fonte era
# curto, em vez de admitir honestamente que a materia tinha pouca
# informacao) - complementada pelo gate automatico _resumo_e_generico, que
# descarta e tenta outra fonte/fallback se o modelo nao seguir a regra.
_ANGULOS_PRIORIDADE_RESUMO = (
    "1) O QUE ACONTECEU - fato concreto, números, empresas e decisões "
    "citados pela fonte.\n"
    "2) CONTEXTO - o que levou ao acontecimento e o que já era conhecido "
    "antes, SE a fonte der essa informação.\n"
    "3) IMPACTO POTENCIAL - implicações pra receita/margem/lucro/dívida/"
    "fluxo de caixa/valuation/mercado, SE a fonte discutir isso (direto "
    "ou com base em dados que ela mesma cita).\n"
    "4) O QUE ACOMPANHAR - próximos resultados/indicadores/decisões/riscos "
    "relevantes, SE a fonte citar algo concreto (data, evento, prazo)."
)

_FRASES_PROIBIDAS_RESUMO = (
    "\"o mercado segue atento\", \"é importante acompanhar os próximos "
    "movimentos\", \"o cenário pode impactar investidores\", \"resta saber "
    "como o mercado vai reagir\", \"vale a pena acompanhar de perto\", "
    "\"os investidores devem ficar de olho\" e qualquer outra frase que "
    "poderia ser colada em QUALQUER notícia de mercado sem mudar nada"
)

_PROMPT_SISTEMA_RESUMO = (
    "Você é um editor financeiro que escreve, em português brasileiro "
    "natural, preciso e profissional, um resumo editorial de uma matéria "
    "do mercado financeiro pra um terminal de investimentos - sempre com "
    "suas próprias palavras, nunca copie frases literais nem reproduza "
    "parágrafos inteiros do texto original, e NUNCA repita a manchete só "
    "com outras palavras (o leitor já viu a manchete; o resumo precisa "
    "agregar informação nova). O texto fornecido foi extraído "
    "automaticamente de uma página web e pode conter trechos de menu, "
    "anúncio ou navegação misturados - ignore esse ruído e resuma só o "
    "conteúdo jornalístico.\n\n"
    "Formato de saída, EXATAMENTE nesta estrutura (sem nenhum outro texto "
    "antes ou depois):\n\n"
    f"{_MARCADOR_RESUMO}\n"
    "<1 a 5 parágrafos curtos, cada um separado por uma linha em branco>\n\n"
    f"{_MARCADOR_LEITURA}\n"
    "<parágrafo curto, só se houver base - ver regra abaixo>\n\n"
    f"REGRAS DO BLOCO {_MARCADOR_RESUMO}\n"
    "- Priorize, NESTA ORDEM e só quando a fonte sustentar cada um (nunca "
    f"force os 4 pra toda matéria):\n{_ANGULOS_PRIORIDADE_RESUMO}\n"
    "- Uma reação de mercado (preço, volume, etc.) só entra quando a "
    "PRÓPRIA FONTE relata como já tendo acontecido (ex: 'as ações caíram "
    "3% após o anúncio') - nunca sua previsão do que pode/deve acontecer.\n"
    "- Um evento futuro só entra se tiver data ou ação EXPLÍCITA na fonte "
    "(ex: 'resultado sai dia 12') - nunca uma recomendação genérica.\n"
    "- Diferencie sempre fato confirmado de interpretação analítica - "
    "nunca apresente uma hipótese/opinião do texto como se fosse um fato "
    "confirmado.\n"
    "- NUNCA afirme que a notícia é positiva ou negativa pra uma ação sem "
    "explicar a lógica e as condições dessa leitura (ex: não basta dizer "
    "'é positivo pro papel' - diga o quê, concretamente, torna isso "
    "positivo, segundo a própria fonte).\n"
    "- O TAMANHO é proporcional à quantidade de informação no texto: texto "
    "curto (nota rápida, 1-2 parágrafos de fonte) gera resumo de 1 "
    "parágrafo curto só - NUNCA infle com conteúdo inventado ou com "
    "generalidades pra preencher mais parágrafos. Se a matéria não "
    "oferecer informação suficiente, escreva um resumo curto e honesto "
    "reconhecendo a limitação (ex: o que SE sabe, por pouco que seja) em "
    "vez de preencher espaço com frases vagas. Nunca invente números, "
    "datas, citações, causalidade, consenso de analistas, preço-alvo ou "
    "fatos que não estejam no texto fornecido.\n"
    "- Nunca apresente uma causa->consequência entre dois fatos que a "
    "fonte não conectou explicitamente, nunca atribua uma expectativa/"
    "consenso de mercado que a fonte não cite.\n"
    "- O Título informado já é um fato estabelecido (ex: direção do "
    "pregão - alta/queda - e percentual, quando o título trouxer isso): "
    "seu resumo NUNCA pode contradizer essa direção/percentual. Se o "
    "texto extraído parecer divergir do título, isso é sinal de que o "
    "texto é sobre OUTRO fato/dia/ativo - nesse caso, responda "
    "exatamente SEM_CONTEUDO em vez de inventar uma reconciliação.\n"
    f"- NUNCA use frases genéricas de preenchimento, como {_FRASES_PROIBIDAS_RESUMO}.\n\n"
    f"REGRAS DO BLOCO {_MARCADOR_LEITURA}\n"
    "- Só escreva este bloco se houver base real no texto pra discutir "
    "relevância pro investidor: por que a notícia pode importar, quais "
    "ativos/setores/variáveis macro podem ser afetados, e o que ainda "
    "falta saber.\n"
    "- Deixe claro quando for SUA interpretação analítica (use linguagem "
    "como 'pode sinalizar', 'tende a', 'a depender de') - nunca apresente "
    "uma inferência sua como se fosse um fato que a fonte confirmou.\n"
    "- Se não houver base suficiente pra essa leitura, OMITA O BLOCO "
    f"INTEIRO (não escreva {_MARCADOR_LEITURA} nem 'não informado' nem "
    "nada parecido).\n\n"
    "Se não houver conteúdo jornalístico aproveitável nenhum, responda "
    "exatamente: SEM_CONTEUDO"
)

_PROMPT_SISTEMA_RESUMO_MANCHETES = (
    "Você é um editor financeiro que escreve, em português brasileiro "
    "natural e profissional, um resumo editorial de um fato do mercado "
    "financeiro a partir SÓ das manchetes de várias fontes sobre o mesmo "
    "fato - não teve acesso ao texto completo de nenhuma matéria (todas "
    "bloquearam o download). SEMPRE com suas próprias palavras, e NUNCA "
    "apenas reescreva a manchete principal com outras palavras.\n\n"
    "Formato de saída, EXATAMENTE nesta estrutura (sem nenhum outro texto "
    "antes ou depois):\n\n"
    f"{_MARCADOR_RESUMO}\n"
    "<1 a 3 parágrafos curtos, separados por linha em branco>\n\n"
    f"{_MARCADOR_LEITURA}\n"
    "<parágrafo curto, só se houver base clara nas manchetes>\n\n"
    "Como só tem as manchetes (não o texto completo), vá direto ao que "
    "elas revelam (o que aconteceu, e contexto/impacto SE alguma manchete "
    "der essa informação) - nunca invente número, data ou fato que não "
    "esteja nelas. O Título informado é um fato estabelecido (direção do "
    "pregão e percentual, quando trouxer isso) - seu resumo NUNCA pode "
    "contradizer essa direção/percentual; se as manchetes parecerem "
    "divergir dele, prefira SEM_CONTEUDO a inventar uma reconciliação. "
    "Uma reação de mercado só conta se alguma manchete "
    "relatar como já acontecida (nunca sua previsão); um próximo passo só "
    "conta se alguma manchete citar um evento futuro explícito. Nunca "
    "conecte duas manchetes com uma relação de causa->consequência que "
    "nenhuma delas afirma, e nunca afirme que o fato é positivo/negativo "
    "pra uma ação sem que alguma manchete sustente essa leitura. Se a "
    f"informação for pouca, prefira um resumo curto e honesto. NUNCA use "
    f"frases genéricas de preenchimento, como {_FRASES_PROIBIDAS_RESUMO}. "
    f"Se não houver base pro bloco {_MARCADOR_LEITURA}, OMITA O BLOCO "
    f"INTEIRO (não escreva {_MARCADOR_LEITURA} nem 'não informado'). "
    "Se as manchetes não derem pra montar nem o RESUMO, responda "
    "exatamente: SEM_CONTEUDO"
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
    veiculo. None se nao conseguir (formato mudou, timeout, decoder
    indisponivel etc).

    Nem todo item do feed passa por aqui vindo do Google News: o pool
    internacional (MarketWatch/CNBC/etc) tambem le RSS proprio de cada
    veiculo, cujo link ja e' a URL real - gnewsdecoder so entende o
    formato de redirect do Google e devolve falha pra qualquer outra
    URL (bug real: media alta de "link nao resolvido" nessas fontes,
    quando na verdade nunca precisava resolver nada)."""
    if not link_google_news:
        return None
    try:
        host = urlparse(link_google_news).netloc.lower()
    except Exception:
        host = ""
    if host and "news.google.com" not in host:
        return link_google_news
    if gnewsdecoder is None:
        return None
    try:
        resultado = gnewsdecoder(link_google_news, interval=1)
    except Exception:
        return None
    if not resultado or not resultado.get("success"):
        return None
    return resultado.get("decoded_url") or None


# limiar bem mais baixo que o antigo (200 chars): materia curta de
# verdade (ex: nota rapida de mercado) costuma ter 1-2 paragrafos reais
# com bem menos que 200 chars e ainda assim da' pra resumir em 2-3 linhas
# proporcionais - o limiar antigo tratava isso como "curto demais" e
# jogava fora um conteudo perfeitamente aproveitavel
_MIN_CHARS_TEXTO = 60
# abaixo disso nem sozinho nem combinado com outro fragmento pequeno vale
# a pena tentar - normalmente e' so' o "menu"/rodape sobrando do
# trafilatura numa pagina que bloqueou o conteudo de verdade
_MIN_CHARS_FRAGMENTO = 15


def _url_imagem_valida(url) -> str | None:
    """So aceita URL absoluta http(s) - nunca inventa/completa uma
    imagem a partir de caminho relativo ou data: URI (risco real de
    imagem quebrada ou irrelevante)."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    return url if url.startswith("http://") or url.startswith("https://") else None


# --- Imagens: descartar logo/favicon/placeholder ANTES de aceitar --------
# achado real (auditoria 2026-10-15): og:image de muitos publishers
# brasileiros aponta pro logo do veiculo (nao pra capa da materia) quando
# a pagina nao tem foto editorial propria - o filtro antigo so checava
# "e' uma URL http(s) valida", entao qualquer logo passava como se fosse
# a foto da noticia. Os padroes abaixo sao heuristica por NOME DE ARQUIVO
# (sem rede extra - o mesmo motivo de so' usar o download ja' feito pro
# texto, ver _extrair_texto_artigo) - cobre os casos mais comuns
# (logo.png, favicon.ico, og-default.jpg, placeholder-foto.svg etc), nao
# e' exaustivo por natureza (nao da pra detectar logo "generico" so pelo
# nome do arquivo em 100% dos casos).
#   achado real (auditoria 2026-10-18, bug "card da Vale mostra imagem
#   ilustrativa que não é a foto da matéria"): rastreando o cache de
#   produção, alguns publishers (ex: spacemoney.com.br, infomoney.com.br
#   nalguns posts) fazem upload de uma foto de BANCO DE IMAGENS (Pexels/
#   Unsplash) pro PRÓPRIO domínio deles e publicam ela como og:image -
#   passa em todos os filtros acima (URL http(s) válida, não é logo/
#   favicon, dimensão declarada grande o bastante) porque TECNICAMENTE é
#   uma imagem real hospedada pelo veículo, só que é uma foto GENÉRICA
#   de banco (ex: silo de grãos aleatório numa matéria sobre níquel no
#   Canadá), nunca a foto real do fato noticiado - o nome do arquivo
#   geralmente preserva o padrão de ID do banco de imagens de origem
#   mesmo depois do re-upload (ex: "pexels-photo-34021878.webp",
#   "...-unsplash_red.jpg"), o que permite o mesmo filtro por NOME já
#   usado acima pra logo/favicon/placeholder.
_PADROES_IMAGEM_GENERICA = (
    "logo", "favicon", "icon-", "-icon", "sprite", "placeholder",
    "default-image", "default_image", "og-default", "og_default",
    "share-image-default", "social-default", "avatar-padrao", "sem-foto",
    "noimage", "no-image", "apple-touch-icon",
    # achado real (auditoria 2026-10-18): avatar de autor/widget com nome
    # tipo "img-default-projeto-...-96x96.png" - "default"/"avatar" sozinhos
    # (sem precisar do prefixo "img-"/sufixo "-padrao" que os padroes acima
    # já exigiam) cobrem essa variação sem exigir dimensão declarada.
    "default", "avatar",
    # banco de imagens (ver achado real acima) - nomes de arquivo que
    # preservam o padrao do banco de origem mesmo apos re-upload pro
    # dominio do veiculo
    "pexels", "unsplash", "shutterstock", "istockphoto", "istock-",
    "gettyimages", "getty-images", "depositphotos", "123rf", "vecteezy",
    "pixabay", "dreamstime", "adobestock", "stock-photo", "stockphoto",
    "banco-de-imagens", "freepik",
)


def _imagem_parece_generica(url: str) -> bool:
    """True se o CAMINHO da URL (sem acento/minusculo) bater com um
    padrao conhecido de logo/favicon/placeholder - nunca mexe na query
    string (irrelevante pro nome do arquivo em si)."""
    caminho = _sem_acento(urlparse(url).path)
    return any(p in caminho for p in _PADROES_IMAGEM_GENERICA)


# dimensao minima aceita quando a PROPRIA pagina declara og:image:width/
# height (SVG de logo/ícone de compartilhamento social costuma vir bem
# pequeno, ex: 96x96 ou 120x120 - foto editorial de verdade quase sempre
# passa de 300px de largura). So' usado quando o meta existe: ausencia de
# largura/altura declarada NAO rejeita a imagem (muitos publishers nao
# declaram, seria descartar foto valida por falta de metadado opcional).
_LARGURA_MINIMA_IMAGEM_EDITORIAL = 200


def _extrair_dimensao_declarada(sopa, seletor_largura: str, seletor_altura: str) -> tuple:
    def _valor(seletor):
        meta = sopa.select_one(seletor)
        bruto = meta.get("content") if meta else None
        try:
            return int(str(bruto).strip())
        except (TypeError, ValueError):
            return None
    return _valor(seletor_largura), _valor(seletor_altura)


# --- Imagens: confirmar via rede (so' quando validar_imagem=True) --------
# NUNCA chamado no caminho padrao de _extrair_texto_artigo/
# _gerar_resumo_grupo (violaria a regra "zero requisicao de rede extra so
# pra imagem", ver docstring de _gerar_resumo_grupo) - so' usado pelo
# PRE-PROCESSAMENTO em lote (pregerar_resumos_news), que ja' tem
# orcamento proprio de tempo/rede reservado pra isso (ver seção 5 do
# pedido: "testar se a URL realmente retorna uma imagem utilizável").
#
# bug real encontrado nesta auditoria (2026-10-17, investigacao do card
# sem foto em produção): esta funcao usava _HEADERS (UA educado e
# autoidentificado, "PregaoApp/0.1 (uso pessoal...)") - apropriado pro
# RSS do Google News (que espera um bot se identificar), mas varios CDNs
# de imagem de veiculo BR (ex: glbimg, imguol) tratam qualquer UA que
# nao pareca navegador real como bot de scraping e bloqueiam (403/406)
# ou devolvem um Content-Type generico, fazendo o GATE desta funcao
# descartar (imagem=None) uma og:image perfeitamente valida so' por
# causa do UA da PROPRIA validacao - nunca da imagem em si. O download
# do ARTIGO (_extrair_texto_artigo, alguns paragrafos acima) ja usa um
# UA de navegador real exatamente por esse motivo e funciona contra os
# mesmos hosts; replica aqui o mesmo UA, so' pra esta chamada (nao
# reaproveita _HEADERS global, que outros fetches - RSS - continuam
# usando sem mudanca).
_HEADERS_IMAGEM = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}


def _url_imagem_utilizavel(url: str) -> bool:
    """HEAD curto (GET como fallback, pra servidor que nao suporta HEAD)
    confirmando que a URL responde com Content-Type de imagem de verdade
    e um tamanho minimo (descarta pixel de rastreio/ícone disfarçado de
    foto) - nunca baixa o corpo inteiro (so' cabecalhos, ou um stream que
    fecha logo apos ler o cabecalho). Qualquer falha (timeout, erro HTTP,
    tipo errado) -> False, nunca lança exceção pra quem chama."""
    if not url or not isinstance(url, str):
        return False
    try:
        r = requests.head(url, headers=_HEADERS_IMAGEM, timeout=(3, 5), allow_redirects=True)
        if r.status_code >= 400 or r.status_code == 405 or not r.headers.get("Content-Type"):
            r = requests.get(url, headers=_HEADERS_IMAGEM, timeout=(3, 5), stream=True)
        if r.status_code >= 400:
            return False
        tipo = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if not tipo.startswith("image/"):
            return False
        tamanho = r.headers.get("Content-Length")
        if tamanho is not None:
            try:
                if int(tamanho) < 1024:  # provavel icone/pixel de rastreio, nao foto editorial
                    return False
            except ValueError:
                pass
        return True
    except requests.RequestException:
        return False
    except Exception:
        return False


def _extrair_texto_artigo(link_google_news: str) -> tuple:
    """Resolve o link do Google News e tenta extrair o artigo por HTTP
    explícito antes do extrator. Alguns hosts respondem diferente ao
    User-Agent padrão do Trafilatura; usamos cabeçalhos de navegador
    comuns, timeout curto e seguimos redirects HTTP normais. Não tenta
    contornar paywall/login/captcha. Retorna (texto, imagem, link_real,
    motivo_falha); nunca inventa conteúdo."""
    link_real = _resolver_link_real(link_google_news)
    if not link_real:
        return None, None, None, "não foi possível resolver o link original do Google News"

    baixado = None
    motivo_download = None
    try:
        with requests.get(
            link_real,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            timeout=(4, 12),
            allow_redirects=True,
        ) as response:
            response.raise_for_status()
            tipo = (response.headers.get("Content-Type") or "").lower()
            if "html" not in tipo and "xhtml" not in tipo:
                motivo_download = f"o endereço respondeu conteúdo não HTML ({tipo or 'tipo desconhecido'})"
            else:
                baixado = response.text
                link_real = response.url or link_real
    except requests.RequestException as exc:
        motivo_download = f"falha HTTP ao acessar a matéria ({type(exc).__name__})"
    except Exception as exc:
        motivo_download = f"falha ao baixar a matéria ({type(exc).__name__})"

    # Segundo método de download como fallback, sem burlar controles do site.
    if not baixado:
        try:
            baixado = trafilatura.fetch_url(link_real)
        except Exception:
            baixado = None
    if not baixado:
        return None, None, link_real, motivo_download or "o site não disponibilizou a página"

    # Parsear os metadados com HTML parser (regex falha quando a ordem
    # dos atributos muda ou há espaços/aspas diferentes).
    sopa = BeautifulSoup(baixado, "html.parser")
    imagem = None

    def _candidata_imagem(url_bruta):
        """URL absoluta + descarta logo/favicon/placeholder por padrao de
        nome (ver _imagem_parece_generica) - usado pelos 3 blocos de
        extração abaixo (meta tags, JSON-LD, itemprop)."""
        if not url_bruta:
            return None
        from urllib.parse import urljoin
        candidata_abs = urljoin(link_real, url_bruta.strip())
        validada = _url_imagem_valida(candidata_abs)
        if not validada or _imagem_parece_generica(validada):
            return None
        return validada

    for seletor, atributo in (
        ('meta[property="og:image"]', "content"),
        ('meta[property="og:image:secure_url"]', "content"),
        ('meta[name="twitter:image"]', "content"),
        ('meta[name="twitter:image:src"]', "content"),
        ('link[rel="image_src"]', "href"),
    ):
        meta = sopa.select_one(seletor)
        candidata = meta.get(atributo) if meta else None
        imagem = _candidata_imagem(candidata)
        if imagem:
            break

    # og:image:width (quando a PROPRIA pagina declara) descarta miniatura/
    # icone de compartilhamento social disfarçado de capa (ex: 120x120) -
    # ausencia do meta NUNCA rejeita a imagem (so' filtra quando a pagina
    # de fato declarou uma dimensao pequena demais pra ser foto editorial).
    if imagem:
        largura, _altura = _extrair_dimensao_declarada(
            sopa, 'meta[property="og:image:width"]', 'meta[property="og:image:height"]'
        )
        if largura is not None and largura < _LARGURA_MINIMA_IMAGEM_EDITORIAL:
            imagem = None

    # Alguns publishers publicam a imagem principal apenas em JSON-LD.
    # Percorre metadados estruturados públicos sem executar scripts.
    #
    # achado real (auditoria 2026-10-18, bug "card da Vale mostra imagem
    # ilustrativa que não é a foto da matéria"): a chave "url" NUNCA pode
    # entrar nessa lista de chaves candidatas a imagem - "url" é uma
    # propriedade genérica do schema.org presente em QUASE TODO node do
    # @graph (WebPage, Organization, Person, BreadcrumbList...), sempre
    # apontando pro link PRÓPRIO daquele node, nunca necessariamente uma
    # imagem. Confirmado em produção: um publisher real (spacemoney.com.br)
    # usa o padrão @graph do Yoast SEO, cujo node "WebPage" tem
    # "url": "<URL da PRÓPRIA matéria>" - sem esse filtro, isso é aceito
    # como se fosse a foto da notícia (passa em todo o resto da validação:
    # é http(s) válido, não bate nenhum padrão de nome genérico), fazendo
    # `imagem` virar a MESMA URL do artigo, nunca uma imagem de verdade.
    # "contentUrl" e "primaryImageOfPage" continuam aqui porque são
    # propriedades específicas de ImageObject (contentUrl) ou que só
    # existem quando a página de fato declara uma imagem principal
    # (primaryImageOfPage) - não têm essa ambiguidade genérica do "url".
    #
    # "logo"/"publisher"/"author" NUNCA entram na varredura "pega
    # qualquer imagem aninhada em qualquer outra chave" (2º loop abaixo):
    # achado real (mesma auditoria) - o node "Organization" do mesmo
    # @graph do spacemoney.com.br tem um "logo" inline (ImageObject com
    # "contentUrl" de verdade) com a logomarca do VEÍCULO ("caption":
    # "SpaceMoney"), não da matéria - sem excluir essas 3 chaves, a
    # varredura catch-all recursava pra dentro do logo e aceitava a
    # marca do site como se fosse a foto da notícia. "logo" é sempre
    # identidade de marca (Organization/WebSite), "publisher"/"author"
    # são sempre entidade (empresa/pessoa) ligada à matéria, nunca o
    # conteúdo visual da matéria em si.
    if not imagem:
        _CHAVES_IMAGEM_JSONLD = ("image", "thumbnailUrl", "contentUrl", "primaryImageOfPage")
        _CHAVES_NUNCA_IMAGEM_JSONLD = ("logo", "publisher", "author")

        def _urls_imagem_jsonld(obj):
            achados = []
            if isinstance(obj, str):
                return achados
            if isinstance(obj, list):
                for item in obj:
                    achados.extend(_urls_imagem_jsonld(item))
                return achados
            if isinstance(obj, dict):
                for chave in _CHAVES_IMAGEM_JSONLD:
                    valor = obj.get(chave)
                    if isinstance(valor, str):
                        achados.append(valor)
                    elif isinstance(valor, (dict, list)):
                        achados.extend(_urls_imagem_jsonld(valor))
                for chave, valor in obj.items():
                    if chave in _CHAVES_IMAGEM_JSONLD or chave in _CHAVES_NUNCA_IMAGEM_JSONLD:
                        continue
                    if isinstance(valor, (dict, list)):
                        achados.extend(_urls_imagem_jsonld(valor))
            return achados

        for script_ld in sopa.select('script[type="application/ld+json"]'):
            try:
                estrutura = json.loads(script_ld.string or script_ld.get_text())
            except (ValueError, TypeError):
                continue
            for candidata in _urls_imagem_jsonld(estrutura):
                imagem = _candidata_imagem(candidata)
                if imagem:
                    break
            if imagem:
                break
        if not imagem:
            meta_itemprop = sopa.select_one('[itemprop="image"][content], [itemprop="image"][src]')
            candidata = (meta_itemprop.get("content") or meta_itemprop.get("src")) if meta_itemprop else None
            imagem = _candidata_imagem(candidata)

    texto = None
    try:
        bruto = trafilatura.extract(
            baixado,
            include_comments=False,
            include_tables=False,
            with_metadata=True,
            output_format="json",
            favor_precision=True,
        )
        dados = json.loads(bruto) if bruto else {}
        texto = (dados.get("text") or "").strip() or None
        if not imagem:
            candidata_trafilatura = _url_imagem_valida(dados.get("image"))
            if candidata_trafilatura and not _imagem_parece_generica(candidata_trafilatura):
                imagem = candidata_trafilatura
    except Exception:
        pass

    # Ultimo fallback: imagem lazy-loaded dentro do bloco de artigo
    # principal (achado real, auditoria 2026-10-17 - rastreando o bug
    # "fotos nao aparecem" ponta a ponta contra cache de producao:
    # guiadoinvestidor.com.br e sites no mesmo molde nao declaram
    # og:image/twitter:image nem JSON-LD NENHUM - a <img> real so existe
    # com src=data:image/svg (placeholder de lazy-load) + a URL de
    # verdade num atributo data-lazy-src/data-src, que os blocos acima
    # (meta tags, JSON-LD, itemprop, trafilatura) nunca olham.
    # So considera a PRIMEIRA <img> dentro do bloco principal que NAO
    # esteja dentro de um <article> aninhado (achado real confirmado
    # nesta auditoria: a mesma pagina embute os "relacionados" como
    # <article> aninhado DENTRO do <article> principal - sem essa
    # exclusao, uma materia SEM foto propria as vezes "roubaria" a foto
    # de outra materia do bloco de relacionados) NEM tenha dimensao
    # declarada pequena demais (achado real, auditoria 2026-10-18: um
    # avatar de autor 40x40 - "width"/"height" no proprio <img>, nome de
    # arquivo "img-default-projeto...") apareceu ANTES de qualquer foto
    # de verdade dentro do bloco principal - mesmo limiar/mesma logica
    # ja usada acima pro og:image:width, so que lendo o atributo da
    # PROPRIA tag em vez de um <meta>.
    if not imagem:
        for seletor in ("article", "main", '[itemprop="articleBody"]'):
            bloco_principal = sopa.select_one(seletor)
            if not bloco_principal:
                continue
            for img_tag in bloco_principal.find_all("img"):
                dentro_de_aninhado = False
                pai = img_tag.parent
                while pai is not None and pai is not bloco_principal:
                    if getattr(pai, "name", None) == "article":
                        dentro_de_aninhado = True
                        break
                    pai = pai.parent
                if dentro_de_aninhado:
                    continue
                try:
                    largura_tag = int(str(img_tag.get("width")).strip())
                except (TypeError, ValueError):
                    largura_tag = None
                if largura_tag is not None and largura_tag < _LARGURA_MINIMA_IMAGEM_EDITORIAL:
                    continue
                candidata_bruta = (
                    img_tag.get("data-lazy-src") or img_tag.get("data-src")
                    or img_tag.get("data-original") or img_tag.get("src")
                )
                imagem = _candidata_imagem(candidata_bruta)
                if imagem:
                    break
            if imagem:
                break

    # Segundo extrator menos restritivo: usa parágrafos de article/main,
    # remove navegação/rodapé e só aceita texto com tamanho mínimo. Não
    # contorna paywall nem tenta executar JavaScript.
    if not texto or len(texto) < _MIN_CHARS_FRAGMENTO:
        for seletor in ("article", "main", '[itemprop="articleBody"]'):
            bloco = sopa.select_one(seletor)
            if not bloco:
                continue
            for ruido in bloco.select("script,style,nav,footer,header,aside,form,button"):
                ruido.decompose()
            paragrafos = [
                p.get_text(" ", strip=True)
                for p in bloco.select("p")
                if len(p.get_text(" ", strip=True)) >= 35
            ]
            candidato = "\\n\\n".join(paragrafos).strip()
            if len(candidato) > len(texto or ""):
                texto = candidato
            if texto and len(texto) >= _MIN_CHARS_TEXTO:
                break

    # Não promover meta-description a corpo da matéria: ela é apenas um
    # resumo curto do publisher e deve continuar identificada como trecho,
    # nunca como leitura integral.
    if not texto or len(texto) < _MIN_CHARS_FRAGMENTO:
        return (
            None, imagem, link_real,
            "página acessível, mas sem texto extraível (possível paywall, consentimento, JavaScript ou bloqueio)",
        )
    return texto, imagem, link_real, None


def _chamar_groq(prompt_sistema: str, prompt_usuario: str) -> tuple:
    """Chamada generica ao Groq (free tier, mesma API usada no research -
    ver data/research/resumir.py, mas com prompts proprios do NEWS).
    Chave/modelo vem de config.obter_credenciais_groq() (lugar unico,
    compartilhado com research). Retorna (resumo, motivo_falha);
    motivo_falha='cota' em 429."""
    chave, modelo = config.obter_credenciais_groq()
    if not chave:
        return None, "GROQ_API_KEY não configurada em st.secrets"

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
            json={
                "model": modelo,
                "messages": [
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_usuario},
                ],
                "temperature": 0.3,
                "max_tokens": _MAX_TOKENS_RESUMO_NEWS,
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


def _resumir_com_groq(texto: str, titulo: str) -> tuple:
    """Resume o TEXTO COMPLETO extraído de uma matéria (formato editorial
    RESUMO/LEITURA DE MERCADO, ver _PROMPT_SISTEMA_RESUMO)."""
    texto_truncado = texto[:6000]
    prompt_usuario = f"Título: {titulo}\n\nTexto extraído da página:\n{texto_truncado}"
    return _chamar_groq(_PROMPT_SISTEMA_RESUMO, prompt_usuario)


_PADROES_LEITURA_SEM_BASE = (
    "nao informado", "nao ha base", "sem base suficiente", "informacao insuficiente",
    "nao e possivel", "nao foi possivel", "n/a", "nao aplicavel",
)


def _leitura_sem_base(texto: str) -> bool:
    """True se o texto da LEITURA DE MERCADO for, na prática, um campo
    vazio (o modelo não seguiu a instrução de OMITIR o bloco inteiro e
    escreveu algo tipo 'não informado') OU curto demais pra ser um
    parágrafo real - nesses casos a seção inteira é descartada, nunca
    mostrada como um rótulo vazio pra UI (ver separar_secoes_resumo)."""
    t = _sem_acento(texto).strip(" .-")
    if len(t) < 15:
        return True
    return any(p in t for p in _PADROES_LEITURA_SEM_BASE) and len(t) < 160


# regex ANCORADA no inicio de linha (^, com re.MULTILINE) - um .find() por
# substring (tentativa original) tratava QUALQUER ocorrencia do texto
# "RESUMO:"/"LEITURA DE MERCADO:" como marcador de secao, mesmo dentro de
# uma frase comum (ex: um paragrafo que cite "leitura de mercado:" dentro
# de uma citacao) - bug real pego pelo proprio teste da secao 4 (ver
# tests/test_news_fase3.py, cenarios 4e/4l) com um texto de exemplo que so'
# MENCIONA a palavra "resumo" no meio da frase.
_RE_MARCADOR_RESUMO = re.compile(r"(?m)^[ \t]*" + re.escape(_MARCADOR_RESUMO))
_RE_MARCADOR_LEITURA = re.compile(r"(?m)^[ \t]*" + re.escape(_MARCADOR_LEITURA))


def separar_secoes_resumo(resumo: str) -> tuple:
    """Quebra o texto bruto do resumo (formato RESUMO:/LEITURA DE MERCADO:,
    ver _PROMPT_SISTEMA_RESUMO) em (paragrafos_corpo: list[str],
    leitura_mercado: str|None) - usado pela UI pra renderizar o modal
    editorial (ver ui/news_tab.py:_abrir_card). Os marcadores so' contam
    quando abrem uma LINHA (ver _RE_MARCADOR_*) - nunca quando a palavra
    aparece no meio de uma frase comum do proprio resumo. Tolerante a
    formato inesperado (o modelo nem sempre segue a estrutura à risca):
    sem os marcadores, devolve o texto inteiro quebrado em parágrafos e
    leitura_mercado=None - nunca lança excecao, nunca inventa conteúdo.
    leitura_mercado vem None tanto quando o marcador não aparece quanto
    quando aparece mas o conteúdo é, na prática, um campo vazio (ver
    _leitura_sem_base) - a UI nunca precisa saber a diferença."""
    texto = (resumo or "").strip()
    if not texto:
        return [], None

    corpo = texto
    leitura = None
    match_leitura = _RE_MARCADOR_LEITURA.search(texto)
    if match_leitura:
        corpo = texto[: match_leitura.start()]
        bruto_leitura = texto[match_leitura.end():].strip()
        if bruto_leitura and not _leitura_sem_base(bruto_leitura):
            leitura = bruto_leitura

    match_resumo = _RE_MARCADOR_RESUMO.search(corpo)
    if match_resumo:
        corpo = corpo[match_resumo.end():]

    paragrafos = [p.strip() for p in re.split(r"\n\s*\n", corpo) if p.strip()]
    return paragrafos, leitura


# --- Gate de qualidade: rejeitar resumo generico (v3, 2026-10-15) -------
# o prompt (_PROMPT_SISTEMA_RESUMO/_MANCHETES) já pede pra NUNCA usar
# frases de preenchimento nem parafrasear a manchete - isto aqui é a rede
# de segurança automática pros casos em que o modelo não obedece (achado
# real: Groq free tier ocasionalmente ignora regra de prompt sob texto-
# fonte pobre). Resumo reprovado NUNCA é cacheado nem devolvido como
# sucesso - _gerar_resumo_grupo trata como falha dessa fonte/caminho e
# segue pro próximo fallback, exatamente como uma falha de extração.
_FRASES_GENERICAS_PROIBIDAS = (
    "o mercado segue atento", "mercado segue atento",
    "e importante acompanhar os proximos movimentos",
    "importante acompanhar os proximos movimentos",
    "o cenario pode impactar investidores", "cenario pode impactar investidores",
    "resta saber como o mercado vai reagir",
    "vale a pena acompanhar de perto",
    "os investidores devem ficar de olho", "investidores devem ficar de olho",
    "e preciso acompanhar os desdobramentos",
    "o mercado deve reagir", "fique atento aos proximos passos",
)


def _resumo_e_generico(resumo: str, titulo: str) -> bool:
    """True quando o CORPO do resumo (bloco RESUMO, sem a LEITURA DE
    MERCADO) é, na prática, preenchimento vazio: ou contém uma das frases
    proibidas (ver _FRASES_GENERICAS_PROIBIDAS), ou é, em essência, a
    MESMA manchete com outras palavras (sobreposição de tokens altíssima
    e sem palavra nova relevante) - os dois sintomas que o prompt proíbe
    explicitamente mas que um modelo às vezes ainda produz sob texto-
    fonte pobre. Nunca lança excecao (resumo/titulo vazios -> False, não
    é "genérico", é "vazio" - tratado em outro lugar)."""
    if not resumo or not titulo:
        return False
    paragrafos, _ = separar_secoes_resumo(resumo)
    corpo = _sem_acento(" ".join(paragrafos))
    if any(f in corpo for f in _FRASES_GENERICAS_PROIBIDAS):
        return True
    tokens_corpo = _tokens_similaridade(" ".join(paragrafos), "")
    tokens_titulo = _tokens_similaridade(titulo, "")
    if tokens_titulo and len(tokens_corpo) <= len(tokens_titulo) + 3:
        if _similaridade(tokens_corpo, tokens_titulo) >= 0.85:
            return True
    return False


# --- Gate de consistencia: contradicao manchete vs resumo (ABA 5, --------
# auditoria 2026-10-17) -----------------------------------------------------
# achado real em producao: manchete "IBOVESPA fecha hoje com alta de 0,54%"
# com RESUMO afirmando queda, e atribuindo o movimento a pesquisas
# eleitorais/Fed/petroleo sem nenhuma base no texto/manchetes de origem.
# O prompt (_PROMPT_SISTEMA_RESUMO) ja' proibia as duas coisas, mas nenhum
# gate automatico verificava - exatamente o mesmo problema que motivou
# _resumo_e_generico (Groq free tier ocasionalmente ignora regra de prompt
# sob texto-fonte pobre, ver comentario ali). Os dois gates abaixo seguem
# o MESMO contrato: deteccao conservadora por regras (nunca por IA), e
# quem chama (_gerar_resumo_grupo) trata reprovacao exatamente como uma
# falha desta fonte/caminho - tenta o proximo fallback, nunca cacheia
# nem devolve como sucesso.
_TERMOS_ALTA_MERCADO = (
    "alta", "sobe", "subiu", "sobem", "avanca", "avancou", "dispara",
    "disparou", "valoriza", "valorizou", "ganha", "ganhou", "recupera",
    "recuperou", "salta", "saltou", "dispara",
)
_TERMOS_QUEDA_MERCADO = (
    "queda", "cai", "caiu", "caem", "recua", "recuou", "desaba", "desabou",
    "despenca", "despencou", "perde", "perdeu", "deprecia", "depreciou",
    "tomba", "tombou", "derrete", "derreteu", "afunda", "afundou",
)

_RE_PERCENTUAL = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*%")
_TOLERANCIA_PERCENTUAL = 0.1  # diferenca de arredondamento entre fontes (ex: 0,54% vs 0,5%)


# "baixa" (substantivo comum em manchete de mercado, ex: "fecha em baixa
# de 1,2%") nao entra em _TERMOS_QUEDA_MERCADO como substring solta - a
# mesma palavra tambem aparece em contextos SEM NADA a ver com direcao
# ("baixa liquidez", "baixa volatilidade", "baixa renda"), o que causaria
# falso positivo de queda num resumo so' comentando liquidez/volatilidade.
# So' conta como sinal de queda quando vem seguida de "de" + numero (o
# padrao real de manchete de fechamento, ex: "baixa de 1,2%") - casos
# ambiguos (sem o numero logo depois) NUNCA contam, mesmo espirito
# conservador do resto deste gate.
_RE_BAIXA_DIRECAO = re.compile(r"\bbaixa\s+de\s*\d")


def _direcao_mercado(texto: str) -> str | None:
    """'alta'/'queda'/None a partir de termos literais de direcao de
    mercado (ver _TERMOS_ALTA_MERCADO/_TERMOS_QUEDA_MERCADO, mais o padrao
    "baixa de <numero>" - ver _RE_BAIXA_DIRECAO). Texto citando as DUAS
    direcoes (ex: comparando ativos diferentes dentro do mesmo paragrafo)
    devolve None de proposito - so' sinaliza contradicao quando cada lado
    (titulo x resumo) tem um sinal INEQUIVOCO, nunca por uma leitura
    ambigua."""
    t = _sem_acento(texto or "")
    tem_alta = any(termo in t for termo in _TERMOS_ALTA_MERCADO)
    tem_queda = any(termo in t for termo in _TERMOS_QUEDA_MERCADO) or bool(_RE_BAIXA_DIRECAO.search(t))
    if tem_alta and not tem_queda:
        return "alta"
    if tem_queda and not tem_alta:
        return "queda"
    return None


# nome proprio (capitalizado, 3+ letras) - usado so' pra decidir se um
# percentual do RESUMO esta' textualmente atribuido a uma empresa/ativo
# diferente do titulo (ver _percentuais_atribuiveis) - deteccao bem
# simples (sem lista de empresas, sem NER) de proposito: o objetivo nao e'
# reconhecer QUAL empresa e', so' ter um sinal razoavel de "este numero e'
# sobre outra coisa, nao sobre o fato do titulo".
_RE_NOME_PROPRIO = re.compile(r"\b[A-ZÀ-ÚÇ][a-zà-úç]{2,}\b")
_JANELA_ATRIBUICAO_PERCENTUAL = 40  # caracteres antes do "%" onde procurar o nome proprio


def _percentuais(texto: str) -> set:
    """Conjunto de percentuais citados (float, 2 casas) - usado so' pra
    comparar titulo vs resumo, nunca pra validar o valor contra uma fonte
    de cotacao independente (nao temos uma aqui)."""
    valores = set()
    for m in _RE_PERCENTUAL.finditer(texto or ""):
        try:
            valores.add(round(float(m.group(1).replace(",", ".")), 2))
        except ValueError:
            continue
    return valores


def _percentuais_atribuiveis(titulo: str, texto: str) -> set:
    """Percentuais do TEXTO que NAO estao atribuidos, pela proximidade
    textual, a um nome proprio AUSENTE do titulo (ex: titulo sobre o
    Ibovespa, resumo citando "...impulsionado pela Vale, que subiu 2,1%
    com a alta do minerio..." - achado real desta revisao: esse 2,1% e'
    sobre a Vale, uma empresa citada como destaque dentro de uma materia
    de fechamento do indice, NUNCA deveria ser comparado ao percentual do
    titulo do INDICE. Sem isso, qualquer resumo de fechamento que cite o
    desempenho de uma acao que puxou o pregao (padrao editorial comum,
    nao um erro) seria rejeitado como "contradicao" por engano - o
    problema nao e' o numero estar errado, e' ele ser sobre OUTRO ativo.
    Deteccao conservadora: so' exclui quando ha' um nome proprio na janela
    curta ANTES do numero que nao aparece no titulo - titulo vazio (so'
    usado nunca, titulo sempre existe aqui) ou sem nome proprio nenhum na
    janela devolve o percentual normalmente (nunca exclui sem motivo)."""
    nomes_titulo = set(_RE_NOME_PROPRIO.findall(titulo or ""))
    valores = set()
    for m in _RE_PERCENTUAL.finditer(texto or ""):
        janela = texto[max(0, m.start() - _JANELA_ATRIBUICAO_PERCENTUAL): m.start()]
        nomes_janela = set(_RE_NOME_PROPRIO.findall(janela)) - nomes_titulo
        if nomes_janela:
            continue
        try:
            valores.add(round(float(m.group(1).replace(",", ".")), 2))
        except ValueError:
            continue
    return valores


def _percentuais_conflitam(a: set, b: set) -> bool:
    if not a or not b:
        return False
    return not any(abs(x - y) <= _TOLERANCIA_PERCENTUAL for x in a for y in b)


def _contradicao_titulo_resumo(titulo: str, corpo_resumo: str) -> str | None:
    """Descricao da contradicao entre o TITULO do grupo e o CORPO do
    resumo (bloco RESUMO, sem LEITURA DE MERCADO - essa secao PODE ser
    interpretacao analitica, ver _PROMPT_SISTEMA_RESUMO), ou None se nao
    houver contradicao detectavel. So' sinaliza quando ha' sinal
    inequivoco e DIFERENTE dos dois lados (direcao de mercado ou
    percentual) - qualquer ambiguidade deixa passar, nunca bloqueia sem
    uma contradicao clara (mesmo espirito conservador de _resumo_e_generico).

    O percentual do RESUMO passa por _percentuais_atribuiveis (nao
    _percentuais puro) - um numero claramente atribuido a outra empresa/
    ativo (ver docstring de _percentuais_atribuiveis) nunca conta como
    contradicao do percentual do indice/fato do titulo."""
    direcao_titulo = _direcao_mercado(titulo)
    direcao_resumo = _direcao_mercado(corpo_resumo)
    if direcao_titulo and direcao_resumo and direcao_titulo != direcao_resumo:
        return f"manchete indica '{direcao_titulo}' mas o resumo gerado indica '{direcao_resumo}'"

    percentuais_titulo = _percentuais(titulo)
    percentuais_resumo = _percentuais_atribuiveis(titulo, corpo_resumo)
    if _percentuais_conflitam(percentuais_titulo, percentuais_resumo):
        return (
            f"percentual da manchete ({', '.join(f'{v:g}' for v in sorted(percentuais_titulo))}%) "
            f"nao bate com o percentual do resumo ({', '.join(f'{v:g}' for v in sorted(percentuais_resumo))}%)"
        )
    return None


# conectores que introduzem uma relacao causa->consequencia explicita -
# clausula que usa um destes PRECISA ter pelo menos 1 palavra de conteudo
# em comum com o texto-base (texto extraido OU manchetes, ver
# _gerar_resumo_grupo), senao e' causalidade que so' a IA conectou, nao a
# fonte (secao 4B/4C do pedido - "nunca atribua causalidade sem evidencia").
_CONECTORES_CAUSAIS = (
    "por causa de", "por causa do", "por causa da", "por causa dos", "por causa das",
    "por conta de", "por conta do", "por conta da", "por conta dos", "por conta das",
    "devido a", "devido ao", "devido as", "devido aos",
    "em meio a", "em meio ao", "em meio as", "em meio aos",
    "impulsionado por", "impulsionada por", "motivado por", "motivada por",
    "na esteira de", "diante de", "em resposta a", "em resposta ao", "em resposta as",
    "puxado por", "puxada por", "pressionado por", "pressionada por",
    "influenciado por", "influenciada por",
)

# palavras genericas demais pra servir de "evidencia" de base (alem das
# _STOPWORDS ja' filtradas por _tokens_similaridade) - sem isso, qualquer
# clausula causal que so' mencione "mercado"/"sessao"/"dia" passaria o
# gate mesmo sem nenhum termo de conteudo real em comum com a fonte.
_PALAVRAS_GENERICAS_CAUSAL = {
    "mercado", "mercados", "sessao", "dia", "dias", "semana", "hoje",
    "ontem", "pregao", "movimento", "movimentos", "cenario", "investidores",
}


def _clausulas_causais(corpo: str) -> list:
    """Trecho causal de cada sentenca do CORPO do resumo que usa um
    conector causal explicito (ver _CONECTORES_CAUSAIS) - SO' a partir do
    conector em diante (a justificativa em si), nunca a sentenca inteira:
    o sujeito/verbo ANTES do conector quase sempre tem base no texto (e'
    o fato principal, normalmente já' extraido dali), e incluir essas
    palavras na checagem de evidencia mascararia uma causa inventada
    colada no final de uma frase por outro lado bem fundamentada (achado
    real ao escrever o teste desta auditoria: 'A Petrobras anunciou X **em
    meio a pesquisas eleitorais**' tem base de sobra pra 'Petrobras'/'X',
    mas NENHUMA pra 'pesquisas eleitorais' - e' exatamente essa 2a parte
    que precisa ser avaliada isoladamente)."""
    sentencas = re.split(r"(?<=[.!?])\s+", corpo or "")
    achadas = []
    for s in sentencas:
        if not s.strip():
            continue
        norm = _sem_acento(s)
        posicoes = (norm.find(c) for c in _CONECTORES_CAUSAIS)
        pos = min((p for p in posicoes if p != -1), default=-1)
        if pos != -1:
            achadas.append(s[pos:])
    return achadas


def _causalidade_sem_evidencia(corpo_resumo: str, texto_base: str) -> str | None:
    """Descricao da PRIMEIRA clausula causal do resumo sem NENHUMA palavra
    de conteudo em comum com o texto_base (texto extraido da materia ou
    manchetes das fontes, dependendo do caminho de geracao - ver
    _gerar_resumo_grupo), ou None se todas as clausulas causais tiverem
    base. So' sinaliza quando a clausula tem pelo menos 2 palavras de
    conteudo (depois de remover stopwords/termos genericos) e ZERO
    sobreposicao com a base - clausula muito curta pra avaliar com
    confianca (so' 1 palavra de conteudo) deixa passar, nunca bloqueia
    por uma diferenca de redacao/sinonimo."""
    clausulas = _clausulas_causais(corpo_resumo)
    if not clausulas:
        return None
    tokens_base = _tokens_similaridade(texto_base or "", "")
    for clausula in clausulas:
        tokens_clausula = _tokens_similaridade(clausula, "") - _PALAVRAS_GENERICAS_CAUSAL
        if len(tokens_clausula) >= 2 and not (tokens_clausula & tokens_base):
            return f"trecho causal sem base no texto/manchetes de origem: \"{clausula.strip()}\""
    return None


def _validar_consistencia(resumo: str, titulo: str, texto_base: str) -> str | None:
    """Motivo de reprovacao do resumo (contradicao de direcao/percentual OU
    causalidade sem evidencia), ou None se passou nos dois gates. So' olha
    o bloco RESUMO (corpo) - a LEITURA DE MERCADO pode ser interpretacao
    analitica por natureza (ver _PROMPT_SISTEMA_RESUMO), entao nao passa
    por este gate. Usado 3x em _gerar_resumo_grupo (texto completo de 1
    fonte / fragmentos combinados / so'-manchetes), cada vez com o
    texto_base apropriado a' evidencia realmente disponivel naquele
    caminho."""
    paragrafos, _leitura = separar_secoes_resumo(resumo)
    corpo = " ".join(paragrafos)
    motivo = _contradicao_titulo_resumo(titulo, corpo)
    if motivo:
        return motivo
    return _causalidade_sem_evidencia(corpo, texto_base)


def _combinar_fragmentos(fragmentos: list, titulos_unicos: tuple) -> str:
    """Junta pedaços curtos de texto de fontes diferentes do grupo (cada
    um curto demais sozinho pra resumir, ver _MIN_CHARS_TEXTO) com as
    manchetes das fontes - ultimo recurso antes do fallback so'-manchete
    (_resumir_das_manchetes), usado quando pelo menos 1 fragmento de
    texto de verdade foi extraído (por curto que seja)."""
    partes = [f"Trechos extraídos de {len(fragmentos)} fonte(s) diferente(s) sobre o mesmo fato:\n" + "\n---\n".join(fragmentos)]
    if titulos_unicos:
        partes.append("Manchetes das fontes:\n" + "\n".join(f"- {t}" for t in titulos_unicos))
    return "\n\n".join(partes)


def _resumir_das_manchetes(titulo: str, titulos: tuple) -> tuple:
    """Fallback quando NENHUMA fonte do grupo deu pra baixar/extrair
    (todas bloquearam/paywall): resume só com base nas manchetes das
    várias fontes que cobriram o mesmo fato (grupo já mesclado por
    _agrupar - ver data/news.py). Mesma assinatura de retorno de
    _resumir_com_groq: (resumo, motivo_falha)."""
    manchetes = "\n".join(f"- {t}" for t in dict.fromkeys(titulos))  # remove duplicatas, preserva ordem
    prompt_usuario = f"Manchetes sobre o mesmo fato (fontes diferentes):\n{manchetes}"
    return _chamar_groq(_PROMPT_SISTEMA_RESUMO_MANCHETES, prompt_usuario)


def _gerar_resumo_grupo(titulo: str, fontes_ordenadas: tuple, titulos: tuple = (), validar_imagem: bool = False) -> dict:
    """Resumo de um GRUPO de noticias (mesmo fato, possivelmente varias
    fontes) - tenta cada fonte do grupo, na ordem recebida (ver
    ordenar_fontes_para_resumo), ate uma dar certo: resolve o link real,
    extrai o texto com trafilatura e resume com Groq, sempre em palavras
    proprias. Se TODAS as fontes falharem (paywall, bloqueio, sem
    conteudo) mas houver mais de uma manchete no grupo (`titulos`), tenta
    um resumo so' com as manchetes (_resumir_das_manchetes) antes de
    desistir - pior que o resumo com texto completo, mas melhor que nada
    quando o grupo tem varias fontes concordando no fato. Se isso tambem
    falhar (ou so' tiver 1 titulo, sem info extra pra sintetizar), retorna
    resumo=None - a interface mostra so "resumo indisponível" e o link da
    materia continua disponivel normalmente (e' o link que a manchete do
    grupo ja usa).

    Fluxo de geracao de verdade - chamado por obter_resumo_grupo so' em
    cache miss (ver data/ia_cache.py).

    motivo_indisponivel guarda o motivo ESPECIFICO da ULTIMA fonte
    tentada (decode falhou / erro ao baixar / conteúdo curto / cota da
    IA) - a interface mostra isso em vez de um "indisponível" generico,
    ajuda a diferenciar bloqueio do servidor de paywall de verdade.

    "imagem" (fase 3, feed editorial): URL da foto principal da materia,
    extraida do MESMO download usado pra resumir (ver
    _extrair_texto_artigo) - nunca uma requisicao de rede extra so' pra
    imagem. So' preenchida no caminho de fonte UNICA bem-sucedida (uma
    pagina real, um og:image real); nos caminhos de fallback (fragmentos
    combinados de VARIAS fontes, ou so'-manchetes) fica None de proposito
    - misturar texto de paginas diferentes e' aceitavel pro resumo
    (sintese), mas escolher a foto de UMA dessas paginas pra representar
    o grupo inteiro seria arbitrario.

    validar_imagem=True (so' usado pelo PRE-PROCESSAMENTO em lote, ver
    pregerar_resumos_news): confirma por rede (_url_imagem_utilizavel)
    que a imagem escolhida realmente responde como foto antes de
    devolver/cachear - default False preserva o comportamento de sempre
    (zero requisicao de rede extra) pro caminho sob-demanda (clique no
    card abre o modal).

    qualidade_texto (ABA 5, 2026-10-17): classifica a evidencia real por
    tras do resumo devolvido - "full_text" (texto integral de 1 fonte),
    "partial_text" (fragmentos curtos combinados de varias fontes),
    "snippet_only" (so' manchetes, nenhum texto baixado) ou
    "extraction_failed" (nenhum resumo). Toda vez que o resumo passa
    (gate _resumo_e_generico) tambem passa por _validar_consistencia
    (contradicao de direcao/percentual entre titulo e resumo, e
    causalidade atribuida sem base no texto/manchetes de origem) - reprovado
    ai' e' tratado EXATAMENTE como uma falha desta fonte/caminho (nunca
    cacheado, tenta o proximo fallback); se todos os caminhos reprovarem,
    a funcao desiste honestamente (resumo=None) em vez de publicar uma
    sintese que contradiz o proprio titulo do grupo."""
    # qual modelo Groq de fato gera o resumo - usado so' como metadado de
    # auditoria/debug na coluna "modelo" do cache global (data/ia_cache.py:
    # resumos_ia_cache); diferente do research, o NEWS nao tem fallback de
    # modelo (_chamar_groq usa sempre config.obter_credenciais_groq(),
    # sem 2a tentativa) - entao aqui e' sempre o mesmo valor, sem
    # ambiguidade nenhuma pra determinar (achado real, FASE 8 2026-10-08).
    _, modelo_groq_usado = config.obter_credenciais_groq()

    ultimo_motivo = "nenhuma fonte disponível no grupo"
    fragmentos_curtos = []
    for veiculo, link in fontes_ordenadas:
        texto, imagem, link_real, motivo_extracao = _extrair_texto_artigo(link)
        if texto is None:
            ultimo_motivo = motivo_extracao or ultimo_motivo
            continue
        if len(texto) < _MIN_CHARS_TEXTO:
            # curto demais pra resumir sozinho (nota rapida/paywall agressivo
            # deixando so' um fragmento) - guarda pra tentar combinar com
            # outras fontes do grupo antes de desistir (ver abaixo)
            fragmentos_curtos.append(texto)
            continue
        resumo, motivo_groq = _resumir_com_groq(texto, titulo)
        if resumo and _resumo_e_generico(resumo, titulo):
            # modelo nao seguiu a regra do prompt (preenchimento generico
            # ou mera parafrase da manchete) - nunca cacheia isso como
            # sucesso; tenta a proxima fonte do grupo, exatamente como se
            # esta fonte tivesse falhado.
            ultimo_motivo = "resumo gerado era genérico/sem informação específica (descartado)"
            resumo = None
        if resumo:
            motivo_inconsistencia = _validar_consistencia(resumo, titulo, texto)
            if motivo_inconsistencia:
                # resumo contradiz o titulo (direcao/percentual) ou atribui
                # causalidade que a propria fonte nao afirma - mesmo
                # tratamento do gate generico acima: nunca cacheia, tenta a
                # proxima fonte do grupo (ver Caso 3 do pedido - "tentar
                # resolver por meio de fontes verificaveis antes de desistir").
                ultimo_motivo = f"resumo gerado é inconsistente com a fonte ({motivo_inconsistencia}) — descartado"
                resumo = None
        if resumo:
            if validar_imagem and imagem and not _url_imagem_utilizavel(imagem):
                imagem = None
            return {"resumo": resumo, "link_original": link_real, "imagem": imagem,
                    "motivo_indisponivel": None, "modelo": modelo_groq_usado, "parcial": False,
                    "qualidade_texto": "full_text"}
        if motivo_groq == "cota" or "GROQ_API_KEY" in (motivo_groq or ""):
            # falha do Groq em si (cota/config), nao da fonte - tentar as
            # proximas fontes do grupo so repetiria o mesmo erro a toa
            return {"resumo": None, "link_original": link_real, "imagem": None, "motivo_indisponivel": motivo_groq}
        ultimo_motivo = motivo_groq or ultimo_motivo

    titulos_unicos = tuple(dict.fromkeys(titulos))

    # nenhuma fonte teve texto longo o bastante sozinha, mas pelo menos 1
    # fragmento curto foi extraido de verdade - combina fragmento(s) +
    # manchetes antes de cair pro fallback so'-manchete (sinal mais fraco).
    # "parcial"=True daqui pra baixo (ver ui/news_tab.py): a sintese nao
    # veio do texto completo de UMA materia, a UI avisa isso discretamente
    # (pedido do Rodrigo - nunca simular acesso ao texto completo).
    if fragmentos_curtos:
        texto_combinado = _combinar_fragmentos(fragmentos_curtos, titulos_unicos)
        resumo, motivo_groq = _resumir_com_groq(texto_combinado, titulo)
        if resumo and _resumo_e_generico(resumo, titulo):
            ultimo_motivo = "resumo gerado era genérico/sem informação específica (descartado)"
            resumo = None
        if resumo:
            motivo_inconsistencia = _validar_consistencia(resumo, titulo, texto_combinado)
            if motivo_inconsistencia:
                ultimo_motivo = f"resumo gerado é inconsistente com a fonte ({motivo_inconsistencia}) — descartado"
                resumo = None
        if resumo:
            return {"resumo": resumo, "link_original": None, "imagem": None,
                    "motivo_indisponivel": None, "modelo": modelo_groq_usado, "parcial": True,
                    "qualidade_texto": "partial_text"}
        if motivo_groq == "cota" or "GROQ_API_KEY" in (motivo_groq or ""):
            return {"resumo": None, "link_original": None, "imagem": None, "motivo_indisponivel": motivo_groq}
        ultimo_motivo = motivo_groq or ultimo_motivo

    if len(titulos_unicos) >= 2:
        manchetes_base = "\n".join(titulos_unicos)
        resumo, motivo_groq = _resumir_das_manchetes(titulo, titulos_unicos)
        if resumo and _resumo_e_generico(resumo, titulo):
            ultimo_motivo = "resumo gerado era genérico/sem informação específica (descartado)"
            resumo = None
        if resumo:
            motivo_inconsistencia = _validar_consistencia(resumo, titulo, manchetes_base)
            if motivo_inconsistencia:
                ultimo_motivo = f"resumo gerado é inconsistente com a fonte ({motivo_inconsistencia}) — descartado"
                resumo = None
        if resumo:
            return {"resumo": resumo, "link_original": None, "imagem": None,
                    "motivo_indisponivel": None, "modelo": modelo_groq_usado, "parcial": True,
                    "qualidade_texto": "snippet_only"}
        if motivo_groq == "cota" or "GROQ_API_KEY" in (motivo_groq or ""):
            return {"resumo": None, "link_original": None, "imagem": None, "motivo_indisponivel": motivo_groq}
        ultimo_motivo = motivo_groq or ultimo_motivo

    return {"resumo": None, "link_original": None, "imagem": None, "motivo_indisponivel": ultimo_motivo,
            "qualidade_texto": "extraction_failed"}


def obter_resumo_grupo(titulo: str, fontes_ordenadas: tuple, titulos: tuple = (), validar_imagem: bool = False) -> dict:
    """Resumo de um GRUPO de noticias - ver _gerar_resumo_grupo pro
    fluxo de geracao de verdade (inalterado). Esta funcao so' embrulha
    com o cache GLOBAL do Supabase (data/ia_cache.py): cache hit (outro
    usuario ja' resumiu o MESMO grupo) devolve sem chamar IA; cache miss
    gera e persiste pra todos os usuarios reutilizarem depois. Chave de
    cache = titulo+conjunto de links das fontes do grupo (ver
    ia_cache.chave_news) - nunca so' o ticker, e muda se uma fonte nova
    entrar no grupo (tratado como documento diferente de proposito).

    validar_imagem: repassado pra _gerar_resumo_grupo - so' True quando
    quem chama e' o pre-processamento em lote (pregerar_resumos_news)."""
    links = tuple(link for _, link in fontes_ordenadas)
    chave = ia_cache.chave_news(titulo, links)
    link_principal = fontes_ordenadas[0][1] if fontes_ordenadas else None
    return ia_cache.obter_resumo_com_cache(
        chave, link_principal, "news",
        lambda: _gerar_resumo_grupo(titulo, fontes_ordenadas, titulos, validar_imagem=validar_imagem),
    )


def obter_resumos_prontos(grupos: list) -> dict:
    """Leitura em LOTE (1 unica query, NUNCA gera) dos resumos/imagens JA
    cacheados pros grupos dados - usada pelo feed editorial (fase 3) pra
    mostrar resumo curto + foto direto no card da lista, sem chamada de
    rede nem de IA por card (ver ia_cache.obter_varios). Grupo ainda sem
    resumo cacheado simplesmente nao aparece no dict retornado - quem
    chama mostra so' titulo+meta pra esse card (nunca inventa resumo).

    Retorna {link_do_grupo: resultado} - 'link' e' a mesma chave que a
    UI ja usa pra identificar um grupo na lista (ver ui/news_tab.py)."""
    link_por_chave = {}
    for g in grupos:
        fontes_ordenadas = ordenar_fontes_para_resumo(g["fontes"])
        links = tuple(link for _, link in fontes_ordenadas)
        chave = ia_cache.chave_news(g["titulo"], links)
        link_por_chave[chave] = g["link"]
    if not link_por_chave:
        return {}
    encontrados = ia_cache.obter_varios(list(link_por_chave.keys()))
    return {link_por_chave[chave]: resultado for chave, resultado in encontrados.items()}


# --- Pre-processamento em lote (reformulacao editorial, 2026-10-15) -----
#
# Problema que isto resolve (ver secao 4 do pedido): o feed editorial so'
# mostra resumo/foto quando algum USUARIO ja' abriu aquele grupo antes
# (obter_resumos_prontos so' LE o que ja' esta' cacheado, nunca gera - ver
# acima); sem pre-processamento, a imensa maioria dos cards novos aparece
# so' com manchete+metadados ate' alguem clicar. A solucao escolhida e' a
# mais simples que se encaixa na arquitetura ja existente: reaproveitar o
# COLETOR PERIODICO que ja roda a cada 30min no GitHub Actions
# (coletor_local.py, ver .github/workflows/coletores-nuvem.yml) - ja' tem
# as credenciais do Supabase, ja' roda fora de qualquer sessao Streamlit
# e ja' usa o MESMO padrao de orcamento de tempo + rotacao de universo
# (ver data/eventos_coleta.py:coletar_eventos_universo). Nao criamos fila/
# worker novo nem infra separada - so' mais um passo dentro do coletor que
# ja existe, chamando a MESMA obter_resumo_grupo que o clique no card ja
# usa (cache-safe, protegido contra geracao duplicada concorrente - ver
# data/ia_cache.py).
#
# Universo coberto por execucao, nesta ordem de prioridade:
# 1. TOP MERCADO (BRASIL+INTERNACIONAL, ja' ranqueado por importancia e
#    limitado a _TOP_MERCADO_QTD=20 itens) - e' o feed GLOBAL que todo
#    usuario ve, maior retorno por resumo gerado.
# 2. Noticias de uma FATIA ROTATIVA do universo de tickers (quem chama
#    passa a fatia - ver coletor_local.py:_universo_rotativo - cobrindo o
#    universo inteiro ao longo de varias execucoes, mesmo padrao do
#    CALENDARIO).
#
# Nunca gera 2x o mesmo grupo (dedup por chave de cache ANTES de chamar a
# IA) e nunca re-gera um grupo ja' cacheado por um usuario entre 2
# execucoes do coletor (checa ia_cache.obter_varios antes). Orcamento de
# tempo E contagem maxima de resumos por execucao (cota do Groq free tier
# e' compartilhada com o research) - nunca roda indefinidamente.
_ORCAMENTO_PREGERAR_RESUMOS_S = 4 * 60
_MAX_RESUMOS_POR_EXECUCAO = 25


def pregerar_resumos_news(tickers_universo: list) -> dict:
    """Gera (e cacheia globalmente) os resumos/imagens ainda FALTANTES do
    TOP MERCADO + da fatia de tickers recebida - chamado so' pelo coletor
    periodico (coletor_local.py), nunca pelo app Streamlit em si (que so'
    LE cache, ver obter_resumos_prontos/render_news). validar_imagem=True
    aqui (unico chamador que usa isso) - o orcamento extra de rede pra
    confirmar a foto so' vale a pena pro conteudo que vai ficar visivel
    pra TODOS os usuarios, nao pro clique individual sob demanda.

    Retorna stats: {"grupos_considerados", "ja_cacheados", "gerados",
    "falhas", "tempo_esgotado", "tabela_disponivel"} - nunca lança
    excecao (falha isolada de 1 grupo/ticker nao aborta os demais, ver
    try/except por item).

    Confere ia_cache.tabela_disponivel() ANTES de buscar qualquer
    noticia ou gastar 1 token de IA (achado real 2026-10-15: a tabela
    resumos_ia_cache nunca foi criada em produção - sql/ia_cache.sql
    nunca rodou lá - e sem esta checagem o pré-processamento gerava 25
    resumos de verdade (cota real do Groq) TODA execução do coletor
    [30min] sem conseguir cachear nenhum: cada resultado era descartado
    em silêncio porque a escrita no Supabase falhava depois do gerar_fn()
    já ter rodado. Nunca bloqueia o caminho sob-demanda (clique no card) -
    só este pré-processamento em lote, que só vale a pena gastar cota se
    o resultado puder ser reaproveitado por todos os usuários depois."""
    stats = {"grupos_considerados": 0, "ja_cacheados": 0, "gerados": 0, "falhas": 0, "tempo_esgotado": False}
    disponivel = ia_cache.tabela_disponivel()
    stats["tabela_disponivel"] = disponivel
    if disponivel is not True:
        return stats

    limite = time.monotonic() + _ORCAMENTO_PREGERAR_RESUMOS_S

    grupos = []
    try:
        grupos.extend(obter_top_mercado_tudo("TODOS") or [])
    except Exception:
        logging.exception("pregerar_resumos_news: falha ao coletar TOP MERCADO")

    for ticker in tickers_universo:
        if time.monotonic() > limite:
            stats["tempo_esgotado"] = True
            break
        try:
            r = obter_noticias(ticker)
            if r:
                grupos.extend(r)
        except Exception:
            stats["falhas"] += 1
            logging.exception("pregerar_resumos_news: falha ao coletar noticias de %s", ticker)

    # dedup por chave de cache (um mesmo fato pode aparecer no TOP
    # MERCADO E na busca por ticker) - mais recente primeiro, ja' e' a
    # ordem devolvida por obter_noticias/obter_top_mercado_tudo
    pendentes = []
    vistos = set()
    for g in grupos:
        fontes_ordenadas = ordenar_fontes_para_resumo(g["fontes"])
        links = tuple(link for _, link in fontes_ordenadas)
        chave = ia_cache.chave_news(g["titulo"], links)
        if chave in vistos:
            continue
        vistos.add(chave)
        pendentes.append((chave, g, fontes_ordenadas))

    stats["grupos_considerados"] = len(pendentes)
    if not pendentes:
        return stats

    ja_prontos = ia_cache.obter_varios([chave for chave, _, _ in pendentes])
    stats["ja_cacheados"] = len(ja_prontos)

    for chave, g, fontes_ordenadas in pendentes:
        if chave in ja_prontos:
            continue
        if stats["gerados"] >= _MAX_RESUMOS_POR_EXECUCAO or time.monotonic() > limite:
            stats["tempo_esgotado"] = True
            break
        try:
            titulos_grupo = tuple(g.get("titulos") or [g["titulo"]])
            resultado = obter_resumo_grupo(g["titulo"], fontes_ordenadas, titulos_grupo, validar_imagem=True)
            # diagnostico temporario (2026-10-15): "gerados" conta toda
            # TENTATIVA sem excecao, nao so' sucesso real - uma falha
            # legitima do Groq (cota/extracao) devolve resumo=None SEM
            # lancar excecao, entao nunca aparecia aqui nem em _falhas.
            # Imprime so' quando resumo=None, pra confirmar se e' isso
            # (motivo_indisponivel real) que explica "gerado mas nada
            # cacheado", em vez de um bug de escrita silenciosa.
            if not resultado.get("resumo"):
                print(f"[pregerar_resumos_news] '{g['titulo'][:50]}' sem resumo: {resultado.get('motivo_indisponivel')!r}")
            stats["gerados"] += 1
        except Exception:
            stats["falhas"] += 1
            logging.exception("pregerar_resumos_news: falha ao gerar resumo de '%s'", g.get("titulo"))

    return stats
