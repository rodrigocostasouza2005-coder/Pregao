# Missão Master — Consolidação, Auditoria e Evolução do PREGÃO (2026-11-23)

## Objetivo

Não adicionar funcionalidade nova indiscriminadamente. Transformar o Pregão num terminal confiável, integrado, com inteligência de verdade, análise de empresas de alta qualidade, valuation consistente e acompanhamento de teses — via 6 frentes paralelas (infra, Comitê, valuation, Radar/teses, Research, UX/produto).

## Estado inicial (HEAD no disparo da missão)

- `origin/main` = `6d5949c` (PR #351, "extrai Perfil da Empresa do expander em COMITÊ pra aba própria"), na sequência direta das PRs #338–#350 (sessão anterior) e da missão "RECONSTRUÇÃO COMPLETA" (PRs #326–#336, 2026-11-18). Ver `docs/continuidade-pregao-20261118-missao-master.md` — **não redescobrir isso**: design system/paleta, reconstrução de navegação (COMITÊ/CALENDÁRIO/VALUATION/dissolução de SETORES e MORNING-CALL), divergência entre especialistas visível, 3º motor de DCF duplicado removido, Perfil da Empresa conectado ao COMITÊ (e agora com aba própria, #351).
- `CLAUDE.md` já define o fluxo de execução/revisão/merge do repo (worktree isolado obrigatório, merge só com autorização explícita por PR, Saúde dos Dados sempre em PR isolada). Esta missão herda essas regras.
- Regra desta missão (pedido explícito do Rodrigo, 2026-11-23): **nenhum merge** — todas as frentes abrem PR e paralisam ali.

## As 6 frentes

| Fase | Tema | Status |
|---|---|---|
| 1 | Estabilidade operacional e infraestrutura | disparado |
| 2 | Comitê de Investimentos | disparado |
| 3 | Valuation e modelos financeiros | disparado |
| 4 | Radar inteligente e acompanhamento de teses | disparado |
| 5 | Research e qualidade das fontes | disparado |
| 6 | Interface, UX e consolidação do produto | disparado |

(Atualizado pelo coordenador conforme os agentes reportam — os agentes não editam este arquivo diretamente, para não colidir entre si; cada um reporta ao coordenador, que consolida aqui.)

## Mapa de arquivos / ownership (evitar dois agentes implementando a mesma coisa)

- **Fase 1**: `.github/workflows/*.yml`, `jobs/morning_call.py`, `jobs/radar_quedas.py` (só infra/retry/idempotência — lógica de tese é da Fase 4), `jobs/email_utils.py`, `jobs/comite_noturno.py` (só execução/infra — lógica dos especialistas é da Fase 2), `jobs/carteira_recomendada_job.py`, `jobs/coordenador.py`, `data/coletores_status.py`, `data/agendamentos_saude.py`, `data/supabase_client.py`, `ui/sistema_tab.py`. **Saúde dos Dados** (`data/saude_dados.py`, `ui/saude_dados_tab.py`) pertence a esta fase mas em PR própria e isolada (regra 8 do CLAUDE.md).
- **Fase 2**: `data/coordenador_central/*.py` (consolidacao, executor, fluxos, modelagem, pareceres, persistencia, registro, sintese_ia, execucoes_agendadas — exceto `dcf.py`/`dcf_operacional.py`, da Fase 3), `data/market_researcher.py`, `data/empresa_perfil.py`, `data/research/comparador.py`, `data/earnings/reviewer.py` (agente Earnings Reviewer — coleta de dado CVM/SEC em si é Fase 5), `data/x_radar/*`, `ui/coordenador_tab.py`, `ui/central_inteligencias_tab.py`.
- **Fase 3**: `data/coordenador_central/dcf.py`, `data/coordenador_central/dcf_operacional.py`, `data/coordenador_central/modelagem.py`, `data/radar.py` (só `valuation_radar`, o motor — a tela é `ui/radar_tab.py:render_valuation`, arquivo compartilhado com a Fase 4: Fase 3 só lê, não edita), `ui/dcf_operacional.py`, `ui/analises_tab.py` (parte de valuation/simulador).
- **Fase 4**: `ui/radar_tab.py` (dono do arquivo inteiro), `data/radar_quedas.py`, `data/carteira_recomendada.py`, `ui/carteira_recomendada_tab.py`. Não tocar `jobs/radar_quedas.py` (Fase 1) nem `data/saude_dados.py`.
- **Fase 5**: `data/research/*.py` (todas as casas + `store.py`/`qualidade.py`/`resumir.py`/`embeddings.py`/`historico.py`/`sinal.py`/`tese.py` — `comparador.py` fica com a Fase 2), `data/earnings/cvm_balanco.py`, `cvm_dfc.py`, `cvm_dre.py`, `editorial.py`, `sec_xbrl.py` (coleta, não o Reviewer), `ui/research_tab.py`, `ui/news_tab.py`, `data/news.py`, `data/news_setores.py`.
- **Fase 6**: `ui/design_system.py`, `ui/navegacao.py`, `ui/workspace.py`, `ui/busca.py`, `ui/paineis.py`, `ui/graficos.py`, `ui/visao_geral.py`, `ui/mercado_tab.py`, `ui/macro_tab.py`, `ui/calendario_tab.py`, `ui/cvm_tab.py`, `ui/setores_tab.py`, `ui/top_mercado_tab.py`, `ui/usuarios_tab.py`, `web/**` (Next.js — auditoria de estratégia, não reconstrução). Achados de UX em arquivo de outra frente são **registrados**, não editados direto, a menos que seja fix visual trivial sem lógica nova.

## Autorizações e restrições (vale para as 6 frentes)

Autorizado: auditoria, implementação, testes, branches, PRs — sem merge nesta missão. Proibido sem autorização explícita adicional: alterar secrets, expor credencial, operação destrutiva/migration em produção, envio real de e-mail em teste, qualquer ação irreversível, novo serviço pago, duplicar estrutura já existente. Problemas que dependam disso: documentar a solução pronta e a ação pendente, não executar.

## Problemas encontrados

_(preenchido pelo coordenador conforme os relatórios chegam)_

## PRs abertas nesta missão

_(preenchido pelo coordenador)_

## Pendências

_(preenchido pelo coordenador)_

## Próxima missão recomendada

_(preenchido ao final)_
