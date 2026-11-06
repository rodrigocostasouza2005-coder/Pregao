import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
URL = "http://127.0.0.1:8767"

SUBABAS = ["Visão Geral", "Especialistas", "Execuções", "Histórico", "Analisar"]

# iPad (portrait) viewport/UA, touch habilitado - mesmo perfil usado pelo
# device descriptor "iPad" do Playwright.
IPAD = {"width": 1024, "height": 1366}


def _overflow_horizontal(page) -> dict:
    return page.evaluate(
        """
        () => {
            const doc = document.documentElement;
            return {scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth};
        }
        """
    )


def _tabelas_overflow(page) -> list:
    return page.evaluate(
        """
        () => {
            const tables = document.querySelectorAll('table.coord-tabela');
            return Array.from(tables).filter(t => t.getBoundingClientRect().width > 0).map(t => {
                const rect = t.getBoundingClientRect();
                const wrap = t.closest("div[class*='coord-tabela-wrap']");
                return {tableWidth: Math.round(rect.width), scrollWidth: t.scrollWidth, hasWrap: !!wrap};
            });
        }
        """
    )


with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport=IPAD,
        user_agent=(
            "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        has_touch=True,
        is_mobile=True,
    )
    page = context.new_page()
    page.goto(URL, wait_until="networkidle")
    time.sleep(2)

    for i, nome in enumerate(SUBABAS):
        tab = page.get_by_role("tab", name=nome, exact=True)
        tab.tap()
        time.sleep(1.5)
        ov = _overflow_horizontal(page)
        overflow_flag = " PAGE-OVERFLOW!" if ov["scrollWidth"] > ov["clientWidth"] + 2 else ""
        tabelas = _tabelas_overflow(page)
        print(f"[{nome}] scrollWidth={ov['scrollWidth']} clientWidth={ov['clientWidth']}{overflow_flag}")
        for t in tabelas:
            flag = " TABLE-OVERFLOW-SEM-SCROLL!" if (t["tableWidth"] > ov["clientWidth"] and not t["hasWrap"]) else ""
            print("   table:", t, flag)
        safe = nome.lower().replace(" ", "_").replace("ú", "u").replace("ó", "o").replace("ê", "e").replace("í", "i")
        page.screenshot(path=str(OUT / f"ipad_{i}_{safe}.png"), full_page=True)

    browser.close()
