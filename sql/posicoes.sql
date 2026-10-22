-- PREGÃO — cadastro de posições reais (quantidade + preço médio por ativo), 2026-10-22.
-- Rode isso uma vez em: Supabase > SQL Editor > New query.
--
-- Mesma infraestrutura Supabase já usada pelo projeto (não é banco
-- paralelo) - so' uma tabela nova, mesmo padrao ja estabelecido em
-- sql/ia_cache.sql / sql/user_prefs (ver data/user_prefs.py). Migracao
-- idempotente (IF NOT EXISTS em tudo) - rodar de novo nao apaga nem
-- altera nenhuma linha ja existente.
--
-- Uma linha por (sub, ticker): cadastrar de novo o mesmo ticker pro
-- mesmo usuario ATUALIZA quantidade/preco_medio (upsert, ver
-- data/posicoes.py:salvar_posicao), nunca duplica. Usada por
-- data/radar.py:risco_carteira pra calcular concentracao/exposicao/
-- correlacao/volatilidade/drawdown/cenarios de estresse de verdade -
-- sem linha aqui pro usuario, o modulo NUNCA deriva posicao a partir da
-- watchlist (watchlist != carteira, regra explicita do projeto).

create table if not exists posicoes_carteira (
  sub             text not null,
  ticker          text not null,
  quantidade      numeric not null,
  preco_medio     numeric not null,
  -- data de referencia do preco medio informado pelo usuario (ex: data da
  -- ultima compra/calculo) - so' auditoria/exibicao, nunca usada como
  -- preco atual (esse sempre vem da cotacao em tempo real, ver data/prices.py)
  data_referencia date not null default current_date,
  criado_em       timestamptz not null default now(),
  atualizado_em   timestamptz not null default now(),
  primary key (sub, ticker)
);

create index if not exists idx_posicoes_carteira_sub on posicoes_carteira (sub);

-- RLS ativado e SEM policies: o backend Python usa a secret key, que
-- sempre ignora RLS. Mesmo padrao de sql/ia_cache.sql / sql/research.sql.
alter table posicoes_carteira enable row level security;
