# -*- coding: utf-8 -*-
"""DIAG TEMPORARIO v11 (somente leitura, NAO MERGEAR): edicao com o codigo
de PRODUCAO (main) - PDF + texto/HTML do e-mail, sem enviar, sem secrets
(sem Supabase, sem e-mail). Cenario 1: agora real. Cenario 2: simulacao
do horario de segunda 19/10 08:03 BRT (so' datas/rotulos; cotacoes e
noticias sao as disponiveis agora)."""
import io, os, sys, re
from datetime import datetime
sys.path.insert(0, os.getcwd())
os.makedirs("saida_diag", exist_ok=True)
from pypdf import PdfReader
from data import morning_call_editorial as ed
from jobs import morning_call as mc
from jobs import morning_call_pdf as pdf

out = []
def p(*a):
    out.append(" ".join(str(x) for x in a))

for nome, agora in (("agora", datetime.now(ed.TZ_SP)), ("seg0803", datetime(2026, 10, 19, 8, 3, tzinfo=ed.TZ_SP))):
    p(f"\n===== CENARIO {nome}: agora={agora.isoformat()} =====")
    anexo = mc._montar_anexo_pdf(agora)
    if anexo is None:
        p("PDF: FALHOU (enviaria sem anexo)")
        continue
    open(f"saida_diag/{nome}.pdf", "wb").write(anexo["conteudo"])
    leitor = PdfReader(io.BytesIO(anexo["conteudo"]))
    p("PDF:", anexo["nome"], len(anexo["conteudo"]), "bytes,", len(leitor.pages), "paginas")
    capa = leitor.pages[0].extract_text()
    p("capa (primeiras linhas):", " | ".join(capa.splitlines()[:6]))
    texto = mc._com_chamada_radar(mc.montar_morning_call(agora), anexo)
    html = mc.montar_morning_call_html(texto)
    p("assunto:", mc._assunto(agora))
    p("texto e-mail:", len(texto), "chars; html:", len(html), "chars; secoes faltantes:",
      [s for s in mc.SECOES_OBRIGATORIAS if s not in texto])
    open(f"saida_diag/{nome}_email.txt", "w").write(texto)
    for linha in texto.splitlines():
        if re.search(r"Ibovespa|Dólar|Selic|CDI|Focus|última sessão|fim de semana", linha):
            p("  ", linha[:200])

open("saida_diag/relatorio.txt", "w").write("\n".join(out))
print("\n".join(out))
