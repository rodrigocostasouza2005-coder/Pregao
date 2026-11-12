-- PREGAO — PROPOSTA de indices novos pra research_itens, achada na
-- auditoria de infra/persistencia de dados (2026-11-11). NAO APLICADO
-- ainda - aguardando aprovacao do Rodrigo (regra do projeto: agente
-- nunca aplica schema/dado real em producao por conta propria). Rode
-- isso uma vez em: Supabase > SQL Editor > New query, SO' depois de
-- revisado. Idempotente (if not exists em tudo) - seguro re-rodar e
-- 100% aditivo (so' cria indices, nenhum ALTER em coluna/dado).
--
-- Contexto (ver data/research/store.py):
--
-- 1) apagar_itens_antigos() roda, a cada chamada, um
--    `delete from research_itens where coletado_em < :limite` (ver
--    store.py:apagar_itens_antigos, 2a chamada) sem nenhum indice na
--    coluna 'coletado_em' hoje (sql/research.sql so' indexa 'casa' e
--    'data') - cada rodada faz um full table scan pra achar as linhas
--    a apagar. research_itens e' perecivel/alto-giro (retencao de 5
--    dias, recoletado com frequencia), entao essa rotina roda com
--    regularidade - o custo cresce com o tamanho total da tabela, nao
--    so' com o que vai ser apagado.
--
-- 2) ultima_coleta_em(casa) (ver store.py) filtra por 'casa' (ja
--    indexado) e ordena por 'coletado_em' desc limit 1 - o indice
--    composto (casa, coletado_em desc) deixa esse ORDER BY+LIMIT
--    resolvido direto pelo indice, sem precisar varrer e ordenar em
--    memoria todas as linhas da casa.

create index if not exists idx_research_itens_coletado_em
  on research_itens (coletado_em);

create index if not exists idx_research_itens_casa_coletado_em
  on research_itens (casa, coletado_em desc);
