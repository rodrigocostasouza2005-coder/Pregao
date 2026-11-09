import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

port = sys.argv[1]
out_name = sys.argv[2]
OUT = Path(__file__).parent / out_name

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1600})
    page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
    time.sleep(2)
    page.screenshot(path=str(OUT), full_page=True)
    browser.close()
print("saved", OUT)
