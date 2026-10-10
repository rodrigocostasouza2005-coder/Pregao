# BACKLOG — PREGÃO

Pendências conhecidas, para resolver depois (ajustes visuais adiados
enquanto avançamos nas próximas fases).

## AUDITORIA VISUAL (2026-10-10) — pendências desta rodada

Ver PROGRESSO.md "AUDITORIA VISUAL — continuação 2026-10-10" pro
relatório completo (método, 6 bugs reais corrigidos com evidência de
screenshot). Itens investigados e **deliberadamente não alterados**:

- **SAÚDE DOS DADOS — tabela principal usa rolagem horizontal no
  mobile** (não truncamento de coluna, diferente do padrão já usado em
  CVM)
  PRIORIDADE: BAIXA · IMPACTO: BAIXO (funcional, só menos polido) · ESFORÇO: MÉDIO
  A tabela tem 6 colunas (COLETOR/FONTE/ESTADO/ÚLTIMA TENTATIVA/ÚLTIMO
  SUCESSO/REGISTROS NOVOS) com texto de largura bem variável (ex:
  "Fonte indisponível: timeout ao conectar na fonte (connection timed
  out apos 15s)" na coluna ESTADO) - truncar com reticências (como CVM
  faz) perderia informação de diagnóstico que é o propósito inteiro
  dessa aba. Rolagem horizontal (já implementada via
  `overflow-x:auto`) é funcional, só não tão polida quanto o padrão de
  truncamento - redesenhar exigiria decidir QUAIS colunas priorizar
  em tela estreita (card empilhado por coletor em vez de tabela?),
  decisão de produto maior que um ajuste pontual desta rodada.
- **EQUITY, TOP MERCADO, CONFIG** — não auditados visualmente nesta
  rodada
  PRIORIDADE: MÉDIA (nunca tiveram auditoria visual dedicada) · IMPACTO: DESCONHECIDO · ESFORÇO: DESCONHECIDO
  Fora da lista de áreas pedida explicitamente pelo Rodrigo nesta
  rodada (RADAR/MERCADO/MACRO/NEWS/CALENDÁRIO/RESEARCH/CVM/SAÚDE DOS
  DADOS/Navegação) - não tocados de propósito, candidatos naturais pra
  próxima rodada de auditoria visual.
- **MERCADO — 4 dos 5 painéis do registro não re-auditados nesta
  rodada** (altas/baixas, mais negociados, setorial, treemap - só
  `_painel_globais` foi reconferido de passagem)
  PRIORIDADE: BAIXA · IMPACTO: BAIXO (já teve 1 bug real corrigido pela
  sessão anterior, `a05c545`) · ESFORÇO: -
  Não refeito do zero sem evidência de regressão - mesmo critério de
  sempre (nunca re-auditar algo já verificado sem motivo concreto).
- **Escala não testada**: toda a auditoria desta rodada usou 3 tickers
  na watchlist (PETR4/VALE3/ITUB4) - nunca testado com watchlist vazia,
  1 ticker só, ou volume real (20+ tickers). Layout pode se comportar
  diferente em escala (ex: paginação, scroll, quantidade de pílulas de
  filtro) - não verificado.

## RADAR (2026-10-09) — pendências da nova aba de inteligência

Ver PROGRESSO.md "FASE RADAR" pra arquitetura completa. Itens
registrados nesta sessão, não resolvidos de propósito:

- ~~**`pytest tests/` completo falha em 3 testes de
  `tests/test_research_resumo_live_sync.py`**~~ — **corrigido** (sessão
  2026-10-09, pós-RADAR): `importlib.reload(research_tab)` depois do
  patch de `st.dialog` força a redecoração de `_abrir_resumo_live`
  independente de import anterior do módulo por outro arquivo de
  teste. `343/343` testes passam agora sob `pytest tests/` completo
  (antes: 340 passavam, 3 falhavam só nessa condição de ordem de
  coleta). Confirmado sem regressão: `compileall`/`pyflakes` limpos e
  os 25 arquivos de teste executados individualmente (convenção do
  projeto) continuam 100% ok.
- **Dado real de produção não confirmado**: Supabase/yfinance 100%
  bloqueados neste sandbox (mesma limitação de toda sessão anterior) -
  AppTest confirma que o RADAR não quebra e degrada certo (estado
  vazio honesto em todos os 5 módulos), mas não confirma que mudanças
  de tese/valuation reais aparecem corretas - só o Rodrigo confirma
  abrindo a aba em produção.
