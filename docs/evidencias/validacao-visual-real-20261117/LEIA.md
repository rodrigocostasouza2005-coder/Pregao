# Validação visual real — 2026-11-17

Missão de captura de evidência (Playwright real, Chromium, sem AppTest) —
nenhum arquivo de produção (`ui/*.py`, `data/*.py`, `jobs/*.py`, `app.py`,
`style.css`) foi alterado em nenhuma das duas frentes abaixo. Antes de
capturar, cada área teve seu arquivo de UI real comparado por
`git log -1` contra a data da última captura já salva em
`docs/evidencias/` (regra "sem auditoria repetida" do `CLAUDE.md`): só
recapturamos o que de fato mudou desde então. Duas sessões trabalharam em
paralelo (worktrees isolados) sobre áreas diferentes do mesmo app, por
isso este arquivo cobre as 8 áreas juntas.

---

# Frente B — RESEARCH / NOTÍCIAS / COMITÊ / RADAR

## RESEARCH (`ui/research_tab.py`, subaba Casas de Análise)

**Fresco.** `research_1440.png` / `research_1024.png`, via
`harness_research.py` (novo — não existia harness salvo pra RESEARCH
antes, só os screenshots soltos em
`docs/evidencias/research-area-20261023/`, sem o `.py`). Recapturado
porque `ui/research_tab.py` mudou em 2026-11-06 (commit `773f827`),
depois da última captura (2026-10-23). Chama `render_casas_analise`
direto, com `preparar_leitura`/`ultimas_coletas_formatadas`/
`obter_status_casas`/`cobertura_cruzada_casas`/
`_premissas_por_tickers_cacheado`/`obter_noticias` monkeypatchados com
dado mockado plausível (nunca dado real).

Achados: nenhum problema real. Pills de filtro (Casa/Tipo/Ticker/
Recomendação/Período), busca textual, cards de tese (badge de
disponibilidade, recomendação/preço-alvo, resumo gerado por IA) e o
expander fechado "COBERTURA E SAÚDE DAS CASAS" renderizam limpos, sem
sobreposição/corte, em 1440px e 1024px. Monoespaçado e paleta âmbar/preto
consistentes com o resto do app.

## NOTÍCIAS (`ui/news_tab.py`, subaba Empresas — feed editorial)

**Fresco.** `noticias_1440.png` / `noticias_1024.png`, via
`harness_news.py` (novo, adaptado de
`docs/evidencias/news-card-redesign-20261019/harness_cards.py` — aquele
só exercitava o componente de card isolado; este chama o PONTO DE
ENTRADA real, `render_news`, pro mesmo padrão de captura "landing" usado
nas outras 3 áreas). Recapturado porque `ui/news_tab.py` mudou em
2026-11-06 (commit `3e33101`), depois da última captura (2026-10-19).

Achado de harness (não é bug de produção): `render_news` é
`@st.fragment` e chama `_renderizar_feed_editorial` internamente, que
TAMBÉM é `@st.fragment` — em bare mode (sem sessão real do Streamlit),
uma função `@st.fragment` chamada "normal" não executa o corpo (mesmo
achado já documentado em `feedback_streamlit_fragment_bare_mode.md`).
Resolvido no harness substituindo a referência interna pela versão
`.__wrapped__` antes de chamar `render_news.__wrapped__`.

Achados de UI: nenhum problema real. Cards (selo/score, veículo, data,
tickers, resumo "gerado por IA", link "abrir") alinhados e sem
sobreposição em 1440px e 1024px; pills de Ticker/Selo responsivos.

## COMITÊ (`ui/coordenador_tab.py`, Visão Geral)

**Reaproveitado** de
`docs/evidencias/agente-d-redesign-estrutural-20261112/
visao_geral_1440_depois.png` e `visao_geral_1024_depois.png` →
`comite_1440.png` / `comite_1024.png`. Justificativa: `ui/
coordenador_tab.py` não mudou depois do commit que gerou essa captura
(`c16029b`, 2026-11-12 20:35) — é a mesma versão de código.

Achado (já documentado na missão original, não é regressão desta
validação): em 1024px, a coluna "RESUMO/ERRO" (tabela ÚLTIMAS EXECUÇÕES
AGENDADAS) e a tabela ANÁLISES SOB DEMANDA RECENTES truncam texto na
borda direita sem indicação de rolagem horizontal visível no
screenshot estático — mesmo padrão de degradação aceito em outras
tabelas do app (`.coord-tabela-wrap`), confirmado no LEIA.md original.
MENOR, nada novo encontrado.

## RADAR (`ui/radar_tab.py`, subaba Alertas)

**Reaproveitado** de
`docs/evidencias/agente-a-redesign-estrutural-20261112/
depois_alertas_1440.png` e `depois_alertas_1024.png` →
`radar_1440.png` / `radar_1024.png`. Justificativa: `ui/radar_tab.py`
teve sua última mudança no commit que gerou essa mesma captura
(`41ad09b`, 2026-11-13 02:16) — é a mesma versão de código. As demais
subabas de RADAR (Oportunidades, Carteiras Recomendadas, Acompanhamento)
também já têm captura corrente nas mesmas duas pastas de origem — não
duplicadas aqui pra não repetir auditoria já feita.

Achados: nenhum problema real. Faixa RESUMO, tabela de alertas e tabela
MONITORADOS AGORA alinhadas, sem sobreposição/corte em 1440px e 1024px.

### Resumo — Frente B

| Área | Estado | Fresco/Reaproveitado |
|---|---|---|
| RESEARCH | nenhum problema real | fresco |
| NOTÍCIAS | nenhum problema real | fresco |
| COMITÊ | MENOR (truncamento já documentado, não é regressão) | reaproveitado |
| RADAR | nenhum problema real | reaproveitado |

---

# Frente A — HOME / MERCADO / MACRO / CALENDÁRIO

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

### Resumo — Frente A

Nenhum problema CRÍTICO encontrado em nenhuma das 4 áreas.

---

## Consolidado — todas as 8 áreas

Nenhum problema CRÍTICO encontrado em nenhuma das 8 áreas (RESEARCH,
NOTÍCIAS, COMITÊ, RADAR, HOME, MERCADO, MACRO, CALENDÁRIO). Achados MÉDIO/
MENOR encontrados são todos pré-existentes (não introduzidos por nenhuma
das duas frentes) e já estavam documentados em missões anteriores onde
aplicável. Nenhum arquivo de produção foi tocado por nenhuma das duas
frentes — diff de ambas restrito a
`docs/evidencias/validacao-visual-real-20261117/`.
