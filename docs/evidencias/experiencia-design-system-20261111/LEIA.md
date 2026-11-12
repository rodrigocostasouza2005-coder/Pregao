# Experiência/Design System — auditoria Agente F (2026-11-11)

Escopo: `ui/busca.py`, `ui/paineis.py`, `ui/saude_dados_tab.py`, `ui/top_mercado_tab.py`,
`ui/navegacao.py`, `ui/radar_tab.py`, `ui/workspace.py`, `app.py` (sidebar/layout global),
`ui/design_system.py` (só consumir), `style.css`.

## Achado principal: os módulos "sem design system" já eram consistentes

O grep inicial (zero uso de `classe_sinal`/`numero_financeiro_html`/literal `FFA028`)
sinalizava os 6 módulos acima como possivelmente defasados. Investigação real (leitura
completa + harness Playwright) mostrou que **5 deles já seguem a regra #1 do próprio
`ui/design_system.py`** ("cor nunca é hex solto — usar `var(--destaque)`/`var(--alta)`/
`var(--baixa)`/`var(--cinza)`/`var(--borda)`"): `ui/paineis.py`, `ui/radar_tab.py`,
`ui/workspace.py`, `ui/top_mercado_tab.py` (reusa componente já migrado de
`ui/news_tab.py`) e `ui/busca.py` (widget nativo, sem HTML próprio). Não precisavam de
mudança de conteúdo — só confirmação visual, feita via harness (prints neste diretório).

`ui/navegacao.py`: confirmado estrutural de propósito (segmented_control puro, cor vem
de `style.css` via `.st-key-nav_secao`/`.st-key-nav_sub`, já ambar). Nenhuma mudança.

`ui/saude_dados_tab.py`: **não tocado**, por regra explícita do `CLAUDE.md` ("Saúde dos
Dados é frente separada... correções nela são sempre uma frente isolada, com sua própria
PR"). Também já está visualmente consistente (classes `.alta`/`.baixa`/`.alerta`/
`.cinza`/`.neutro`, mesmas usadas no resto do app) — não havia nada de "visual antigo"
pra corrigir mesmo se estivesse no escopo desta PR.

## Mudanças de código feitas (2 arquivos)

1. **`app.py`** (sidebar "WATCHLIST", `_fragmento_watchlist`): o card por ticker ainda
   reimplementava `cls = "alta" if var >= 0 else "baixa"` + `sinal = "+" if ...`, o
   padrão duplicado que `ui/design_system.py:variacao_html` foi criado para substituir
   (já aplicado no ticker tape do mesmo arquivo, mas não aqui). Trocado por
   `design_system.variacao_html(...)`. Puramente visual — mesmo resultado, uma fonte a
   menos de divergência futura.

2. **`style.css`**: **achado real, confirmado por screenshot** (ver
   `top_mercado_desktop-1440.png` antes/depois) — o VALOR de
   `st.selectbox`/`st.text_input`/`st.multiselect`/etc já tinha `font-size:0.8rem`
   (regra existente), mas o RÓTULO do widget (ex: "Região", "Setor", "Buscar ativo")
   ficava no tamanho/peso padrão do Streamlit (maior, branco puro) — inconsistente com
   o resto do app. Adicionada 1 regra: `[data-testid="stWidgetLabel"] p { color:
   var(--neutro) !important; font-size:0.8rem !important; }` (mesmo padrão já usado
   para `.stCheckbox`/`.stRadio`, só generalizado pro testid estável que cobre os outros
   widgets). Afeta o app inteiro (rótulos de todos os widgets), sempre pra mais
   consistente — rodada a suíte completa (2250 testes) depois, sem regressão.

## Evidência visual (Playwright real, não AppTest)

Harnesses locais (sem login/Supabase/rede — mesmo padrão de
`docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py` e
`docs/evidencias/responsividade-bloomberg-20261106/harness_radar.py`), screenshot em 3
breakpoints (`desktop-1440`, `ipad-1024`, `ipad-820`):

- `harness_nav.py` — `ui/navegacao.py` com o registro `AREAS` real (10 áreas / 43
  subabas — a árvore cresceu desde a estimativa de "8/~29" do briefing, RESEARCH e
  COORDENADOR viraram áreas próprias numa PR anterior). Nav + subnav renderizam e
  trocam de rota sem exception em nenhuma combinação visitada.
- `harness_busca_paineis.py` — `ui/busca.py` + `ui/paineis.py` (popover "⚙" de
  tamanho/visibilidade).
- `harness_top_mercado.py` — `ui/top_mercado_tab.py` com BRASIL/INTERNACIONAL/TUDO.
- `harness_workspace.py` — `ui/workspace.py` (toolbar, drag/resize, popover por painel).
- `harness_sidebar_watchlist.py` — replica o trecho alterado em `app.py` usando o
  `design_system.variacao_html` real (não uma reimplementação) pra validar o visual da
  mudança nº 1.
- reaproveitado `docs/evidencias/responsividade-bloomberg-20261106/harness_radar.py`
  (não modificado) só pra confirmar visualmente que `ui/radar_tab.py` segue consistente.

`shot_all.py`: script que sobe os 6 (mais o de radar, já existente) e varre os 3
breakpoints, checando ausência de `stException`/`stAlert[kind=error]` na tela. Resultado:
**sem erros detectados** em nenhuma combinação.

## O que NÃO foi possível validar

Walkthrough autenticado das 43 subabas na app real (login Google/`st.login`, Supabase de
produção) não é viável neste ambiente (sandbox sem credencial OAuth nem acesso ao
Supabase de produção) — mesma limitação que `CLAUDE.md` já pede pra declarar em vez de
alegar validação de produção. A cobertura real foi: harness Playwright por módulo
tocado/sob responsabilidade (acima) + leitura completa dos módulos restantes (sem
harness dedicado) comparando com o padrão já estabelecido nas abas migradas.

## Achados em áreas de outros agentes (só relato, não corrigido aqui)

Nenhum achado de regressão visual nas pastas/arquivos de outros agentes durante esta
auditoria (não foi feito um Playwright completo nelas — fora do escopo de edição desta
PR; o relato é limitado ao que apareceu incidentalmente ao navegar/ler código
compartilhado, ex. `ui/news_tab.py` reusado por `ui/top_mercado_tab.py`, que está
consistente).
