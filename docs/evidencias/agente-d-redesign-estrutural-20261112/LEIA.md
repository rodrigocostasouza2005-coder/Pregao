# Redesign visual ESTRUTURAL — Agente D (2026-11-12)

Missão: redesign estrutural real (não só design system/cores) do PREGÃO.
Este documento é o registro honesto do que foi e não foi estruturalmente
redesenhado nesta frente, com evidência real (Playwright, antes/depois).

## Inventário completo (`ui/*.py` em `origin/main`, commit `36dda39`)

| Arquivo | O que é | Estado antes desta missão |
|---|---|---|
| `visao_geral.py` | MERCADO › Visão Geral (HOME) | **Já redesenhada estruturalmente** em 2026-11-09 (grade de 3 regiões, ver `docs/evidencias/visao-geral-redesign-estrutural-20261109/`) — não retrabalhada aqui |
| `mercado_tab.py` | MERCADO › Painel | **Já redesenhada estruturalmente** em 2026-10-27 (grade fixa, treemap, ranking denso) — não retrabalhada aqui |
| `research_tab.py` | RESEARCH (Feed/Casas/Radar X/Tese/Memória) | Feed já tem grade (`research_grid_watchlist_radar`); comparador de casas (`data/research/comparador.py`, já em `main`) já integrado via `render_comparativo_casas` — não retrabalhada aqui |
| `coordenador_tab.py` | COORDENADOR (Visão Geral/Especialistas/Execuções/Histórico/Analisar) | 1 coluna só, expander fechável escondendo dado | **REDESENHADA NESTA MISSÃO** |
| `radar_tab.py` | RADAR + ANÁLISES›Valuation/Teses | Oportunidades: 2 `st.expander` sequenciais (1 escondido) | **Oportunidades REDESENHADA NESTA MISSÃO**; Alertas/Carteiras/Acompanhamento/Valuation/Teses **não tocados** |
| `analises_tab.py`, `news_tab.py`, `cvm_tab.py`, `macro_tab.py`, `setores_tab.py`, `calendario_tab.py`, `morning_call_tab.py`, `top_mercado_tab.py`, `sistema_tab.py`, `usuarios_tab.py`, `dcf_operacional.py` | Demais abas/componentes | Já usam o design system (cores/`classe_sinal`/`numero_financeiro_html`) de missões anteriores — **não receberam redesign estrutural nesta missão** (sem tempo disponível) |
| `saude_dados_tab.py` | MAIS › Saúde dos Dados | **Intencionalmente fora de escopo** (CLAUDE.md regra 8: frente isolada) |
| `design_system.py`, `navegacao.py`, `secoes.py`, `paineis.py`, `workspace.py`, `graficos.py`, `busca.py` | Infraestrutura/compartilhado, não são abas | Não aplicável |

Áreas/subabas completas de navegação (`ui/navegacao.py:AREAS`): MERCADO
(Visão Geral/Painel/Agenda/Mercados Globais) · NOTÍCIAS (Destaques/Brasil/
Internacional/Empresas/Documentos CVM) · RADAR (Alertas/Carteiras
Recomendadas/Oportunidades/Acompanhamento/Preferências) · RESEARCH (Feed/
Casas de Análise/Radar X/Minha Tese/Memória de Research) · ANÁLISES
(Empresas/Fundamentos/Valuation) · COORDENADOR (Visão Geral/Especialistas/
Execuções/Histórico/Analisar) · MACRO (Indicadores/Juros/Câmbio e
Commodities/Calendário Econômico) · SETORES (Mapa Setorial/Visão por
Setor/Catalisadores) · MORNING CALL (Edição Atual/Relatório Completo/
Histórico/Preferências) · MAIS (Watchlist/Configurações/Sistema/Saúde dos
Dados/Usuários).

## O que foi ESTRUTURALMENTE redesenhado (descrição concreta, não adjetivo)

### 1. COORDENADOR › Visão Geral (`render_visao_geral`)

**Antes:** 1 coluna só, de cima a baixo — título → nota → `st.expander`
fechável com a tabela de execuções agendadas → 8 métricas num único
`flex-wrap` sem agrupamento → 1 linha de texto sobre a última análise.

**Depois:** 2 regiões de 2 colunas lado a lado (`st.container(key=
"coord_grid_...")`, mesmo mecanismo de grade responsiva de VISÃO GERAL/
MERCADO/RESEARCH):
- Região 1: painel "ESPECIALISTAS" (4 métricas) | painel "ANÁLISES SOB
  DEMANDA" (4 métricas, incluindo tempo médio) — as 8 métricas que antes
  eram 1 bloco só agora são 2 painéis agrupados por assunto.
- Região 2: "ÚLTIMAS EXECUÇÕES AGENDADAS" promovida de `expander` pra
  painel sempre visível | "ANÁLISES SOB DEMANDA RECENTES" (novo, preview
  das 5 análises mais recentes — sobre o MESMO dado já buscado pras
  métricas, zero consulta nova), com atalho pra COORDENADOR › Execuções.

Zero dado novo, zero cálculo novo, zero funcionalidade removida.

### 2. Cabeçalho de decisão do Comitê (`_render_cabecalho_decisao`, compartilhado por HISTÓRICO e ANALISAR)

**Antes:** narrativa (empresa/recomendação/confiança/resumo/justificativa)
e o painel numérico de preços-alvo (preço atual/score/alvo DCF/potencial/
alvo P-L/consenso das casas) ficavam EMPILHADOS, nessa ordem, cada um
ocupando a largura toda.

