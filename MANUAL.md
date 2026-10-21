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

**Busca global**: campo acima do menu, visível em qualquer aba — busca
por ticker ou nome. Três atalhos: **EQUITY ↗** (abre a cotação completa),
**NOTÍCIAS ↗** (abre NEWS já filtrado por esse ticker), **+ WATCHLIST**
(só adiciona, sem sair da aba atual). Os dois primeiros adicionam o
ticker à watchlist automaticamente se ele ainda não estiver lá (EQUITY e
NEWS só mostram dado de ticker rastreado).

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

- **Fonte de dados**: lote único via `yf.download` sobre a **composição
  oficial do Ibovespa**, direto da API pública da B3
  (`data/ibovespa.py:obter_composicao_oficial`, ~76 papéis, cache de
  24h). Setor de cada papel continua vindo de uma curadoria manual
  (`config.IBOVESPA_SETORES` — a B3 não classifica por setor nesse
  endpoint); ticker novo sem setor mapeado aparece em "Outros". Se a B3
  falhar, cai pro fallback estático (mesmo dict, lista curada de blue
  chips). Atualize `IBOVESPA_SETORES` conforme rebalanceamentos pra
  cobrir setor dos papéis novos; é só um dicionário ticker→setor, não
  exige mexer em mais nada. Alguns papéis podem falhar no lote em
  determinados momentos (bloqueio/instabilidade do yfinance) — nesse
  caso saem do cálculo em vez de aparecer com dado errado (nunca
  inventa número).
- **Termômetro**, **maiores altas/baixas** e **desempenho setorial**:
  cada um com seletor DIA/SEMANA/MÊS (efeito imediato, independente
  entre os três painéis — trocar um não afeta os outros). Semana/mês =
  7/30 dias corridos, mesma convenção já usada nos retornos da aba
  EQUITY. Papel sem histórico suficiente na janela (ex: IPO recente)
  fica de fora do cálculo daquela janela específica.
- **Mais negociados**: por volume financeiro estimado (preço × volume
  em ações) no dia — só dia, é sobre liquidez/atenção do momento, não
  retorno.
- **Desempenho setorial**: variação média simples (não ponderada por
  valor de mercado) dos papéis de cada setor, na janela escolhida.
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

- **LAYOUT — MACRO/MERCADO**: cada painel tem um "⚙" no canto — clique
  pra escolher a largura (1/4, 1/2, 3/4 ou FULL), com efeito imediato,
  ou esconder o painel. Painéis numa mesma linha com largura somando até
  100% ficam lado a lado. Pra reexibir um painel escondido: CONFIG →
  seção LAYOUT (único ajuste que precisa vir de lá — reordenar também
  fica em CONFIG). Só nessas duas abas por enquanto — as outras (EQUITY,
  CVM, NEWS, RESEARCH, TOP MERCADO, VISÃO GERAL) não usam esse sistema
  de painéis. Sem redimensionamento livre com o mouse (Streamlit não
  tem isso nativo).
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

**Limitações conhecidas:** cobre as empresas da sua watchlist que
tiverem CNPJ mapeado no FCA da própria CVM (`data/cvm.py:_mapa_ticker_cnpj`);
BDRs de empresa estrangeira (MELI34 etc.) não têm registro direto na CVM
brasileira, então não aparecem aqui.

## CALENDÁRIO

Próximos resultados (ITR/DFP) da sua watchlist, numa grade mensal com
painel lateral de detalhe. Fonte: hierarquia RI da empresa → notícia de
veículo confiável → prazo regulatório da CVM (Instrução CVM 480/2009) —
nessa ordem de confiabilidade.

- **Selo CONFIRMADO**: data vinda do RI oficial da própria empresa.
- **Selo ESTIMADO**: data vinda de notícia de veículo confiável, ainda
  sem confirmação oficial da empresa.
- **Selo PRAZO CVM**: nenhuma das duas fontes acima disponível — mostra
  o prazo MÁXIMO legal pra entrega do ITR/DFP, nunca uma data anunciada
  pela empresa (aviso explícito no detalhe do evento).
- **Grade mensal**: navegação por mês, célula de HOJE destacada; painel
  lateral mostra a semana atual e os eventos do dia selecionado.
- **CONTEXTO (hub do evento)**: ao selecionar um evento, abas compactas
  com RESEARCH/NEWS/DOCUMENTOS CVM/HISTÓRICO relacionados ao ticker —
  mesmas fontes/cache já usadas pelas abas RESEARCH/NEWS/CVM, sem
  nenhuma chamada de IA nem fonte nova.
