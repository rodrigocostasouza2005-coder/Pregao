# Auditoria 360° + Redesign — PREGÃO

**Data:** 2026-10-18
**Branch:** `audit/redesign-360-20261018` (a partir de `main` em `9a3d2d0`)
**Autor:** Claude (Sonnet 5), a pedido do Rodrigo
**Escopo:** auditoria completa de todas as abas + Radar + performance/navegação (pedido original, seções 1-16)

## Como ler este documento

Este relatório é **honesto sobre o que já está bem resolvido**. O Pregão não é um
produto greenfield: é um terminal com histórico extenso de auditorias reais
(visuais, de performance, do Radar) já executadas em sessões anteriores, com
screenshots Playwright, bugs reais encontrados/corrigidos e testes de regressão
— tudo documentado em `PROGRESSO.md`/`CHANGELOG.md`/`BACKLOG.md`. Não vou reclassificar
como "achado novo" algo que já foi investigado e resolvido. Onde o código já está
sólido, digo isso explicitamente, com a evidência que confirma.

Os achados **novos** desta sessão (confirmados por leitura direta do código em
`main`, não por suposição) estão marcados com evidência `arquivo:linha`.
Os que viraram correção de verdade nesta sessão estão marcados **[IMPLEMENTADO]**
com o commit correspondente.

---

## 1. Inventário real (matriz de cobertura)

Estrutura real (não presumida): navegação por seções (`app.py:270-291`), onde **só a
seção ativa executa** — diferente de `st.tabs()`, que roda o conteúdo de todas as
abas em toda rerun. 11 seções visíveis ao usuário comum + 2 restritas a admin
(`SISTEMA`, `SAÚDE DOS DADOS`, gate por e-mail em `config.obter_emails_admin()`).

