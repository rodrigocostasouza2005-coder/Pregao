# Variante do shot.py que clica "TESTAR TODAS AS FONTES" antes do
# screenshot - valida visualmente a tabela de ui/design_system.py:
# numero_financeiro_html aplicada as colunas TEMPO/TAMANHO (app.py,
# dentro do bloco "mais"/"config", painel DIAGNOSTICO DE FONTES).
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "harness_config_diagnostico.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1700})
    page.goto("http://127.0.0.1:18993", wait_until="networkidle")
    time.sleep(3)
    page.get_by_text("TESTAR TODAS AS FONTES", exact=True).click()
    time.sleep(2)
    page.screenshot(path=str(OUT), full_page=True)
    browser.close()
print("saved", OUT)
