"""DIAG TEMPORARIO (NAO MERGEAR): abre cada rota do terminal web rodando
no runner (dados publicos reais, sem secrets/Supabase) e salva
screenshot desktop+celular, erros de console e o texto visivel."""
import json, sys
from playwright.sync_api import sync_playwright

base = "http://localhost:3000"
rotas = ["/", "/mercado", "/macro", "/research", "/noticias", "/cvm", "/agenda", "/morning-call",
         "/inteligencia", "/configuracoes", "/ativo/PETR4", "/busca?q=vale"]
relatorio = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for r in rotas:
        for nome, w, h in (("desktop", 1440, 900), ("celular", 390, 844)):
            pg = b.new_page(viewport={"width": w, "height": h})
            erros = []
            pg.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
            resp = pg.goto(base + r, wait_until="networkidle", timeout=180000)
            arq = (r.strip("/").replace("/", "_").replace("?", "_").replace("=", "-") or "home") + f"_{nome}.png"
            pg.screenshot(path=f"saida_web/{arq}", full_page=True)
            relatorio.append({"rota": r, "tela": nome, "http": resp.status if resp else None,
                              "scrollWidth": pg.evaluate("document.documentElement.scrollWidth"),
                              "erros_console": erros[:5],
                              "texto": pg.inner_text("main")[:1500] if nome == "desktop" else ""})
            pg.close()
    b.close()
json.dump(relatorio, open("saida_web/relatorio.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps([{k: v for k, v in x.items() if k != "texto"} for x in relatorio], ensure_ascii=False, indent=1))
# rodada 2
