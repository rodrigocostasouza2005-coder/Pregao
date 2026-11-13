-- PREGAO — historico de mudanca de data em eventos_resultados (missao
-- noturna 2026-11-12/13, frente CALENDARIO).
-- Rode isso uma vez em: Supabase > SQL Editor > New query.
--
-- ADITIVO, nunca destrutivo: so adiciona 1 coluna numa tabela ja
-- existente (ver sql/eventos.sql) - nenhuma linha e apagada/alterada,
-- nenhum dado de usuario e tocado. Antes desta coluna, quando uma
-- empresa adiava/corrigia a data de divulgacao (ver
-- data/eventos_coleta.py:_confirmado_precisa_reverificar), o
-- upsert em eventos_resultados SOBRESCREVIA a linha antiga em silencio -
-- a data anterior (e quando ela foi valida) se perdia pra sempre, sem
-- nenhum jeito de o usuario saber que a empresa mudou a data. Agora
-- data/eventos_coleta.py:salvar_evento_se_mais_confiavel guarda cada
-- valor anterior (data/status/fonte/verificado-em) aqui antes de
-- sobrescrever, so quando a DATA realmente mudou (nunca em upsert
-- idempotente/so-reverificacao sem mudanca real).

alter table eventos_resultados add column if not exists historico jsonb not null default '[]'::jsonb;
