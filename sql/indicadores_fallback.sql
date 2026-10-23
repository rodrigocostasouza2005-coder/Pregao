-- PREGAO — fallback persistente de indicadores fundamentalistas
-- (data/prices.py:obter_indicadores, 2026-10-23). Rode uma vez em:
-- Supabase > SQL Editor > New query. Idempotente (if not exists em
-- tudo, seguro re-rodar). Reutiliza a MESMA infraestrutura Supabase já
-- usada pelo projeto - não é um banco paralelo.
--
-- Causa raiz investigada (incidente: todos os ativos da watchlist
-- mostrando "indisponível agora" em P/L/P-VP/DY/etc, com cotação
-- funcionando normalmente): o fallback existente
-- (data/prices.py:_ultimo_indicadores_valido, @st.cache_resource) só
-- vive na MEMÓRIA do processo Streamlit - toda vez que o app reinicia
-- (Streamlit Community Cloud reinicia o container a cada push pra
-- main, não só recarrega o script), esse fallback zera. Se o Yahoo
-- Finance estiver bloqueando tk.info (.info - já documentado, bloqueio
-- conhecido de IP de datacenter, diferente do endpoint de cotação que
-- continua respondendo) justo depois de um restart, TODOS os tickers
-- ficam sem nenhum valor-base pra cair de volta, mesmo tendo
-- funcionado minutos antes do deploy. Esta tabela dá ao fallback uma
-- memória que sobrevive ao restart - sem mudar em nada o
-- comportamento quando a coleta de agora funciona.

create table if not exists indicadores_fallback (
  ticker       text primary key,
  dados        jsonb not null,      -- mesmo schema de obter_indicadores() MENOS beta/_coletado_em (recalculados/preenchidos na leitura)
  coletado_em  timestamptz not null  -- quando esses dados foram coletados de verdade (nunca "agora")
);

-- RLS ativado e SEM policies: o backend Python usa a secret key, que
-- sempre ignora RLS. Mesmo padrão de sql/ia_cache.sql / sql/research.sql.
alter table indicadores_fallback enable row level security;
