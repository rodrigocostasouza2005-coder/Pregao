# Validação independente HOME/MERCADO — 06/11/2026

Segunda opinião independente sobre o redesign terminal de HOME (VISÃO GERAL) e
MERCADO (PAINEL), pedida pelo Rodrigo porque uma sessão anterior tinha concluído
(só por auditoria de código, sem screenshot novo) que o redesign do pedido original
(gráfico principal amplo, radar de eventos integrado, faixa de cotações, rankings
densos) já estava satisfeito pela PR #187 (27/10/2026). Esta sessão não aceitou essa
conclusão sem checar: montou harness local (Streamlit, sem login, `render_visao_geral`/
`render_mercado` chamados direto com `config.PREFS_PADRAO` e dados mockados realistas)
e rodou Playwright/Chromium de verdade (1440×900, página inteira).

Harness local, mesmo padrão de `docs/evidencias/watchlist-bloomberg-20261106/`
(sem login, dados mockados realistas via `unittest.mock.patch`, nunca chamada real a
Yahoo/Supabase/Groq — fora do alcance deste sandbox).

| Arquivo | O que mostra |
|---|---|
| `harness_home.py` | Harness de `ui.visao_geral.render_visao_geral` |
| `harness_mercado.py` | Harness de `ui.mercado_tab.render_mercado` |
| `shot_home.py` / `shot_mercado.py` | Script Playwright (screenshot de página inteira — mede o `scrollHeight` real de `[data-testid="stMain"]`, que no Streamlit 1.64 tem overflow próprio, e redimensiona o viewport antes de capturar) |
| `home_full.png` | HOME completa, 1440×1918, **depois** da correção abaixo |
| `mercado_full.png` | MERCADO completa, 1440×2403 |

## Veredito

**CONFIRMADO** (com 1 correção estrutural aplicada no caminho — ver abaixo): o
cockpit de HOME tem gráfico principal amplo em destaque (70% da largura, candle+volume,
maior elemento visual da tela), radar de eventos (RESULTADOS DA WATCHLIST) integrado
sem precisar trocar de aba, faixa de indicadores no topo visualmente contínua (além do
ticker tape animado já existente em `app.py`, fora do escopo deste harness) e rankings
(altas/baixas, mais negociados) em tabela/lista densa de terminal, não cards. MERCADO
segue o mesmo padrão (TERMÔMETRO + métricas + 2 linhas de 3 colunas fixas, rankings com
monograma/ticker/nome+valor em grid apertado).

## Gap real encontrado e corrigido

Playwright pegou um bug real de renderização em `ui/visao_geral.py:_painel_leitura_pregao`
(painel "LEITURA DO PREGÃO", o primeiro bloco da tela): os chips (`_chip_html`) começam
com `<span>`, uma tag INLINE — o CommonMark só reconhece um "HTML block" (conteúdo cru,
sem nenhum parsing por cima) quando a string entregue a `st.markdown` começa com uma tag
de BLOCO (`div`/`table`/`p`/...), nunca com `<span>`. Sem isso, o markdown-it do
Streamlit processa a string como parágrafo normal — e qualquer `$` solto (ex.: "R$" no
chip de maior volume financeiro, que aparece quase sempre, + um "US$" dentro de um texto
de síntese por IA mencionando preço em dólar, cenário realista) é interpretado como
abre/fecha de matemática LaTeX. Tudo entre os dois `$` virava um bloco `language-math`
quebrado (HTML cru aparecendo como texto na tela) em vez do conteúdo pretendido —
exatamente o painel mais no topo da hierarquia que este pedido queria garantir limpo.

Reproduzido e corrigido via Playwright contra o harness real (capturas antes/depois
comparadas durante a investigação, não commitadas — só a versão corrigida ficou em
`home_full.png`). Correção: envolver a string final dos chips num `<div>` (tag de
bloco), fazendo o CommonMark reconhecer HTML block de verdade e pular o parsing
inline — mesmo efeito visual (chips lado a lado, `display:inline-flex` em cada
`<span>`), zero dado/texto alterado. Teste de regressão:
`tests/test_visao_geral_terminal.py::test_painel_leitura_pregao_chips_ficam_dentro_de_bloco_html`.

Suíte completa (`pytest -q`): 2242 passed.
