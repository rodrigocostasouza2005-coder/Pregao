"""Auditoria rapida de overflow horizontal nas abas recem-reformuladas
(Bloomberg), 3 breakpoints (desktop 1440 / iPad 1024 / celular 390) -
contra o app REAL (bypass de login, ver _local_bypass/sitecustomize.py,
fora do repo) rodando em http://127.0.0.1:8778. Critério objetivo:
document.documentElement.scrollWidth > viewport width = algo estourou a
largura da tela (overflow-x real, nao so' suspeita visual)."""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
BASE = "http://127.0.0.1:8778"

ROTAS = [
    ("mercado-visaogeral", "mercado", "visao-geral"),
    ("mercado-painel", "mercado", "painel"),
    ("watchlist", "mais", "watchlist"),
    ("research-feed", "research", "feed"),
    ("research-casas", "research", "casas"),
    ("coordenador-visaogeral", "coordenador", "visao-geral"),
    ("analises-empresas", "analises", "empresas"),
    ("analises-valuation", "analises", "valuation"),
    ("radar-alertas", "radar", "alertas"),
    ("radar-carteiras", "radar", "carteiras"),
    ("noticias-destaques", "noticias", "destaques"),
    ("morningcall-edicao", "morning-call", "edicao"),
]

BREAKPOINTS = [
    ("desktop-1440", {"width": 1440, "height": 900}, False),
    ("ipad-1024", {"width": 1024, "height": 1366}, True),
    ("celular-390", {"width": 390, "height": 844}, True),
]

resultados = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    for bp_nome, viewport, touch in BREAKPOINTS:
        ctx = browser.new_context(viewport=viewport, has_touch=touch)
        page = ctx.new_page()
        for rota_nome, aba, sub in ROTAS:
            page.goto(f"{BASE}/?aba={aba}&sub={sub}", wait_until="networkidle")
            page.wait_for_timeout(1800)
            scroll_w = page.evaluate("document.documentElement.scrollWidth")
            client_w = page.evaluate("document.documentElement.clientWidth")
            overflow = scroll_w > client_w + 2  # folga de 2px (subpixel/scrollbar)
            item = {
                "rota": rota_nome, "breakpoint": bp_nome,
                "scrollWidth": scroll_w, "clientWidth": client_w, "overflow": overflow,
            }
            resultados.append(item)
            if overflow:
                page.screenshot(path=str(OUT / f"OVERFLOW_{rota_nome}_{bp_nome}.png"), full_page=True)
        ctx.close()
    browser.close()

(OUT / "overflow_audit_resultado.json").write_text(
    json.dumps(resultados, indent=2, ensure_ascii=False)
)
com_overflow = [r for r in resultados if r["overflow"]]
print(f"TOTAL testado: {len(resultados)} | COM OVERFLOW: {len(com_overflow)}")
for r in com_overflow:
    print(r)
