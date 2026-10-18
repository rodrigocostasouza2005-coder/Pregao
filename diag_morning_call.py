# -*- coding: utf-8 -*-
"""DIAG TEMPORARIO v6 (somente leitura, NAO MERGEAR): estrutura do JSON
oficial de historico do Copom (www.bcb.gov.br)."""
import json, os, requests
os.makedirs("saida_diag", exist_ok=True)
UA = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial)"}
r = requests.get("https://www.bcb.gov.br/api/servico/sitebcb/historicotaxasjuros", headers=UA, timeout=(5, 25))
d = r.json()
txt = [f"HTTP {r.status_code} chaves topo={list(d)} n={len(d.get('conteudo', []))}"]
for item in d.get("conteudo", [])[:3]:
    txt.append(json.dumps(item, ensure_ascii=False))
txt.append("ULTIMO: " + json.dumps(d.get("conteudo", [])[-1], ensure_ascii=False))
open("saida_diag/relatorio.txt", "w").write("\n".join(txt))
print("\n".join(txt))
