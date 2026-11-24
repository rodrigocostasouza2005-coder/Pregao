# Medicao real (Playwright/Chromium, nao suposicao) do achado registrado em
# docs/evidencias/fase6-ux-missao-master-20261123/LEIA.md: sidebar sobrepoe
# conteudo em telas touch ~1024px. Precisa de harness_sidebar_overlap.py
# rodando em http://127.0.0.1:<porta> (streamlit run ... --server.port=<porta>).
#
# Mede, pra cada largura e cada capacidade de input (touch vs mouse):
# - aria-expanded da sidebar (aberta/fechada no load, decisao do
#   initial_sidebar_state="auto")
# - position computada da sidebar (fixed = overlay, static/relative = empurra
#   o layout)
# - bounding box da sidebar e do marcador de conteudo principal
#   (#conteudo-principal-teste)
# - overlap real (interseccao das 2 bounding boxes) em px e % da area do
#   conteudo
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
PORT = sys.argv[1] if len(sys.argv) > 1 else "8799"
BASE = f"http://127.0.0.1:{PORT}"

LARGURAS = [640, 700, 768, 800, 900, 1000, 1024, 1100, 1200, 1280, 1366, 1440]

resultados = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    for touch in (True, False):
        for w in LARGURAS:
            ctx = browser.new_context(
                viewport={"width": w, "height": 900},
                has_touch=touch,
                is_mobile=False,
            )
            page = ctx.new_page()
            page.goto(BASE, wait_until="networkidle")
            page.wait_for_selector("#conteudo-principal-teste", timeout=10000)
            page.wait_for_timeout(400)

            sidebar = page.locator("section[data-testid='stSidebar']")
            conteudo = page.locator("#conteudo-principal-teste")

            info = {"largura": w, "touch": touch}
            if sidebar.count():
                info["sidebar_aria_expanded"] = sidebar.get_attribute("aria-expanded")
                info["sidebar_position_css"] = sidebar.evaluate(
                    "el => getComputedStyle(el).position"
                )
                sbox = sidebar.bounding_box()
                info["sidebar_box"] = sbox
            else:
                sbox = None

            cbox = conteudo.bounding_box() if conteudo.count() else None
            info["conteudo_box"] = cbox

            if sbox and cbox:
                ox1 = max(sbox["x"], cbox["x"])
                oy1 = max(sbox["y"], cbox["y"])
                ox2 = min(sbox["x"] + sbox["width"], cbox["x"] + cbox["width"])
                oy2 = min(sbox["y"] + sbox["height"], cbox["y"] + cbox["height"])
                ow = max(0, ox2 - ox1)
                oh = max(0, oy2 - oy1)
                overlap_area = ow * oh
                conteudo_area = cbox["width"] * cbox["height"]
                info["overlap_px_largura"] = ow
                info["overlap_pct_largura_conteudo"] = round(100 * ow / cbox["width"], 1) if cbox["width"] else 0
                info["overlap_pct_area_conteudo"] = (
                    round(100 * overlap_area / conteudo_area, 1) if conteudo_area else 0
                )
            else:
                info["overlap_px_largura"] = None

            # elementFromPoint no centro vertical do conteudo, 20px da borda
            # esquerda (onde ficaria um botao/link real) - confirma se o
            # toque realmente chega no conteudo ou e' engolido pela sidebar
            if cbox:
                px, py = cbox["x"] + 20, cbox["y"] + cbox["height"] / 2
                elemento = page.evaluate(
                    "(pt) => { const e = document.elementFromPoint(pt.x, pt.y); "
                    "return e ? {tag: e.tagName, id: e.id, classe: (e.className||'').toString().slice(0,80)} : null; }",
                    {"x": px, "y": py},
                )
                info["elemento_no_ponto_20px_da_borda"] = elemento

            resultados.append(info)
            ctx.close()
    browser.close()

(OUT / "medir_overlap_resultado.json").write_text(
    json.dumps(resultados, indent=2, default=str, ensure_ascii=False)
)
print(json.dumps(resultados, indent=2, default=str, ensure_ascii=False))
