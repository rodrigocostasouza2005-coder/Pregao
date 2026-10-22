# -*- coding: utf-8 -*-
"""Prévia TEMPORÁRIA do Morning Call com dados PÚBLICOS (22/10/2026), rodada
no runner do GitHub Actions sem nenhum secret (sem Supabase, sem IA, sem
e-mail). NUNCA envia nada: monta edição/PDF/texto a partir de cotações,
BCB, CVM e Google News e imprime no log (PDF em base64 para inspeção)."""
import base64
from datetime import datetime
from zoneinfo import ZoneInfo

from data.morning_call_editorial import montar_edicao
from jobs.morning_call import _resumo_edicao, montar_morning_call
from jobs.morning_call_pdf import gerar_pdf

agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
edicao = montar_edicao(agora)
pdf = gerar_pdf(edicao)
print("EDICAO:", _resumo_edicao(edicao, pdf))
capa = edicao.get("capa") or {}
for rotulo, item in [("MANCHETE", capa.get("manchete"))] + [("CHAMADA", c) for c in capa.get("chamadas") or []]:
    if item:
        print(f"  {rotulo}: {item.get('veiculo')} | confiavel={item.get('fonte_confiavel')} | {item.get('titulo')}")
print("AGENDA_PROXIMOS:", [(e.get("ticker"), str(e.get("data")), e.get("status_rotulo")) for e in (edicao.get("empresas") or {}).get("agenda_proximos") or []])
print("TEXTO_INICIO")
print(montar_morning_call(agora))
print("TEXTO_FIM")
print("PDF_B64_INICIO")
print(base64.b64encode(pdf).decode())
print("PDF_B64_FIM")
