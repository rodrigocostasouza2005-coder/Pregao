"""Auditoria de toque real (Playwright, has_touch=True) em RADAR > Alertas e
RADAR > Carteiras Recomendadas - harness_radar.py precisa estar rodando em
http://127.0.0.1:8777 (streamlit run ... --server.port=8777)."""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
BASE = "http://127.0.0.1:8777"

IPAD = {"width": 1024, "height": 1366}

resultados = {}


def tap_report(page, locator, label):
    """Tenta tocar (dispatchar tap real via touchscreen) num elemento e
    reporta se um evento click chegou nele - sem isso nao sabemos se o
    toque "pegou" ou se outra coisa (overlay/hover-trap) engoliu o evento."""
    el = locator.first
    if el.count() == 0:
        return {"label": label, "achou": False}
    box = el.bounding_box()
    if box is None:
        return {"label": label, "achou": True, "visivel": False}
    marca = f"__tap_marker_{abs(hash(label)) % 100000}"
    # instrumenta um listener de click no PROPRIO elemento (via element
    # handle, sem depender de selector CSS valido pro document.querySelector)
    el.evaluate(
        f"""(node, marca) => {{
            window.__cliques = window.__cliques || [];
            node.addEventListener('click', () => {{ window.__cliques.push(marca); }}, true);
        }}""",
        marca,
    )
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    elemento_no_ponto = page.evaluate(
        "(pt) => { const e = document.elementFromPoint(pt.x, pt.y); return e ? e.outerHTML.slice(0,200) : null; }",
        {"x": cx, "y": cy},
    )
    page.touchscreen.tap(cx, cy)
    page.wait_for_timeout(400)
    cliques = page.evaluate("window.__cliques || []")
    return {
        "label": label, "achou": True, "visivel": True, "box": box,
        "elemento_no_ponto_do_toque": elemento_no_ponto,
        "clique_registrado": marca in cliques,
    }


with sync_playwright() as p:
    browser = p.chromium.launch()

    # ---- 1. screenshots nos 3 breakpoints (desktop/iPad/celular) ----------
    for nome, viewport in [("desktop-1440", {"width": 1440, "height": 900}),
                            ("ipad-1024", IPAD),
                            ("celular-390", {"width": 390, "height": 844})]:
        ctx = browser.new_context(viewport=viewport, has_touch=(nome != "desktop-1440"))
        page = ctx.new_page()
        for secao in ["alertas", "carteiras"]:
            page.goto(f"{BASE}/?secao={secao}", wait_until="networkidle")
            time.sleep(1.5)
            page.screenshot(path=str(OUT / f"{secao}_{nome}.png"), full_page=True)
        ctx.close()

    # ---- 2. auditoria de toque real no iPad (has_touch=True) --------------
    ctx = browser.new_context(viewport=IPAD, has_touch=True, is_mobile=False)
    page = ctx.new_page()

    # --- ALERTAS: pills de periodo, selectbox de casa, link de ticker, botao
    page.goto(f"{BASE}/?secao=alertas", wait_until="networkidle")
    time.sleep(1.5)
    resultados["alertas_pill_7dias"] = tap_report(
        page, page.locator("[data-testid='stButtonGroup'] button", has_text="7 DIAS"), "pill 7 dias"
    )
    resultados["alertas_pill_30dias_antes"] = page.locator(
        "[data-testid='stButtonGroup'] button[aria-checked='true']"
    ).inner_text() if page.locator("[data-testid='stButtonGroup'] button[aria-checked='true']").count() else None
    el = page.locator("[data-testid='stButtonGroup'] button", has_text="30 DIAS").first
    if el.count():
        box = el.bounding_box()
        page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_selector("[data-testid='stButtonGroup'] button[aria-checked='true']", timeout=5000)
        page.wait_for_timeout(600)
        resultados["alertas_pill_30dias_depois"] = page.locator(
            "[data-testid='stButtonGroup'] button[aria-checked='true']"
        ).inner_text()
    page.wait_for_selector("a.rq-ticker", timeout=5000)
    resultados["alertas_link_ticker"] = tap_report(page, page.locator("a.rq-ticker"), "link ticker PETR4")

    # --- CARTEIRAS: selectbox nativo pra escolher carteira, link de ticker
    page.goto(f"{BASE}/?secao=carteiras", wait_until="networkidle")
    page.wait_for_selector("a.rq-ticker", timeout=8000)
    time.sleep(0.5)
    resultados["carteiras_link_ticker"] = tap_report(page, page.locator("a.rq-ticker"), "link ticker na composicao")
    sel = page.locator("[data-testid='stSelectbox']").first
    if sel.count():
        box = sel.bounding_box()
        page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        time.sleep(0.6)
        aberto = page.locator("[role='listbox']").count() > 0
        resultados["carteiras_selectbox_abre_por_toque"] = aberto
        if aberto:
            opcao = page.locator("[role='option']").first
            obox = opcao.bounding_box()
            page.touchscreen.tap(obox["x"] + obox["width"] / 2, obox["y"] + obox["height"] / 2)
            time.sleep(0.8)
            resultados["carteiras_selectbox_valor_apos_toque"] = sel.inner_text()

    page.screenshot(path=str(OUT / "touch_ipad_alertas_final.png"), full_page=True)
    ctx.close()
    browser.close()

(OUT / "touch_audit_resultado.json").write_text(json.dumps(resultados, indent=2, default=str, ensure_ascii=False))
print(json.dumps(resultados, indent=2, default=str, ensure_ascii=False))
