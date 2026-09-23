-- PREGAO — itens de research coletados das casas (Genial Analisa etc.)
-- Rode isso uma vez em: Supabase > SQL Editor > New query

create table if not exists research_itens (
  link          text primary key,          -- URL do relatorio original, chave unica (upsert)
  casa          text not null,              -- ex: 'Genial Analisa'
  titulo        text not null,
  data          text,                       -- data do relatorio, 'YYYY-MM-DD' (como vem da fonte)
  autor         text,
  tipo          text not null,              -- ACOES / ESTRATEGIA / MACRO / NEWSLETTER
  tickers       text[] not null default '{}',
  resumo        text,                       -- resumo por IA, com palavras proprias - NUNCA o texto completo
  modelo_resumo text,                       -- ex: 'llama-3.1-8b-instant' (qual LLM gerou o resumo)
  coletado_em   timestamptz not null default now()
);

create index if not exists idx_research_itens_casa on research_itens (casa);
create index if not exists idx_research_itens_data on research_itens (data desc);

-- RLS ativado e SEM policies: o backend Python usa a secret key, que
-- sempre ignora RLS. Nenhuma outra chave (ex: anon) consegue ler ou
-- escrever nessa tabela. Mesmo padrao de sql/schema.sql (user_prefs).
alter table research_itens enable row level security;
