# RESEARCH — data da recomendação na watchlist (2026-10-18)

Capturas geradas com um harness local (Streamlit + Playwright) chamando
`ui.research_tab._painel_watchlist` real com **dados de exemplo** (não são
dados de produção: este ambiente não tem acesso ao Supabase).

- `depois_desktop.png` / `depois_mobile.png` — depois da correção
  (`fix/research-watchlist-data-snapshot-20261018`): a linha da recomendação
  agora mostra "· atualizado em dd/mm/aaaa" quando a data existe no snapshot
  persistido.

## O que foi corrigido

`_painel_watchlist` (RESEARCH → NA SUA WATCHLIST) mostra a recomendação mais
recente da Genial Analisa por ticker (ex.: "Genial: COMPRA · potencial
12,3% · preço-alvo R$ 48,50"), **sem nenhuma indicação de quando essa
recomendação foi capturada**. Em produção, a recomendação "ao vivo" da
Genial está sempre vazia (`tentar_coleta_automatica=False`, bloqueio WAF no
Streamlit Cloud — achado documentado na auditoria 360), então a tela
praticamente sempre usa o fallback de snapshot persistido
(`data/research/historico.py:ultimo_snapshot`).

Esse snapshot **tem** a data de captura (`capturado_em`, inclusive usada
para ORDENAR qual é o snapshot "mais recente"), mas o fallback em
`_painel_watchlist` descartava esse campo ao montar `recomendacao_ticker`
(`ui/research_tab.py`, antes da correção: dict só com
`ticker/recomendacao/preco_alvo/potencial_pct`). O único lugar que mostrava
qualquer data era `_expander_historico_recomendacao` — mas esse expander só
aparece quando há **2 ou mais** snapshots distintos daquele ticker
(`len(historico) < 2: return`), porque só existe "evolução" para mostrar
nesse caso. Para o caso mais comum — um ticker com só 1 snapshot já
coletado — não havia absolutamente nenhuma data visível em lugar nenhum da
tela: o usuário via uma recomendação "COMPRA, potencial +12,3%" sem jeito
nenhum de saber se isso é de hoje ou de 3 meses atrás.

## Correção

1. `capturado_em` passou a ser copiado do snapshot pro dict
   `recomendacao_ticker` (`ui/research_tab.py`).
2. A linha da recomendação passou a mostrar "· atualizado em dd/mm/aaaa"
   (reaproveitando `_fmt_capturado_em`, já usado no expander de histórico)
   quando essa data existe.
3. Recomendação "ao vivo" (sem `capturado_em` — a própria fonte não expõe
   essa data nesse caso) não mostra nada a mais — nunca inventa uma data
   que a fonte não oferece.

## Testes

- Teste de reprodução (`tests/test_research_news_context.py::test_12c_*`)
  escrito ANTES da correção, confirmado que falhava no código antigo, passa
  depois.
- Teste existente (`test_13_*`) estendido para confirmar explicitamente que
  o caminho "ao vivo" nunca inventa uma data.
- Suíte completa: 888 passed.

Validado com Playwright (harness isolado, sem login): texto aparece de
verdade nos 2 breakpoints (1280px/390px), sem erro de console, sem
sobreposição/corte.
