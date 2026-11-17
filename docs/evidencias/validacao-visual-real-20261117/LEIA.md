# Validação visual real (C) — WORKSPACE, DCF, SAÚDE DOS DADOS, BUSCA/NAVEGAÇÃO (2026-11-17)

Missão de **captura de evidência**, não de correção — nenhum arquivo de produção
(`ui/*.py`, `data/*.py`, `jobs/*.py`, `app.py`, `style.css`) foi alterado. Só harnesses
novos/copiados e screenshots dentro deste diretório.

Todos os screenshots em 2 larguras (`desktop-1440` e `ipad-1024`), via Playwright real
(Chromium), não `AppTest`.

## WORKSPACE — reaproveitado

`ui/workspace.py` não muda desde `2026-10-19` (commit `0dda4b8`), bem antes da captura
de `2026-11-11` (`docs/evidencias/experiencia-design-system-20261111/`). `style.css`
mudou depois (`2026-11-13`, PR #315), mas só numa regra `@media (max-width:640px)`
restrita a `.st-key-cal_grade_area` (grade do Calendário) — não afeta WORKSPACE em
nenhuma das 2 larguras capturadas. Reaproveitado sem recaptura:
`workspace_desktop-1440.png`, `workspace_ipad-1024.png` (cópia idêntica de
`docs/evidencias/experiencia-design-system-20261111/`).

**Problemas encontrados:** nenhum. Painéis A/B renderizam corretamente (preto/âmbar,
título em âmbar, borda sutil, instrução de drag/resize em cinza/ciano). Nenhuma
sobreposição ou corte em nenhuma das 2 larguras.

## BUSCA/NAVEGAÇÃO — reaproveitado

`ui/busca.py` e `ui/navegacao.py` mudaram em `2026-11-16` (commit `933633d`, PR #318) —
depois da captura de `2026-11-11`/`2026-11-12`. Diff conferido: a mudança é **só
docstring/comentário de auditoria** ("este arquivo não tem lógica duplicada de
sinal/cor/formatação pra migrar pro design system"), zero linha de código executável
alterada em nenhum dos 2 arquivos. `ui/paineis.py` (usado por `harness_busca_paineis.py`)
teve a mesma mudança docs-only no mesmo commit. `ui/design_system.py` não muda desde
`2026-11-06`, antes de ambas as capturas. Reaproveitados sem recaptura:
`busca_paineis_desktop-1440.png`, `busca_paineis_ipad-1024.png`, `nav_desktop-1440.png`,
`nav_ipad-1024.png`, `sidebar_watchlist_desktop-1440.png`,
`sidebar_watchlist_ipad-1024.png` (cópias idênticas de
`docs/evidencias/experiencia-design-system-20261111/`).

**Problemas encontrados:** nenhum. Busca de ativo e painéis A/B lado a lado renderizam
limpos nas 2 larguras. Navegação: abas principais + subabas corretas, quebra pra 2 linhas
em 1024px (MORNING CALL/MAIS descem) sem cortar nenhum rótulo. Sidebar watchlist:
verde/vermelho/cinza (alta/baixa/sem variação) corretos, botões "x" alinhados.

## DCF OPERACIONAL — capturado agora (nunca tinha harness/screenshot)

Harness novo: `harness_dcf.py`. Chama `ui/dcf_operacional.py:render_dcf_operacional()`
de verdade, com premissas **100% mockadas e ficticias** (WACC 12%, crescimento perpétuo
4%, receita-base R$ 12 bi, margem EBIT ~22-24%, cotação atual R$ 11,00 — nunca dado real
de nenhuma empresa) passadas pro motor real de
`data/coordenador_central/dcf_operacional.py` (`calcular_dcf_operacional` +
`calcular_cenarios_dcf_operacional` + `calcular_sensibilidade_dcf_operacional`, sem
nenhuma lógica de cálculo reimplementada no harness). O `st.expander` do módulo é
forçado a abrir (monkeypatch só no harness) pra capturar o conteúdo calculado sem exigir
clique num navegador headless.

Screenshots: `dcf_desktop-1440.png`, `dcf_ipad-1024.png`.

**Problemas encontrados:**

- **CRÍTICO** — a tabela "PROJEÇÃO — DERIVADA DAS PREMISSAS ACIMA" usa `st.dataframe`
  (ver `ui/dcf_operacional.py` linha ~300), que renderiza com **fundo branco/claro**
  (tema padrão do componente nativo do Streamlit, não o preto/âmbar do resto da tela) —
  é a única área clara em toda a aba, quebrando a identidade Bloomberg de forma visível
  nas 2 larguras. Confirmado via screenshot real; `style.css` não tem nenhuma regra de
  cor pro seletor `[data-testid="stDataFrame"]` (só 1 regra de `max-width` num media
  query de mobile, sem relação com cor). `grep` confirma que só 2 arquivos usam
  `st.dataframe` no projeto todo (`ui/dcf_operacional.py` e `ui/analises_tab.py`) — não é
  um padrão já aceito/corrigido em outro lugar, é um gap real.
- **MÉDIO** — em 1024px (iPad), os cartões `st.metric` "VALOR DA FIRMA" e "VALOR DO
  PATRIMÔNIO" cortam o número com reticências (ex.: `R$ 25,915.3 …`, `R$ 22,415.3 …`),
  escondendo o valor real. Em 1440px os mesmos 2 números aparecem completos. "VALOR
  TERMINAL / VP" não corta em nenhuma das 2 larguras (rótulo mais curto).
- Confirmado funcionando corretamente: hero de preço-alvo (âmbar), cartões de cenário
  (pessimista vermelho / base âmbar / otimista verde, cores corretas em ambos os
  sentidos — testado com cotação mock que cruza o preço-alvo de propósito, pra garantir
  que tanto upside quanto downside aparecem no mesmo screenshot), tabela de
  sensibilidade WACC×g (célula base contornada em âmbar, verde/vermelho corretos em
  ambos os sentidos), chip "PREMISSA" tracejado.

## SAÚDE DOS DADOS — capturado agora (nunca tinha harness/screenshot)

Harness novo: `harness_saude_dados.py`. Chama `ui/saude_dados_tab.py:render_saude_dados()`
de verdade; só as 3 funções de LEITURA de `data/saude_dados.py`
(`diagnostico_infraestrutura`, `obter_painel_saude`, `obter_painel_consumo`) são
substituídas via `unittest.mock.patch` por um painel **mockado** com 8 coletores e 3
linhas de consumo fictícios — nenhuma lógica de classificação/HTML de
`ui/saude_dados_tab.py` foi tocada. Respeita a regra do `CLAUDE.md` ("Saúde dos Dados é
frente separada") — zero alteração no módulo real, só leitura substituída no harness.

Screenshots: `saude_dados_desktop-1440.png`, `saude_dados_ipad-1024.png`.

**Confirmado (sem problemas encontrados):**

- As **4 cores de estado** de coletor (`_COR_POR_ESTADO`) aparecem todas distintas e
  corretas: verde/`alta` (NEWS "Coleta OK - dados novos", MERCADO "Coleta OK - sem
  novidades"), âmbar/`alerta` (MACRO (BCB) "Dados desatualizados", RADAR DE QUEDAS
  "Coleta parcial"), vermelho/`baixa` (CVM "Falha de execução", CVM (FCA) "Falha de
  persistência"), cinza/`cinza` (Genial Analisa "Nunca executado", XP Investimentos "Não
  comprovado") — visualmente distintas entre si e do texto neutro (nome do coletor,
  branco/claro).
- As **3 cores de CONSUMO EFETIVO** (`_COR_POR_ESTADO_CONSUMO`) também corretas: verde
  (NEWS Brasil, usado), âmbar (NEWS Internacional, ausente — nunca vermelho, por
  desenho), cinza (NEWS watchlist, sem edição recente).
- "MARKET RESEARCHER — ACHADOS PRIORIZADOS" lista exatamente os 6 coletores com
  `alerta`/`desconhecido` (nunca os 2 em sucesso), ordenados por crítico+gravidade — bate
  com a lógica real de `data/market_researcher.py:achados_qualidade_coletores` (não
  remockada; roda de verdade sobre o painel mockado).
- Número grande de `REGISTROS NOVOS` (128430, item NEWS) renderiza como **"128.430"**
  (separador de milhar BR) — confirma que `design_system.numero_financeiro_html` está
  aplicado e funcionando nessa coluna (migração do PR #319).
- Em 1024px, os cabeçalhos de tabela mais longos ("ÚLTIMO SUCESSO", "REGISTROS NOVOS")
  quebram em 2 linhas e as linhas ficam mais altas, mas nada corta, sobrepõe ou perde
  alinhamento — layout responsivo funcionando.

## O que não foi validado

Walkthrough autenticado (login real, Supabase/Groq de produção) não é viável neste
ambiente — mesma limitação já registrada nas capturas anteriores. Cobertura real: harness
Playwright local por módulo (acima) com dados mockados explícitos.
