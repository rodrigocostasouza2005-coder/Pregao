# CHANGELOG — PREGÃO

Entradas curtas por commit, em português simples: o que mudou e por quê.
Mais recente primeiro.

## 2026-10-08 (rotina autônoma, parte 1/4 — confiabilidade de testes)

Sessão autônoma agendada (ciclo de 4 partes). Retomou exatamente o
ponto deixado pela sessão anterior: `tests/test_eventos.py` tinha 10
falhas confirmadas como pré-existentes (não regressão) ao rodar via
`pytest`, com a causa raiz ainda não investigada.

- **`tests/test_eventos.py` quebrava sob `pytest` (10 testes) — causa
  raiz confirmada e corrigida**: o arquivo foi escrito pra rodar via
  `python tests/test_eventos.py`, com um mock global de
  `obter_cnpj` aplicado só dentro do bloco `if __name__ == "__main__"`.
  Esse mock ficou necessário desde 2026-10-08 (correção anterior em
  `data/eventos.py:periodo_pendente`, que passou a checar
  `obter_cnpj(ticker)` antes de calcular qualquer prazo). Rodando via
  `pytest` (que nunca executa o bloco `__main__`), todo teste chamava o
  `obter_cnpj` REAL — sem rede/dados locais neste runner, sempre
  devolve `None` — fazendo `periodo_pendente` devolver `None` sempre e
  `calcular_proximo_resultado` devolver `None` pra qualquer ticker,
  quebrando 10 testes com `TypeError: 'NoneType' object is not
  subscriptable`. Corrigido com uma fixture `pytest.fixture(autouse=True)`
  que replica o mesmo default do runner `__main__` (CNPJ fake mapeado
  por padrão); o teste que cobre o caso real "ticker sem CNPJ" segue
  funcionando porque o `with patch.object(...)` local dele prevalece
  enquanto ativo. Nenhuma mudança em código de produção — o bug era só
  do arnês de teste, não de `data/eventos.py`. Suite completa:
  233/243 → **249/249** (os 6 testes "extras" vieram só do recount do
  pytest depois do fix, não de testes novos).
- **Curva pré (ETTJ, MACRO) — investigação da legenda sobreposta/cortada
  (item do BACKLOG)**: reproduzida com Playwright/Chromium (dados
  sintéticos, já que a rede bloqueia a ANBIMA aqui) nos 3 breakpoints
  (390/768/1280px), usando o layout real de
  `ui/macro_tab.py:_painel_curva_pre`. **Não reproduziu** — o Plotly
  encolhe a área do gráfico pra caber a legenda (que quebra em 2-3
  linhas em telas estreitas) dentro da altura declarada, sem clipping
  visível em nenhum breakpoint. Não alterado o código (nada a
  corrigir sem reprodução); BACKLOG.md atualizado com o resultado da
  investigação e uma hipótese não testável aqui (painel
  redimensionado manualmente abaixo do necessário no workspace
  modular, que exige sessão autenticada real).
- **Nota de ambiente**: mesma limitação de sessões anteriores — rede
  deste sandbox bloqueia Yahoo Finance/B3/ANBIMA/RSS, então toda
  validação visual usou dados sintéticos plausíveis via harness
  isolado (Playwright + Chromium pré-instalados, plotly.js embutido
  inline pra não depender de CDN). Suite de testes/`compileall`/
  `pyflakes` rodados em Python 3.12 (venv dedicado, `/tmp/venv312` —
  o projeto usa sintaxe de f-string que exige 3.12+, sandbox vem com
  3.11 por padrão).

## 2026-10-08 (continuação — UX/hierarquia/mobile/performance percebida)

Sessão autônoma agendada, continuação da sessão anterior (mesmo dia -
calendário/botão de login mobile já resolvidos, não repetidos aqui).
Foco: revisão crítica de UX nas 9 telas + responsividade real
(Playwright 390/768/1280px) + feedback de carregamento.

- **Feedback de carregamento ausente no app inteiro** (`data/cvm.py`,
  `data/news.py`, `data/macro.py`, `data/research/genial.py`): todo
  `@st.cache_data` do projeto usava `show_spinner=False` sem exceção -
  numa consulta fria (CVM, notícias, research, séries macro, todas com
  TTL de 20min-24h e fetch de rede real), a tela ficava literalmente
  parada, sem spinner nem texto, até o dado chegar (achado real: zero
  ocorrências de `st.spinner` nas camadas de dado do projeto todo).
  Adicionado texto de spinner (`show_spinner="buscando notícias…"`,
  etc.) exatamente nas funções que: (a) fazem fetch de rede de verdade
  (não só leitura de Supabase já cacheada) e (b) NÃO vivem dentro de um
  `st.fragment(run_every=...)` de auto-atualização (só 4 lugares no
  app inteiro - ticker tape, watchlist do header, comparativo da
  watchlist em EQUITY, painel PREÇOS - nenhum deles chama essas
  funções), pra nunca piscar o spinner a cada refresh periódico.
  Conferido um a um: funções já cobertas por um `st.spinner(...)`
  manual no ponto de chamada (resumo de documento CVM, resumo de
  notícia, calendário, coleta de relatórios pendente) foram
  deliberadamente DEIXADAS de fora pra não duplicar/aninhar spinner com
  texto diferente no mesmo carregamento.
- **MERCADO/MACRO/VISÃO GERAL: botão "↺ RESTAURAR LAYOUT" cortava em
  QUALQUER tela abaixo de ~800px de conteúdo, tablet incluído, não só
  celular** (`ui/workspace.py:renderizar_workspace`) — bug real
  confirmado com Playwright (390/768/1280px, harness com dados
  mockados já que a rede deste sandbox bloqueia Yahoo/B3/RSS - ver nota
  de ambiente abaixo): o botão vivia num `st.columns([5, 1.3])` ao lado
  da dica de arrastar — uma FRAÇÃO da largura, não um valor fixo, então
  "RESTAURAR LAYOUT" (19 caracteres) nunca cabia nos ~20% de coluna
  reservados a ele abaixo de ~800px, virando "RESTAURAR ..." cortado e
  inútil. Removida a divisão em colunas: dica em cima (some de todo
  abaixo de 640px — nessa largura o workspace já cai pro fallback
  empilhado, arrastar/redimensionar não existe mais, a dica ficaria
  descrevendo uma interação indisponível), botão embaixo, largura
  total sempre — não depende de nenhum breakpoint específico, funciona
  igual em qualquer largura. Afeta as 3 abas que usam o workspace
  modular (MERCADO, MACRO, VISÃO GERAL).
- **MERCADO (painel DESEMPENHO SETORIAL): rótulo de % cortava na borda
  do gráfico em telas estreitas + nome de setor comprido cortava na
  borda ESQUERDA em tablet/desktop** (`ui/mercado_tab.py:_painel_setorial`)
  — 2 bugs reais confirmados com Playwright (mesmo harness mockado):
  (1) o texto "+X,XX%" de cada barra (`textposition="outside"`) não
  tinha folga reservada no eixo X pra caber depois da última barra em
  containers estreitos — corrigido com uma folga fixa de 55% sobre o
  maior valor absoluto do dia (pra ambos os lados, setor pode estar em
  alta OU baixa) + `cliponaxis=False` como rede de segurança; (2) nomes
  de setor mais longos ("Petróleo e Gás", "Materiais Básicos")
  cortavam na borda esquerda do painel mesmo em 768/1280px porque o
  `margin.l` fixo do layout nunca foi pensado pra reservar espaço pro
  rótulo de categoria — corrigido com `automargin=True` no eixo Y
  (Plotly calcula o espaço de verdade a partir do texto mais largo).
  Esse painel é reaproveitado por VISÃO GERAL também (mesma função,
  `ui/visao_geral.py:REGISTRO_PAINEIS`) — o fix vale pras duas abas.
  Limitação conhecida: a 390px (celular), "Petróleo e Gás" ainda perde
  1 caractere ("'etróleo e Gás") — a largura disponível ali (~300px,
  descontado o espaço do próprio rótulo) é estreita demais pro rótulo
  mais longo do conjunto caber inteiro ao lado de uma barra+texto
  legíveis; não persegui esse último caractere pra não gastar o tempo
  da sessão num detalhe cosmético de 1 painel (dado continua
  identificável - "etróleo e Gás" + a barra colorida ao lado).
- **Nota de ambiente**: rede deste sandbox bloqueia Yahoo Finance/B3/
  RSS/sites de research (confirmado: toda tentativa de fetch real
  nessas fontes retornou indisponível) — validação visual real das
  telas com DADO DE VERDADE não foi possível aqui (mesma limitação já
  documentada em sessões anteriores, ver nota de 2026-09/10 em
  PROGRESSO.md sobre harness Playwright com dados mockados). Contornado
  com 2 harnesses Playwright isolados (fora do app.py real, sem login):
  um importando os `render_*` de verdade contra a rede real (confirma
  ausência de overflow horizontal e exercita os estados vazio/erro,
  que acabaram sendo o que a rede bloqueada mostrou de qualquer jeito);
  outro com `data.mercado`/`data.ibovespa` substituídos por dados
  sintéticos plausíveis (só pra MERCADO, onde estavam os 2 bugs reais
  acima) pra validar tabelas/gráfico/treemap com conteúdo de verdade
  nos 3 breakpoints. Mesmo venv Python 3.12 (`/tmp/venv312`) das
  sessões anteriores, por causa da mesma sintaxe de f-string aninhada
  que exige 3.12+.
- **Testes**: suite completa (17 arquivos, 243 testes) rodada em Python
  3.12 - 233 passam, 10 falham em `tests/test_eventos.py`
  (`calcular_proximo_resultado` retornando `None` em vez de dict em
  alguns cenários de leitura de evento persistido) - confirmado que as
  10 falhas já existiam ANTES desta sessão (mesmo resultado rodando os
  testes no HEAD limpo, `ab4ca56`, sem nenhuma mudança minha) - não são
  regressão deste ciclo, ficam registradas aqui pro próximo ciclo
  investigar a causa raiz. `compileall` limpo em todos os arquivos
  tocados.
