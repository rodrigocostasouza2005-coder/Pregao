# Responsividade Bloomberg (2026-11-06) — evidências

Frente final da reformulação visual Bloomberg: responsividade (desktop/notebook/iPad/celular)
+ correção do bug de toque em iPad já identificado por duas sessões anteriores em
`ui/radar_tab.py` (ver comentário em `_bloco_carteiras_detalhadas`).

## Bug real encontrado e corrigido (toque em iPad, ALERTAS/CARTEIRAS RECOMENDADAS)

**Investigação** (Playwright, viewport iPad 1024x1366, `has_touch=True`, app real rodando
localmente com bypass de login fora do repo — `_local_bypass/sitecustomize.py`, nunca
commitado, nunca editou `auth.py`, mesmo padrão já usado pela sessão de 2026-11-01):
hipótese inicial de "componente HTML customizado competindo com touch" não se confirmou —
`ui/radar_tab.py` isolado (harness, sem o chrome do app) respondeu a toque perfeitamente em
todos os widgets (pills de período, link `<a class="rq-ticker">`, `st.selectbox` de carteira).

A causa real só apareceu testando a aba DENTRO do app completo: a sidebar (WATCHLIST) abre
por padrão em telas largas o bastante (`initial_sidebar_state="auto"`, decisão do próprio
Streamlit só por LARGURA) e, em touch, é sempre *overlay* (`position:fixed`, z-index nativo
999991 — correção de 2026-11-01). Num iPad (1024px) essa faixa de 300px cobre exatamente as
2 primeiras subabas de RADAR — **Alertas** e **Carteiras Recomendadas** — as mais à esquerda
da subnav. Confirmado com `document.elementFromPoint` no ponto exato do botão "Alertas":
o elemento ali era uma linha da watchlist da sidebar (ex. "VALE3"), não o botão — o toque é
literalmente engolido pela sidebar, a aba nunca troca (nem fecha a sidebar: não é sequer um
dismiss-ao-tocar-fora, o toque não chega perto do botão real).

- `tap_alertas_debug.txt` / `apos_toque_em_alertas_coberto.png` — ANTES do fix: toque no
  ponto exato do botão "Alertas" bate na watchlist da sidebar, URL não muda.
- `tap_alertas_depois_fix.txt` / `apos_toque_em_alertas_FIX_v2_bg.png` — DEPOIS do fix: toque
  no mesmo ponto bate em `<p>Alertas</p>` de verdade, URL muda pra `sub=alertas` (e o mesmo
  teste confirma `sub=carteiras` a partir de Alertas).

**Fix** (`style.css`, dentro do media query de touch já existente,
`@media (hover: none), (pointer: coarse)`): `.st-key-nav_sub` (a subnav de cada área) ganha
`position:relative; z-index:1000000` (acima do z-index nativo da sidebar) + fundo sólido
(`var(--bg)`, mesmo padrão já usado em `header[data-testid="stHeader"]` pra fechar esse tipo
de buraco) pra não deixar o texto "fantasma" da sidebar por trás. Nenhum outro elemento
(header_fixo completo, nav_secao) foi elevado — eles ocupam a MESMA faixa onde a própria
sidebar tem seu botão de FECHAR (topo dela, corrigido em 2026-11-01), subir esses também
cobriria esse botão e trocaria um bug de toque por outro (ver comentário completo no CSS).

## Auditoria de overflow (3 breakpoints)

`overflow_audit.py` testou 12 rotas recém-reformuladas (Home/Mercado, Watchlist, Research,
Comitê/Coordenador, Análises, Valuation, Radar/Carteiras, Notícias/Morning Call) × 3
breakpoints (desktop 1440 / iPad 1024 / celular 390) contra `document.documentElement.
scrollWidth` vs `clientWidth` — **0 de 36 combinações com overflow horizontal real**
(`overflow_audit_resultado.json`). Reformulações anteriores já tinham tratado isso bem
(wrappers `overflow-x:auto`, `flex-wrap`, colunas empilhando no celular). Spot-checks visuais
em 390px (`spotcheck_*.png`) confirmam texto legível, sem corte, tabelas com rolagem própria.

## Arquivos

- `harness_radar.py` / `touch_audit.py` / `touch_audit_resultado.json` — harness isolado de
  `ui/radar_tab.py` (mock de `data/radar_quedas.py`, sem Supabase) + teste de toque real
  (pills, link de ticker, selectbox) nos 3 breakpoints.
- `alertas_*.png` / `carteiras_*.png` — screenshots do harness isolado, 3 breakpoints.
- `overflow_audit.py` / `overflow_audit_resultado.json` / `spotcheck_*.png` — auditoria do
  app completo.
- `real_app_alertas_ipad_v2.png`, `apos_toque_em_alertas_coberto.png`,
  `apos_toque_em_alertas_FIX_v2_bg.png`, `tap_alertas_debug.txt`,
  `tap_alertas_depois_fix.txt` — evidência do bug real no app completo e do fix.

Validação com dados reais de produção (Supabase/Yahoo) depende do deploy (Streamlit Cloud) —
aqui os dados são mock, mesma limitação já documentada nas evidências anteriores do projeto.