- **Leitura via snapshot**: a tela só lê o snapshot calculado
  periodicamente em background (`coletor_local.py`) — nunca recalcula
  ao navegar/filtrar, por isso é instantânea mesmo com watchlist grande.

**Limitações conhecidas:** o prazo regulatório da CVM só existe pra
empresas de fato registradas na CVM (mesmo CNPJ mapeado usado pela aba
CVM) — BDR de empresa estrangeira (MELI34 etc.) nunca aparece aqui, já
que nunca protocola ITR/DFP nesse regime (mesma limitação documentada
na aba CVM acima). A categoria oficial "Calendário de Eventos
Corporativos" da CVM não tem campo estruturado com a data do evento em
si (só a data de protocolo do documento) — por isso o CONFIRMADO/
ESTIMADO depende de RI/notícia, não de um feed estruturado único.


## RADAR DE QUEDAS — CARTEIRAS RECOMENDADAS

O painel RADAR mostra alertas persistidos em `radar_alertas_queda`, consolidados por ticker e pregão, com filtro por ticker, casa e período. A regra é estrita: variação diária menor que -4,00%, usando preço atual e fechamento anterior do provedor. Cotações do Yahoo Finance podem ser atrasadas; a UI exibe a barra/coleta quando disponíveis.

A primeira fonte estruturada conectada é a seção pública de recomendações da Genial. O coletor da Genial pode falhar no Streamlit/GitHub Actions por bloqueio de rede; uma falha não significa carteira vazia. XP, BTG e outras casas não são marcadas como coletadas sem fonte pública estruturada acessível. Datas/validade ficam nulas quando a fonte não as fornece; recomendações não devem ser tratadas como vigentes além da evidência disponível.

## MORNING CALL POR E-MAIL

Job independente `python -m jobs.morning_call`, no workflow `.github/workflows/radar-morning-call.yml`. O horário principal configurado é **08:03 BRT em dias úteis**, com tentativas de reserva às **08:17, 08:38 e 09:07 BRT**. Esses horários são gatilhos do GitHub Actions, não garantia de entrega pontual: o GitHub pode atrasar ou descartar eventos agendados. Para reduzir esse risco, configure o disparo externo descrito em **Disparo externo dos agendamentos** abaixo.

O conteúdo consolida os dados disponíveis; indisponibilidades devem ser identificadas como tal. Os cenários são condicionais e não representam previsão garantida. O conteúdo não depende de carteiras recomendadas nem de alertas.

## Configuração necessária

1. Executar `sql/radar_research.sql` no SQL Editor do Supabase para criar as tabelas usadas pelo Radar e pelo registro de execuções do Morning Call.
2. Em GitHub → Settings → Secrets and variables → Actions, configurar `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `RESEND_API_KEY` e `EMAIL_FROM`. O workflow usa Resend por padrão; `EMAIL_PROVIDER` só precisa ser definido se quiser escolher outro provedor compatível. SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`) é necessário apenas se optar por SMTP. Nunca enviar credenciais no chat ou versioná-las.
3. No Pregão, cada destinatário precisa ativar **RECEBER MORNING CALL POR E-MAIL** em CONFIG. O envio agendado usa essa lista de assinantes opt-in; `EMAIL_TO` não substitui a inscrição dos usuários.
4. Para testar sem enviar à lista real, abra Actions → **Radar e Morning Call** → Run workflow, selecione `morning_call` e preencha `teste_destinatario` com um único endereço de teste. O assunto sai marcado como `[TESTE]`.
5. Para um envio normal manual, deixe `teste_destinatario` vazio e escolha `morning_call`. A idempotência evita novo envio para quem já recebeu no mesmo dia, quando o Supabase está disponível.

Nunca envie credenciais no chat ou versioná-las. Sem migration e secrets, os jobs não conseguem persistir nem enviar e-mails. O agendamento nativo do GitHub Actions é best effort, não um SLA de execução pontual; veja **Disparo externo dos agendamentos** para a alternativa recomendada.

## Resumos das matérias (Groq) no Morning Call

O Morning Call **não chama o Groq**: ele só lê os resumos que o workflow **Coletores na nuvem** (`coletores-nuvem.yml` → `coletor_local.py` → `pregerar_resumos_news`) já gerou e guardou no cache (`resumos_ia_cache`). Sem resumo no cache, a matéria sai no PDF só com manchete, veículo e link — nunca com texto inventado.

Esse workflow precisa do secret `GROQ_API_KEY`. Em 18/10/2026 ele chegava **vazio** ao job (log: `'GROQ_API_KEY não configurada em st.secrets'` em todos os grupos). Para configurar:

