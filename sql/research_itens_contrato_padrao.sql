-- PREGAO — PROPOSTA de colunas novas pra research_itens, achada na
-- auditoria de ARQUITETURA dos coletores de research (Agente A,
-- 2026-11-12). NAO APLICADO ainda - aguardando aprovacao do Rodrigo
-- (regra do projeto: agente nunca aplica schema/dado real em producao
-- por conta propria). Rode isso uma vez em: Supabase > SQL Editor >
-- New query, SO' depois de revisado. Idempotente (add column if not
-- exists em tudo) - seguro re-rodar e 100% aditivo (nenhum ALTER em
-- coluna/dado existente, nenhum DROP).
--
-- Contexto (ver data/research/base.py, topo do modulo - contrato padrao
-- de item ampliado, e data/research/store.py:salvar_itens):
--
-- O pedido original (Rodrigo, missao de arquitetura 2026-11-12) descreve
-- um registro padrao com: casa/analista/empresa/ticker/setor/
-- data_publicacao/tipo_relatorio/recomendacao/preco_alvo/
-- preco_referencia/horizonte/url_fonte/texto_integral_disponivel.
--
-- A maioria desses campos JA' tem uma coluna equivalente em
-- research_itens (ver sql/research.sql) - nao duplicada aqui:
--   casa            -> casa
--   analista        -> autor
--   ticker          -> tickers (array - 1 relatorio pode cobrir mais de
--                      1 ativo, mais geral que singular)
--   data_publicacao -> data (+ publicado_em, timestamp completo, fase 3)
--   tipo_relatorio  -> tipo
--   recomendacao    -> recomendacao
--   preco_alvo      -> preco_alvo
--   url_fonte       -> link
--
-- Os 5 campos abaixo SAO novos - nenhum coletor existente e' obrigado a
-- preenche-los (seria reescrever os 11 adapters so' pra isso, risco de
-- regressao sem beneficio imediato); data/research/base.py:normalizar_item
-- ja preenche com default seguro (None/False) quem nao preencher, e
-- data/research/store.py:salvar_itens ja sabe mandar a coluna pro
-- Supabase so' quando pelo menos 1 item do lote tiver o campo (mesmo
-- padrao defensivo usado pra 'publicado_em' desde a fase 3 - se a
-- coluna nao existir ainda, tenta de novo sem ela, nunca quebra a
-- coleta de TODAS as casas por isso).

alter table research_itens
  add column if not exists empresa text;

alter table research_itens
  add column if not exists setor text;

alter table research_itens
  add column if not exists preco_referencia numeric;

alter table research_itens
  add column if not exists horizonte text;

alter table research_itens
  add column if not exists texto_integral_disponivel boolean;