- **Custo/latência real do comparativo setorial**
  (`data/radar.py:comparaveis_setor`, ~5-15 chamadas yfinance por
  clique, dentro de um `@st.dialog` sob demanda) nunca medido contra
  rede real - se ficar lento demais em produção, considerar reduzir o
  universo de pares ou pré-calcular por setor num coletor agendado
  (mesmo padrão do CALENDÁRIO) em vez de ao vivo por clique.
- **Timezone multi-mercado**: RADAR herda a mesma lacuna já registrada
  na FASE 7 (ver abaixo, "FASE EUA 3") - datas de catalisadores/
  research pros ativos EUA piloto (NVDA/AAPL/MSFT) aparecem convertidas
  pro fuso de Brasília, não `America/New_York`.
- **Mudanças de tese cobrem só Genial Analisa** (única casa com
  histórico estruturado persistido hoje, ver `data/research/
  historico.py`) - XP/outras casas quando tiverem dado estruturado
  equivalente alimentam a MESMA tabela (`casa` já é campo genérico),
  zero mudança de schema necessária, só o coletor.
- **Copiloto de research é determinístico** (sem chamada de IA nova) -
  decisão de arquitetura deliberada (ver PROGRESSO.md, seção 2 da FASE
  RADAR), não um atalho forçado por falta de `GROQ_API_KEY` no sandbox.
  Se o Rodrigo quiser respostas em linguagem mais natural/sintetizada
  no futuro, dá pra acrescentar uma camada de IA por cima das MESMAS
  evidências (reaproveitando `data/research/resumir.py:_chamar_groq` ou
  equivalente) sem mudar a lógica de agregação.
- **Argumento contrário quase sempre vazio**: a tabela de histórico de
  recomendação (Genial) só guarda número (recomendação/preço-alvo), não
  o racional por escrito - sem texto pra extrair um argumento contrário
  real. Campo existe no schema (`argumento_contrario`), pronto pra uma
  fonte futura com racional em texto.

## FASE 8 (2026-10-09) — pendências da auditoria funcional/performance/MERCADO

Ver PROGRESSO.md FASE 8 pra auditoria completa (2 bugs reais corrigidos
nesta sessão: sincronia do resumo de Morning Call/Lives, rotação do
universo do coletor de eventos do CALENDÁRIO). Itens investigados e
**não confirmados/não implementados** nesta sessão:

- **"Mapa do mercado aparentemente vazio"**: não reproduzido com
  evidência real (sandbox sem rede pra buscar panorama real do
  Ibovespa). Hipótese não confirmada: se a última vela do dia tiver
  `volume=0` (ex: logo após abertura do pregão), TODOS os papéis caem
  no filtro `volume_financeiro > 0` de `ui/mercado_tab.py:_painel_
  treemap` e o mapa aparece vazio de verdade (não é bug de renderização,
  seria um efeito real do filtro combinado com o timing da coleta).
  **Pendência concreta pro Rodrigo**: em que dia/horário exato viu o
  mapa vazio? Se foi logo na abertura do pregão (perto das 10h),
  a hipótese ganha força; se foi no meio do pregão com volume normal
  em outras telas (ex: TOP MERCADO funcionando), é outra causa.
- **"Tabelas/gráficos cortados" em MERCADO**: testado com harness
  Playwright real (CSS/layout fiéis ao `style.css`/`ui/workspace.py`
  reais) em 2 cenários plausíveis (tabela de 10 linhas em painel de
  altura padrão 18rem; painel redimensionado pro mínimo 8rem) - NENHUM
  corte reproduzido nos dois (o painel usa `overflow:auto`, que vence
  sobre o `overflow-y:hidden` da tabela quando o conteúdo é maior que o
  espaço - resultado é scroll, não corte). **Pendência concreta pro
  Rodrigo**: qual painel especificamente, em que largura/altura de
  tela (desktop normal? notebook pequeno? painel redimensionado na
  mão?) - sem isso não dá pra tentar reproduzir de novo com mais
  precisão.
