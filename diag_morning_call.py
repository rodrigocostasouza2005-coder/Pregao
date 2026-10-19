# -*- coding: utf-8 -*-
"""DIAG TEMPORARIO v13 (somente leitura, NAO MERGEAR): edicao REAL com o
codigo do PR #81 (701ac42) - PDF completo + texto do e-mail + auditoria
editorial. Sem secrets (sem Supabase/resumos, sem e-mail)."""
import io, os, re, sys
from datetime import datetime
sys.path.insert(0, os.getcwd())
os.makedirs("saida_diag", exist_ok=True)
from pypdf import PdfReader
from data import morning_call_editorial as ed
from jobs import morning_call as mc
from jobs import morning_call_pdf as pdf

agora = datetime.now(ed.TZ_SP)
_coleta = ed._coletar_noticias()
ed._coletar_noticias = lambda: _coleta
erros, br, emp, ext = _coleta
edicao = ed.montar_edicao(agora)
registro = {}
conteudo = pdf.gerar_pdf(edicao, registro)
open("saida_diag/morning_call_real.pdf", "wb").write(conteudo)
leitor = PdfReader(io.BytesIO(conteudo))
texto_pdf = "\n".join(p.extract_text() for p in leitor.pages)
email = mc.montar_morning_call(agora)
open("saida_diag/email.txt", "w").write(email)

out = []
p = lambda *a: out.append(" ".join(str(x) for x in a))
p("agora:", agora.isoformat(), "| erros coleta:", erros, "| paginas:", len(leitor.pages), registro.get("total_paginas"))
p("masthead:", pdf._linha_referencia_masthead(agora, pdf._sessao_da_edicao(edicao)))
p("resumos:", edicao.get("resumos"), "| nota:", pdf._nota_sem_resumo(edicao))
janela = ed.inicio_janela_noticias(agora)
p("\n== DESCARTADOS (na janela) ==")
for item in br + emp + ext:
    m = ed._data_item(item)
    if m is None or m < janela:
        continue
    t = item.get("titulo")
    if ed.e_opiniao(t):
        p("  opiniao |", t)
    elif ed._fora_de_pauta(t):
        p("  fora_de_pauta |", t)
    elif not ed.tem_relevancia_financeira(item):
        p("  sem_relevancia |", t)
for secao, campo, nome in (("brasil", "noticias", "BRASIL"), ("empresas", "cards", "EMPRESAS"), ("exterior", "noticias", "MUNDO")):
    p(f"\n== {nome} ==")
    for f in (edicao.get(secao) or {}).get(campo) or []:
        p(f"- {f['titulo']} | {f.get('veiculo')} | {pdf._momento_publicacao(f.get('data'), agora)}"
          + (" | OUTRO DIA" if f.get("publicado_outro_dia") else ""))
m = edicao["capa"]["manchete"]
p("\nmanchete:", m and m["titulo"])
p("chamadas:", [c["titulo"][:60] for c in edicao["capa"]["chamadas"]])
p("\n== MACRO ==")
for l in edicao["brasil"]["indicadores"]:
    if "indicador" in l:
        p(" ", l["indicador"], l.get("valor"), l.get("referencia"), "|", l.get("erro"))
p("\n== ATIVOS ==")
for l in edicao["brasil"]["indicadores"][:2] + edicao["exterior"]["indicadores"]:
    p(" ", l.get("nome"), l.get("preco"), l.get("variacao_pct"), l.get("barra_fmt"))
p("\n== VARREDURA DE TEXTO TECNICO NO PDF E NO E-MAIL ==")
for proibido in ("HTTPSConnectionPool", "timed out", "timeout", "Traceback", "Exception", "Error(", "api.bcb.gov.br", "port=443"):
    p(f"  {proibido!r}: pdf={proibido in texto_pdf} email={proibido in email}")
p("  'Edição das 8h' no PDF:", "Edição das 8h" in texto_pdf)
p("\n== REPETICAO CAPA x PAG.2 ==")
capa = leitor.pages[0].extract_text().replace("\n", " ")
resto = " ".join(pg.extract_text() for pg in leitor.pages[1:]).replace("\n", " ")
for c in edicao["capa"]["chamadas"] + ([m] if m else []):
    k = c["titulo"][:45]
    if k in capa:
        p(f"  capa={'s'} pag2+={'SIM' if k in resto else 'nao'} corpo={bool(c.get('corpo'))} | {c['titulo'][:70]}")
open("saida_diag/relatorio.txt", "w").write("\n".join(out))
print("\n".join(out))