| Tela | Arquivo | Componentes principais | Objetivo | Estado |
|---|---|---|---|---|
| VISÃO GERAL | `ui/visao_geral.py` | Mercado agora (7 cards), gráfico Ibovespa, altas/baixas, setorial, mercados globais, market news, minha watchlist — via `ui/workspace.py` (drag/resize) | Entender o mercado em ~10s | Maduro; 1 achado corrigido nesta sessão (watchlist) |
| RADAR | `ui/radar_tab.py` + `data/radar_quedas.py` + `data/radar.py` | Radar de Quedas (Cobertura/Monitorados/Alertas) + Inteligência da Watchlist (Mudanças de Tese/Valuation/Catalisadores/Risco/Evidências/Copiloto) | Sinalizar o que mudou, onde investigar, o que pode dar errado | **Redesenhado hoje mais cedo** (commit `3084b4f`, mesma sessão de trabalho, ver seção 4 |
| EQUITY | `app.py:498-927` | Preços, indicadores, gráfico (candle/linha/área + MMs), comparativo da watchlist, notícias do ticker, CVM do ticker | Analisar 1 ativo em profundidade | Maduro |
| MACRO | `ui/macro_tab.py` | Resumo (Selic/CDI/IPCA/juro real), Curva Pré, IPCA, Selic×CDI, Cenário Global | Contexto macroeconômico | Maduro, bem documentado |
| RESEARCH | `ui/research_tab.py` + `data/research/` | Carteiras recomendadas, relatórios por casa, lives (Genial), watchlist com contexto | Acompanhar recomendações de research | Cobertura real parcial (ver seção 5) |
| NEWS | `ui/news_tab.py` (1427 linhas) | Feed editorial com cards+resumo IA, modal de notícia, feed "wire" denso | Notícias de mercado | Maduro; 1 achado de hierarquia de clique (ver seção 6) |
| TOP MERCADO | `ui/top_mercado_tab.py` | Ranking de notícias por importância estimada (BR/Internacional) | Notícias mais relevantes do dia | Reaproveita 100% o componente de NEWS |
| MERCADO | `ui/mercado_tab.py` | Termômetro, altas/baixas, mais negociados, setorial, treemap, globais | Visão ampla do pregão | Maduro, com 2 achados de navegação (ver seção 6) |
| CVM | `ui/cvm_tab.py` | Fato relevante/comunicado/resultados/proventos, modal com resumo + link oficial | Documentos oficiais | Maduro |
| CALENDÁRIO | `ui/calendario_tab.py` | Agenda de resultados corporativos (CONFIRMADO/ESTIMADO/PRAZO CVM), grade mensal | Catalisadores de data | Maduro, 1 achado menor (ver seção 6) |
| CONFIG | `app.py:986-1201` | Tema/densidade/fonte/formato, atualização automática, abas visíveis, ordem/visibilidade de painéis, casas de research, diagnóstico de fontes (admin) | Preferências | Maduro |
| SISTEMA (admin) | `ui/sistema_tab.py` | CHANGELOG/PROGRESSO/MANUAL em abas | Documentação interna | Simples, sem problema |
| SAÚDE DOS DADOS (admin) | `ui/saude_dados_tab.py` | Status real por coletor (última tentativa/sucesso/registros), diagnóstico de infraestrutura | Monitorar coletores | **Referência de honestidade** — ver seção 5.C |

**Componentes compartilhados:** `ui/busca.py` (busca global), `ui/paineis.py` +
`ui/workspace.py` (2 sistemas de layout de painel coexistindo — ver seção 3),
`ui/graficos.py` (chave de zoom de gráfico Plotly), `style.css` (1096 linhas),
`config.py` (temas/densidades/fontes/cadastro de ativos).

**Jobs (fora da UI, mas no escopo por afetarem o que o usuário recebe):**
`jobs/morning_call.py` + `jobs/morning_call_pdf.py` + `data/morning_call_editorial.py`
(briefing diário por e-mail/PDF), `jobs/radar_quedas.py` (worker do Radar).

**Testes:** 49 arquivos, 776 testes (baseline desta sessão, depois dos
testes novos — ver seção 9), todos via `pytest`, sem Playwright/browser real
no CI (ver seção 12, limitações).

---

## 2. Avaliação geral

O Pregão já é, em boa parte, o que o pedido original descreve como objetivo: um
terminal denso, consistente, com identidade visual própria (âmbar/laranja sobre
fundo escuro, `IBM Plex Mono`), que **não inventa dado nem mascara falha de
coletor**. Isso não é incomum em auditorias — é resultado direto de um padrão de
trabalho raro e visível no histórico: cada mudança visual documentada cita
"achado real", confirmado por Playwright, nunca por suposição; estados de erro/
vazio/desatualizado são tratados caso a caso, nunca com "—" genérico escondendo
o motivo; a aba SAÚDE DOS DADOS existe exatamente para impedir indicador falso de
sucesso.

Isso muda o tipo de achado que uma auditoria nova deveria procurar: não "este
produto é inconsistente e precisa de um design system do zero" (já tem um,
implícito em `config.TEMAS`/`style.css`, aplicado com disciplina), mas sim:
(a) pontos específicos onde a disciplina do resto do produto ainda não chegou;
(b) lacunas de navegação/clique que a seção 16 do pedido original pede
explicitamente; (c) dívida técnica já **admitida no próprio código** (comentários
"achado real (auditoria X): ainda não corrigido", constantes que deveriam estar
em `config.py` mas não foram movidas por conflito de sessão, etc.).

---

## 3. Sistema de layout de painel: 2 mecanismos coexistindo

`ui/paineis.py` (popover "⚙" com tamanhos fixos 1/4-1/2-3/4-FULL) e
`ui/workspace.py` (drag/resize livre, JS via `st.iframe`) **não são dois sistemas
concorrentes aleatoriamente** — é uma migração em andamento: MERCADO, MACRO e
VISÃO GERAL já usam `workspace.renderizar_workspace` (confirmado por grep:
`ui/mercado_tab.py:574`, `ui/macro_tab.py:432`, `ui/visao_geral.py:248`); as
demais abas não usam nenhum sistema de registro de painel (layout fixo).

O que **é** uma redundância real: CONFIG (`app.py:1075-1092`) ainda expõe
`paineis.controle_ordem_config`/`controle_visibilidade_config` para essas 3 abas
— um multiselect global de ordem/visibilidade — **ao lado** do popover "⚙" próprio
de cada painel no workspace (que já faz RESTAURAR/OCULTAR individualmente). Dois
caminhos para a mesma ação, não documentados um pro outro.

- **P2.** Redundância de controle (ordem/visibilidade duplicada entre CONFIG e o
  popover "⚙" do workspace) nas 3 abas migradas. **Risco de implementar agora:**
  médio — o popover por painel não tem hoje uma forma de REORDENAR (só
  restaurar/ocultar), então remover o controle de CONFIG tiraria uma
  funcionalidade real sem substituto. Recomendação: não remover, documentar em
  CONFIG que o ajuste fino de tamanho/posição é feito direto no painel.