- **Performance: `@st.fragment` em MERCADO/MACRO/VISÃO GERAL** -
  candidato identificado (as únicas 3 seções sem fragment, entre as 8
  que usam alguma forma de renderização por aba; as outras 5 já
  ganharam isso na FASE 13 do ciclo de 2026-10-01, especificamente pra
  parar o "scroll pra cima" a cada clique de filtro). As 3 passam por
  `ui/workspace.py:renderizar_workspace` (drag/resize com ponte JS↔
  Python via iframe), sistema com histórico documentado de bugs sutis
  de escopo de rerun (3 bugs reais já corrigidos em produção, ver
  comentário em `ui/workspace.py:273-298`). Mudar o escopo de rerun
  (full-page → fragment) nessas 3 abas PODE ser uma melhoria real de
  performance (qualquer clique dentro delas hoje reroda a página
  inteira: header, ticker tape, sidebar, nav), mas precisa de validação
  com browser real (Playwright contra o app rodando de verdade,
  simulando o gesto de drag/resize) antes de aplicar - não disponível
  de forma segura neste sandbox. Próxima sessão com acesso a
  browser real contra o app rodando (não só harness isolado) pode
  tentar isso com segurança.

## FASE C (2026-10-09) — pendências do modal editorial de NEWS

Ver PROGRESSO.md FASE C pra auditoria completa (prompt novo, parser,
layout) + CHANGELOG.md pro resumo do que mudou. Itens não verificáveis
deste sandbox, registrados aqui pra o Rodrigo confirmar em produção:

- **Imagem real em produção**: o harness Playwright isolado confirmou
  que o fallback (`onerror`) dispara corretamente quando uma imagem
  falha ao carregar, mas a rede do sandbox bloqueia hosts de imagem
  externos (CDN de veículo de notícia) — nunca foi possível confirmar
  visualmente uma og:image REAL carregando no modal. Precisa abrir
  NOTÍCIAS em produção e clicar numa matéria com foto conhecida.
- **Formato RESUMO/LEITURA DE MERCADO com o Groq real**: o prompt novo
  (`data/news.py:_PROMPT_SISTEMA_RESUMO`) só foi testado com mocks
  (`_chamar_groq` nunca foi chamado de verdade nesta sessão, sem
  `GROQ_API_KEY` configurada no sandbox) — o parser
  (`separar_secoes_resumo`) é tolerante a formato inesperado (cai pro
  texto inteiro como 1 parágrafo se os marcadores não aparecerem), mas
  o ideal (3-5 parágrafos + LEITURA DE MERCADO omitida quando não há
  base) só se confirma com uma resposta real da API em produção.
- **Cache antigo invalidado, não migrado**: resumos já gerados no
  formato antigo (4 campos fixos) nunca mais são lidos (bump de versão
  em `ia_cache.chave_news`) — primeira visita a cada grupo depois do
  deploy reprocessa 1x (custo normal de cache miss, não um bug), mas
  isso significa que todo grupo popular vai gerar 1 chamada de IA extra
  na primeira hora após o deploy. Sem problema de verba (free tier
  Groq), só registrado pra não ser confundido com um bug de cache se
  alguém notar mais chamadas que o normal logo após o deploy.
- **Cobertura de teste do formato parcial com imagem presente+inválida
  simultaneamente** (ex: trafilatura retorna og:image mas o link está
  quebrado) não foi testada separadamente — o fallback de `<img
  onerror>` cobre isso no browser, mas não há teste automatizado
  Python específico pra esse caso exato (já era assim antes desta
  sessão, comportamento do HTML/browser, não da lógica Python).

## FASE 7 (2026-10-09) — pendências da SAÚDE DOS DADOS / piloto EUA / X

Ver PROGRESSO.md FASE 7 pra auditoria completa + matriz de
classificação de cada coletor. Itens deliberadamente não resolvidos
nesta sessão (tempo/escopo), registrados aqui pra não serem
reinventados do zero:

- ~~**SAÚDE DOS DADOS — MACRO com 2 fontes numa linha só**~~ — **corrigido
  ainda nesta sessão** (depois do registro inicial): BCB (SGS,
  IPCA/Selic/CDI) e ANBIMA (ETTJ/curva pré) agora são 2 linhas
  separadas (`"MACRO (BCB)"`/`"MACRO (ANBIMA)"`) na tabela
  `coletores_status` — não compartilham mais status.
- **SAÚDE DOS DADOS — cobertura parcial dos entry points**: só o
  agregador principal de cada coletor foi instrumentado
  (`obter_top_mercado_tudo` em NEWS, `_baixar_lote` em MERCADO,
  `obter_ipca`/`obter_curva_pre` em MACRO, `_ipe_ano` em CVM). Pontos
  mais granulares (ex: `data/news.py:obter_noticias` por ticker
  individual) continuam sem registro de tentativa própria.
