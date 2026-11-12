import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
BREAKPOINTS = {"desktop-1440": 1440, "ipad-1024": 1024, "ipad-820": 820}
PAGES = {
    "nav": 8781,
    "busca_paineis": 8782,
    "top_mercado": 8783,
    "workspace": 8784,
    "sidebar_watchlist": 8785,
    "radar": 8786,
}

erros = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    for nome, porta in PAGES.items():
        for bp_nome, largura in BREAKPOINTS.items():
            page = browser.new_page(viewport={"width": largura, "height": 1000})
            page.goto(f"http://127.0.0.1:{porta}", wait_until="networkidle", timeout=30000)
            time.sleep(5.5)
            caixa_erro = page.locator('[data-testid="stException"], [data-testid="stAlert"][kind="error"]')
            n_erro = caixa_erro.count()
            if n_erro:
                erros.append(f"{nome}@{bp_nome}: {n_erro} caixa(s) de erro/exception na tela")
            page.screenshot(path=str(OUT / f"{nome}_{bp_nome}.png"), full_page=True)
            page.close()
    browser.close()

print("ERROS:" if erros else "SEM ERROS DETECTADOS")
for e in erros:
    print(" -", e)
