# BACKLOG — PREGÃO

Pendências conhecidas, para resolver depois (ajustes visuais adiados
enquanto avançamos nas próximas fases).

## NEWS — feed editorial: card com selo/ticker sobrepondo o item seguinte
(investigado 2026-10-08, rotina autônoma parte 4/4 — **não corrigido**,
evidência insuficiente pra decidir a causa real)

Continuando a auditoria visual pendente (Playwright, 390/768/1280px) que
as partes 1-3/4 já tinham feito pra MERCADO/CVM, rodei a mesma técnica em
`render_news` (feed editorial da aba NOTÍCIAS, `ui/news_tab.py`) com dados
sintéticos plausíveis e o `style.css`/CSS próprio reais (harness isolado,
sem login, mesma técnica já validada). **Achado visual real** (não
hipótese — confirmado em screenshot com zoom pixel a pixel, replicável
após reload completo da página): a linha de metadados de cada notícia
(`_meta_noticia_html` — selo · veículo · hora · ticker(s) · nº de fontes
· link "↗ abrir") aparece cortada/sobreposta pelo divisor do item
seguinte quando o texto quebra pra 2 linhas — o conteúdo real (confirmado
via `innerText`/`getBoundingClientRect` do DOM) está completo e com cor
correta, mas visualmente alguns pixels do fim da 2ª linha (ex: badge do
ticker, link "↗ abrir") ficam cobertos.

**Causa raiz investigada, não fechada com confiança**: medindo a altura
do elemento `stElementContainer` do Streamlit (que envolve o
`st.markdown` dessa linha) contra a altura real do conteúdo
(`getBoundingClientRect`), a primeira é sistematicamente MENOR que a
segunda (ex: container 27.75px vs conteúdo 40.9px) — sobra ~13px de
conteúdo "vazando" por baixo do container, exatamente onde o próximo
elemento (divisor) começa, causando a sobreposição visual. Isso persiste
depois de reload completo (não é uma animação/transição que só não deu
tempo de terminar) e uma tentativa de forçar `height:auto !important`
via `:has()` no container, bem como forçar o texto a NUNCA quebrar
(`white-space:nowrap + ellipsis` na própria `.news-item-meta`), **não
resolveu** — pelo contrário, a segunda tentativa (testada com reinício
limpo do servidor, não só injeção JS tardia) piorou visualmente (quase
todo o conteúdo da linha ficou invisível, cortado num container ainda
menor) e foi revertida imediatamente (`git diff` confirmado limpo antes
de seguir). Ou seja: o mecanismo real por trás da altura "travada" do
container não é simplesmente "o texto quebra em 2 linhas" — pode ser
algo mais profundo do próprio Streamlit (cache de altura via
ResizeObserver medido num momento diferente do layout final, específico
desta versão 1.64.0) ou um artefato específico deste harness isolado
(sandbox sem internet, sem a fonte real "IBM Plex Mono" carregada via
Google Fonts — só fallback monospace genérico, métricas de caractere
diferentes das de produção).

**Por que não virou um fix nesta sessão**: qualquer mudança de CSS
tentada pra "consertar" sem entender o mecanismo real arriscava piorar
(como já aconteceu uma vez, revertida). Investigar mais a fundo exigiria
acesso ao bundle JS do Streamlit (fora do escopo de uma correção
cirúrgica) ou confirmação em produção real (Google Fonts carregando,
Streamlit Cloud, navegador real) pra saber se o sintoma reproduz do
mesmo jeito — nenhuma das duas era viável nesta janela de execução.

**Pendência concreta pra próxima sessão/pro Rodrigo**: confirmar ao vivo
em `pregao.streamlit.app` (NEWS, watchlist com 2+ tickers, tela estreita
ou tablet) se algum card de notícia mostra o selo/ticker/link "↗ abrir"
cortado ou sobreposto pela linha divisória do próximo item. Se confirmado
em produção real (não só neste harness), o próximo passo é testar a
mesma mudança isolando UMA variável por vez (ex: só reduzir o número de
elementos inline distintos na mesma `st.markdown`, ou forçar um
`st.rerun()` extra após o primeiro mount pra dar ao Streamlit uma segunda
chance de remedir a altura) em vez de mexer no CSS de wrap, que já
provou piorar as coisas. Esta aba já usa um padrão mais simples (uma
linha só, sem wrap, com ellipsis) em `_linha_noticia`/`_renderizar_lista`
("wire", reusado por TOP MERCADO e pelo bloco compacto de NEWS da aba
EQUITY) — **esse estilo NÃO tem este problema** (confirmado lendo o
código: cada parte vive na sua própria coluna de largura fixa, com
`white-space:nowrap` + `text-overflow:ellipsis`, nunca quebra linha) —
é específico do estilo "editorial" (cards, Fase 3) usado só no feed
principal de `render_news`.

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