- Não fiz (falta de tempo nesta janela de ~1h, ficam pro próximo
  ciclo): revisão visual completa de NEWS/CVM/RESEARCH/TOP MERCADO/
  CALENDÁRIO/EQUITY nos 3 breakpoints com dados mockados (só MERCADO
  recebeu harness mockado dedicado nesta sessão - as outras abas só
  foram validadas contra a rede real bloqueada, que mostrou os estados
  vazio/erro mas não o layout com conteúdo real); auditoria de
  hierarquia visual (itens 1-9 do pedido original - VISÃO GERAL como
  primeira impressão, EQUITY como experiência de análise, NEWS como
  leitura editorial, etc.) não foi abordada por falta de tempo depois
  do trabalho de responsividade/loading state, que achei ter maior
  impacto imediato (bugs reais confirmados, cross-tela) do que
  reorganização de hierarquia sem bug concreto por trás.

## 2026-10-08 (auditoria de confiabilidade/UX/responsividade — rotina autônoma)

Sessão autônoma agendada, focada na suspeita de que o CALENDÁRIO
mostrava cobertura baixa (2-3 empresas) + responsividade mobile real.

- **CALENDÁRIO: causa real da "cobertura baixa" identificada — não é
  bug de coleta/parsing/dedup** (`ui/calendario_tab.py:_painel_agenda`):
  auditei o pipeline completo (fonte CVM → `_mapa_ticker_cnpj` → IPE →
  `periodo_pendente` → `calcular_calendario` → snapshot → UI). A fonte
  cobre normalmente as ~84 empresas de `config.IBOVESPA_SETORES` — o
  que o usuário via era o filtro padrão da UI (MINHA WATCHLIST) somado
  à watchlist padrão de quem nunca editou (`config.TICKERS_PADRAO`, só
  3 tickers: PETR4/VALE3/ITUB4). Não mudei filtro/fonte/dado algum (só
  mascararia o sintoma ou inflaria contagem artificialmente, ambos
  proibidos) — adicionei uma legenda de 1 linha no painel, visível só
  quando o filtro é MINHA WATCHLIST, mostrando o tamanho real da
  watchlist e quantas empresas o TODOS cobre. Testes novos (22-23 em
  `tests/test_calendario_ui.py`) travam o texto exato e que ela some
  fora desse filtro.
- **Mobile: botão ENTRAR COM GOOGLE cortava/vazava em telas estreitas**
  (`auth.py:tela_apresentacao`) — bug real confirmado com Playwright
  (390/768/1280px, Streamlit rodando em Python 3.12, já que este
  sandbox tem 3.11 por padrão — ver nota de ambiente abaixo): o botão
  vivia dentro de `st.columns([1,1,1])` pra ficar centralizado no
  desktop, o que o espremia em 1/3 da largura do painel (~100px a
  390px) — "ENTRAR COM GOOGLE" não cabia. Removida a coluna (a própria
  div do botão já tinha `max-width:320px`); a centralização real
  (achado 2: `justify-content:center` no wrapper nunca fazia efeito,
  porque o filho de fato é `div[data-testid="stButton"]`, que já
  preenche 100% da linha sozinho) passou pro `margin:0 auto !important`
  no próprio botão. Validado visualmente nos 3 breakpoints (screenshots
  antes/depois, botão centralizado e texto completo nos 3).
- **Pills sem quebra de linha em telas estreitas, fora de CALENDÁRIO/
  RESEARCH/NEWS/paineis.py** (`style.css`): a correção de flex-wrap das
  pills (`st.pills`/`segmented_control`) já existia, mas duplicada
  identicamente em 4 arquivos — nunca chegou em MACRO/MERCADO/TOP
  MERCADO/VISÃO GERAL, que também usam pills e tinham o mesmo bug.
  Centralizada em `style.css` (infra compartilhada, pedido explícito
  de preferir isso a regra por aba); removidas as 4 cópias duplicadas
  (`ui/calendario_tab.py`, `ui/research_tab.py`, `ui/paineis.py`,
  `ui/news_tab.py` — a última ficou sem `_injetar_css`/`_CSS_RESEARCH`
  nenhum, já que isso era todo o conteúdo).
- **Nota de ambiente**: este sandbox de auditoria tem Python 3.11.17
  por padrão, mas o projeto usa sintaxe de f-string com aspas aninhadas
  (`app.py`, `ui/mercado_tab.py`) que exige Python 3.12+ (PEP 701) —
  `compileall`/testes desses 2 arquivos falham aqui por isso, não por
  regressão (confirmado compilando com `python3.12` explícito, sem
  erro). Validação real (testes, `compileall`, Playwright) rodou num
  venv Python 3.12 criado só pra esta sessão.
- **Testes**: suite completa (17 arquivos) verde em Python 3.12,
  incluindo os 2 novos de `test_calendario_ui.py`; `test_mercado.py`
  também passa em 3.12 (falha só em 3.11 pelo motivo acima).
  `compileall`/pyflakes limpos nos arquivos tocados.
- Não fiz (falta de tempo/risco maior que o ganho, ficam pro próximo
  ciclo): revisão visual completa das 9 abas (Prioridade 2 do pedido —
  só o achado do CALENDÁRIO foi tratado); validação visual real das
  abas autenticadas (EQUITY/MACRO/MERCADO/...) — exigem login Google
  real, não automatizável neste sandbox; só a tela de login/apresentação
  (pública, sem auth) foi validada ao vivo no navegador.

## 2026-10-08 (chore: harden post-v1 terminal — FASE 8/9)

Continuação controlada da melhoria contínua, partindo do estado
validado da rodada anterior (NÃO repete a auditoria de lá). Fecha os
itens que tinham ficado em BACKLOG.md por falta de tempo/escopo:

- **N+1 de cotação corrigido na sidebar e no comparativo da EQUITY**
  (`app.py:_fragmento_watchlist`, `_painel_comparativo_watchlist`):
  os 2 últimos pontos que ainda chamavam `data/prices.py:obter_cotacao`
  1x por ticker num loop agora usam `data/mercado.py:obter_cotacoes_lote`
  (já existente, já testado) — 1 única requisição em lote. No
  comparativo, `obter_indicadores` (P/L, P/VP, DY) **continua** por
  ticker de propósito: vem de `yf.Ticker().info`, que o yfinance não
  oferece em lote — já cacheado 12h por ticker, custo real de rede raro.
- **Coluna `modelo` do cache global de IA deixa de ficar sempre vazia**
  (`data/ia_cache.py:resumos_ia_cache`, sem alterar `ia_cache.py` em
  si): `data/research/resumir.py:resumir_com_groq` já calculava
  internamente qual dos 2 modelos (principal/fallback) de fato gerou o
  resumo (`usou_fallback`) mas descartava essa informação (`_`) antes
  de chegar no dict salvo — agora propaga o modelo REAL (nunca
  presumido; `None` quando genuinamente não disponível, nunca um
  "chute"). `data/news.py:_gerar_resumo_grupo` (sem fallback de modelo,
  sem ambiguidade) também passa a reportar o modelo usado.
- **Testes de integração do motor de dedup de NEWS**
  (`tests/test_news_dedup.py`, novo): `_agrupar`/`_mesmo_grupo` sem
  nenhuma cobertura antes — cobre notícias equivalentes fundindo por
  texto/entidade/título idêntico, notícias distintas (mesma empresa,
  empresas diferentes) ficando separadas, cadeia de títulos mudando
  gradualmente sem fragmentar, e propagação de `relevante`/`ao_vivo`
  pro grupo. Documenta também (teste explícito, não um "bug" alterado)
  uma característica real da heurística: o nome da própria empresa
  sozinho (capitalizado, 5+ letras) já conta como "entidade em comum"
  dentro da janela de 24h.
- **Testes de `_bloco_contexto_research`** (`tests/test_news_contexto_research.py`,
  novo): integração NEWS→RESEARCH dentro do dialog da notícia (FASE 3)
  sem nenhum teste direto antes — cobre contexto correto, ausência de
  contexto, múltiplos tickers com limite, fallback quando nenhum ticker
  da notícia está na watchlist, fonte indisponível, e que nunca fabrica
  potencial/preço-alvo ausente.
- **Código morto removido**: `config.obter_modelo_groq()` (wrapper fino
  de 1 linha, ficou sem nenhum chamador depois da correção da coluna
  `modelo` acima).
- Investigado e **deliberadamente não alterado** (ver BACKLOG.md,
  "Auditoria 2026-10-08 (FASE 8)", com prioridade/impacto/esforço):
  link CVM→CALENDÁRIO (bloqueado por restrição real de ordenação do
  nav do Streamlit, não é "pequeno"), `_layout_grafico_escuro`
  duplicado (sem bug ativo), chave de `session_state` compartilhada
  entre MERCADO/VISÃO GERAL (confirmada empiricamente, mas é UX — nunca
  mostra dado errado — decisão de produto), `_cache_eventos()` sem
  poda (auditado, crescimento desprezível pra terminal pessoal, seguro).

Validação: suíte completa (17 arquivos, 3 novos) + `compileall` +
`pyflakes` (repo inteiro) limpos. Sem acesso a browser real neste
ambiente — mesma limitação já documentada; os 2 pontos de N+1
corrigidos vivem em closures de `app.py` que dependem de login real
(`auth.py`, "impossível de automatizar", mesma decisão de fases
anteriores) e por isso não têm harness `AppTest` dedicado — a correção
é a mesma função já testada (`obter_cotacoes_lote`, `tests/test_mercado.py`
da rodada anterior) em 2 pontos de chamada adicionais, confirmados por
revisão de código (compatibilidade de campos) + `compileall`/`pyflakes`.

## 2026-10-08 (fix/feat/perf/test: ciclo de melhoria contínua pós-FASE 3)

Auditoria completa (leitura real do código, não só do relatório da fase
anterior) em NEWS/RESEARCH/MERCADO/EQUITY/VISÃO GERAL/MACRO/CVM/
CALENDÁRIO, seguida de correção autônoma dos achados de maior impacto.
Detalhe completo das decisões em PROGRESSO.md; itens revistos e
deixados pra depois em BACKLOG.md ("Auditoria 2026-10-08").

- **CALENDÁRIO não fabrica mais PRAZO_CVM pra ticker sem CNPJ mapeado**
  (`data/eventos.py:periodo_pendente`): BDR estrangeiro (MELI34 etc,
  nunca protocola ITR/DFP na CVM nesse regime) parava de ser
  distinguido de uma empresa CVM-regulada que só ainda não tem
  documento no período — agora checa `obter_cnpj(ticker)` antes de
  calcular prazo, mesma limitação já documentada pra aba CVM.
- **"nan" literal corrigido** em `data/cvm.py:obter_documentos_cvm`
  (`data_referencia` vindo do CSV da CVM como `float('nan')`, campo
  vazio, aparecia como "(ref. nan)" no CALENDÁRIO → HISTÓRICO —
  `bool(nan)` é `True` em Python, escapava do filtro antigo).