- **FASE 3 (EUA) — timezone multi-mercado não implementado**:
  `America/Sao_Paulo` está hardcoded em ~10 módulos (news/cvm/eventos/
  macro/research/app.py) sem diferenciar `America/New_York` pra
  NASDAQ/NYSE. `config.FUSO_POR_MERCADO` já existe (mapa mercado->fuso)
  mas nenhum caller usa ainda — qualquer horário de notícia/evento
  exibido pra NVDA/AAPL/MSFT hoje aparece convertido pro fuso de
  Brasília, não pro fuso real do mercado americano.
- **FASE 3 — status de pregão aberto/fechado** (barra de status,
  `app.py`) continua só B3 — não diferencia horário de pregão
  NASDAQ/NYSE.
- **FASE 3 — fundamentos/notícias/CVM/calendário pra ativos EUA**: só
  cotação (preço/variação/beta/indicadores básicos via
  `yf.Ticker().info`) funciona hoje pro grupo-piloto. CVM é 100%
  Brasil (dataset oficial `dados.cvm.gov.br`, sem equivalente SEC
  EDGAR implementado) — documentos oficiais/calendário de resultados
  NÃO existem pra NVDA/AAPL/MSFT. Notícias (Google News) deveriam
  funcionar (agnóstico de mercado, já lida com nome de empresa
  estrangeira via `TICKER_ALIASES` de BDR) mas não foi testado
  especificamente pro grupo-piloto nesta sessão.
- **FASE 3 — comparativo da watchlist (EQUITY)** ainda não diferencia
  BRL/USD lado a lado - se a watchlist tiver um ticker BR e um US
  juntos, o painel comparativo pode mostrar os dois sem indicar a
  moeda de cada um (`formatar_valor_mercado` já aceita `moeda=`, mas
  nenhum caller do comparativo passa isso ainda).
- **FASE 4 (X)** — `data/x_signals.py` isolado/desligado, pronto pra
  integração futura. Decisão de custo (ver PROGRESSO.md FASE 7) fica
  com o Rodrigo; não reabrir sem aprovação explícita de orçamento/
  credencial nova.
- **Confirmação em produção real** de todas as instrumentações desta
  sessão (SAÚDE DOS DADOS) — não verificável deste sandbox (sem acesso
  a Supabase/rede de produção reais). A tabela `coletores_status` só
  passa a ter dado depois que alguém abrir as abas correspondentes em
  `pregao.streamlit.app` após o deploy.

## Research (Genial) — "Swing trade" nunca aparece na watchlist em produção
(investigado 2026-10-09, FASE 6 — **não corrigido**, falta decisão de escopo)

Mesma causa raiz do bug corrigido nesta sessão pra "recomendação"/Research
Radar (ver CHANGELOG.md 2026-10-09): em produção, `obter_swing_trade()` só
tem leitura AO VIVO da Genial, desligada por `tentar_coleta_automatica=
False`. A diferença é que recomendação/preço-alvo JÁ tinham uma tabela de
histórico persistido (`research_recomendacoes_historico`, alimentada por
`coletor_local.py:coletar_snapshot_genial`) que a UI simplesmente não
sabia ler — bug corrigido agora. Swing trade **nunca foi persistido em
tabela alguma** — não existe hoje nenhum dado salvo pra servir de
fallback. Pra corrigir de verdade precisa de: (1) uma função de coleta
análoga a `coletar_snapshot_genial` (ex: `coletar_snapshot_swing_trade`,
persistindo ticker/empresa/recomendação/status/data/link — schema novo,
porque swing trade tem campos que `research_itens` não tem, como
`status` "em aberto"/encerrado), (2) uma tabela nova ou coluna(s) extra
em uma existente, (3) chamada no `coletor_local.py`, (4) leitura
equivalente a `ultimo_snapshot` em `ui/research_tab.py`. Não implementado
nesta sessão por ser mudança de schema (tabela nova), fora do escopo de
"correção pequena e verificável" pedido pra esta rodada — fica registrado
pra uma próxima sessão dedicada, se o Rodrigo confirmar que quer esse
dado também disponível em produção (sem ele, swing trade continua
visível só pra quem abre o app localmente, onde a coleta ao vivo da
Genial funciona).

## Research (Genial Lives) — "última coleta" ficou parada em 08/10 21:13
(investigado 2026-10-09, FASE 6 — **sem bug de código confirmado**, falta acesso aos Logs do Cloud)

