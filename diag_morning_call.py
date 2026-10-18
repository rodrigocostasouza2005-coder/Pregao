# -*- coding: utf-8 -*-
"""DIAGNOSTICO TEMPORARIO v4 (radar setorial) (somente leitura, NAO MERGEAR): gera a
edicao REAL do Morning Call com o codigo da branch de auditoria. Sem
secrets: sem Supabase (zero escrita), sem e-mail, sem Groq."""
import json, os, sys, threading, traceback
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, os.getcwd())
TZ = ZoneInfo("America/Sao_Paulo")
os.makedirs("saida_diag", exist_ok=True)
log = open("saida_diag/relatorio.txt", "w")
def p(*a):
    t = " ".join(str(x) for x in a); print(t, flush=True); log.write(t + "\n"); log.flush()
p("AGORA", datetime.now(TZ).isoformat(), "SUPABASE?", bool(os.getenv("SUPABASE_URL")))

import data.morning_call_editorial as ed
from data import macro
# agenda real com limite de tempo (sem Supabase recalcula ao vivo, so leitura)
_agenda_real = ed._agenda_hoje
def _agenda_com_limite(agora):
    res = {}
    th = threading.Thread(target=lambda: res.setdefault("v", _agenda_real(agora)), daemon=True)
    th.start(); th.join(420)
    if "v" not in res:
        p("AGENDA: excedeu 420s -> None (indisponivel nesta execucao)")
        return None
    return res["v"]
ed._agenda_hoje = _agenda_com_limite

# noticias brutas antes do filtro, para auditar o que saiu e por que
erros, br, emp, intl = ed._coletar_noticias()
p("erros noticias", erros, "| BR", len(br), "EMP", len(emp), "INT", len(intl))
agora = datetime.now(TZ)
p("janela desde", ed.inicio_janela_noticias(agora))
mantidos = {id(i) for i in ed.filtrar_noticias(br + emp, agora)} | {id(i) for i in ed.filtrar_noticias(intl, agora)}
for nome, lista in (("BR", br), ("EMP", emp), ("INT", intl)):
    for i in sorted(lista, key=lambda x: -(x.get("importancia") or 0))[:25]:
        p(f"  [{nome}] {'OK ' if id(i) in mantidos else 'FORA'} imp={i.get('importancia')} {i.get('data')} {i.get('titulo')[:110]} | {i.get('veiculos')}")

edicao = ed.montar_edicao(agora)
for chave in ("brasil", "exterior"):
    for ind in (edicao[chave].get("indicadores") or []):
        p(chave, json.dumps(ind, ensure_ascii=False, default=str)[:400])
p("mercados_nota:", edicao.get("mercados_nota"))
p("motivos SGS:", macro.motivo_indisponivel("selic"), "|", macro.motivo_indisponivel("cdi"))
p("manchete:", (edicao["capa"]["manchete"] or {}).get("titulo"))
for chave, campo in (("brasil", "noticias"), ("exterior", "noticias"), ("empresas", "cards")):
    itens = edicao[chave].get(campo) or []
    p(f"{chave}: {len(itens)}")
    for i in itens:
        p(f"   - {i.get('data')} {i.get('veiculo')} | {i.get('titulo')[:110]} | corpo={len(i.get('corpo') or [])} | {i.get('link')}")
p("agenda:", json.dumps(edicao["empresas"].get("agenda"), ensure_ascii=False, default=str)[:1500])

radar = edicao.get("radar")
p("\n===== RADAR SETORIAL =====")
if radar is None:
    p("radar None")
else:
    p("plano do dia:", radar.get("plano"))
    p("historico (plano recalculado):", radar.get("historico"))
    for b in radar.get("setores") or []:
        p(f"\n## {b['nome']} ({b['setor']}) - {b['palavras']} palavras")
        p("O que aconteceu:"); [p("  ", f) for f in b["o_que_aconteceu"]]
        p("Por que importa:", b["por_que_importa"])
        p("Empresas e ativos relacionados:", b["empresas"])
        p("O que acompanhar:", b["acompanhar"])
        p("Fontes:")
        for f in b["fontes"]:
            p(f"   - {f['titulo']} | {f['veiculo']} | {f['data'].isoformat()} | {f['link']}")
    for e in radar.get("excluidos") or []:
        p("EXCLUIDO:", e)
json.dump(radar, open("saida_diag/radar.json", "w"), ensure_ascii=False, indent=1, default=str)

from jobs.morning_call_pdf import gerar_pdf
try:
    open("saida_diag/morning_call_real.pdf", "wb").write(gerar_pdf(edicao))
    p("PDF ok")
except Exception:
    p("PDF EXC", traceback.format_exc())
# rerun 1792338988
# rerun v4.1
# rerun v4.2
# rerun v4.3
# rerun v4.4
