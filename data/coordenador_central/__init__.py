# -*- coding: utf-8 -*-
"""COORDENADOR CENTRAL (Fase E, pedido do Rodrigo, 2026-10-31) - orquestra
as inteligências Python já existentes e dispersas no PREGÃO ("especialistas")
com registro padronizado, execução paralela/isolada, consolidação
determinística e persistência.

Pacote separado de jobs/coordenador.py (esse é só o AGENDADOR/scheduler via
GitHub Actions, continua existindo e fazendo exatamente o que já fazia - ver
docstring dele). Este pacote é o orquestrador SOB DEMANDA, chamado pela UI
(ui/coordenador_tab.py) e, no futuro, por qualquer outra parte do sistema.

Submódulos:
- registro.py: catálogo dos especialistas (funções já existentes, nenhuma
  reescrita) com contrato de entrada/saída padronizado.
- executor.py: execução isolada (timeout real) e paralela de especialistas.
- consolidacao.py: agregação determinística dos resultados em 7 seções
  (zero chamada de IA nova aqui).
- fluxos.py: casos de uso de alto nível (Fluxo A/B/C) chamados pela UI.
- persistencia.py: histórico de análises e métricas de especialistas no
  Supabase (sql/coordenador_central.sql), nunca lança exceção.

Nenhum destes módulos reescreve a lógica de negócio das inteligências
originais - sempre importa e reaproveita (data/research/comparador.py,
data/research/embeddings.py, data/market_researcher.py, data/news.py,
data/eventos.py, data/radar.py, data/earnings/reviewer.py,
data/x_radar/__init__.py)."""