Auditoria completa do pipeline (`data/research/genial_lives.py` — feed
RSS do canal, identificação de programa por título, `store.salvar_itens`
upsert/dedup por link) não encontrou nenhuma falha de parsing/dedup que
impedisse `coletado_em` de avançar: toda vez que `obter_relatorios()`
retorna pelo menos 1 item, `salvar_itens` atualiza `coletado_em` de TODOS
os itens enviados (upsert, não é condicional a mudança de conteúdo).
Causa mais provável, mas **não verificável sem acesso real aos Logs do
Streamlit Cloud** (a rede deste ambiente de execução bloqueia até o feed
público do YouTube — erro 403 do proxy do próprio sandbox, não da
Genial/YouTube — então não dá pra testar reachability real a partir
daqui): coleta de casas com `tentar_coleta_automatica=True` (inclui
Genial Lives) só roda como efeito colateral de alguém abrir a aba
RESEARCH (`coletar_pendentes` dentro de `ui/research_tab.py:
render_research`) — não é um cron de verdade. Streamlit Community Cloud
hiberna o app sem visitas recentes; "última coleta" parada pode ser
simplesmente "ninguém abriu a aba RESEARCH desde então", não uma falha.
**Pendência concreta pro Rodrigo**: checar os Logs do app em
`share.streamlit.io` (ou painel do Cloud) por linhas
`[research] coleta Genial (Lives): FALHOU` no período - se existirem,
é uma falha real de rede/feed (investigar bloqueio de IP do Cloud,
mesma classe de problema já confirmada pra Genial/XP); se não existirem
tentativas nenhumas, é só falta de visita à aba.

## Research (Genial) — ticker do LINK de relatório pode ser case-sensitive
(investigado 2026-10-08, FASE 5 — **não corrigido**, falta confirmação)

`data/research/genial.py:_TICKER_NO_LINK` (regex que extrai o ticker do
LINK de um relatório de ações/estratégia/macro, usado por
`_ticker_do_link` — diferente do bug já corrigido em
`obter_recomendacoes`/`_ticker_da_url_recomendacao`, que era sobre URL
com barra final) é `r"^/acoes/([A-Z0-9]{4,6})(?:/|$)"` — case-sensitive,
só casa maiúsculas. Se a Genial usar minúsculas no slug da URL em algum
relatório real (ex: `/acoes/petr4/...`), a atribuição de ticker se
perde silenciosamente pra TODO relatório daquele tipo, mesma classe de
bug do que já foi corrigido. Não dá pra confirmar o formato real sem
acesso de rede ao domínio (bloqueado neste sandbox) nem amostra de URL
salva no repo — não arriscado um fix especulativo. **Pendência
concreta pro Rodrigo**: abrir um relatório de ações qualquer em
`pregao.streamlit.app` (aba RESEARCH, casa Genial) e conferir se a URL
mostrada tem o ticker em maiúscula ou minúscula. Se for minúscula, o
fix é trivial e seguro — mesmo padrão de `.upper()` já usado em
`data/research/xp.py:_tickers_do_class_list`.

## Auditoria 2026-09-30 — itens revistos (releitura do código real)

Vários itens abaixo listados em sessões anteriores já tinham sido
corrigidos como efeito colateral de outras tarefas, mas o BACKLOG não
tinha sido limpo. Confirmado lendo o código atual (não só memória):

- **Beta** já é calculado localmente desde a correção registrada em
  MANUAL.md (`data/prices.py:_calcular_beta`, cov/var 2 anos vs
  `^BVSP`) — item antigo removido daqui.
- **MM20 na mesma cor da linha de preço (modo LINHA)**: já corrigido —
  `app.py` usa `tema["neutro"]` pra MM20 em LINHA/AREA e só
  `tema["destaque"]` em CANDLE (onde não colide, preço vira barra sem
  cor própria). Candle confirmado com `increasing_line_color`/
  `decreasing_line_color` corretos.
- **Barra de ferramentas do Plotly em MACRO**: já está com
  `config={"displayModeBar": False}` em todos os `st.plotly_chart` de
  `ui/macro_tab.py` — item resolvido.
- **Eixo X do IPCA em mês/ano**: já implementado
  (`ui/macro_tab.py:_eixo_x_mes_ano`, ex: "ago/2026").
- **Cabeçalho de tabela cortado (PREÇOS/RESUMO) + espaço vazio
  embaixo** e **título "INDICADORES" sumindo + scrollbar interna**:
  mesma causa raiz provável — a regra
  `[data-testid="stMarkdown"]:has(table) { overflow-x: auto;
  overflow-y: hidden; }` em `style.css` foi adicionada depois (o
  comentário no próprio CSS já cita "RESUMO e INDICADORES" como motivo)
  especificamente pra evitar que `overflow-x:auto` sozinho virasse scroll
  vertical indevido — mecanismo idêntico ao que cortava o cabeçalho da
  PREÇOS, já que ambas são tabela dentro de `st.markdown`. **Ainda
  pendente confirmação visual** (sem acesso à extensão do Chrome nesta
  sessão) — se reaparecer, é outra causa, não essa.