- **Fuso horário do CALENDÁRIO corrigido pra America/Sao_Paulo**
  (`data/eventos.py`, `ui/calendario_tab.py`): `date.today()` usava o
  fuso do servidor (UTC no Streamlit Cloud) — perto da meia-noite UTC
  (~21h BRT) considerava um trimestre encerrado ~3h antes da hora real
  e destacava a célula de HOJE errada por até 3h todo dia.
- **CVM para de reescrever a watchlist inteira no Supabase a cada
  clique**: `obter_documentos_cvm`/`obter_documentos_watchlist`
  (`data/cvm.py`) agora cacheados (`st.cache_data`, mesmo TTL de 6h da
  fonte) — a aba roda dentro de `@st.fragment` desde 2026-10-01, e cada
  clique em filtro/pill/busca reexecutava o upsert inteiro mesmo sem
  documento novo.
- **CALENDÁRIO ganha `@st.fragment`** (`ui/calendario_tab.py`):
  navegação de mês/seleção de dia/pills de CONTEXTO disparavam rerun
  da página inteira a cada clique — mesmo padrão já corrigido em
  CVM/RESEARCH/TOP MERCADO/NEWS.
- **Variação do CDI na VISÃO GERAL deixa de ser fabricada**
  (`ui/visao_geral.py:_painel_mercado_agora`): o card "DI (CDI anual.)"
  mostrava sempre "+0,00%" fixo (hardcoded, nunca calculado) — agora
  calcula a variação real (p.p.) entre as 2 últimas leituras do CDI
  anualizado; sem leitura suficiente mostra "—", nunca mais um número
  inventado.
- **N+1 de cotação corrigido no header (ticker tape) e na VISÃO GERAL**
  (`data/mercado.py:obter_cotacoes_lote`, nova função, reaproveita
  `_baixar_lote`/`_linha_papel` já usados por `obter_panorama_ibovespa`):
  `app.py:_ticker_tape` e `ui/visao_geral.py:_painel_watchlist_compacta`
  faziam 1 `yf.Ticker().fast_info` POR TICKER da watchlist, sequencial —
  agora é 1 única requisição em lote. Sidebar/EQUITY comparativo ainda
  não migrados (ver BACKLOG.md — também buscam indicadores por ticker).
- **Rótulo "atraso de ~15 min" da EQUITY passa a respeitar pregão
  fechado** (`app.py`): fora do horário de pregão (fim de semana/
  feriado/após 17h) misturava "hora em que a página renderizou" com
  "hora real da cotação" — agora mostra "cotação de fechamento (mercado
  fechado)" usando `_pregao_esta_aberto` (já existia, só não era
  reaproveitada aqui).
- **Morning Call/lives da Genial: `data` deixa de vir em UTC crua**
  (`data/research/genial_lives.py`): vídeo publicado perto das 21h+ BRT
  (típico do "Fechamento de Mercado") caía no dia UTC seguinte —
  `publicado_em` (hora completa) continua em UTC, mas `data` (usada por
  retenção/filtro/selo NOVO do Research Radar) agora vem da conversão
  pro fuso de Brasília. Coleta também isolada por item (1 vídeo
  malformado não derruba os demais, mesmo padrão de `xp.py`).
- **NEWS ganha `@st.fragment` no ponto de entrada inteiro**
  (`ui/news_tab.py:render_news`): só o feed interno era fragment — os
  pills de ticker/selo e o botão VER MAIS, fora dele, continuavam
  disparando rerun da página inteira (e reconsultando Supabase) a cada
  clique. Mesmo padrão já usado em RESEARCH.
- **Código de contrato futuro (WDOV26/WINV26 etc) para de ser marcado
  como ticker** nas tags de notícia do TOP MERCADO (`data/news.py:
  _tickers_no_titulo`): filtra pelo sufixo numérico REAL de ticker B3
  (ação/unit/BDR), não só "4 letras + 1-2 dígitos".
- **Histórico de recomendação exposto na UI** (`ui/research_tab.py`):
  `data/research/historico.py:historico_ticker` existia só na camada de
  dado desde a fase RESEARCH original — agora aparece num expander
  fechado por padrão na watchlist, quando há 2+ snapshots.
- **Bloco "CONTEXTO RECENTE · NEWS" deixa de repetir por relatório**
  (`ui/research_tab.py:_painel_watchlist`): ticker com 3-4 relatórios
  com resumo já cacheado repetia o mesmo bloco de notícias 3-4 vezes —
  agora aparece 1x por ticker, depois do loop de relatórios.
- **"—" de potencial ausente deixa de aparecer verde**
  (`ui/research_tab.py`): `(potencial or 0) >= 0` classificava a
  ausência de dado como "alta" (span verde); agora só classifica
  alta/baixa quando há potencial real.
- **HTML não escapado corrigido** em 2 pontos de `ui/research_tab.py`
  (recomendação/status vindos da Genial) — mesmo tratamento que
  `ui/news_tab.py` já aplicava pro mesmo tipo de dado.
- **Testes novos** (nenhum arquivo quebrado — suíte inteira + compileall
  seguem verdes): `tests/test_cvm.py` (zero cobertura antes),
  `tests/test_mercado.py` (zero cobertura antes — inclui regressão do
  bug "+NaN%" do treemap já documentado), `tests/test_news_tickers.py`,
  `tests/test_news_relevancia.py` (motor de relevância/dedup/score de
  `data/news.py`, zero cobertura direta antes), + extensões em
  `tests/test_eventos.py`, `tests/test_research_fase3.py`,
  `tests/test_research_news_context.py`. Validado também via harness
  AppTest (scratchpad, fora do repo) nas 6 telas tocadas — sem exceção,
  sem acesso a browser real neste ambiente (mesma limitação documentada
  em fases anteriores).
- **Docs**: nova seção CALENDÁRIO em MANUAL.md (não existia desde que a
  aba foi criada); docstring desatualizado de `ui/workspace.py`
  corrigido (dizia que VISÃO GERAL ainda não tinha migrado pro
  workspace modular — já tinha, desde a ETAPA 5).

## 2026-10-08 (feat: FASE 3 — feed editorial NEWS + integração RESEARCH)

- **NOTÍCIAS vira um feed editorial** (`ui/news_tab.py`): cada item vira
  um card com foto (quando disponível), título, veículo/hora/ticker e
  um teaser de 2-4 linhas do resumo — tudo isso **só quando já estiver
  cacheado por algum uso anterior** (leitura em lote,
  `data/ia_cache.py:obter_varios` + `data/news.py:obter_resumos_prontos`
  — 1 única query pra tela inteira, nunca 1 chamada de rede/IA por
  card). Item sem imagem cacheada mostra um fallback discreto (iniciais
  do veículo), nunca um ícone de foto quebrada. O estilo "wire" denso
  original (`_linha_noticia`/`_renderizar_lista`) continua **intocado**
  — usado só por TOP MERCADO e pelo bloco compacto da aba EQUITY.
- **Foto da matéria sem nenhuma requisição de rede extra**: a imagem
  (meta `og:image`) é extraída do MESMO download HTML já usado pra
  gerar o resumo (`trafilatura.extract(..., with_metadata=True)`) — zero
  fonte nova, zero custo extra. Fica cacheada junto do resumo no Supabase
  (`resultado.imagem`, mesma tabela `resumos_ia_cache`).
- **Morning Call intercalado cronologicamente no feed**, não mais numa
  seção isolada: itens "LIVE" da Genial (Morning Call, Resumo da Manhã,
  Fechamento de Mercado etc — já coletados pelo RESEARCH, ver
  `data/research/genial_lives.py`) ganham um card próprio
  (`_cartao_live`), identificado por programa+casa, posicionado por
  horário real entre as notícias. Nova coluna `publicado_em` (timestamp
  completo) em `research_itens` — nullable, preenchida só pelas lives;
  sem ela (banco ainda não migrado), o item aparece sem hora exibida
  (nunca inventada) e `salvar_itens` cai pro upsert antigo sem quebrar a
  coleta de nenhuma outra casa. **Ação necessária**: rodar
  `sql/research.sql` atualizado no Supabase (idempotente).
- **Resumo do Morning Call reescrito** (`data/research/resumir.py`,
  foco `MORNING_CALL`, mesmo sistema de IA/cache de sempre — nenhum
  pipeline novo): troca o resumo genérico por estrutura real **O QUE
  IMPORTA HOJE** (Brasil/Exterior/Juros/Câmbio/Commodities/Ações, só os
  temas que o episódio de fato cobriu) + **DESTAQUES** (tickers citados
  pelo nome), reforçando a separação FATO vs VISÃO DA CASA/ANALISTA vs
  LEITURA e proibindo explicitamente inventar tese/impacto/consenso/
  preço-alvo/recomendação. Cai pro formato narrativo genérico quando o
  episódio não tem conteúdo real pros blocos (nunca força template vazio).
- **Integração NEWS↔RESEARCH no dialog da notícia**: quando um ticker do
  item já tem recomendação/preço-alvo coletado da Genial, aparece um
  bloco compacto "Research" dentro do card de detalhe — mesma função
  cacheada que a aba RESEARCH já usa (`obter_recomendacoes`), zero fonte
  nova, zero chamada de IA, nunca N+1 (só no dialog já aberto).
- **Testes** (`tests/test_news_fase3.py` novo — 26 checks; +9 em
  `tests/test_ia_cache.py`; `tests/test_research_fase3.py` novo — 17
  checks): extração de imagem do mesmo download (sucesso, sem og:image,
  JSON malformado, falha de fetch, link não resolvido), `obter_varios`/
  `obter_resumos_prontos` em lote (1 única query, nunca N+1), merge
  cronológico NOTÍCIA+LIVE (pego um bug real de ordenação por string
  entre offsets de fuso diferentes — corrigido comparando datetime de
  verdade), hora de exibição honesta (nunca inventa HH:MM sem
  `publicado_em`), teasers (news e live), `publicado_em` aditivo/
  gracioso no upsert (incluindo coluna ausente no banco), prompt do
  Morning Call. `compileall` do projeto limpo. Validação de nível
  Streamlit via harness `AppTest` isolado (scratchpad, fora do repo,
  mesmo padrão de fases anteriores — nunca toca `auth.py`/login real):
  feed completo (foto ok, foto ausente, Morning Call intercalado,
  Morning Call sem resumo), clique abrindo o dialog (resumo + contexto
  RESEARCH), falha total de fontes, watchlist vazia — todos sem exceção;
  + harness separado confirmando TOP MERCADO e o bloco compacto da
  EQUITY (estilo wire, intocado) continuam funcionando, inclusive o
  dialog com a seção nova de contexto RESEARCH.
