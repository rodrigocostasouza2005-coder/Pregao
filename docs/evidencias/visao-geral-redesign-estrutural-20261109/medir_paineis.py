"""Mede a altura real (px) de cada painel bordered da VISAO GERAL atual,
via Playwright contra o harness_home.py ja existente (dados mockados
realistas). Objetivo: fundamentar o reagrupamento de colunas em altura
MEDIDA, nao em proporcao chutada."""
import json
import sys

from playwright.sync_api import sync_playwright

PORT = sys.argv[1] if len(sys.argv) > 1 else "18991"
WIDTH = int(sys.argv[2]) if len(sys.argv) > 2 else 1440

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": WIDTH, "height": 1200})
    page.goto(f"http://127.0.0.1:{PORT}", wait_until="networkidle")
    page.wait_for_timeout(3000)

    titulos = page.evaluate("""
    () => {
        const nodes = document.querySelectorAll('.painel-titulo');
        const out = [];
        for (const n of nodes) {
            let el = n;
            while (el && el.getAttribute('data-testid') !== 'stLayoutWrapper') {
                el = el.parentElement;
            }
            if (!el) continue;
            const rect = el.getBoundingClientRect();
            out.push({titulo: n.textContent.trim(), altura: Math.round(rect.height), largura: Math.round(rect.width)});
        }
        return out;
    }
    """)
    print(json.dumps(titulos, ensure_ascii=False, indent=2))
    browser.close()
