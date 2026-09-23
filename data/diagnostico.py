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

_HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
_TIMEOUT = 10

# uma URL representativa por fonte - pra APIs, o endpoint real usado pelo
# coletor/consumidor; pra sites ainda nao investigados, a home da area de
# research (ver BACKLOG.md pra contexto de cada uma)
FONTES = [
    {"nome": "Genial Analisa", "url": "https://analisa.genialinvestimentos.com.br"},
    {"nome": "XP Investimentos", "url": "https://conteudos.xpi.com.br/wp-json/wp/v2/rel-acoes-fund?per_page=1"},
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
]


def testar_fonte(fonte: dict) -> dict:
    """Testa uma fonte de verdade: GET com timeout curto e impersonate
    Chrome (mesmo metodo que os coletores reais usam, pra o teste refletir
    a mesma coisa que aconteceria numa coleta de verdade). Nunca lanca
    excecao - status vira 'timeout' ou 'erro: <msg>' se a requisicao
    falhar. Retorna {nome, url, status, tempo_ms, tamanho_bytes, ok}."""
    inicio = time.monotonic()
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