- `ui/paineis.py:26-32` tem docstring desatualizada (ainda lista VISÃO GERAL
  entre as abas "monolíticas sem registro de painel" — não é mais verdade desde
  a migração para `workspace`). **P3**, cosmético, comentário apenas.
- `ui/workspace.py` é um sistema MVP (a própria docstring usa essa palavra, linha
  2) validado manualmente em produção (3 bugs reais de drag/resize encontrados e
  corrigidos via harness Playwright dedicado, ver `PROGRESSO.md`) mas **sem
  nenhum teste automatizado** (`tests/test_workspace*.py` não existe). **P2** —
  risco de regressão silenciosa em qualquer mudança futura de `style.css`/
  `ui/paineis.py` que esse sistema reaproveita.

---

## 4. Auditoria do Radar — já redesenhado nesta mesma sessão de trabalho

Importante: o Radar foi reformulado **antes** desta auditoria, no mesmo dia
(commit `3084b4f`, "revisão do Radar de Quedas — tabelas densas, ativos
monitorados e pregão real", com 9 testes novos/atualizados e comparação
antes/depois em `docs/evidencias/radar-20261018/`). O estado atual já cobre a
maior parte do que a seção 5 do pedido original pede:

| Pedido original (seção 5) | Estado real (`ui/radar_tab.py:406-641`, `data/radar_quedas.py`) |
|---|---|
| Separar sinal / contexto / evidência / estado operacional da fonte | Sim: COBERTURA (estado da fonte: ATUALIZADA/DESATUALIZADA/INDISPONÍVEL) → MONITORADOS AGORA (estado do ativo: ALERTA/ATENÇÃO/NORMAL/SEM_COTAÇÃO) → ALERTAS REGISTRADOS (histórico, com status de e-mail) — 3 blocos, sem mistura |
| Dedup de alerta, sem reaparecer à toa | `registrar_alerta` (idempotência ticker+pregão) + `_mesma_cotacao` (evita duplicar em feriado quando o Yahoo repete a cotação do pregão anterior, achado real documentado em `data/radar_quedas.py:189-204`) |
| Distinguir falha de coleta / bloqueio externo / dado antigo / ausência legítima | `resumo_fontes_vigentes` + `_tabela_cobertura_html`: XP/BTG explicitamente citadas como "sem carteira recomendada pública acessível" (não "sem dado", nota em `ui/radar_tab.py:574-577`); `_desatualizada` (72h) separado de `_carteira_expirada` (40 dias) — dois níveis de "não confiar mais nisso" |
| Rastreabilidade da fonte | Links reais por alerta (`fontes`, só URLs `https://`) |
| Não confundir queda de preço com "está barato" | `_secao_valuation`/Valuation Radar continua separado, com nota "sem P/L/P-VP válido pra empresa com prejuízo..." — Radar de Quedas não afirma nada sobre valuation |

**O que não está nesse redesenho de hoje (pré-existente, não regressão):**
coletores estruturados só para Genial Analisa e Safra Corretora — XP/BTG seguem
bloqueados por borda Akamai (`data/radar_quedas.py:4-12`, confirmado, não é
"card decorativo", é ausência honesta).

### Achados novos confirmados nesta auditoria

- **P1 — Falsa affordance nos tickers das tabelas densas.** `.rq-ticker` (
  `ui/radar_tab.py:103`) usa `color: var(--destaque); font-weight: 700`, **o
  mesmo tratamento visual** usado pelo botão de ticker clicável do ranking de
  MERCADO (`ui/mercado_tab.py:210-214`) — mas aqui é `<span>` dentro de HTML
  puro, sem destino. Confirmado em MONITORADOS AGORA (`:492`) e ALERTAS
  REGISTRADOS (`:523`). **Não implementado nesta sessão** — ver justificativa
  abaixo.
  - *Por que não corrigi agora:* essas tabelas foram desenhadas **hoje, horas
    antes**, especificamente para resolver densidade (ver mensagem do commit
    `3084b4f`: "tabelas densas" era a correção de um problema anterior de
    colunas largas demais). Convertê-las de volta para `st.columns`+`st.button`
    por linha (único jeito de ter um botão real dentro de uma lista do
    Streamlit) reintroduziria exatamente esse problema. É uma mudança real,
    mas arriscada de fazer sem revisão visual do Rodrigo — registrada aqui como
    pendência clara em vez de arriscar regressão num componente recém-ajustado.
    Alternativa de menor risco pra próxima sessão: manter a tabela densa e
    tornar a *linha inteira* clicável via link `<a>` por cima da `<tr>` com
    `?abrir_ticker=X` lido por `app.py` (mesmo princípio do `_ir_com_ticker`,
    nunca implementado/validado nesta sessão — não arrisquei subir sem testar).

