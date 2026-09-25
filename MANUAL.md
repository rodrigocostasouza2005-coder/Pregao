# MANUAL — PREGÃO

O que cada aba/painel faz, de onde vêm os dados e as limitações
conhecidas. Atualizado a cada tarefa relevante (ver PROGRESSO.md pro
histórico de execução e CHANGELOG.md pro histórico de mudanças).

## Navegação

O menu principal é um seletor (`st.segmented_control`) que renderiza **só
a seção ativa** — diferente de `st.tabs()`, que roda o código de todas as
abas em toda execução do script. Isso importa pra quem for mexer no
código: um erro numa seção não derruba as outras, e cada seção só busca
dados quando está de fato selecionada.

## EQUITY

Cotação, indicadores e gráfico de UM ticker da sua watchlist (escolhido
por um seletor no topo da aba).

- **PREÇOS**: preço atual, variação do dia, máx/mín do dia, volume,
  máx/mín 52 semanas. Fonte: `yfinance` (`fast_info`), atualiza a cada
  `atualizacao_intervalo` segundos (configurável em CONFIG). Atraso de
  ~15min (fonte gratuita do Yahoo Finance).
- **INDICADORES**: valor de mercado, P/L, P/VP, dividend yield (12
  meses, calculado a partir do histórico de dividendos — não usa o
  campo `dividendYield` do yfinance, que às vezes diverge do que foi
  pago de verdade), e **BETA (2A)**: calculado localmente
  (cov/var de retornos semanais dos últimos 2 anos contra o Ibovespa
  `^BVSP`) — o campo `beta` do próprio yfinance não é confiável pra
  ações da B3.
- **FUNDAMENTOS** (segunda tabela do painel INDICADORES): ROE, margem
  líquida, margem operacional, margem EBITDA e dívida líquida (com
  múltiplo dívida líquida/EBITDA, quando o EBITDA está disponível).
  Fonte: `tk.info` do yfinance. Bancos/seguradoras não têm margem EBITDA
  (sem conceito de EBITDA tradicional) — aparece como "—", não "0,00%".
  **ROIC não está disponível**: o yfinance não tem esse campo pronto, e
  calculá-lo na mão exigiria estimar capital investido e taxa efetiva de
  imposto a partir de outros relatórios — decidido não aproximar.
- **GRÁFICO**: candlestick, linha ou área (escolha em CONFIG), com
  médias móveis 20/50/200 (cada uma opcional) e opção de comparar com o
  Ibovespa (base 100). Períodos diários (1M a 5A) e intradiários (1D=5min,
  1S=30min).
- **NOTÍCIAS** (painel no fim da aba): as notícias mais recentes desse
  ticker específico (`render_news_ticker`), mesmo motor de dados da aba
  NEWS.

**Limitações conhecidas:** yfinance é gratuito e não garante SLA — pode
falhar ou ficar lento, principalmente em IP de datacenter (Streamlit
Cloud). Ver BACKLOG.md pra itens visuais pendentes.

## MACRO

Indicadores macroeconômicos brasileiros.

- **IPCA**: mensal e acumulado 12 meses, com faixa da meta de inflação
  (Banco Central/CMN). Fonte: SGS do Banco Central (`api.bcb.gov.br`).
- **SELIC/CDI**: taxa meta e CDI, histórico configurável. Fonte: SGS.
- **FOCUS**: expectativas de mercado (mediana) pro IPCA e Selic, ano
  atual e os dois seguintes. Fonte: Olinda/BC (`olinda.bcb.gov.br`).
- **CURVA PRÉ (ETTJ)**: estrutura a termo da taxa de juros prefixada.
  Fonte: ANBIMA (scraping de uma página pública, não é API oficial —
  mais frágil que as fontes do BC).
- **CENÁRIO GLOBAL**: ouro, petróleo (Brent/WTI), minério de ferro
  (futuro SGX TSI CFR China), Treasuries 10 anos e VIX — preço e
  variação do dia. Fonte: Yahoo Finance (yfinance), mesmo mecanismo de
  lote usado pelos mercados globais da aba MERCADO.

**Limitações conhecidas:** curva ANBIMA só guarda ~5-6 pregões de
histórico rolante (comparações "1 mês atrás" não funcionam de verdade —
ver BACKLOG.md). Legenda da curva pode sobrepor em telas estreitas.
Agenda econômica (próxima reunião do Copom, calendário de indicadores)
não está implementada: exigiria uma fonte de calendário confiável que o
projeto ainda não integra — não inventamos datas.

## RESEARCH