- **Limitação real**: validação visual (como o card realmente fica na
  tela — cor, espaçamento, densidade) não foi feita num navegador de
  verdade neste ambiente (sandbox de nuvem sem Playwright/Chromium
  configurado pro app completo) — só os harnesses `AppTest` acima
  (corretude de render/estado do Streamlit, não aparência). Pendência
  real: Rodrigo confirmar visualmente em `pregao.streamlit.app`.
- Arquivos: `ui/news_tab.py`, `data/news.py`, `data/ia_cache.py`,
  `data/research/resumir.py`, `data/research/genial_lives.py`,
  `data/research/store.py`, `sql/research.sql` + 3 arquivos de teste
  novos/estendidos. Nenhuma mudança em CALENDÁRIO/CVM/MACRO/MERCADO/
  preços/Supabase (arquitetura)/sistema de cache existente (só reuso).

## 2026-10-02 (feat: CALENDÁRIO - Hub do evento)

- Detalhe de um evento vira um hub compacto: RESEARCH, NEWS, CVM e
  HISTÓRICO (resultados já entregues pelo ticker), nessa ordem. Seção
  some quando vazia. Todo link abre a fonte original em nova aba.
- `obter_documentos_cvm` agora é chamado 1x por `_detalhe_evento` e
  reaproveitado por CVM e HISTÓRICO (evita N+1). Zero fonte nova, zero
  chamada de IA, `data/eventos.py` intocado.
- +17 testes novos (`tests/test_calendario_ui.py`, 29 no total).

## 2026-10-02 (fix: CALENDÁRIO V3 - separa PRÓXIMOS RESULTADOS de PRAZOS CVM)

- PRAZO CVM ≠ data de divulgação. A UI agora separa visualmente em duas
  listas: "PRÓXIMOS RESULTADOS" (só CONFIRMADO/ESTIMADO, "Nenhuma data
  de divulgação confirmada." quando vazio) e "PRAZOS CVM" (ticker, data,
  período, status). Painel renomeado de "PRÓXIMOS RESULTADOS DA
  WATCHLIST" pra "RESULTADOS DA WATCHLIST".
- Detalhe de um evento PRAZO CVM agora mostra aviso explícito: "Prazo
  regulatório para entrega do documento. Não representa necessariamente
  a data de divulgação do resultado."
- Painel principal renomeado de "CALENDÁRIO DE RESULTADOS" pra
  "CALENDÁRIO"; mensagem de período vazio ajustada pra "Nenhum evento
  no período."
- Nenhuma mudança em `data/eventos.py` (lógica/fonte dos eventos
  intocada) - só semântica da UI. 12 testes novos
  (`tests/test_calendario_ui.py`).

## 2026-10-01 (feat: CALENDÁRIO V2 - prioridade/dedup/cache resiliente)

- **Investigação real**: dados ao vivo da CVM confirmam que a categoria
  "Calendário de Eventos Corporativos" não tem a data do evento em
  nenhum campo estruturado (só data de protocolo) - a data real só
  existe dentro do PDF, exatamente o "texto ambíguo" que não deve virar
  CONFIRMADO. Sem fonte oficial segura identificada, o pipeline real
  continua só com PRAZO_CVM - decisão deliberada, documentada.
- Nova camada, testada com dados sintéticos (pronta pra quando uma fonte
  real existir): `mesclar_eventos` (CONFIRMADO > ESTIMADO > PRAZO_CVM
  pro mesmo ticker+período, nunca duplicado, fonte perdedora nunca
  escondida) e `aplicar_cache_resiliente` (nunca regride um
  CONFIRMADO/ESTIMADO conhecido de volta pra PRAZO_CVM só porque a
  fonte falhou numa consulta pontual).
- Watchlist agora ordena por confiabilidade, não só por data. Detalhe
  do evento mostra fonte como link e aviso quando o dado pode estar
  desatualizado.
- +12 testes novos (33 no total em `tests/test_eventos.py`).

## 2026-10-01 (feat: nova aba CALENDÁRIO de resultados corporativos)

- Nova aba CALENDÁRIO (v1): agenda de resultados (ITR/DFP) agrupada por
  data, com destaque "PRÓXIMOS RESULTADOS DA WATCHLIST" e filtros
  [MINHA WATCHLIST/TODOS/SETOR] × [SEMANA/MÊS].
- Única fonte de data real disponível hoje: prazo regulatório da CVM
  (Instrução 480/2009 - ITR 45 dias, DFP ~3 meses) - todo evento vem
  como status PRAZO_CVM; CONFIRMADO/ESTIMADO já estão na estrutura,
  prontos pra quando houver fonte confiável. Cruza com documentos CVM
  já publicados pra não mostrar como pendente um trimestre já entregue.
- Detalhe de cada evento mostra contexto de CVM/NEWS/RESEARCH **só se
  já existir no sistema** - zero chamada de IA.
- Bug real corrigido durante o desenvolvimento: cálculo pulava o
  trimestre recém-encerrado (ainda dentro do prazo) direto pro seguinte.
- `tests/test_eventos.py` (novo, 21 checks) + validação visual via
  Playwright.

## 2026-10-01 (feat: Research - contexto de NEWS por ativo)

- Research de um ticker ganha seção "CONTEXTO RECENTE · NEWS" (até 5
  notícias, mais recentes primeiro, só título+data+link) - reaproveita
  `data.news.obter_noticias` (mesma função/cache/identificador que a
  aba NEWS já usa, nenhum sistema novo). Nunca gera resumo de IA, nunca
  afirma causalidade.
- Só é chamado quando um resumo é de fato exibido (não na lista inteira)
  - sem N+1, sem deixar o Research mais lento.
- 11 testes novos (`tests/test_research_news_context.py`) + validação
  visual via Playwright.

## 2026-10-01 (fix: Research - fallback de modelo quando cota da IA esgota)

- **Causa**: `_chamar_groq` falhava (HTTP 429, free tier Groq) e o
  resumo ficava direto indisponível, sem segunda tentativa. 2 pontos na
  UI também vazavam texto cru de exceção pra falhas não-cota (achado
  junto, corrigido).
- **Fallback sem credencial nova**: mesma conta/chave Groq, segundo
  modelo (`openai/gpt-oss-120b`) - cota/rate-limit na Groq é por modelo,
  não por conta. Testado manualmente antes de habilitar.
  `_chamar_groq_com_fallback` tenta 1x o principal, 1x o fallback se
  necessário (nunca loop), nunca expõe detalhe técnico na UI (só no log
  via `_log_erro_ia`).
- Cache (resumo já salvo nunca chama IA de novo) e separação entre erro
  de extração de texto vs erro de IA - confirmados intactos, sem
  mudança necessária.
- 7 cenários novos de teste (modelo principal, fallback por cota,
  fallback por erro técnico, ambos falhando, skip de modelo já sabido
  esgotado, cache, separação de motivos).

## 2026-10-01 (test: Research - primeira suíte de testes commitada)

- `tests/test_research.py` (novo diretório `tests/`, primeiro arquivo de
  teste do projeto a ser commitado) - 19 checks determinísticos
  (histórico de mudanças + parsing da extração estruturada), Groq e
  Supabase mockados, roda sem secrets nem custo de API.
- Validação visual da aba RESEARCH via Playwright (harness isolado) -
  "O QUE MUDOU" e Research Radar renderizando corretamente, sem erro de
  console.

## 2026-10-01 (feat: Research - separação FATO/visão da casa no prompt)

- Prompt narrativo ganha uma regra nova (não substitui nada): opinião/
  expectativa de casa/analista precisa continuar atribuída
  explicitamente dentro do texto ("Segundo a X...") - nunca vira fato de
  mercado. Leitura própria do sistema (quando conecta pontos que a fonte
  não conecta) também precisa vir sinalizada como tal. Foco de Morning
  Call reforçado pra sempre nomear quem falou e quais ativos foram
  citados. Validado com chamadas reais à Groq.

## 2026-10-01 (feat: Research - "O que mudou" + Research Radar)

- Novo painel "O QUE MUDOU" na watchlist do RESEARCH - só aparece quando
  há mudança real de recomendação/preço-alvo (sempre citando a casa,
  nunca "consenso de mercado"). Novo painel **Research Radar** (CASA |
  TICKER | TIPO | DATA | STATUS) com sinais reais (NOVO = relatório
  publicado hoje; MUDANÇA DE TARGET/RECOMENDAÇÃO = histórico comparado).
- `coletor_local.py` agora também coleta snapshot de recomendações da
  Genial (necessário pra popular o histórico em produção - mesma
  limitação de WAF que já afetava a coleta de relatórios).

## 2026-10-01 (feat: Research - extração estruturada + histórico não-perecível)

- `resumir_com_groq` agora também extrai preço-alvo/recomendação (só
  documentos tipo AÇÕES, chamada extra pequena reaproveitando o texto
  já carregado) - regra explícita: nunca estimar, só reportar o que
  estiver literalmente no texto. Prompt narrativo principal **intocado**.
- 2 colunas novas em `research_itens` (`preco_alvo`, `recomendacao`) e
  nova tabela `research_recomendacoes_historico` (não-perecível, ao
  contrário de `research_itens` que apaga após 5 dias) - base real pra
  "O que mudou" em partes futuras desta fase.
- **Ação necessária**: rodar `sql/research.sql` atualizado no Supabase
  (idempotente, seguro re-rodar).
- Testado com 9 cenários reais via Groq (preço-alvo/recomendação certos
  quando existem, `None` quando não existem - nunca inventado) + 12
  testes de histórico com Supabase mockado.

## 2026-10-01 (perf: corrige scroll pulando pro topo ao filtrar)

- **RESEARCH, CVM e TOP MERCADO**: clicar num filtro (pill de ticker/
  tipo/casa/região/setor, busca, paginação) disparava rerun da página
  inteira, resetando a posição de scroll. Corrigido com `@st.fragment`
  nas 3 funções de entrada (`render_research`, `render_cvm`,
  `render_top_mercado`) - mesmo padrão já usado em NEWS. Zero mudança
  de dado/lógica.

## 2026-10-01 (feat: workspace modular em VISÃO GERAL + MACRO)