---

## 5. Auditoria de dados, notícias e indicadores financeiros

### A. RESEARCH — status real por casa (confirmado em `data/research/__init__.py`)

| Casa | Coletor | `tentar_coleta_automatica` | Status real |
|---|---|---|---|
| Genial Analisa | Sim (JSON `__NEXT_DATA__`) | **False** | Depende de `coletor_local.py` rodando fora do Streamlit Cloud |
| XP Investimentos | Sim | **False** | Bloqueio Akamai documentado (403, header `edge-rsp-blk`) |
| Genial (Lives) | Sim (RSS YouTube) | — | Única 100% ao vivo |
| BTG Research | — | `disponivel: False` | Nem aparece como card — 8 tentativas reais documentadas (`ERR_HTTP2_PROTOCOL_ERROR`/timeout) |
| Safra, Itaú BBA, BB, Santander, Agora/Bradesco, Inter | — | — | "ainda não investigadas" (comentário explícito) |

Nenhuma casa aparece como card decorativo sem dado real — o que não funciona
simplesmente não aparece no filtro (BTG). Isso é o comportamento correto pedido
na seção 5.C do briefing original.

- **P1.** RESEARCH não diferencia visualmente recomendação vigente de antiga —
  mesmo layout, só a data muda (`ui/research_tab.py:230-258`); histórico de
  preço-alvo só existe (hardcoded) para Genial Analisa, então comparar o mesmo
  ticker entre casas exige ler linha por linha. **Não implementado** (mudança de
  estrutura de dado, não só de apresentação — fora do escopo seguro desta sessão).
- **P2.** RESEARCH mistura dois padrões de interação no mesmo feed: itens LIVE
  abrem `st.dialog`, itens normais (AÇÕES/MACRO) só expandem texto inline ou
  mostram botão "RESUMIR" (`ui/research_tab.py:267-309`).
- **P2.** CVM: resumo por IA no modal não tem rótulo visual "gerado por IA"
  diferenciando-o do texto oficial (a distinção existe no código/comentário, não
  na tela) — mesmo padrão de risco do achado P0 corrigido no Morning Call (ver
  seção 7).

### B. Morning Call — achado P0 confirmado e corrigido

**[IMPLEMENTADO]** commit `ba0f620`. `data/morning_call_editorial.py:_cards_empresas`
aplicava a tag `FATO` ao card inteiro mesmo quando `resumo` (texto sintetizado
por IA via `data/news.py:obter_resumos_prontos`) substituía o título literal no
PDF — confirmado lendo `jobs/morning_call_pdf.py:588-590`
(`texto = card.get("resumo") or card.get("titulo")`, mas a tag chip desenhada
era sempre a de `card.get("tag")`, que ficava `FATO`). Um briefing diário real,
por e-mail e PDF, rotulando síntese de IA como fato apurado — exatamente a
mistura que a missão original do módulo (ver docstring) diz que nunca pode
acontecer.

Corrigido com nova tag `SÍNTESE` (cor própria no PDF, nota de limitações
atualizada), aplicada só quando `resumo` existe; card sem resumo continua
`FATO` normalmente. 2 testes novos (`tests/test_morning_call_editorial.py`)
cobrindo os dois casos.

O e-mail em texto simples (`jobs/morning_call.py`) **não tem esse bug** — a
seção EMPRESAS E SETORES ali é só lista de manchetes, sem campo `resumo`
anexado (pipeline totalmente separado do PDF).

### C. SAÚDE DOS DADOS — referência de honestidade, não achado

Mencionado aqui porque a seção 5.C do pedido pede explicitamente para não
aceitar card verde que mascara falha. `ui/saude_dados_tab.py` já faz o oposto
do que a auditoria deveria temer: mostra `ultima_tentativa_em`/
`ultimo_sucesso_em`/`registros_novos` por coletor, distingue
`NAO_COMPROVADO`/`NUNCA_EXECUTADO` (cinza) de `FALHA_EXECUCAO`/
`FALHA_PERSISTENCIA`/`FONTE_INDISPONIVEL` (vermelho), e diferencia "tabela
ausente" de "erro de credencial" de "erro desconhecido" no diagnóstico de
infraestrutura. Nenhum achado aqui.

