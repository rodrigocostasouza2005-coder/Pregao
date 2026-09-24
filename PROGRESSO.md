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