Relatórios de casas de análise, agregados e persistidos no Supabase
(tabela `research_itens`) — a aba sempre lê do banco primeiro (rápido) e
só depois tenta coletar o que estiver desatualizado (>30min desde a
última coleta bem-sucedida).

- **Genial Analisa**: JSON embutido (`__NEXT_DATA__`) na home. **Hoje
  bloqueada tanto no sandbox de dev quanto no Streamlit Cloud**
  ("HTTP/2 stream reset by server" — o coletor tenta várias combinações
  de TLS/HTTP antes de desistir). Ver "última coleta" no topo da aba.
- **XP Investimentos**: API pública do WordPress
  (`conteudos.xpi.com.br/wp-json`). Campos confirmados manualmente pelo
  Rodrigo; **também bloqueada no Cloud** (403). Resumo nunca passa do
  trecho aberto do relatório — paywall nunca é contornado.
- **BTG Research**: mapeada mas indisponível (bot-detection Akamai,
  precisaria de navegador real).
- Resumo por IA (Groq) só automático pra relatórios da watchlist; os
  demais, sob demanda (botão "RESUMIR"), gravado no Supabase (nunca
  regenerado pro mesmo link).
- Retenção: itens com mais de 5 dias (data de publicação OU última
  coleta) são apagados do Supabase automaticamente.
- **`coletor_local.py`**: script pra rodar a coleta de fora do Cloud
  (Agendador de Tarefas do Windows), quando as fontes estão bloqueadas
  lá mas funcionam da sua rede. Ver PROGRESSO.md pro passo a passo.

**Limitações conhecidas:** Genial e XP bloqueadas em produção hoje (ver
"última coleta" na aba pra saber se os dados estão frescos). Itaú BBA,
Santander, BB Investimentos, Safra, Ágora, Inter ainda não têm coletor
(ver BACKLOG.md pro reconhecimento feito em cada uma).

## NEWS

Notícias por empresa da sua watchlist, com selo de confiabilidade
calculado por regras (nunca IA) — fonte de dados, não verificação
factual.

- Fonte: RSS de busca do Google News (`news.google.com/rss/search`),
  filtrado por ticker/nome da empresa aparecendo no título (senão é
  ruído da busca, o item nem entra no resultado).
- Notícias do mesmo fato, vindas de tickers diferentes da watchlist, são
  fundidas num item só com todos os tickers na linha.
- Páginas de cobertura contínua ("Ao Vivo"/"Tempo Real") saem do feed
  por ticker (não é matéria específica sobre a empresa).
- Retenção: só mostra notícias dos últimos 5 dias.
- Resumo por IA (Groq) só ao clicar na manchete (nunca automático na
  lista) — baixa a matéria de verdade (via link decodificado do Google
  News + extração com `trafilatura`), nunca copia texto literal.

**Limitações conhecidas:** o resumo depende de conseguir baixar a
matéria de verdade — sites com paywall forte ou que bloqueiem o IP do
Cloud mostram "resumo indisponível" com o motivo específico. Ver
DIAGNÓSTICO DE FONTES (aba CONFIG, admin) pra testar isso em produção.

## TOP MERCADO

As notícias "mais importantes" do momento (Brasil, Internacional ou os
dois juntos), por **estimativa** de relevância (não existe fonte pública
de "mais lida") — nº de fontes cobrindo o fato, recência, veículos
confiáveis e temas de mercado no título. Filtro por setor.

- Fontes: seção de negócios do Google News (BR e EUA) + busca por temas
  de mercado (Ibovespa, Copom, Selic, dólar, IPCA, fiscal, Fed,
  commodities) + feeds diretos (CNBC, MarketWatch, Yahoo Finance, na
  parte internacional). Busca paralelizada (`ThreadPoolExecutor`).
- Páginas "Ao Vivo"/"Tempo Real" ganham uma tag visível em vez de serem
  filtradas (aqui faz sentido mostrar, diferente do feed por ticker).
- Mesma retenção de 5 dias e mesmo resumo sob demanda do NEWS.

## MERCADO

Visão ampla do pregão (não é sobre um papel específico, ao contrário de
EQUITY): termômetro, altas/baixas, mais negociados, desempenho setorial,
mapa de calor e mercados globais.

- **Fonte de dados**: lote único via `yf.download` sobre uma lista curada
  de blue chips do Ibovespa (`config.IBOVESPA_COMPOSICAO`, ~60 papéis com
  setor) — **não é a composição oficial completa do índice** (~86 papéis,
  rebalanceada trimestralmente pela B3). Atualize esse dict conforme
  rebalanceamentos; é só um dicionário ticker→setor, não exige mexer em
  mais nada. Alguns papéis podem falhar no lote em determinados momentos
  (bloqueio/instabilidade do yfinance) — nesse caso saem do cálculo em
  vez de aparecer com dado errado (nunca inventa número).
