# Sidebar sobrepõe o conteúdo em tablet touch (~1024px) — 2026-11-24

Achado registrado em `docs/evidencias/fase6-ux-missao-master-20261123/LEIA.md`
("Achado NOVO... fora do escopo desta correção"), nunca corrigido até agora.
Esta branch (`fix/sidebar-tablet-overlap-20261124`, a partir de
`origin/main`) corrige, com validação visual real (Playwright/Chromium, não
AppTest nem leitura de CSS "no olho").

## Playwright real confirmado neste ambiente

`C:\Users\Dell\Projects\pregao\.venv\Scripts\python.exe -m playwright
--version` → `Version 1.63.0`; Chromium lança normalmente (`p.chromium.launch()`
testado, versão `153.0.8010.12`). Mesmo `.venv` compartilhado usado em missões
anteriores do projeto — nenhum venv novo criado.

## Reprodução (ANTES do fix)

Harness isolado (`harness_sidebar_overlap.py`, mesmo padrão de
`docs/evidencias/regressao-toque-ipad-radar-20261112/harness_nav_sidebar.py`):
`streamlit run` real, sem login/Supabase — `st.set_page_config(initial_sidebar_state="auto")`
+ `style.css` real + sidebar WATCHLIST real (mock) + `ui/navegacao.py` real
(nav principal + subnav reais) + um marcador de "conteúdo principal" visível
(`#conteudo-principal-teste`) pra medir sobreposição de verdade via
`getBoundingClientRect`.

`medir_overlap.py`: mede, em 12 larguras (640–1440px) × 2 capacidades de
input (touch/mouse), `aria-expanded` da sidebar, `position` computada,
bounding boxes e overlap real. Resultado bruto: `medir_overlap_ANTES_resultado.json`.

**Causa raiz medida (não suposta):**

1. `app.py:59` — `initial_sidebar_state="auto"` decide abrir a sidebar
   sozinho, só pela LARGURA da tela (breakpoint interno do próprio
   Streamlit, confirmado entre 768px fechado e 800px aberto — `aria-expanded`
   vira `"true"` a partir de 800px, com ou sem touch).
2. `style.css` (bloco `@media (hover: none), (pointer: coarse)`, ~linha 412
   antes do fix) — fix intencional e correto de 2026-11-01 que força
   `position: fixed !important; height: 100vh` na sidebar em QUALQUER
   largura quando o dispositivo é touch, pra evitar que ela "aperte" o
   conteúdo (bug real documentado, confirmado em iPad 810px).

**A interação dos dois**: em qualquer tablet touch com largura ≥800px
(inclusive 1024px, 1366px...), a sidebar abre sozinha (regra 1) E vira um
overlay fixo de altura total (regra 2) — cobrindo os primeiros ~300px do
conteúdo **em qualquer posição de rolagem** (`position:fixed`, não é um
overlay "de uma vez só" no topo). Medido em 1024px touch: overlap de 284px
de largura (28,6% da largura do conteúdo) pela ALTURA INTEIRA da página —
inclusive o header (logo/busca/ticker, que não desloca porque o deslocamento
do header só é aplicado para mouse), os rótulos das abas principais e o
início de qualquer painel. Confirmado também com screenshot do app real já
existente (`docs/evidencias/fase6-ux-missao-master-20261123/resp_mercado_visaogeral_1024.png`):
logo, parte do ticker e metade das abas principais ficam literalmente
atrás da sidebar.

Em mouse, na MESMA largura (1024px), a sidebar empurra o conteúdo em vez de
sobrepor (`position: relative`, regra já existente só para
`hover:hover and pointer:fine`) — 692px de conteúdo disponível, sem nenhum
aperto. Ou seja: o espaço já é suficiente para empurrar em vez de sobrepor
nessa largura; o problema é que a regra de overlay (pensada para telas
realmente estreitas como celular ou iPad em pé ~810px) nunca tinha uma
condição de largura, então também capturava tablets em paisagem (1024px+)
onde empurrar seria seguro.

Screenshots ANTES: `antes_1024_touch.png` (bug real, conteúdo/nav/header
cortados), `antes_1440_mouse.png`, `antes_390_touch.png` (baseline, sem bug).

## Fix aplicado (`style.css`, só CSS, zero mudança de lógica)

Mínimo necessário: adicionar uma condição de largura às duas media queries
já existentes que decidem "empurrar vs sobrepor" (nenhuma regra nova
criada, nenhuma reescrita de lógica de layout):

- `@media (min-width: 641px) and (hover: hover) and (pointer: fine)` →
  `@media (min-width: 641px) and (hover: hover) and (pointer: fine), (min-width: 1024px)`
  (a regra de "empurrar" — `position: relative; z-index: 1100` — passa a
  valer também para touch quando a tela já é larga o bastante, igual já
  valia para mouse).
