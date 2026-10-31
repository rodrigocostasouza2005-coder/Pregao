-- PREGÃO — checkpoints de rotação de coletores (2026-10-31).
-- Rode isso uma vez em: Supabase > SQL Editor > New query. Idempotente.
--
-- Substitui, pro CALENDÁRIO (RI/NEWS/PRAZO_CVM de resultados, ver
-- data/eventos_coleta.py), o checkpoint local em arquivo + o fallback
-- de GITHUB_RUN_NUMBER (coletor_local.py:_universo_rotativo) - os dois
-- avançam o offset em exatamente +1 por execução, o que cobre o
-- universo inteiro em N execuções. Isso era aceitável com N=84
-- (~3 dias pra cobertura completa), mas o universo virou 481 tickers em
-- 2026-10-24 (reforma CVM/FCA + watchlists, ver PROGRESSO.md) sem essa
-- rotação ser revisada - N=481 execuções (agendamento seg-sex, ~26/dia)
-- levam ~18 dias úteis pra UMA rodada completa, deixando a maioria das
-- empresas sem a tentativa de descobrir a data REAL (RI/NEWS) por
-- semanas, presas no fallback genérico PRAZO_CVM. Esta tabela permite
-- avançar o checkpoint pelo TRABALHO REAL feito em cada execução
-- (quantos tickers o orçamento de 5min conseguiu processar), não um
-- contador fixo - e sobrevive ao filesystem efêmero do GitHub Actions
-- (motivo original do hack de GITHUB_RUN_NUMBER).

create table if not exists coletor_checkpoints (
  nome          text primary key,             -- ex: 'calendario_eventos'
  offset_atual  integer not null default 0,
  atualizado_em timestamptz not null default now()
);

-- RLS ativado e SEM policies: o backend Python usa a secret key, que
-- sempre ignora RLS. Mesmo padrao de sql/coletores_status.sql.
alter table coletor_checkpoints enable row level security;