---

## 6. Problemas de navegação / clique (seção 16 do pedido)

### A. Troca de abas — já rápida por design

Confirmado em `app.py:270-274`: a navegação principal **não é** `st.tabs()` —
é um `if secao_atual == "X":` por seção, então só a seção ativa executa
(`st.tabs()` roda o conteúdo de todas as abas em toda rerun e só esconde por
CSS). Cotações usam `st.fragment(run_every=...)` isolando o custo de
atualização automática do resto da página (ticker tape, watchlist, painéis de
preço/comparativo em EQUITY). Cotações em lote (`obter_cotacoes_lote`) evitam
N+1 — documentado como corrigido em várias frentes (`app.py`, `ui/visao_geral.py`,
`ui/mercado_tab.py`). TTLs de cache calibrados por volatilidade do dado (30s
cotação de índice, 90s painéis de mercado, 4-6h macro, 24h composição B3).

Nenhum achado de performance real aqui — é a área mais madura do produto nesse
quesito. Único ponto observado sem evidência de impacto real: MERCADO/MACRO não
usam `st.fragment` (mudar um filtro local rerenderiza a aba inteira), mas como
os dados já são cacheados, o custo extra é renderização pura, não rede/banco —
não registrado como achado por falta de medição que comprove impacto perceptível
(este ambiente não tem acesso a Yahoo/Supabase para medir end-to-end, ver
seção 12).

### B. Notícias — clique já bem resolvido, com 1 ressalva de mobile

`ui/news_tab.py`: título é um `st.button` estilizado como link que abre
`@st.dialog` interno (`_abrir_card`); um ícone "↗" separado, como `<a target=
"_blank">` real, abre a matéria original — diferenciação clara entre "ver
resumo aqui dentro" e "abrir no site de origem", exatamente como o pedido
original especifica. Reaproveitado de forma consistente em EQUITY
(`render_news_ticker`) e RADAR (`abrir_card_noticia`).

- **P2.** No card editorial (feed principal de NEWS), o link "↗ abrir" fica
  embutido na mesma linha compacta de metadados do botão-título
  (`.news-item-meta`, `ui/news_tab.py:1087`) — área pequena, pouco espaçamento
  vertical entre os dois controles. Risco de clique acidental maior em mobile.
  **Não implementado** (ajuste fino de CSS que merece confirmação visual antes
  de mexer num componente usado em 3 lugares).
- **P2.** Dois estilos de card coexistem (wire denso vs. editorial) com
  truncamento de título inconsistente (92 caracteres no wire, sem truncar no
  editorial).

### C. Cards sem destino real — 1 corrigido, outros documentados

**[IMPLEMENTADO]** commit `53369ad`. Painel MINHA WATCHLIST (VISÃO GERAL): ticker
tinha a mesma cor/peso (`var(--destaque)`, 600) do padrão "isto é clicável" já
estabelecido no ranking de MERCADO, mas sem nenhum `on_click` — corrigido para
`st.button` real com `on_click=_ir_para_equity` (mesmo callback já usado no
ranking, importado — este arquivo já reaproveita funções "privadas" de
`ui.mercado_tab`, prática já estabelecida no próprio código,
`ui/visao_geral.py:23` antes desta mudança). Validado com Playwright (harness
isolado, sem login): botão existe, clique não gera erro de console, 2
breakpoints. Durante a própria correção, um bug real de mobile foi encontrado
(linha de preço sobrepondo o botão da linha seguinte, abaixo de 640px) e
corrigido antes do commit — ver `docs/evidencias/visao-geral-watchlist-20261018/`.

Outras instâncias confirmadas do mesmo padrão (ticker com `color:var(--destaque)`
sem destino), **documentadas mas não corrigidas** por envolver tabelas HTML
densas onde não há como embutir um widget Streamlit real sem reestruturar o
componente (mesmo trade-off do achado do Radar, seção 4):

- `.rq-ticker` no Radar (MONITORADOS AGORA / ALERTAS REGISTRADOS) — **P1**,
  justificativa completa na seção 4.
