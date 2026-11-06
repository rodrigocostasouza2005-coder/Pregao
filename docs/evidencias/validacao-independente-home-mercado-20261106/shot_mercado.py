import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "mercado_full.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://127.0.0.1:8767", wait_until="networkidle")
    time.sleep(3)
    page.wait_for_timeout(2000)
    altura_real = page.evaluate(
        "document.querySelector('[data-testid=\"stMain\"]').scrollHeight"
    )
    page.set_viewport_size({"width": 1440, "height": int(altura_real) + 60})
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT), full_page=True)
print("saved", OUT)
