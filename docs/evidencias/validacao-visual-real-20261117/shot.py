# Screenshot generico (sem depender de nenhuma classe CSS especifica, pra
# funcionar tanto no harness "ANTES" (sem design system, sem painel-titulo)
# quanto no "DEPOIS") - mede a altura real do container interno do
# Streamlit (stMain, overflow-y propio) e reabre com viewport alto o
# bastante pra full_page=True capturar tudo.
import sys

from playwright.sync_api import sync_playwright

PORT = sys.argv[1] if len(sys.argv) > 1 else "18961"
WIDTH = int(sys.argv[2]) if len(sys.argv) > 2 else 1440
OUT = sys.argv[3] if len(sys.argv) > 3 else "out.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": WIDTH, "height": 900})
    page.goto(f"http://127.0.0.1:{PORT}", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(8000)
    altura_real = page.evaluate(
        "document.querySelector('[data-testid=\"stMain\"]') ? "
        "document.querySelector('[data-testid=\"stMain\"]').scrollHeight : document.body.scrollHeight"
    )
    page.set_viewport_size({"width": WIDTH, "height": int(altura_real) + 60})
    page.wait_for_timeout(1000)
    page.screenshot(path=OUT, full_page=True)
    browser.close()
print("saved", OUT)
