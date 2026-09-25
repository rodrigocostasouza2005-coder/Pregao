# PROGRESSO — Modo Autônomo (2026-09-23)

Log de execução das filas autônomas. Cada tarefa: implementar → `python
-m compileall .` → AppTest das abas afetadas + EQUITY → commit → push →
registro aqui. Duas filas chegaram (FILA 1 = "MODO AUTÔNOMO", FILA 2 =
"MODO AUTÔNOMO 2") — os números de tarefa colidem (cada fila tem um T1,
T2...) então prefixo FILA1-/FILA2- nos títulos abaixo. Por instrução
explícita da FILA 2 (regra 8), termino a FILA 1 antes de começar a 2.

## FILA 1 — Tarefas concluídas

### FILA1-T1 — Groq centralizado
- `config.py`: nova `obter_credenciais_groq()` -> (api_key, modelo).
  `api_key`: `st.secrets["groq"]["api_key"]`, fallback
  `st.secrets["GROQ_API_KEY"]` na raiz. `modelo`:
  `st.secrets["groq"]["modelo"]` ou `GROQ_MODELO_PADRAO`
  ("openai/gpt-oss-20b"). Novas constantes `GROQ_REASONING_EFFORT="low"`
  e `GROQ_MAX_TOKENS=400`. `obter_modelo_groq()` mantida (delega pra
  nova função), ninguém mais chamava direto.
- `data/research/resumir.py`: `resumir_com_groq` usa a função nova;
  adicionado `reasoning_effort` (faltava aqui, só o news.py tinha).
  Removido `import streamlit as st` (ficou sem uso).
- `data/news.py`: `_resumir_com_groq` usa a função nova; removida
  `_MODELO_GROQ_NEWS` (constante duplicada, sem uso depois da troca).
- Arquivos: config.py, data/news.py, data/research/resumir.py
- Testes: `compileall` limpo; AppTest EQUITY/NEWS/TOP MERCADO/CONFIG
  sem exceção; `config.obter_credenciais_groq()` retorna chave+modelo
  corretos em teste direto.
- Commit: (ver abaixo)

### FILA1-T2 — Integração TOP MERCADO/EQUITY (já estava completo)
Verificado: `config.ABAS_DISPONIVEIS` já tem "TOP MERCADO" depois de
"NEWS"; `app.py` já importa e chama `render_news`, `render_news_ticker`
(dentro do bloco EQUITY, dentro de `st.container(border=True)`, sem
coleta nova por interação — `obter_noticias` já é cacheado 20min) e
`render_top_mercado`; placeholders antigos removidos, só sobra CVM
(`_titulos_futuros = {"CVM": "Fase 5"}`). Nada a fazer — trabalho de
sessão anterior já cobriu isso. Nenhuma mudança de código.

### FILA1-T3 — CSS stButtonGroup (já estava completo)
Verificado: `style.css` e `ui/news_tab.py` já usam
`[data-testid="stButtonGroup"] button` (não mais `stPills`/
`stSegmentedControl`, que não existem nesta versão do Streamlit). O
seletor já é específico o suficiente por construção: `stButtonGroup` é o
testid interno só de segmented_control/pills — botões comuns (RESUMIR,
SALVAR etc.) não usam esse testid, não são afetados. AppTest confirma
EQUITY/MACRO/NEWS/TOP MERCADO renderizando sem exceção com os widgets de
pills em uso. Nenhuma mudança de código.

### FILA1-T4/T5 — Auditoria + performance
Achados reais (não hipotéticos, confirmados no código):
1. `data/prices.py:_ultima_cotacao_indice_valida` tinha
   `@st.cache_data(ttl=30)` empilhado ACIMA de `@st.cache_resource` —
   quebra a garantia de "mesmo objeto compartilhado entre chamadas" que
   o fallback do letreiro depende (cache_data pode copiar o retorno).
   Removido o `@st.cache_data` duplicado; confirmado em teste direto que
   agora é o mesmo objeto entre chamadas (`c1 is c2 == True`).
2. `data/prices.py:obter_cotacao_indice` não tinha cache algum (só o
   fallback de erro) — toda re-execução do script (não só o refresh
   automático do fragment) batia no yfinance de novo. Adicionado
   `@st.cache_data(ttl=30)`.
3. `data/research/genial.py:_buscar_next_data` não era cacheada —
   `obter_recomendacoes()` e `obter_swing_trade()` (chamadas toda vez
   que a aba RESEARCH renderiza, sem gate de 30min) batiam na MESMA
   home da Genial 2x separadas. Adicionado `@st.cache_data(ttl=
   TTL_COLETA)`.
4. `data/news.py`: TOP MERCADO buscava 8-10 fontes independentes
   (temas de mercado + feeds diretos) sequencialmente. Paralelizado com
   `ThreadPoolExecutor` (`_coletar_em_paralelo`, max_workers=8) — cada
   fonte já tinha timeout e falha isolada (None), só mudou o tempo de
   espera. Medido: `obter_top_mercado()` limpo de cache = 2.84s (antes
   não medido, mas eram 9 requests sequenciais de ~0.3-1s cada = várias
   vezes mais lento).
5. `data/research/genial.py:_tentar_buscar` (sequência de 4 tentativas
   de TLS/HTTP) não tinha orçamento de tempo total — numa falha ruim
   (timeout puro em vez de erro rápido), as 4 tentativas podiam somar
   bem mais que TIMEOUT×4. Reproduzido em teste real: uma chamada
   chegou a >100s e estourou o timeout do próprio AppTest (60s).
   Adicionado orçamento de 20s total (`_ORCAMENTO_TOTAL_S`); reteste
   confirmou parar em ~31s em vez de >100s.
