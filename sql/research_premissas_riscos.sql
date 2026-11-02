-- PREGAO — coluna aditiva `riscos` em research_premissas (fechamento do
-- gap de riscos do Comparador de Casas, pedido do Rodrigo 2026-11-01).
-- Mesmo padrao de `premissas` (sql/research_premissas.sql): frases
-- curtas extraidas do texto do relatorio, NUNCA inventadas/calculadas -
-- ver data/research/resumir.py:_extrair_premissas_projecoes.
--
-- Rode isso uma vez em: Supabase > SQL Editor > New query. Idempotente
-- (add column if not exists, seguro re-rodar). So' ADITIVO - nao toca
-- nenhuma linha/coluna existente.

alter table research_premissas add column if not exists riscos text[] not null default '{}';
