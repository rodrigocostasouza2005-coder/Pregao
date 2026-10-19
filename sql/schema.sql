-- PREGAO — tabela de preferencias por usuario (Supabase / Postgres)
-- Rode isso uma vez em: Supabase > SQL Editor > New query

create table if not exists user_prefs (
  sub          text primary key,             -- st.user.sub (ID estavel do Google)
  email        text not null,                -- st.user.email, salvo em minusculo
  preferencias jsonb not null default '{}'::jsonb,
  updated_at   timestamptz not null default now()
);

create index if not exists idx_user_prefs_email on user_prefs (email);

-- RLS ativado e SEM policies: o backend Python usa a service_role key,
-- que sempre ignora RLS. Nenhuma outra chave (ex: anon) consegue ler ou
-- escrever nessa tabela. Isso protege os dados mesmo que a anon key
-- vaze algum dia.
alter table user_prefs enable row level security;

-- updated_at atualizado automaticamente a cada UPDATE
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_user_prefs_updated_at on user_prefs;
create trigger trg_user_prefs_updated_at
before update on user_prefs
for each row execute function set_updated_at();

-- 2026-10-18 (painel administrativo USUÁRIOS, ver data/admin_usuarios.py) —
-- migracao idempotente (ADD COLUMN IF NOT EXISTS em tudo, rodar de novo
-- nao apaga nem altera nenhuma linha ja existente), mesmo padrao ja
-- estabelecido em sql/research.sql pra colunas novas numa tabela
-- existente.
--
-- created_at  = quando o registro desta linha foi criado. AVISO HONESTO:
--               pra quem JA tinha linha em user_prefs antes desta
--               migracao, o DEFAULT now() abaixo grava a DATA DA
--               MIGRACAO, nao a data real de cadastro (esse dado nunca
--               existiu antes - nao tem como reconstruir retroativamente
--               sem inventar historico). So' e' a data de cadastro real
--               pra quem criar a linha DEPOIS desta migracao (ver
--               data/user_prefs.py:registrar_acesso). A UI do painel
--               (ui/usuarios_tab.py) avisa disso explicitamente.
-- last_seen_at = ultimo acesso identificado (ver registrar_acesso) - nulo
--                pra quem ainda nao acessou de novo depois do deploy
--                desta migracao; a UI mostra "sem registro", nunca trata
--                nulo como "inativo ha muito tempo" (seria inventar dado).
alter table user_prefs add column if not exists created_at timestamptz not null default now();
alter table user_prefs add column if not exists last_seen_at timestamptz;

create index if not exists idx_user_prefs_created_at on user_prefs (created_at);
create index if not exists idx_user_prefs_last_seen_at on user_prefs (last_seen_at);