- **VISÃO GERAL e MACRO ganham layout livre** (drag/resize), mesma
  mecânica já validada em produção na aba MERCADO. VISÃO GERAL já
  estava estruturada em funções de painel discretas - só precisou
  registrar (`REGISTRO_PAINEIS`) e trocar o renderizador, zero
  reescrita de conteúdo. Adicionados controles de ordem/visibilidade no
  CONFIG pra VISÃO GERAL (faltavam - sem eles, um painel oculto lá
  ficaria preso sem jeito de reexibir).
- `ui/workspace.py` continua sem nenhum caso especial por aba
  (`aba_id` é só uma string) - mesma correção de 3 bugs reais já
  aplicada vale pra todas as abas que adotam o sistema.

## 2026-10-01 (feat: ticker de mercado unificado)

- **Duas faixas de ticker viram uma só.** A faixa de índices (IBOVESPA/
  DÓLAR/EURO, animação contínua em CSS puro) e a faixa da watchlist
  pessoal (estática, cortava com `overflow-x:auto`, posicionada logo
  após a NAV) se fundem numa única fita dentro do header fixo - a
  watchlist entra na mesma lista de itens que já alimentava o loop dos
  índices, mesma fonte de dados (`obter_cotacao`, já em uso), zero
  ticker inventado.
- `_watchlist_chips()` e seu CSS (`.wchip*`) removidos - deixaram de
  existir como faixa separada.
- Validado com Playwright (harness com CSS/DOM reais, sem login): 1
  faixa só, animação de movimento confirmada em tempo real, geometria
  HEADER→TICKER→NAV→CONTEÚDO sem sobreposição, zero erro de JS.

## 2026-10-01 (fix: workspace modular - 3 bugs reais corrigidos, validado em producao)

- **Drag/resize do workspace modular (MERCADO) não funcionava de verdade
  em produção** (feature abaixo tinha ido ao ar quebrada). 3 causas
  independentes em `ui/workspace.py`: (1) conflito de especificidade CSS
  fazia `position:absolute` nunca ser aplicado nos painéis; (2) a ponte
  JS→Python só disparava `input`, que o `st.text_input` do Streamlit não
  comita pro backend (precisa de blur/Enter) - nada era persistido; (3)
  a flag anti-duplicação de listener (`dataset.workspaceLigado`)
  sobrevivia entre reruns num elemento preservado pelo React, enquanto o
  Streamlit recria o iframe do script a cada rerun - só o primeiro gesto
  da sessão funcionava. Detalhes completos (causa, por que quebrava,
  correção) no PROGRESSO.md.
- Achados e corrigidos só com um harness Playwright dedicado (mouse real
  no DOM) - AppTest não executa JS/interação de navegador, por isso
  nenhum desses 3 bugs tinha aparecido nos testes anteriores.
- **Confirmado por Rodrigo rodando de verdade em pregao.streamlit.app.**
- Commit `bf023c2`. Único arquivo alterado: `ui/workspace.py`.

## 2026-10-01 (feature: workspace modular/layout livre em MERCADO)

- **MERCADO ganha layout livre** (`ui/workspace.py`, novo): arraste pelo
  título do painel pra mover, pela borda/canto inferior-direito pra
  redimensionar — sem lib de grid de terceiro (CSS posiciona os mesmos
  `st.container` de sempre; JS via `st.iframe` manipula o DOM real do
  app, mesma origem; resultado final volta pro Python por um
  `st.text_input` oculto, só ao soltar o mouse). Popover "⚙" por painel
  (restaurar tamanho/posição, ocultar) e botão pra restaurar a aba
  inteira. Nova prefs `layout_paineis_livre`. MERCADO é a aba piloto;
  as demais continuam no sistema antigo de tamanhos fixos.
- **Corrigido antes de ir pro ar**: o script usava
  `st.components.v1.html` (API deprecada desde 01/06/2026); trocado por
  `st.iframe`, que por sua vez rejeita `height=0` — ajustado pra
  `height=1`.
- Detalhes completos (arquitetura, decisões de unidade x/y/w/h, testes)
  no PROGRESSO.md.

## 2026-09-28 (feature: transcrição das lives da Genial)

- **`data/research/genial_lives.py` passa a coletar de verdade**: pedido
  explícito do Rodrigo. O mecanismo (feed RSS do canal no YouTube +
  legenda automática via `youtube_transcript_api`) já estava pronto e
  testado há dias, mas ficava desligado porque o robots.txt do YouTube
  proíbe `/feeds/videos.xml` pra bots genéricos — mesma política de
  respeitar robots.txt usada em toda coleta do projeto. Removida a
  checagem de robots.txt SÓ nesse módulo, com justificativa documentada
  no próprio arquivo (uso pessoal/não-comercial, volume baixo,
  exceção única — não generalizar sem decisão explícita igual).
- `CASAS["genial_lives"]` (`data/research/__init__.py`):
  `disponivel`/`ativa_por_padrao` viram `True`.
  `config.PREFS_PADRAO["research_casas_ativas"]` ganha "genial_lives"
  pra usuário novo. **Usuário existente (Rodrigo) precisa marcar
  manualmente** "Genial (Lives)" em CONFIG → CASAS DE RESEARCH (prefs
  já salvas não migram sozinhas, mesma limitação que já existia pra
  esse seletor).
- Testado com chamada real: feed retornou 9 vídeos (Morning Call,
  Fechamento de Mercado, Podcast Genial Analisa), transcrição extraída
  com sucesso de um deles (35.994 caracteres). AppTest na aba RESEARCH
  sem exceção.

## 2026-09-28 (feature: composição oficial do Ibovespa via B3)

- **Universo de tickers da aba MERCADO (e da busca global) deixa de ser
  uma lista curada à mão e passa a vir da API oficial e pública da B3**
  (`data/ibovespa.py`, novo — mesmo endpoint usado pelo site oficial de
  composição do índice, sem autenticação). Retorna a carteira teórica
  real do Ibovespa (76 papéis hoje, contra ~64 aproximados antes) com
  peso de cada papel; cache de 24h (a carteira só muda em rebalanceamento
  trimestral). Descoberto e confirmado funcionando neste sandbox — item
  novo no DIAGNÓSTICO DE FONTES ("B3 (composição Ibovespa)") pra
  confirmar também em produção.
- **`config.IBOVESPA_COMPOSICAO` renomeado pra `IBOVESPA_SETORES`**: a B3
  não classifica por setor econômico nesse endpoint, então a curadoria
  manual continua existindo, mas só como mapa ticker→setor (+ fallback
  de universo de tickers se a B3 falhar). Ticker real sem setor curado
  cai em "Outros" em vez de inventar classificação.
- **24 papéis novos que a composição oficial trouxe e não estavam na
  lista antiga ganharam setor curado** (ex: ALOS3→Shoppings e Imóveis,
  ITSA4/BBDC3→Bancos, BBSE3/PSSA3/CXSE3→Seguros [categoria nova],
  COGN3/YDUQ3→Educação [categoria nova], VBBR3→Petróleo e Gás,
  TAEE11/EGIE3/ENGI11/ISAE4→Energia Elétrica, CSMG3→Saneamento, entre
  outros) — sem isso, ~1/3 dos papéis reais apareceria sem setor no
  painel SETORIAL.
- **JBSS32 confirmado fora do índice oficial** (não é mais membro do
  Ibovespa desde a migração pra BDR/NYSE) — continua funcionando
  normalmente na busca/watchlist (não depende de estar no índice), só
  não entra mais nos painéis de visão de mercado (termômetro, altas/
  baixas, setorial), que são especificamente sobre o índice.
- Testado via `streamlit.testing.v1.AppTest` (VISÃO GERAL, MERCADO,
  EQUITY, sem exceção) e chamada real contra a B3 (76/76 papéis com
  dado válido, 0 em "Outros" depois da curadoria). `compileall` limpo.

## 2026-09-28 (bug real + pedido: tickers desatualizados + desempenho semana/mês)

- **Bug real relatado pelo Rodrigo**: buscou "JBSS3" na busca global e o
  ticker não foi reconhecido nem adicionado à watchlist. Investigado a
  fundo (não presumido): confirmado via yfinance + pesquisa que **13
  tickers da lista curada (`config.IBOVESPA_COMPOSICAO`) estavam
  desatualizados** por eventos corporativos reais entre 2025 e 2026 —
  fusões, mudanças de nome/ticker e uma deslistagem:
  - ELET3/ELET6 → **AXIA3** (Eletrobras virou Axia Energia, nov/2025)
  - EMBR3 → **EMBJ3** (Embraer, nov/2025)
  - JBSS3 → **JBSS32** (JBS migrou pra NYSE, ação local virou BDR)
  - MRFG3 + BRFS3 → **MBRF3** (fusão Marfrig+BRF, set/2025)
  - NTCO3 → **NATU3** (Natura&Co incorporada pela Natura Cosméticos)
  - CCRO3 → **MOTV3** (CCR virou Motiva, mai/2025)
  - RRRP3 → **BRAV3** (fusão 3R+Enauta, virou Brava Energia)
  - ARZZ3 → **AZZA3** (fusão Arezzo+Grupo Soma, virou Azzas 2154)
  - CPLE6 → **CPLE3** (mesma empresa, classe de ação diferente — CPLE6
    parou de responder no yfinance)
  - AZUL4 e CRFB3: **removidos sem substituto** (AZUL4 virou AZUL54, que
    também não responde no yfinance; CRFB3/Carrefour Brasil foi
    deslistada de verdade em 30/05/2025, fechou capital).
  - Todos os 12 tickers novos testados individualmente contra dado real
    antes de entrar no config — confirmado 60/60 papéis da lista
    curada com dado válido agora (antes: 47/60, 13 falhando).
- **Pedido do Rodrigo**: desempenho da semana e do mês, além do dia, em
  VISÃO GERAL e MERCADO. Adicionado seletor DIA/SEMANA/MÊS (efeito
  imediato) nos painéis Maiores Altas/Baixas, Termômetro e Desempenho
  Setorial — VISÃO GERAL reusa essas mesmas funções, ganha o recurso de
  graça. Cada painel tem sua janela independente (mudar um não afeta os
  outros). Janelas: 7/30 dias corridos, mesma convenção já usada nos
  retornos da aba EQUITY (1S/1M).
- Arquivos: `config.py` (tickers corrigidos), `data/news_setores.py`
  (mesmos tickers no classificador de setor do TOP MERCADO/NEWS),
  `data/mercado.py` (`variacao_semana_pct`/`variacao_mes_pct`, período
  do lote 5d→2mo), `ui/mercado_tab.py` (seletor de janela).
