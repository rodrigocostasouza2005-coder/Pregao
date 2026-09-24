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
  atual e seguinte. Fonte: Olinda/BC (`olinda.bcb.gov.br`).
- **CURVA PRÉ (ETTJ)**: estrutura a termo da taxa de juros prefixada.
  Fonte: ANBIMA (scraping de uma página pública, não é API oficial —
  mais frágil que as fontes do BC).

**Limitações conhecidas:** curva ANBIMA só guarda ~5-6 pregões de
histórico rolante (comparações "1 mês atrás" não funcionam de verdade —
ver BACKLOG.md). Legenda da curva pode sobrepor em telas estreitas.

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

Em desenvolvimento por outra sessão de trabalho — ver `data/cvm.py`,
`ui/cvm_tab.py`. Não documentado aqui ainda (evitar descrever algo que
pode mudar antes de terminar).
