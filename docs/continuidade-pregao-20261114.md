# Continuidade PREGÃO — 2026-11-14

Documento de retomada gerado a partir de uma auditoria de continuidade completa (5 agentes paralelos, somente leitura: Git/PRs/CI/deploy, Supabase, Terminal/Mercado/Coletores, Comitê de Investimentos/Valuation/Carteiras, Visual/design system). Relatório completo (mapa funcional, problemas priorizados, plano de fases) preservado fora do repositório; este arquivo resume o essencial pra quem retomar o trabalho depois.

## Estado no momento desta auditoria

- HEAD auditado: `72a3b41` (PR #315), 100% sincronizado com `origin/main`, 0 PRs abertas, CI verde.
- 3 crons rodando (`coletores-nuvem.yml`, "Comitê de Investimentos — análise noturna", `radar-morning-call.yml`); Morning Call confirmado enviando e-mail real (1 assinante opt-in), mas ~8h atrasado — limitação conhecida de agendamento do GitHub Actions, workaround via cron-job.org documentado em `MANUAL.md` mas não ativo.
- Deploy Streamlit Cloud (`pregao.streamlit.app`) e Vercel (`pregao.vercel.app`, app Next.js em `web/`) ambos no ar. Frontend Next.js dormente desde 2026-10-30 (~2 semanas sem trabalho real de UI).
- 189 worktrees acumulados; 1 branch sem PR mapeada ("Equity Research 18 perguntas") candidata a investigação dedicada.

## Migrações aplicadas nesta retomada (2026-11-14)

As 4 migrações abaixo, propostas em sessões anteriores e nunca aplicadas em produção, foram aplicadas com aprovação explícita do Rodrigo nesta sessão (todas aditivas, sem DROP/perda de dado):

1. `sql/coletores_status_metricas.sql` — 8 colunas cumulativas em `coletores_status` (habilita taxa de sucesso/tempo médio real por fonte).
2. `sql/research_itens_contrato_padrao.sql` — colunas `empresa/setor/preco_referencia/horizonte/texto_integral_disponivel` em `research_itens`.
3. 3 `ALTER TABLE` presentes no próprio `sql/research.sql` (não marcados "proposto", mas nunca aplicados de fato — achado desta auditoria): `preco_alvo/recomendacao/publicado_em` em `research_itens`.
4. `sql/carteira_recomendada.sql` — as 3 tabelas (`carteira_recomendada_itens/_historico/_acompanhamento`) com índices e RLS sem policy (mesmo padrão do resto do projeto).

**Ainda não aplicadas (fora do escopo desta retomada, decidir depois)**: `ia_hibrida_execucoes`, `research_itens_historico`, `research_recomendacoes_historico` (este sem aviso de "proposto" no arquivo — mas confirmado ausente em produção), `x_sinais*`.

## Bug corrigido nesta retomada

`ui/carteira_recomendada_tab.py:_resumo()` lia `cenario_macro` no shape ANTIGO (DataFrame indexado por coluna, chaves `selic_meta`/`cdi`/`focus_ipca`) — mas desde o PR #313, `data/carteira_recomendada.py:_contexto_macro()` produz `{nome_indicador: {"valor","unidade","referencia","detalhe","erro"}}` (chaves como `"Selic meta"`/`"CDI"`/`"Focus IPCA 2026"`). A seção "CENÁRIO MACRO" nunca renderizava, sem erro visível — nenhuma fixture de teste anterior populava `cenario_macro` de verdade (`_carteira()` sempre usava `{}`). Corrigido pra ler o shape atual, iterando todos os indicadores com `valor` não nulo (em vez de 3 chaves fixas antigas). 2 testes de regressão novos em `tests/test_carteira_recomendada_tab_ui.py`.

## Decisões a preservar (não redescobrir em sessão futura)

- JPMorgan/BofA/Morgan Stanley/Citi/Goldman Sachs/Jefferies/Deutsche Bank = hub editorial público, **nunca** research pago — documentado no próprio código (`data/research/__init__.py`), não é limitação a esconder.
- Itaú BBA/Bradesco BBI sem research pago = decisão deliberada (sem canal público de coleta) — diferente de XP/Genial Analisa, que são bloqueio técnico ATIVO (Akamai/WAF), não decisão.
- Genial (Lives) com `disponivel=False` desde 2026-10-24 (404 no feed RSS do YouTube) é decisão — mas a coleta residual (13 linhas) continua acontecendo por um caminho separado da UI.
- X Radar desligado = decisão de custo (falta `X_BEARER_TOKEN`), não bug — arquitetura pronta.
- `recomendacao`/`preco_alvo` em `research_itens` só existem de fato DEPOIS que o resumo de IA é gerado — nunca estrutural da fonte original.
- Migrations ficam paradas até aprovação explícita do Rodrigo por item — regra do próprio `CLAUDE.md` do projeto, não esquecimento.
- Saúde dos Dados é frente isolada (regra 8 do `CLAUDE.md`) — não misturar correção nela com mudança em outra aba.

## Achados que ainda precisam de decisão/trabalho

- **Resumo de IA do research em 0% de cobertura** (0 de 155 itens na janela de retenção atual) — provável mesma causa já conhecida (`GROQ_API_KEY` ausente nos secrets do GitHub Actions), mas a severidade real (0%, não "degradado") só foi medida nesta auditoria.
- **20 execuções órfãs em `coordenador_analises`** desde 2026-11-05 (11 dias) — script de encerramento já revisado e testado na PR #312, nunca executado contra produção. Precisa de autorização explícita pra rodar.
- **Síntese de IA real do Comitê (`sintese_ia=True`)** segue dormente — nenhum caller de produção passa o parâmetro, só testes. Decisão de custo de API pendente.
- **Ciclo de persistência da Carteira Recomendada** — as tabelas agora existem (ver acima), mas nenhum job/UI real ainda chama `registrar_revisao`/`registrar_acompanhamento`. Falta o código que decide quando/o que registrar a cada rodada.
- **Valuation Reviewer** nunca retornou `disponivel=True` nas 3 únicas execuções reais registradas — confirmar se é esperado (audita sem "aprovar" disponibilidade) ou bug raro.
- **10 arquivos de UI sem nenhum uso do design system**: `busca.py, calendario_tab.py, navegacao.py, paineis.py, radar_tab.py, saude_dados_tab.py, sistema_tab.py, top_mercado_tab.py, workspace.py, dcf_operacional.py`.
- **Workspace modular** hoje só ativo em MERCADO e MACRO (divergência real da documentação anterior, que também listava VISÃO GERAL — vale decidir se reativa ou documenta a remoção).
- **Monitoramento de mudança de tese** (`data/radar.py:mudancas_tese`) tem mecanismo real, mas a única fonte (snapshot Genial) está desligada — não detecta nada novo até haver fonte viva.

## Plano de fases (ordem recomendada)

1. **Integridade e estabilidade de dados** — em andamento nesta retomada (migrações + bug do Cenário Macro). Falta: rodar o script de encerramento de órfãos (com autorização).
2. **Coletores e integrações** — cadastrar `GROQ_API_KEY` no Actions, reativar disparo externo do Morning Call (cron-job.org), confirmar `GEMINI_API_KEY` em produção.
3. **Comitê de Investimentos** — decidir sobre `sintese_ia=True` em produção, investigar o Valuation Reviewer.
4. **Análises, valuation e recomendações** — implementar o job/caller que ativa o ciclo da Carteira Recomendada, documentar os 3 motores de DCF existentes (Model Builder, Valuation Reviewer, simulador manual em `ui/analises_tab.py`), implementar histórico de recomendações do usuário.
5. **Terminal e experiência visual** — estender o design system pras 10 telas restantes, revalidar responsividade (4 telas sem harness: busca/painéis/navegação/saúde dos dados) com Playwright real, decidir sobre o workspace modular.
6. **Carteiras, monitoramento e avançado** — decidir fonte viva pro monitoramento de tese, decidir sobre X Radar e sobre o futuro do app Next.js/Vercel.

## Pendências administrativas (fora do alcance de qualquer agente)

- Decidir sobre custo de API (Groq p/ síntese de IA do Comitê, resumo de research).
- Configurar `GROQ_API_KEY` nos secrets do GitHub Actions.
- Ativar/configurar o disparo externo do Morning Call (cron-job.org).
- Autorizar a execução do script de encerramento de análises órfãs.
- Investigar a branch "Equity Research 18 perguntas" (worktree sem PR mapeada).