- "Mais Negociados" e treemap em MERCADO (`ui/mercado_tab.py`) — **P2**, ranking
  de Altas/Baixas na mesma aba já resolve o caso de uso mais comum (ver ativo e
  abrir em EQUITY); treemap é visão agregada, não lista de tickers individual.
- Cards "Cenário Global" em MACRO — **P3**, são ativos sem página EQUITY própria
  (ouro, Brent, WTI, câmbio) — não há destino real possível hoje, então a
  recomendação aqui é justamente *não* dar a impressão de clicável (já não dão
  — não usam a convenção destaque+bold).
- Tabela comparativa da watchlist dentro de EQUITY (`app.py:555`, dentro de
  `_painel_comparativo_watchlist`) — **P2**, caso diferente dos acima: aqui a
  troca poderia ser *na própria aba* (trocar qual ticker está selecionado no
  segmented_control acima), sem navegação entre seções — mecanismo mais simples
  de implementar com segurança numa próxima sessão.

### D. Acesso rápido / atalhos de teclado

**[IMPLEMENTADO]** commit `bb0c7ec`. O rótulo "CTRL K" ao lado da busca global
(`app.py:361-362`, `col_ctrlk`) já existia visualmente, mas não tinha nenhum
keybinding real. Implementado via `st.iframe` com script JS (mesma técnica já
validada em produção por `ui/workspace.py`, acesso a `window.parent.document`,
mesma origem) — um `keydown` global que foca o `<input>` real da busca (seletor
`[class*="st-key-busca_global_ticker"] input"`, mesma convenção de classe que o
projeto já usa em `ui/workspace.py:354`). Validado com Playwright num harness
isolado antes de integrar: Ctrl+K foca o campo, digitar abre as sugestões
normalmente, sem erro de console.

Busca global por ativos/notícias/seções já existe (`ui/busca.py`, universo B3 +
BDRs + watchlist) — não é um achado, já atende à seção 16.D.

Não implementado (fora do escopo de uma correção segura nesta sessão): voltar à
tela anterior preservando filtro/posição ao navegar por um card — hoje trocar de
seção via `_ir_com_ticker`/`_ir_para_equity` perde a posição de scroll/filtro de
onde o usuário veio (comportamento padrão de qualquer troca de aba no app, não
uma regressão introduzida agora).

---

## 7 e 8. Direção de arte e design system — já existe, documentado aqui pela primeira vez de forma centralizada

O Pregão já tem um design system funcional, só nunca documentado num lugar só.
Consolidado abaixo a partir do código real (`config.py`, `style.css`):

**Paleta (4 temas, `config.TEMAS`):** AMBAR (padrão, fundo preto + acento
`#FFA028`), FÓSFORO (verde `#33FF66`), AZUL (`#4FC3F7` sobre `#00111A`), CLARO
(único tema claro, `#F5F5F0`/`#B36B00`). Todos compartilham a mesma estrutura de
7 chaves (`fundo`/`painel`/`borda`/`destaque`/`alta`/`baixa`/`neutro`/`cinza`/
`ciano`) — cores semânticas (alta=verde, baixa=vermelho) fixas entre temas,
só o acento de identidade muda. Um teste de regressão já existe garantindo que
nenhum hex hardcoded sobrevive fora desses tokens
(`tests/test_mercado_ranking_ui.py:test_4_sem_cores_hardcoded_fora_dos_tokens_de_tema`).

**Tipografia:** `IBM Plex Mono` em tudo (`style.css:3,50`) — decisão deliberada
de terminal financeiro, não uma lacuna. Escala de densidade (`config.FONTES`:
P/M/G = 0.78/0.9/1.05rem) e densidade de padding (`config.DENSIDADES`:
COMPACTA/CONFORTÁVEL) configuráveis pelo usuário, aplicadas via variável CSS
`--fonte-base`/`--padding-painel`.

**Espaçamento/densidade:** não uniforme por decisão — cada tela define seus
próprios tamanhos de fonte inline (ex.: 0.65rem a 0.85rem em RESEARCH/CVM,
listados na seção 9). Essa é a maior lacuna real de um "design system" formal:
não existe uma escala tipográfica nomeada (ex.: `--fs-caption`/`--fs-body`/
`--fs-valor-destaque`) reutilizada por `class`, cada tela reimplementa o próprio
valor em `style=""` inline.

