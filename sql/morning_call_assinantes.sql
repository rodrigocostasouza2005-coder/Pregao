-- PREGÃO — Morning Call por assinante (opt-in individual, 2026-10-16).
-- Migration aditiva e idempotente. Executar no Supabase SQL Editor.
--
-- Não cria tabela nova pra assinatura: o opt-in mora dentro da coluna
-- `preferencias` (jsonb) que já existe em `user_prefs` (ver sql/schema.sql)
-- — mesma chave "morning_call_email" usada por qualquer outra preferência
-- de CONFIG, sem precisar de migration pra isso.
--
-- O que muda aqui é só `morning_call_execucoes`: antes guardava 1 linha
-- por EXECUÇÃO do job (destinatário único via EMAIL_TO fixo); agora
-- guarda 1 linha por ENVIO a um assinante individual, então precisa de
-- colunas pra identificar o assinante e o dia de referência, e de uma
-- forma de distinguir envio REAL (AGENDADO) de envio de TESTE (pra um
-- único endereço explícito, nunca contado como entrega aos assinantes).
alter table morning_call_execucoes add column if not exists destinatario_sub text;
alter table morning_call_execucoes add column if not exists pregao_referencia date;
alter table morning_call_execucoes add column if not exists modo text not null default 'AGENDADO';

-- Idempotência real no banco (não só na aplicação): nenhum assinante
-- pode receber o Morning Call AGENDADO duas vezes no mesmo dia de
-- referência, mesmo com 2 execuções concorrentes do job (retry manual,
-- "Re-run failed jobs" do GitHub Actions, ou 2 sessões disparando ao
-- mesmo tempo). Escopado a modo='AGENDADO': um envio de TESTE pro
-- mesmo endereço no mesmo dia nunca é bloqueado por isso, nem bloqueia
-- o envio AGENDADO real daquele dia.
create unique index if not exists idx_morning_call_execucoes_dedup_assinante
  on morning_call_execucoes (destinatario, pregao_referencia)
  where modo = 'AGENDADO' and destinatario is not null;

create index if not exists idx_morning_call_execucoes_modo
  on morning_call_execucoes (modo, pregao_referencia);
