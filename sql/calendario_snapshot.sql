-- PREGAO — snapshot persistido do calendario de resultados, 2026-10-05.
-- Rode isso uma vez em: Supabase > SQL Editor > New query.
--
-- Desacopla "quando o usuario abre o CALENDARIO" de "quando o calculo
-- caro (CVM + Supabase por ticker) acontece": o coletor (coletor_local.py,
-- agendado) calcula o calendario pro universo inteiro e grava AQUI; a UI
-- (ui/calendario_tab.py) so' LE esta tabela (1 consulta, instantanea) -
-- nunca recalcula ao renderizar/navegar. Singleton (1 linha so',
-- id='latest') - nao e' historico, so' o ultimo snapshot valido.
--
-- Migracao idempotente (IF NOT EXISTS em tudo) - rodar de novo nao
-- apaga nem altera nenhuma linha ja existente.

create table if not exists calendario_snapshot (
  id            text primary key,
  eventos       jsonb not null,
  atualizado_em timestamptz not null default now()
);

-- RLS ativado e SEM policies: o backend Python usa a secret key, que
-- sempre ignora RLS. Mesmo padrao de sql/research.sql / sql/eventos.sql /
-- sql/ia_cache.sql.
alter table calendario_snapshot enable row level security;
