# Auditoria de paridade Streamlit × Vercel — Coordenador de Inteligência

Data: 2026-10-29 · Branch: `feat/coordenador-inteligencia-20261029` (a partir de `origin/main` @ `8da2227`)

Objetivo desta auditoria: decidir, módulo a módulo, o que já existe e funciona (nunca recriar), o que está só no Python/Streamlit (recuperar via porte de leitura, nunca recoletar), e o que falta de fato para o Coordenador e o Backoffice descritos no pedido.

Convenção de estado:
- **OK-TESTADO**: implementado e com teste automatizado cobrindo o comportamento real.
- **OK-SEM-TESTE**: implementado, roda em produção, mas sem teste automatizado direto.
- **PARCIAL**: existe, mas só cobre parte do fluxo (ex.: lê mas não agenda; agenda mas não expõe na UI).
- **SÓ-STREAMLIT**: função Python existe e funciona, zero equivalente no Next.js.
- **NÃO-IMPLEMENTADO**: não existe em nenhuma das duas versões.
- **BLOQUEADO**: dependente de credencial/custo/fonte externa indisponível — não contornar.

## Matriz

| # | Inteligência | Função analítica | Código Streamlit | Código Vercel | Fontes/tabelas | Natureza | Estado | Falta para web |
|---|---|---|---|---|---|---|---|---|
| 1 | **Radar de Inteligência (agregação)** | Combina catalisadores, mudanças de tese, evidências e qualidade de indicadores por ticker | `data/radar.py` (`catalisadores`, `mudancas_tese`, `evidencias_recentes`, `linha_valuation`) | — | `research_recomendacoes_historico`, `cvm_documentos`, `eventos_resultados`, cotação (yfinance) | FATO + CÁLCULO_INTERNO (tipado explicitamente no próprio módulo) | SÓ-STREAMLIT (função pura, sem teste de rede, mas usada em produção via `ui/radar_tab.py`) | Não existe `web/lib/server/dominio/radar.ts`. A página `inteligencia/page.tsx` hoje recalcula uma versão **mais simples** direto (sem `catalisadores`/`evidencias_recentes` com a tipagem FATO/CÁLCULO) |
| 2 | **Valuation Radar** | `linha_valuation(ticker)`: P/L, P/VP, DY, dívida/EBITDA com alertas de qualidade de indicador | `data/radar.py:linha_valuation` | — | `data/prices.py:obter_indicadores` (yfinance `tk.info`) | CÁLCULO_INTERNO | SÓ-STREAMLIT | Não portado. É a base de `_riscos` em `market_makers.py` — portar junto com #1 |
| 3 | **Comitê/Divergências entre casas** | ≥2 casas com recomendação estruturada diferente para o mesmo ticker | `data/market_researcher.py:cobertura_cruzada_casas` **e** (separadamente) `web/lib/server/dominio/research.ts:divergencias` | **OK — já portado**, com um porte paralelo mais simples (compara só `radar_carteiras_recomendadas` vigentes, não todo `research_itens`) | `radar_carteiras_recomendadas` | FATO (contagem, nunca inferência) | OK-SEM-TESTE (TS); OK-TESTADO (Python, `tests/test_market_researcher.py`) | Nenhum gap funcional — os dois concordam na regra (≥2 casas, campo estruturado). Diferença de fonte (carteiras vs. todos os itens) é aceitável, documentar no coordenador |
| 4 | **Research Radar / mudanças de recomendação** | Diff entre capturas sucessivas de recomendação/preço-alvo por casa+ticker | `data/research/historico.py` | **OK — já portado** `web/lib/server/dominio/research.ts:mudancasRecomendacao` | `research_recomendacoes_historico` | FATO | OK-SEM-TESTE (TS) | Nenhum — paridade real |
| 5 | **Mudanças de tese (research)** | "O que mudou" consolidando research + CVM + quedas + earnings | `data/market_makers.py` (contexto_ticker) | **OK — já portado**, versão própria `web/lib/server/dominio/inteligencia.ts:oQueMudou` | `research_recomendacoes_historico`, `cvm_documentos`, `radar_alertas_queda`, `earnings_reviews` | FATO/ANALISTA (`Natureza` explícito) | OK-SEM-TESTE (TS) | É o embrião do coordenador — falta: achados do backoffice e síntese IA não entram nessa lista hoje |
| 6 | **Tese própria do usuário (thesis tracker)** | Hipótese/convicção/preço-alvo-tese do próprio Rodrigo por ticker, versionado (append-only) | `data/research/tese.py` (adaptado do skill oficial `thesis-tracker`) | — | `research_teses` (escopo por `usuario_sub`) | HIPÓTESE_ANALISTA (nunca fato) | SÓ-STREAMLIT | Não portado; depende de auth por usuário (web já tem NextAuth — viável, mas fora do escopo pedido: coordenador consome, não cria UI de escrita de tese) |
| 7 | **Notícias e resumos** | Coleta + resumo por IA (Groq) de manchetes, com gates anti-contradição/causalidade | `data/news.py` (3470 linhas), `data/news_setores.py` | **OK parcial** `web/lib/server/noticias.ts` (usado em `ativo/[ticker]`, `noticias/page.tsx`) | cache de resumo em `resumos_ia_cache` (`origem='news'`) | FATO (manchete) + INFERÊNCIA (resumo, rotulado) | OK-SEM-TESTE (TS, leitura); OK-TESTADO (Python, geração) | Web só lê notícias cruas, não lê os **resumos de IA** já cacheados (`resumos_ia_cache origem='news'`) — gap de leitura, zero coleta nova necessária |
| 8 | **Radar setorial (Morning Call)** | 4 blocos setoriais didáticos por edição, sem IA e sem número inventado | `data/radar_setorial.py` | — (consumido só dentro do e-mail/PDF do Morning Call) | `data/news.py` (mesma coleta) | FATO (cita manchete) | OK-TESTADO (Python) | Não precisa de porte dedicado — já chega à web dentro do texto da edição (`morning_call_execucoes.conteudo`, lido por `morningCall.ts`) |
| 9 | **CVM / documentos e fatos relevantes** | Coleta IPE/FCA, documentos por ticker | `data/cvm.py` | **OK — já portado** `web/lib/server/dominio/cvm.ts:lerDocumentosCvm` | `cvm_documentos` | FATO | OK-SEM-TESTE (TS) | Nenhum — paridade real |
| 10 | **Calendário/catalisadores (eventos)** | Prazo regulatório CVM (ITR/DFP) — única fonte confiável hoje; CONFIRMADO/ESTIMADO deliberadamente não implementados (sem fonte íntegra) | `data/eventos.py`, `data/eventos_coleta.py` | **OK — já portado** `web/lib/server/dominio/agenda.ts` | `eventos_resultados`, `calendario_snapshot` | FATO (prazo legal) | OK-SEM-TESTE (TS) | Nenhum gap de porte — o gap é upstream (sem fonte confiável de data confirmada), mesmo nas duas versões, documentado no próprio módulo Python |
| 11 | **Earnings / análise de resultados** | Nota estruturada por trimestre (DRE normalizada BR via CVM / US via SEC XBRL), fato vs. `[INTERPRETAÇÃO]`, versionado | `data/earnings/cvm_dre.py`, `sec_xbrl.py`, `reviewer.py` | **OK — já portado (leitura)** `web/lib/server/dominio/inteligencia.ts:lerEarnings` | `earnings_reviews` | FATO + INTERPRETAÇÃO (prefixo explícito) | OK-SEM-TESTE (TS); OK-TESTADO (Python) | Nenhum — paridade real. `data/earnings/editorial.py` (ponte pro corpo do Morning Call) está **pendente mesmo no Python** (documentado no próprio módulo) — não é gap de porte |
| 12 | **Radar de Quedas** | Alerta de queda ≥4% em ticker de carteira recomendada vigente (Genial/Safra), e-mail para assinantes opt-in | `data/radar_quedas.py` + `jobs/radar_quedas.py` (cron 15min) | **OK — já portado (leitura)** `inteligencia.ts:lerAlertasQueda` | `radar_alertas_queda`, `radar_carteiras_recomendadas` | FATO | OK-TESTADO (Python); OK-SEM-TESTE (TS) | Nenhum gap de porte — job já roda via GitHub Actions independente de usuário, exatamente o padrão a reaproveitar no coordenador |
| 13 | **Morning Call** | Edição diária (macro+mercado+notícias+earnings+setorial), e-mail + PDF | `jobs/morning_call.py` (1140 linhas) + `morning_call_editorial.py`, `morning_call_briefing.py`, `morning_call_historico.py` | **OK — já portado (leitura)** `web/lib/server/dominio/morningCall.ts` | `morning_call_execucoes` | FATO + INFERÊNCIA (seções de síntese) | OK-TESTADO (Python); OK-SEM-TESTE (TS) | Nenhum — o e-mail/PDF continuam no pipeline Python por design (RN explícita, não recriar) |
| 14 | **Síntese executiva ("Analista de Mercado")** | 1 chamada de IA (Groq) interpretando fatos já coletados: resumo, movimentos, oportunidades/riscos, cenários (bull/base/bear qualitativo), o que observar — nunca inventa causalidade/preço/recomendação | `data/sintese_mercado.py` (541 linhas) | — | cache em `resumos_ia_cache` (`origem='sintese_mercado'`) | INFERÊNCIA (explicitamente rotulada, com fallback "ANTERIOR" quando a rodada atual falha) | OK-TESTADO (Python, `tests/test_sintese_mercado.py`); **zero porte web** | **Maior gap real do Coordenador**: síntese só é gerada quando um usuário abre `ui/visao_geral.py`/`ui/morning_call_tab.py`/`ui/analises_tab.py` no Streamlit — nunca por agendamento. Web não lê `resumos_ia_cache origem='sintese_mercado'` |
| 15 | **Market Researcher — achados de qualidade (backoffice)** | Prioriza achados do painel de saúde por severidade (crítico/atenção), nunca recalcula coleta | `data/market_researcher.py:achados_qualidade_coletores` | — | deriva de `coletores_status` | FATO (estado observado) | OK-TESTADO (Python, `tests/test_market_researcher.py`) | Zero porte web — é o motor do Backoffice pedido na Fase 3 |
| 16 | **Market Researcher — memória operacional persistente** | Upsert por chave (coletor\|categoria\|tipo); auto-resolve quando o achado para de aparecer | `data/market_researcher.py:registrar_achados_atuais` | — | `market_researcher_achados` (**tabela já existe**, schema já cobre id/chave/categoria/tipo/severidade/status ABERTO·RESOLVIDO/ocorrências/causa_raiz/commit_correcao) | FATO | OK-TESTADO (Python) | **Só é acionado pelo clique em "ATUALIZAR" na aba Streamlit** — nunca por agendamento; schema não tem ainda `prioridade`/`proxima_acao_recomendada`/estados intermediários (investigando/aguardando intervenção/inconclusivo) exigidos pela Fase 3 |
| 17 | **Saúde dos dados (painel de coletores)** | Classifica cada coletor em 9 estados (nunca finge "verde" sem evidência); painel de consumo efetivo (seção do Morning Call usou o dado ou não) | `data/saude_dados.py` (635 linhas) | **OK — já portado** `web/lib/server/dominio/saude.ts:painelSaude/classificarEstado` | `coletores_status` | FATO | OK-TESTADO (Python); OK-SEM-TESTE (TS) | Web não tem o **painel de consumo efetivo** (`obter_painel_consumo`) nem é exibido como página própria — hoje só filtra alguns `problemas` dentro de `inteligencia/page.tsx`. Não há página `/saude` dedicada no Next.js |
| 18 | **X (Twitter) signals** | Descoberta de sinais via X/Twitter | `data/x_signals.py` | — | — | — | **BLOQUEADO** (`DISPONIVEL=False`) — sem tier de API gratuito/viável desde 06/02/2026; custo Enterprise (US$42k/mês) | Não contornar. Módulo fica isolado e desligado, nenhuma ação |
| 19 | **Macro** | IPCA/Selic/CDI/Focus (BCB), cenário global (ouro/petróleo/VIX/Treasuries) | `data/macro.py` | **OK — já portado** `web/lib/server/dominio/mercado.ts` (parcial) + página `/macro` | fontes BCB/ANBIMA direto (sem tabela própria) | FATO | OK-SEM-TESTE (TS) | Já instrumentado na Saúde dos Dados; nenhum gap de coordenador específico |

