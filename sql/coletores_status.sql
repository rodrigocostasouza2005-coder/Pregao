-- PREGAO — tabela de SAUDE DOS COLETORES (status real de execucao),
-- 2026-10-09 (FASE "SAUDE DOS DADOS", preparacao pra aba RADAR).
-- Rode isso uma vez em: Supabase > SQL Editor > New query.
--
-- Reutiliza a MESMA infraestrutura Supabase ja usada pelo projeto (nao
-- e' um banco paralelo) - mesmo padrao ja estabelecido em
-- user_prefs/research_itens/resumos_ia_cache. Migracao idempotente
-- (IF NOT EXISTS em tudo) - rodar de novo nao apaga nem altera nenhuma
-- linha ja existente.
--
-- Diferente de research_itens/eventos_resultados (que guardam O DADO
-- coletado), esta tabela guarda só o METADADO da TENTATIVA de coleta -
-- "o coletor X rodou agora, deu certo/errado, salvou/nao salvou,
-- achou quantos registros novos" - e' o que falta hoje pra distinguir
-- "sem novidade" de "fonte caiu" de "nunca rodou" (ver data/saude_dados.py).
--
-- execucao_ok   = a BUSCA dos dados (rede/parsing) funcionou.
-- persistencia_ok = a GRAVACAO do que foi buscado funcionou (so' faz
--                    sentido quando execucao_ok=true; coletor que nem
--                    buscou nao tem o que persistir).
-- parcial       = coleta funcionou mas incompleta (ex: algumas fontes
--                 de um grupo falharam, outras nao).
-- ultimo_sucesso_em = so' avanca quando execucao_ok E persistencia_ok
--                      sao true na tentativa (ver
--                      data/coletores_status.py:registrar_tentativa) -
--                      preserva o ultimo sucesso real mesmo que a
--                      tentativa mais recente tenha falhado.

create table if not exists coletores_status (
  nome                 text primary key,     -- identificador estavel, ex: "Genial Analisa", "NEWS"
  fonte                text not null,         -- fonte de dados usada, p/ exibicao
  categoria            text not null default '',  -- agrupamento na UI (ex: "Research", "Calendario")
  execucao_ok          boolean not null,
  persistencia_ok      boolean not null default true,
  parcial              boolean not null default false,
  registros_novos      integer not null default 0,
  ultimo_erro          text,
  ultima_tentativa_em  timestamptz not null default now(),
  ultimo_sucesso_em    timestamptz,
  updated_at           timestamptz not null default now()
);

create index if not exists idx_coletores_status_categoria on coletores_status (categoria);

-- RLS ativado e SEM policies: o backend Python usa a secret key, que
-- sempre ignora RLS. Mesmo padrao de sql/research.sql / sql/ia_cache.sql.
alter table coletores_status enable row level security;

-- create or replace (nao "if not exists"): a funcao em si e' idempotente
-- e identica a' de sql/schema.sql - redeclarar aqui so' torna este
-- arquivo seguro de rodar sozinho, sem depender da ordem de execucao.
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_coletores_status_updated_at on coletores_status;
create trigger trg_coletores_status_updated_at
before update on coletores_status
for each row execute function set_updated_at();