- Timeouts em chamadas externas: já presentes em todas as `requests.get`/
  `cffi_requests.get` de data/news.py, data/macro.py, data/research/*,
  data/diagnostico.py (auditado, nenhum gap encontrado).
- Arquivos: data/prices.py, data/research/genial.py, data/news.py
- Testes: `compileall` limpo; AppTest EQUITY/MACRO/RESEARCH/NEWS/TOP
  MERCADO/CVM/CONFIG sem exceção (rodado em duas passadas — a primeira
  pegou o timeout de 100s+ da Genial ANTES do fix do item 5, confirmando
  o achado; a segunda, depois do fix, passou limpa).
- Commit: (ver abaixo)

### FILA1-T10 — E-mails de admin pra secrets (adiantado da FILA 2, mesmo tema)
`config.EMAILS_DIAGNOSTICO` (fixo, e-mail pessoal no código) virou
`config.obter_emails_admin()`, lendo `st.secrets["admin"]["emails"]` com
fallback pro e-mail atual enquanto o secret não existir — painel de
diagnóstico continua funcionando antes e depois da ação manual. Ver
AÇÕES MANUAIS PENDENTES pro bloco a colar.
- Arquivos: config.py, app.py (site de uso do painel DIAGNÓSTICO)
- Testes: `compileall` limpo; AppTest EQUITY/CONFIG sem exceção;
  `config.obter_emails_admin()` retorna o fallback correto em teste
  direto.
- Commit: (ver abaixo)

### FILA1-T6/T7 — Resumos e densidade visual (já estavam completos)
T6: verificado — RESEARCH já só resume automático pra watchlist
(`_painel_watchlist` com `permitir_resumo_auto=True`; o feed geral usa
botão). `_linha_relatorio` já confere `rel.get("resumo")` (já veio do
`listar_itens`) antes de chamar `obter_resumo`, sem consulta redundante
ao Supabase no mesmo rerun. NEWS/TOP MERCADO: resumo só dentro do
`@st.dialog` do card (clique), nunca automático na lista.
T7: layout já denso (linha wire de uma linha por notícia, card compacto
com veículos confiáveis primeiro + "e mais N"). Nenhuma mudança de
código nas duas.

### FILA1-T8 — BACKLOG (itens que não dependiam do Rodrigo)
- `ui/macro_tab.py`: barra de ferramentas do Plotly escondida nos 3
  gráficos (faltava `config={"displayModeBar": False}`, só existia em
  app.py).
- `ui/macro_tab.py`: eixo X do IPCA 12 meses em "mês/ano" abreviado
  PT-BR (ex: "ago/2026") — Plotly.js não tem locale PT-BR pro
  tickformat de data, rótulos montados na mão (`_eixo_x_mes_ano`).
- `app.py`: gráfico LINHA/AREA — MM20 saía com a mesma cor
  (`tema["destaque"]`) da linha de preço, ficavam indistinguíveis; MM20
  usa `tema["neutro"]` nesses dois modos (CANDLE continua com
  `destaque`, onde não colide).
- `data/prices.py`: beta recalculado localmente (cov/var de retornos
  semanais, 2 anos, contra `^BVSP`) em vez do campo `info['beta']` do
  yfinance (não confiável pra B3) — coluna BETA volta a aparecer em
  INDICADORES (tooltip explica o cálculo). Testado com dados reais:
  PETR4≈0.60, VALE3≈0.79, ITUB4≈1.25 (plausíveis).
- Avisos em estilo fino: já cobertos globalmente por
  `[data-testid="stAlert"]` em style.css, nenhuma mudança necessária.
- **Não resolvidos** (precisam de inspeção visual real, não dá pra
  confirmar só com AppTest que não renderiza CSS): título INDICADORES
  sumindo, título RESEARCH espremido, legenda da curva pré sobreposta,
  DY 12m duplicando JCP. Deixados no BACKLOG.md.
- Arquivos: app.py, data/prices.py, ui/macro_tab.py
- Testes: `compileall` limpo; `_calcular_beta` com dados reais (valores
  plausíveis); AppTest EQUITY/MACRO sem exceção.
- Commit: (ver abaixo)

### FILA1-T9 — "última coleta" + coletor local
- `data/research/__init__.py`: `ultimas_coletas_formatadas(casas_ativas)`
  - texto "casa: dd/mm hh:mm" (fuso BR) por casa ativa, usando
    `store.ultima_coleta_em`. Mostrado no topo da aba RESEARCH.
- `coletor_local.py` (novo, raiz do projeto): script standalone que
  chama `coletar_todas_disponiveis()` (sem gate de 30min — quem decide a
  frequência é o agendamento) + `apagar_itens_antigos()`, exit code 1 se
  alguma casa falhar. Testado rodando de verdade (falha aqui, esperado —
  sandbox bloqueia as duas fontes — mas roda sem quebrar e reporta certo).
- Passo a passo do Agendador de Tarefas do Windows: ver AÇÕES MANUAIS
  PENDENTES abaixo. Não agendei nada — só preparei o script e o guia.
- Não fiz: desligar a tentativa de coleta no Cloud quando uma fonte
  está bloqueada. O cooldown de 10min (FILA1-T5) já evita martelar a
  fonte a cada interação; ativar/desativar por ambiente (Cloud vs local)
  exigiria detectar em qual ambiente o app está rodando, o que não há
  hoje um jeito limpo de fazer — decisão conservadora: manter tentando
  (com cooldown), não me pareceu certo desativar sem confirmar com o
  Rodrigo se ele quer isso.
- Arquivos: data/research/__init__.py, ui/research_tab.py,
  coletor_local.py (novo)
- Testes: `compileall` limpo; AppTest EQUITY/RESEARCH sem exceção;
  `coletor_local.py` rodado de verdade (exit 1, esperado neste sandbox).
- Commit: (ver abaixo)

### FILA1-T11 — Qualidade (limpeza)
`pyflakes` (instalado localmente só pra essa checagem, não faz parte de
requirements.txt) rodado em todos os arquivos tocados na FILA 1 hoje
(app.py, config.py, data/news.py, data/prices.py, data/diagnostico.py,
data/research/*, ui/news_tab.py, ui/macro_tab.py, ui/research_tab.py,
coletor_local.py) — zero avisos (sem import não usado, sem nome
indefinido). Nenhuma mudança necessária.

## FILA 1 — CONCLUÍDA (T1 a T11, todas as tarefas do adendo original)

## FILA 2 — Tarefas concluídas

### FILA2-T0 — Acompanhamento (CHANGELOG, MANUAL, aba SISTEMA)
- `CHANGELOG.md` (criado antes, na FILA 1) — mantido a partir daqui.
- `MANUAL.md` (novo): o que cada aba/painel faz, fonte de dados,
  limitações conhecidas — escrito com base no código atual (EQUITY,
  MACRO, RESEARCH, NEWS, TOP MERCADO, CONFIG; CVM deixado em aberto de
  propósito, é de outra sessão ainda em andamento).
- `ui/sistema_tab.py` (novo) + `app.py`: aba SISTEMA, visível só pra
  `config.obter_emails_admin()` — **não** entra em
  `config.ABAS_DISPONIVEIS` de propósito (isso faria a migração
  automática de abas oferecer ela pra todo mundo); é adicionada à lista
  de seções só quando o e-mail logado é admin, então nem aparece no
  menu de usuário comum. 3 sub-abas (`st.tabs` local, ok aqui — não é a
  navegação principal, é conteúdo estático de 3 arquivos): CHANGELOG,
  PROGRESSO, MANUAL, lidos do disco.
- Arquivos: app.py, ui/sistema_tab.py (novo), MANUAL.md (novo)
- Testes: `compileall` limpo; AppTest confirma SISTEMA aparece e
  renderiza sem exceção pro e-mail admin, e fica totalmente ausente
  (nem o texto "SISTEMA" aparece) pra outro e-mail.
- Commit: (ver abaixo)

### Correção urgente — NEWS/TOP MERCADO lentos, matéria não abria, formatação regredida
Pausou a FILA 2 a pedido direto do Rodrigo (produção com problema visível).
Quatro problemas relatados, todos confirmados e corrigidos:
- **Lentidão em toda interação:** `_renderizar_lista` (usada por NEWS e TOP
  MERCADO) rodava o script inteiro a cada clique/expand. Envolvida em
  `@st.fragment` — reruns ficam isolados à lista, sem recarregar a aba
  inteira. Validado com AppTest que `st.dialog` ainda abre certo disparado
  de dentro de um fragment nesta versão do Streamlit (é um gotcha
  conhecido em outras versões).
- **Matéria não abria:** causa real era outra (ver "Complemento" abaixo) —
  o `st.dialog` sempre abriu; o que cobria o conteúdo era o tooltip.
  Mesmo assim, foi adicionado um ícone `↗` por linha
  (`<a href=... target='_blank'>`) como acesso direto à matéria, sem
  depender do dialog.
- **Agrupamento de notícias:** o algoritmo antigo (`_agrupar`) comparava
  cada notícia nova só contra o ÚLTIMO grupo aberto (single-representative
  greedy) — manchetes sobre o mesmo fato com redação diferente ficavam em
  grupos separados. Reescrito: `_extrair_entidades` pega substantivos
  próprios (sequências de palavras capitalizadas, sub-janelas de 2
  palavras + a run inteira se >2), com lista de exclusão
  (`_ENTIDADE_IGNORAR`) pra termos genéricos (dias da semana, "governo",
  "operação/caso/processo" etc.); `_mesmo_grupo` funde se o título é
  idêntico, OU se há entidade em comum dentro de 24h
  (`_JANELA_HORAS_ENTIDADE`), OU se a similaridade textual já usada antes
  bate dentro da janela de dias antiga. Testado com script sintético
  reproduzindo o caso real relatado (5 manchetes variando a redação sobre
  "Banco Genial" → 1 grupo só; manchete de controle sobre "Ibovespa"
  permanece separada) — sem esse teste, uma primeira versão da extração de
  entidades colava "Ex-Banco"/"Caso Banco Genial" como uma entidade
  indivisível (hífen tratado como parte da palavra) e não mesclava com
  "Banco Genial" puro; corrigido tratando qualquer caractere não-palavra
  como separador.
- **Formatação (scroll horizontal, coluna vazia, tooltip):** causa raiz do
  corte/scroll horizontal era o `min-width: auto` padrão do flexbox nas
  colunas do `st.columns()` recusando encolher abaixo do texto
  `white-space: nowrap` — `min-width: 0 !important` nas colunas +
  `overflow-x: hidden` na linha resolveu. Coluna de ticker vazia (era só
  "—" quando a notícia não tinha ticker) removida; ticker agora é prefixo
  inline no próprio texto da manchete (`_prefixo_tickers`). Contagem de
  fontes compactada pra "NF" (`_plural_fontes`). Botões de setor com
  `flex-wrap` pra não estourar largura.
- **Complemento (tooltip cobrindo o card aberto):** `help=` do botão de
  manchete usa o `title=`/tooltip nativo do browser, que renderiza acima
  de QUALQUER conteúdo da página — inclusive um `st.dialog` aberto (não é
  parte do stacking context normal da página). Removido o `help=` da
  manchete; tooltip explicativo mantido só no selo de relevância.
- Arquivos: `data/news.py` (`_extrair_entidades`, `_mesmo_grupo`,
  `_agrupar`, `_ENTIDADE_IGNORAR`), `ui/news_tab.py` (`_renderizar_lista`
  com `@st.fragment`, `_linha_noticia`, `_prefixo_tickers`,
  `_plural_fontes`, CSS de colunas/botões), `ui/top_mercado_tab.py`
  (nenhuma mudança direta — reusa as funções de `news_tab.py`).
- Testes: `compileall` limpo; AppTest em EQUITY/NEWS/TOP MERCADO sem
  exceção; teste dirigido clicando um botão de manchete real (prefixo de
  key `news-manchete-`, usado tanto em NEWS quanto em TOP MERCADO) e
  confirmando que o dialog abre com resumo; script sintético de
  agrupamento (fora do repo, scratchpad da sessão).
- Commit: correção enviada e registrada no `CHANGELOG.md`.

### Letreiro (ticker tape) — tamanho maior
Fonte de 0.75rem (~12px) pra 0.875rem (~14px) em `.ticker-tape-set`
(`style.css`); padding vertical da faixa de 0.35rem pra 0.4rem e espaço
entre itens (`padding-right`) de 2.5rem pra 3rem; símbolo da watchlist no
letreiro agora em negrito (`font-weight:600`, igual já era na sidebar) em
`_ticker_tape()` (`app.py`). `padding-top` do `.block-container` ajustado
de 5.4rem pra 5.65rem pra compensar a faixa fixa mais alta (senão o topo
do conteúdo ficaria coberto). Estimativa de largura em px/caractere usada
pro cálculo de velocidade do modo ANIMADO também ajustada (7.5 → 8.75,
proporcional ao aumento da fonte), senão a duração da animação ficaria
calculada pra um texto mais estreito do que o real.
Opcional (tamanho P/M/G configurável em CONFIG) não implementado — pedido
explicitamente como opcional pelo Rodrigo; fica registrado em MELHORIAS
FUTURAS se ele quiser depois.
- Arquivos: `style.css`, `app.py`.
- Testes: `compileall` limpo; AppTest em EQUITY/NEWS/TOP MERCADO sem
  exceção.
- Commit: enviado.

### coletor_local.py — log em arquivo
Pendência do item 3 do "Diagnóstico no Cloud" (24/09): rodando via
Agendador de Tarefas "sem abrir janela", o stdout do script não fica
visível em lugar nenhum depois — só o exit code aparece no Histórico da
tarefa. Adicionado `logging` com dois handlers (console, igual antes +
`RotatingFileHandler` gravando em `coletor_local.log` na raiz do
projeto, 1MB x 3 arquivos pra não crescer sem limite com execuções a
cada 30min). Escopo: só as linhas de resumo do próprio
`coletor_local.py` (status por casa, contagem de itens, limpeza) vão pro
arquivo — os `print()` internos de `data/research/__init__.py`/
`genial.py`/`xp.py` (detalhe de cada tentativa de conexão) continuam só
no stdout; decisão conservadora pra não reescrever o logging desses
módulos, e o resumo já é o que importa pra saber se a coleta funcionou.
`coletor_local.log` adicionado ao `.gitignore` (artefato de execução,
não versionado).
- Arquivos: `coletor_local.py`, `.gitignore`.
- Testes: `compileall` limpo; rodei o script de verdade
  (`.venv/Scripts/python.exe coletor_local.py`) — Genial/XP falharam como
  esperado (mesmo bloqueio de sempre neste sandbox), e o arquivo
  `coletor_local.log` foi criado com as linhas de resumo corretas.
- Commit: enviado.

### Timeout curto no diagnóstico + bug real corrigido na watchlist do RESEARCH
Pendências do item 2/3 do "Diagnóstico no Cloud" (24/09), fechadas agora:
- `data/research/genial.py`/`xp.py`: `testar_conexao()` ganhou um
  parâmetro de orçamento/timeout com default de 5s (`orcamento_s`/
  `timeout`), usado só pelo painel DIAGNÓSTICO DE FONTES
  (`data/diagnostico.py`, chama sem argumentos → pega o novo default). A
  coleta real (`obter_relatorios`, usada por `coletar_pendentes` e por
  `coletor_local.py`) continua chamando `_tentar_buscar`/
  `_tentar_requisitar` sem esse argumento, então mantém o orçamento cheio
  de 20s/10s — só o diagnóstico ficou mais rápido.
- **Achado durante o teste desse item:** rodando AppTest na aba RESEARCH
  depois da mudança, o log ainda mostrava tentativas reais de conexão com
  a Genial levando ~20s, mesmo com `tentar_coleta_automatica: False`.
  Causa: `ui/research_tab.py`/`_painel_watchlist` chama
  `obter_recomendacoes()`/`obter_swing_trade()` da Genial DIRETO, sem
  passar pelo `preparar_leitura`/`coletar_pendentes` (que já respeitava o
  flag) — esses dois retornam dado só-ao-vivo, cacheado só em memória do
  processo (`@st.cache_data(ttl=TTL_COLETA)`), nunca gravado no Supabase,
  então não tem como o `coletor_local.py` alimentar isso. Ou seja, a
  correção anterior ("pule a coleta da Genial/XP no Cloud") estava
  incompleta: cobria a listagem geral de relatórios, mas não esse painel
  específico, que continuava travando a aba periodicamente (a cada
  estouro do cache em memória). Corrigido pulando as duas chamadas quando
  `tentar_coleta_automatica` da Genial é `False` — a seção "Genial:
  recomendação"/"Swing trade" some da watchlist nesse caso, mas o resto
  do painel (relatórios vindos do Supabase) continua normal.
- Arquivos: `data/research/genial.py`, `data/research/xp.py`,
  `ui/research_tab.py`.
- Testes: `compileall` limpo; AppTest em EQUITY/RESEARCH sem exceção;
  reprodução direta do bug (rodei o teste ANTES da correção do
  `research_tab.py` e vi as tentativas reais de conexão com a Genial no
  log/stdout, confirmando que era um problema de verdade, não suspeita).
- Commit: enviado, registrado no CHANGELOG.

## Nota: decisão FILA1-T9 (abaixo) superada
A decisão "não desativar coleta automática de Genial/XP no Cloud" (ver
"Decisões registradas" abaixo) foi **revertida** depois do diagnóstico real
de produção confirmar que ambas ficam bloqueadas no Cloud também (não só
no sandbox). `data/research/__init__.py`: `CASAS["genial"|"xp"]` agora tem
`"tentar_coleta_automatica": False` — a aba RESEARCH só lê do Supabase
pra essas duas, sem tentar coletar (e sem os ~20s de espera). Coleta real
dessas casas fica só com `coletor_local.py` rodando fora do Cloud.

### FILA2-T1 — Qualidade do resumo de notícias
Formato antigo (2-3 linhas livres) trocado por formato fixo estruturado
em `_PROMPT_SISTEMA_RESUMO` (`data/news.py`): O QUE ACONTECEU / NÚMEROS /
IMPACTO / PRÓXIMOS PASSOS, 5-8 linhas, sempre em palavras próprias (nunca
copia o texto original), campo sem informação vira "não informado" (não
inventa dado). Orçamento de tokens próprio (`_MAX_TOKENS_RESUMO_NEWS =
700`, maior que o do research, que usa formato mais enxuto) — antes o
resumo de NEWS usava por engano `config.GROQ_MAX_TOKENS` (o budget do
research), pequeno demais pro formato de 4 campos.

**Fallback por manchetes:** quando TODAS as fontes do grupo falham a
extração (paywall/bloqueio total), mas o grupo tem 2+ manchetes
diferentes (fontes distintas cobrindo o mesmo fato, graças ao
agrupamento por entidade da correção urgente), `_resumir_das_manchetes`
tenta sintetizar um resumo mais curto (3-5 linhas) só com base nas
manchetes, mesmo formato fixo, com nota "(resumo baseado nas manchetes)"
anexada no fim pra deixar claro que a fonte foi mais fraca. Com só 1
manchete (sem info extra pra cruzar), não tenta — continua "resumo
indisponível" como antes, pra não inventar conteúdo a partir de uma
frase só.

**Bug pego durante a implementação:** a `<div class='w-resumo-dialogo'>`
que mostra o resumo no card (`ui/news_tab.py`) não tinha
`white-space: pre-line` — o formato de 4 linhas ia colapsar tudo numa
linha só no navegador (HTML ignora quebra de linha simples por padrão).
Corrigido.

Refatorado `_resumir_com_groq` em duas partes: `_chamar_groq(prompt_sistema,
prompt_usuario)` genérico (reusado pelos dois prompts) +
`_resumir_com_groq`/`_resumir_das_manchetes` específicos.
`obter_resumo_grupo` ganhou o parâmetro `titulos` (tupla, default vazio
por compatibilidade) — `ui/news_tab.py`/`_abrir_card` passa
`n.get("titulos") or [n["titulo"]]`.

- Arquivos: `data/news.py`, `ui/news_tab.py`.
- Testes: `compileall` limpo; AppTest EQUITY/NEWS/TOP MERCADO sem
  exceção; **medição real de taxa de sucesso** — amostra de 20 grupos
  reais do TOP MERCADO (`obter_top_mercado_tudo()[:20]`, mistura de
  Ibovespa/câmbio/juros/Copom/ações/internacional): **20/20 (100%)**
  geraram resumo com sucesso via extração de texto completo (0 precisou
  do fallback de manchetes nessa amostra — as fontes usadas responderam
  bem). Como a amostra real não exercitou o fallback, testei ele
  separado com mocks (fora do repo, scratchpad): forçando falha de
  extração em TODAS as fontes de um grupo sintético com 3 manchetes
  diferentes sobre o mesmo fato ("Banco Genial...") — o fallback gerou
  resumo corretamente, com a nota "(resumo baseado nas manchetes)"; um
  segundo caso com 1 manchete só (sem 2+ pra cruzar) corretamente NÃO
  tentou o fallback e voltou "indisponível", como esperado.
- Commit: enviado, registrado no CHANGELOG.

### FILA2-T2 — Tooltips explicativos
`title=` nos cabeçalhos da tabela INDICADORES (EQUITY): VALOR DE MERCADO,
P/L, P/VP, DIV. YIELD (12M) — BETA (2A) já tinha desde a auditoria da
FILA1. `help=` nos checkboxes de média móvel (CONFIG): MÉDIA MÓVEL
20/50/200, cada um com uma frase curta do que representa e pra que serve
na prática (curto/médio/longo prazo).
- Arquivos: `app.py`.
- Testes: `compileall` limpo; AppTest EQUITY e CONFIG sem exceção.
- Commit: enviado.

### FILA2-T3 — Nova aba MERCADO
Nova aba (`data/mercado.py`, `ui/mercado_tab.py`): termômetro (papéis em
alta/baixa/estáveis), maiores altas/baixas, mais negociados (por volume
financeiro), desempenho setorial (barra horizontal), mapa de calor
(treemap Plotly, tamanho=volume financeiro, cor=variação %) e mercados
globais (S&P 500, Nasdaq, Dow, FTSE, DAX, Nikkei, Hang Seng, Xangai).

**Dados**: lote único via `yf.download` (não um `fast_info` por papel —
com ~60 tickers, uma chamada em lote é ordens de magnitude mais rápida
que 60 sequenciais, mesmo raciocínio do `ThreadPoolExecutor` do TOP
MERCADO). Fonte: `config.IBOVESPA_COMPOSICAO`, lista curada de blue
chips com setor — **decisão registrada abaixo** sobre por que não é a
composição oficial completa.

**Bugs reais pegos durante o teste funcional** (rodei as funções de
`data/mercado.py` contra dado real antes de construir a UI em cima,
scratchpad da sessão):
1. `obter_mercados_globais` reusava `_para_symbol_yf` (de
   `data/prices.py`), que só sabe lidar com tickers da B3 (`PETR4` →
   `PETR4.SA`) e símbolos de índice/moeda que começam com `^` ou têm `=`
   — o símbolo de Xangai (`000001.SS`) não bate em nenhum desses casos e
   virou `000001.SS.SA` (inválido, 0 resultado). Corrigido com
   `_baixar_lote_bruto`, que NÃO passa os símbolos de
   `config.INDICES_GLOBAIS` por essa conversão (eles já vêm no formato
   exato que o yfinance espera).
2. Confirmado que 13 dos 64 tickers curados falharam no lote no momento
   do teste (`ELET3`, `ELET6`, `EMBR3`, `AZUL4` etc. — mensagem "no data
   found, symbol may be delisted" do yfinance). Não investiguei se é
   delisting real, instabilidade do yfinance ou bloqueio de IP do
   sandbox (mesmo tipo de problema já visto com Genial/XP) — o
   importante é que o código já trata isso corretamente por design:
   papel sem dado válido simplesmente sai do panorama (nunca aparece com
   número inventado/zerado). 51/64 papéis responderam bem o suficiente
   pra alimentar todos os painéis.

- Arquivos: `config.py` (`IBOVESPA_COMPOSICAO`, `INDICES_GLOBAIS`,
  `ABAS_DISPONIVEIS`), `data/mercado.py` (novo), `ui/mercado_tab.py`
  (novo), `app.py` (import + roteamento), `MANUAL.md`.
- Testes: `compileall` limpo; teste funcional direto de
  `data/mercado.py` contra yfinance real (scratchpad, achou os 2 bugs
  acima); AppTest em EQUITY/MERCADO/CONFIG sem exceção (inclusive com a
  migração automática de `abas_visiveis` pra usuário com prefs antigas,
  já testada na FILA1, cobrindo a aba nova sem precisar de código extra).
- Commit: enviado, registrado no CHANGELOG.

## Decisão registrada (regra 1 de autonomia) — escopo do T3
Três sub-itens do pedido original do T3 foram tratados assim:
- **Composição do Ibovespa "via config file"**: implementada como um
  dict curado (`config.IBOVESPA_COMPOSICAO`, ~60 blue chips com setor)
  em vez de raspar a composição oficial completa (~86 papéis) do site da
  B3. Motivo: scraping da B3 não tinha sido investigado/confirmado como
  viável (like Genial/BTG, pode estar atrás de bot-detection), e o
  próprio pedido já previu esse risco ("facilmente atualizável") — dict
  simples resolve isso sem depender de mais uma fonte externa frágil.
- **Curva de juros (DI futuro)**: NÃO duplicada na aba MERCADO — já
  existe uma curva de juros prefixada real (ANBIMA ETTJ,
  `data/macro.py:obter_curva_pre`) na aba MACRO, construída antes desta
  sessão. Motivo: reimplementar o mesmo dado dentro de outra aba seria
  redundante e aumentaria a chance de os dois painéis mostrarem números
  diferentes se algo divergir.
- **Agenda de Copom/resultados**: NÃO implementada. Motivo: exigiria uma
  fonte de calendário confiável (datas de reunião do Copom, datas de
  resultados por empresa) que o projeto não tem hoje — inventar essas
  datas violaria o princípio já estabelecido em `data/macro.py` ("Nunca
  inventa dados"). Fica como MELHORIA FUTURA: precisa de uma decisão de
  fonte (scraping do calendário do BCB? alguma API paga de agenda
  corporativa?) antes de implementar — não é uma tarefa surgical.

### FILA2-T4 — Polimento visual
Barra de status fixa (relógio de Brasília HH:MM:SS, indicador ●PREGÃO
ABERTO/FECHADO em verde/vermelho — dia útil + horário 10h-17h,
simplificado de propósito, não é fonte oficial de horário de pregão —,
nota de atraso de cotação ~15min) — adicionada dentro do MESMO fragment
do letreiro (`_ticker_tape()`), no mesmo `run_every` das cotações, de
propósito: um fragment próprio só pro relógio precisaria rodar a
1x/segundo pra não "travar" visualmente, o que geraria muito mais rerun
do que o necessário e contrariaria o trabalho de performance da FILA1.

O resto do pedido do T4 (header de painel estilizado, tabelas densas
alinhadas) já estava coberto por CSS de sessões anteriores a este modo
autônomo (`.painel-titulo`, regra global `table { font-size:0.78rem;
... } td,th { padding:0.15rem 0.5rem; }`) — não havia nada quebrado ou
pendente aí, então não mexi por mexer.

- Arquivos: `app.py`, `style.css`.
- Testes: `compileall` limpo; AppTest EQUITY/MERCADO sem exceção;
  conferido o HTML gerado de verdade (via `at.markdown`) pra confirmar
  que o indicador de pregão aberto/fechado está no marcador certo.
- Commit: enviado.

### FILA2-T5 — Layout de painéis arrastável/redimensionável (NÃO implementado)
Por decisão explícita do Rodrigo (regra 6 da FILA 2: mudanças
arquiteturais grandes só devem ser documentadas como sugestão, não
implementadas), este item fica só registrado aqui, sem código:

**O que seria**: cada usuário podendo arrastar/reordenar/redimensionar os
painéis de cada aba (EQUITY, MERCADO etc.), com o layout persistido por
usuário no Supabase (tabela nova, ex: `user_layout`, chave por
`usuario_id + aba`).

**Por que é uma mudança grande**: a navegação atual (`if secao_atual ==
"X": render_x(prefs)`) já foi deliberadamente desenhada pra renderizar só
a seção ativa, sem "grid" de posições — introduzir arrastar/redimensionar
exigiria (a) trocar `st.container(border=True)` sequencial por um
sistema de grid com posições/tamanhos salvos, (b) uma biblioteca de
drag-and-drop pro Streamlit (não é nativo — precisaria de um componente
customizado ou HTML/JS via `st.components.v1.html`, algo que o projeto
não usa em lugar nenhum hoje), (c) uma nova tabela no Supabase +
migração, (d) redesenhar CADA painel de CADA aba pra funcionar dentro de
um container redimensionável. Não é uma tarefa surgical - é uma mudança
de arquitetura de UI inteira.

**Sugestão pra quando for pra frente**: como passo intermediário mais
barato, dá pra oferecer só REORDENAR (sem redimensionar) os painéis via
um `st.multiselect`/lista com drag simples (existe componente de
terceiros pra isso, ex: `streamlit-sortables`) salvando só uma lista de
ordem por aba em `user_prefs` (reaproveitando a tabela que já existe,
sem tabela nova) - cobre a parte mais pedida ("quero ver X antes de Y")
sem entrar no redimensionamento livre, que é o pedaço realmente caro.

### FILA2-T6 — Integração CVM (NÃO implementado por enquanto)
Verifiquei (só leitura, sem editar nada) que `data/cvm.py` (450 linhas) e
`ui/cvm_tab.py` (238 linhas, `render_cvm` importa e expõe normal) já
parecem funcionalmente completos — têm `obter_documentos_watchlist`,
`documento_confirmador` (pra badge "CONFIRMADA" cruzando notícia com
filing da CVM) e `obter_resumo_documento`, exatamente os pontos que o T6
pedia pra integrar. MAS os dois arquivos (+ `sql/cvm.sql` +
`preview_cvm.py`) estão **sem commit nenhum** (`git status` mostra `??` -
untracked), ou seja, é trabalho em andamento de outra sessão que ainda
não foi para o controle de versão.

**Decisão**: não fiz a integração (badge CONFIRMADA em NEWS, painel
RESULTADOS em EQUITY, entrada em DIAGNÓSTICO DE FONTES) nem removi o
placeholder "Fase 5" que esconde a aba CVM da navegação em `app.py`.
Mesmo sem editar os arquivos proibidos diretamente, construir essa
integração agora significa: (a) depender de uma interface que a outra
sessão ainda pode estar mudando (nada commitado = nenhuma garantia de
estabilidade), e (b) ativar em produção uma aba que a própria outra
sessão claramente decidiu manter atrás de um placeholder de proposito -
não é meu lugar destravar isso por ela. Regra de ouro da fila
("nunca edite data/cvm.py, ui/cvm_tab.py, sql/cvm.sql, preview_cvm.py")
existe justamente pra não colidir com esse trabalho paralelo; tratei o
espírito da regra como cobrindo também "não ativar/depender dele em
produção antes da hora", não só "não editar o arquivo literalmente".

**Retomar quando**: a outra sessão commitar esses arquivos (ou o Rodrigo
confirmar que já pode integrar) - aí sim dá pra fazer o badge/painel/
diagnóstico sem risco de trabalhar em cima de areia movediça.
- Commit: nenhum (nada mudou nos arquivos do projeto pra este item).

### FILA2-T7 — Painéis novos em EQUITY (comparador + altas/baixas da watchlist)
Painel "COMPARATIVO DA WATCHLIST" (só aparece com 2+ tickers na
watchlist): tabela lado a lado com TICKER/PREÇO/VAR. DIA/P-L/P-VP/DY pra
todos os papéis da watchlist (reusa `obter_cotacao`/`obter_indicadores`
já existentes, sem função de dado nova), mais uma linha de destaque
"melhor desempenho do dia" / "pior desempenho do dia" (cobre o pedido de
"altas e baixas da watchlist" sem precisar de um painel separado).

**Bug pego no teste** (rodei AppTest de verdade e conferi o HTML gerado
via `at.markdown`, não só "sem exceção"): a primeira versão rotulava os
extremos como "maior alta"/"maior baixa" usando `max`/`min` por
variação % puro — se a watchlist inteira estivesse no vermelho no dia,
o "maior alta" mostrava um ticker NEGATIVO rotulado como alta (ex:
"PETR4 -0,70%" chamado de "maior alta do dia"), enganoso. Corrigido
renomeando pra "melhor/pior desempenho do dia" (neutro quanto ao sinal)
e colorindo cada rótulo pela classe REAL do valor (alta/baixa), não pela
posição (melhor/pior).

- Arquivos: `app.py`.
- Testes: `compileall` limpo; AppTest EQUITY sem exceção; conferido o
  HTML de verdade (via `at.markdown`) ANTES e DEPOIS da correção do bug
  do rótulo, com a watchlist padrão de teste (PETR4/VALE3/ITUB4, todos
  em queda no dia do teste) — cenário que só acontece na prática quando
  o mercado inteiro cai, mas que o teste automático pegou de qualquer
  jeito por sorte de timing.
- Commit: enviado, registrado no CHANGELOG.

### FILA2-T8 — Lives da Genial no YouTube (implementado, mas desligado)
Pedido original: transcrever e resumir as lives da Genial no YouTube
(Morning Call, Resumo da Manhã, Fechamento de Mercado, Podcast Genial
Analisa ter/qui 19h, Estratégia em Ação última quarta 18h30, Conversa com
Zé Márcio sáb 14h, Reunião do Copom quartas 19h30 ~45 dias), identificado
pelo título do vídeo, mesmo formato de resumo.

**Investigação (com ferramenta de busca/fetch web, dados reais, não
suposição)**:
1. Canal oficial confirmado: "Genial Investimentos",
   `UCYSOMA4Yx1CJvrdI8epLfnA` (conferido pelo conteúdo do feed batendo
   com notícias do dia 24/09/2026 de verdade).
2. O feed RSS público do canal (`/feeds/videos.xml?channel_id=...`, sem
   API key) retorna os ~15 vídeos mais recentes com título/data/link -
   testado e os títulos reais batem com os padrões esperados ("Morning
   Call Genial", "Resumo da Manhã", "Fechamento Genial" etc.).
3. Legenda automática em português existe pra todo vídeo testado do
   canal (`youtube_transcript_api`) - texto extraído de verdade (41 mil
   caracteres num teste real), qualidade suficiente pra resumir.
4. **Bloqueio real encontrado**: o `robots.txt` do YouTube
   (`https://www.youtube.com/robots.txt`) tem, sob `User-agent: *`
   (aplica a qualquer bot genérico, inclusive o `PregaoApp/...` deste
   projeto): `Disallow: /feeds/videos.xml` E `Disallow: /api/`. O
   `permitido()` que TODA coleta deste projeto já respeita (mesma função
   usada por Genial/XP/etc, ver `data/research/base.py`) bloqueia
   corretamente esse feed - não é bug, é a proteção funcionando como
   projetada.

**Decisão (regra 1 de autonomia)**: implementei o módulo inteiro
(`data/research/genial_lives.py` - feed, identificação de programa por
título, extração de legenda) e testei cada parte contra dado real
(funciona tecnicamente), mas registrei a "casa" como `disponivel: False`
(mesmo padrão do BTG) em vez de ativá-la - contrariar o robots.txt
específico pra este source, depois de o projeto inteiro seguir essa
política em toda outra fonte, seria inconsistente e é uma decisão de
risco/ToS que não é minha pra tomar sozinho. Caminho limpo seria a API
oficial do YouTube Data v3 (precisa de API key nova - ver AÇÕES MANUAIS
PENDENTES) pra LISTAR vídeos; mesmo essa API, a parte de BAIXAR legenda
de vídeo de outro canal exige OAuth do dono do canal (Genial não vai
autorizar o app pessoal do Rodrigo), então nem a API oficial cobre
transcrição de terceiro de forma limpa - **este item pode não ter uma
solução 100% "por dentro das regras" com o canal de outra empresa**, vale
alinhar com o Rodrigo se ele topa usar o mecanismo já pronto mesmo assim
(ele mesmo pode religar em 1 linha: `disponivel: True` em
`data/research/__init__.py`) ou se prefere deixar desligado.

- Arquivos: `data/research/genial_lives.py` (novo), `data/research/__init__.py`,
  `data/diagnostico.py` (entrada no painel de diagnóstico, testa e mostra
  o bloqueio honestamente), `ui/research_tab.py` (label "LIVE/VÍDEO"),
  `requirements.txt` (`youtube-transcript-api`).
- Testes: `compileall` limpo; teste funcional direto contra dado real
  (feed, identificação de programa, transcrição) ANTES da decisão de
  desligar; AppTest EQUITY/RESEARCH/CONFIG sem exceção; `testar_conexao()`
  confirmado reportando o bloqueio corretamente ("bloqueado pelo
  robots.txt").
- Commit: enviado, registrado no CHANGELOG.

## MODO AUTÔNOMO 3 — bugs P0/P1 (em andamento)

### P0.1 — Indicadores (P/L, P/VP, DY, valor de mercado) regrediram pra "—"
Causa real: `obter_indicadores` usava `tk.info` do yfinance sem nenhuma
resiliência - um bloqueio/instabilidade do Yahoo (mais comum em IP de
datacenter como o do Streamlit Cloud) derrubava TODOS os campos pra
None de uma vez, sem fallback. Corrigido em `data/prices.py`:
- `_tk_info_com_retry`: tenta `tk.info` primeiro com uma sessão
  `curl_cffi` impersonando Chrome (mesma técnica já usada pra Genial -
  Yahoo bloqueia menos requisições que parecem vir de um navegador de
  verdade), com fallback pra sessão padrão do yfinance.
- TTL de `obter_indicadores` de 1h pra 12h (fundamentos mudam pouco
  intra-dia, reduz quanto bate no Yahoo).
- `_ultimo_indicadores_valido` (`st.cache_resource`, mesmo padrão do
  fallback da ticker tape): se a coleta atual não trouxer NENHUM campo
  válido, usa o último valor bem-sucedido em vez de "—" - só troca por
  "—" de verdade se NUNCA tiver havido uma coleta boa.
- `testar_conexao_indicadores` registrada em DIAGNÓSTICO DE FONTES.
- Testado com dado real: PETR4/VALE3/MELI34 voltando P/L, P/VP, DY,
  valor de mercado corretos.

### P0.3 — Coletor local não tinha tarefa agendada ("Última coleta: nunca")
Tarefa "PREGAO - coleta research" criada no Agendador de Tarefas do
Windows via PowerShell (dias úteis Seg-Sex, 7h-20h, a cada 30min,
`pythonw.exe` do `.venv`, sem janela). Rodei manualmente pra testar.

**Achado real ajustando a pedido do Rodrigo** (a primeira versão usava
`python.exe`, abrindo uma janela de console visível): trocado pra
`pythonw.exe`. Isso expôs um bug real: sob `pythonw` (sem console),
`sys.stdout`/`sys.stderr` podem vir `None`, e os módulos de coleta usam
`print()` de propósito (aparecem nos Logs do Streamlit Cloud) - um
`print()` batendo em `stdout=None` derruba o processo antes de logar
qualquer coisa. Corrigido em `coletor_local.py`: guarda `sys.stdout`/
`sys.stderr` pra um sink seguro (`os.devnull`) se vierem `None`, ANTES
de importar qualquer coisa que possa chamar `print()`; logger do
`streamlit` (barulhento com warnings "No runtime found...") silenciado
pra ERROR, sem mexer no logger próprio do script.

**Resultado do teste real**: a tarefa roda corretamente, sem crash, log
gravado certinho em `coletor_local.log`. MAS Genial e XP continuam
FALHANDO mesmo rodando localmente nesta máquina (timeout na Genial,
HTTP 403 na XP) - ou seja, o bloqueio não é exclusivo do Streamlit
Cloud, afeta essa rede também. "Última coleta: nunca" **continua sem
resolver de verdade** pra essas duas casas específicas, mesmo com a
infraestrutura de agendamento 100% funcional agora - depende de rodar
de uma rede onde esses sites não estejam bloqueados (não é algo que eu
controle a partir daqui).

- Arquivos: `coletor_local.py`.
- Testes: tarefa disparada manualmente 2x (antes e depois da correção
  do pythonw), log conferido, `Get-ScheduledTask`/`Get-ScheduledTaskInfo`
  conferidos via PowerShell.
- Commit: enviado.

### P0.5 — Curva pré: rótulo "Hoje" quando a publicação não é de hoje
`_painel_curva_pre` (`ui/macro_tab.py`) comparava a data real da
publicação da ANBIMA (`data_referencia`) contra a data de hoje - se
diferente (ANBIMA publica só no fim do dia, ou não publicou hoje ainda),
rotula "Última (dd/mm/aaaa)" em vez de "Hoje (dd/mm/aaaa)".
- Testes: `compileall` limpo; AppTest MACRO sem exceção.
- Commit: enviado (junto com P0.1).

### PRIORIDADE 1/2 — Notícias de BDR não apareciam (MELI34 e outras)
**Investigação completa da cadeia** (ATIVO → identidade → busca → fontes
→ relevância → dedup → exibição), causa raiz encontrada em DOIS bugs
reais, ambos genéricos (não específicos de MELI34):

1. `_SUFIXO_JURIDICO` (`data/prices.py`) só removia sufixos jurídicos em
   português (S.A., Participações, Holding) do `longName` do yfinance -
   nomes de empresa estrangeira em BDR vêm em inglês (ex: MELI34 ->
   "MercadoLibre, Inc.") e ficavam com a vírgula+sufixo grudados no nome
   "limpo". `_nome_curto` (`data/news.py`) então derivava
   `"mercadolibre,"` (COM vírgula) como o "nome curto" pra checar
   relevância - isso NUNCA batia com nenhum token de título de notícia
   de verdade (o tokenizador separa a vírgula), então `_relevante()`
   sempre retornava False pra BDR de empresa estrangeira, mesmo com a
   empresa claramente no título.
2. A busca em si (`termo = f'"{nome}" {ticker}'`) só tentava o nome
   legal completo do yfinance + o ticker local da B3 - cobertura de
   imprensa (BR ou internacional) sobre uma BDR quase nunca menciona o
   ticker da B3 (ex: "MELI34") nem o nome legal completo, e sim o
   ticker/nome originais (MELI, MercadoLibre) ou o nome popular em
   português (Mercado Livre).

**Correção genérica** (não é um `if ticker == "MELI34"`):
- `_SUFIXO_JURIDICO` ganhou sufixos em inglês (Inc., Corp., Ltd., LLC,
  N.V., PLC, Co., AG, SE) + vírgula opcional antes do sufixo, com `\b`
  (limite de palavra) - **bug pego no próprio teste desta correção**: a
  primeira versão sem `\b` cortava "Unibanco" pra "Unibanc" (o "co" do
  final de "Unibanco" batia com o padrão solto "Co\.?" por não exigir
  fronteira de palavra) - corrigido antes de commitar.
- `_nome_curto` reescrito pra usar a MESMA extração de tokens do
  tokenizador de relevância (`_tokenizar`, regex `[a-z0-9]+`) em vez de
  `.split()` por espaço - garante que o "nome curto" comparado é sempre
  extraído do mesmo jeito que os tokens do título, eliminando essa
  classe inteira de bug de pontuação.
- `config.TICKER_ALIASES` (novo, dict genérico ticker->lista de aliases,
  mesmo padrão de `TICKER_NOME`): cadastrado pros BDRs mais comuns
  (MELI34, NFLX34, AAPL34, GOGL34, AMZO34, MSFT34, TSLA34, NVDC34,
  DISB34, COCA34) com ticker original + nome popular. Ticker sem entrada
  = comportamento idêntico a antes (nome do yfinance + ticker local).
- `obter_noticias` agora busca UM termo por alias (além do termo padrão
  nome+ticker), consolida os resultados por LINK (dedup) antes de seguir
  pro agrupamento/relevância normais - só retorna None se TODAS as
  buscas falharem (mais resiliente que antes: uma busca de alias falhar
  não derruba as outras).
- `_relevante` ganhou o parâmetro `aliases`: além do ticker/nome
  derivado do yfinance, aceita qualquer alias cadastrado cujas palavras
  apareçam TODAS no título (cobre nome de 2+ palavras tipo "Mercado
  Livre", que nunca bateria com o "nome curto" de 1 palavra só).

**Teste real, com dado de produção**: MELI34 passou de "nenhuma notícia"
pra 3 grupos reais e relevantes ("Mercado Livre (MELI34) vai vender
remédios...", etc.); ITUB4 passou de 0 (por causa do bug do truncamento
"Unibanc") pra notícia real encontrada; PETR4/VALE3 (sem alias, já
funcionavam) continuam idênticos - sem regressão. NFLX34/SMFT3/SBFG3
com 0 resultados **confirmados como corretos** (não é bug): rastreei a
cadeia inteira pro NFLX34 e vi 111 itens relevantes encontrados, TODOS
fora da janela de retenção de 5 dias (notícias de jan/abr/jul, nenhuma
recente - não há cobertura de Netflix nos últimos 5 dias agora mesmo).

- Arquivos: `data/prices.py`, `data/news.py`, `config.py`.
- Testes: `compileall` limpo; testes unitários diretos de
  `_limpar_sufixo_juridico`/`_nome_curto`/`_relevante` (scratchpad);
  `obter_noticias()` rodado de verdade pra MELI34, PETR4, VALE3, ITUB4,
  NFLX34, ALPA4 (os tickers que o Rodrigo pediu pra testar) contra rede
  real; AppTest EQUITY/RESEARCH/NEWS/TOP MERCADO sem exceção.
- Commit: enviado.

### P0.4 — Formatação/filtro de NEWS
- Filtro de ticker (aba NEWS) mostrava tickers fora da watchlist (achado
  real: WDOV26/WINV26 - código de contrato futuro, não ticker de ação).
  Corrigido com interseção explícita contra a watchlist do usuário.
- Manchete duplicando o ticker no prefixo (ex: "PETR4 · PETR4 vê alta")
  quando o título já começa citando o próprio ticker/empresa - corrigido
  em `_prefixo_tickers`: pula ticker que já aparece nos primeiros 40
  caracteres do título.
- Título "página de cotação/perfil" tipo "Alpargatas (ALPA4)" (achado
  real testando ALPA4: o Google News as vezes indexa a própria página de
  perfil de um agregador como se fosse notícia) - novo padrão
  `_PADRAO_SO_NOME_E_TICKER` filtra título que é SÓ "Nome (TICKER)" sem
  mais nada (nome curto, até 4 palavras, pra não filtrar por engano uma
  manchete de verdade que só COMECE citando a empresa).
- Janela de tempo (48h padrão, até 5 dias com "VER MAIS") agora
  explícita no caption da aba, como pedido.
- Arquivos: `ui/news_tab.py`, `data/news.py`.
- Testes: incluído no mesmo teste/commit da correção de MELI34 acima.
- Commit: enviado (junto com PRIORIDADE 1/2).

### P0.2/PRIORIDADE 3 — Mapa do Mercado: +NaN% e tooltip técnico
**Causa raiz do "+NaN%"**: `px.treemap` gera automaticamente os nós
agregados de setor/raiz (acima dos tickers individuais) calculando
sozinho um valor de "color" pra eles (média dos filhos) - em alguns
casos essa agregação automática vem indefinida, e o `texttemplate`
aplicado a TODO nó (raiz/setor/ticker) então mostrava "+NaN%" nos blocos
de setor/raiz especificamente (não nos tickers individuais, que sempre
tiveram valor real).

**Causa raiz do tooltip técnico**: o hover padrão do `px.treemap` mostra
os nomes das colunas do DataFrame literalmente (`labels=`, `tamanho=`,
`parent=`, `id=`, `variacao_pct=`) - não tinha `hovertemplate` customizado.

**Correção**: reescrito com `go.Treemap` direto (não `px.treemap`) -
cada nó (raiz "IBOVESPA", cada setor, cada ticker) é construído A MÃO
com id/label/parent/value/cor/texto/hovertext explícitos, sem nada
"automático" do Plotly. Isso elimina as duas causas de raiz ao mesmo
tempo: não há mais agregação automática indefinida (a cor de cada nó de
setor é calculada por mim, média simples da variação dos papéis do
setor, sempre um número real) nem hover automático (hovertext 100%
customizado, só com rótulos em português: "Variação", "Preço", "Volume
financeiro").

Também adicionado: legenda de cor (gradiente vermelho→cinza→verde com
os valores mín/máx do dia) abaixo do gráfico.

**Tamanho dos blocos**: mantido proporcional ao volume financeiro (sem
transformação/distorção) por decisão explícita - a dominância visual de
papéis como PETR4/VALE3 reflete concentração real de volume no
Ibovespa (fato do mercado, não bug de configuração do treemap). Se
quiser suavizar isso no futuro (ex: escala raiz quadrada), é uma
mudança de uma linha (`values=`) - não apliquei sem confirmação porque
alteraria o SIGNIFICADO do tamanho (deixaria de ser estritamente
proporcional ao volume).

- Arquivos: `ui/mercado_tab.py` (`_cor_treemap` novo, `_painel_treemap`
  reescrito), `data/mercado.py` (removida `obter_dados_treemap`, ficou
  órfã depois da reescrita - `ui/mercado_tab.py` agora usa
  `obter_panorama_ibovespa()` direto pra ter acesso a todos os campos).
- Testes: `compileall` limpo; script dedicado verificando que nenhum
  texto/hovertext gerado contém `NaN`/`None`/`Infinity`/nome técnico de
  campo (`labels=`, `parent=`, `id=`, `tamanho=`) nem cor hex inválida,
  rodado contra dado real (51 papéis, 18 setores); AppTest EQUITY/
  MERCADO/TOP MERCADO/CONFIG sem exceção.
- Commit: enviado.

### P4 — CVM ativada (outra sessão encerrada, assumida)
`data/cvm.py`/`ui/cvm_tab.py` (450+238 linhas, já prontos de outra
sessão) estavam sem commit. Confirmado que a outra sessão encerrou -
assumido, testado com dado real e commitado.

**Adaptação pra "sem tabela nova no Supabase"**: o código original criava
`cvm_documentos` (ver `sql/cvm.sql`, agora marcado como não usado).
Redirecionado pra reusar `research_itens` (mesma tabela do research
geral) - o schema já cobre tudo que um documento CVM precisa
(link/título/data/tipo/tickers/resumo), só `casa="CVM"` marca a origem.
`apagar_documentos_antigos` agora delega pro mecanismo throttled já
existente em `data/research/__init__.py` (1x/hora) em vez de rodar um
DELETE sem gate a cada render da EQUITY.

**Categoria nova, "Dados Econômico-Financeiros" (resultados
trimestrais/anuais)**: verificado contra o CSV real do IPE 2026 que essa
categoria da CVM mistura resultado financeiro de verdade
("Demonstrações Financeiras Intermediárias/Anuais/Adicionais",
"Press-release") com outras coisas (relatório de agente fiduciário,
relatório de agência de rating, laudo de avaliação) - filtrado só pelos
`Tipo` que são resultado de verdade, pra não poluir o painel RESULTADOS
com documento que não é sobre desempenho da empresa. Testado com dado
real: VALE3 trouxe "Desempenho da Vale no 2T26"/"1T26" corretamente.

**Selo CONFIRMADA em NEWS**: `SELO_CONFIRMADA` já existia como constante
reservada em `data/news.py` (nunca atribuída - claramente preparada de
antemão pra esta integração). `obter_noticias` agora chama
`cvm.documento_confirmador(ticker, titulo, data)` pra cada grupo -
se houver Fato Relevante/Comunicado ao Mercado da CVM com assunto
parecido (sobreposição de palavras ≥40%) e data a até 2 dias, o selo vira
CONFIRMADA (sobrescreve o score heurístico - uma confirmação oficial da
CVM é mais forte que qualquer regra de veículo/linguagem) e o card ganha
um link direto pro documento oficial. Só implementado no fluxo de
`obter_noticias` (NEWS + painel de EQUITY) - TOP MERCADO/`_processar_pool`
fica de fora por enquanto (grupos lá podem ter múltiplos tickers ou
nenhum, não é um encaixe natural pra "confirmar contra UM ticker").
Testado com mock (fonte da CVM não garante ter um match real disponível
na hora do teste) - selo/regra/link aplicados corretamente nos 3 grupos
de teste do PETR4.

**Painel CVM na EQUITY**: `render_cvm_ticker` (já existia, pronto) ligado
logo abaixo do painel de notícias.

**DIAGNÓSTICO DE FONTES**: nova entrada testando o download do IPE.

- Arquivos: `data/cvm.py`, `ui/cvm_tab.py`, `sql/cvm.sql` (marcado como
  não usado), `app.py`, `data/news.py`, `ui/news_tab.py`,
  `data/diagnostico.py`.
- Testes: `compileall` limpo; `obter_documentos_cvm` testado com dado
  real (PETR4: 271 docs, VALE3: 251 docs incluindo 23 de RESULTADOS,
  MELI34: 0 - correto, é BDR de empresa estrangeira sem registro CVM
  direto); `salvar_documentos`/`store.listar_itens(["CVM"])` testados
  end-to-end (grava e lê de volta de `research_itens` sem erro); selo
  CONFIRMADA testado com mock; AppTest EQUITY/NEWS/TOP MERCADO/CVM/
  CONFIG sem exceção.
- Commit: enviado.

### Resumos e acesso às matérias (NEWS/TOP MERCADO) — melhoria pedida
1. **Matéria curta ganhava "conteúdo muito curto" mesmo tendo texto
   real**: limiar mínimo de extração caiu de 200 pra 60 caracteres
   (`_MIN_CHARS_TEXTO`) — uma nota rápida de 1-2 parágrafos reais quase
   sempre passa disso. Prompt do resumo reescrito pra ser PROPORCIONAL
   ao tamanho do texto (2-3 linhas pra texto curto, até 8 pra texto
   longo) em vez de forçar sempre os 4 campos completos — testado com
   texto curto real: resultado saiu em 4 linhas, "não informado" nos
   campos sem base no texto, sem inventar conteúdo pra preencher.
2. **Combinação de fragmentos antes de desistir**: texto entre 15 e 60
   caracteres (curto demais sozinho, mas não vazio) agora é guardado
   como fragmento (`_MIN_CHARS_FRAGMENTO=15`) em vez de descartado; se
   NENHUMA fonte tiver texto longo o bastante sozinha mas houver 1+
   fragmento, combina todos os fragmentos + as manchetes do grupo
   (`_combinar_fragmentos`) numa única tentativa de resumo antes de cair
   pro fallback só-manchetes (já existente) — testado com 2 fragmentos
   curtos de fontes diferentes ("Ibovespa sobe 0,3%..." + "Dólar cai
   0,5%..."): combinou e gerou resumo correto num só resumo coerente.
3. **Acesso à matéria original**: botão "ABRIR MATÉRIA ↗" movido pro
   TOPO do card (antes só aparecia embaixo, depois do resumo carregar -
   agora aparece imediatamente, sem esperar o resumo); links por veículo
   («Veículos (N)») ganharam o ícone ↗ (já abriam em nova aba, só
   faltava o sinal visual). Ícone ↗ por linha na lista já existia (feito
   na correção urgente anterior desta sessão).
4. **Medição real (20 itens, amostra do TOP MERCADO)**: 15/20 (75%) de
   sucesso na medição - MAS as 5 falhas foram TODAS por `motivo=cota`
   (limite de taxa do Groq free-tier, batido por rodar 20 resumos em
   sequência rápida num script de teste - não acontece no uso real,
   onde o usuário pede resumo um de cada vez ao clicar) - **nenhuma
   falha foi por conteúdo curto/indisponível**, que era o problema que
   esta melhoria visava resolver. Ou seja: 100% das falhas restantes
   são de cota da API, não de extração de conteúdo.
- Arquivos: `data/news.py`, `ui/news_tab.py`.
- Testes: `compileall` limpo; testes diretos do caso de fragmento
  combinado e do caso de texto curto proporcional (scratchpad, com
  mock); AppTest EQUITY/NEWS/TOP MERCADO sem exceção; teste dirigido
  clicando manchete real e confirmando que "ABRIR MATÉRIA" aparece no
  topo do card; medição de 20 itens contra dado real.
- Commit: enviado.

## REDESIGN DO TERMINAL — ETAPA 1 (fundação)
Plano completo em `C:\Users\Dell\.claude\plans\mutable-meandering-peacock.md`
(auditoria + roadmap das etapas 2-8). Etapa 1 concluída:

### 1. Reset de zoom universal
`ui/graficos.py` (novo): `zoom_key(chave_base, *partes_estado)` renderiza
um botão "↺" pequeno e retorna uma `key=` pro `st.plotly_chart` — a key
muda tanto quando o usuário clica no botão quanto quando qualquer
`partes_estado` passado muda (ticker, período, tipo de gráfico etc),
forçando o Streamlit a remontar o componente do zero (= reset de zoom)
nos dois casos, sem coleta de dado nova. Aplicado nos 7 gráficos Plotly
existentes: EQUITY (preço/candlestick + comparação com IBOV, em
`app.py`), MACRO (curva pré, IPCA, Selic×CDI, em `ui/macro_tab.py`),
MERCADO (setorial, treemap, em `ui/mercado_tab.py`).

**Achado da auditoria**: nenhum desses gráficos passava `key=` antes -
é por isso que trocar de ticker/período não resetava o zoom (Streamlit
mantém o estado do componente, incluindo zoom, quando a key não muda,
mesmo com dado novo por baixo). Duplo clique pra reset é comportamento
nativo do Plotly (não depende de `displayModeBar`, que continua
desligado de propósito) - não precisou de código extra.

### 2. Busca/autocomplete de ativo (TickerAutocomplete)
`ui/busca.py` (novo): `buscar_ativo()` usa `st.selectbox` com busca
nativa (filtra por substring ao digitar, ↑/↓/Enter/Esc de graça, zero
chamada de rede por tecla) sobre um universo curado
(`config.IBOVESPA_COMPOSICAO` + `config.TICKER_ALIASES` + watchlist
atual). Substitui o `st.text_input` cru (exigia ticker exato) na
sidebar "adicionar ticker" - mantém um `st.expander` com o fluxo manual
antigo pra ticker fora da lista curada (nunca perde a capacidade de
adicionar qualquer ticker válido, só fica mais rápido pros mais
comuns).

**Bug de performance pego ANTES de commitar** (rodei a função isolada
antes de integrar): a primeira versão buscava o nome de cada ticker via
`obter_nome_yf` (1 chamada de yfinance por ticker) pra montar a lista -
pros ~74 tickers do universo, isso levou mais de 30 segundos só pra
montar as opções, violando a própria regra do pedido ("não fazer
request a cada tecla... usar lote"). Corrigido com
`config.NOMES_ATIVOS_BUSCA` (novo, estático - nomes comuns das empresas
mais conhecidas do Ibovespa + BDRs, curados manualmente, zero chamada
de rede). Depois da correção: função roda em memória, praticamente
instantânea (testado).

### 3. Sweep de NaN/None residual
Verificação (sem mudança de código - já estava tudo coberto pelos
ajustes desta sessão: P0.1 indicadores, T7 comparativo, correção do
treemap): toda formatação numérica em `app.py`, `ui/macro_tab.py`,
`ui/mercado_tab.py`, `ui/research_tab.py` passa por um helper
None-safe (`_fmt`, `_num_ou_traco`, ternário explícito) ou opera sobre
um valor estruturalmente garantido não-None (filtrado antes). `ui/cvm_tab.py`/
`ui/top_mercado_tab.py`/`data/mercado.py` não fazem formatação numérica
direta nenhuma. Nenhum ponto residual encontrado.

**Limitação conhecida**: interação de mouse/teclado (zoom real, duplo
clique, digitar na busca) não é verificável só por AppTest - e o
PREGÃO usa login Google real (`st.login()`), que eu não consigo
completar sem as credenciais do Rodrigo, então não dá pra testar isso
num browser de verdade a partir daqui. Verificado por AppTest: botão de
reset existe e não quebra ao clicar; busca tem as 74 opções esperadas;
selecionar + adicionar um ticker funciona ponta a ponta. **Pendente**:
Rodrigo conferir visualmente (zoom, duplo clique, digitação na busca)
na próxima vez que abrir o app.

- Arquivos: `ui/graficos.py` (novo), `ui/busca.py` (novo), `config.py`
  (`NOMES_ATIVOS_BUSCA`), `app.py`, `ui/macro_tab.py`, `ui/mercado_tab.py`.
- Testes: `compileall` limpo a cada commit; AppTest EQUITY/MACRO/
  MERCADO/CONFIG sem exceção; teste dirigido de clique no botão de
  reset e de seleção+adição via a busca.
- Commits: enviados (3 - zoom, busca, e este registro).

## REDESIGN DO TERMINAL — ETAPA 2 (VISÃO GERAL)
Nova aba "0 VISÃO GERAL" (`ui/visao_geral.py`, novo), agora a home/
landing padrão do app. **Zero coleta de dado nova** - cada bloco chama
direto uma função já existente (mesmo cache):
- MERCADO AGORA: cards IBOV/DÓLAR/DI(CDI anualizado)/S&P 500/NASDAQ/
  PETR4/VALE3 (`obter_cotacao_indice`, `obter_cdi`, `obter_mercados_globais`,
  `obter_cotacao` - todas já usadas em outras abas).
- Gráfico do IBOV com seletor de período e reset de zoom
  (`obter_historico` + `ui/graficos.py`, mesmo mecanismo da ETAPA 1).
- Altas/baixas, mais negociados, desempenho setorial: reaproveita
  `_painel_altas_baixas`/`_painel_mais_negociados`/`_painel_setorial`
  de `ui/mercado_tab.py` DIRETO (mesmas funções, sem cópia de lógica).
- Notícias: `obter_top_mercado_tudo()` + `_renderizar_lista()` de
  `ui/news_tab.py` (mesmo componente do TOP MERCADO), limitado a 8 itens.
- Mercados globais: reaproveita `_painel_globais` de `ui/mercado_tab.py`.
- Watchlist compacta: nova (tabela simples ticker/preço/variação).

**Renumeração da navegação**: pedido explícito foi "0 VISÃO GERAL, 1
EQUITY, 2 MACRO, 3 RESEARCH, 4 NEWS, 5 CVM, 6 TOP MERCADO, 7 MERCADO, 8
CONFIG, 9 SISTEMA" - `app.py` mudou de `enumerate(secoes)` com `+1`
pra sem offset (0-based), e `config.ABAS_DISPONIVEIS` foi reordenado
(CVM antes de TOP MERCADO/MERCADO) pra bater exatamente com essa ordem.
VISÃO GERAL como primeiro item também a torna a aba padrão ao abrir o
app (usa o mecanismo de `_escolha_estavel` que já pega `rotulos_secao[0]`
como padrão - sem código novo pra isso).

**Achado do teste**: meu próprio harness de AppTest (scratchpad, fora
do repo) tinha uma suposição implícita de que EQUITY sempre era a aba
padrão (pulava re-testar "1 EQUITY" assumindo que a primeira renderização
já cobria isso) - corrigido o script de teste antes de confiar no
resultado, porque com VISÃO GERAL virando a nova padrão essa suposição
ficou errada e mascarava EQUITY não sendo testado de verdade.

- Arquivos: `ui/visao_geral.py` (novo), `app.py`, `config.py`.
- Testes: `compileall` limpo; AppTest em TODAS as 9 seções (0-8, mais
  CONFIG) sem exceção, incluindo a landing padrão; conferido via
  `at.markdown` que os 7 painéis da VISÃO GERAL renderizam de verdade
  (não só "sem exceção").
- Commit: enviado.

## REDESIGN DO TERMINAL — ETAPA 3 (MACRO)
Plano completo em `C:\Users\Dell\.claude\plans\mutable-meandering-peacock.md`.
Escopo da etapa: expectativas Focus em tabela multi-ano, cenário global.
Agenda econômica/próxima reunião do Copom ficam de fora (sem fonte de
calendário confiável — mesmo princípio já aplicado nas lives da Genial e
no resto do projeto: não inventar dado).

### 1. Focus multi-ano
`data/macro.py`: `_focus_ano_atual_e_seguinte` generalizada pra
`_focus_multi_ano(indicador, quantidade_anos=3)` — mesmo request por ano
de antes (1 por indicador/ano), só passou a pedir 3 anos em vez de 2.
`obter_focus_ipca`/`obter_focus_selic` (mesma assinatura, sem breaking
change pros chamadores) agora retornam ano atual + dois seguintes.
`ui/macro_tab.py`: `_linha_focus` e o `colspan` da tabela generalizados
pra `QUANTIDADE_ANOS_FOCUS=3` em vez de hardcoded 2.

### 2. Painel CENÁRIO GLOBAL (novo)
`config.CENARIO_GLOBAL` (novo, mesmo padrão de `INDICES_GLOBAIS`): ouro
(`GC=F`), Brent (`BZ=F`), WTI (`CL=F`), minério de ferro (`TIO=F` —
futuro SGX TSI CFR China), Treasuries 10 anos (`^TNX`) e VIX (`^VIX`).

**Verificação antes de codar** (a preocupação do plano original era se o
yfinance cobria minério de ferro): testado os 6 tickers contra dado real
— todos retornaram preço válido, inclusive `TIO=F`. `^TNX` confirmado
como já vindo em % a.a. direto (histórico de 1 mês variando 4.6-5.2, sem
precisar dividir por 10 como o índice CBOE tradicional sugeriria).

`data/macro.py:obter_cenario_global()` reusa `_baixar_lote_bruto`/
`_linha_papel` de `data/mercado.py` (import direto dos helpers privados,
mesmo padrão já usado em `data/diagnostico.py` pra `data/news.py`) — sem
duplicar a lógica de lote/cálculo de variação. `ui/macro_tab.py`:
`_painel_cenario_global` (mesmo layout de cards do `_painel_globais` da
aba MERCADO), registrado em `REGISTRO_PAINEIS` (reordenável em CONFIG).

- Arquivos: `config.py` (`CENARIO_GLOBAL`), `data/macro.py`
  (`obter_cenario_global`, `_focus_multi_ano`), `ui/macro_tab.py`
  (`_painel_cenario_global`, `_linha_focus` generalizada).
- Testes: `compileall` limpo; `obter_cenario_global`/`obter_focus_ipca`/
  `obter_focus_selic` rodados contra dado real (6/6 itens do cenário
  global com preço+variação válidos; Focus IPCA/Selic com 3 anos cada,
  2026/2027/2028); AppTest em todas as 9 seções (VISÃO GERAL, EQUITY,
  MACRO, RESEARCH, NEWS, CVM, TOP MERCADO, MERCADO, CONFIG — instância
  nova por aba, sem exceção); conferido via `at.markdown` que "CENÁRIO
  GLOBAL" e "FOCUS IPCA" aparecem de verdade no HTML da aba MACRO (não
  só "sem exceção").
- Commit: enviado.

## REDESIGN DO TERMINAL — ETAPA 4 (EQUITY)
Plano completo em `C:\Users\Dell\.claude\plans\mutable-meandering-peacock.md`.
Escopo da etapa: fundamentos (ROE/ROIC/margens/dívida líquida) na medida
em que `tk.info` do yfinance cobrir de verdade — campo a campo, o que
não existir fica de fora em vez de inventado (regra já seguida em toda
outra fonte do projeto).

**Auditoria de campos** (testado contra dado real: PETR4, VALE3, ITUB4,
MELI34, cobrindo blue chip, mineradora, banco e BDR — perfis bem
diferentes de propósito): `returnOnEquity` disponível pros 4;
`profitMargins`/`operatingMargins` disponíveis pros 4; `ebitdaMargins`
disponível pra 3/4 (bancos não têm); `totalDebt`/`totalCash` disponíveis
pros 4; nenhum campo equivalente a ROIC em lugar nenhum do `.info`
(conferido também buscando por "capital"/"invest"/"roic" em todas as
~165 chaves retornadas).

**Decisão — ROIC fica de fora**: sem campo direto no `tk.info`,
calculá-lo exigiria montar capital investido (dívida + patrimônio -
caixa) e taxa efetiva de imposto a partir de outros relatórios
(balanço/DRE) - isso é estimativa, não dado reportado. Mesmo princípio
de "nunca inventar dado" já aplicado em toda outra fonte do projeto
(agenda econômica, lives da Genial etc.) - decidido não implementar em
vez de aproximar.

**Bug real pego no teste**: `ebitdaMargins` (e outras margens baseadas
em custo de produtos vendidos) vêm `0.0` do yfinance pra ITUB4 (banco) -
não é `None`, é `0.0` literal. Não é margem zero de verdade: bancos não
têm o conceito contábil de EBITDA/COGS que essas margens pressupõem.
Mostrar "0,00%" seria enganoso (parece que a margem é zero, quando na
real o dado simplesmente não existe pra esse tipo de empresa).
Corrigido com `_pct_ou_none()` (`data/prices.py`), que trata `None` E
`0.0` como ausência de dado nesses campos específicos.

**Implementação**: `data/prices.py:obter_indicadores()` ganhou 6 campos
novos (`roe`, `margem_liquida`, `margem_operacional`, `margem_ebitda`,
`divida_liquida`, `divida_liquida_ebitda`) - reusa o mesmo `info` já
buscado (sem chamada extra ao Yahoo) e o mesmo mecanismo de fallback
pro último valor válido (`_ultimo_indicadores_valido`) já existente.
Dívida líquida = `totalDebt - totalCash` (cálculo direto de dois campos
reais, mesmo padrão do juro real em `data/macro.py`). Dívida
líquida/EBITDA só calculado quando ambos existem e EBITDA > 0.
`app.py`: segunda tabela dentro do painel INDICADORES (mesmo
container/estilo, sem painel novo), com tooltips explicando cada campo
e a ressalva de bancos/seguradoras sem margem EBITDA.

- Arquivos: `data/prices.py` (`obter_indicadores`, `_pct_ou_none` novo),
  `app.py` (painel INDICADORES, segunda tabela FUNDAMENTOS).
- Testes: `compileall` limpo; `obter_indicadores()` rodado contra dado
  real pros 4 tickers de teste, valores conferidos um a um (incluindo o
  `None` correto pra margem EBITDA do ITUB4); AppTest em todas as 9
  seções (instância nova por aba, sem exceção); conferido via
  `at.markdown` que ROE/MARGEM LÍQUIDA/MARGEM OPERACIONAL/MARGEM EBITDA/
  DÍVIDA LÍQUIDA aparecem de verdade no HTML da aba EQUITY.
- Commit: enviado.

## UPGRADE ABA CVM (pedido explícito do Rodrigo, 2026-09-25)
Pedido pontual e detalhado do Rodrigo, fora da ordem do roadmap de
redesign (ETAPA 5 seria a próxima, mas este pedido tem prioridade
explícita e escopo isolado). Escopo: só a aba CVM do Pregão - não
confundir com o TVB Radar (problema de rerender/scroll de filtros
mencionado no pedido é de outro projeto, não tratado aqui).

**Investigação antes de mexer** (pedida explicitamente no prompt):
- Coleta: `data/cvm.py` já baixa o IPE (CSV da CVM) 1x por ano,
  cacheado 6h (`_ipe_ano`, `st.cache_data`), filtra em memória por CNPJ.
- Armazenamento: reusa `research_itens` no Supabase (mesma tabela do
  research geral, `casa="CVM"`).
- Filtros: já operavam 100% em memória sobre `documentos` (lista já
  coletada) - trocar ticker/tipo NUNCA disparava nova consulta à CVM.
  Confirmado que a arquitetura pedida no item 10 do prompt ("nunca
  reconsultar a CVM ao filtrar") já existia - não precisou de mudança
  em `data/cvm.py`.
- Renderização: `ui/cvm_tab.py`, uma linha por documento via
  `st.columns()`, sem cabeçalho de coluna.
- Cache: confirmado acima (`_TTL_DOCUMENTOS=6h`, `_TTL_MAPA_TICKER=24h`).
- Abertura de documento: `st.dialog` com resumo sob demanda (Groq) + link
  pro documento original - já funcionava, preservado sem mudança de
  fluxo.

**Achado real (causa raiz do "conteúdo cortado à direita")**:
`_COLS = [88, 62, 118, 1]` em `st.columns()` - esses números são PESOS
RELATIVOS entre si, não pixels. A coluna de assunto recebia 1/269 da
largura total (~0,4%), o oposto do que o comentário antigo dizia
("peso relativo, cresce pra preencher"). Corrigido pra `[9, 8, 16, 55]`
(assunto ≈62% da largura útil).

**Implementado** (`ui/cvm_tab.py`, reescrito):
1. Colunas redistribuídas (ver achado acima) + cabeçalho de tabela novo
   (DATA/TICKER/TIPO/DOCUMENTO-ASSUNTO com divisor), que não existia.
2. Busca textual (`st.text_input`, placeholder "Buscar documentos..."),
   normalizada (sem acento/caixa), procura em ticker+assunto+tipo_label+
   categoria_original, combinada via AND com os pills de ticker/tipo.
3. Paginação real substituindo o "VER MAIS" incremental: 50/página,
   `‹ Anterior` / janela de números ao redor da página atual (±2) +
   primeira/última sempre visíveis com "…" nos buracos / `Próxima ›`.
   Página reseta pra 1 quando o fingerprint do filtro (ticker, tipo,
   busca) muda - sem isso, trocar de filtro com a página 3 selecionada
   podia renderizar uma página vazia.
4. Removida a janela automática de 30 dias + "ver mais pra expandir":
   com paginação de verdade e ordenação por data desc, os documentos
   mais recentes já aparecem primeiro na página 1 sem precisar de uma
   heurística de janela escondida - simplifica o modelo mental (o
   contador mostra o total real, não "total dentro de 30 dias").
5. Hover de linha: cada linha virou um `st.container(key=f"cvm-row-...")`
   de verdade (antes eram só `st.columns()` soltas, sem contêiner
   compartilhado) - permite `div[class*="st-key-cvm-row-"]:hover` com
   highlight de fundo sutil, indicando que a linha é clicável.
6. Badges (`_CLASSE_TIPO`) com padding/alinhamento mais consistentes,
   mesmas duas classes de antes (destaque laranja pra FATO RELEVANTE,
   outline cinza pro resto) - só polimento visual, sem mudar a lógica.
7. Contador reformatado: "N resultados · M documentos" quando há
   filtro/busca ativo, só "M documentos" quando não há (evita
   redundância tipo "653 resultados · 653 documentos").
8. Descrição da aba compactada: parágrafo longo (4 linhas) virou duas
   linhas curtas (principal + secundária "Atualização periódica · dados
   públicos da CVM").

**Bug de implementação pego e corrigido antes de testar**: a primeira
versão tentava envolver a paginação num `<div class="cvm-paginacao">`
aberto num `st.markdown()` e fechado em outro `st.markdown()` separado,
esperando que o flexbox se aplicasse aos `st.columns()`/botões
renderizados no meio - não funciona (cada `st.markdown` isola seu HTML
num container próprio; uma tag aberta num não "vaza" pro próximo). Não
chegou a ser commitado - corrigido antes do primeiro teste, trocando
pelo padrão correto (`st.container(key=...)`, que de fato agrupa os
elementos renderizados dentro do `with` num container real do DOM).

- Arquivos: `ui/cvm_tab.py` (reescrito). `data/cvm.py` sem mudanças.
- Testes: `compileall` limpo; AppTest em todas as 9 seções (instância
  nova por aba) sem exceção; teste dirigido da CVM (scratchpad) cobrindo
  contra dado real (653 documentos de PETR4+VALE3+ITUB4, mesmo número
  citado no pedido original do Rodrigo como exemplo, coincidência
  confirmada): carga inicial (653), filtro ticker=PETR4 (271), +
  tipo=FATO_RELEVANTE (37), + busca "acionista" (8), reset pra TODOS
  (volta a 653, página volta a 1), paginação (Próxima avança pra página
  2), abertura de documento (dialog abre e carrega resumo).
- **Validação visual pendente**: a extensão Chrome não conectou nesta
  sessão (`tabs_context_mcp` retornou "extension not connected" duas
  vezes) - não deu pra confirmar visualmente layout/cores/responsividade
  num navegador de verdade. Rodrigo pediu pra commitar sem esperar por
  isso; ficou um preview isolado testado localmente
  (`streamlit run` apontando direto pra `render_cvm()`, fora do repo,
  sem tocar em `auth.py`/login) que confirmou o servidor sobe e responde
  HTTP 200, mas sem inspeção visual de verdade. Conferir na prática
  (1366px, 1920px, tela menor) na próxima vez que abrir o app.
- Commit: enviado.

## UPGRADE TELA INICIAL/LOGIN (pedido explícito do Rodrigo, 2026-09-25)
Pedido pontual, escopo isolado na tela de apresentação (sem login) -
`auth.py:tela_apresentacao()`. Explicitamente proibido mexer em
OAuth/sessão/permissões/banco/rotas/outras abas - só a apresentação
visual dessa tela.

**Diagnóstico do estado anterior**: `tela_apresentacao()` tinha só logo
+ um parágrafo longo (4 linhas, texto corrido) + botão - o "bloco
central parecia um placeholder" (queixa literal do Rodrigo), com bastante
área preta vazia embaixo sem uso.

**Implementado** (`auth.py`, reescrito):
1. Hero: título "SEU TERMINAL DE MERCADO." (com cursor piscando via CSS
   `@keyframes`, efeito bem sutil) + subtítulo curto + microcopy
   ("DADOS PÚBLICOS · ATUALIZAÇÃO PERIÓDICA · 100% GRATUITO") -
   substitui o parágrafo longo anterior.
2. Linha de tags minimalista (bullet laranja + label cinza uppercase):
   B3 · MACRO · JUROS · NEWS · RESEARCH · CVM.
3. Prévia ilustrativa do terminal: caixa com borda (mesmo padrão visual
   dos painéis do resto do app) mostrando IBOVESPA/DÓLAR no topo, mini
   grid PETR4/VALE3/ITUB4/JUROS, e "ÚLTIMAS NOTÍCIAS" com 2 manchetes
   mock. Rotulada "PRÉVIA ILUSTRATIVA" no canto superior da caixa -
   **decisão deliberada de não buscar dado real aqui** (ver abaixo).
4. Botão "ENTRAR COM GOOGLE" com ícone "G" oficial (SVG 4 cores,
   embutido como data URI base64 direto no CSS via `::before` no botão -
   `st.button` só aceita texto simples no label, não HTML/ícone, então o
   ícone entra via CSS puro, sem depender de request externo/CDN numa
   tela que roda antes de qualquer coisa carregar), largura máxima
   320px (não "gigante"), hover discreto (borda muda pra laranja).
   Microcopy abaixo: "Acesso gratuito · Entre com sua conta Google para
   acessar o terminal."
5. Fade-in sutil (`@keyframes`, opacity+translateY, 0.45s) no painel
   inteiro ao carregar - única animação, sem partículas/efeitos.

**Decisão — prévia com dado ilustrativo, não real**: o pedido permitia
explicitamente ("não precisa ser dado real, se for simples reusar
melhor ainda"). Decidido NÃO buscar cotação real aqui porque essa tela
carrega ANTES de qualquer login - toda visita anônima (incl. bots/
crawlers) dispararia uma chamada de rede ao Yahoo Finance sem nenhum
gate de usuário/cache por sessão, o oposto do princípio de "evitar
request desnecessária" já seguido no resto do projeto (ver decisão
equivalente na aba CVM). Resolvido com dado estático rotulado
"PRÉVIA ILUSTRATIVA" - explícito que não é live, sem fingir ser dado
real (mesmo princípio de nunca inventar dado, aplicado aqui como "nunca
disfarçar ilustração de dado real").

**Bug pego e corrigido ANTES de testar** (mesma classe de erro já visto
no upgrade da aba CVM nesta mesma sessão): a primeira versão tentava
abrir `<div class="login-wrap">` num `st.markdown()` e fechar em outro
mais adiante (depois do botão nativo) - não funciona, cada `st.markdown`
isola seu HTML. Corrigido usando `st.container(border=True,
key="login-panel")` (que já existia pro painel, só faltava o `key=`) pra
aplicar a animação de fade-in via CSS no container real, e removendo os
dois `<div>` órfãos de abertura/fechamento em vez de tentar consertá-los
- o texto "Acesso gratuito..." abaixo do botão já centraliza sozinho
via `text-align:center` na própria classe, sem precisar de wrapper.

- Arquivos: `auth.py` (reescrito).
- Testes: `compileall` limpo; AppTest da tela SEM mock de autenticação
  (testa o caminho real de visitante anônimo, não o de usuário logado)
  confirma render sem exceção e presença de hero/tags/prévia/botão no
  HTML; AppTest nas 9 seções autenticadas (instância nova por aba) sem
  exceção, confirmando que nada fora do escopo quebrou.
- **Validação visual pendente**: extensão Chrome não conectou nesta
  sessão (confirmado pelo Rodrigo: "a extensão do chrome n funciona") -
  não deu pra confirmar visualmente hero/prévia/botão/responsividade
  num navegador de verdade. Commitado sem essa confirmação, a pedido
  dele (mesmo padrão já aceito no upgrade da aba CVM, mesma sessão).
  Conferir na prática (1366px, 1920px, tela menor) na próxima vez que
  abrir o app deslogado.
- Commit: enviado.

## ETAPA 5 (CVM) — bloco de destaques (2026-09-25)
Fecha o item que restava da ETAPA 5 do roadmap ("CVM: filtros mais
granulares, bloco de destaques") — filtros/busca já tinham sido cobertos
no upgrade pontual anterior da aba CVM (mesma sessão). Continuação
natural pedida pelo próprio Rodrigo ("continua, oq você acha que
podemos melhorar").

**Implementado** (`ui/cvm_tab.py`): `_painel_destaques(documentos)`,
chamado logo após a descrição da aba, antes da busca/filtros - roda
sobre a lista COMPLETA de documentos (não filtrada), então sempre mostra
o pulso real da watchlist, independente do que o usuário filtrar depois.
Três campos, layout de linha única (flex, sem cards):
1. Fatos relevantes nos últimos 30 dias (`_JANELA_DESTAQUES_DIAS`).
2. Ticker mais ativo no mesmo período (`collections.Counter` sobre
   `d["ticker"]`) - com fallback pro conjunto completo se não houver
   nenhum documento dentro da janela (evita `Counter` vazio).
3. Último documento recebido (`documentos[0]` - já vem ordenado por
   data desc de `obter_documentos_watchlist`, sem novo sort).

- Arquivos: `ui/cvm_tab.py`.
- Testes: `compileall` limpo; teste dirigido (scratchpad) confirmando
  contra dado real: 1 fato relevante/30 dias, PETR4 mais ativo (6 docs),
  último documento 19/09/2026 (PETR4, COMUNICADO); reteste completo dos
  7 cenários da CVM (carga inicial, filtro ticker, filtro ticker+tipo,
  busca combinada, reset, paginação, abertura de documento) sem
  regressão; AppTest nas 9 seções sem exceção.
- Commit: enviado.

## ETAPA 6 (NEWS/RESEARCH/TOP MERCADO) — filtros do RESEARCH (2026-09-25)
Continuação do roadmap ("continua, oq você acha que podemos melhorar" -
Rodrigo delegou a escolha). Auditoria das 3 abas do escopo:

- **NEWS/TOP MERCADO**: já muito polidas (várias rodadas de correção em
  sessões anteriores - performance com `@st.fragment`, agrupamento por
  entidade, formatação, tooltip cobrindo dialog, BDR). Nenhum achado
  novo que justifique mudança agora - `_COLS_PADRAO`/`_COLS_RANK` já têm
  pesos corretos (manchete domina a largura), diferente do bug real que
  a CVM tinha.
- **RESEARCH**: único achado real - filtros de Casa/Tipo (`st.multiselect`)
  e Ticker (`st.selectbox`) usam os componentes genéricos do Streamlit,
  visualmente destoando do padrão de pills (`st.pills`) usado em TODAS
  as outras abas com filtro (CVM, NEWS, TOP MERCADO, MERCADO).

**Implementado** (`ui/research_tab.py`):
- Casa/Tipo: `st.multiselect` → `st.pills(selection_mode="multi")`,
  mesmo `default=`(lista completa, tudo selecionado) de antes.
- Ticker: `st.selectbox` → `st.pills(selection_mode="single")` com
  "Todos" como opção, mesmo padrão de CVM/NEWS.
- Lógica de filtro (`r["casa"] in filtro_casa`, etc.) **intocada** - só
  o widget mudou, o formato do valor retornado (lista pra multi, string
  pra single) é o mesmo dos widgets antigos.
- `_injetar_css()` novo (módulo não tinha CSS próprio antes) só com a
  regra de `flex-wrap` nos grupos de pills - mesma regra já usada em
  `ui/news_tab.py`/`ui/cvm_tab.py`, preventiva contra estouro de largura
  com Tipo (até 6 opções) numa coluna de 1/3.

- Arquivos: `ui/research_tab.py`.
- Testes: `compileall` limpo; **Genial e XP bloqueadas neste sandbox**
  (mesma limitação de sempre, documentada em várias sessões) - feed real
  vem vazio aqui, então testei com `preparar_leitura` mockado
  (`unittest.mock.patch.object`, 3 relatórios sintéticos, 2 casas, 2
  tipos, 2 tickers): confirmado que Casa/Tipo vêm com tudo pré-selecionado
  (mesmo comportamento do multiselect antigo), filtro por casa
  (3→2 relatórios) e por ticker (→1 relatório) funcionam corretamente;
  AppTest nas 9 seções sem exceção.
- Commit: enviado.

## ETAPA 7 — layout configurável: visibilidade + tamanho (2026-09-25)
Continuação do roadmap ("bora"). Reautoriza e estende o T5 original
(FILA2-T5, que só cobria reordenar) com visibilidade + tamanho por
painel, escopo já reduzido no próprio plano do redesign pra evitar
drag-and-resize de verdade (sem componente de terceiros).

**Achado da auditoria antes de implementar**: o plano original assumia
"páginas novas (Etapas 2-6) já estarem com seus painéis registrados no
mesmo sistema" - **isso não é verdade**. Só MACRO e MERCADO usam
`ui/paineis.py` (`REGISTRO_PAINEIS` + `paineis.renderizar`); EQUITY,
CVM, NEWS, RESEARCH, TOP MERCADO e VISÃO GERAL renderizam do jeito
monolítico de sempre. Migrar todas pra esse sistema é um refactor bem
maior (cada painel precisaria funcionar dentro de uma coluna mais
estreita, ex: gráficos Plotly com largura menor) - decidido NÃO fazer
isso nesta rodada (risco alto de regredir abas já estáveis, fora do
espírito "ajuste pontual"). Escopo final: MACRO e MERCADO, as duas que
já tinham a base pronta.

**Implementado** (`ui/paineis.py`):
- `TAMANHOS = ["1/4", "1/2", "3/4", "FULL"]` + `_FRACOES` (mapa pra
  peso de `st.columns`).
- `_pid_visivel_salvo`/`_tamanho_efetivo`: mesma convenção já usada em
  `ordem_efetiva` (nada salvo = comportamento padrão, ou seja, tudo
  visível/FULL - zero mudança pra quem nunca mexeu em CONFIG).
- `_empacotar_linhas`: greedy, soma frações na ordem escolhida até
  estourar 1.0, aí começa linha nova. Painel FULL (1.0) sempre sozinho
  na própria linha (a soma já estoura com ele sozinho).
- `renderizar()` reescrito pra usar o empacotamento - caso especial
  (1 painel, FULL): continua usando `st.container(border=True)` direto,
  SEM envolver num `st.columns([1.0])` desnecessário - garante que quem
  nunca configurou nada tem o DOM idêntico a antes (zero risco visual).
- `controle_layout_config` (novo): uma linha por painel (checkbox de
  visibilidade + pills de tamanho), pra usar em CONFIG logo após
  `controle_ordem_config`. `st.pills` dentro de `st.form` testado e
  confirmado funcionando nesta versão do Streamlit antes de usar (não é
  óbvio - `st.button` normal é proibido dentro de forms, então testei
  `st.pills` isolado antes de depender disso).

**Decisão - esconder tudo é permitido**: diferente do `ordem_paineis`
(seleção vazia = acidente, volta pro padrão), uma lista de painéis
visíveis vazia é tratada como escolha deliberada (exigiria desmarcar
várias checkboxes uma a uma, não é um "limpar sem querer" como o
multiselect de ordem) - `renderizar()` mostra um aviso de uma linha em
vez de tela em branco silenciosa nesse caso.

- Arquivos: `ui/paineis.py`, `config.py` (`PREFS_PADRAO`), `app.py`
  (formulário de CONFIG).
- Testes: `compileall` limpo; testes unitários diretos de
  `_empacotar_linhas` (mix de frações, inclusive FULL forçando linha
  nova) e de `_pid_visivel_salvo`/`_tamanho_efetivo` (com e sem config
  salva); teste end-to-end via AppTest: achou os 4 checkboxes+pills de
  MACRO em CONFIG, desmarcou 1 painel e mudou outro pra 1/2, salvou o
  formulário, confirmou `prefs["paineis_visiveis"]["MACRO"]` e
  `prefs["tamanho_paineis"]["MACRO"]` gravados corretos, reabriu MACRO e
  confirmou que renderiza sem exceção com o layout customizado; AppTest
  nas 9 seções sem exceção (garantindo que MACRO/MERCADO sem config
  continuam idênticas).
- Commit: enviado.

## Correção urgente — KeyError('roe') em produção (2026-09-25)
Rodrigo reportou erro ao vivo em produção: `KeyError: 'roe'`, traceback
apontando `app.py` linha 540 (tabela FUNDAMENTOS, ETAPA 4). Pausou a
ETAPA 8 (busca global) pra investigar na hora.

**Causa raiz**: `data/prices.py:_ultimo_indicadores_valido()` é
`@st.cache_resource` - o objeto (dict) sobrevive entre deploys DENTRO
do mesmo processo do Streamlit Cloud (cache de recurso, não de sessão -
não é limpo a cada `git push`, só quando o processo reinicia de
verdade). Um valor gravado nesse cache ANTES da ETAPA 4 (schema antigo:
só `valor_mercado`/`pl`/`pvp`/`dividend_yield`/`beta`) continuou vivo na
memória; quando a coleta do momento falhava (Yahoo bloqueado/lento) e
`obter_indicadores()` caía no fallback (`{**anterior, "beta":
resultado["beta"]}`), o dict retornado tinha o formato ANTIGO - sem
`roe`/`margem_liquida`/`margem_operacional`/`margem_ebitda`/
`divida_liquida`/`divida_liquida_ebitda`. `app.py` acessa esses campos
com colchete (`ind['roe']`, não `.get()`) - quebrou com `KeyError`.

**Reproduzido antes de corrigir**: script direto simulando um cache
`_ultimo_indicadores_valido()['FAKE9']` no formato antigo (5 campos) +
`_tk_info_com_retry` forçado a retornar vazio (simula coleta falhando) -
confirmado `KeyError: 'roe'` batendo exatamente como no traceback do
Rodrigo.

**Correção**: a mesclagem do fallback inverteu a ordem - antes começava
de `anterior` e só sobrescrevia `beta`; agora começa de `resultado`
(schema ATUAL, todas as chaves de hoje, valores `None`) e sobrescreve
com o que `anterior` realmente tiver, então `beta` de novo por cima.
Resultado: todas as chaves do schema atual SEMPRE presentes, não importa
de que versão do código o cache é - campo que o `anterior` não tem vira
`None` (mostra "—" na UI, não quebra, não inventa dado).

**Nota geral pro projeto**: esse é um risco de classe que existe em
qualquer `st.cache_resource` usado como "último valor bom conhecido" -
toda vez que o schema do dict cacheado mudar (campo novo adicionado),
o fallback precisa ser resiliente a cache antigo. Vale revisar se
`_ultima_cotacao_indice_valida` (mesmo padrão, `data/prices.py`) tem o
mesmo risco se o formato da cotação de índice mudar um dia - não
verificado agora (fora do escopo desta correção pontual), mas é o tipo
de coisa a lembrar se aparecer outro `KeyError` parecido.

- Arquivos: `data/prices.py` (`obter_indicadores`).
- Testes: `compileall` limpo; reprodução direta do bug ANTES da
  correção (confirmado `KeyError`) e confirmação de que sumiu DEPOIS
  (valores antigos preservados, campos novos viram `None`); dado real
  (PETR4) continua retornando todos os campos corretos; AppTest nas 9
  seções sem exceção.
- Commit: enviado.

## FILA 2 — em andamento (ver seção própria abaixo)

## Tarefas bloqueadas

(preenchido se alguma falhar 2x)

## Decisões registradas (regra 1 de autonomia)

- **T9 (Genial/XP bloqueadas no Cloud):** não desativei a tentativa
  automática de coleta quando rodando no Cloud (deixei o cooldown de
  10min do FILA1-T5 como única proteção contra martelar a fonte).
  Motivo: não há um jeito limpo de detectar "estou no Cloud vs local"
  sem introduzir um novo flag/config, e desativar coleta automática é
  uma mudança de comportamento maior — opção mais conservadora foi
  manter tentando (já protegido pelo cooldown) e deixar o
  `coletor_local.py` como reforço, não substituto.

## Ações manuais pendentes

### Colar em `.streamlit/secrets.toml` (local) e no App settings → Secrets do Streamlit Cloud
```toml
[admin]
emails = ["rodrigo.costa.souza2005@gmail.com"]
```
Até colar isso, o painel DIAGNÓSTICO DE FONTES continua funcionando
normalmente (usa o fallback fixo em `config._EMAILS_ADMIN_PADRAO`) — não
é bloqueante, só uma ação de segurança pra repo público.

### Lives da Genial no YouTube (T8) — decisão sua antes de eu religar
O mecanismo está pronto e testado (`data/research/genial_lives.py`), mas
desligado (`disponivel: False`) por bloqueio de `robots.txt` do YouTube
no feed público usado pra listar os vídeos - ver decisão detalhada acima,
seção "FILA2-T8". Duas opções, sua escolha:

1. **Deixar desligado** (padrão atual) - não precisa fazer nada.
2. **Religar mesmo assim** (uso pessoal, sem republicar o conteúdo) - só
   mudar `"disponivel": False` pra `True` no dict `genial_lives` em
   `data/research/__init__.py`. Funciona tecnicamente (testado), mas
   contraria o robots.txt do YouTube - decisão sua, não fiz sozinho.
3. **Caminho "oficial"**: criar uma API key do YouTube Data v3 (Google
   Cloud Console → criar projeto → ativar "YouTube Data API v3" → criar
   credencial tipo "Chave de API") e colar em `secrets.toml`:
   ```toml
   [youtube]
   api_key = "sua-chave-aqui"
   ```
   Mesmo assim, resolveria só a LISTAGEM de vídeos (endpoint `search`/
   `playlistItems`, sem bloqueio de robots.txt pra chamadas de API) - a
   parte de TRANSCRIÇÃO continuaria dependendo do mesmo mecanismo atual
   (legenda automática via `youtube_transcript_api`, que não é uma API
   key), já que a API oficial de legendas exige OAuth do dono do canal
   (a Genial não vai autorizar o app pessoal do Rodrigo). Se quiser essa
   opção, avise que eu escrevo a parte de listagem via API antes de usar.

### Agendador de Tarefas do Windows — coleta local do RESEARCH
Genial e XP estão bloqueadas tanto neste sandbox quanto (confirmado pelo
diagnóstico) no Streamlit Cloud. `coletor_local.py` (novo, na raiz do
projeto) roda a coleta de fora do Cloud — se a sua rede de casa/trabalho
não tiver o mesmo bloqueio, os dados ficam frescos mesmo com o Cloud sem
conseguir coletar. Passo a passo (interface gráfica, sem PowerShell):

1. Abra o **Agendador de Tarefas** (pesquisar no menu Iniciar).
2. **Ação → Criar Tarefa Básica...**
3. Nome: `PREGAO - coleta research`. Avançar.
4. Gatilho: **Diariamente**. Avançar. Hora de início: `07:00`. Avançar.
5. Ação: **Iniciar um programa**. Avançar.
6. Programa/script: caminho completo do python do `.venv`, algo como
   `C:\Users\Dell\Projects\pregao\.venv\Scripts\python.exe`.
   Argumentos: `coletor_local.py`.
   Iniciar em: `C:\Users\Dell\Projects\pregao` (importante — sem isso não
   acha `.streamlit\secrets.toml` nem os módulos do projeto).
7. Concluir. Depois, clique com o botão direito na tarefa criada →
   **Propriedades**:
   - Aba **Disparadores** → editar o gatilho → marcar **Repetir a cada**:
     `30 minutos`, **por até**: `13 horas` (cobre 7h–20h).
   - Aba **Condições**: desmarcar "Iniciar a tarefa somente se o
     computador estiver ligado à energia CA" se for notebook na bateria
     (opcional).
   - Aba **Geral**: marcar "Executar estando o usuário conectado ou não"
     se quiser que rode mesmo deslogado (pede a senha do Windows uma
     vez).
   - Não há campo nativo de "só dias úteis" combinado com "a cada 30min"
     numa tarefa só — mais simples: criar o gatilho **Semanalmente**, dias
     Seg-Sex, em vez de Diariamente no passo 4, e aplicar a repetição do
     mesmo jeito.
8. Teste: botão direito na tarefa → **Executar**. Confira em alguns
   segundos se rodou sem erro (aba **Histórico**, se estiver habilitado,
   ou apenas veja se novos itens apareceram no Supabase/na aba RESEARCH).

Nada disso é bloqueante — o app funciona normalmente sem essa tarefa
configurada, só não atualiza Genial/XP enquanto o Cloud estiver
bloqueado. A aba RESEARCH agora mostra "última coleta: hh:mm" por casa,
então dá pra ver quando os dados foram atualizados de verdade.
