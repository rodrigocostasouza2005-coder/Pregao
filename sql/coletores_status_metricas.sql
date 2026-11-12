-- PREGAO — PROPOSTA de colunas novas (METRICAS cumulativas) pra
-- coletores_status, achada na auditoria de ARQUITETURA dos coletores de
-- research (Agente A, 2026-11-12). NAO APLICADO ainda - aguardando
-- aprovacao do Rodrigo (regra do projeto: agente nunca aplica
-- schema/dado real em producao por conta propria). Rode isso uma vez
-- em: Supabase > SQL Editor > New query, SO' depois de revisado.
-- Idempotente (add column if not exists em tudo) - seguro re-rodar e
-- 100% aditivo (nenhum ALTER em coluna/dado existente).
--
-- Contexto (achado real da auditoria, ver sql/coletores_status.sql):
-- coletores_status guarda so' a ULTIMA tentativa de cada coletor (upsert
-- por nome) - nao existe nenhuma forma de calcular "taxa de sucesso" ou
-- "tempo medio de coleta" so' com essas colunas, porque o historico de
-- tentativas anteriores nao e' guardado em lugar nenhum. Em vez de criar
-- uma tabela de LOG (cresceria sem limite, exigiria retencao/limpeza
-- propria), este arquivo propoe CONTADORES CUMULATIVOS incrementados a
-- cada tentativa (ver data/coletores_status.py:registrar_tentativa) -
-- mesmo espirito do "upsert que preserva o que ja existia" ja usado pra
-- ultimo_sucesso_em (nunca reseta, so' avanca).
--
-- taxa_sucesso(nome)/tempo_medio_s(nome) (data/coletores_status.py) leem
-- essas colunas pra calcular as metricas pedidas (Rodrigo, missao de
-- arquitetura 2026-11-12): taxa de sucesso, tempo medio, duplicidades,
-- publicacoes encontradas vs documentos extraidos - tudo derivado de
-- numeros REAIS acumulados, nunca estimado/interpolado.

alter table coletores_status
  add column if not exists tempo_ultima_execucao_s double precision;

alter table coletores_status
  add column if not exists total_tentativas integer not null default 0;

alter table coletores_status
  add column if not exists total_sucessos integer not null default 0;

alter table coletores_status
  add column if not exists total_falhas integer not null default 0;

alter table coletores_status
  add column if not exists total_tempo_s double precision not null default 0;

alter table coletores_status
  add column if not exists total_publicacoes_encontradas integer not null default 0;

alter table coletores_status
  add column if not exists total_documentos_extraidos integer not null default 0;

alter table coletores_status
  add column if not exists total_duplicidades integer not null default 0;
