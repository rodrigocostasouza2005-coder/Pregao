-- PREGAO — documentos oficiais da CVM (fato relevante, comunicado ao
-- mercado, avisos aos acionistas/proventos, calendário de eventos)
-- Rode isso uma vez em: Supabase > SQL Editor > New query

create table if not exists cvm_documentos (
  link          text primary key,          -- Link_Download da CVM (RAD/ENET), chave unica (upsert)
  ticker        text not null,
  tipo          text not null,              -- FATO_RELEVANTE / COMUNICADO / PROVENTOS / CALENDARIO
  assunto       text not null,
  data          text not null,              -- data de entrega na CVM, 'YYYY-MM-DD' (como vem da fonte)
  destaque      boolean not null default false,  -- true so' pra FATO_RELEVANTE
  coletado_em   timestamptz not null default now()
);

create index if not exists idx_cvm_documentos_ticker on cvm_documentos (ticker);
create index if not exists idx_cvm_documentos_data on cvm_documentos (data desc);

-- feed "vivo" (nao e' historico) - documentos com mais de 5 dias sao
-- apagados pela propria aplicacao (data/cvm.py:apagar_documentos_antigos),
-- nao por uma rotina do banco. Essa tabela e' so' cache compartilhado
-- entre sessoes/deploys; a fonte de verdade continua sendo a CVM.

-- RLS ativado e SEM policies: o backend Python usa a secret key, que
-- sempre ignora RLS. Nenhuma outra chave (ex: anon) consegue ler ou
-- escrever nessa tabela. Mesmo padrao de sql/research.sql e sql/schema.sql.
alter table cvm_documentos enable row level security;
