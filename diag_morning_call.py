# -*- coding: utf-8 -*-
"""DIAG TEMPORARIO v8 (somente leitura, NAO MERGEAR): valida o PR A do
Morning Call com dados reais - edicao montada com o codigo do PR A, PDF
gerado e auditoria por regra (OK/FORA). Sem secrets: sem Supabase, sem
e-mail."""
import json, os, re, sys
from datetime import datetime
sys.path.insert(0, os.getcwd())
os.makedirs("saida_diag", exist_ok=True)
from data import morning_call_editorial as ed
from jobs import morning_call_pdf as pdf

agora = datetime.now(ed.TZ_SP)
_coleta = ed._coletar_noticias()
ed._coletar_noticias = lambda: _coleta  # a auditoria ve EXATAMENTE a mesma coleta da edicao
erros, brasil_bruto, empresas_bruto, exterior_bruto = _coleta
edicao = ed.montar_edicao(agora)
registro = {}
open("saida_diag/morning_call_real.pdf", "wb").write(pdf.gerar_pdf(edicao, registro))

out = []
def p(*a):
    out.append(" ".join(str(x) for x in a))

p("agora:", agora.isoformat(), "| erros de coleta:", erros)
p("bruto: brasil", len(brasil_bruto), "empresas", len(empresas_bruto), "exterior", len(exterior_bruto))
p("sessao_mercado:", edicao.get("sessao_mercado"))
p("masthead:", pdf._linha_referencia_masthead(agora, pdf._sessao_da_edicao(edicao)))
p("paginas:", registro.get("total_paginas"))

# descartes do filtro editorial (por regra) - evidencia do que saiu
janela = ed.inicio_janela_noticias(agora)
p("\n== DESCARTADOS PELO FILTRO (dentro da janela) ==")
for item in brasil_bruto + empresas_bruto + exterior_bruto:
    m = ed._data_item(item)
    if m is None or m < janela:
        continue
    t = item.get("titulo")
    if ed._fora_de_pauta(t):
        p("  fora_de_pauta |", t)
    elif not ed.tem_relevancia_financeira(item):
        p("  sem_relevancia |", t)

def fatos(secao, chave):
    return (edicao.get(secao) or {}).get(chave) or []

brutos = {i.get("link"): i for i in brasil_bruto + empresas_bruto + exterior_bruto}
publicados = fatos("brasil", "noticias") + fatos("empresas", "cards") + fatos("exterior", "noticias")
fora = 0
def check(ok, rotulo):
    global fora
    fora += 0 if ok else 1
    p(f"  [{'OK' if ok else 'FORA'}] {rotulo}")

for secao, chave, nome in (("brasil", "noticias", "BRASIL"), ("empresas", "cards", "EMPRESAS"),
                           ("exterior", "noticias", "MUNDO")):
    p(f"\n== {nome} ==")
    for f in fatos(secao, chave):
        t = f["titulo"]
        p(f"- {t} | {f.get('veiculo')} | {pdf._momento_publicacao(f.get('data'), agora)}"
          f"{' | PUBLICADO OUTRO DIA' if f.get('publicado_outro_dia') else ''}")
        regiao = ed.editoria_por_assunto(t, "INT" if nome == "MUNDO" else "BR")
        check(regiao == ("INT" if nome == "MUNDO" else "BR"), "editoria pelo assunto")
        if nome == "EMPRESAS":
            check(ed.e_noticia_de_empresa(t), "empresa/ticker no titulo")
        if nome == "BRASIL":
            check(not ed.e_noticia_de_empresa(t), "nao e noticia de empresa")
        bruto = brutos.get(f.get("link")) or f
        p(f"    veiculos do grupo: {len(bruto.get('veiculos') or [])}")
        check(ed.tem_relevancia_financeira(bruto), "piso de relevancia (item bruto)")
        check(not ed._fora_de_pauta(t), "nao fora de pauta")
        check(bool(pdf._momento_publicacao(f.get("data"), agora)), "linha de fonte com data")

p("\n== CAPA ==")
m = edicao["capa"]["manchete"]
p("manchete:", m and m["titulo"], "| outro dia:", m and m.get("publicado_outro_dia"))

p("\n== RADAR ==")
radar = edicao.get("radar") or {}
links_pub = {f.get("link") for f in publicados if f.get("link")}
titulos_pub = {" ".join(ed._sem_acento(f["titulo"]).lower().split()) for f in publicados}
for s in radar.get("setores") or []:
    p("setor:", s.get("nome") or s.get("setor"))
    for fo in s.get("fontes") or []:
        rep = fo.get("link") in links_pub or " ".join(ed._sem_acento(fo["titulo"]).lower().split()) in titulos_pub
        p("   ", fo["titulo"], "|", fo.get("veiculo"))
        check(not rep, "evidencia nao publicada nas editorias")
for e in radar.get("excluidos") or []:
    p("excluido:", e.get("nome"), "-", e.get("motivo"))

p("\n== MACRO ==")
for l in edicao["brasil"]["indicadores"]:
    if "indicador" in l:
        p(" ", json.dumps({k: l.get(k) for k in ("indicador", "valor", "referencia", "erro")},
                          ensure_ascii=False, default=str))

p("\nTOTAL FORA:", fora)
open("saida_diag/relatorio.txt", "w").write("\n".join(out))
print("\n".join(out))
