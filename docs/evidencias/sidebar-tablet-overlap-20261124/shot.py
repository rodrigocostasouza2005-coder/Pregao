# Screenshot generico (padrao ja usado em outras pastas de evidencia, ex.
# docs/evidencias/validacao-visual-real-20261117/shot.py): porta, largura,
# altura, touch, caminho de saida.
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

porta = sys.argv[1]
largura = int(sys.argv[2])
altura = int(sys.argv[3]) if len(sys.argv) > 4 else 900
saida = sys.argv[4] if len(sys.argv) > 4 else sys.argv[3]
touch = "--touch" in sys.argv

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": largura, "height": altura}, has_touch=touch, is_mobile=False)
    page = ctx.new_page()
    page.goto(f"http://127.0.0.1:{porta}", wait_until="networkidle")
    page.wait_for_selector("#conteudo-principal-teste", timeout=10000)
    page.wait_for_timeout(500)
    page.screenshot(path=saida, full_page=False)
    ctx.close()
    browser.close()
print("ok", saida)