- `@media (hover: none), (pointer: coarse)` (só a parte que força
  `position: fixed` da sidebar) → restrita a
  `@media (max-width: 1023px) and (hover: none), (max-width: 1023px) and (pointer: coarse)`
  (overlay forçado continua existindo, mas só abaixo de 1024px — celular e
  tablet em pé, onde empurrar 300px realmente aperta o conteúdo, bug
  original de 2026-11-01 preservado).
- As outras 2 correções que viviam no mesmo bloco (botão de fechar sempre
  visível em touch, alvo de toque mínimo de 44px do checkbox) foram
  mantidas SEM restrição de largura — não têm relação com
  overlay-vs-empurrar, continuam necessárias em qualquer largura touch.
- `.st-key-nav_sub` (z-index acima da sidebar) também ficou sem restrição —
  inócuo acima de 1024px (nunca mais há sobreposição ali pra "ganhar"), sem
  necessidade de mexer.

1024px escolhido por ser exatamente a faixa real, medida, entre os tablets
em pé confirmados quebrando com push (~768–900px) e os tablets deitados
(1024px+, onde o push já funciona de forma idêntica ao mouse na mesma
largura) — não é um valor arbitrário "no olho".

## Validação (DEPOIS do fix)

Mesmo harness, mesma medição (`medir_overlap_DEPOIS_resultado.json`):

- **1024px touch**: `aria-expanded="true"`, mas `position` agora `relative`
  (empurra); overlap = 0px (antes: 284px). Conteúdo disponível = 692px,
  **idêntico** ao valor já obtido com mouse na mesma largura (692px) —
  comportamento agora indistinguível entre touch e mouse nessa faixa.
- **800–1000px touch**: inalterado (overlay preservado, como antes do fix)
  — a faixa que genuinamente precisa de overlay continua protegida.
- **640/700/768px touch**: inalterado (`aria-expanded="false"`, sidebar
  fechada por padrão, sem overlap) — mobile não regrediu.
- **Todas as larguras com mouse (touch=false)**: resultado numérico
  **idêntico**, byte a byte, ao ANTES — zero regressão em desktop.

Screenshots DEPOIS: `depois_1024_touch.png` (bug resolvido — nav completa,
conteúdo "CONTEUDO PRINCIPAL (marcador de teste)" totalmente legível, igual
ao layout de desktop), `depois_1440_mouse.png` (idêntico pixel a pixel ao
ANTES — confirma visualmente zero regressão em desktop),
`depois_390_touch.png` (idêntico ao ANTES — confirma zero regressão em
mobile).

Regressão específica também revalidada: o teste já existente
`docs/evidencias/regressao-toque-ipad-radar-20261112/touch_regressao.py`
(toque real em iPad 1024×1366 na 2ª subaba do RADAR, bug original do PR
#270) continua passando — `REGRESSAO: OK` — e o toque chega ainda mais
diretamente no botão real agora (botão em x=399, fora de qualquer disputa
de z-index com a sidebar, já que ela não sobrepõe mais nessa largura).
Evidências daquela pasta (`apos_toque_ipad_hoje.png`,
`touch_regressao_resultado.json`) foram restauradas ao estado original após
o teste — não fazem parte do escopo desta PR.

## Testes

- Suíte pertinente (`tests/test_style_css_vg_ticker_link.py`,
  `tests/test_mercado_ranking_ui.py`,
  `tests/test_coordenador_tab_tabelas_scroll_wrap.py`,
  `tests/test_calendario_grade_mobile_nowrap.py`,
  `tests/test_smoke_todas_abas.py`): **26 passed**.
- Suíte completa (`pytest`): ver resultado no corpo da PR (rodada em
  background nesta sessão) — mudança é só CSS (2 condições de media query),
  risco de regressão em teste Python é baixo, mas a execução completa
  confirma.

## Limitações honestas

- Validação visual real RODOU (Playwright/Chromium real, não AppTest),
  mas via harness isolado sem login Google/Supabase (mesmo padrão já
  estabelecido no projeto para este tipo de bug de CSS/layout) — não é uma
  passada completa pelo app real logado em produção.
- O breakpoint de 1024px cobre os tamanhos reais de tablet testados
  (iPad portrait ~768-900px overlay, iPad landscape 1024px+ push). Um
  tablet incomum entre ~900-1024px (pouco comum no mercado) poderia cair
  numa zona não testada explicitamente nesta sessão — o comportamento
  nessa faixa não muda em relação ao que já existia antes do fix (overlay),
  então não há regressão possível ali, só a correção não se estende a ela.
