# -*- coding: utf-8 -*-
"""DIAG TEMPORARIO v5 (somente leitura, NAO MERGEAR): quais endpoints
OFICIAIS de Selic/CDI respondem a partir do runner do GitHub. Usa o
mesmo User-Agent do projeto (sem trocar UA para driblar bloqueio)."""
import json, os, re, time
from datetime import date, timedelta
import requests
os.makedirs("saida_diag", exist_ok=True)
out = open("saida_diag/relatorio.txt", "w")
UA = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial)"}
hoje = date.today(); ini = hoje - timedelta(days=20)
f = lambda d: d.strftime("%d/%m/%Y")
URLS = [
    ("SGS 432 intervalo", f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?formato=json&dataInicial={f(ini)}&dataFinal={f(hoje)}"),
    ("SGS 432 ultimos/1", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"),
    ("SGS 4389 ultimos/1", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/1?formato=json"),
    ("SGS 12 ultimos/1", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json"),
    ("SGS 433 ultimos/1 (IPCA)", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/1?formato=json"),
    ("BCB site historico Copom", "https://www.bcb.gov.br/api/servico/sitebcb/historicotaxasjuros"),
    ("BCB site Copom ultimas", "https://www.bcb.gov.br/api/servico/sitebcb/copom/comunicados?quantidade=1"),
    ("Olinda servicos", "https://olinda.bcb.gov.br/olinda/servico/"),
    ("Olinda Expectativas selic (ok antes)", "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais?$top=1&$format=json"),
    ("B3/Cetip taxa DI", "https://www2.cetip.com.br/ConsultarTaxaDi/ConsultarTaxaDICetip.aspx"),
]
for rodada in range(2):
    for nome, url in URLS:
        try:
            r = requests.get(url, headers=UA, timeout=(5, 20))
            ct = r.headers.get("Content-Type", "")
            corpo = re.sub(r"\s+", " ", r.text[:400])
            titulo = re.search(r"<title>(.*?)</title>", r.text, re.I | re.S)
            linha = f"[{rodada}] {nome}: HTTP {r.status_code} ct={ct} len={len(r.text)} titulo={titulo.group(1).strip()[:60] if titulo else None} | {corpo[:300]}"
        except Exception as e:
            linha = f"[{rodada}] {nome}: EXC {type(e).__name__}: {e}"
        print(linha, flush=True); out.write(linha + "\n")
    time.sleep(20)
