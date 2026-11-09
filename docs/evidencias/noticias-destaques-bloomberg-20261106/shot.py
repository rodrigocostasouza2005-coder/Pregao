import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).parent
PORT = sys.argv[1] if len(sys.argv) > 1 else "8799"

REGIOES = {
    "destaques": "TUDO",
    "brasil": "BRASIL",
    "internacional": "INTERNACIONAL",
}

with sync_playwright() as p:
    browser = p.chromium.launch()
    for nome, regiao in REGIOES.items():
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(f"http://127.0.0.1:{PORT}/?regiao={regiao}", wait_until="networkidle")
        time.sleep(3)
        page.wait_for_selector(".w-divider", timeout=15000)
        time.sleep(5)
        out = OUT_DIR / f"desktop_{nome}.png"
        page.screenshot(path=str(out), full_page=True)
        print("saved", out)
        page.close()
    browser.close()