1. GitHub → repositório **Pregao** → **Settings** → **Secrets and variables** → **Actions** → aba **Secrets** → **New repository secret**.
2. *Name*: `GROQ_API_KEY` (exatamente assim). *Secret*: a mesma chave usada no app (Streamlit Cloud → *Manage app* → *Settings* → *Secrets*). Não crie como *Variable* nem como secret de *Environment*: o workflow lê `secrets.GROQ_API_KEY` do repositório.
3. Confira na próxima execução de **Coletores na nuvem** (ou *Run workflow* manual): a linha `resumos de NEWS: ... gerado(s) agora` deve deixar de mostrar `GROQ_API_KEY não configurada`.

Os resumos só entram no Morning Call se uma execução dos coletores rodar **antes** do envio (os coletores rodam a partir das 07h11, o Morning Call às 08h03, horário de Brasília).

## Disparo externo dos agendamentos (recomendado)

O `schedule` do GitHub Actions é "best effort": sob carga, o GitHub atrasa ou **descarta** disparos. Medido em 2026-10-18: entre 14 e 17/10, de ~220 disparos esperados (Radar a cada 15 min + Coletores a cada 30 min + Morning Call), só 23 aconteceram — e nenhum na sexta 17/10 (o Morning Call das 08h não saiu). Os workflows já usam minutos quebrados e disparos de reserva para reduzir a perda, mas a única forma confiável é um agendador externo chamando o `workflow_dispatch`.

Diagnóstico das execuções de 14 a 17/10/2026 (verificado no histórico do Actions):

- **Atraso, não só descarte:** o Morning Call agendado para 10h UTC (07h de Brasília, horário da época) só foi entregue pelo GitHub às 14h39 UTC de 15/10 e às 14h31 UTC de 16/10 — cerca de 4h30 depois. O Radar (a cada 15 min) teve 3 a 4 execuções por dia, também atrasadas. Em 17/10 (sexta) nenhum disparo agendado de nenhum workflow aconteceu.
- **As duas execuções que chegaram falharam por configuração de e-mail** (`EMAIL_FROM e EMAIL_TO precisam estar configurados`), já corrigida em 17/10 (envio por assinante opt-in + Brevo). Os envios de teste de 18/10, com os mesmos secrets, saíram com `ok=True`.
- **Hoje:** o Morning Call está em `3 11 * * 1-5` (08h03 de Brasília) com reservas às 08h17, 08h38 e 09h07. Não há proteção de horário: um disparo atrasado envia na hora em que chegar (o primeiro que rodar envia; os seguintes só confirmam "já enviado").
- **Sem e-mail duplicado:** as execuções do Morning Call rodam em série (`concurrency: pregao-morning-call`) e cada uma pula quem já tem registro `ENVIADO` no dia em `morning_call_execucoes`. Um disparo externo extra (abaixo) cai nessa mesma checagem. Exceção documentada no código: se a consulta a essa tabela falhar, o envio segue (prefere-se um duplicado raro a nenhum e-mail).

Passo a passo (gratuito, ~10 min):

1. **Token do GitHub (só para este repositório):** GitHub → Settings (do seu perfil) → Developer settings → Personal access tokens → **Fine-grained tokens** → *Generate new token*. Em *Repository access*, escolha **Only select repositories → Pregao**. Em *Permissions → Repository permissions*, deixe **Actions: Read and write** (nada mais). Validade: 1 ano. Copie o token (ele só aparece uma vez).
2. **Agendador:** crie conta em https://cron-job.org e crie 3 jobs, todos com:
   - *Request method*: `POST`
   - *Headers*: `Authorization: Bearer SEU_TOKEN`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`
   - *Timezone*: `America/Sao_Paulo`

   | Job | URL | Body | Horário |
   |---|---|---|---|
   | Radar | `https://api.github.com/repos/rodrigocostasouza2005-coder/Pregao/actions/workflows/radar-morning-call.yml/dispatches` | `{"ref":"main","inputs":{"job":"radar"}}` | a cada 15 min, seg–sex, 10h–17h |
   | Morning Call | mesma URL acima | `{"ref":"main","inputs":{"job":"morning_call"}}` | 08:00, seg–sex |
   | Coletores | `https://api.github.com/repos/rodrigocostasouza2005-coder/Pregao/actions/workflows/coletores-nuvem.yml/dispatches` | `{"ref":"main"}` | a cada 30 min, seg–sex, 07h–20h |

3. Teste um job com *Run now*: a resposta esperada é **HTTP 204** e um run novo aparece em Actions.

Os agendamentos do próprio GitHub podem continuar ligados: Radar e Morning Call são idempotentes (o Radar não duplica alerta do mesmo ticker/pregão; o Morning Call não reenvia no mesmo dia), então um disparo a mais não gera e-mail duplicado.
