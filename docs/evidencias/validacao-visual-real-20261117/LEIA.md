# Validação visual real — RESEARCH / NOTÍCIAS / COMITÊ / RADAR (2026-11-17)

Missão de captura de evidência (Playwright real, Chromium, sem AppTest) —
nenhum arquivo de produção (`ui/*.py`, `data/*.py`, `jobs/*.py`, `app.py`,
`style.css`) foi alterado. Antes de capturar, cada área teve seu arquivo
de UI real comparado por `git log -1` contra a data da última captura já
salva em `docs/evidencias/` (regra "sem auditoria repetida" do
`CLAUDE.md`): só recapturamos o que de fato mudou desde então.

## RESEARCH (`ui/research_tab.py`, subaba Casas de Análise)

**Fresco.** `research_1440.png` / `research_1024.png`, via
`harness_research.py` (novo — não existia harness salvo pra RESEARCH
antes, só os screenshots soltos em
`docs/evidencias/research-area-20261023/`, sem o `.py`). Recapturado
porque `ui/research_tab.py` mudou em 2026-11-06 (commit `773f827`),
depois da última captura (2026-10-23). Chama `render_casas_analise`
direto, com `preparar_leitura`/`ultimas_coletas_formatadas`/
`obter_status_casas`/`cobertura_cruzada_casas`/
`_premissas_por_tickers_cacheado`/`obter_noticias` monkeypatchados com
dado mockado plausível (nunca dado real).

Achados: nenhum problema real. Pills de filtro (Casa/Tipo/Ticker/
Recomendação/Período), busca textual, cards de tese (badge de
disponibilidade, recomendação/preço-alvo, resumo gerado por IA) e o
expander fechado "COBERTURA E SAÚDE DAS CASAS" renderizam limpos, sem
sobreposição/corte, em 1440px e 1024px. Monoespaçado e paleta âmbar/preto
consistentes com o resto do app.

## NOTÍCIAS (`ui/news_tab.py`, subaba Empresas — feed editorial)

**Fresco.** `noticias_1440.png` / `noticias_1024.png`, via
`harness_news.py` (novo, adaptado de
`docs/evidencias/news-card-redesign-20261019/harness_cards.py` — aquele
só exercitava o componente de card isolado; este chama o PONTO DE
ENTRADA real, `render_news`, pro mesmo padrão de captura "landing" usado
nas outras 3 áreas). Recapturado porque `ui/news_tab.py` mudou em
2026-11-06 (commit `3e33101`), depois da última captura (2026-10-19).

Achado de harness (não é bug de produção): `render_news` é
`@st.fragment` e chama `_renderizar_feed_editorial` internamente, que
TAMBÉM é `@st.fragment` — em bare mode (sem sessão real do Streamlit),
uma função `@st.fragment` chamada "normal" não executa o corpo (mesmo
achado já documentado em `feedback_streamlit_fragment_bare_mode.md`).
Resolvido no harness substituindo a referência interna pela versão
`.__wrapped__` antes de chamar `render_news.__wrapped__`.

Achados de UI: nenhum problema real. Cards (selo/score, veículo, data,
tickers, resumo "gerado por IA", link "abrir") alinhados e sem
sobreposição em 1440px e 1024px; pills de Ticker/Selo responsivos.

## COMITÊ (`ui/coordenador_tab.py`, Visão Geral)

**Reaproveitado** de
`docs/evidencias/agente-d-redesign-estrutural-20261112/
visao_geral_1440_depois.png` e `visao_geral_1024_depois.png` →
`comite_1440.png` / `comite_1024.png`. Justificativa: `ui/
coordenador_tab.py` não mudou depois do commit que gerou essa captura
(`c16029b`, 2026-11-12 20:35) — é a mesma versão de código.

Achado (já documentado na missão original, não é regressão desta
validação): em 1024px, a coluna "RESUMO/ERRO" (tabela ÚLTIMAS EXECUÇÕES
AGENDADAS) e a tabela ANÁLISES SOB DEMANDA RECENTES truncam texto na
borda direita sem indicação de rolagem horizontal visível no
screenshot estático — mesmo padrão de degradação aceito em outras
tabelas do app (`.coord-tabela-wrap`), confirmado no LEIA.md original.
MENOR, nada novo encontrado.

## RADAR (`ui/radar_tab.py`, subaba Alertas)

**Reaproveitado** de
`docs/evidencias/agente-a-redesign-estrutural-20261112/
depois_alertas_1440.png` e `depois_alertas_1024.png` →
`radar_1440.png` / `radar_1024.png`. Justificativa: `ui/radar_tab.py`
teve sua última mudança no commit que gerou essa mesma captura
(`41ad09b`, 2026-11-13 02:16) — é a mesma versão de código. As demais
subabas de RADAR (Oportunidades, Carteiras Recomendadas, Acompanhamento)
também já têm captura corrente nas mesmas duas pastas de origem — não
duplicadas aqui pra não repetir auditoria já feita.

Achados: nenhum problema real. Faixa RESUMO, tabela de alertas e tabela
MONITORADOS AGORA alinhadas, sem sobreposição/corte em 1440px e 1024px.

## Resumo

| Área | Estado | Fresco/Reaproveitado |
|---|---|---|
| RESEARCH | nenhum problema real | fresco |
| NOTÍCIAS | nenhum problema real | fresco |
| COMITÊ | MENOR (truncamento já documentado, não é regressão) | reaproveitado |
| RADAR | nenhum problema real | reaproveitado |

Nenhum arquivo de produção foi tocado por esta missão — diff restrito a
`docs/evidencias/validacao-visual-real-20261117/`.