- **P2 — Recomendação de design system (não implementada, proposta pra próxima
  sessão):** extrair uma escala de 5-6 tamanhos nomeados (`--fs-micro`,
  `--fs-caption`, `--fs-body`, `--fs-valor`, `--fs-titulo-painel`) para
  `style.css:root`, e trocar os `style="font-size:0.7Xrem"` inline por classes
  utilitárias (`.fs-caption`, etc.) em RESEARCH/CVM primeiro (onde a variação é
  maior, 9+ tamanhos distintos sem relação aparente). **Risco de fazer tudo de
  uma vez:** alto — toca praticamente todo arquivo de UI; recomendo fazer 1 aba
  por vez, com confirmação visual do Rodrigo entre cada uma (ver nota abaixo).

**Nota sobre ritmo de mudança visual:** uma sessão anterior já registrou
explicitamente (`PROGRESSO.md`, linha ~2303) a decisão de **não** fazer
"formatação visual" pura sem o ciclo de confirmação direta do Rodrigo
(prioridade ESTRUTURA > FUNCIONALIDADE > PERFORMANCE > CONSISTÊNCIA > VISUAL),
por já ter acontecido de mudanças estéticas feitas sem esse ciclo precisarem
ser revertidas. Esta auditoria respeita essa decisão: as correções implementadas
nesta sessão são estruturais/funcionais (rótulo de dado incorreto, clique sem
destino, atalho ausente) — mudanças cosméticas amplas (ex.: aplicar a escala
tipográfica acima em todas as 13 telas) ficam como **proposta**, não como
código já commitado, para o Rodrigo revisar com screenshots antes/depois antes
de um rollout maior.

**O que preservar (já está certo, não mexer):** fundo escuro + acento âmbar
seletivo (nunca cor forte em tudo); divisórias finas em vez de card pesado em
toda parte (confirmado — a maioria das telas usa `border-top` de 1-2px, não
sombra/gradiente); ausência de emoji como ícone de interface (confirmado via
leitura de todos os arquivos de UI — os únicos símbolos usados são `●`/`↗`/`▣`/
`✓`/`⚙`, nunca emoji colorido).

---

## 9. Mudanças sugeridas por tela (resumo consolidado)

| Tela | Implementado nesta sessão | Documentado, não implementado |
|---|---|---|
| VISÃO GERAL | Ticker da watchlist clicável (P1) + bug de mobile corrigido | — |
| RADAR | — (já redesenhado antes desta auditoria) | `.rq-ticker` sem destino (P1) |
| Header global | Atalho CTRL K real (P2) | Tabela comparativa de EQUITY com ticker clicável *na própria aba* (P2) |
| Morning Call (PDF/e-mail) | Tag FATO incorreta em resumo de IA (P0) | — |
| RESEARCH | — | Vigente vs. antigo sem diferenciação visual (P1); 2 padrões de interação no mesmo feed (P2); tipografia ad-hoc (P2) |
| CVM | — | Resumo de IA sem rótulo visual (P2) |
| NEWS | — | Link "↗ abrir" perto demais do botão-título em mobile (P2); 2 estilos de card coexistindo (P2) |
| MERCADO | — | Mais Negociados/treemap sem clique (P2) |
| MACRO | — | Nenhum achado de prioridade alta |
| CALENDÁRIO | — | Mesma célula do dia não diferencia evento passado/futuro (P3) |
| design system (global) | — | Escala tipográfica nomeada (P2, proposta — ver seção 8) |

---

## 10. Priorização (impacto × risco × esforço)

| # | Achado | Prioridade | Esforço | Risco de implementar | Status |
|---|---|---|---|---|---|
| 1 | Morning Call: síntese de IA rotulada como FATO | **P0** | Baixo | Baixo (isolado, testado) | **Feito** |
| 2 | Watchlist (VISÃO GERAL): ticker sem destino | **P1** | Baixo | Baixo (isolado, testado, validado visualmente) | **Feito** |
| 3 | CTRL K decorativo, sem atalho real | P2 | Baixo | Baixo (validado com Playwright antes de integrar) | **Feito** |
| 4 | Radar: `.rq-ticker` sem destino nas tabelas densas | P1 | Médio | Médio (componente redesenhado horas antes; densidade em jogo) | Documentado |
| 5 | RESEARCH: vigente vs. antigo sem diferenciação | P1 | Médio-alto | Médio (mudança de estrutura de dado) | Documentado |
| 6 | Design system: escala tipográfica nomeada | P2 | Alto (toca ~13 telas) | Alto sem ciclo de confirmação visual | Proposta |
| 7 | `ui/workspace.py` sem teste automatizado | P2 | Médio | — (é trabalho de teste, não de produto) | Documentado |
| 8 | CONFIG × popover "⚙": controle de painel duplicado | P2 | Baixo | Médio (remover sem substituto quebra reordenar) | Documentado |
| 9 | CVM/RESEARCH: resumo de IA sem rótulo visual | P2 | Baixo | Baixo | Documentado |
| 10 | NEWS: área de clique "↗ abrir" pequena em mobile | P2 | Baixo | Baixo | Documentado |
| 11 | Demais achados P2/P3 da seção 9 | P2/P3 | Variável | — | Documentado |

