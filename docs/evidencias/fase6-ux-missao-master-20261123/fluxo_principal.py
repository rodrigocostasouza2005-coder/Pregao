# Walkthrough do FLUXO PRINCIPAL (pedido explicito da missao Fase 6):
# ver mercado -> achar empresa -> fundamentos -> noticias -> research ->
# comite -> cenarios -> valuation -> risco -> tese. Contra o APP REAL
# (app.py, nao harness isolado) com bypass de login (ver sitecustomize.py,
# fora do repo) rodando em http://127.0.0.1:19500. Sem Supabase real
# (banco_ok=False esperado) - prefs default (config.PREFS_PADRAO, watchlist
# TICKERS_PADRAO) valem so' pra esta sessao. Dados de mercado podem bater
# em yfinance real (sem mock) - instabilidade de rede e' possivel e nao
# e' bug de produto se acontecer (mesma ressalva ja documentada no
# projeto).
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
BASE = "http://127.0.0.1:19500"

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))

    def passo(nome, aba, sub, espera=6000):
        page.goto(f"{BASE}/?aba={aba}&sub={sub}", wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(espera)
        # mesma tecnica de shot.py (evidencias 2026-11-17): stMain tem
        # overflow proprio - full_page=True sem isso so' captura o viewport.
        altura_real = page.evaluate(
            "(() => { var m = document.querySelector('[data-testid=\"stMain\"]'); "
            "return m ? m.scrollHeight : document.body.scrollHeight; })()"
        )
        page.set_viewport_size({"width": 1440, "height": int(altura_real) + 60})
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / f"fluxo_{nome}.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 900})
        print("capturado", nome, "altura", altura_real)

    # 1. ver o que acontece no mercado
    passo("01_mercado_visaogeral", "mercado", "visao-geral")
    # 2. achar uma empresa (ANALISES > Empresas, ticker default da watchlist)
    passo("02_analises_empresas", "analises", "empresas")
    # 3. entender fundamentos
    passo("03_analises_fundamentos", "analises", "fundamentos")
    # 3b. perfil da empresa (riscos/catalisadores/cenarios - extraido na missao de hoje)
    passo("03b_analises_perfil", "analises", "perfil")
    # 4. ver noticias relevantes
    passo("04_noticias_empresas", "noticias", "empresas")
    # 5. consultar Research
    passo("05_research_feed", "research", "feed")
    passo("05b_research_casas", "research", "casas")
    # 6. executar o Comite
    passo("06_comite_visaogeral", "comite", "visao-geral")
    # 7. entender cenarios + 8. valuation
    passo("07_valuation_simulador", "valuation", "simulador")
    passo("08_valuation_parecer", "valuation", "parecer", espera=6000)
    # 9. risco (perfil da empresa cobre riscos/invalidacao - ja capturado no 03b)
    # 10. acompanhar a tese
    passo("10_research_teses", "research", "teses")

    ctx.close()
    browser.close()

(OUT / "fluxo_console_erros.json").write_text(
    json.dumps(console_errors, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(f"TOTAL console/page errors: {len(console_errors)}")
for e in console_errors[:50]:
    print("ERR:", e)
