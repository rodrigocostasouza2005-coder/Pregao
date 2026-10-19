# MERCADO — alturas de painel genéricas escondiam a maior parte do conteúdo (2026-10-19)

Missão de redesign + performance, prioridade 3 (MERCADO/gráficos/tabelas).
Harness isolado rodando `ui/mercado_tab.py:render_mercado` com **dados reais**
(B3 + Yahoo Finance — este ambiente tem acesso de rede real, confirmado antes
de usar; nenhum dado sintético aqui), sem login.

**Achado, medido no DOM real (`getComputedStyle`/`scrollHeight`, não por
suposição):** `ui/workspace.py:_ALTURA_PADRAO_REM=18rem` (288px) é aplicado
genericamente a todo painel que não declara override — `render_mercado` nunca
passava `alturas_padrao` (mecanismo que já existe e já é usado por
`ui/macro_tab.py`). Resultado, com dados reais:

| Painel | Conteúdo real | Mostrado antes | % oculto |
|---|---|---|---|
| MAIORES ALTAS/BAIXAS | 983px | 286px | ~71% |
| MAIS NEGOCIADOS | 615px | 286px | ~54% |
| DESEMPENHO SETORIAL | 689px | 286px | ~58% |
| MAPA DO MERCADO | 553px | 286px | ~48% |
| MERCADOS GLOBAIS | 286px | 286px | 0% (já cabia) |

`antes_rodape_cortado.png` mostra o treemap com caixas cortadas na borda
inferior — consequência visual direta do mesmo problema.

**Correção:** `ui/mercado_tab.py` ganhou `_ALTURAS_PADRAO` (mesmo padrão do
`ui/macro_tab.py`) com altura calibrada pelo conteúdo real medido (62/40/44/36
rem) e passou a repassar pra `workspace.renderizar_workspace`. Remedido depois
da correção: `clientHeight == scrollHeight` em todos os 5 painéis (ajuste
exato, nenhum espaço desperdiçado, nenhum corte).

`antes_desktop.png` / `depois_desktop.png` / `depois_mobile.png` — Playwright,
dados reais (IBOVESPA ao vivo no momento da captura). Altura é em `rem`
(independe de viewport) — confirmado por medição que o ajuste vale igual em
mobile.

982→984 testes passando (2 novos em `tests/test_mercado_ranking_ui.py`:
cobertura de `_ALTURAS_PADRAO` e confirmação de que `render_mercado` repassa
o override pro workspace).
