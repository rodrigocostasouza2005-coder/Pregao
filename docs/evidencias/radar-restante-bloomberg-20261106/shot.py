# Captura os screenshots desktop/iPad das 4 telas usando harness_radar_restante.py
# (ja' rodando em `streamlit run harness_radar_restante.py`) - mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/shot.py.
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
BASE = "http://localhost:8733"  # ajuste pra porta usada no `streamlit run`
TELAS = ["alertas", "oportunidades", "acompanhamento", "preferencias"]
# Marcador final de cada tela (ultimo texto a renderizar) - mais confiavel
# que networkidle/timeout fixo: reruns do Streamlit via WebSocket nao geram
# trafego de rede novo, entao networkidle pode resolver ANTES do conteudo
# terminar de chegar.
MARCADOR = {
    "alertas": "text=Sinais para investigar",
    "oportunidades": "text=RESEARCH COM EVIDÊNCIAS",
    "acompanhamento": "text=Itens salvos e anotações pessoais",
    "preferencias": "text=PREFERÊNCIAS DE RECEBIMENTO",
}


def _capturar(page, tela, path, largura):
    page.goto(f"{BASE}/?secao={tela}", wait_until="load")
    page.wait_for_selector(MARCADOR[tela], timeout=45000)
    page.wait_for_timeout(1000)
    # Streamlit roda o scroll dentro de um container proprio (nao o
    # <body>) - full_page=True sozinho fica preso na altura do viewport.
    # Mede a altura real do conteudo e redimensiona o viewport antes do
    # screenshot (mais confiavel que full_page aqui).
    altura = page.evaluate(
        "Math.max(document.body.scrollHeight, "
        "document.querySelector('[data-testid=\"stAppViewContainer\"]')?.scrollHeight || 0)"
    )
    page.set_viewport_size({"width": largura, "height": min(int(altura) + 120, 15000)})
    page.wait_for_timeout(300)
    page.screenshot(path=path, full_page=True)


with sync_playwright() as p:
    browser = p.chromium.launch()

    # Desktop 1440px
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = ctx.new_page()
    _capturar(page, "alertas", str(OUT / "_warmup.png"), 1440)  # 1a carga do processo e' mais lenta
    for tela in TELAS:
        _capturar(page, tela, str(OUT / f"desktop-1440-{tela}.png"), 1440)
        print(f"desktop {tela} ok")
    ctx.close()

    # iPad 1024px com touch (RADAR teve bug real de touch em iPad hoje, PR #270)
    ctx2 = browser.new_context(viewport={"width": 1024, "height": 1366}, has_touch=True, is_mobile=False)
    page2 = ctx2.new_page()
    for tela in TELAS:
        _capturar(page2, tela, str(OUT / f"ipad-1024-touch-{tela}.png"), 1024)
        print(f"ipad {tela} ok")
    ctx2.close()

    browser.close()

(OUT / "_warmup.png").unlink(missing_ok=True)
print("done")
