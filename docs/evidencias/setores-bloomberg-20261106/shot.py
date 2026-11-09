import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PORT = sys.argv[1] if len(sys.argv) > 1 else "8771"
OUT = sys.argv[2] if len(sys.argv) > 2 else "harness_screenshot.png"
OUT = Path(__file__).parent / OUT

with sync_playwright() as p:
    # --headless=old: o modo "new headless" padrao do Chromium bundlado
    # (versao 156) produz screenshot TOTALMENTE PRETO nesta maquina pra
    # paginas Streamlit completas (bug real confirmado aqui: o DOM/texto
    # renderiza certo - innerText nao vazio - mas o screenshot (full-page
    # OU elemento OU viewport) sai preto solido; o modo headless antigo
    # nao tem esse problema, mesma pagina). Builds com pouco DOM (teste
    # sanity com 1 <h1>) nao reproduziam - so' paginas Streamlit reais.
    browser = p.chromium.launch(args=["--headless=old"])
    page = browser.new_page(viewport={"width": 1440, "height": 1600})
    page.goto(f"http://127.0.0.1:{PORT}", wait_until="networkidle")
    time.sleep(2.5)
    texto = page.inner_text("body")
    page.screenshot(path=str(OUT), full_page=True)
    browser.close()
print("saved", OUT)
if "Oh no" in texto or "Traceback" in texto or "Error" in texto:
    print("POSSIVEL ERRO NA PAGINA - revisar texto abaixo")
    print(texto[:3000])