- Testes: `compileall` limpo; `obter_panorama_ibovespa()` confirmado
  60/60 com dado válido (era 47/60); teste dirigido do seletor de
  janela (mudança de conteúdo ao trocar DIA→SEMANA→MÊS, painéis
  independentes entre si); AppTest nas 9 seções sem exceção.

## 2026-09-28 (ETAPA 8 — busca global no header)

- **Busca global (nova)**: campo de busca acima da navegação principal,
  visível em qualquer aba — busca por ticker ou nome (mesmo autocomplete
  da ETAPA 1). Três atalhos: **EQUITY ↗** (abre a cotação completa do
  ativo), **NOTÍCIAS ↗** (abre NEWS já filtrado por esse ticker), **+
  WATCHLIST** (só adiciona, sem sair da aba atual).
- **Auto-adiciona à watchlist quando necessário**: EQUITY e NEWS só
  mostram dado de tickers da watchlist (é assim que já funcionavam) —
  os atalhos "↗" adicionam o ticker primeiro (com a mesma validação já
  usada na barra lateral) se ele ainda não estiver lá.
- **Bug real pego no teste**: `st.session_state["secao_ativa"]` (a key
  do próprio widget de navegação) só pode ser escrita ANTES desse
  widget instanciar no mesmo rerun — escrever depois derruba com
  `StreamlitWidgetAlreadyInstantiatedError`. Corrigido reordenando o
  código: o cálculo das seções e a busca global agora vêm ANTES do
  widget de navegação em si (puro reposicionamento, lógica do nav
  intocada).
- Arquivos: `app.py`.
- Testes: `compileall` limpo; teste dirigido (usuário novo por
  execução) cobrindo os 3 atalhos com tickers reais fora da watchlist
  (MELI34 → EQUITY, BBAS3 → NOTÍCIAS com filtro pré-aplicado, AAPL34 →
  só adicionar sem navegar); AppTest nas 9 seções sem exceção.

## 2026-09-26 (revisão da ETAPA 7 — tamanho do painel direto na aba)

- **Feedback do Rodrigo**: a primeira versão da ETAPA 7 só deixava
  escolher tamanho/visibilidade dentro do formulário de CONFIG, longe
  do painel — sem ver o resultado na hora. Pedido explícito: "queria
  escolher na aba mesmo".
- **Popover "⚙" em cada painel** (MACRO/MERCADO): tamanho (1/4, 1/2,
  3/4, FULL) muda com efeito imediato, sem formulário — clica, o painel
  já muda de largura na hora. Também dá pra esconder o painel direto
  dali. Persiste de verdade (Supabase), não só na sessão.
- **CONFIG agora só cuida de reexibir** um painel escondido (única coisa
  que precisa vir de fora — um painel escondido não tem cabeçalho pra
  clicar). Tamanho saiu do formulário de CONFIG de propósito, pra não
  ter duas UIs fazendo a mesma coisa.
- Arquivos: `ui/paineis.py` (popover novo, `controle_layout_config` →
  `controle_visibilidade_config`, sem tamanho), `ui/macro_tab.py`/
  `ui/mercado_tab.py` (`persistir_fn` repassado), `app.py` (integração).
- Testes: `compileall` limpo; teste dirigido com usuário novo por
  execução (evita contaminar com estado de testes antigos — achado
  real do próprio processo de teste, não da aplicação): resize
  imediato persistindo sem CONFIG, esconder painel direto na aba,
  reexibir via CONFIG; AppTest nas 9 seções sem exceção.

## 2026-09-25 (correção urgente — KeyError em produção na aba EQUITY)

- **Bug real relatado pelo Rodrigo em produção**: `KeyError: 'roe'` ao
  abrir EQUITY, traceback apontando pra tabela FUNDAMENTOS (ETAPA 4).
- **Causa raiz**: `data/prices.py:obter_indicadores()` usa
  `_ultimo_indicadores_valido()` (`st.cache_resource`, sobrevive entre
  deploys no mesmo processo do Streamlit Cloud) como fallback quando a
  coleta do momento falha. Um valor cacheado ANTES da ETAPA 4 (sem
  `roe`/`margem_*`/`divida_liquida`, campos adicionados só depois)
  ficava vivo na memória do processo; quando esse fallback era usado, o
  dict retornado não tinha as chaves novas — `ind['roe']` em `app.py`
  quebrava com `KeyError`.
- **Correção**: a mesclagem do fallback agora começa do schema ATUAL
  (`resultado`, todas as chaves de hoje presentes) e só sobrescreve com
  o que `anterior` realmente tiver — garante todas as chaves sempre
  presentes, mesmo com um cache mais antigo. Reproduzido com um cache
  falso no formato antigo antes de corrigir, confirmado que o bug some
  depois.
- Arquivos: `data/prices.py` (`obter_indicadores`).
- Testes: `compileall` limpo; reprodução direta do bug (cache simulado
  no formato pré-ETAPA-4) confirmando `KeyError` ANTES da correção e
  ausência dele DEPOIS, com os valores antigos preservados e os campos
  novos virando `None` (não quebra, não inventa dado); `obter_indicadores`
  com dado real (PETR4) continua retornando todos os campos certos;
  AppTest nas 9 seções sem exceção.

## 2026-09-25 (ETAPA 7 — layout configurável: visibilidade + tamanho de painel)

- **Visibilidade e tamanho por painel (MACRO e MERCADO)**: além de
  reordenar (já existia), agora dá pra esconder um painel e escolher a
  largura dele (1/4, 1/2, 3/4, FULL) em CONFIG. Painéis na mesma linha
  com largura somando até 1.0 ficam lado a lado (`st.columns`); um
  painel FULL sempre fica sozinho na própria linha.
