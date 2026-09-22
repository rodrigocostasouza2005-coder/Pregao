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
