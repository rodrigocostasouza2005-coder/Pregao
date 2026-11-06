import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "harness_screenshot.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 1400})
    page.goto("http://127.0.0.1:8765", wait_until="networkidle")
    time.sleep(2)
    page.screenshot(path=str(OUT), full_page=True)
    browser.close()
print("saved", OUT)