---

## 11. Dependências técnicas e riscos de regressão

- Toda mudança em `ui/mercado_tab.py:_ir_para_equity` afeta agora **2** chamadores
  (`ui/mercado_tab.py` ranking + `ui/visao_geral.py` watchlist) — mudança de
  assinatura precisa considerar os dois.
- `ui/workspace.py` não tem teste automatizado — qualquer mudança futura em
  `style.css` (classes `st-key-*`, `stHorizontalBlock`) ou em `ui/paineis.py`
  (que `workspace.py` reaproveita: `_esconder_painel`, `_pid_visivel_salvo`,
  `ordem_efetiva`) é risco silencioso.
- O padrão `[class*="st-key-X"]` (usado pelo CTRL K novo e já usado por
  `ui/workspace.py`) depende de uma classe que o Streamlit gera automaticamente
  a partir do parâmetro `key=` — confirmado estável nesta versão (1.64.0), mas
  é comportamento não-documentado publicamente pelo Streamlit; um upgrade de
  versão merece re-teste.

---

## 12. Limitações de acesso e validação

- **Login Google (`auth.py`) impossível de automatizar neste ambiente** — mesma
  limitação documentada em todas as sessões anteriores (`PROGRESSO.md`). Nenhuma
  validação rodou contra o app publicado de verdade; toda validação visual usou
  harnesses Playwright isolados (fora de `app.py`, sem login/Supabase/Yahoo),
  chamando as funções de render reais com dados de exemplo — mesma metodologia
  já estabelecida e validada em sessões anteriores (ex.: `docs/evidencias/radar-20261018/`).
- **Sem acesso a Yahoo Finance/B3/Supabase/ANBIMA/CVM neste sandbox** —
  confirma o padrão já documentado. Isso bloqueou medição real de performance
  end-to-end (seção 16.E do pedido: "tempo até primeira renderização útil",
  "latência de banco/serviços externos") — não registrei nenhum número porque
  não consegui medir de verdade, e o pedido original explicitamente pede para
  nunca inventar métrica.
- **Validado visualmente nesta sessão (Playwright, harness isolado, 2
  breakpoints):** painel MINHA WATCHLIST (antes/depois,
  `docs/evidencias/visao-geral-watchlist-20261018/`), atalho CTRL K (sem
  screenshot comitado — comportamento funcional, não visual).
- **Não validado visualmente** (sem tempo/acesso para fazer com segurança nesta
  sessão): as 11 telas restantes não tocadas por mudança de código — não
  precisam de nova validação visual porque não houve mudança nelas.
- **Auditado via leitura de código (não via app rodando):** 100% dos achados
  listados neste documento — cada um cita `arquivo:linha` verificável.

---

## 13. O que ficou explicitamente para uma próxima sessão

Por ordem de valor/risco, na visão desta auditoria:

1. Radar: tornar `.rq-ticker` clicável sem perder a densidade da tabela (opção
   proposta na seção 4 — link `<a>` por linha com query param, precisa de
   validação Playwright antes de subir).
2. RESEARCH: diferenciação visual vigente/antigo + unificar os 2 padrões de
   interação do feed.
3. Escala tipográfica nomeada no design system — só com revisão visual do
   Rodrigo por tela (não em lote).
4. Teste automatizado para `ui/workspace.py` (puro trabalho de teste, zero
   risco de regressão de produto).
5. Rótulo visual "gerado por IA" nos modais de resumo (CVM, RESEARCH) — mesmo
   princípio do achado P0 corrigido no Morning Call, risco menor aqui porque já
   há nota textual, mas vale o mesmo cuidado visual.
