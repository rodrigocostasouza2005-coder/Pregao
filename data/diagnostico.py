# -*- coding: utf-8 -*-
"""Diagnostico de fontes externas: testa reachability/tempo de resposta
de cada fonte de dados do PREGAO rodando de verdade no servidor (local ou
Streamlit Cloud). NAO faz parte do fluxo normal do app - so o painel
DIAGNOSTICO DE FONTES na aba CONFIG usa isso, sob demanda (botao), pra
confirmar o que funciona em producao sem depender do sandbox de
desenvolvimento (que tem varios dominios bloqueados por WAF/CDN por
IP/geografia - ver BACKLOG.md)."""

import time

from curl_cffi import requests as cffi_requests

from .research import genial, genial_lives, xp

_HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
_TIMEOUT = 10


def _testar_gnews_decode() -> tuple:
    """Busca uma noticia real do Google News (termo generico) e tenta
    decodificar o link + extrair o texto - mesmo pipeline do resumo de
    noticias (ver data/news.py:_extrair_texto_artigo). Existe porque o
    resumo de noticias as vezes falha so' em producao (Streamlit Cloud) -
    esse teste ajuda a saber se e' o decode do link (gnewsdecoder) ou o
    download da materia em si que esta sendo bloqueado."""
    from data.news import _buscar_feed, _extrair_texto_artigo

    entries = _buscar_feed("Ibovespa")
    if not entries:
        return False, "busca no Google News não retornou nada"
    link = entries[0].get("link") or ""
    if not link:
        return False, "entrada sem link"
    texto, link_real, motivo = _extrair_texto_artigo(link)
    if texto is None:
        return False, f"falhou: {motivo}"
    return True, f"OK ({len(texto)} chars extraídos, via {(link_real or '')[:50]})"


def _testar_trafilatura(url: str):
    """Baixa e extrai texto de uma URL direta (sem passar pelo Google
    News) com trafilatura - isola se o bloqueio e' no download do site em
    si (ex: InfoMoney, Money Times bloqueando o IP do Streamlit Cloud)."""
    def _testar():
        import trafilatura
        baixado = trafilatura.fetch_url(url)
        if not baixado:
            return False, "download falhou"
        texto = trafilatura.extract(baixado)
        if not texto:
            return False, "extração não achou texto"
        return True, f"OK ({len(texto)} chars extraídos)"
    return _testar


# Genial e XP tem coletor com retry (varias tentativas de TLS/HTTP/UA -
# ver testar_conexao em cada modulo) - o diagnostico chama a MESMA funcao
# que o coletor real usa, pra refletir se a coleta de verdade funcionaria,
# nao so um GET generico de uma tentativa so. Google News/InfoMoney/Money
# Times testam o pipeline de resumo de noticias (decode + download +
# extracao), separado da fonte de dados da noticia em si (RSS, ja testado
# implicitamente por qualquer noticia aparecer na aba NEWS).
_TESTES_ESPECIFICOS = {
    "Genial Analisa": genial.testar_conexao,
    "XP Investimentos": xp.testar_conexao,
    "Genial (Lives)": genial_lives.testar_conexao,
    "Google News (decode+extração)": _testar_gnews_decode,
    "InfoMoney (extração)": _testar_trafilatura("https://www.infomoney.com.br/"),
    "Money Times (extração)": _testar_trafilatura("https://www.moneytimes.com.br/"),
}

# uma URL representativa por fonte - pra APIs, o endpoint real usado pelo
# coletor/consumidor; pra sites ainda nao investigados, a home da area de
# research (ver BACKLOG.md pra contexto de cada uma). Genial/XP tambem tem
# url aqui so de referencia (o teste de verdade usa _TESTES_ESPECIFICOS).
FONTES = [
    {"nome": "Genial Analisa", "url": "https://analisa.genialinvestimentos.com.br"},
    {"nome": "XP Investimentos", "url": "https://conteudos.xpi.com.br/wp-json/wp/v2/rel-acoes-fund?per_page=1"},
    {"nome": "Genial (Lives)", "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCYSOMA4Yx1CJvrdI8epLfnA"},
    {"nome": "BTG Research", "url": "https://content.btgpactual.com/api/research/public-router/media-research/api/media-research/public/v1/medias/lives?status=LIVE&pageNumber=1&pageSize=1"},
    {"nome": "Itaú BBA", "url": "https://www.itau.com.br/itaubba-pt/analises-economicas"},
    {"nome": "Santander", "url": "https://www.santandercorretora.com.br/corretora/home/nossos-servicos/relatorios.html"},
    {"nome": "BB Investimentos", "url": "https://investalk.bb.com.br/relatorios-e-analises"},
    {"nome": "Safra", "url": "https://oespecialista.safra.com.br/"},
    {"nome": "Ágora Investimentos", "url": "https://insights.agorainvestimentos.com.br/conteudo"},
    {"nome": "Inter Invest", "url": "https://interinvest.inter.co/"},
    {"nome": "Google News", "url": "https://news.google.com/rss?hl=pt-BR&gl=BR&ceid=BR:pt-419"},
    {"nome": "Banco Central (SGS)", "url": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"},
    {"nome": "ANBIMA (ETTJ)", "url": "https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp"},
    {"nome": "Google News (decode+extração)", "url": "https://news.google.com/rss/search?q=Ibovespa"},
    {"nome": "InfoMoney (extração)", "url": "https://www.infomoney.com.br/"},
    {"nome": "Money Times (extração)", "url": "https://www.moneytimes.com.br/"},
]


def testar_fonte(fonte: dict) -> dict:
    """Testa uma fonte de verdade. Pra Genial/XP, chama o testar_conexao()
    do proprio coletor (varias tentativas de TLS/HTTP/UA, a mesma logica
    da coleta real). Pras demais, um GET simples com timeout curto e
    impersonate Chrome. Nunca lanca excecao - status vira 'timeout' ou
    'erro: <msg>' se a requisicao falhar. Retorna {nome, url, status,
    tempo_ms, tamanho_bytes, ok}."""
    inicio = time.monotonic()

    teste_especifico = _TESTES_ESPECIFICOS.get(fonte["nome"])
    if teste_especifico:
        try:
            ok, detalhe = teste_especifico()
            tempo_ms = int((time.monotonic() - inicio) * 1000)
            return {
                "nome": fonte["nome"], "url": fonte["url"], "status": detalhe,
                "tempo_ms": tempo_ms, "tamanho_bytes": 0, "ok": ok,
            }
        except Exception as e:
            tempo_ms = int((time.monotonic() - inicio) * 1000)
            return {
                "nome": fonte["nome"], "url": fonte["url"], "status": f"erro: {e}",
                "tempo_ms": tempo_ms, "tamanho_bytes": 0, "ok": False,
            }

    try:
        r = cffi_requests.get(fonte["url"], headers=_HEADERS, impersonate="chrome", timeout=_TIMEOUT)
        tempo_ms = int((time.monotonic() - inicio) * 1000)
        return {
            "nome": fonte["nome"], "url": fonte["url"], "status": str(r.status_code),
            "tempo_ms": tempo_ms, "tamanho_bytes": len(r.content), "ok": r.status_code == 200,
        }
    except Exception as e:
        tempo_ms = int((time.monotonic() - inicio) * 1000)
        texto_erro = str(e).lower()
        status = "timeout" if "timeout" in texto_erro or "timed out" in texto_erro else f"erro: {e}"
        return {
            "nome": fonte["nome"], "url": fonte["url"], "status": status,
            "tempo_ms": tempo_ms, "tamanho_bytes": 0, "ok": False,
        }
