# CHANGELOG — PREGÃO

Entradas curtas por commit, em português simples: o que mudou e por quê.
Mais recente primeiro.

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
