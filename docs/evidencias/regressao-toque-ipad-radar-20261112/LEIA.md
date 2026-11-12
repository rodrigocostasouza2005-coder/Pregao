# Regressão de toque em iPad — RADAR (baseline 2026-11-12, Agente E)

Confirma que o fix do PR #270 (`cbe0d8d`, `.st-key-nav_sub` com `z-index:1000000` +
fundo sólido dentro do media query de touch) continua funcionando em `origin/main`
hoje, ANTES do merge das PRs paralelas (Agentes A-D) — baseline de regressão.

## Harness

`harness_nav_sidebar.py` renderiza, sem login/Supabase: `st.set_page_config(..., initial_sidebar_state="auto")`
real + `style.css` real + sidebar WATCHLIST (HTML mock, mesmas classes de `app.py:529+`)
+ `ui/navegacao.render_nav_principal`/`render_subnav` reais (sem mock) — reproduz a
condição exata do bug original (sidebar auto-aberta cobrindo a subnav num viewport
de iPad), mesmo padrão de `docs/evidencias/responsividade-bloomberg-20261106/harness_radar.py`.

## Teste

`touch_regressao.py` (Playwright, viewport iPad 1024x1366, `has_touch=True`): abre
RADAR > Alertas, confirma sidebar visível, toca no ponto exato do botão "Carteiras
Recomendadas" (a 2ª subaba, coberta antes do fix) e confirma que o elemento no ponto
do toque é o `<p>` real do botão (não uma linha da sidebar) e que a URL muda pra
`sub=carteiras`.

## Resultado (origin/main, 36dda39)

```
sidebar_visivel: true
elemento_no_ponto_do_toque: {tag: "P", texto: "Carteiras Recomendadas"}
url_apos_toque: ".../?aba=radar&sub=carteiras"
mudou_para_carteiras: true
REGRESSAO: OK
```

Ver `apos_toque_ipad_hoje.png` (screenshot) e `touch_regressao_resultado.json` (dados
completos). Sem regressão — serve de baseline pra comparar depois do merge do
Agente D (redesign visual estrutural em `ui/*.py`), que é o mais provável de tocar
CSS/estrutura de nav e arriscar reintroduzir o bug.

Como rodar de novo: `streamlit run docs/evidencias/regressao-toque-ipad-radar-20261112/harness_nav_sidebar.py --server.port=8778 --server.headless=true` (background) e depois `python docs/evidencias/regressao-toque-ipad-radar-20261112/touch_regressao.py`.
