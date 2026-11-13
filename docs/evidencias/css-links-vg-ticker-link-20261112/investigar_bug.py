# Investigacao real (Playwright, Chromium) do bug .vg-ticker-link azul/
# sublinhado. Roda contra harness_vg_ticker_link.py (porta 8779, ja' de pe').
# Objetivo: capturar getComputedStyle ANTES da correcao + achar a regra CSS
# exata do proprio Streamlit que esta vencendo (percorre document.styleSheets
# e testa element.matches(selector) pra cada seletor, sem supor hash nenhum).
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
        textDecoration: cs.textDecoration,
        outline: cs.outline,
        outlineOffset: cs.outlineOffset,
        ancestorClasses: (() => {
            let n = el;
            const chain = [];
            while (n && chain.length < 6) {
                chain.push(n.tagName + '.' + (n.className || ''));
                n = n.parentElement;
            }
            return chain;
        })(),
    };
}
"""

JS_MATCHING_RULES = """
(sel) => {
    const el = document.querySelector(sel);
    if (!el) return [];
    const out = [];
    for (const sheet of document.styleSheets) {
        let rules;
        try { rules = sheet.cssRules; } catch (e) { continue; }
        if (!rules) continue;
        for (const rule of rules) {
            if (!rule.selectorText) continue;
            // cada regra pode ter varios seletores separados por virgula
            const partes = rule.selectorText.split(',').map(s => s.trim());
            for (const parte of partes) {
                try {
                    if (el.matches(parte)) {
                        out.push({
                            selector: parte,
                            color: rule.style.color || null,
                            textDecoration: rule.style.textDecoration || rule.style.textDecorationLine || null,
                            href: sheet.href,
                            cssText: rule.style.cssText,
                        });
                    }
                } catch (e) { /* seletor invalido pro browser atual, ignora */ }
            }
        }
    }
    return out;
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

        # estado normal (sem interacao)
        bloco["normal"] = page.evaluate(JS_COMPUTED, "#link-teste-vg")
        bloco["regras_que_batem_normal"] = page.evaluate(JS_MATCHING_RULES, "#link-teste-vg")

        # estado hover
        page.hover("#link-teste-vg")
        page.wait_for_timeout(150)
        bloco["hover"] = page.evaluate(JS_COMPUTED, "#link-teste-vg")

        # estado focus (via teclado real, Tab) - comeca do body
        page.evaluate("document.activeElement && document.activeElement.blur && document.activeElement.blur()")
        page.mouse.move(0, 0)
        page.keyboard.press("Tab")
        # pode levar mais de um Tab pra alcancar o link dependendo da ordem
        # de foco da pagina - avanca ate' achar ou esgotar tentativas
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

        # controle externo (deve continuar com o visual nativo do navegador,
        # a correcao NAO deve toca-lo)
        bloco["externo_normal"] = page.evaluate(JS_COMPUTED, "#link-teste-externo")

        resultados[viewport_nome] = bloco

        page.screenshot(path=str(OUT / f"antes_fix_{viewport_nome}.png"), full_page=False)
        ctx.close()

    browser.close()

(OUT / "antes_fix_resultado.json").write_text(
    json.dumps(resultados, indent=2, ensure_ascii=False)
)
print(json.dumps(resultados, indent=2, ensure_ascii=False))
