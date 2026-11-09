import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PORTA = sys.argv[1] if len(sys.argv) > 1 else "8766"
NOME = sys.argv[2] if len(sys.argv) > 2 else "harness_screenshot"
OUT = Path(__file__).parent / f"{NOME}.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1600})
    page.goto(f"http://127.0.0.1:{PORTA}", wait_until="networkidle")
    time.sleep(4)
    page.screenshot(path=str(OUT), full_page=True)
    browser.close()
print("saved", OUT)
