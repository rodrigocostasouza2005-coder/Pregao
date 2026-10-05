-- PREGAO — eventos de resultados corporativos com data REAL (CONFIRMADO/
-- ESTIMADO), fase COLETOR DE DATAS DE RESULTADOS (2026-10-02).
-- Rode isso uma vez em: Supabase > SQL Editor > New query.
--
-- Reutiliza a MESMA infraestrutura Supabase ja usada pelo projeto (nao
-- e' um banco paralelo) - so' uma tabela nova, no mesmo padrao ja
-- estabelecido em research_recomendacoes_historico (ver sql/research.sql).
-- PRAZO_CVM continua calculado on-the-fly por data/eventos.py, NUNCA
-- persistido aqui - e' uma regra deterministica, recalcular e' barato e
-- sempre atualizado. So' datas REAIS (CONFIRMADO/ESTIMADO) descobertas
-- pelo coletor (data/eventos_coleta.py) valem a pena guardar.

create table if not exists eventos_resultados (
  ticker       text not null,
  periodo      text not null,          -- ex: '3T26'
  data_evento  date not null,
  status       text not null,          -- CONFIRMADO ou ESTIMADO (PRAZO_CVM nunca entra aqui)
  fonte        text not null,          -- ex: 'Petrobras RI' ou o nome do veiculo de noticia
  url_fonte    text,
  coletado_em  timestamptz not null default now(),
  primary key (ticker, periodo)
);

create index if not exists idx_eventos_resultados_ticker on eventos_resultados (ticker);

-- RLS ativado e SEM policies: o backend Python usa a secret key, que
-- sempre ignora RLS. Mesmo padrao de sql/schema.sql / sql/research.sql.
alter table eventos_resultados enable row level security;