**Depois:** painel de decisão em 2 colunas (52%/48%) lado a lado — esquerda
= narrativa ("o porquê"), direita = os 6 números de preço-alvo ("o
quanto") — lidos ao mesmo tempo, não em sequência. Extraído em função
própria (`_render_metricas_preco_alvo`), nenhum campo novo/recalculado.

### 3. RADAR › Oportunidades (`render_radar_oportunidades`)

**Antes:** "Próximos Catalisadores" (expander aberto) e "Research com
Evidências" (expander FECHADO por padrão) — a 2ª pergunta ficava escondida
atrás de 1 clique, nunca lado a lado com a 1ª.

**Depois:** 2 colunas sempre visíveis (`radar_grid_oportunidades`),
nenhuma escondida atrás de accordion. Zero dado/função de cálculo tocada.

### CSS (`style.css`)

Adicionados os prefixos wildcard `st-key-coord_grid_`/`st-key-radar_grid_`
às regras responsivas já existentes (`@media max-width:900px` e `1200px
com sidebar aberta`) que fazem colunas de grade virar 100% de largura e
empilhar em telas estreitas — mesmo mecanismo já usado por `vg_grid_`/
`painel_grid_`/`research_grid_watchlist_radar`, confirmado nos
screenshots 820px (ver abaixo). Adicionado `.coord-tabela-execagendadas
{ min-width: 560px }` (mesma técnica de `.coord-tabela-dcf`/`.coord-tabela-
sens`) pra tabela de execuções agendadas rolar horizontalmente em vez de
cortar texto, agora que divide a largura com o painel ao lado.

## O que NÃO deu tempo de redesenhar estruturalmente (honesto)

- RADAR › Alertas, Carteiras Recomendadas, Acompanhamento, e ANÁLISES ›
  Valuation/Teses — continuam com a composição anterior (fixa, sequencial,
  com expanders em alguns pontos). Capturado "antes" de Acompanhamento
  (`acompanhamento_1440_antes.png`) mas **não há "depois"** — não foi
  alterado.
- CVM, NEWS (Empresas), MACRO, SETORES, MORNING CALL, TOP MERCADO,
  SISTEMA, USUÁRIOS, DCF operacional (standalone) — permanecem só com o
  design system já aplicado em missões anteriores (cores/tipografia/
  `classe_sinal`/`numero_financeiro_html`), **sem** reorganização
  estrutural de composição nesta missão.
- COORDENADOR › Especialistas e Execuções — já eram tabelas densas (não
  cards), consideradas de menor prioridade dado o tempo disponível; não
  reagrupadas numa grade.

Se o resultado final ainda parecer "parecido com antes" nessas abas
listadas acima, é porque **de fato está** — não foram tocadas nesta
frente.

## Validação

- **Playwright real** (Chromium, `.venv` do repo principal), harnesses em
  `harness_coordenador.py`/`harness_radar.py` (mesmo padrão de
  `docs/evidencias/validacao-independente-home-mercado-20261106/
  harness_home.py`: chama `render_*` direto com dado mockado realista,
  sem Supabase/login real). Screenshots antes/depois em desktop (1440px)
  e iPad (1024px), mais uma 3ª largura (820px) confirmando o wrap
  responsivo abaixo do breakpoint de 900px:
  - `visao_geral_{1440,1024}_{antes,depois}.png`, `visao_geral_820_depois_stack.png`
  - `historico_{1440,1024}_{antes,depois}.png` (cabeçalho de decisão)
  - `oportunidades_{1440,1024}_{antes,depois}.png`, `oportunidades_820_depois_stack.png`
  - `acompanhamento_1440_antes.png` (sem depois — não alterado)
- **Interação real** confirmada via Playwright: pills de filtro (período/
  escopo/setor) e abas de especialista (`st.tabs`) renderizam e respondem
  normalmente nas telas redesenhadas; nenhum widget interativo foi
  removido ou substituído por versão simplificada.
- **Toque no iPad**: a navegação por toque (correção real do PR #270) não
  foi tocada — nenhuma mudança em `ui/navegacao.py` nem no mecanismo de
  `segmented_control`/histórico do navegador. As mudanças desta missão são
  só de composição (`st.columns`/`st.container(key=...)`), sem nenhum
  componente de toque novo ou removido.
- **Suíte pytest completa**: `2339 passed` (`pytest tests/ -q -p no:randomly`),
  sem regressão. 1 teste precisou ser ajustado porque checava
  deliberadamente a estrutura antiga (`test_coordenador_tab_execucoes_
  agendadas.py`: antes verificava o título dentro de um `st.expander` —
  esse expander foi removido de propósito, teste atualizado pra verificar
  o título como painel sempre visível, mesmo conteúdo). Achado à parte:
  `tests/test_radar_acompanhamento_redesign_ui.py` falha quando rodado
  numa combinação específica de 5 arquivos de teste (flakiness de
  ordem/estado compartilhado do `AppTest`) — confirmado que o MESMO
  comportamento já existe em `origin/main`, sem nenhuma mudança desta
  missão (reproduzido rodando a mesma combinação com `git stash`
  revertendo tudo). Não é regressão desta PR.

## Fora de escopo (confirmado, não tocado)

`data/research/*.py`, lógica de coleta/persistência, nenhuma migration
SQL, `PROGRESSO.md`/`CHANGELOG.md`.
