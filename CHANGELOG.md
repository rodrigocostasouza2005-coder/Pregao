# CHANGELOG — PREGÃO

Entradas curtas por commit, em português simples: o que mudou e por quê.
Mais recente primeiro.

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
