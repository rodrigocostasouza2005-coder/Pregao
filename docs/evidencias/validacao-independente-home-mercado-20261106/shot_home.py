import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "home_full.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://127.0.0.1:8765", wait_until="networkidle")
    time.sleep(3)
    page.wait_for_timeout(2000)
    # Streamlit 1.64 usa um container interno (section[data-testid="stMain"],
    # altura 100vh) com overflow-y:auto PROPRIO - full_page=True do Playwright
    # nao enxerga esse scroll interno (so' o scroll do documento/html, que
    # fica preso ao viewport). Mede o scrollHeight real do container e
    # reabre a pagina com um viewport alto o bastante pra o 100vh cobrir
    # tudo sem precisar de overflow - essa' e' a forma confiavel de pegar
    # "pagina inteira" aqui (full_page=True sozinho cortava a captura em
    # 900px, escondendo tudo abaixo do GRAFICO/PARA INVESTIGAR).
    altura_real = page.evaluate(
        "document.querySelector('[data-testid=\"stMain\"]').scrollHeight"
    )
    page.set_viewport_size({"width": 1440, "height": int(altura_real) + 60})
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT), full_page=True)
    browser.close()
print("saved", OUT)