- **Termômetro**: quantos papéis da lista estão em alta/baixa/estáveis.
- **Maiores altas/baixas** e **mais negociados**: por variação % e por
  volume financeiro estimado (preço × volume em ações) no dia.
- **Desempenho setorial**: variação média simples (não ponderada por
  valor de mercado) dos papéis de cada setor.
- **Mapa do mercado**: treemap (tamanho = volume financeiro, cor =
  variação % no dia).
- **Mercados globais**: S&P 500, Nasdaq, Dow Jones, FTSE 100, DAX, Nikkei
  225, Hang Seng, Xangai (`config.INDICES_GLOBAIS`).
- **Curva de juros (DI futuro)**: não duplicada aqui — já existe uma
  curva de juros prefixada real (ANBIMA ETTJ) na aba MACRO.
- **Agenda de Copom/resultados**: não implementada. Exigiria uma fonte de
  calendário confiável (datas de reunião do Copom, datas de divulgação de
  resultados por empresa) que o projeto ainda não integra — não dá pra
  inventar essas datas. Ver MELHORIAS FUTURAS em PROGRESSO.md.

## CONFIG

Preferências por usuário (tema, densidade, fonte, gráfico, abas
visíveis, casas de research ativas), salvas no Supabase
(`st.user.sub` como chave). Abas novas (ex: TOP MERCADO quando foi
lançada) são adicionadas automaticamente pra usuários existentes, sem
reaparecer o que foi escondido de propósito.

- **DIAGNÓSTICO DE FONTES** (só pros e-mails em
  `config.obter_emails_admin()`): testa, rodando de verdade no servidor,
  cada fonte de dados do app — útil pra saber o que funciona em produção
  sem depender do ambiente de desenvolvimento (que tem vários domínios
  bloqueados por WAF/CDN).
- **SISTEMA** (só admin, se existir — ver PROGRESSO.md se ainda não foi
  implementada): últimas entradas do CHANGELOG, status da fila de
  trabalho e este manual.

## CVM

Documentos oficiais (fato relevante, comunicado ao mercado, resultados,
proventos, calendário de eventos) das empresas da sua watchlist. Fonte:
dados abertos da CVM (`dados.cvm.gov.br`, dataset IPE) — atualização
diária/semanal da fonte, não é tempo real (para o texto oficial
imediato, consulte o RAD/ENET da própria CVM).

- **Destaques**: linha logo abaixo da descrição, calculada sobre todos
  os documentos (não filtrados) — fatos relevantes nos últimos 30 dias,
  ticker mais ativo no período e último documento recebido. Pulso rápido
  antes de filtrar/buscar.
- **Busca**: campo de texto acima dos filtros, procura em ticker/
  assunto/tipo/categoria original — combina com os filtros de ticker e
  tipo abaixo (ex: ticker=PETR4 + tipo=FATO RELEVANTE + busca
  "dividendos"). Tudo em memória sobre os documentos já coletados, não
  dispara nova consulta à CVM.
- **Filtros**: ticker (pills) e tipo de documento (pills) — os mesmos
  cinco tipos oficiais (FATO RELEVANTE, COMUNICADO, RESULTADOS,
  PROVENTOS, CALENDÁRIO).
- **Tabela**: DATA / TICKER / TIPO / DOCUMENTO-ASSUNTO, assunto ocupando
  a maior parte da largura, com ellipsis + tooltip pro título completo
  quando não cabe. Clique no assunto abre um card com resumo por IA
  (Groq, sob demanda, nunca automático) e link pro documento original.
- **Paginação**: 50 documentos por página, reseta pra página 1 quando
  filtro/busca muda.
- **Selo CONFIRMADA em NEWS**: quando uma notícia bate com um Fato
  Relevante/Comunicado da CVM do mesmo ticker (sobreposição de
  assunto ≥40%, até 2 dias de diferença), o card da notícia ganha esse
  selo e um link direto pro documento oficial.

**Limitações conhecidas:** cobre só as ~64 empresas de
`config.IBOVESPA_COMPOSICAO` presentes na sua watchlist (mapa
ticker→CNPJ vem do FCA da própria CVM); BDRs de empresa estrangeira
(MELI34 etc.) não têm registro direto na CVM brasileira, então não
aparecem aqui.