## Visual / layout
- E-mail do usuário sumiu do header (só aparece o botão SAIR). Causa
  mais provável (2026-09-30): o botão SAIR usava `width="stretch"` e
  texto que não quebra linha, brigando por espaço com o chip de e-mail
  dentro de uma coluna estreita — a disputa deixava quase nada pro
  `pregao-user-chip`, que então cortava quase tudo via ellipsis
  (parecendo "sumido"). **Correção aplicada**: `col_user` ganhou mais
  largura relativa (1.35→1.7, `col_busca` cedeu um pouco), proporção
  interna foi de `[3,1]` pra `[4,1]`, e o botão SAIR perdeu o
  `width="stretch"` (fica do tamanho do próprio texto). Pendente
  confirmação visual real (print/inspeção) — se persistir, próximo
  passo é investigar `.block-container{overflow-x:clip}` recortando o
  header fixo quando a sidebar está expandida (ver comentário em
  `style.css` sobre `.block-container`).
- Limpeza de nome de empresa parece remover acentos em produção (ex:
  "Ginástica e Dança" → "Ginástica e Danca"). Testado localmente
  (`obter_nome_yf('SMFT3')`) e o resultado veio com acento correto —
  `longName` do yfinance e a função de limpeza não mexem em
  maiúscula/minúscula nem em encoding, só cortam o sufixo jurídico do
  final. Suspeita: diferença de locale/encoding entre o ambiente local e
  o container do Streamlit Cloud, não bug na lógica em si — investigar
  direto em produção (não reproduz local).

## Indicadores
- Dividend yield: investigado em 2026-09-30 — não há evidência de bug.
  `Ticker.dividends` do yfinance registra cada evento de distribuição
  (dividendo OU JCP) como uma linha própria por data-ex; o cálculo atual
  (`data/prices.py:_dividend_yield_12m`) só soma essas linhas na janela
  de 12 meses, sem nenhum ponto óbvio de dupla contagem. Não dá pra
  confirmar com 100% de certeza sem comparar contra a relação oficial de
  proventos de um ticker específico (CVM não traz valor pago, só
  metadado do documento) — manter como item de baixa prioridade, não
  reabrir sem um caso concreto de DY visivelmente inflado.

## Macro
- Curva pré (ETTJ ANBIMA): a fonte só guarda ~5-6 pregões de histórico
  rolante — comparação de "1 mês atrás" não funciona (testado, confirma
  o limite). Para viabilizar essa comparação, salvar um snapshot diário
  da curva no Supabase via GitHub Actions (Fase 7 do roadmap original,
  coleta automática). Já degrada graciosamente (aviso explícito na UI
  quando a comparação de 1 mês não está disponível).
- Curva pré: legenda (Hoje / 1 semana atrás / 1 mês atrás) — investigado
  a fundo em 2026-10-08 (rotina autônoma, parte 1/4) com inspeção visual
  real (Playwright/Chromium, 390/768/1280px, reproduzindo exatamente o
  layout de `ui/macro_tab.py:_painel_curva_pre`/`_layout_grafico_escuro`
  com dados sintéticos plausíveis, já que a rede deste sandbox bloqueia
  a ANBIMA): **não reproduziu** sobreposição/corte em nenhum dos 3
  breakpoints — a legenda horizontal com os 3 rótulos quebra pra 2-3
  linhas em telas estreitas (390px) e o Plotly encolhe a área do
  gráfico pra caber tudo dentro da `height=380` declarada, sem
  clipping. Hipótese não descartada: o sintoma original pode ter vindo
  do wrapper `overflow:auto` dos painéis arrastáveis/redimensionáveis
  (`ui/workspace.py`, workspace modular) quando o usuário encolhe o
  painel manualmente abaixo da altura que o gráfico precisa — isso não
  é testável sem sessão Streamlit autenticada real (login Google) nem
  reproduzido aqui. Rebaixado: reabrir só se o Rodrigo confirmar o
  sintoma ao vivo em produção, com os passos exatos (tamanho do painel,
  breakpoint, tema).

