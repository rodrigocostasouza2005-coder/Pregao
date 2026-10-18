# -*- coding: utf-8 -*-
"""DIAG TEMPORARIO v7 (somente leitura, NAO MERGEAR): tabela macro real
com o codigo da branch de pendencias (plano B da Selic pelo Copom)."""
import json, os, sys
sys.path.insert(0, os.getcwd())
os.makedirs("saida_diag", exist_ok=True)
from data import morning_call_editorial as ed
linhas = ed._macro_rows()
txt = [json.dumps(l, ensure_ascii=False, default=str) for l in linhas]
open("saida_diag/relatorio.txt", "w").write("\n".join(txt))
print("\n".join(txt))
