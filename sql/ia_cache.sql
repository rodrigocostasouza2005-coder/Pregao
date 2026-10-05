-- PREGAO — cache GLOBAL de resumos de IA (Research + News), 2026-10-05.
-- Rode isso uma vez em: Supabase > SQL Editor > New query.
--
-- Reutiliza a MESMA infraestrutura Supabase ja usada pelo projeto (nao
-- e' um banco paralelo) - so' uma tabela nova, mesmo padrao ja
-- estabelecido em research_itens/eventos_resultados. Migracao
-- idempotente (IF NOT EXISTS em tudo) - rodar de novo nao apaga nem
-- altera nenhuma linha ja existente.
--
-- chave_documento identifica o documento especifico (link do research,
-- ou hash de titulo+conjunto-de-links do grupo de news) - NUNCA so' o
-- ticker, ver data/ia_cache.py:chave_research/chave_news.
-- status='gerando' enquanto uma requisicao reservou a geracao (resultado
-- ainda NULL); status='concluido' quando o resumo ja' esta pronto.

create table if not exists resumos_ia_cache (
  chave_documento text primary key,
  origem          text not null,               -- 'research' ou 'news' (auditoria/diagnostico)
  link_principal  text,                          -- link/URL do documento (auditoria/debug)
  status          text not null default 'gerando',  -- 'gerando' ou 'concluido'
  resultado       jsonb,                          -- dict completo do resumo (resumo/preco_alvo/recomendacao/etc) - NULL enquanto 'gerando'
  modelo          text,
  criado_em       timestamptz not null default now(),
  atualizado_em   timestamptz not null default now()
);

create index if not exists idx_resumos_ia_cache_origem on resumos_ia_cache (origem);
create index if not exists idx_resumos_ia_cache_status on resumos_ia_cache (status);

-- RLS ativado e SEM policies: o backend Python usa a secret key, que
-- sempre ignora RLS. Mesmo padrao de sql/research.sql / sql/eventos.sql.
alter table resumos_ia_cache enable row level security;