- **Sem redimensionamento livre com o mouse**: decisão já registrada
  antes (FILA2-T5) e mantida — Streamlit não tem drag-resize nativo, e
  introduzir um componente de terceiros seria uma dependência nova. As
  4 larguras fixas cobrem o pedido comum ("quero X e Y lado a lado,
  menores") só com `st.columns()`.
- **Escopo**: só MACRO e MERCADO, as únicas abas que já usavam o sistema
  de painéis registrados (`ui/paineis.py`). Migrar EQUITY/CVM/NEWS/
  RESEARCH/TOP MERCADO/VISÃO GERAL pra esse sistema é um trabalho bem
  maior (redesenhar cada painel pra funcionar numa coluna mais estreita)
  — fora do escopo desta rodada.
- **Zero mudança de comportamento pra quem nunca configurar nada**: sem
  config salva, cada painel continua FULL width, um por linha, exatamente
  como antes (`st.container(border=True)` direto, sem `st.columns`
  desnecessário).
- Arquivos: `ui/paineis.py` (`controle_layout_config`, empacotamento em
  linhas), `config.py` (`paineis_visiveis`/`tamanho_paineis` em
  `PREFS_PADRAO`), `app.py` (integração no formulário de CONFIG).
- Testes: `compileall` limpo; testes unitários do empacotamento em
  linhas e da resolução de tamanho/visibilidade (com e sem config
  salva); teste dirigido end-to-end (AppTest) esconder um painel +
  redimensionar outro via CONFIG, salvar, reabrir MACRO e confirmar que
  renderiza sem exceção com o layout novo; AppTest nas 9 seções sem
  exceção.

## 2026-09-25 (ETAPA 6 — RESEARCH: filtros consistentes com o resto do app)

- **Filtros de Casa/Tipo/Ticker (aba RESEARCH)** trocados de
  `st.multiselect`/`st.selectbox` (chips genéricos do Streamlit) para
  `st.pills` (mesmo componente visual usado em CVM/NEWS/TOP MERCADO/
  MERCADO) — Casa e Tipo em modo multi-seleção (mesmo comportamento de
  antes, tudo selecionado por padrão), Ticker em seleção única com
  "Todos". Zero mudança na lógica de filtro em si (mesma comparação
  `in`/`==` sobre as mesmas listas) — só o widget mudou.
- Adicionado `flex-wrap` nos grupos de pills da aba (mesma regra já
  usada em NEWS/CVM) — sem isso, Tipo (até 6 opções) podia estourar a
  largura de uma coluna de 1/3.
- Auditoria do resto da aba (feed de relatórios, painel watchlist,
  cabeçalho): sem achados adicionais — já bem polido de sessões
  anteriores, nenhuma mudança fora dos filtros.
- Arquivos: `ui/research_tab.py`.
- Testes: `compileall` limpo; teste dirigido com dados mockados (Genial/
  XP bloqueadas neste sandbox, não dá pra testar com dado real de
  research aqui) confirmando as pills vêm com tudo selecionado por
  padrão e o filtro por casa/ticker funciona (3→2→1 relatórios); AppTest
  nas 9 seções sem exceção.

## 2026-09-25 (ETAPA 5 — CVM: bloco de destaques)

- **Painel DESTAQUES (novo)** no topo da aba CVM, antes da busca/filtros:
  fatos relevantes nos últimos 30 dias, ticker mais ativo (mais
  documentos no período) e último documento recebido — pulso rápido da
  atividade da watchlist antes de filtrar/buscar. Calculado sobre TODOS
  os documentos (não filtrados), em memória, sem consulta nova à CVM.
- Fecha o item pendente da ETAPA 5 do redesign ("filtros mais
  granulares, bloco de destaques") — os filtros/busca já tinham sido
  cobertos no upgrade anterior da aba CVM.
- Arquivos: `ui/cvm_tab.py` (`_painel_destaques`, `_dentro_de_dias`).
- Testes: `compileall` limpo; teste dirigido confirmando os 3 campos
  com valor real (1 fato relevante, PETR4 como mais ativo com 6
  documentos, último documento 19/09/2026); reteste completo da CVM
  (filtro/busca/paginação/reset/abertura de documento) sem regressão;
  AppTest nas 9 seções sem exceção.

## 2026-09-25 (upgrade tela inicial/login — pedido explícito)

- **Tela de apresentação (sem login) redesenhada** de ponta a ponta:
  título forte ("SEU TERMINAL DE MERCADO." com cursor piscando), subtítulo
  e microcopy curtos (substituem o parágrafo longo anterior), linha de
  tags (B3 · MACRO · JUROS · NEWS · RESEARCH · CVM), prévia ilustrativa
  do terminal (IBOVESPA/DÓLAR + mini watchlist + notícias mock,
  claramente rotulada "PRÉVIA ILUSTRATIVA" — não são dados reais) e botão
  "ENTRAR COM GOOGLE" com ícone oficial do Google (SVG embutido, sem
  request externo) e hover discreto.
- **Zero mudança em autenticação**: `st.login()`/`st.user`/sessão/rotas
  intocados — só a apresentação (`auth.tela_apresentacao()`) mudou.
- **Decisão**: prévia do terminal usa dados estáticos/ilustrativos, não
  busca cotação real — evita adicionar chamada de rede numa tela que
  qualquer visitante anônimo carrega (antes de qualquer login/cache por
  usuário), e o rótulo "PRÉVIA ILUSTRATIVA" deixa claro que não é dado ao
  vivo (consistente com o princípio do projeto de nunca fazer dado
  passar por real quando não é).
- Arquivos: `auth.py` (reescrito).
- Testes: `compileall` limpo; AppTest da tela sem login (sem mock de
  autenticação — testa o caminho real de visitante anônimo) confirma
  render sem exceção e todos os elementos (hero/tags/prévia/botão)
  presentes no HTML; AppTest nas 9 seções autenticadas sem exceção
  (confirma que nada fora da tela de login quebrou). **Validação visual
  em navegador não foi possível** (extensão Chrome não conectou nesta
  sessão, confirmado pelo Rodrigo) — commitado sem essa confirmação, a
  pedido dele; fica pendente conferir visualmente (hero/prévia/botão/
  responsividade) na próxima vez que abrir o app.

## 2026-09-25 (upgrade aba CVM — pedido explícito, fora da ordem do redesign)

- **Bug real de raiz corrigido:** a tabela da aba CVM usava
  `st.columns([88, 62, 118, 1])` pra DATA/TICKER/TIPO/ASSUNTO — esses
  números são pesos RELATIVOS (não pixels), então a coluna de assunto
  recebia 1/269 da largura (~0,4%), não "o resto da tela" como o
  comentário antigo sugeria. Era a causa raiz do conteúdo cortado à
  direita, não a truncagem em si. Corrigido pra `[9, 8, 16, 55]`
  (assunto ~62% da largura) + cabeçalho de coluna novo (a tabela não
  tinha nenhum antes).
- **Busca textual (nova):** campo "Buscar documentos..." acima dos
  filtros, procura em ticker/assunto/tipo/categoria original
  (normalizado, sem acento/maiúscula), combinável com os filtros de
  ticker/tipo já existentes — tudo em memória sobre os documentos já
  coletados, nenhuma consulta nova à CVM.
- **Paginação real (nova):** substituiu o "VER MAIS" incremental por
  navegação por página (‹ Anterior / números / Próxima ›), 50 documentos
  por página, reseta pra página 1 quando filtro/busca muda. Removida a
  janela automática de 30 dias (a ordenação por data mais recente
  primeiro já resolve isso naturalmente com paginação de verdade).
- **Hover de linha + badges mais compactos:** cada linha agora é um
  `st.container(key=...)` de verdade (antes as colunas eram soltas),
  permitindo highlight de fundo ao passar o mouse; badges de tipo com
  padding/alinhamento mais consistentes.
- **Contador reformatado:** "N resultados · M documentos" quando há
  filtro ativo, só "M documentos" quando não há.
- **Descrição da aba compactada:** de um parágrafo longo pra duas linhas
  curtas (principal + secundária).
- Arquivos: `ui/cvm_tab.py` (reescrito). `data/cvm.py` não mudou — a
  pipeline coleta→cache→filtro já era 100% em memória, sem nova consulta
  por filtro (confirmado antes de mexer, não precisou de mudança).
- Testes: `compileall` limpo; AppTest em todas as 9 seções sem exceção;
  teste dirigido da CVM cobrindo carga inicial (653 docs reais),
  filtro ticker (PETR4: 271), filtro ticker+tipo (37), busca combinada
  com os dois filtros (8), reset pra TODOS (volta a 653, página volta a
  1), paginação (avança pra página 2), e abertura de documento (dialog
  abre) — todos passando contra dado real. **Validação visual em
  navegador pendente**: a extensão Chrome não conectou nesta sessão,
  então não deu pra confirmar visualmente (layout/cores/responsividade)
  antes do commit, a pedido do Rodrigo. Fica pendente conferir na
  prática.

## 2026-09-25 (redesign — ETAPA 4: EQUITY)

- **Painel FUNDAMENTOS (novo, dentro de INDICADORES):** ROE, margem
  líquida, margem operacional, margem EBITDA e dívida líquida (com
  múltiplo DL/EBITDA) — tudo via `tk.info` do yfinance, mesmo mecanismo
  de fallback/cache já usado pelos indicadores existentes.
- **ROIC ficou de fora:** testado contra dado real (PETR4/VALE3/ITUB4/
  MELI34) e o `tk.info` não tem campo equivalente — calcular na mão
  exigiria estimar capital investido e taxa efetiva de imposto a partir
  de outros relatórios, virando aproximação em vez de dado reportado.
  Mesmo princípio de nunca inventar dado já aplicado no resto do
  projeto.
- **Bug real pego no teste:** `ebitdaMargins`/margens baseadas em custo
  de produtos vendidos vêm `0.0` (não `None`) do yfinance pra bancos
  (ITUB4) — não é margem zero de verdade, é ausência de dado pro modelo
  contábil de instituição financeira (sem EBITDA/COGS tradicional).
  Mostrar "0,00%" seria enganoso. Corrigido tratando `0.0` como ausente
  nesses campos.
- Arquivos: `data/prices.py` (`obter_indicadores`, `_pct_ou_none`),
  `app.py` (painel INDICADORES).
- Testes: `compileall` limpo; `obter_indicadores` rodado contra dado
  real pros 4 tickers de teste, confirmando valores corretos e o `None`
  do bug do ITUB4; AppTest em todas as 9 seções sem exceção; conferido
  via `at.markdown` que a tabela FUNDAMENTOS renderiza de verdade.

## 2026-09-25 (redesign — ETAPA 3: MACRO)

- **Focus multi-ano:** tabela FOCUS IPCA/SELIC na aba MACRO passou de
  2 colunas (ano atual + seguinte) pra 3 (ano atual + dois seguintes),
  mesma fonte (Olinda/BC), sem chamada extra por ano (já buscava um
  request por ano/indicador).
- **Painel CENÁRIO GLOBAL (novo):** ouro, petróleo Brent/WTI, minério de
  ferro (SGX TSI CFR China), Treasuries 10 anos e VIX — preço + variação
  do dia, via yfinance (mesmo mecanismo de lote já usado pros mercados
  globais da aba MERCADO). Agenda econômica/próxima reunião do Copom
  ficam de fora por enquanto: exigiria uma fonte de calendário confiável
  que o projeto não tem hoje (não inventamos datas).
- Arquivos: `config.py` (`CENARIO_GLOBAL`), `data/macro.py`
  (`obter_cenario_global`, `_focus_multi_ano`), `ui/macro_tab.py`.
- Testes: `compileall` limpo; `obter_cenario_global`/`obter_focus_ipca`/
  `obter_focus_selic` rodados contra dado real (6/6 itens do cenário
  global, 3 anos em ambos os Focus); AppTest em todas as 9 seções
  (instância nova por aba, sem exceção).

## 2026-09-24 (modo autônomo 3 — bugs P0/P1)

- **P0.1 — indicadores (P/L, P/VP, DY, valor de mercado) voltaram a
  funcionar:** estavam todos "—" em produção (Yahoo bloqueando `tk.info`
  em IP de datacenter). Corrigido com sessão `curl_cffi` (impersonate
  Chrome) + fallback pra sessão padrão, cache de 12h e fallback pro
  último valor válido conhecido se a coleta do momento falhar.
- **PRIORIDADE 1/2 — notícias de BDR (MELI34 e outras) não apareciam:**
  causa raiz eram dois bugs genéricos de normalização de nome de empresa
  (sufixo jurídico em inglês não removido do longName do yfinance,
  quebrando o filtro de relevância; busca só tentava o nome legal/ticker
  da B3, nunca o ticker/nome originais). Corrigido com sufixos em inglês
  no regex de limpeza + `config.TICKER_ALIASES` (genérico, qualquer
  ticker pode ganhar aliases) + busca multi-termo com dedup. MELI34
  testado de verdade: 0 → 3 notícias reais.
- **P0.4 — formatação/filtro de NEWS:** filtro de ticker restrito à
  watchlist (não mostra mais código de contrato futuro tipo WDOV26),
  ticker duplicado no prefixo da manchete corrigido, páginas de
  perfil/cotação sem conteúdo real ("Alpargatas (ALPA4)") filtradas,
  janela de tempo (48h/5 dias) explícita no caption.
- **P0.3 — coletor local agendado:** tarefa criada no Agendador de
  Tarefas do Windows (dias úteis, 7h-20h, a cada 30min, `pythonw.exe`
  sem janela). Achado real ajustando pra `pythonw`: `sys.stdout`/
  `sys.stderr` podem vir `None` sob esse modo, e os módulos de coleta
  usam `print()` — corrigido com um sink seguro antes de qualquer
  import. Genial/XP continuam bloqueadas mesmo localmente (rede desta
  máquina também bloqueia) — infraestrutura de agendamento funcional,
  mas ainda sem coletar dado novo dessas duas casas especificamente.
- **P0.5 — curva pré:** rótulo "Última (dd/mm)" em vez de "Hoje" quando
  a publicação da ANBIMA não é do dia atual.

- **P0.2/PRIORIDADE 3 — mapa do mercado sem +NaN% e sem tooltip
  técnico:** causa raiz era a agregação automática do `px.treemap` pros
  nós de setor/raiz (às vezes indefinida) + hover padrão mostrando nomes
  de coluna (`labels=`, `parent=` etc). Reescrito com `go.Treemap`
  manual — cada nó com cor/texto/hover 100% explícitos, sem nada
  automático do Plotly. Adicionada legenda de cor.

- **P4 — aba CVM ativada:** trabalho pronto de outra sessão (encerrada),
  assumido e testado. Documentos oficiais (fato relevante, comunicado,
  resultados trimestrais/anuais, proventos, calendário) da watchlist,
  resumo sob demanda, selo CONFIRMADA em notícias quando bate com um
  filing oficial da CVM, painel na EQUITY. Adaptado pra reusar
  `research_itens` em vez de criar tabela nova no Supabase.

- **Resumos e acesso às matérias (NEWS/TOP MERCADO):** matéria curta
  ganha resumo proporcional em vez de "conteúdo muito curto" (limiar
  200→60 chars); fragmentos curtos de fontes diferentes são combinados
  + manchetes antes de desistir de vez; botão "ABRIR MATÉRIA ↗" agora
  no topo do card (não precisa esperar o resumo); links por veículo com
  ícone ↗. Medição em 20 itens: 15/20 (75%), mas as 5 falhas foram
  todas por limite de cota do Groq (rodando em sequência rápida no
  teste) — zero falhas por conteúdo curto/indisponível.

- **REDESIGN DO TERMINAL — ETAPA 1 (fundação):** reset de zoom
  universal em todos os gráficos Plotly (`ui/graficos.py` — troca de
  ticker/período já reseta sozinha, mais um botão manual; achado real:
  nenhum gráfico tinha `key=`, por isso o zoom "grudava" ao trocar de
  filtro); busca/autocomplete de ativo (`ui/busca.py`, por ticker ou
  nome, sem chamada de rede por tecla) substituindo o campo que exigia
  ticker exato na sidebar. Bug de performance pego antes de commitar
  (nomes buscados ao vivo levavam 30s+ pra montar a lista) e corrigido
  com uma tabela estática de nomes. Plano completo das próximas etapas
  em `.claude/plans/`.

- **REDESIGN DO TERMINAL — ETAPA 2 (VISÃO GERAL):** nova aba "0 VISÃO
  GERAL", agora a home padrão do app — mercado agora (cards), gráfico
  do IBOV, altas/baixas, mais negociados, setorial, notícias, mercados
  globais, watchlist. Zero coleta nova — reaproveita funções já
  existentes de MERCADO/NEWS/MACRO direto. Navegação renumerada pra
  0-9 (VISÃO GERAL=0), abas reordenadas pra bater com o pedido.

## 2026-09-24 (sessão anterior)

- **Letreiro (ticker tape) maior:** fonte de ~12px pra ~14px, mais espaço
  entre itens, ticker da watchlist em negrito, `padding-top` do conteúdo
  ajustado pra faixa fixa (agora mais alta) não cobrir nada.
- **Correção urgente — NEWS/TOP MERCADO:** lentidão (lista envolvida em
  `st.fragment`, reruns não recarregam mais a aba inteira), agrupamento de
  notícias reescrito (funde manchetes sobre o mesmo fato mesmo com redação
  diferente, via entidades em comum + janela de 24h — antes só comparava
  contra o último grupo aberto), ícone `↗` de abertura direta por linha,
  scroll horizontal/corte de conteúdo corrigido (`min-width:0` nas colunas
  do `st.columns()`), coluna de ticker vazia removida (vira prefixo
  inline), tooltip nativo da manchete removido (cobria o `st.dialog`
  aberto por cima de qualquer coisa da página — mantido só no selo).
- **T8 (modo autônomo 2) — lives da Genial no YouTube:** mecanismo
  completo implementado e testado com dados reais
  (`data/research/genial_lives.py` - identifica Morning Call/Resumo da
  Manhã/Fechamento/Podcast Genial Analisa/Estratégia em Ação/Conversa com
  Zé Márcio/Reunião do Copom pelo título do vídeo, extrai legenda
  automática em pt), mas **desligado por padrão**: o robots.txt do
  YouTube proíbe o feed usado pra listar vídeos pra bots genéricos, e
  este projeto sempre respeitou robots.txt em toda coleta - não fiz
  exceção sozinho. Decisão de religar ou não fica com o Rodrigo (ver
  AÇÕES MANUAIS PENDENTES em PROGRESSO.md).
- **T7 (modo autônomo 2):** painel COMPARATIVO DA WATCHLIST em EQUITY
  (preço/variação/P-L/P-VP/DY lado a lado pra todos os papéis da
  watchlist + melhor/pior desempenho do dia). Corrigido um rótulo
  enganoso pego no teste: "maior alta" podia mostrar um ticker negativo
  quando a watchlist inteira estava no vermelho — renomeado pra "melhor/
  pior desempenho", neutro quanto ao sinal.
- **T6 (modo autônomo 2):** NÃO implementado — `data/cvm.py`/
  `ui/cvm_tab.py` parecem prontos, mas estão sem commit (trabalho em
  andamento de outra sessão); integrar agora dependeria de uma interface
  que ainda pode mudar, e ativaria em produção uma aba que a outra sessão
  deixou de propósito atrás de um placeholder. Retomar quando ela
  commitar. Ver decisão registrada em PROGRESSO.md.
- **T4 (modo autônomo 2):** barra de status fixa com relógio de Brasília,
  indicador de pregão aberto/fechado e nota de atraso de cotação — dentro
  do mesmo fragment do letreiro, sem rerun extra.
- **T5 (modo autônomo 2):** NÃO implementado por decisão do próprio
  Rodrigo (mudança arquitetural grande) — layout de painéis
  arrastável/redimensionável fica só documentado em PROGRESSO.md como
  sugestão futura.
- **T3 (modo autônomo 2) — nova aba MERCADO:** visão ampla do pregão -
  termômetro, maiores altas/baixas, mais negociados, desempenho setorial
  (gráfico de barras), mapa de calor (treemap) e mercados globais (S&P
  500, Nasdaq, Dow, FTSE, DAX, Nikkei, Hang Seng, Xangai). Dados via lote
  único do yfinance sobre uma lista curada de blue chips do Ibovespa
  (`config.IBOVESPA_COMPOSICAO`, não a composição oficial completa - ver
  MANUAL.md). Curva de juros e agenda de Copom/resultados ficaram de
  fora de propósito (ver PROGRESSO.md, decisão registrada).
- **T2 (modo autônomo 2):** tooltips explicativos em VALOR DE MERCADO,
  P/L, P/VP, DIV. YIELD e nas médias móveis 20/50/200 (BETA já tinha).
- **T1 (modo autônomo 2) — resumo de NEWS estruturado + fallback por
  manchetes:** formato fixo (O QUE ACONTECEU/NÚMEROS/IMPACTO/PRÓXIMOS
  PASSOS, 5-8 linhas); quando todas as fontes do grupo falham a extração
  mas há 2+ manchetes diferentes cobrindo o fato, tenta um resumo mais
  curto só com as manchetes (nota "(resumo baseado nas manchetes)").
  Corrigido também um bug de renderização (`white-space: pre-line`
  faltando fazia o resumo virar uma linha só no card). Medido em amostra
  real de 20 grupos: 100% de sucesso via texto completo; fallback
  validado à parte com teste dirigido (mock forçando falha total).
- **`coletor_local.py` grava log em arquivo:** rodando sem janela pelo
  Agendador de Tarefas, o stdout não fica visível em lugar nenhum — agora
  grava também em `coletor_local.log` (raiz do projeto, rotativo: 1MB x 3
  arquivos), além do stdout de sempre. Testado rodando o script de
  verdade (Genial/XP continuam bloqueadas neste sandbox, como esperado —
  o log registrou a falha corretamente).
- **Diagnóstico Genial/XP mais rápido:** `testar_conexao()` de ambas
  (usada só pelo painel DIAGNÓSTICO DE FONTES, aba CONFIG) agora usa
  orçamento/timeout ≤5s por padrão, em vez do orçamento de 20s da coleta
  real — a coleta real (usada pelo `coletor_local.py`) continua com o
  orçamento cheio.
- **Bug real corrigido — RESEARCH ainda travava por causa da Genial:** o
  painel "NA SUA WATCHLIST" chamava `obter_recomendacoes()`/
  `obter_swing_trade()` da Genial direto, sem passar pelo gate
  `tentar_coleta_automatica` nem pelo cooldown do `coletar_pendentes` —
  eram dados só-ao-vivo (cache em memória, nunca gravados no Supabase),
  então a trava de até 20s continuava acontecendo nesse painel específico
  mesmo depois do resto da aba já pular a coleta. Corrigido em
  `ui/research_tab.py`: pula as duas chamadas quando a Genial está com
  coleta automática desligada.
- **Genial/XP no Cloud:** confirmado por diagnóstico real de produção que
  ambas ficam bloqueadas também no Streamlit Cloud (não só no sandbox de
  dev) — `tentar_coleta_automatica: False` pras duas; a aba RESEARCH só lê
  do Supabase pra elas, sem esperar tentativa de coleta. Coleta real fica
  a cargo do `coletor_local.py` rodando fora do Cloud.

## 2026-09-23

- **T10 (modo autônomo 2):** e-mails com acesso a painéis de admin
  (DIAGNÓSTICO DE FONTES) saem do código (`config.EMAILS_DIAGNOSTICO`
  fixo) e passam a vir de `st.secrets["admin"]["emails"]`, com fallback
  pro e-mail atual enquanto o secret não é colado — nada quebra antes
  disso. Motivo: repositório público não deve ter e-mail pessoal fixo no
  código-fonte.
- **T4/T5 (modo autônomo, auditoria + performance):** achados reais na
  auditoria — `_ultima_cotacao_indice_valida` (fallback do letreiro)
  tinha um decorator `@st.cache_data` indevido empilhado sobre
  `@st.cache_resource`, quebrando a garantia de estado compartilhado que
  o fallback dependia; `_buscar_next_data` da Genial era chamada 2x
  separadas por `obter_recomendacoes`/`obter_swing_trade` sem cache
  próprio, batendo na mesma página duas vezes por render da aba
  RESEARCH; a busca de 8-10 fontes independentes do TOP MERCADO era
  sequencial (paralelizada com `ThreadPoolExecutor`, ~3s em vez de
  vários segundos); a sequência de tentativas da Genial (HTTP/1.1 +
  outros perfis) não tinha orçamento de tempo total, podendo passar de
  100s numa falha ruim — limitado a ~20s.
- **T1 (modo autônomo 2):** leitura de chave/modelo do Groq centralizada
  em `config.obter_credenciais_groq()` (fallback pra
  `st.secrets["GROQ_API_KEY"]` na raiz se `[groq]` não tiver a chave) —
  usada por research e news, que antes liam `st.secrets` cada um do seu
  jeito.
- Correções de produção (prefs de abas novas, letreiro "--", relevância/
  duplicata de notícias entre tickers, retenção de 5 dias) — ver commits
  anteriores a este changelog.

## Antes deste changelog

Ver histórico do git (`git log`) e `PROGRESSO.md` — o changelog começou
a ser mantido a partir do modo autônomo 2.
