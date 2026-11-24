# Responsividade (3 breakpoints: desktop 1440 / ipad 1024 / celular 390,
# referencia do projeto) das telas do ESCOPO DA FASE 6 ainda sem evidencia
# fresca pos-paleta nova (PR #326, 2026-11-18) e pos-rollout (#341,
# 2026-11-19): MACRO > Indicadores (fix do eixo Y + camada analitica nova
# do #334), CALENDARIO (achado MENOR pendente da auditoria 2026-11-17:
# rotulo CONFIRMADO/ESTIMADO cortado pela borda da celula) e MERCADO >
# Visao Geral em mobile (nunca testada em 390px com a paleta nova - as
# capturas de responsividade-bloomberg-20261106 sao de ANTES do #326).
# Contra o app REAL (bypass de login, ver sitecustomize.py fora do repo).
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
BASE = "http://127.0.0.1:19500"

ROTAS = [
    ("mercado_visaogeral", "mercado", "visao-geral"),
    ("macro_indicadores", "macro", "indicadores"),
    ("macro_juros", "macro", "juros"),
    ("macro_cambio", "macro", "cambio"),
    ("calendario_corporativo", "calendario", "corporativo"),
    ("calendario_economico", "calendario", "economico"),
]

BREAKPOINTS = [
    ("1440", 1440, 900),
    ("1024", 1024, 1366),
    ("390", 390, 844),
]

resultados = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    for bp_nome, w, h in BREAKPOINTS:
        ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=(bp_nome != "1440"))
        page = ctx.new_page()
        for rota_nome, aba, sub in ROTAS:
            page.goto(f"{BASE}/?aba={aba}&sub={sub}", wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(5000)
            altura_real = page.evaluate(
                "(() => { var m = document.querySelector('[data-testid=\"stMain\"]'); "
                "return m ? m.scrollHeight : document.body.scrollHeight; })()"
            )
            page.set_viewport_size({"width": w, "height": int(altura_real) + 60})
            page.wait_for_timeout(500)
            scroll_w = page.evaluate("document.documentElement.scrollWidth")
            client_w = page.evaluate("document.documentElement.clientWidth")
            overflow = scroll_w > client_w + 2
            page.screenshot(path=str(OUT / f"resp_{rota_nome}_{bp_nome}.png"), full_page=True)
            resultados.append({"rota": rota_nome, "bp": bp_nome, "scrollW": scroll_w, "clientW": client_w, "overflow": overflow})
            page.set_viewport_size({"width": w, "height": h})
            print("ok", rota_nome, bp_nome, "overflow:", overflow)
        ctx.close()
    browser.close()

(OUT / "responsivo_fase6_resultado.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
print("COM OVERFLOW:", [r for r in resultados if r["overflow"]])
