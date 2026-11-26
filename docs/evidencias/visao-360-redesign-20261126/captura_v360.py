# Captura Playwright REAL (navegador de verdade, JS/layout executados) da
# Visão 360 redesenhada, missão visao-360-redesign-20261126.
#
# Por que Playwright e não AppTest: AppTest do Streamlit não executa CSS nem
# layout - lição já registrada no projeto (ver docs/evidencias/
# validacao-visual-real-20261117). Overflow horizontal, grade que não reflui,
# texto sobreposto e coluna desproporcional só aparecem num navegador real.
#
# Mede, em cada largura: scrollWidth do body/html (overflow horizontal da
# página = reprovação), qualquer elemento mais largo que o viewport, e a
# altura total. Tira screenshot da página inteira e de cada seção do andar
# de aprofundamento.
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8599"
SAIDA = Path(__file__).resolve().parent
LARGURAS = [("desktop-1920", 1920, 1200), ("notebook-1440", 1440, 900), ("tablet-1024", 1024, 900)]

_JS_MEDIDAS = """() => {
  const vw = window.innerWidth;
  const estourando = [...document.querySelectorAll('body *')]
    .filter(el => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && (r.right > vw + 2 || r.left < -2);
    })
    .slice(0, 12)
    .map(el => ({
      tag: el.tagName.toLowerCase(),
      cls: (el.className || '').toString().slice(0, 90),
      left: Math.round(el.getBoundingClientRect().left),
      right: Math.round(el.getBoundingClientRect().right),
    }));
  return {
    innerWidth: vw,
    bodyScrollWidth: document.body.scrollWidth,
    htmlScrollWidth: document.documentElement.scrollWidth,
    alturaTotal: document.documentElement.scrollHeight,
    elementosEstourando: estourando,
    textoPreco: (document.querySelector('.v360-preco') || {}).textContent || null,
    nPaineis: document.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"]').length,
  };
}"""

SECOES = ["PARECERES DOS ESPECIALISTAS", "RESEARCH E CONSENSO", "EVIDÊNCIAS E DIVERGÊNCIAS",
          "NOTÍCIAS", "HISTÓRICO DE ANÁLISES"]


def _esperar_render(pagina):
    pagina.wait_for_selector(".v360-ticker", timeout=60_000)
    pagina.wait_for_timeout(1200)


def main():
    relatorio = {}
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        for nome, largura, altura in LARGURAS:
            pagina = navegador.new_page(viewport={"width": largura, "height": altura})
            pagina.goto(BASE, wait_until="networkidle")
            _esperar_render(pagina)
            relatorio[nome] = {"pagina_inteira": pagina.evaluate(_JS_MEDIDAS)}
            pagina.screenshot(path=str(SAIDA / f"{nome}-completa.png"), full_page=True)

            # cada seção do aprofundamento, só na largura de desktop e tablet
            if nome in ("desktop-1920", "tablet-1024"):
                for secao in SECOES:
                    try:
                        pagina.get_by_role("radio", name=secao, exact=False).first.click(timeout=8000)
                    except Exception:
                        try:
                            pagina.get_by_text(secao, exact=True).first.click(timeout=8000)
                        except Exception as exc:
                            relatorio[nome][secao] = {"erro": repr(exc)[:200]}
                            continue
                    pagina.wait_for_timeout(2500)
                    relatorio[nome][secao] = pagina.evaluate(_JS_MEDIDAS)
                    slug = secao.lower().replace(" ", "-").replace("ê", "e").replace("ô", "o")
                    slug = "".join(c for c in slug if c.isascii())
                    pagina.screenshot(path=str(SAIDA / f"{nome}-{slug}.png"), full_page=True)
            pagina.close()
        navegador.close()

    (SAIDA / "medidas.json").write_text(json.dumps(relatorio, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
    falhas = []
    for nome, blocos in relatorio.items():
        for rotulo, medidas in blocos.items():
            if "erro" in medidas:
                falhas.append(f"{nome}/{rotulo}: {medidas['erro']}")
                continue
            vw = medidas["innerWidth"]
            if medidas["bodyScrollWidth"] > vw + 2 or medidas["htmlScrollWidth"] > vw + 2:
                falhas.append(
                    f"{nome}/{rotulo}: scroll horizontal (body={medidas['bodyScrollWidth']}, "
                    f"html={medidas['htmlScrollWidth']}, viewport={vw})"
                )
            if medidas["elementosEstourando"]:
                falhas.append(f"{nome}/{rotulo}: {len(medidas['elementosEstourando'])} elemento(s) "
                              f"fora do viewport -> {medidas['elementosEstourando'][:3]}")
    print(json.dumps(relatorio, indent=2, ensure_ascii=False))
    if falhas:
        print("\n=== REPROVADO ===")
        for f in falhas:
            print(" -", f)
        sys.exit(1)
    print("\n=== OK: nenhuma largura com overflow horizontal ou elemento fora do viewport ===")


if __name__ == "__main__":
    main()
