# Validação visual real — HOME, MERCADO, MACRO, CALENDÁRIO (2026-11-17)

Missão de CAPTURA DE EVIDÊNCIA (Playwright real, Chromium, não AppTest) para
4 áreas — zero correção de código de produção aplicada nesta frente.

Regra do projeto (CLAUDE.md, regra 7: "sem auditoria repetida") seguida à
risca: antes de capturar qualquer coisa, confirmado via `git log -1 --format=%ci`
se o arquivo de UI real de cada área mudou depois da última captura existente
em `docs/evidencias/`.

## Decisão por área

- **HOME** (`ui/visao_geral.py`, última mudança 2026-11-12) — screenshot mais
  recente é de 2026-11-13 15:02 (`revisao-interface-bloomberg-20261113/`),
  POSTERIOR à última mudança do arquivo. Reaproveitado sem recaptura
  (`home_1440.png`, `home_1024.png`).
- **MERCADO** (`ui/mercado_tab.py`, última mudança 2026-11-06) — mesma lógica,
  screenshot de 2026-11-13 é posterior. Reaproveitado (`mercado_1440.png`,
  `mercado_1024.png`).
- **MACRO** (`ui/macro_tab.py`) — arquivo mudou em 2026-11-13 11:15 (PR #306),
  mas o diff real (`git show 7dab345`) toca SÓ as sub-abas Câmbio e Calendário
  Econômico (reorganização `st.container` → `st.columns`, zero dado novo).
  Indicadores e Juros não foram tocados por aquele PR nem depois.
  - Câmbio e Calendário Econômico: reaproveitados das screenshots "depois"
    já tiradas NO MESMO COMMIT do PR #306
    (`macro_cambio_1440/1024.png`, `macro_calendario_economico_1440/1024.png`).
  - Indicadores e Juros: só existia screenshot 1440 (2026-11-06, código
    inalterado desde então) — capturado FRESCO só para completar o par
    1024, reaproveitando o harness existente sem alteração
    (`macro_indicadores_1440/1024.png`, `macro_juros_1440/1024.png`).
- **CALENDÁRIO** (`ui/calendario_tab.py`, rota MERCADO > Agenda) — arquivo
  mudou em 2026-11-16 10:36 (PR #320, migração do divisor lateral pra
  `design_system.divisor_html()`), DEPOIS da última captura (2026-11-13
  15:02). Recapturado fresco (`calendario_1440.png`, `calendario_1024.png`)
  adaptando o harness já existente (`harness_calendario.py`, cópia exata de
  `revisao-interface-bloomberg-20261113/`, sem alteração — a API mockada
  continua idêntica).

## Avaliação visual (olhando cada imagem)

- **HOME / MERCADO**: identidade Bloomberg preto/âmbar consistente, tipografia
  monoespaçada, tabelas bem alinhadas, nada sobreposto/cortado de forma
  funcionalmente quebrada. Achado pré-existente (já presente nas screenshots
  reaproveitadas, não é regressão): no painel "MAPA DO MERCADO" (treemap),
  os rótulos dos setores menores ("Bancos e Serviços Financeiros", "Bens de
  Capital e Industrial") ficam cortados sem reticências nas bordas direita
  dos retângulos, em 1440 e 1024 — MÉDIO.
- **MACRO > Indicadores**: achado pré-existente (confirmado comparando com
  `macro-bloomberg-20261106/harness_macro_indicadores.png` — já existia antes,
  não é regressão): o título do eixo Y secundário dos gráficos "CURVA PRÉ" e
  "IPCA" renderiza sobreposto/ilegível (texto rotacionado de "% a.a." e
  "IPCA 12 meses (%)" embaralhados um sobre o outro) — MÉDIO.
- **MACRO > Juros**: nenhum problema visível.
- **MACRO > Câmbio / Calendário Econômico**: layout lado a lado confirmado
  (fix do PR #306 funcionando, sem espaço vazio desperdiçado). Nenhum
  problema visível.
- **CALENDÁRIO**: visualmente equivalente à captura anterior ao PR #320 (a
  mudança era cosmética — trocar um border-top avulso pelo helper do design
  system — zero diferença perceptível). Achado pré-existente (já presente na
  captura de 2026-11-13, não é regressão do #320): o rótulo de status
  ("CONFIRMADO"/"ESTIMADO") de alguns dias no grid mensal encosta/é cortado
  pela borda inferior da célula quando o dia tem evento (visível em 1440 e
  1024) — MENOR.

Nenhum problema CRÍTICO encontrado em nenhuma das 4 áreas.
