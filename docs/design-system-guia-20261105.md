# Guia rápido: design system compartilhado do PREGÃO ("Bloomberg terminal")

Pra abas aplicando o padrão visual consolidado (PRs #185-#212 + esta missão).
Não recria nada já existente — só aponta onde está.

## Tokens CSS (`style.css`, `:root`)

`--bg` (fundo app), `--painel-bg` (fundo de painel), `--borda`, `--destaque`
(âmbar `#FFA028` — títulos/links/ênfase), `--alta` (verde), `--baixa`
(vermelho), `--neutro` (texto principal), `--cinza` (texto secundário),
`--ciano`. Fonte: IBM Plex Mono em todo o app (herdado globalmente, não
precisa declarar). Nunca usar hex/rgb fixo — sempre `var(--token)`.

## Classes globais já prontas (`style.css`)

- `.painel-titulo` — cabeçalho de painel (âmbar, uppercase, borda inferior).
  Use dentro de `st.container(border=True)` — o wrapper do container já
  recebe borda+fundo certos automaticamente
  (`div[data-testid="stVerticalBlockBorderWrapper"]`).
- `.alta` / `.baixa` / `.neutro` / `.cinza` / `.ciano` / `.alerta` — cor de
  texto. Sempre usar essas em vez de inventar cor nova pra sinal positivo/
  negativo/neutro.
- `.vg-ticker-link` — link clicável de ticker (ex: `?ticker=PETR4`).
- Widgets nativos do Streamlit (botão, input, selectbox, toggle, checkbox,
  radio, metric, tabs) já têm estilo Bloomberg aplicado globalmente — não
  precisa (e não deve) sobrescrever com CSS próprio.

## `ui/design_system.py` — único módulo formal do padrão

- `subtitulo(texto)` — rótulo genérico de subseção dentro de um painel
  (ex: "Riscos", "Filtros", "Research das casas"). Chama `st.markdown`
  direto — só em código que já roda numa sessão Streamlit real.
- `subtitulo_html(texto)` — mesmo visual, mas retorna a string em vez de
  renderizar. Use quando sua função monta um bloco HTML grande e só chama
  `st.markdown` uma vez no final (padrão de `ui/morning_call_tab.py`,
  funções puras testáveis fora de sessão Streamlit).
- `lista_compacta(linhas_html)` — lista com marcador `·`, recebe HTML já
  escapado por quem chama.

## Padrão por aba (CSS local, quando necessário)

Abas com conteúdo rico (Coordenador, Análises, Research, Morning Call)
costumam ter um bloco `_CSS_X`/`_estilo_x()` próprio, injetado via
`st.markdown(f"<style>{...}</style>")`, com classes prefixadas
(`coord-*`, `casas-*`, `mc-*`). Convenções observadas nesse CSS local:

- Badge/chip/pílula: `border: 1px solid var(--borda); border-radius: 3px`.
- Painel/tabela/container maior: `border-radius: 0` (nunca arredondar).
- Fonte de dado/número: `'IBM Plex Mono', monospace`, tabular-nums.
- Tamanhos típicos: rótulo 0.6-0.7rem, corpo 0.76-0.86rem, título de seção
  0.72-0.78rem com `letter-spacing` 0.03-0.09em.

Sempre que faltar algo, estenda `design_system.py`/`style.css` (adicionar,
nunca remover/renomear token ou classe que outra aba já usa).
