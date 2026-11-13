# Mesma verificacao de investigar_bug.py, rodada DEPOIS da correcao em
# style.css, pra comparar antes/depois lado a lado. Reusa o harness ja'
# rodando na porta 8779 (cada nova sessao/pagina executa o script do
# harness do zero, que le' style.css do disco a cada run - nao precisa
# reiniciar o processo do Streamlit pra pegar o CSS atualizado).
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
BASE = "http://127.0.0.1:8779"

JS_COMPUTED = """
(sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    return {
        color: cs.color,
        textDecorationLine: cs.textDecorationLine,
        outline: cs.outline,
        outlineOffset: cs.outlineOffset,
    };
}
"""

resultados = {}

with sync_playwright() as p:
    browser = p.chromium.launch()

    for viewport_nome, viewport in [
        ("desktop_1440", {"width": 1440, "height": 900}),
        ("ipad_1024x768", {"width": 1024, "height": 768}),
    ]:
        ctx = browser.new_context(viewport=viewport)
        page = ctx.new_page()
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_selector("#link-teste-vg", timeout=10000)
        page.wait_for_timeout(300)

        bloco = {}
        bloco["normal"] = page.evaluate(JS_COMPUTED, "#link-teste-vg")

        page.hover("#link-teste-vg")
        page.wait_for_timeout(150)
        bloco["hover"] = page.evaluate(JS_COMPUTED, "#link-teste-vg")

        page.evaluate("document.activeElement && document.activeElement.blur && document.activeElement.blur()")
        page.mouse.move(0, 0)
        page.keyboard.press("Tab")
        achou_foco = False
        for _ in range(10):
            foco_id = page.evaluate("document.activeElement && document.activeElement.id")
            if foco_id == "link-teste-vg":
                achou_foco = True
                break
            page.keyboard.press("Tab")
        bloco["focus_via_tab_alcancado"] = achou_foco
        if not achou_foco:
            page.evaluate("document.getElementById('link-teste-vg').focus()")
        page.wait_for_timeout(150)
        bloco["focus"] = page.evaluate(JS_COMPUTED, "#link-teste-vg")

        # controle externo - precisa continuar EXATAMENTE igual ao "antes"
        # (nao pode ter sido afetado pela correcao, que e' escopada a
        # .vg-ticker-link)
        bloco["externo_normal"] = page.evaluate(JS_COMPUTED, "#link-teste-externo")

        resultados[viewport_nome] = bloco
        page.screenshot(path=str(OUT / f"depois_fix_{viewport_nome}.png"), full_page=False)
        ctx.close()

    browser.close()

(OUT / "depois_fix_resultado.json").write_text(
    json.dumps(resultados, indent=2, ensure_ascii=False)
)
print(json.dumps(resultados, indent=2, ensure_ascii=False))

# ---- checagem automatica dos 7 requisitos (menos o 6, que compara com o
# "antes" na comparacao final feita a parte) ----
falhas = []
for vp in ("desktop_1440", "ipad_1024x768"):
    n = resultados[vp]["normal"]
    h = resultados[vp]["hover"]
    f = resultados[vp]["focus"]
    ext = resultados[vp]["externo_normal"]

    if "rgb(61, 157, 243)" in (n["color"], h["color"], f["color"]):
        falhas.append(f"{vp}: ainda tem azul padrao do navegador em algum estado")
    if n["textDecorationLine"] != "none":
        falhas.append(f"{vp}: normal com sublinhado (esperado none, veio {n['textDecorationLine']})")
    if n["color"] != "rgb(230, 230, 230)":  # --neutro #E6E6E6
        falhas.append(f"{vp}: normal nao esta em --neutro (veio {n['color']})")
    if h["color"] != "rgb(255, 160, 40)":  # --destaque #FFA028
        falhas.append(f"{vp}: hover nao esta em --destaque (veio {h['color']})")
    if "none" in f["outline"].lower():
        falhas.append(f"{vp}: focus sem outline visivel")
    if ext["color"] == "rgb(230, 230, 230)" or ext["color"] == "rgb(255, 160, 40)":
        falhas.append(f"{vp}: link EXTERNO foi afetado pela correcao (nao deveria)")

print("\nFALHAS:" if falhas else "\nTODOS OS 7 REQUISITOS OK (automatizados que nao dependem do 'antes').")
for item in falhas:
    print(" -", item)
import sys
sys.exit(1 if falhas else 0)
