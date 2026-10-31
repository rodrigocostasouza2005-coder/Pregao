-- PREGAO — embeddings vetoriais da biblioteca permanente de research
-- (research_premissas, ver sql/research_premissas.sql) pra busca semantica
-- (RAG, Equity Research Library Fase C, pedido do Rodrigo 2026-10-30).
--
-- ATENCAO - PRE-REQUISITO AINDA NAO CONFIRMADO: a disponibilidade da
-- extensao pgvector neste projeto Supabase nao foi verificada (sem acesso
-- pra executar SQL direto nesta tarefa). O comando abaixo
-- (`create extension if not exists vector`) E' TAMBEM O TESTE REAL dessa
-- disponibilidade. Se ele FALHAR ao rodar (ex: erro "extension vector is
-- not available" ou similar), pgvector NAO esta habilitado neste projeto
-- Supabase e a Fase C de busca semantica real NAO pode funcionar como
-- esta — reporte isso ao Rodrigo. Nenhum outro modulo do projeto depende
-- de pgvector pra funcionar: data/research/embeddings.py:buscar() cai
-- automaticamente pra busca so' lexical/estrutural quando a tabela/RPC
-- abaixo nao existir ou a chamada falhar (sempre dentro de try/except,
-- nunca quebra a aba RESEARCH).
--
-- Rode isso uma vez em: Supabase > SQL Editor > New query. Idempotente
-- (if not exists / create or replace em tudo, seguro re-rodar). So'
-- CRIA objetos novos — nenhum ALTER em tabela existente (research_itens,
-- research_premissas ou qualquer outra).

create extension if not exists vector;

-- link = mesmo link (chave) de research_premissas.link — SEM foreign key,
-- pelo mesmo motivo de research_premissas nao ter FK pra research_itens
-- (ver sql/research_premissas.sql): ciclos de vida independentes. Uma
-- linha aqui so' existe depois que research_premissas.link ja foi
-- extraido por IA (data/research/resumir.py) — mas nenhuma constraint de
-- banco impõe isso, e' responsabilidade de quem chama
-- data/research/embeddings.py:indexar_pendentes.
create table if not exists research_embeddings (
  link             text primary key,
  embedding        vector(768) not null,      -- 768 = config.GEMINI_EMBEDDING_DIMENSAO (Gemini gemini-embedding-001, output_dimensionality=768)
  texto_indexado   text not null,              -- string determinística que gerou este vetor (ver embeddings.py:_texto_para_indexar) - usada pra saber se precisa reindexar
  modelo_embedding text,
  atualizado_em    timestamptz not null default now()
);

-- HNSW (nao ivfflat): a doc oficial do Supabase recomenda HNSW "pela
-- performance e robustez" pra pgvector >= 0.7.0 com vetores de ate 2000
-- dimensoes (https://supabase.com/docs/guides/ai/vector-indexes) — 768
-- dimensoes aqui esta bem dentro desse limite. Se o Supabase do projeto
-- tiver uma versao de pgvector mais antiga que nao suporte HNSW, este
-- create index falha isoladamente (a tabela/coluna acima continua
-- existindo) — nesse caso, troque pra
-- `using ivfflat (embedding vector_cosine_ops) with (lists = 100)` como
-- fallback, que funciona em qualquer versao do pgvector.
create index if not exists idx_research_embeddings_vector
  on research_embeddings using hnsw (embedding vector_cosine_ops);

-- RLS ativado e SEM policies: mesmo padrao de TODAS as outras tabelas do
-- projeto (ver sql/schema.sql, sql/research.sql, sql/research_premissas.sql)
-- — so' a service role key do backend Python (data/supabase_client.py)
-- le/escreve, nunca o cliente anonimo/publico.
alter table research_embeddings enable row level security;

-- RPC de busca por similaridade de cosseno (receita oficial Supabase +
-- pgvector, https://supabase.com/docs/guides/ai/vector-columns) -
-- chamavel via `cliente.rpc("match_research_embeddings", {...})` no
-- Python (ver data/research/embeddings.py:_buscar_por_similaridade).
--
-- filtro_links (opcional, NULL = sem filtro) restringe a busca vetorial a
-- um subconjunto de links JA filtrado estruturalmente (por ticker/casa/
-- data, feito em Python ANTES desta chamada) - evita comparar contra a
-- tabela inteira quando o filtro estrutural ja' reduziu bastante o
-- universo de candidatos, e garante que a busca semantica nunca "escapa"
-- de um filtro explicito do usuario (ex: ticker=PETR4).
create or replace function match_research_embeddings (
  query_embedding vector(768),
  match_count int,
  filtro_links text[] default null
)
returns table (
  link text,
  similaridade float
)
language sql stable
as $$
  select
    research_embeddings.link,
    1 - (research_embeddings.embedding <=> query_embedding) as similaridade
  from research_embeddings
  where filtro_links is null or research_embeddings.link = any(filtro_links)
  order by research_embeddings.embedding <=> query_embedding asc
  limit match_count;
$$;