## Research
- BTG Research: API pública em
  `https://content.btgpactual.com/api/research/public-router/<servico>/api/<servico>/public/v1/...`
  (ex. que funciona: `.../media-research/.../medias/lives?status=LIVE&pageNumber=1&pageSize=8`).
  A lista de relatórios (requisição "ALL?pageNumber=1&pageSize=9&channel=...")
  deu 404 na home e não apareceu em /acoes/ultimos-relatorios; pode ser
  restrita a clientes. Próximo passo: procurar "public-router" nos bundles
  JS para mapear as rotas, ou testar a área aberta content.btgpactual.us.
- XP Investimentos: implementada (`data/research/xp.py`), API pública do
  WordPress (`conteudos.xpi.com.br/wp-json/wp/v2/{rel-acoes-fund,
  rel-artigo-aloc,rel-acoes-tec}`). IP deste sandbox de dev é bloqueado
  pelo CDN da XP (confirmado com `requests` e com `curl_cffi
  impersonate="chrome"` - mesmo Reference ID de bloqueio, então é IP/geo,
  não fingerprint de TLS); coletor testado só com dados mockados aqui,
  `ativa_por_padrao=False` até confirmar em produção/local.
- Reconhecimento rápido das 6 casas restantes (2026-09-23, sem
  implementar nada ainda):
  - **Itaú BBA** (`itau.com.br/itaubba-pt/analises-economicas`) e
    **Santander** (`santandercorretora.com.br`): domínio bloqueado (403)
    já na raiz, deste sandbox - não deu pra investigar mais.
  - **BB Investimentos** (`investalk.bb.com.br/relatorios-e-analises`):
    site acessível, mas `/wp-json/` e `/feed/` retornam 403 - API
    deliberadamente fechada.
  - **Safra** (`oespecialista.safra.com.br`): é WordPress de verdade
    (`/wp-json/` existe), mas a REST API está bloqueada por plugin
    ("DRA: Only authenticated users can access the REST API").
  - **Ágora/Bradesco** (`insights.agorainvestimentos.com.br/conteudo`) e
    **Inter** (`interinvest.inter.co`): site acessível, mas sem
    WordPress/JSON óbvio no HTML de superfície (Inter parece SPA React -
    `data-react-helmet`). Precisariam do mesmo trabalho de arqueologia de
    bundle JS feito pro BTG pra confirmar se têm API interna usável - não
    investigado a fundo ainda.

## Fases futuras
- Morning Call da Genial: transcrição + resumo automático. Fase futura,
  ainda não desenhada (fonte, formato do resumo, frequência de
  atualização etc. — definir quando chegar a vez).

## Auditoria 2026-10-08 (FASE 8) — itens revistos, classificados

Continuação controlada da rodada de melhoria contínua pós-FASE 3. A
FASE 8 fechou a maior parte dos itens que a auditoria anterior tinha
deixado em aberto (N+1 de cotação na sidebar/EQUITY, coluna `modelo`
do cache de IA, testes de dedup de NEWS e de `_bloco_contexto_research`
— ver CHANGELOG.md/PROGRESSO.md pra detalhe completo). Os itens abaixo
foram investigados nesta rodada e **deliberadamente não alterados**,
com prioridade/impacto/esforço:

