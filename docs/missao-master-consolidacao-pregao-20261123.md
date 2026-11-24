# Missão Master — Consolidação, Auditoria e Evolução do PREGÃO (2026-11-23)

## Objetivo

Não adicionar funcionalidade nova indiscriminadamente. Transformar o Pregão num terminal confiável, integrado, com inteligência de verdade, análise de empresas de alta qualidade, valuation consistente e acompanhamento de teses — via 6 frentes paralelas (infra, Comitê, valuation, Radar/teses, Research, UX/produto).

## Estado inicial (HEAD no disparo da missão)

- `origin/main` = `6d5949c` (PR #351, "extrai Perfil da Empresa do expander em COMITÊ pra aba própria"), na sequência direta das PRs #338–#350 (sessão anterior) e da missão "RECONSTRUÇÃO COMPLETA" (PRs #326–#336, 2026-11-18). Ver `docs/continuidade-pregao-20261118-missao-master.md` — **não redescobrir isso**: design system/paleta, reconstrução de navegação (COMITÊ/CALENDÁRIO/VALUATION/dissolução de SETORES e MORNING-CALL), divergência entre especialistas visível, 3º motor de DCF duplicado removido, Perfil da Empresa conectado ao COMITÊ (e agora com aba própria, #351).
- `CLAUDE.md` já define o fluxo de execução/revisão/merge do repo (worktree isolado obrigatório, merge só com autorização explícita por PR, Saúde dos Dados sempre em PR isolada). Esta missão herda essas regras.
- Regra desta missão (pedido explícito do Rodrigo, 2026-11-23): **nenhum merge** — todas as frentes abrem PR e paralisam ali.

## As 6 frentes

| Fase | Tema | Status | PR(s) |
|---|---|---|---|
| 1 | Estabilidade operacional e infraestrutura | **concluída** | #354 |
| 2 | Comitê de Investimentos | **concluída** | #355 |
| 3 | Valuation e modelos financeiros | **concluída** | #353 |
| 4 | Radar inteligente e acompanhamento de teses | **concluída** | #358 |
| 5 | Research e qualidade das fontes | **concluída** | #356, #357 |
| 6 | Interface, UX e consolidação do produto | **concluída** | #359 |

Missão concluída em 2026-11-23, mesmo dia do disparo. As 6 frentes rodaram em paralelo, cada uma em worktree isolado; nenhuma fez merge (regra explícita da missão). 2 frentes (Fase 2 e Fase 5) tiveram interrupção por limite de sessão no meio da execução e foram retomadas pelo coordenador; a Fase 6 perdeu o transcript por completo e foi relançada como agente novo reaproveitando o worktree/branch já criado — sem perda de trabalho commitado em nenhum caso.

## Mapa de arquivos / ownership (evitar dois agentes implementando a mesma coisa)

- **Fase 1**: `.github/workflows/*.yml`, `jobs/morning_call.py`, `jobs/radar_quedas.py` (só infra/retry/idempotência — lógica de tese é da Fase 4), `jobs/email_utils.py`, `jobs/comite_noturno.py` (só execução/infra — lógica dos especialistas é da Fase 2), `jobs/carteira_recomendada_job.py`, `jobs/coordenador.py`, `data/coletores_status.py`, `data/agendamentos_saude.py`, `data/supabase_client.py`, `ui/sistema_tab.py`. **Saúde dos Dados** (`data/saude_dados.py`, `ui/saude_dados_tab.py`) pertence a esta fase mas em PR própria e isolada (regra 8 do CLAUDE.md).
- **Fase 2**: `data/coordenador_central/*.py` (consolidacao, executor, fluxos, modelagem, pareceres, persistencia, registro, sintese_ia, execucoes_agendadas — exceto `dcf.py`/`dcf_operacional.py`, da Fase 3), `data/market_researcher.py`, `data/empresa_perfil.py`, `data/research/comparador.py`, `data/earnings/reviewer.py` (agente Earnings Reviewer — coleta de dado CVM/SEC em si é Fase 5), `data/x_radar/*`, `ui/coordenador_tab.py`, `ui/central_inteligencias_tab.py`.
- **Fase 3**: `data/coordenador_central/dcf.py`, `data/coordenador_central/dcf_operacional.py`, `data/coordenador_central/modelagem.py`, `data/radar.py` (só `valuation_radar`, o motor — a tela é `ui/radar_tab.py:render_valuation`, arquivo compartilhado com a Fase 4: Fase 3 só lê, não edita), `ui/dcf_operacional.py`, `ui/analises_tab.py` (parte de valuation/simulador).
- **Fase 4**: `ui/radar_tab.py` (dono do arquivo inteiro), `data/radar_quedas.py`, `data/carteira_recomendada.py`, `ui/carteira_recomendada_tab.py`. Não tocar `jobs/radar_quedas.py` (Fase 1) nem `data/saude_dados.py`.
- **Fase 5**: `data/research/*.py` (todas as casas + `store.py`/`qualidade.py`/`resumir.py`/`embeddings.py`/`historico.py`/`sinal.py`/`tese.py` — `comparador.py` fica com a Fase 2), `data/earnings/cvm_balanco.py`, `cvm_dfc.py`, `cvm_dre.py`, `editorial.py`, `sec_xbrl.py` (coleta, não o Reviewer), `ui/research_tab.py`, `ui/news_tab.py`, `data/news.py`, `data/news_setores.py`.
- **Fase 6**: `ui/design_system.py`, `ui/navegacao.py`, `ui/workspace.py`, `ui/busca.py`, `ui/paineis.py`, `ui/graficos.py`, `ui/visao_geral.py`, `ui/mercado_tab.py`, `ui/macro_tab.py`, `ui/calendario_tab.py`, `ui/cvm_tab.py`, `ui/setores_tab.py`, `ui/top_mercado_tab.py`, `ui/usuarios_tab.py`, `web/**` (Next.js — auditoria de estratégia, não reconstrução). Achados de UX em arquivo de outra frente são **registrados**, não editados direto, a menos que seja fix visual trivial sem lógica nova.

## Autorizações e restrições (vale para as 6 frentes)

Autorizado: auditoria, implementação, testes, branches, PRs — sem merge nesta missão. Proibido sem autorização explícita adicional: alterar secrets, expor credencial, operação destrutiva/migration em produção, envio real de e-mail em teste, qualquer ação irreversível, novo serviço pago, duplicar estrutura já existente. Problemas que dependam disso: documentar a solução pronta e a ação pendente, não executar.

## Problemas encontrados e corrigidos, por frente

**Fase 1 (infra, PR #354)** — P0 investigado com evidência real de log (`gh run view --log`), não assumido por hipótese: `radar` saindo `skipped` é comportamento correto por design (jobs `radar`/`morning-call` respondem a listas de `schedule` disjuntas). A falha real era outra: quando o GitHub atrasa um disparo de `schedule` (já documentado desde 18/10 em `MANUAL.md` — atraso de ~12h observado, 8 reservas da manhã entregues de uma vez às 18h+ BRT), o job corretamente recusa enviar uma edição velha do Morning Call, mas devolvia código de saída 1, acendendo `failure` no Actions 8 vezes pela mesma causa — contrariando a própria política do projeto ("só vermelho em perda total"). Corrigido para `warning`, mantendo o registro em Saúde dos Dados.

**Fase 2 (Comitê, PR #355)** — 2 bugs de corretude: (1) os validadores anti-alucinação da síntese de IA (`market_researcher`/`sintese_ia`) só sanitizavam a lista estruturada de casas/especialistas citados, nunca o texto livre — onde a atribuição indevida realmente apareceria pro usuário; agora rejeitam a síntese inteira se o texto citar fonte real fora da cobertura da análise. (2) 5 blocos `except` degradavam em silêncio sem log. Evolução: conectou dispersão de preço-alvo/divergência entre casas (já calculada, nunca exibida) numa seção nova do Perfil da Empresa. **Validado com 8 cenários reais (Groq/CVM/yfinance ao vivo, sem mock)**: PRIO3, GGBR4, LREN3, VALE3, CSNA3, AZUL4, MRVE3 — em todos, o sistema distinguiu fundamento de preço corretamente, nunca inventou número com dado faltante (P/L indefinido, ticker delistado tratados como limitação explícita), e toda divergência entre especialistas foi rastreável a um número real. Único ponto não fechado: validação numérica de "geração de caixa negativa" com um ticker que de fato tivesse FCF negativo (aceito como resultado parcial, não insistido).

**Fase 3 (Valuation, PR #353)** — bug real de magnitude alta no motor #1 de DCF: `ui/analises_tab.py` alimentava `calcular_dcf` com o FCF acumulado do ano (YTD, a integração CVM nunca cobre Q4) tratado como se fosse o FCF anual completo. Medido com o motor real: mesmas premissas, FCF anual verdadeiro R$1bi → preço-alvo R$119,42; FCF de 6 meses (YTD) tratado como anual → R$54,71 — menos da metade, só pelo erro de base temporal. Corrigido: sem o ponto anual real, o DCF agora bloqueia honestamente em vez de subavaliar silenciosamente. Também expôs o waterfall completo do cálculo na UI (rastreabilidade de premissa). Cenários Bear/Base/Bull confirmados já corretos (sem default silencioso, `revisar_valuation` já reprova ordenação incoerente). Nenhum motor novo criado.

**Fase 4 (Radar/teses, PR #358)** — nova função `estado_tese()` classifica cada ativo da Carteira Recomendada em PRESERVADA/FORTALECIDA/ENFRAQUECIDA/EM_REVISÃO/INVALIDADA/DADOS_INSUFICIENTES, com linha do tempo de eventos, retorno acumulado e relativo ao Ibovespa — 100% de dado já persistido, zero chamada nova a IA. **Achado crítico interceptado antes do commit**: a primeira versão comparava `sinal_comite`/`confianca_comite`/`score_comite` contra o snapshot anterior, mas confirmou por leitura real em produção que a tabela `carteira_recomendada_itens` nunca teve essas colunas — geraria "mudança" falsa em todo ticker, toda rodada, pra sempre. Corrigido antes de expor. Confirmado que queda de preço isolada nunca é tratada como sinal de compra (já estava correto). Confirmado que a pendência antiga "tabelas da Carteira Recomendada nunca existiam em produção" (registrada em missão de 13/11) está resolvida desde o PR #321.

**Fase 5 (Research, PRs #356/#357)** — causa raiz real do coletor Safra Corretora (carteiras): o PDF de novembro mudou separador decimal de vírgula pra ponto, e o regex só aceitava vírgula — zerava os 10 tickers da casa. Corrigido e reproduzido contra a rede real. Também: gate de tamanho mínimo de texto antes do resumo por IA no caminho PDF (só existia no caminho HTML), e setor "TMT" não reconhecido. **Incidente auto-corrigido**: 2 dos testes desta frente escreviam de fato na tabela `coletores_status` de produção (não mockavam `registrar_tentativa`) — poluição detectada, revertida e **confirmada por leitura real em produção** (não assumida) antes de prosseguir; isolamento de teste corrigido no PR #357. Métrica real medida: das 47 linhas de research de casas ativas (de 24.321 linhas totais em `research_itens`, o resto é CVM), 100% estão sem recomendação/preço-alvo porque o resumo por IA só roda quando um humano abre o item na UI, nunca em lote — com retenção de 5 dias, a maioria é apagada antes disso acontecer.

**Fase 6 (UX, PR #359)** — bug real no CALENDÁRIO: rótulo de status (`● CONFIRMADO` etc.) tinha a borda da célula cruzando o texto na última linha do grid mensal — causa raiz medida via Playwright real (`getBoundingClientRect`), não estimada; o wrapper interno do Streamlit renderiza sistematicamente mais baixo que o conteúdo real e não é controlável via CSS no elemento interno — corrigido por compensação no padding da célula externa, validado em 1440px/390px com 1 e 4 eventos/dia. Os outros 2 pontos herdados (eixo Y do IPCA, responsividade 390px de MERCADO) foram **confirmados falsos alarmes** — já corrigidos ancestralmente ou sem overflow real. Confirmado via auditoria real: Streamlit é o terminal principal de fato; `web/` (Next.js) é deliberadamente um espelho somente-leitura mais leve, cobrindo um subconjunto de telas — não há reconstrução dupla, não há inconsistência de estratégia a corrigir agora.

## PRs abertas nesta missão (nenhuma mergeada — regra da missão)

Todas `MERGEABLE`/`CLEAN`, sem conflito de arquivo entre si (ownership por frente respeitado):

| PR | Frente | Resumo |
|---|---|---|
| [#352](https://github.com/rodrigocostasouza2005-coder/Pregao/pull/352) | Coordenação | Este documento de continuidade (docs-only) |
| [#353](https://github.com/rodrigocostasouza2005-coder/Pregao/pull/353) | Fase 3 | DCF nunca usa FCF acumulado (YTD) da CVM como anual |
| [#354](https://github.com/rodrigocostasouza2005-coder/Pregao/pull/354) | Fase 1 | Disparo agendado tarde não derruba mais o job do Actions |
| [#355](https://github.com/rodrigocostasouza2005-coder/Pregao/pull/355) | Fase 2 | Anti-alucinação em texto livre + consenso de research no Perfil |
| [#356](https://github.com/rodrigocostasouza2005-coder/Pregao/pull/356) | Fase 5 | Safra Corretora (decimal) + gate de texto mínimo antes da IA |
| [#357](https://github.com/rodrigocostasouza2005-coder/Pregao/pull/357) | Fase 5 | Isola testes de SEC XBRL de escrita real em produção |
| [#358](https://github.com/rodrigocostasouza2005-coder/Pregao/pull/358) | Fase 4 | `estado_tese()` — acompanhamento real de tese na Carteira Recomendada |
| [#359](https://github.com/rodrigocostasouza2005-coder/Pregao/pull/359) | Fase 6 | Corrige rótulo de status no grid do CALENDÁRIO |

## Pendências (aguardando decisão/autorização do Rodrigo)

**Schema/migration (nenhuma aplicada):**
1. `ia_hibrida_execucoes` / `research_recomendacoes_historico` — ainda não existem no Supabase de produção (pendência já registrada em 13/11, reconfirmada agora: toda telemetria de IA híbrida falha silenciosa-mas-logada).
2. 3 colunas aditivas em `carteira_recomendada_itens` (`sinal_comite`/`confianca_comite`/`score_comite`) — documentada em `sql/carteira_recomendada.sql`, não aplicada; sem ela, `estado_tese()` não detecta rebaixamento/elevação de recomendação para ativo que permanece na carteira.

**Decisão de produto/custo:**
3. Ativar `SINTESE_IA_COMITE_ATIVA` em produção (custo real de Groq) — guard-rails confirmados corretos pela Fase 2, decisão de custo continua do Rodrigo.
4. Disparo externo via cron-job.org para mitigar o atraso de `schedule` do GitHub Actions na raiz (pendência pessoal antiga, não resolvida nesta missão — só a mitigação de alarme falso foi).

**Achados novos, sem dono nesta missão (registrar para a próxima):**
5. `CSNA3` (Companhia Siderúrgica Nacional, ticker líquido) não está mapeado em `data/cvm.py:_mapa_ticker_cnpj()` — quebra o Earnings Reviewer e qualquer feature de calendário/eventos para esse ticker especificamente.
6. Sidebar sobrepõe todo o conteúdo em telas touch ~1024px (tablet), em qualquer aba — interação entre dois fixes anteriores corretos isoladamente (`app.py`/`style.css`).
7. `divida_liquida_ebitda` em `data/prices.py` calcula a razão sem exigir EBITDA > 0 (diferente de `_ev_ebitda` em `data/radar.py`, que já bloqueia corretamente) — pode exibir "dívida baixa" quando o problema real é EBITDA negativo.
8. Dimensão de research independente do sinal quantitativo do Comitê (`data/research/sinal.py`) quase nunca ativa na prática — confirmado real, não só teórico.

## Próxima missão recomendada

O maior gargalo real que sobrou, com evidência desta missão: **a camada de inteligência "híbrida" (telemetria de IA + Research Radar/"o que mudou") está arquitetada e codificada, mas nunca chegou a existir em produção** — duas tabelas-chave (`ia_hibrida_execucoes`, `research_recomendacoes_historico`) nunca foram migradas, então toda a parte do sistema que deveria *aprender/mudar ao longo do tempo* (telemetria de qualidade da IA, histórico de mudança de recomendação de research) degrada silenciosamente pra vazio desde sempre. Isso conecta diretamente com o `estado_tese()` novo da Fase 4 (que já documenta a mesma classe de limitação pra Carteira Recomendada) e com o achado da Fase 2 sobre telemetria falhando silenciosa-mas-logada. Recomendação: uma missão focada em (a) decidir e aplicar as migrations pendentes com segurança, (b) conectar o que já existe no código a elas, (c) medir de verdade o ganho antes de expandir mais escopo.
