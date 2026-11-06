import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
URL = "http://127.0.0.1:8767"

SUBABAS = ["Visão Geral", "Especialistas", "Execuções", "Histórico", "Analisar"]


def _overflow_horizontal(page) -> dict:
    return page.evaluate(
        """
        () => {
            const doc = document.documentElement;
            return {scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth};
        }
        """
    )


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(URL, wait_until="networkidle")
    time.sleep(2)

    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    tabs = page.get_by_role("tab")
    print("tabs found:", tabs.count())
    for nome in tabs.all_text_contents():
        print(" -", repr(nome))

    for i, nome in enumerate(SUBABAS):
        tab = page.get_by_role("tab", name=nome, exact=True)
        tab.click()
        time.sleep(1.5)
        ov = _overflow_horizontal(page)
        overflow_flag = " OVERFLOW!" if ov["scrollWidth"] > ov["clientWidth"] + 2 else ""
        print(f"[{nome}] scrollWidth={ov['scrollWidth']} clientWidth={ov['clientWidth']}{overflow_flag}")
        safe = nome.lower().replace(" ", "_").replace("ú", "u").replace("ó", "o").replace("ê", "e").replace("í", "i")
        page.screenshot(path=str(OUT / f"desktop_{i}_{safe}.png"), full_page=True)

    print("console errors:", console_errors)
    browser.close()