- **Link de navegação CVM → CALENDÁRIO/RESEARCH**
  PRIORIDADE: BAIXA · IMPACTO: BAIXO · ESFORÇO: MÉDIO (arquitetural, não "pequeno")
  Investigado a fundo nesta rodada: app.py só permite escrever em
  `st.session_state["secao_ativa"]` (troca de aba) **antes** do widget
  de navegação (`st.segmented_control`) ser instanciado no mesmo rerun
  — é assim que a busca global (`_ir_com_ticker`) já faz, documentado
  explicitamente no próprio código ("descoberto na prática:
  StreamlitWidgetAlreadyInstantiatedError"). A aba CVM renderiza bem
  depois desse ponto no fluxo do script — um botão "ver no CALENDÁRIO"
  dentro de `ui/cvm_tab.py` bateria direto nesse erro. Não é "pequeno e
  consistente com a UI existente" (critério explícito pra essa tarefa):
  precisaria mover a ordem de renderização ou criar um mecanismo de
  navegação diferido (ex: redirecionar só no próximo rerun) — isso é
  mudança de arquitetura de navegação, fora do escopo autorizado.
- **`obter_indicadores(t)` no comparativo da EQUITY continua por ticker**
  PRIORIDADE: BAIXA · IMPACTO: BAIXO · ESFORÇO: ALTO (sem solução segura hoje)
  A cotação do comparativo da EQUITY e da sidebar JÁ foi migrada pra
  `obter_cotacoes_lote` nesta rodada (FASE 8). `obter_indicadores`
  (P/L, P/VP, DY — vem de `yf.Ticker().info`) continua 1x por ticker
  porque o yfinance **não oferece** esse dado em lote (só
  `fast_info`/`download` de preço são batcháveis) — não é uma omissão,
  é um limite real da fonte. Impacto prático baixo: já é cacheado 12h
  por ticker (`data/prices.py:_TTL_INDICADORES`), bem acima do
  `run_every` do fragment, então o custo de rede só aparece no 1º load
  ou na expiração do cache, não a cada rerun.
- **`_layout_grafico_escuro` (template Plotly dark) duplicado** em
  `app.py`, `ui/mercado_tab.py`, `ui/macro_tab.py` e inline em
  `ui/visao_geral.py`.
  PRIORIDADE: BAIXA · IMPACTO: BAIXO (manutenção, não bug) · ESFORÇO: MÉDIO
  Candidato a função única em `ui/graficos.py` (já é o módulo
  compartilhado de infra de gráfico) — refactor transversal a 4
  arquivos sem bug ativo por trás; critério explícito desta rodada é só
  refatorar com "benefício concreto de manutenção e baixo risco", e
  tocar 4 arquivos de UI pra um ganho puramente estético não atinge essa
  barra ainda.
- **Chave de `session_state` dos seletores DIA/SEMANA/MÊS compartilhada
  entre MERCADO e VISÃO GERAL** (`ui/mercado_tab.py:_escolha_estavel_mercado`,
  chave `"mercado_altas_baixas"`/`"mercado_setorial"` etc.)
  PRIORIDADE: BAIXA · IMPACTO: NENHUM CONFIRMADO (UX, não dado errado) · ESFORÇO: BAIXO (se decidido separar)
  **Confirmado empiricamente nesta rodada** (não é só suspeita): setar
  a chave pelo lado de MERCADO e ler pelo lado de VISÃO GERAL devolve o
  valor persistido — as duas abas de fato compartilham a escolha de
  janela, porque `ui/visao_geral.py` reaproveita as MESMAS funções
  (`_painel_altas_baixas`/`_painel_setorial`) de `ui/mercado_tab.py`,
  mesma chave de widget. Importante: isso nunca mostra dado ERRADO (as
  duas abas sempre renderizam a janela selecionada corretamente, só
  compartilham QUAL janela está selecionada) — não é bug de
  corretude, é uma escolha de UX (persistência entre abas) que pode ser
  intencional ou não. Não alterado — decisão de produto do Rodrigo:
  manter compartilhado (atual) ou separar por `aba_id`.
- **`_cache_eventos()` (último-dado-válido do CALENDÁRIO,
  `data/eventos.py`) nunca é podado**
  PRIORIDADE: BAIXA · IMPACTO: BAIXO (auditado nesta rodada — seguro) · ESFORÇO: BAIXO
  Reauditado nesta rodada: cresce ~1 entrada por `(ticker, período)` já
  calculado, nunca removida — mas cada ticker só acumula ~4
  entradas/ano (1 por trimestre), é um `st.cache_resource` de processo
  único (terminal pessoal, não multi-tenant), e nenhuma entrada antiga
  é lida de novo (lookups são sempre pelo período ATUAL). Memória
  desperdiçada é desprezível mesmo depois de anos de uso — confirmado
  seguro, não alterado "só por estética" (critério explícito desta
  rodada).
- **EQUITY não é "Company 360"** (contexto de Research/preço-alvo
  integrado à ficha do ativo)
  PRIORIDADE: MÉDIA (iniciativa de produto) · IMPACTO: ALTO (se feito bem) · ESFORÇO: ALTO
  Pendência já conhecida de ciclos anteriores, reconfirmada nesta
  auditoria; decisão de produto/design grande demais pra uma rodada de
  correção controlada — mantida explicitamente como iniciativa futura
  de maior escopo, não uma tarefa pequena a encaixar.
- **Browser real indisponível neste ambiente de execução** (limitação
  de infraestrutura, não do produto) — Playwright/Chromium não estão
  configurados contra o app Streamlit completo aqui; toda validação
  visual usa `compileall` + suíte determinística + harness `AppTest`
  (prova "renderiza sem exceção com o dado certo", não "fica bonito na
  tela"). Confirmação visual real fica sempre pendente pro Rodrigo em
  `pregao.streamlit.app`.
