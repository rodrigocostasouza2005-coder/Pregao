# -*- coding: utf-8 -*-
"""Sondagem TEMPORÁRIA de fontes candidatas de research (22/10/2026),
rodada só no runner do GitHub Actions (o sandbox de desenvolvimento não
tem rede para esses sites). Só leitura: GET de robots.txt e do feed,
imprime status, tipo, itens e um trecho bruto para virar fixture."""
import sys
from urllib.parse import urlparse

import feedparser
import requests

UA = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
CANDIDATOS = [
    ("Itaú Private Insights", "https://blog.itau.com.br/privateinsights/feed/"),
    ("Itaú Análises", "https://www.itau.com.br/investimentos/analises/feed/"),
    ("Safra O Especialista", "https://oespecialista.safra.com.br/feed/"),
    ("Monte Bravo", "https://www.montebravo.com.br/feed/"),
    ("Rico economia-e-analises", "https://riconnect.rico.com.vc/blog/category/economia-e-analises/feed/"),
    ("BB Investalk", "https://investalk.bb.com.br/feed/"),
    ("Ágora", "https://www.agorainvest.com.br/feed/"),
    ("Órama", "https://blog.orama.com.br/feed/"),
    ("Toro", "https://blog.toroinvestimentos.com.br/feed/"),
    ("Ativa", "https://www.ativainvestimentos.com.br/feed/"),
    ("Bradesco DEPEC", "https://www.economiaemdia.com.br/feed/"),
    ("Inter Invest", "https://blog.bancointer.com.br/feed/"),
    ("Warren", "https://warren.com.br/magazine/feed/"),
]


def robots(url):
    p = urlparse(url)
    try:
        r = requests.get(f"{p.scheme}://{p.netloc}/robots.txt", headers=UA, timeout=10)
        linhas = [l for l in r.text.splitlines() if l.lower().startswith(("user-agent", "disallow", "allow"))]
        return f"HTTP {r.status_code}: " + " | ".join(linhas[:25])
    except Exception as e:
        return f"erro: {type(e).__name__}"


for nome, url in CANDIDATOS:
    print(f"\n===== {nome} :: {url}")
    print("robots:", robots(url))
    try:
        r = requests.get(url, headers=UA, timeout=15)
    except Exception as e:
        print("GET erro:", type(e).__name__, str(e)[:200])
        continue
    print("HTTP", r.status_code, r.headers.get("content-type"), "final:", r.url, "bytes:", len(r.content))
    feed = feedparser.parse(r.content)
    print("itens:", len(feed.entries), "bozo:", feed.bozo, "titulo do feed:", feed.feed.get("title"))
    for e in feed.entries[:6]:
        print("  -", e.get("published") or e.get("updated"), "|", (e.get("title") or "")[:110], "|", e.get("link"),
              "| cats:", [t.get("term") for t in e.get("tags", [])][:5])
    if feed.entries:
        print("BRUTO_INICIO")
        print(r.text[:6000])
        print("BRUTO_FIM")
sys.exit(0)
