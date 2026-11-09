import sys
import time

from playwright.sync_api import sync_playwright

PORT = sys.argv[1] if len(sys.argv) > 1 else "18992"
WIDTH = int(sys.argv[2]) if len(sys.argv) > 2 else 1440
OUT = sys.argv[3] if len(sys.argv) > 3 else "docs/evidencias/visao-geral-redesign-estrutural-20261109/novo.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": WIDTH, "height": 900})
    page.goto(f"http://127.0.0.1:{PORT}", wait_until="networkidle")
    time.sleep(3)
    page.wait_for_timeout(2000)
    altura_real = page.evaluate(
        "document.querySelector('[data-testid=\"stMain\"]').scrollHeight"
    )
    page.set_viewport_size({"width": WIDTH, "height": int(altura_real) + 60})
    page.wait_for_timeout(1500)
    page.screenshot(path=OUT, full_page=True)
    browser.close()
print("saved", OUT)