## Síntese por categoria pedida no escopo

- **Radar de Inteligência de Investimentos**: SÓ-STREAMLIT (#1, #2) — portar como leitura para o coordenador.
- **Research Radar e mudanças de tese**: paridade real (#3, #4, #5); tese própria do usuário (#6) só Streamlit, fora do escopo do coordenador (é escrita pessoal, não achado consolidável).
- **Valuation Radar**: SÓ-STREAMLIT (#2).
- **Divergências entre casas**: paridade real, com nota de fonte diferente (#3).
- **Notícias e resumos**: paridade na coleta; resumo de IA cacheado não é lido pela web (#7).
- **Inteligência de documentos/CVM**: paridade real (#9).
- **Macro e catalisadores**: paridade real (#10, #19).
- **Radar de Quedas**: paridade real, já agendado via GitHub Actions (#12) — modelo a copiar para o coordenador.
- **Earnings**: paridade real na leitura (#11).
- **Morning Call**: paridade real na leitura (#13).
- **Saúde dos dados e coletores**: paridade parcial — falta consumo efetivo e página dedicada (#17).
- **Qualquer outro agente encontrado**: síntese executiva via IA (#14) e achados de qualidade/backoffice (#15, #16) — ambos **totalmente ausentes da web** e **nunca agendados** nem no Python. São o verdadeiro núcleo do que falta construir.

## Conclusão da auditoria (o que o Coordenador/Backoffice realmente precisam fazer)

1. **Não recriar nenhuma lógica de coleta ou cálculo.** Tudo que os itens 14, 15 e 16 fazem já existe e já é testado em Python.
2. **O gap real é duplo:**
   - **Agendamento**: `obter_sintese_mercado()` e `registrar_achados_atuais()` só rodam quando um humano abre uma aba do Streamlit. Nenhum dos dois está em `jobs/` nem nos workflows do GitHub Actions.
   - **Leitura web**: nenhuma das duas saídas (`resumos_ia_cache origem='sintese_mercado'`, `market_researcher_achados`) tem um módulo em `web/lib/server/dominio/`.
3. **Schema do backoffice precisa de 2 colunas aditivas** (`prioridade`, `proxima_acao_recomendada`) e de um pequeno ajuste no upsert Python para não sobrescrever um estado manual (`INVESTIGANDO`/`AGUARDANDO_INTERVENCAO`/`INCONCLUSIVO`) a cada execução agendada — hoje `registrar_achados_atuais` força `status="ABERTO"` em toda atualização, o que é seguro só porque hoje é 100% manual (clique em "ATUALIZAR").
4. **O "Coordenador"** é, na prática, uma camada nova (`web/lib/server/dominio/coordenador.ts`) que: lê `oQueMudou()` (já existe), lê a síntese de IA (novo leitor), lê os achados do backoffice (novo leitor), lê divergências/catalisadores (já existem) — e consolida tudo em uma visão única, priorizada, com natureza explícita. Nenhum cálculo novo de negócio, só orquestração de leitura + priorização + rotulagem.
5. **O agendamento do Coordenador/Backoffice** deve ser um novo job Python (`jobs/coordenador.py`) chamado como um passo adicional do workflow `coletores-nuvem.yml` já existente (mesma cadência ~30min, dias úteis 07–20h BRT) — não um workflow novo, reaproveitando 100% da infraestrutura de cron, secrets e validação já existente.

## Entrega (Fase 8)

Branch: `feat/coordenador-inteligencia-20261029` (a partir de `origin/main` @ `8da2227`, worktree isolado em `~/Projects/pregao-worktrees/coordenador-inteligencia` — `~/Projects/pregao` nunca foi tocado).

### Funcionalidades recuperadas/implementadas

- **Backoffice agendado**: `data/market_researcher.py:registrar_achados_atuais()` e `data/sintese_mercado.py:obter_sintese_mercado()` (já existentes e testados) agora rodam por agendamento (`jobs/coordenador.py`, passo novo em `.github/workflows/coletores-nuvem.yml`), não só sob clique/visita no Streamlit.
- **Patch de segurança no Python**: `registrar_achados_atuais()` não sobrescreve mais um estado de triagem manual (`INVESTIGANDO`/`AGUARDANDO_INTERVENCAO`/`INCONCLUSIVO`) a cada execução agendada — só preserva o comportamento antigo (upsert `ABERTO`/`RESOLVIDO` automático) quando não há triagem manual em andamento.
- **Coordenador (`web/lib/server/dominio/coordenador.ts`)**: lê a síntese de IA já persistida (`resumos_ia_cache`, origem `sintese_mercado`) e consolida com `oQueMudou`, divergências, catalisadores e achados do Backoffice numa fila única, priorizada e deduplicada por chave estável (`montarItensConsolidados`, função pura e testada).
- **Backoffice web (`web/lib/server/dominio/backoffice.ts`)**: leitura de `market_researcher_achados`, priorização (port determinístico de `_PRIORIDADE_ESTADO`/`_CATEGORIAS_CRITICAS`), causa provável e próxima ação (hipóteses, nunca fato), e as novas transições de estado manuais.
- **Triagem manual** (`web/lib/server/dominio/backofficeAcoes.ts`): server action restrita a administrador (`ADMIN_EMAILS`, mesmo gate de Configurações) e a uma whitelist fixa de transições — nunca cria achado, nunca altera schema.
- **Página de Inteligência** (`web/app/(terminal)/inteligencia/page.tsx`): integrado ao coordenador/backoffice sem criar página nova — resumo executivo (síntese + cenários), fila de investigação, mudanças de tese, catalisadores, comitê (divergências/cobertura), status dos especialistas, backoffice (fila de incidentes com triagem) e histórico (resolvidos). Filtros por tipo de evento, "só crítico" e estado do incidente via query string.
- **Guardrail de natureza** (`web/components/Selo.tsx`): adicionados os tons `calculo` (cálculo interno) e `insuficiente` (dado insuficiente), preservando a distinção FATO/VISÃO DE ANALISTA/CÁLCULO/INFERÊNCIA/DADO INSUFICIENTE em toda a nova UI.

### Migração SQL

- `sql/coordenador.sql` — **100% aditiva**: cria só a tabela nova `coordenador_execucoes` (log de execução do job). Nenhuma tabela/coluna existente é alterada. Precisa ser rodada manualmente no SQL Editor do Supabase de produção antes do job funcionar de ponta a ponta (mesmo procedimento manual já documentado para toda migração deste projeto).

### Dependências externas / ações manuais necessárias

- Rodar `sql/coordenador.sql` no Supabase de produção (idempotente, `create table if not exists`).
- Nenhuma credencial nova: reaproveita `SUPABASE_URL`/`SUPABASE_SECRET_KEY`/`GROQ_API_KEY` já configurados em Actions secrets.
- Para a triagem manual aparecer na UI, o e-mail do usuário precisa estar em `ADMIN_EMAILS` (mesma variável já usada por Configurações) — sem isso, a fila de incidentes é só leitura.

### Testes executados

- `python -m pytest -q` (suíte completa): **1685 passed**.
- `npm run test` (vitest, web completo): **66 passed** (8 arquivos), incluindo os 4 novos: `backoffice.test.ts`, `coordenador.test.ts`, `backofficeAcoes.test.ts`, e a extensão de `tests/test_jobs_coordenador.py`/`tests/test_market_researcher.py` no lado Python.
- `npm run typecheck`: sem erros.
- `npm run build` (produção Next.js): sucesso, rota `/inteligencia` incluída na saída.
- Smoke test real: servidor Next.js de produção iniciado localmente (`PREGAO_DIAG_SEM_LOGIN=1`, sem Supabase configurado) e a rota `/inteligencia` respondeu HTTP 200, renderizando todas as seções novas no estado degradado "não configurado" (sem erro de runtime/digest).

### Validações pendentes (não cobertas nesta sessão)

- **Dados reais**: este ambiente não tem credenciais do Supabase/Groq de produção — o smoke test cobriu só o estado "não configurado"/vazio. Falta validar visualmente com dados reais (após rodar a migração e o primeiro ciclo do job) que a síntese de IA, a fila de incidentes e a triagem manual aparecem corretamente.
- **Execução real do job agendado**: `jobs/coordenador.py` foi testado com mocks (isolamento de falha, log de execução, retomada após travamento) mas nunca rodou de verdade contra o Supabase/Groq de produção — só acontecerá no primeiro disparo do workflow depois do merge.
- **Atualização da interface sem refresh manual** (Fase 7, item 12): não implementada — nenhuma página deste app (nem as já existentes) usa polling/websocket/revalidação automática hoje; a arquitetura atual é 100% server-rendered sob requisição. Fora de escopo desta tarefa (teria mudança de arquitetura, não pedida).
- **Teste de renderização com dados reais/parciais/erro via componente** (Fase 7, item 11): cobrto só via smoke test HTTP (estado não configurado); não há harness de renderização de componente React neste projeto (nenhuma outra página tem) nem Playwright configurado — consistente com o padrão já usado no repositório (ver memória "validação real de navegador": Playwright seria o próximo passo antes de uma validação visual completa com dados reais).
