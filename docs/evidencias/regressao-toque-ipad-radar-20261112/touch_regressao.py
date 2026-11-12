# Regressao do bug de toque em iPad corrigido no PR #270 (commit cbe0d8d):
# sidebar WATCHLIST auto-aberta (initial_sidebar_state="auto") cobria, em
# overlay, as 2 primeiras subabas da subnav (ex: RADAR > Alertas/Carteiras
# Recomendadas) num viewport de iPad. Precisa de harness_nav_sidebar.py
# rodando em http://127.0.0.1:8778 (streamlit run ... --server.port=8778).
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
BASE = "http://127.0.0.1:8778"
IPAD = {"width": 1024, "height": 1366}

resultados = {}

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport=IPAD, has_touch=True, is_mobile=False)
    page = ctx.new_page()
    page.goto(f"{BASE}/?aba=radar&sub=alertas", wait_until="networkidle")
    page.wait_for_selector("text=Alertas", timeout=10000)
    page.wait_for_timeout(500)

    # confere que a sidebar esta' realmente aberta (auto, viewport >= breakpoint)
    sidebar = page.locator("section[data-testid='stSidebar']")
    resultados["sidebar_visivel"] = sidebar.is_visible() if sidebar.count() else False

    # localiza o botao "Carteiras Recomendadas" dentro da subnav (nav_sub) -
    # e' a 2a subaba, a que o bug original cobria (junto com Alertas, a 1a,
    # que ja' esta ativa por padrao via query param)
    botao = page.locator(
        "[data-testid='stButtonGroup'] button", has_text="Carteiras"
    ).first
    resultados["botao_achado"] = botao.count() > 0
    resultados["debug_botoes_group"] = page.locator("[data-testid='stButtonGroup'] button").count()
    if botao.count():
        box = botao.bounding_box()
        resultados["box"] = box
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        elemento_no_ponto = page.evaluate(
            "(pt) => { const e = document.elementFromPoint(pt.x, pt.y); "
            "return e ? {tag: e.tagName, texto: (e.textContent||'').slice(0,60), "
            "classe: e.className} : null; }",
            {"x": cx, "y": cy},
        )
        resultados["elemento_no_ponto_do_toque"] = elemento_no_ponto
        page.touchscreen.tap(cx, cy)
        page.wait_for_timeout(600)
        resultados["url_apos_toque"] = page.url
        resultados["mudou_para_carteiras"] = "sub=carteiras" in page.url

    page.screenshot(path=str(OUT / "apos_toque_ipad_hoje.png"), full_page=True)
    ctx.close()
    browser.close()

(OUT / "touch_regressao_resultado.json").write_text(
    json.dumps(resultados, indent=2, default=str, ensure_ascii=False)
)
print(json.dumps(resultados, indent=2, default=str, ensure_ascii=False))

ok = resultados.get("mudou_para_carteiras") is True
print("\nREGRESSAO:", "OK (toque chegou no botao real, sem bug)" if ok else "FALHOU (toque nao mudou de aba - bug pode ter voltado)")
sys.exit(0 if ok else 1)
