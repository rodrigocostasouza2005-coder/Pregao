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

## Revisão da ETAPA 7 — tamanho do painel direto na aba (2026-09-26)
Feedback direto do Rodrigo sobre a primeira versão da ETAPA 7: "não era
assim que eu podia escolher o layout, queria escolher na aba mesmo
sabe?... eu escolher o tamanho mesmo". A versão anterior só deixava
ajustar tamanho/visibilidade dentro do formulário de CONFIG, sem
feedback visual imediato no painel sendo ajustado. Perguntei como ele
imaginava o controle "na aba mesmo" - escolheu "botões no cabeçalho de
cada painel".

**Redesenho** (`ui/paineis.py`):
- Cada painel (dentro do `st.container(border=True, key=...)` que já
  existia) ganhou um popover "⚙" no canto (posicionado via CSS
  `position:absolute` sobre o container, que agora tem `key=` e
  `position:relative` de propósito) - dentro do popover: pills de
  tamanho (1/4/1/2/3/4/FULL, efeito imediato ao clicar - `st.rerun()`
  direto, sem esperar formulário nenhum) + botão "ESCONDER ESTE
  PAINEL".
- `_salvar_tamanho`/`_esconder_painel` (novos): mutam `prefs` em memória
  (efeito instantâneo na mesma sessão, já que toda render_fn lê a MESMA
  referência de `prefs`) e chamam `persistir_fn()` se foi passado -
  grava de verdade no Supabase, não só na sessão atual.
- `renderizar()` ganhou o parâmetro `persistir_fn` (keyword-only, depois
  de `*args` - threading até `app.py` via `ui/macro_tab.py:render_macro`/
  `ui/mercado_tab.py:render_mercado`, que agora aceitam e repassam esse
  parâmetro pros dois call sites em `app.py`, passando
  `_persistir_prefs`).
- `controle_layout_config` (CONFIG) virou `controle_visibilidade_config`
  - só checkboxes agora, tamanho saiu de lá. Motivo: com o popover
    fazendo o resize direto na aba com efeito imediato, manter também no
    formulário seria duas UIs pra mesma coisa (redundante, potencial
    fonte de confusão sobre "qual vale"). CONFIG continua sendo o único
    lugar pra REEXIBIR um painel escondido (só isso realmente precisa
    vir de fora - um painel escondido não renderiza, então não tem
    popover pra clicar nele de volta).
- `app.py`: removida a escrita de `tamanho_paineis` do submit do
  formulário de CONFIG (a chave nem entra mais no dict do
  `st.session_state.prefs.update({...})` - omitir a chave deixa o valor
  atual intocado, já que o popover grava direto).

**Verificação de "st.pills dentro de st.form"** (herdada da versão
anterior) não se aplica mais aqui - o popover roda FORA de qualquer
`st.form`, então usa `st.button`/`st.rerun()` normal (mais simples e com
efeito imediato, que é justamente o que faltava antes).

**Achado real durante o teste (não é bug da aplicação)**: a primeira
tentativa de validar via AppTest reportou um botão "1/2" desabilitado
onde eu esperava ele habilitado - investigado a fundo antes de assumir
bug: confirmado que era CONTAMINAÇÃO DO PRÓPRIO TESTE, não da aplicação
- reusei o mesmo `sub` fake ("teste-sub-123") em várias rodadas de teste
ao longo da sessão (ETAPA 7 v1 incluída), e como o Supabase deste
ambiente está de fato acessível (`banco_ok: True`), uma gravação bem-
sucedida de um teste ANTERIOR persistiu de verdade e "sobrou" pras
rodadas seguintes - o botão estava desabilitado CORRETAMENTE (o
tamanho salvo de verdade era mesmo aquele). Corrigido usando um `sub`
único por execução de teste (`f"teste-layout-{int(time.time())}"`) -
lição: testes que usam um usuário fake fixo contra um Supabase de
verdade acumulam estado entre rodadas, não são idempotentes por padrão.

- Arquivos: `ui/paineis.py`, `ui/macro_tab.py`, `ui/mercado_tab.py`,
  `app.py`.
- Testes: `compileall` limpo; teste dirigido (usuário novo por
  execução): popover mostra os 4 painéis de MACRO com os botões certos
  (tamanho atual desabilitado, resto clicável); clique num tamanho não-
  atual persiste imediatamente em `prefs["tamanho_paineis"]` sem passar
  por CONFIG; esconder um painel direto no popover persiste em
  `prefs["paineis_visiveis"]`; reexibir esse painel via CONFIG funciona;
  AppTest nas 9 seções sem exceção.
- Commit: enviado.

## ETAPA 8 — busca global no header (2026-09-28)
Última etapa do roadmap de redesign (`C:\Users\Dell\.claude\plans\mutable-meandering-peacock.md`).
Reusa o `TickerAutocomplete` da ETAPA 1 (`ui/busca.py:buscar_ativo`, já
usado na sidebar) - dropdown com atalhos, exatamente como o plano
descrevia.

**Implementado** (`app.py`): campo de busca + 3 botões (EQUITY ↗,
NOTÍCIAS ↗, + WATCHLIST) acima da navegação principal, visível em
qualquer aba. `_ir_com_ticker(chave_secao_destino, ticker,
chave_pill_ticker)`: adiciona o ticker na watchlist se ainda não estiver
lá (EQUITY e NEWS só mostram dado de ticker da watchlist - função
`obter_noticias_watchlist`/seletor de ticker do EQUITY já eram assim),
muda de seção e preseleciona o ticker (`ticker_selecionado` pra EQUITY,
`news_pill_ticker` pra NEWS).

**Bug real pego no teste, corrigido antes de qualquer coisa ir pra
produção**: primeira tentativa escrevia
`st.session_state["secao_ativa"] = rotulo_alvo` DEPOIS do
`st.segmented_control(key="secao_ativa")` do nav já ter instanciado no
mesmo rerun (a busca global tinha sido colocada FISICAMENTE depois do
nav no código) - `StreamlitWidgetAlreadyInstantiatedError` (Streamlit
não deixa escrever na session_state de um widget depois dele já ter
sido criado nesse mesmo rerun). Corrigido reordenando: o cálculo de
`secoes`/`rotulos_secao`/`mapa_rotulo_secao` (puro, sem widget) subiu
pra antes da busca global; a busca global (com os botões que escrevem
em `secao_ativa`) ficou entre esse cálculo e a instanciação de verdade
do `st.segmented_control` do nav, que desceu pra depois. Zero mudança
na lógica do nav em si, só reposicionamento. Sem `st.rerun()` explícito
em `_ir_com_ticker`: como a escrita acontece ANTES do widget do nav
instanciar nesse MESMO rerun, o resto do script já usa o valor novo sem
precisar de um rerun extra.

**Achado menor, não é bug**: pré-aplicar o filtro de ticker do NEWS
(`news_pill_ticker`) só funciona de verdade se aquele ticker tiver
notícia na janela de 48h - testado com NFLX34 (BDR de cobertura fina)
e o filtro voltou vazio silenciosamente (mesmo fallback `or "TODOS"` já
usado no resto do NEWS). Não é regressão, é limitação real de
disponibilidade de notícia - trocado por BBAS3 (papel grande, cobertura
garantida) no teste pra não confundir isso com bug de verdade.

- Arquivos: `app.py`.
- Testes: `compileall` limpo; teste dirigido (usuário novo por
  execução, evita a mesma contaminação de Supabase já documentada na
  revisão da ETAPA 7): EQUITY auto-adiciona MELI34 e navega com o
  ticker certo selecionado; NOTÍCIAS auto-adiciona BBAS3 e navega com o
  filtro pré-aplicado; +WATCHLIST adiciona AAPL34 sem sair da aba
  atual; AppTest nas 9 seções sem exceção.
- Commit: enviado.

**Roadmap de redesign completo** (ETAPAS 1-8, iniciado 2026-09-23,
concluído 2026-09-28).

## Bug real: tickers desatualizados na lista curada (2026-09-28)
Rodrigo reportou: buscou "JBSS3" na busca global (ETAPA 8, recém
enviada) e nada funcionou - nem EQUITY, nem NOTÍCIAS, nem +WATCHLIST.

**Investigação** (não assumi que era bug da busca global - testei a
fundo antes de concluir):
1. `validar_ticker("JBSS3")` → `yf.Ticker("JBSS3.SA").history()` vazio,
   confirmado com teste direto. Testado também com `curl_cffi`
   (impersonate="chrome", a mesma técnica que já resolve bloqueio de
   Yahoo em outros lugares do projeto) - continuou vazio. Não é
   bloqueio de IP, é o símbolo mesmo que não existe mais.
2. Testei PETR4.SA como controle no mesmo run - funcionou normal,
   confirmando que não é uma falha geral de rede/yfinance.
3. Achei na PROGRESSO.md de uma sessão anterior (ETAPA 3/4) uma nota
   nunca resolvida: "13 dos 64 tickers curados falharam... não
   investiguei se é delisting real, instabilidade do yfinance ou
   bloqueio de IP do sandbox". Testei os 13 individualmente - todos
   vazios de verdade, incluindo ELET3/EMBR3 (blue chips enormes, sem
   motivo nenhum pra estarem delistados de verdade) - isso indicava
   RENOMEAÇÃO de ticker, não empresa suspensa/falida.
4. `WebSearch` pra cada caso (3 buscas, cobrindo os 13 tickers) -
   confirmado que são eventos corporativos reais de 2025/2026:
   fusões, trocas de nome/ticker, uma deslistagem de verdade
   (Carrefour Brasil, comprada pelo controlador francês).
5. Testei CADA ticker novo individualmente contra yfinance antes de
   editar `config.py` - só entrou no código o que respondeu com dado
   real.

**Correção** (`config.py`, `data/news_setores.py`):
- ELET3/ELET6 → AXIA3 (Eletrobras virou Axia Energia, 10/11/2025 -
  AXIA6 testado e não respondeu no yfinance, só entrou AXIA3)
- EMBR3 → EMBJ3 (Embraer, 03/11/2025)
- JBSS3 → JBSS32 (JBS: listagem principal virou NYSE via holding
  JBS N.V.; ação local virou BDR - CVM ainda analisando pedido de
  cancelamento de registro, protocolado 21/09/2026)
- MRFG3 + BRFS3 → MBRF3 (fusão Marfrig+BRF, debut 23/09/2025 - troca
  de 0,8521 ação Marfrig por ação BRF; entrada duplicada virou uma só)
- NTCO3 → NATU3 (Natura&Co incorporada pela Natura Cosméticos,
  01/07/2025, ticker voltou ao de antes de 2019)
- CCRO3 → MOTV3 (CCR virou Motiva Infraestrutura de Mobilidade,
  02/05/2025)
- RRRP3 → BRAV3 (fusão 3R Petroleum + Enauta, virou Brava Energia,
  09/2024)
- ARZZ3 → AZZA3 (fusão Arezzo + Grupo Soma, virou Azzas 2154,
  01/08/2024 - SOMA3 também removido do classificador de setor, mesma
  empresa agora)
- CPLE6 → CPLE3 (Copel: mesma empresa, PNB parou de responder no
  yfinance, ON funciona - troca de classe de ação, não de empresa)
- **AZUL4 removido sem substituto**: virou AZUL54 (23/12/2025), mas
  AZUL54 também não respondeu no yfinance - nenhuma opção funcional
  encontrada, melhor não oferecer nada a inventar/manter algo quebrado
- **CRFB3 removido sem substituto**: Carrefour Brasil deslistada de
  verdade em 30/05/2025 (controlador francês CSA fechou capital) - não
  existe mais como ação negociada, ponto final

`data/news_setores.py` (classificador de setor do TOP MERCADO/NEWS por
palavra-chave + ticker) recebeu os mesmos ajustes - é um dict de puro
texto pra matching (não busca preço), então incluí mesmo AZUL54 e
AXIA6 ali (podem aparecer como MENÇÃO em notícia mesmo sem cotação
funcionando).

**Verificação final**: `obter_panorama_ibovespa()` (a função que
alimenta MERCADO/VISÃO GERAL/TOP MERCADO/treemap) confirmada 60/60
papéis da lista curada com dado válido - antes eram 47/60 (13
falhando silenciosamente, sem warning nenhum pro usuário, só sumindo
do panorama).

- Arquivos: `config.py`, `data/news_setores.py`.
- Testes: `compileall` limpo; teste individual de cada ticker novo
  contra yfinance real ANTES de entrar no config; `obter_panorama_ibovespa()`
  confirmado 60/60 depois da correção; AppTest nas 9 seções sem
  exceção.
- Commit: enviado (junto com o pedido de desempenho semana/mês abaixo,
  mesma sessão de investigação).

## Pedido: desempenho da semana e do mês (VISÃO GERAL/MERCADO), 2026-09-28
Pedido direto do Rodrigo, veio no meio da investigação do bug acima:
"na visão geral e mercado queria um desempenho da semana e do mês além
do desempenho do dia tb".

**Implementado**:
- `data/mercado.py`: `_baixar_lote()` foi de `period="5d"` pra
  `period="2mo"` (histórico suficiente pra calcular janela de 30 dias
  corridos com folga). `_linha_papel()` ganhou
  `variacao_semana_pct`/`variacao_mes_pct` - mesma técnica de
  `data/prices.py:_precos_base_retornos` (acha o fechamento no ou
  antes de "hoje - N dias corridos", calcula % contra o preço atual) -
  mesma convenção de dias já usada nos retornos do EQUITY (1S=7,
  1M=30), pra bater com o que o resto do app já chama de
  "semana"/"mês". Campo vira `None` (não inventa dado) se o papel não
  tiver histórico suficiente na janela (ex: IPO recente).
- `obter_altas_baixas`/`obter_termometro`/`obter_desempenho_setorial`
  ganharam parâmetro `janela` ("dia"/"semana"/"mes", padrão "dia") -
  filtram por `CAMPO_VARIACAO_POR_JANELA[janela]`, papel sem dado
  válido na janela fica de fora (não aparece com número errado).
- `ui/mercado_tab.py`: `_seletor_janela()` (segmented_control DIA/
  SEMANA/MÊS, efeito imediato) chamado dentro de `_painel_termometro`,
  `_painel_altas_baixas` e `_painel_setorial` - cada painel tem sua
  PRÓPRIA escolha independente (`_escolha_estavel_mercado`, chave por
  painel), pra poder ver ex. "altas/baixas da semana" com "setorial"
  ainda no dia. `_tabela_papeis` ganhou parâmetro `campo` (qual chave
  do dict mostrar) em vez de sempre `variacao_pct`.
- VISÃO GERAL (`ui/visao_geral.py`) reusa `_painel_altas_baixas`/
  `_painel_setorial` DIRETO de `ui/mercado_tab.py` (já documentado
  assim desde a ETAPA 2) - ganhou o seletor de janela automaticamente,
  zero mudança de código lá.
- Escopo: só os 3 painéis "de desempenho" (altas/baixas, termômetro,
  setorial). Mais Negociados (é sobre volume, não retorno), Mapa do
  Mercado (visual do dia especificamente) e Mercados Globais (fonte de
  dado diferente, `_baixar_lote_bruto`) ficaram de fora - não é o que
  foi pedido, e mexer nesses três seria escopo maior sem necessidade.

- Arquivos: `data/mercado.py`, `ui/mercado_tab.py`.
- Testes: `compileall` limpo; `obter_altas_baixas`/`obter_termometro`/
  `obter_desempenho_setorial` testados com dado real nas 3 janelas
  (líderes diferentes por janela, ex: MGLU3 +43,9% no mês vs CVCB3
  +2,8% no dia - números plausíveis, sem inventar); teste dirigido
  (AppTest) confirmando que trocar o seletor de ALTAS/BAIXAS muda o
  conteúdo renderizado E não afeta o seletor independente do SETORIAL;
  AppTest nas 9 seções sem exceção.
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

## Ciclo novo: auditoria real + quick wins de data sanity (2026-09-30/10-01)

Pedido do Rodrigo veio como um super-prompt de redesign bem amplo
(terminal + Research Intelligence Layer: Company 360, Earnings Bot,
AI Research Assistant multifonte, Research Radar, FACTO/VISÃO DA
CASA/INFERÊNCIA separados, etc. — escopo de meses). Antes de tocar em
qualquer código, fiz a auditoria real do repositório (app.py, style.css,
ui/research_tab.py, data/research/resumir.py, data/research/__init__.py,
ui/visao_geral.py, MANUAL.md, BACKLOG.md) pra separar o que o prompt
supõe (genérico) do que o projeto já tem de verdade.

**Achados da auditoria que corrigem a premissa do prompt**: NEWS e CVM
não são placeholder (já têm agrupamento, score, selo CONFIRMADA, busca+
paginação); o resumo de research já NÃO usa template
TESE/NÚMEROS/RISCOS (prompt de `resumir.py` já é narrativo, causa→
consequência, blocos adaptativos); o shell/header já foi redesenhado há
poucos dias (ticker tape sem duplicidade, nav com sublinhado, busca
compacta); Beta e DY já não vêm cru do yfinance. Gaps reais confirmados:
truncamento cru de 12k em `resumir.py`, sem múltiplos por setor, sem
"o que mudou desde ontem", EQUITY não é um Company 360 (RESEARCH não
aparece dentro do ticker), sem Research Radar/comparação entre casas,
sem separação visual FATO/VISÃO DA CASA/INFERÊNCIA, versionamento de
resumo é um hack de heurística de texto (`_resumo_formato_antigo`), e
vários itens do BACKLOG.md já estavam resolvidos sem o arquivo ser
limpo.

Perguntei ao Rodrigo por onde começar (escopo grande demais pra decidir
sozinho) — escolheu **"Quick wins + data sanity"** como primeiro
incremento, deixando Company 360/"o que mudou"/Research Intelligence
Layer pra ciclos seguintes.

**Implementado neste ciclo** (commit 2433b24):
- `config.formatar_multiplo`: P/L e P/VP ≤ 0 viram "N.M." em vez do
  número negativo cru (lucro/patrimônio líquido negativo faz o múltiplo
  perder sentido como medida de preço) — aplicado em INDICADORES e no
  painel comparativo da watchlist (`app.py`).
- `data/research/resumir.py`: fim do `texto[:12000]` cru. Texto acima do
  limite passa por `_condensar_texto_longo` (divide em pedaços de 10k,
  extrai fatos/números/nomes de cada um com uma chamada leve e barata —
  `_PROMPT_EXTRACAO_CHUNK`, max_tokens=800) antes do resumo narrativo de
  verdade rodar sobre o texto condensado. Texto curto (maioria dos
  relatórios) continua em 1 chamada só, comportamento idêntico a antes.
  HTTP da Groq extraído pra `_chamar_groq` (reusado pelas duas etapas).
- `app.py`: tentativa de correção do bug real "e-mail do usuário some do
  header" — hipótese (BACKLOG.md): botão SAIR com `width="stretch"` +
  texto que não quebra linha brigava por espaço com o chip de e-mail
  numa coluna estreita. Removido o `width="stretch"` do SAIR e realocada
  a proporção das colunas (`col_user` 1.35→1.7, email/sair 3:1→4:1).
  **Pendente confirmação visual** — não tive acesso à extensão do Chrome
  nesta sessão (mesma instabilidade de sessões anteriores).
- `BACKLOG.md`: limpeza — removidos 5 itens já resolvidos como efeito
  colateral de outras tarefas (beta, cor da MM20 em modo LINHA, toolbar
  do Plotly em MACRO, eixo X do IPCA, scrollbar/título sumido do
  INDICADORES — essa última com hipótese de causa raiz documentada, a
  mesma regra CSS `:has(table)` que já resolve RESUMO); documentada
  investigação de DY/JCP (sem evidência de bug real, yfinance já separa
  cada evento de distribuição por data-ex).

**Testes**: `compileall` limpo; teste dirigido isolado do chunking
(mock de `_chamar_groq` — texto curto = 1 chamada, texto longo de 25k
chars = 3 pedaços + 1 chamada final = 4, falha de cota num pedaço
intermediário propaga sem gerar resumo parcial); `formatar_multiplo`
testado com None/negativo/zero/positivo; AppTest nas 9 seções
(VISÃO GERAL/EQUITY/MACRO/RESEARCH/NEWS/TOP MERCADO/MERCADO/CVM/CONFIG)
sem exceção, rodando contra o Supabase real deste sandbox (`sub` de
teste único por execução, ver lição de teste mais acima neste arquivo).

**Pendências que ficaram pro próximo ciclo** (ordem sugerida, Rodrigo
decide): Company 360 (EQUITY em abas + múltiplos por setor), "O que
mudou desde ontem" por ativo, Research Intelligence Layer (Radar,
comparação entre casas, separação FATO/VISÃO/INFERÊNCIA, versionamento
real de resumo). Confirmação visual do bug do e-mail no header e da
legenda sobreposta na Curva Pré (MACRO) seguem pendentes de inspeção
real (print ou extensão do Chrome funcionando).

## Workspace modular — layout livre na aba MERCADO (MVP, 2026-10-01)

Trabalho retomado de uma sessão anterior que tinha deixado o código
pronto mas não commitado (sem passar por teste/documentação). Antes de
continuar, auditei o que já existia: `ui/workspace.py` (arquitetura
Workspace → Layout Manager → Panel Container → Panel Content, decidida
numa auditoria prévia com o Rodrigo antes de implementar — ver
docstring do módulo) e a troca de `ui/paineis.py` por `ui/workspace.py`
em `ui/mercado_tab.py:render_mercado` (MERCADO é a aba piloto; MACRO e
as demais continuam no sistema antigo de larguras fixas 1/4-1/2-3/4-FULL
até essa ETAPA 1 ser validada).

**Mecânica**: sem lib de grid de terceiro (streamlit-elements etc. —
exigiria reescrever o conteúdo dos painéis na árvore de elementos dela).
Em vez disso: CSS posiciona cada `st.container(border=True, key=...)`
de forma absoluta dentro do workspace (x/w em % da largura — responsivo
ao redimensionar a janela/sidebar; y/h em rem — acompanha a densidade de
fonte do usuário, não a largura da tela); um script (`st.iframe` com
HTML/JS inline, mesma origem via `window.parent.document`) dá vida ao
drag (pelo título do painel) e resize (canto inferior-direito) sem criar
nenhum nó de DOM dentro da árvore que o React do Streamlit controla; o
resultado final (só ao SOLTAR o mouse, nunca durante o gesto) volta pro
Python por uma ponte: `st.text_input` oculto cujo valor é setado via JS
(native setter + dispatchEvent). Popover "⚙" por painel (RESTAURAR
TAMANHO/POSIÇÃO, OCULTAR) e botão "↺ RESTAURAR LAYOUT" da aba inteira.
Nova prefs `layout_paineis_livre` (`config.PREFS_PADRAO`): painel sem
entrada aí cai no layout padrão empilhado calculado pela ordem no
registro — nunca colide, mesmo misturando painel já personalizado com
painel novo que o usuário nunca tocou.

**Achado real durante a revisão**: o script de drag/resize estava indo
pra produção com `st.components.v1.html(..., height=0)` — API marcada
para remoção em 2026-06-01 (já vencida na data de hoje) e, pior,
`st.iframe` (substituto natural na mesma versão instalada, Streamlit
1.64) rejeita `height=0` (`StreamlitInvalidHeightError` — exige inteiro
positivo, `"stretch"` ou `"content"`). Trocado por `st.iframe(html,
height=1)`, confirmado sem exceção via AppTest. Sem essa troca o deploy
ia funcionar hoje mas quebrar na primeira limpeza de API deprecada do
Streamlit Cloud.

**Testes**: `compileall` limpo; bateria dirigida isolada (sem rede/sem
Streamlit rodando) de `ui/workspace.py` — `layout_efetivo` (padrão
empilhado sem prefs; painel customizado + painel novo misturados sem
colidir), `_layout_valido` (rejeita shape incompleto/tipo errado),
`_aplicar_bridge` (JSON válido grava e chama `persistir_fn`; JSON
quebrado não derruba nem persiste; pid fora do registro é descartado;
clamp de x/y/w/h nos limites mínimos/máximos), `_restaurar_layout_aba`/
`_restaurar_layout_painel` (cada um limpa só o que deve). AppTest da
aba MERCADO com `obter_termometro` mockado (dado de mercado ao vivo é
lento/instável neste sandbox — mock isola o teste do workspace da
disponibilidade de rede) confirma a UI do workspace renderizando de
verdade (aviso de arrastar/redimensionar, botão RESTAURAR LAYOUT) sem
exceção; smoke test das 9 seções (login mockado, `sub` único por
execução) sem regressão nas demais abas.

**Pendente**: confirmação visual real do drag/resize (extensão do
Chrome instável neste ambiente, mesmo padrão de sessões anteriores) —
a mecânica de gesto em si (pointerdown/pointermove/pointerup, cálculo
de %/rem, MutationObserver pra painéis que entram depois) não tem como
ser exercitada por AppTest (não há mouse real no DOM do navegador
dentro do teste). Validar com o Rodrigo rodando local antes de
considerar a ETAPA 1 fechada; ETAPA 2 (expandir pra outras abas) só
depois disso.

## Workspace modular — 3 bugs reais corrigidos, validado em produção (commit bf023c2, 2026-10-01)

A validação visual do MVP acima (primeiro deploy) falhou: Rodrigo não
conseguiu arrastar nem redimensionar nada em `pregao.streamlit.app`.
Investigação a fundo (harness Playwright dedicado, fora do app real —
ver abaixo) achou **3 bugs independentes em `ui/workspace.py`**, cada
um suficiente sozinho pra quebrar a experiência:

**Bug A (CSS)**: uma regra decorativa do handle de resize em `_CSS_BASE`
usava um seletor com 2 atributos (especificidade 0,2,0) setando
`position: relative` em todo painel. A regra que deveria valer —
`position: absolute` por painel, gerada em `_gerar_css()` — tem só 1
atributo + 1 elemento (especificidade 0,1,1), **menor**. CSS resolve
conflito por especificidade, não por ordem no documento, então
`relative` sempre vencia, mesmo vindo antes no HTML — nenhum painel
chegava a ser de fato posicionado livremente; cada um ficava deslocado
por `left/top` só que *em cima* do fluxo normal do documento, causando
sobreposição e tamanhos estranhos visíveis desde o load inicial, sem
precisar nem arrastar nada. Corrigido removendo a declaração de
`position` da regra genérica (não precisava dela - o `::after`
decorativo só precisa de QUALQUER containing block não-estático, e o
`position:absolute` por painel já fornece isso).

**Bug B (ponte JS→Python)**: a ponte escreve o layout num
`st.text_input` oculto via `dispatchEvent(new Event('input'))` (truque
padrão pra inputs React). Mas `st.text_input` só manda o valor pro
backend (dispara `on_change`/rerun) no **blur ou Enter** — debounced de
propósito pra não re-rodar o script a cada tecla. Um `input` isolado
nunca chegava no servidor: dava pra *ver* o painel se mexer, mas nada
era persistido, e o próximo rerun real (qualquer um) descartava a
mudança. Corrigido com `input.focus(); input.blur();` depois do
`dispatchEvent` - simula a saída do campo, gatilho real de commit do
Streamlit.

**Bug C (listener morto)**: `ligarPainel()` marcava cada painel com
`dataset.workspaceLigado = '1'` pra não duplicar listener. Mas o
Streamlit recria o iframe do script a cada rerun (nunca reaproveita),
enquanto o elemento do painel é preservado pelo React (mesma key). Na
segunda montagem do iframe (disparada pelo primeiro gesto, via Bug B
corrigido), o script via `'1'` já presente e desistia de anexar
listener novo - os antigos pertenciam a um iframe já destruído.
Resultado: só o PRIMEIRO gesto da sessão inteira funcionava; qualquer
coisa depois disso (ou depois de qualquer rerun, por qualquer motivo)
ficava surda a mouse até recarregar a página. Corrigido trocando a flag
fixa `'1'` por um `MOUNT_ID` único por montagem (`Date.now()+Math.random()`).

**Metodologia de teste**: AppTest não executa JS/mouse real, então as
rodadas anteriores não tinham como pegar nenhum desses 3 bugs (todos só
aparecem com interação de navegador de verdade). Construído um harness
Playwright dedicado (`streamlit run` isolado, fora do app real — bypassa
login Google via `auth.py`, impossível de automatizar, e Supabase real,
substituído por JSON local) que monta `ui.workspace.renderizar_workspace`
sem modificação nenhuma pro teste. 23 checks cobrindo: `position`
computado via `getComputedStyle`, drag pelo header, resize horizontal/
vertical/diagonal com valores intermediários reais (não presos a
25/50/75/100%), clique em botão E interação com gráfico Plotly real
dentro do painel sem disparar drag/resize acidental, persistência via
bridge, rerun, reload de página (sessão nova), restaurar layout sem
apagar outras preferências do usuário (watchlist etc.), zero erros de
JS no console. Esse harness não faz parte do repo (scratchpad de
sessão) - só o fix em si foi commitado.

**Confirmado por Rodrigo rodando de verdade em `pregao.streamlit.app`**:
arrastar, redimensionar nos 3 modos, persistência tudo funcionando.
ETAPA 1 agora fechada de verdade. Único arquivo alterado:
`ui/workspace.py` (42 inserções, 13 remoções) - nada de design/CSS
visual/outras abas tocado.

## Modo autônomo (2026-10-01) — roadmap de 16 fases pra transformar o PREGÃO num terminal mais utilizável

Rodrigo autorizou trabalho autônomo (~2h, sem pausar pra perguntar) com
um roadmap de 16 fases, prioridade ESTRUTURA > FUNCIONALIDADE >
PERFORMANCE > CONSISTÊNCIA > VISUAL. Registro de cada fase abaixo
conforme avança. Regra: nunca destruir funcionalidade existente,
nunca inventar dado financeiro, commit+push ao fechar cada fase, nunca
acumular fases num commit só.

### FASE 1 — Market ticker unificado (commit pendente nesta sessão)

**Problema**: duas faixas diferentes de "ticker" coexistiam. Camada 2
(`_ticker_tape`, dentro do header fixo) mostrava só os índices
(IBOVESPA/DÓLAR/EURO) com animação CSS contínua de verdade (marquee,
`@keyframes pregao-marquee` em `style.css`, conteúdo duplicado +
`translateX(-50%)`, sem rerun do Streamlit pra animar). Camada 4
(`_watchlist_chips`, fora do header fixo, logo após a NAV) mostrava os
tickers da watchlist pessoal numa fita ESTÁTICA (`overflow-x:auto` sem
animação) - essa que Rodrigo descreveu como "mal posicionada/cortada".

**Correção**: removida `_watchlist_chips()` inteira (função + CSS
`.wchip*` + chamada) - a aba watchlist deixou de existir como faixa
separada. `_ticker_tape()` (única faixa restante, dentro do header
fixo) passou a incluir os tickers da watchlist na MESMA lista `itens`
que já alimentava o loop dos índices - zero mecanismo novo, só mais
conteúdo no que já existia e já funcionava. Fonte de dados: a própria
`prefs["watchlist"]` + `obter_cotacao` (mesma função que a faixa
removida já usava, mesmo cache) - nenhuma fonte nova, nenhum ticker
inventado. `--folga-seguranca` (style.css) subiu de 0.3rem pra 0.8rem
pra repor o respiro visual que a faixa antiga dava via seu próprio
`margin-bottom` (perdido com a remoção dela).

**Validação**: AppTest das 9 seções sem exceção. Harness Playwright
dedicado (`style.css` real + estrutura DOM idêntica ao header de
produção, sem precisar de login Google) confirmou: exatamente 1 faixa
de ticker no DOM, índices E ações na mesma faixa, animação
`pregao-marquee` aplicada e o trilho realmente se move sozinho ao
longo do tempo (medido via `getComputedStyle().transform` em 2
instantes), nenhuma faixa antiga (`.wchip-row`) sobrou, sem vazamento
de texto (`overflow:hidden` confirmado), geometria das camadas correta
(HEADER.bottom ≤ TICKER.top ≤ NAV.top ≤ CONTEUDO.top, sem sobreposição
em nenhum ponto), espaçamento NAV→conteúdo razoável (35px), zero erros
de JS. Screenshot confirma visual: uma fita só, estética de terminal
preservada (preto/âmbar/verde/vermelho, mono, sem caixas).

**Arquivos alterados**: `app.py` (`_ticker_tape` estendida,
`_watchlist_chips` removida), `style.css` (`.wchip*` removido,
`--folga-seguranca` ajustada).

### FASE 2 — Auditoria de geometria do shell (header/ticker/nav/conteúdo)

Auditoria completa do CSS do shell fixo (`.st-key-header_fixo`,
`.block-container`, z-index, overflow, scroll). **Achado**: o próprio
`style.css` já documenta, em comentários extensos, pelo menos 3 bugs
reais de geometria corrigidos em sessões anteriores no mesmo dia
(buraco sem fundo no header nativo, `overflow-x/y` inválido duplicando
scroll container, `padding-top` desalinhado da altura real das
camadas) - ou seja, essa auditoria já tinha sido feita a fundo antes
desta sessão. Correção pontual: comentário desatualizado citava
"z-index 50" pro header fixo, valor real é 56 (`.st-key-header_fixo`).

**Validação**: harness Playwright com scroll real (80 linhas de
conteúdo, `mouse.wheel`) + 3 metodologias de teste até chegar numa
prova real de "sem vazamento visual" - as duas primeiras tentativas
deram falso-positivo (comparar bounding boxes geometricamente conta
sobreposição normal de `position:fixed` como se fosse bug;
`elementFromPoint` é enganado por `pointer-events:none` no header
nativo do Streamlit, que é um elemento decorativo vazio existindo só
pra reservar espaço - hit-test "atravessa" ele mas o PAINT continua
normal por cima). A prova real: amostragem de cor de pixel na
screenshot renderizada de verdade (nenhum pixel com a cor de texto de
conteúdo aparece dentro da faixa do header) - zero vazamento
confirmado. Header não se move ao rolar, fundo sólido confirmado.

**Lição de metodologia** (vale pra futuras auditorias de layout):
geometria de bounding box e hit-testing (`elementFromPoint`) NÃO
provam vazamento visual sozinhos - a prova real é a cor do pixel
renderizado. Guardar esse padrão de teste pra qualquer auditoria futura
de z-index/overlap.

**Arquivo alterado**: `style.css` (1 linha, comentário).

### FASE 3 — Auditoria final do workspace MERCADO

Já tinha sido corrigido e validado em produção mais cedo nesta mesma
sessão (3 bugs reais: especificidade CSS, ponte JS/Python, listener
morto pós-rerun - ver seção "Workspace modular — 3 bugs reais
corrigidos" acima). Reconfirmado depois das mudanças de Fase 1/2 (que
não tocam `ui/workspace.py`): bateria dirigida (8/8), harness Playwright
completo (23/23 - drag, resize nos 3 modos, interação com gráfico
Plotly real, persistência rerun/reload, restore) e AppTest da aba
MERCADO contra o `app.py` real, todos sem regressão. Nenhuma mudança de
código necessária nesta fase - só confirmação.

### FASE 4 — Expandir workspace pra MACRO

Também já concluída mais cedo nesta sessão (commit `e5d55e1`, antes do
roadmap de 16 fases ter sido formalizado): `ui/macro_tab.py` trocou
`ui.paineis.renderizar` por `ui.workspace.renderizar_workspace` - mesmo
`REGISTRO_PAINEIS` de sempre (RESUMO fixo + CURVA PRÉ/IPCA/SELIC x
CDI/CENÁRIO GLOBAL arrastáveis), nenhum conteúdo reescrito. `aba_id` em
`ui/workspace.py` já era 100% genérico (nenhum caso especial pra
MERCADO), confirmado por grep antes da migração. AppTest da aba MACRO
sem exceção (~85s - lento por causa das chamadas reais a ANBIMA/BCB/
yfinance nesta sandbox, não é regressão).

### FASE 5 — Expandir workspace pra VISÃO GERAL

**Achado real que simplificou a fase inteira**: `ui/visao_geral.py` JÁ
estava estruturada como funções de painel discretas (`_painel_mercado_agora`,
`_painel_ibov_grafico`, `_painel_noticias_resumo`,
`_painel_watchlist_compacta`, + 4 reaproveitadas direto de
`ui/mercado_tab.py`: altas_baixas/mais_negociados/setorial/globais),
cada uma já com `painel-titulo` - só não estava registrada no sistema
de `REGISTRO_PAINEIS`, era chamada em sequência direta dentro de
`render_visao_geral`. Não precisou nenhuma reestruturação de conteúdo
(exatamente como pedido: "apenas separar corretamente os blocos
existentes em painéis").

**Implementado**: novo `REGISTRO_PAINEIS` em `ui/visao_geral.py` (8
painéis, mesma ordem que já existia), `render_visao_geral` passa a
chamar `workspace.renderizar_workspace("VISÃO GERAL", ...)` em vez de
empilhar os `st.container(border=True)` manualmente. **Achado durante a
implementação** (evitou um bug de UX real antes de ir pro ar): o
popover "⚙ OCULTAR ESTE PAINEL" do workspace só tem um jeito de
REEXIBIR depois - o formulário de CONFIG
(`paineis.controle_visibilidade_config`) - e esse controle só existia
pra MERCADO/MACRO. Sem adicionar o mesmo controle pra VISÃO GERAL, um
painel escondido lá ficaria preso pra sempre, sem nenhum jeito de
trazer de volta (nem o "RESTAURAR LAYOUT" do workspace resolve isso -
ele só reseta posição/tamanho, não visibilidade). Adicionado
`controle_ordem_config`/`controle_visibilidade_config` pra "VISÃO
GERAL" no formulário de CONFIG, espelhando MERCADO/MACRO exatamente.

**Testes**: `compileall` limpo; AppTest das 9 seções sem exceção
(CONFIG incluso, com os 2 novos controles); AppTest focado em VISÃO
GERAL confirma UI do workspace presente (aviso de arrastar, botão
RESTAURAR LAYOUT) sem exceção. Mecânica de drag/resize em si não
precisou de nova bateria Playwright - já provada 100% genérica por
`aba_id` nas Fases 1-4 (23/23 checks, nenhum caso especial pra MERCADO/
MACRO no código).

**Arquivos alterados**: `ui/visao_geral.py` (REGISTRO_PAINEIS novo,
render_visao_geral migrada), `app.py` (import do registro, persistir_fn
no call site, controles de ordem/visibilidade no CONFIG).

### FASE 6 — Auditoria de padrão estrutural dos painéis

**Achado**: a arquitetura PANEL → HEADER/TITLE → ACTIONS → CONTENT já é
o padrão de facto, idêntico nos dois sistemas que existem
(`ui/paineis.py` sistema antigo de larguras fixas, `ui/workspace.py`
novo de layout livre): PANEL = `st.container(border=True, key="painel-outer-...")`;
HEADER/TITLE = a div `.painel-titulo` que cada `render_fn` desenha
primeiro; ACTIONS = popover "⚙" no canto (tamanho+esconder no sistema
antigo, restaurar+ocultar no novo) injetado por fora da `render_fn`,
sempre com a mesma linguagem visual (confirmado no próprio código-fonte:
o popover do workspace foi escrito "duplicado de propósito... mesma
linguagem visual" do antigo). Nenhuma mudança de código necessária -
já está padronizado onde existe o conceito de "múltiplos painéis numa
aba" (MERCADO/MACRO/VISÃO GERAL).

**Fora de escopo nesta fase, de propósito**: EQUITY/CVM/NEWS/RESEARCH/
TOP MERCADO não usam o conceito de "painéis múltiplos" - são blocos
monolíticos únicos por aba. Transformá-los em painéis registrados seria
uma decisão de PRODUTO (quais blocos viram painéis separados, em que
ordem), não uma padronização estrutural - fica reservado pras fases
dedicadas de cada aba (8/9/10), evitando mudança fora do escopo "só
estrutura, sem redesign" desta fase.

### FASE 7 — Produto da VISÃO GERAL (entender o mercado em ~10s)

**Achado**: a ordem de prioridade pedida (1 mercado agora, 2 IBOV, 3
altas/baixas, 4 negociados, 5 setores, 6 notícias, 7 globais, 8
watchlist) já é EXATAMENTE a ordem que `ui/visao_geral.py` já tinha
antes de qualquer mudança desta sessão (preservada 1:1 no
`REGISTRO_PAINEIS` da Fase 5) - nenhuma reordenação necessária. O
problema de "página vertical gigantesca" que a Fase 7 queria resolver
já foi endereçado estruturalmente pela Fase 5: agora os painéis são
arrastáveis/redimensionáveis livremente (o usuário pode pôr lado a
lado, encolher o que não interessa) em vez de forçosamente empilhados
um embaixo do outro. Nenhum conteúdo cortado ou dado novo inventado.
Nenhuma mudança de código necessária nesta fase além do que a Fase 5 já
entregou.

### FASE 8/9 — Auditoria de NEWS e CVM

**Achado**: ambas já foram estruturalmente redesenhadas em sessões
anteriores (ver histórico mais acima neste arquivo - "fase 3 NEWS" e
"P4/CVM" concluídas há várias sessões, bem antes deste roadmap de 16
fases existir). Confirmado lendo o código-fonte atual:
- **NEWS** (`ui/news_tab.py`): já é uma linha densa por notícia (HORA |
  SELO | MANCHETE | Nº FONTES | ↗), com tickers citados destacados
  (watchlist em cor de destaque), card expansível com resumo sob
  demanda, veículos com link, filtros por pill - bate ponto a ponto com
  o pedido da Fase 8.
- **CVM** (`ui/cvm_tab.py`): já é DATA | TICKER | TIPO | ASSUNTO com
  busca textual, filtro por ticker/tipo, paginação real, painel de
  destaques (fatos relevantes recentes + ticker mais ativo), card
  expansível - bate ponto a ponto com o pedido da Fase 9.

Nenhuma mudança de código feita - a auditoria confirmou que o trabalho
já existe e está à altura do pedido. Forçar uma reescrita aqui violaria
a regra de segurança do próprio roadmap ("não sobrescreva trabalho
existente sem entender o que é").

### FASE 13 — Auditoria de performance (fora de ordem - ver nota abaixo)

Feita antes das Fases 10-12 porque não dependem delas e porque
"filtros causando scroll pra cima" era um problema CONCRETO e
nomeado explicitamente, resolvível com um padrão já comprovado no
próprio projeto.

**"Analytics ficando pesado"**: não existe nenhuma feature/aba chamada
"Analytics" neste projeto (`grep` vazio) - item não se aplica ao
PREGÃO, provavelmente veio de um checklist genérico. Não inventei nada
pra "corrigir" algo que não existe.

**"Filtros causando comportamento de scroll pra cima" - achado real e
corrigido**: RESEARCH, CVM e TOP MERCADO disparavam rerun da PÁGINA
INTEIRA a cada clique num pill de filtro (ticker/tipo/casa/região/setor/
busca/paginação) - um rerun completo do Streamlit reresetava a posição
de scroll, exatamente o sintoma relatado. NEWS já tinha resolvido isso
pra sua lista com `@st.fragment` (achado lendo o próprio código-fonte).
Apliquei o MESMO padrão já comprovado (não é gambiarra nova, é o
mecanismo oficial do Streamlit pra isso) nas 3 funções de entrada:
`render_cvm`, `render_top_mercado`, `render_research` - cada uma
decorada com `@st.fragment`, isolando o rerun de clique-em-filtro só
àquele bloco. Zero mudança de dado/lógica/resultado financeiro - só
escopo de rerun. `coletar_pendentes`/`st.rerun()` internos do
RESEARCH continuam funcionando normalmente dentro do fragment (rerun
passa a ser escopado ao fragment, que é o comportamento desejado).

**Demais itens da lista** (rerenders desnecessários, consultas
repetidas, dados cacheáveis): auditoria do código de dados
(`data/mercado.py`, `data/prices.py`) mostra que o projeto já usa
`@st.cache_data` com TTL consistente (90s pro lote pesado da B3/
Ibovespa) em todos os pontos de coleta em lote revisados - não achei
chamada óbvia sem cache nem consulta duplicada nova. Auditoria mais
profunda (profiling real) fica pro próximo ciclo dedicado a
performance, se o Rodrigo achar que ainda vale depois de sentir o
efeito do fix de scroll.

**Testes**: `compileall` limpo; AppTest das 9 seções sem exceção
(RESEARCH/CVM/TOP MERCADO incluídos, agora como fragments).

**Arquivos alterados**: `ui/cvm_tab.py`, `ui/top_mercado_tab.py`,
`ui/research_tab.py` (um decorator `@st.fragment` + comentário em cada
função de entrada - nenhuma outra linha mudou).

### FASE 14 — Auditoria de consistência de UX (parcial)

Auditoria rápida e focada: mensagens de "empty state" (`st.info("Nenhum
X encontrado...")`) em CVM/NEWS/RESEARCH/paineis já seguem o MESMO
padrão de frase ("Nenhum [tipo] [encontrado/disponível] ... no
momento"), escopado corretamente por contexto (watchlist vazia vs
filtro sem resultado vs feed geral sem dado). Não achei inconsistência
real que valesse mudar - mais um caso de trabalho de sessões anteriores
já ter cuidado disso. Não fiz auditoria exaustiva de TODOS os padrões
pedidos (tabelas/badges/status/loading/erros/modais/botões/títulos) por
tempo - ver "não iniciado" abaixo.

## RELATÓRIO FINAL DO MODO AUTÔNOMO (2026-10-01)

### FASES CONCLUÍDAS
1. Market ticker unificado (commit `ed15135`)
2. Shell/geometria do terminal auditada e 1 bug de comentário corrigido (commit `77a40e9`)
3. Workspace MERCADO reconfirmado sem regressão (commit `e8c15e1`)
4. Workspace expandido pra MACRO (commit `e5d55e1`, antes do roadmap formal)
5. Workspace expandido pra VISÃO GERAL (commit `021f1fa`)
6. Padrão estrutural de painéis auditado - já consistente, sem mudança necessária
7. Produto da VISÃO GERAL auditado - ordem já era a pedida, resolvido pela Fase 5
8. NEWS auditada - já satisfaz a estrutura pedida (trabalho de sessão anterior)
9. CVM auditada - já satisfaz a estrutura pedida (trabalho de sessão anterior)
13. Performance: corrigido bug real de scroll pulando ao filtrar (RESEARCH/CVM/TOP MERCADO), commit `b316e83`

### FASES PARCIAIS
14. Consistência de UX: só um recorte (empty states) auditado e confirmado consistente; os demais padrões (tabelas/badges/loading/modais/botões/títulos) não foram revisados

### FASES NÃO INICIADAS (com motivo)
10. Research Intelligence (FATO/VISÃO DA CASA/INFERÊNCIA, nunca inventar consenso/preço-alvo): escopo grande e sensível a dado financeiro - já tinha sido explicitamente adiado pelo próprio Rodrigo numa sessão anterior ("Research Intelligence Layer pra ciclos seguintes"); não tentei nesta sessão pra não arriscar uma implementação rasa numa área onde "inventar" é o pior erro possível
11. "O que mudou?": depende conceitualmente da Fase 10 (separação FATO/VISÃO/INFERÊNCIA) pra fazer sentido de verdade
12. Integração entre fontes (NEWS↔RESEARCH↔CVM↔ASSET↔PRICE): depende das Fases 10/11 estarem prontas primeiro
15. Formatação visual: propositalmente NÃO tentada - é a prioridade mais baixa (ESTRUTURA > FUNCIONALIDADE > PERFORMANCE > CONSISTÊNCIA > VISUAL) e o projeto historicamente depende muito de confirmação visual direta do Rodrigo antes/depois de qualquer ajuste estético (extensa documentação de sessões anteriores sobre isso) - fazer sem esse ciclo de feedback é mais risco que ganho
16. Auditoria final: feita PARCIALMENTE (compileall + AppTest das 9 seções + testes dirigidos do workspace, todos verdes) - faltou screenshot real de cada aba (bloqueado por login Google, mesma limitação de sempre) e profiling real de performance

### BUGS ENCONTRADOS E CORRIGIDOS NESTA SESSÃO
- Especificidade CSS impedia `position:absolute` nos painéis do workspace (Fase anterior ao roadmap formal)
- Ponte JS→Python nunca comitava (faltava blur) - nada persistia de verdade
- Listener morto após rerun - só o primeiro gesto da sessão funcionava
- Duas faixas de ticker concorrentes, uma delas cortando visualmente
- Scroll pulando pro topo ao usar filtros em RESEARCH/CVM/TOP MERCADO
- Comentário desatualizado (z-index 50→56) no CSS do shell

### TESTES
`compileall` limpo em todo o projeto; AppTest das 9 seções sem exceção
(rodado múltiplas vezes ao longo da sessão); bateria dirigida isolada
do workspace (8/8); harness Playwright dedicado pro workspace (23/23 -
drag, resize nos 3 modos, interação com gráfico Plotly real,
persistência rerun/reload, restore); harness Playwright dedicado pro
ticker (14/14 - faixa única, animação real medida, geometria sem
sobreposição); harness Playwright pra scroll/vazamento visual (3/3,
usando amostragem de pixel real depois de descartar 2 metodologias que
davam falso-positivo).

### COMMITS DESTA SESSÃO (mais recentes primeiro)
`b316e83` perf, `021f1fa` feat workspace VISÃO GERAL, `e8c15e1` fix
docs workspace, `77a40e9` fix shell, `ed15135` feat ticker, `e5d55e1`
feat workspace MACRO (+ os commits anteriores da correção dos 3 bugs
reais do workspace MERCADO, já documentados acima no arquivo).

### LIMITAÇÕES
- Extensão do Chrome instável neste ambiente (padrão recorrente, documentado em sessões anteriores) - toda validação visual real dependeu de harnesses Playwright isolados (fora do app.py, sem login Google) em vez do app publicado diretamente
- Login Google impossível de automatizar - nenhum teste rodou contra `pregao.streamlit.app` de verdade nesta sessão; tudo foi validado em harnesses que reproduzem o mecanismo/CSS real, mas a confirmação final na URL publicada ainda depende do Rodrigo
- Fases 10-12 e 15 não iniciadas (motivos acima) - roadmap longe de "completo", mas o que foi feito é real, testado e já está em produção

### PRÓXIMOS PASSOS (sugestão, não determinado por mim)
1. Rodrigo validar visualmente o ticker novo + workspace em MACRO/VISÃO GERAL na URL publicada
2. Decidir se entra Fase 10 (Research Intelligence) como próximo ciclo grande, ou mais itens pontuais primeiro
3. Fase 15 (visual) só depois de tudo acima confirmado, com ciclo de feedback visual direto

## FASE RESEARCH — Resumos + inteligência de eventos (2026-10-01)

Rodrigo pediu explicitamente a Fase 10 que eu tinha deixado não-iniciada
(sensível demais pra arriscar sozinho antes). Auditoria completa antes
de codar (`ui/research_tab.py` + todo `data/research/*.py`):

**Achados da auditoria:**
- O prompt narrativo (`_PROMPT_SISTEMA` em `resumir.py`) já é sofisticado
  de propósito: 2-4 blocos narrativos adaptativos (nunca template fixo),
  regras fortes anti-invenção já existentes ("nunca invente declarações,
  números, preços-alvo..."), atribuição de falas a atores nomeados já
  obrigatória, foco por tipo de documento (MORNING_CALL/AÇÕES/MACRO) já
  existente. **Preservado integralmente** - só refinado, nunca
  substituído.
- `resumo` era só texto opaco - nenhum campo estruturado extraído/salvo.
  Bloqueava "O QUE MUDOU"/Research Radar de verdade.
- **Achado crítico de arquitetura**: `research_itens` (documentos/
  resumos) tem retenção de só 5 dias por design (conteúdo perecível) -
  impossível construir histórico de verdade em cima dela sozinha.
- Única fonte de dado estruturado hoje: `obter_recomendacoes()` (Genial,
  `data/research/genial.py`) - ticker/recomendação/preço-alvo AO VIVO,
  nunca persistido, e **efetivamente desligada em produção** (mesmo
  bloqueio de WAF que afeta toda coleta via Genial no Streamlit Cloud -
  `tentar_coleta_automatica: False`). `coletor_local.py` (roda na
  máquina do Rodrigo) hoje só coleta relatórios, não recomendações.

**Implementado nesta primeira parte** (`data/research/resumir.py`,
`data/research/store.py`, novo `data/research/historico.py`,
`sql/research.sql`):

1. **Extração estruturada de preço-alvo/recomendação**: nova chamada
   Groq pequena e barata (`_extrair_dados_estruturados`, max_tokens=60,
   reaproveita o MESMO texto já carregado - zero requisição de rede
   nova) rodando só pra documentos tipo ACOES (não desperdiça chamada em
   MACRO/NEWSLETTER/LIVE). Regra explícita: NAO_IDENTIFICADO em vez de
   estimar, sempre. `resumir_com_groq` agora retorna
   `(resumo, motivo, dados_estruturados)`; `obter_resumo` repassa pro
   Supabase (2 colunas novas em `research_itens`: `preco_alvo`,
   `recomendacao`, nullable).
2. **Histórico não-perecível** (`data/research/historico.py`, nova
   tabela `research_recomendacoes_historico`): só grava um snapshot
   NOVO quando recomendação/preço-alvo mudam de verdade desde o último
   conhecido daquele casa+ticker (nunca grava redundante). Base honesta
   pra "O QUE MUDOU" - compara valor de hoje com valor real do passado,
   nunca inventa um "antes" que não existiu. `processar_recomendacoes`
   (cache 30min, mesma janela de `obter_recomendacoes`) evita bater no
   Supabase a cada rerun da aba.

**Testes (todos passaram)**:
- `compileall` limpo; AppTest das 9 seções sem exceção.
- `historico.py`: 12 checks com Supabase mockado (primeiro snapshot
  grava mas não reporta "mudança"; sem mudança real não grava; mudança
  de preço-alvo/recomendação grava E retorna o valor anterior correto;
  banco fora do ar nunca quebra nem finge mudança; função `_mudou` nos
  casos extremos incluindo "preço None nos dois lados" sem falso-positivo).
- `resumir.py`: **9 cenários pedidos, com chamadas REAIS à Groq** (chave
  já configurada neste ambiente) - documento curto com preço-alvo e
  recomendação explícitos (extraídos certo: R$48/COMPRA); documento sem
  preço-alvo nem recomendação (None/None, não inventou); Morning Call
  (narrativa preservada, extração estruturada corretamente PULADA -
  economiza chamada); documento com múltiplos tickers (pegou o
  preço-alvo do ticker do TÍTULO - R$50 da ABCD4, não R$22 da XYZW3
  mencionada de passagem); documento vago sem dado financeiro nenhum
  (resumo gerado sem inventar nada). Nenhum resumo mencionou "não
  informado" (regra antiga preservada).

**Ação pendente do Rodrigo**: rodar o `sql/research.sql` atualizado no
SQL Editor do Supabase (idempotente - `if not exists` em tudo, seguro
re-rodar mesmo já tendo a tabela antiga) antes das próximas partes desta
fase funcionarem de ponta a ponta em produção.

**Próximas partes desta fase** (commits separados, em andamento):
wiring do histórico na UI (watchlist + "O QUE MUDOU"), coleta de
recomendações no `coletor_local.py` (hoje só coleta relatórios),
Research Radar, refino do foco de Morning Call, testes de UI/Playwright.

### Parte 2: histórico+radar na UI, coleta local

- `coletor_local.py`: além de `coletar_todas_disponiveis()` (relatórios),
  agora também chama `historico.coletar_snapshot_genial()` - mesmo
  motivo arquitetural (Genial bloqueada por WAF no Streamlit Cloud, só
  funciona rodando da máquina do Rodrigo). Sem isso, a tabela de
  histórico nunca seria populada em produção de verdade.
- `ui/research_tab.py`: `_painel_watchlist` ganhou um bloco "O QUE
  MUDOU" no topo (só aparece quando existe mudança REAL - nunca um
  resumo genérico do dia), citando a casa explicitamente ("Genial:
  Recomendação: COMPRA → MANTER", nunca "o mercado mudou"). Novo painel
  **Research Radar** (CASA | TICKER | TIPO | DATA | STATUS) com só 2
  sinais reais: "NOVO" (data de PUBLICAÇÃO do relatório é hoje - não
  `coletado_em`, que mudaria toda vez que uma fonte é re-raspada mesmo
  pra relatório antigo, dando falso "novo") e "MUDANÇA DE
  RECOMENDAÇÃO"/"MUDANÇA DE TARGET" (do histórico comparado de verdade).
  `processar_recomendacoes` calculado 1x em `render_research` e
  reaproveitado pelos dois painéis (watchlist filtra pra só os tickers
  do usuário; radar mostra tudo) - evita processar a mesma lista duas
  vezes/bater no Supabase em dobro.
- `data/research/store.py`: `_linha_para_item` passou a expor
  `coletado_em` (já existia na tabela, só não chegava até a UI).

**Testes**: `compileall` limpo; AppTest das 9 seções sem exceção.

### Parte 3: refino FATO vs VISÃO DA CASA + foco Morning Call

Adicionado ao `_PROMPT_SISTEMA` (não substituiu nada - acrescentou um
parágrafo novo de regra): quando o texto traz uma OPINIÃO/expectativa da
casa/analista (não um fato reportado), a atribuição precisa continuar
explícita dentro da narrativa ("Segundo a X...", "o analista espera...")
- nunca apresentar a tese de uma casa como fato do mercado; e se o
próprio sistema precisar conectar pontos que a fonte não conecta
explicitamente, isso precisa vir sinalizado como leitura própria ("o que
sugere...", "isso pode indicar..."), nunca como afirmação direta da
fonte. Foco de MORNING_CALL reforçado pra sempre nomear quem falou
(várias vozes num programa) e quais ativos/tickers específicos foram
citados, em vez de generalizar como "o mercado"/"as ações".

**Testado com chamadas reais à Groq** (2 cenários, 7 checks): documento
com fato (lucro divulgado) + visão de analista nomeado - resumo atribuiu
corretamente ("segundo Pedro Santos... que prevê...", nunca apresentou
como fato de mercado); Morning Call com 2 vozes e 3 tickers específicos
(AZUL4/PETR4/VALE3) - todos nomeados explicitamente no resumo, nenhum
generalizado. Preço-alvo/recomendação continuaram extraídos certo. Zero
regressão na qualidade do texto (ainda narrativo, ainda sem template
fixo).

### Parte 4: validação visual (Playwright) + suíte de testes commitada

**Validação visual**: harness isolado (CSS real do projeto, dados
mockados representando uma mudança de preço-alvo detectada + 1
relatório novo) via Playwright - confirmado sem erro de console, "O QUE
MUDOU" aparece com formatação clara ("ABCD4 · Genial Analisa ·
Preço-alvo: R$ 42,00 → R$ 48,00"), Research Radar mostra as 2 linhas
esperadas (MUDANÇA DE TARGET + NOVO) na mesma linguagem visual densa/
sem cards do resto do terminal. Screenshot confirma visualmente.

**Suíte de testes commitada** (`tests/test_research.py`, primeira vez
que o projeto commita um arquivo de teste - até aqui todo teste era
ad-hoc/documentado, nunca versionado): cobre só a parte 100%
determinística (parsing da extração estruturada + comparação de
histórico) com Groq e Supabase mockados - roda em qualquer máquina sem
`.streamlit/secrets.toml` nem custo de API. Os 9 cenários de qualidade
de texto pedidos (documento curto/longo, com/sem preço-alvo, Morning
Call, múltiplos tickers etc.) foram validados com chamadas REAIS à Groq
durante o desenvolvimento (ver Partes 1 e 3 acima) - esse tipo de
validação (qualidade de texto gerado por LLM, não-determinística) não
cabe numa suíte commitada que precisa rodar sempre igual; documentado
aqui em vez disso. 19 checks no arquivo commitado, todos passando.

**Testes finais**: `compileall` do projeto inteiro limpo; AppTest das 9
seções sem exceção.

## CORREÇÃO — Resiliência do pipeline de resumo (quota de IA, 2026-10-01)

Rodrigo reportou em produção: "Cota gratuita de resumo por IA esgotada
por enquanto" bloqueando o resumo mesmo com conteúdo disponível. Pedido
explícito: corrigir resiliência, NÃO mexer no conteúdo/prompt/estrutura
FATO-VISÃO-LEITURA/histórico/Radar já entregues.

**Causa exata**: `data/research/resumir.py:_chamar_groq` retorna
`(None, "cota")` em HTTP 429 (Groq, free tier) - `resumir_com_groq`
propagava isso direto pra UI sem nenhuma segunda tentativa.
`ui/research_tab.py:_AVISO_COTA` já mostrava mensagem amigável (não
vazava o 429 em si), mas o `else: st.caption(f"Resumo indisponível
({motivo}).")` em 2 pontos DO vazava texto cru de exceção pra qualquer
falha não-cota (ex: `str(e)` de erro de rede/timeout) - achado
adicional, corrigido junto por estar na mesma função/escopo.

**Fallback utilizado**: nenhum segundo PROVEDOR estava configurado no
projeto (confirmado por auditoria - só Groq, em `resumir.py`/`news.py`/
`cvm.py`, cada um com seu próprio client). Mas a MESMA conta Groq
oferece vários modelos com cota/rate-limit POR MODELO (não por conta) -
testado manualmente nesta sessão: `openai/gpt-oss-20b` (principal) e
`openai/gpt-oss-120b` (mesma família, escolhido como fallback) ambos
respondem normalmente com a chave já configurada. **Fallback habilitado
SEM nenhuma credencial nova** - só mais um model id na mesma chamada,
exatamente o que o pedido pedia pra verificar antes de inventar algo.

**Implementado**:
- `config.py`: `GROQ_MODELO_FALLBACK = "openai/gpt-oss-120b"` +
  `obter_modelo_groq_fallback()` (nova função, não mexe em
  `obter_credenciais_groq()` - `data/news.py` já desempacota essa como
  tupla de 2, mudar pra 3 quebraria NEWS, fora do escopo desta correção).
- `data/research/resumir.py`: nova `_chamar_groq_com_fallback` - tenta
  principal, se falhar (cota OU qualquer erro técnico - timeout/5xx/
  conexão, nunca por falta de conteúdo) tenta o fallback UMA única vez
  (nunca repete em loop). Retorna sempre um motivo de um conjunto
  pequeno e seguro (`None`/`"cota"`/`"indisponivel"`) - o texto cru da
  exceção some pro log (`_log_erro_ia`: provedor, modelo, tipo de erro,
  timestamp - só no stdout/Logs do Streamlit Cloud, nunca na UI).
  `_condensar_texto_longo` (documentos longos) usa o mesmo mecanismo,
  com uma otimização: se o principal falhar num pedaço, os pedaços
  seguintes (e a chamada narrativa final) pulam direto pro fallback em
  vez de martelar um modelo recém-falho de novo (nunca chamada extra
  desnecessária).
- `ui/research_tab.py`: novo aviso amigável `_AVISO_IA_INDISPONIVEL`
  pro motivo "indisponivel" (distinto de "cota") - mesma linguagem
  curta, nunca HTTP/exceção/stack trace.

**Cache confirmado (já existia, nenhuma mudança)**: `rel.get("resumo")`
é checado ANTES de chamar `obter_resumo` em `_linha_relatorio`/
`_abrir_resumo_live` - um documento com resumo salvo nunca aciona nova
chamada de IA. `link` (chave primária de `research_itens`) já é
identificador suficiente.

**Testes**: `compileall` limpo; AppTest das 9 seções sem exceção;
chamada real ao modelo principal confirmando que o caminho feliz
continua intacto; 7 cenários novos em `tests/test_research.py` (modelo
principal funciona sem tentar fallback; cota aciona fallback com
sucesso; erro técnico não-cota também aciona fallback; ambos falhando
retorna motivo seguro sem nenhum detalhe técnico vazado - verificado
literalmente que "stack trace"/host/porta não aparecem no motivo
retornado; `pular_principal` evita chamada redundante; resumo já salvo
nunca chama `obter_resumo` de novo, testado na função REAL da UI; erro
de extração de texto continua com motivo distinto de erro de IA, nunca
confundidos). 36 checks no total no arquivo, todos passando.

**Limitação que continua**: se AMBOS os modelos da Groq esgotarem cota
ao mesmo tempo (ex: free tier inteiro no limite diário), não há
terceiro fallback - o documento fica preservado (nada é apagado, nenhum
dado é inventado) e o usuário vê "Resumo por IA temporariamente
indisponível", podendo tentar de novo mais tarde (cota reseta por
janela de tempo). Habilitar um provedor de IA diferente (ex: OpenAI,
Anthropic, Cerebras) exigiria uma credencial nova - não implementado
intencionalmente (pedido explícito: não inventar credencial/serviço).

## FASE — RESEARCH ↔ NEWS: contexto por ativo (2026-10-01)

Primeira integração entre fontes do PREGÃO (escopo explicitamente
limitado a RESEARCH↔NEWS - sem CVM/preço/causalidade nesta fase).

**Auditoria antes de codar**: `data/news.py:obter_noticias(ticker)` já
existia, cacheada (`@st.cache_data(ttl=20min)`), já filtra por
relevância (ticker/nome no título), já retorna ordenado por data desc,
já respeita retenção de 5 dias, já usa o MESMO identificador (`ticker`)
que Research usa em `tickers: list`. **Nenhum sistema de identificação
novo foi criado** - reaproveitamento direto, exatamente como pedido.

**Implementado**: `ui/research_tab.py:_bloco_contexto_news(tickers)` -
chama `obter_noticias(ticker)` pra cada ticker do item (normalmente só
1), deduplica por link, ordena por data desc, mostra até 5
(`_LIMITE_CONTEXTO_NEWS`), só título+data+link (nunca gera resumo de
IA, nunca afirma causalidade - "CONTEXTO RECENTE · NEWS" com itens lado
a lado, sem nenhuma frase tipo "subiu por causa de"). Se não houver
notícia ou a fonte falhar, a seção simplesmente não aparece (pedido
explícito).

**Decisão de performance chave**: a seção só é chamada logo após
`_bloco_resumo(...)` já ter sido exibido (4 pontos em
`ui/research_tab.py`) - nunca na lista inteira do feed (que pode ter até
60 itens). Isso significa, no máximo, 1-3 chamadas a `obter_noticias`
por vez (quando o usuário de fato abre/expande UM item), nunca N+1 na
renderização da lista inteira - satisfaz "a integração não pode tornar
a abertura do Research significativamente mais lenta" sem nenhum
mecanismo novo de cache (reaproveita o cache de 20min que
`obter_noticias` já tinha).

**Testes** (`tests/test_research_news_context.py`, novo arquivo, 11
checks, tudo mockado/sem rede): research com ticker mostra notícias
relacionadas; sem notícias (lista vazia ou fonte indisponível) não
quebra, seção some; múltiplas notícias ordenadas por data DESC e
limitadas a 5; notícia de ticker diferente nunca aparece (confirma que
nunca mistura tickers); tickers vazio/None nunca chama a fonte; **sem
N+1** (exatamente 1 chamada por ticker do item, nunca mais, mesmo com 3
notícias retornadas ou 2 tickers no mesmo item); nenhuma chamada a
`obter_resumo` (IA) a partir dessa função.

Validação visual via Playwright (harness com dados mockados) - "CONTEXTO
RECENTE · NEWS" renderiza certo nas 2 posições (watchlist e feed), estilo
denso/terminal consistente com o resto da aba, zero erro de console.
`compileall` do projeto + testes anteriores do Research + AppTest das 9
seções, todos sem regressão.

**Arquivo alterado**: só `ui/research_tab.py` (import de
`data.news.obter_noticias` + nova função + 4 chamadas) e o novo arquivo
de teste. Nenhuma mudança em `data/news.py`, prompt, histórico ou
Research Radar.

## FASE — CALENDÁRIO de resultados corporativos (2026-10-01)

Nova aba CALENDÁRIO, focada em resultados (ITR/DFP) - primeira versão.

**Auditoria antes de codar**: `data/cvm.py` já tinha uma categoria
oficial da CVM chamada literalmente "Calendário de Eventos
Corporativos" e outra "Dados Econômico-Financeiros" (filtrada por
`_TIPOS_RESULTADOS` pros tipos que são resultado de verdade - press-
release, demonstrações financeiras). `_ipe_ano()` baixa o CSV da CVM
(~30-40 mil linhas, TODAS as empresas) **1 vez por ano, cacheado** -
filtrar por CNPJ depois é operação em memória, não uma requisição nova
por ticker. Isso significa que calcular o calendário pra "TODOS" os
~76 tickers do Ibovespa é barato (1 download cacheado + N filtros em
memória), não N requisições.

**Decisão de arquitetura mais importante desta fase**: não existe hoje
nenhuma fonte automática confiável de "data CONFIRMADA pela empresa"
nem "data ESTIMADA por consenso" integrada ao projeto - extrair isso de
PDF de "Calendário de Eventos Corporativos" exigiria parsing de texto
livre sem IA, com risco real de ler a data errada e apresentá-la como
oficial (indo direto contra "nunca inventar datas"). A única fonte REAL,
pública e determinística disponível é o **prazo regulatório** da CVM
(Instrução CVM 480/2009): ITR até 45 dias após o fim do trimestre, DFP
até ~3 meses após o fim do exercício. Por isso, nesta v1, **todo evento
calculado tem status PRAZO_CVM** - a camada normalizada (`data/eventos.py`)
já tem os status CONFIRMADO/ESTIMADO prontos pra quando/se uma fonte
confiável desses for integrada depois (documentado explicitamente no
módulo, não escondido).

**Bug real encontrado e corrigido durante o desenvolvimento**: a busca
pelo "próximo trimestre pendente" começava no trimestre que CONTÉM hoje,
em vez do trimestre ANTERIOR (que acabou de se encerrar e ainda está
dentro do prazo de entrega) - em 01/10/2026 (temos o exemplo do próprio
Rodrigo usando "3T26"), isso pulava direto pro 4T26/DFP, ignorando o 3T26
que só vence em 14/11. Pego pelos próprios testes (cenário 3c/3d) antes
de qualquer uso real.

**Implementado**:
- `data/eventos.py` (novo): `calcular_proximo_resultado(ticker)` /
  `calcular_calendario(tickers)` - cruza com `obter_documentos_cvm`
  (mesmo identificador/fonte que CVM já usa) pra NÃO mostrar como
  "pendente" um trimestre que a empresa já entregou de verdade.
  Limitação documentada: assume ano fiscal = ano civil (maioria das
  empresas B3).
- `ui/calendario_tab.py` (novo): `PRÓXIMOS RESULTADOS DA WATCHLIST`
  (destaque + contagem "X eventos nos próximos 7 dias") + agenda
  agrupada por data com filtros [MINHA WATCHLIST/TODOS/SETOR] ×
  [SEMANA/MÊS] (setor reaproveita `config.IBOVESPA_SETORES`, já
  existente). Cada evento abre um `st.expander` com ticker/empresa/
  período/data+horário/status/fonte + contexto **somente se já houver
  dado no sistema** (CVM/NEWS/RESEARCH - reaproveita
  `obter_documentos_cvm`/`obter_noticias`/`store.listar_itens`, as
  MESMAS funções cacheadas que as outras abas já usam) - zero chamada
  de IA em qualquer ponto desta aba.
- `config.py`: `"CALENDÁRIO"` adicionado a `ABAS_DISPONIVEIS` (migra
  automaticamente pra usuários existentes, mesmo mecanismo que já
  existia) + ícone Material.
- `app.py`: import + bloco de seção, mesmo padrão de CVM/NEWS.

**Testes** (`tests/test_eventos.py`, novo, 21 checks, tudo mockado/sem
rede): prazo CVM calculado certo pro trimestre corrente; resultado já
entregue pula pro próximo trimestre; prazo já vencido também pula;
evento sem horário (nunca inventado); ausência de documento CVM ainda
permite calcular o prazo regulatório; data_referencia inválida/ausente
não quebra nem conta como "já entregue"; ticker duplicado gera 1 evento
só; fonte CVM indisponível nunca inventa evento (e não derruba o
cálculo dos outros tickers); só processa os tickers recebidos (nunca
busca por conta própria); estrutura (status/rótulos) já suporta
CONFIRMADO/ESTIMADO mesmo sem fonte real ainda. `compileall` do projeto
+ AppTest das 10 seções (nova aba incluída) sem exceção. Validação
visual via Playwright (harness com eventos sintéticos cobrindo os 3
status, incluindo clicar e expandir o detalhe de um evento) - zero erro
de console.

**Limitações**: sem data CONFIRMADA/ESTIMADA de verdade ainda (ver
decisão de arquitetura acima); assume ano fiscal = ano civil; "horário"
nunca é preenchido (CVM não informa isso); setor vem de
`config.IBOVESPA_SETORES` (curado manualmente, pode não cobrir 100% dos
tickers novos - mesma limitação que MERCADO já tinha).

## FASE — CALENDÁRIO V2: datas reais de resultados (2026-10-01)

Rodrigo pediu pra evoluir o calendário pra ter CONFIRMADO/ESTIMADO de
verdade, com uma investigação explícita antes de implementar.

**Investigação real feita nesta sessão (achado definitivo, verificado
com dado AO VIVO da CVM, não suposição)**: baixei e inspecionei as
linhas reais de 2026 da categoria oficial "Calendário de Eventos
Corporativos" do IPE da CVM (onde a empresa de fato comunica seu
calendário). Resultado: `Tipo`, `Especie` e `Assunto` vêm todos vazios
(NaN) pra essa categoria - os ÚNICOS campos estruturados são
`Data_Entrega` (quando o documento foi protocolado, não quando o
resultado sai) e `Data_Referencia` (sempre fixo em 31/12, é o fim do
exercício que o calendário cobre, não uma data de evento). **A data real
do resultado só existe dentro do PDF** (`Link_Download`) - extrair isso
seria exatamente o "texto ambíguo" que o pedido proíbe tratar como
CONFIRMADO. Tentei também achar um endpoint estruturado da B3 (mesmo
domínio que já funcionou pra composição do Ibovespa,
`sistemaswebb3-listados.b3.com.br`) - sem a extensão do Chrome
funcionando (instável de novo nesta sessão, mesmo padrão recorrente) não
dá pra inspecionar o tráfego de rede real do site da B3 pra confirmar um
endpoint de agenda, e não inventei um endpoint que não pude verificar.

**Decisão honesta**: não existe hoje fonte automática segura de
CONFIRMADO (anunciado pela empresa) nem ESTIMADO (fonte externa
confiável) pra integrar sem violar "nunca inventar data"/"nunca extrair
de texto ambíguo". O pipeline real (`calcular_calendario`) continua
produzindo só PRAZO_CVM - **nenhuma mudança de cobertura**, só de
arquitetura. O que foi entregue: a camada de prioridade/deduplicação e
resiliência de cache, testada com dados sintéticos, pronta pra quando
uma fonte confiável existir (manual, verificada pelo próprio Rodrigo no
RI da empresa, ou um endpoint B3 confirmado numa sessão futura) - zero
refatoração necessária nesse dia.

**Implementado** (`data/eventos.py`):
- `PRIORIDADE_STATUS` (CONFIRMADO=3 > ESTIMADO=2 > PRAZO_CVM=1).
- `mesclar_eventos(*listas)`: deduplica eventos do MESMO (ticker,período)
  vindos de várias fontes na mesma rodada, mantendo só o de maior
  confiabilidade - nunca mostra dois eventos pro mesmo resultado. A
  fonte perdedora fica preservada em `_fontes_alternativas` (nunca
  escondida, só não vira linha duplicada).
- `aplicar_cache_resiliente(eventos)`: cache (`st.cache_resource`, mesma
  técnica já usada em `data/research/__init__.py`) por (ticker,período) -
  se uma fonte de maior confiabilidade falhar numa consulta pontual,
  mantém o último dado válido conhecido (nunca regride CONFIRMADO/
  ESTIMADO de volta pra PRAZO_CVM) e marca `_pode_estar_desatualizado`
  (nunca escondido). `calcular_calendario` já passa por essa camada -
  benefício imediato mesmo só com PRAZO_CVM hoje (uma falha pontual da
  CVM não some mais o evento da tela).
- Evento ganha `coletado_em`.

**UI** (`ui/calendario_tab.py`): watchlist agora ordena por
CONFIRMADO > ESTIMADO > PRAZO_CVM (não só por data, pedido explícito);
detalhe do evento mostra fonte como link clicável quando há URL, aviso
"⚠ pode estar desatualizado" quando resgatado do cache, e qualquer
fonte alternativa perdida na deduplicação (nunca escondida).

**Testes** (`tests/test_eventos.py`, +12 checks novos, 33 no total):
os 11 cenários pedidos, com eventos sintéticos (já que não há fonte real
de CONFIRMADO/ESTIMADO - documentado em cada teste) provando que a
CAMADA funciona: data oficial vira CONFIRMADO preservando fonte+URL;
fonte externa confiável vira ESTIMADO sem esconder a fonte; pipeline
real sem fonte oficial só produz PRAZO_CVM (nunca inventa); CONFIRMADO
substitui ESTIMADO e PRAZO_CVM numa mesma rodada (fonte perdedora
preservada); ausência de fonte nunca inventa evento; dedup nunca funde
tickers/períodos diferentes; fonte indisponível preserva o último
CONFIRMADO conhecido (marcado como desatualizado, nunca escondido);
cache grava a chave corretamente; evento já confirmado não regride numa
consulta seguinte; watchlist ordena por confiabilidade. `compileall` do
projeto + AppTest das 10 seções sem exceção (nenhuma regressão).
Validação visual via Playwright confirmando fonte clicável, aviso de
desatualizado e fonte alternativa visível, zero erro de console.

**Arquivos alterados**: `data/eventos.py`, `ui/calendario_tab.py`,
`tests/test_eventos.py`. Nenhuma mudança em Research/News/header/
ticker/workspace.

## FASE — CALENDÁRIO V3: corrigir semântica da UI (2026-10-02)

Correção pequena e cirúrgica pedida: hoje os únicos eventos reais são
PRAZO CVM, mas a UI colocava todos sob o rótulo "PRÓXIMOS RESULTADOS" -
risco real do usuário interpretar o prazo regulatório como se fosse a
data em que a empresa vai divulgar o resultado (as duas coisas são
frequentemente bem diferentes na prática).

**Mudança feita, só em `ui/calendario_tab.py`** (nenhuma linha de
`data/eventos.py` tocada - lógica/fonte dos eventos intocada):
- `_painel_proximos_watchlist` (painel da watchlist, renomeado de
  "PRÓXIMOS RESULTADOS DA WATCHLIST" pra "RESULTADOS DA WATCHLIST")
  agora separa em DUAS listas sob subtítulos distintos: "PRÓXIMOS
  RESULTADOS" (só CONFIRMADO/ESTIMADO - com "Nenhuma data de divulgação
  confirmada." quando vazio, exatamente como pedido) e "PRAZOS CVM" (só
  PRAZO_CVM, ticker+data+período+badge). As duas nunca aparecem sob o
  mesmo rótulo - se no futuro existir CONFIRMADO/ESTIMADO de verdade,
  automaticamente vai pra seção certa (a separação é por `status`, não
  por posição).
- `_detalhe_evento`: quando o status é PRAZO_CVM, mostra explicitamente
  "Prazo regulatório para entrega do documento. Não representa
  necessariamente a data de divulgação do resultado." - texto exato
  pedido. CONFIRMADO/ESTIMADO não mostram esse aviso (não se aplica).
- Painel principal da agenda renomeado de "CALENDÁRIO DE RESULTADOS"
  pra "CALENDÁRIO" (neutro - cada linha já mostra seu status/badge real,
  só o título do painel prometia algo que a lista não entrega hoje).
  Mensagem de período vazio corrigida de "Nenhum evento no período
  selecionado." pra "Nenhum evento no período." (texto exato pedido) -
  só aparece quando NÃO há evento nenhum (nem PRAZO_CVM); quando só há
  PRAZO_CVM, a lista mostra eles normalmente (nenhuma mudança de
  comportamento aqui, só confirmado que já era assim).

**Testes**: `tests/test_calendario_ui.py` (novo, 12 checks, mocka só
`calcular_calendario`/contexto - sem rede/IA): só PRAZO_CVM mostra a
mensagem certa e nunca aparece sob PRÓXIMOS RESULTADOS; CONFIRMADO e
ESTIMADO aparecem em PRÓXIMOS RESULTADOS, nunca em PRAZOS CVM; mix dos
dois fica em seções corretas e na ordem certa (resultados antes dos
prazos); mensagem de período vazio com o texto exato pedido; detalhe de
PRAZO_CVM mostra o aviso obrigatório; detalhe de CONFIRMADO não mostra
esse aviso. `tests/test_eventos.py` (33 checks, lógica/fonte intocada)
continua passando sem nenhuma mudança. `compileall` do projeto +
AppTest das 10 seções sem exceção. Validação visual via Playwright
(cenário misto CONFIRMADO+ESTIMADO+PRAZO_CVM) confirma a separação
visual e o aviso no detalhe, zero erro de console.

**Arquivo alterado**: só `ui/calendario_tab.py` + novo
`tests/test_calendario_ui.py`.

## FASE — CALENDÁRIO: Hub do evento (2026-10-02)

Evoluiu só a interação de detalhe (`_detalhe_evento`) - transformou o
card simples (ticker/período/data/status/fonte) num hub compacto com 4
seções: RESEARCH, NEWS, CVM, HISTÓRICO, nessa ordem (pedido explícito).

**Achado real na auditoria antes de codar**: RESEARCH/NEWS/CVM já
existiam desde a fase anterior do CALENDÁRIO (`_contexto_research`/
`_contexto_news`/`_contexto_cvm`) - só faltava HISTÓRICO. `_contexto_cvm`
já chamava `obter_documentos_cvm(ticker)` sozinha; pra adicionar
HISTÓRICO sem bater 2x na mesma fonte (pedido explícito: evitar N+1),
`_detalhe_evento` passou a buscar os documentos UMA vez e repassar pra
`_contexto_cvm` e pra `_contexto_historico` (ambas agora recebem a lista
pronta, não o ticker) - confirmado com teste que faz asserção sobre
`call_count == 1`.

**HISTÓRICO** (`_contexto_historico`, novo): filtra os MESMOS documentos
CVM já buscados por tipo `"RESULTADOS"` (mesmo campo que
`data/eventos.py:_ja_entregou` já usa internamente pra saber se um
trimestre foi entregue - aqui só exposto pro usuário em vez de só
usado no cálculo), ordenado por data desc, até 4 itens, com a data de
referência do trimestre quando disponível. Zero fonte nova, zero
chamada de IA.

**Não mexido**: `data/eventos.py` (lógica/fonte dos eventos intocada),
Research/News/CVM (só consumidas via suas próprias funções já
cacheadas), header/ticker/workspace.

**Testes** (`tests/test_calendario_ui.py`, +17 checks, 29 no total):
evento com as 4 fontes disponíveis mostra as 4 seções na ordem certa
(RESEARCH→NEWS→CVM→HISTÓRICO) e confirma 1 única chamada a
`obter_documentos_cvm`; evento sem algumas fontes oculta só as vazias
(documento genérico não-RESULTADOS aparece em CVM mas não em HISTÓRICO);
ticker sem dado nenhum oculta as 4 seções, inclusive quando a fonte CVM
retorna `None` (indisponível) em vez de lista vazia - sem quebrar; todos
os links apontam pra URL original e abrem em nova aba; nenhuma chamada
a `resumir_com_groq`/`obter_resumo` (funções de IA do projeto)
acontece ao montar o hub. `tests/test_eventos.py` (33 checks) e
`tests/test_calendario_ui.py` (12 checks da V3) continuam passando sem
alteração. `compileall` do projeto + AppTest das 10 seções sem exceção.
Validação visual via Playwright com as 4 seções populadas (Petrobras:
research+news+cvm+histórico sintéticos) confirma renderização compacta
no estilo terminal, link clicável, zero erro de console.

## FASE 3 — evolução completa de NEWS + RESEARCH (2026-10-08)

Pedido do Rodrigo, executado de forma autônoma (sessão agendada, sem
aprovação intermediária): transformar NOTÍCIAS num feed editorial de
terminal (foto + título + resumo curto), intercalar o Morning Call
cronologicamente no mesmo feed (em vez de seção isolada), melhorar o
resumo do Morning Call (estrutura real em vez de genérico) e integrar
NEWS↔RESEARCH de forma compacta — sem introduzir N+1, sem nova chamada
de rede por card/imagem, sem duplicar o sistema de cache/IA existente.

**Auditoria antes de codar** (pra não duplicar nem contradizer decisões
já tomadas): li `data/news.py` (score de confiabilidade, agrupamento
por fato, cache `st.cache_data` de 20min, resumo por grupo via
`data/ia_cache.py` — cache GLOBAL no Supabase desde 2026-10-05),
`data/research/resumir.py` (prompt narrativo + `_FOCO_POR_TIPO`, já
tinha um foco `MORNING_CALL` desde a fase do Morning Call/lives da
Genial), `data/research/genial_lives.py` (coleta de metadados via RSS
do YouTube + legenda automática), `ui/news_tab.py` (estilo "wire" denso
reusado por TOP MERCADO e pelo bloco compacto da EQUITY) e
`ui/research_tab.py` (dialog `_abrir_resumo_live`, painel de
recomendações da Genial). Decisão central: **reusar tudo isso**, nunca
criar um pipeline paralelo.

**Decisão de arquitetura mais importante — foto sem rede extra**: o
RSS do Google News não traz imagem de matéria (só título/veículo/data).
A única forma de ter foto real sem violar "nunca 1 chamada de rede por
card" é extrair o `og:image` do MESMO HTML que já é baixado pra gerar o
resumo via `trafilatura` — e `trafilatura.extract(..., with_metadata=True,
output_format="json")` devolve texto+metadado (incluindo `image`) numa
chamada só, confirmado com um teste local antes de codar (HTML
sintético com `og:image`, sem rede). Resultado: a foto fica disponível
exatamente quando o resumo também fica (lazy, sob demanda, cacheada
globalmente no Supabase junto do resumo) — zero fonte nova, zero custo
extra, nunca inventada (fallback visual discreto quando ausente/falha).

**Decisão — card do feed só mostra o que já está cacheado**: gerar
resumo/imagem pra TODOS os itens visíveis da lista seria N+1 real (e
custaria cota de IA/trafilatura à toa pra itens que o usuário nunca vai
abrir). Em vez disso, `data/ia_cache.py:obter_varios` faz 1 única
query (`IN (...)`) pra todas as chaves visíveis, e
`data/news.py:obter_resumos_prontos` embrulha isso pro formato do feed.
Item ainda não resumido por ninguém aparece só com título+meta (nunca
inventa teaser) — e assim que QUALQUER usuário abrir o dialog e gerar o
resumo pela primeira vez, o card dele passa a mostrar foto+teaser pra
TODO MUNDO nas próximas renderizações (cache global, mesmo mecanismo
que já existia).

**Decisão — Morning Call cronológico precisa de hora real**: o campo
`data` de `research_itens` sempre foi só a DATA (dia), nunca a hora —
suficiente pro resto do projeto, insuficiente pra intercalar "08:30
MORNING CALL" entre notícias de minuto certo. O feed do YouTube
(`genial_lives.py`) já trazia `published_parsed` com hora completa, só
que era truncado pra `[:10]` antes de salvar. Solução: nova coluna
`publicado_em` (timestamptz, nullable) em `research_itens`, preenchida
só pela Genial Lives — `data` (coluna antiga, usada por todo o resto do
projeto: radar, retenção, filtro por dia) **intocada**. Pra não quebrar
a coleta de QUALQUER outra casa enquanto o Rodrigo não rodar a migração
no Supabase, `store.salvar_itens` tenta o upsert COM a coluna nova e,
se falhar (coluna ainda não existe), tenta de novo SEM ela antes de
desistir — confirmado com teste simulando exatamente esse cenário
("column ... does not exist" na 1ª tentativa, sucesso na 2ª). Sem
`publicado_em` (linha antiga ou coluna não migrada ainda), o item nunca
mostra uma hora inventada — só entra no feed numa posição aproximada
(meio-dia da data, só pra ordenar) e a UI mostra o horário em branco,
nunca "08:00" fingindo precisão que não existe. Isso também corrigiu
um bug real pego pelo próprio teste de ordenação: comparar as strings
ISO cruas (ex: `"09:42-03:00"` vs `"11:30+00:00"`) ordena errado entre
fusos diferentes — a ordenação do feed agora usa `datetime` parseado de
verdade, não a string.

**Decisão — resumo do Morning Call reescrito, mesmo sistema**: só o
texto do foco `MORNING_CALL` em `_FOCO_POR_TIPO` (resumir.py) mudou —
zero pipeline novo, zero prompt paralelo, mesmo cache/fallback de
modelo de sempre. Pede estrutura real (**O QUE IMPORTA HOJE** com
subtemas Brasil/Exterior/Juros/Câmbio/Commodities/Ações, só os que o
episódio de fato cobriu; **DESTAQUES** com os tickers citados pelo
nome), reforça a separação FATO/VISÃO DA CASA/LEITURA já existente no
prompt geral, e proíbe explicitamente inventar tese, impacto, consenso,
preço-alvo, recomendação ou causalidade que o programa não disse — com
uma válvula de escape explícita pro formato narrativo genérico quando o
episódio não tiver conteúdo real pra nenhum dos 2 blocos (nunca força
template vazio, mesma filosofia que já existia no prompt geral).

**Integração NEWS↔RESEARCH**: bloco compacto "Research" dentro do
dialog de detalhe da notícia, só quando algum ticker do item já tem
recomendação/preço-alvo coletado pela Genial — reusa
`data/research/genial.py:obter_recomendacoes()` (já cacheada, já usada
pela aba RESEARCH), nunca uma chamada nova, nunca N+1 (só dispara
dentro do dialog já aberto pelo clique do usuário).

**O que NÃO foi tocado**: `_linha_noticia`/`_renderizar_lista` (estilo
"wire" denso original) continuam exatamente como estavam — usados só
por TOP MERCADO e pelo bloco compacto de NOTÍCIAS da aba EQUITY,
deliberadamente fora do escopo visual desta fase pra não arriscar
regressão onde não foi pedido. CALENDÁRIO, CVM, MACRO, MERCADO, preços,
coleta não relacionada, Supabase (arquitetura geral) e o sistema de
cache existente (`data/ia_cache.py`) — zero mudança estrutural, só uso.

**Testes**: `tests/test_news_fase3.py` (novo, 26 checks) — extração de
imagem do mesmo download (sucesso, sem `og:image`, imagem relativa/
inválida descartada, JSON malformado do `trafilatura.extract` não
quebra, falha de download, link não resolvido), `obter_resumos_prontos`
em lote (1 única chamada, nunca por grupo), merge cronológico
NOTÍCIA+LIVE (ordem correta, tipo certo, feed vazio), hora de exibição
honesta (nunca inventa HH:MM), teaser de notícia (extrai O QUE
ACONTECEU+IMPACTO, nunca "não informado", cai pro texto cru se o
formato não bater) e teaser de live (remove título do bloco e tags
`<b>`). `tests/test_ia_cache.py` (+9 checks, 38 no total) —
`obter_varios`: só devolve concluído, nunca gera/reserva, lista vazia e
Supabase fora do ar não quebram, erro de schema não quebra, exatamente
1 query pra várias chaves (prova direta contra N+1).
`tests/test_research_fase3.py` (novo, 17 checks) — `publicado_em`
extraído do mesmo feed (com e sem o campo estruturado), `data` (coluna
antiga) intocada, upsert aditivo/gracioso (com a coluna, sem nenhum
item com ela, retry sem a coluna quando ela não existe no banco, falha
persistente retorna False sem exceção), `_linha_para_item` com
`.get()` seguro, e o prompt do foco MORNING_CALL (pede os 2 blocos,
proíbe resumo genérico, reforça FATO vs VISÃO DA CASA, proíbe inventar
preço-alvo/recomendação/consenso, permite cair pro formato genérico sem
conteúdo real). Todos os 10 arquivos de teste do projeto (104+ checks
no total) passando, `compileall` limpo (venv recriado com Python 3.12,
já que `app.py`/`ui/mercado_tab.py` usam sintaxe de f-string aninhada
só válida a partir do 3.12 — nada relacionado a esta fase, achado do
próprio setup do ambiente).

Validação de nível Streamlit via 2 harnesses `AppTest` isolados
(scratchpad, fora do repo — mesmo padrão de sessões anteriores: nunca
tocam `auth.py`/login real, que é impossível de automatizar). Harness 1
(feed editorial): cenário completo (notícia com foto cacheada, notícia
sem imagem/fallback, Morning Call intercalado cronologicamente, teaser
de ambos aparecendo) sem exceção; clique na manchete abre o dialog,
gera resumo+imagem, mostra o contexto RESEARCH (recomendação Genial)
sem exceção; falha total das fontes (notícias=None, lives=None) não
quebra a página; watchlist vazia mostra o aviso certo; live sem resumo
ainda gerado mostra o aviso "clique pra gerar". Harness 2 (TOP
MERCADO/EQUITY, estilo wire): confirma que os dois pontos que reusam
`_renderizar_lista`/`_linha_noticia` continuam funcionando sem nenhuma
mudança visual, incluindo o dialog com a seção nova de contexto
RESEARCH, sem exceção.

**Nota de validação visual (honesta)**: este ambiente é um sandbox na
nuvem sem Playwright/Chromium configurado contra o app Streamlit
completo (nem haveria como passar pelo login Google do `auth.py`, limite
já documentado em fases anteriores). A correção dos harnesses `AppTest`
acima prova que o Streamlit renderiza sem exceção, estados de erro
degradam graciosamente e os fluxos de clique funcionam — **não** prova
como o card realmente fica na tela (cor exata, densidade, alinhamento,
responsividade). Isso fica como pendência real: Rodrigo confirmar
visualmente em `pregao.streamlit.app` depois do deploy, e rodar a
migração `sql/research.sql` atualizada no Supabase (idempotente) pra
`publicado_em` passar a ser preenchido de verdade (sem ela, Morning
Call aparece no feed sem hora exibida — degradação já prevista, nunca
quebra).

**Arquivos alterados**: `ui/news_tab.py` (feed editorial + integração
Morning Call/RESEARCH), `data/news.py` (extração de imagem +
`obter_resumos_prontos`), `data/ia_cache.py` (`obter_varios`, leitura em
lote), `data/research/resumir.py` (prompt do foco MORNING_CALL),
`data/research/genial_lives.py` (`publicado_em`), `data/research/store.py`
(`publicado_em` aditivo/gracioso), `sql/research.sql` (coluna nova,
idempotente) + `tests/test_news_fase3.py`,
`tests/test_research_fase3.py` (novos) e `tests/test_ia_cache.py`
(estendido). Nenhuma mudança em `app.py`, CALENDÁRIO, CVM, MACRO,
MERCADO, preços, Supabase (arquitetura) ou no estilo "wire" original.

## FASE — ciclo de melhoria contínua pós-FASE 3 (2026-10-08)

Continuação autônoma pedida explicitamente nesses termos: "não criar
funcionalidades aleatórias — primeiro entender profundamente o que já
existe, o que foi corrigido e como o usuário realmente utiliza o
Pregão, depois encontrar melhorias". Ciclo AUDITAR → IDENTIFICAR →
PRIORIZAR → IMPLEMENTAR → TESTAR → REVISAR → COMMITAR, sem perguntar o
que fazer.

**Guarda de entrada**: antes de qualquer alteração, confirmado via
`git log origin/main` que a FASE 3 (feed editorial NEWS+RESEARCH) de
fato estava concluída e pushada em main (commit `3666cf3`), com
CHANGELOG/PROGRESSO/testes reais — não só relatório de intenção. Só
então a tarefa prosseguiu.

**Auditoria**: 3 agentes de leitura em paralelo (nenhum alterou
código), cruzando achados contra PROGRESSO.md/BACKLOG.md pra não
redescobrir decisões já tomadas: (1) NEWS+RESEARCH, (2) MERCADO/EQUITY/
TOP MERCADO/VISÃO GERAL, (3) MACRO/CVM/CALENDÁRIO + transversal
(integração/performance/manutenção). ~27 achados reais no total,
priorizados por impacto×esforço; os de impacto alto/médio com esforço
baixo/médio foram implementados nesta mesma sessão (lista completa e
justificativa de cada um em CHANGELOG.md, entrada "ciclo de melhoria
contínua pós-FASE 3"). Os que exigiam decisão estratégica maior (ex:
Company 360 no EQUITY, link CVM→CALENDÁRIO) ou tinham risco
desproporcional ao ganho (ex: coluna `modelo` do cache de IA, refactor
de `_layout_grafico_escuro` em 4 arquivos) foram registrados em
BACKLOG.md ("Auditoria 2026-10-08"), não implementados às pressas.

**Decisões de implementação que valem registrar** (raciocínio, não só
o "o quê" — esse já está no CHANGELOG):

- `periodo_pendente` (CALENDÁRIO) tratava "ticker sem CNPJ mapeado" e
  "ticker com CNPJ mas sem documento ainda" como o MESMO caso (ambos
  `obter_documentos_cvm` retornando `[]`) — só o primeiro é um bug (prazo
  fabricado pra quem nunca vai reportar); o segundo é comportamento
  correto e já tinha teste cobrindo exatamente essa intenção (`test_7`
  antigo). A correção precisou distinguir os dois casos via
  `obter_cnpj(ticker) is None`, não simplesmente "nunca calcular prazo
  quando `[]`" — isso quebraria o caso legítimo. `tests/test_eventos.py`
  reescrito pra isolar os 2 cenários (`test_7`/`test_7b`), com CNPJ fake
  default pro resto do arquivo via `patch.object` em volta do runner
  `__main__` (evita precisar editar 15+ `with patch.object(...)` um por
  um, já que quase todo o resto do arquivo representa ticker CVM-regulado
  de verdade).
- `obter_cotacoes_lote` (novo, `data/mercado.py`) foi aplicado só no
  ticker tape do header e na VISÃO GERAL, NÃO na watchlist da sidebar
  nem no comparativo da EQUITY (mesmo padrão N+1 lá) — esses 2 também
  buscam `obter_indicadores(t)` por ticker (sem equivalente em lote
  hoje), então migrar só a cotação resolveria metade do problema;
  registrado em BACKLOG.md em vez de fazer um fix parcial.
- `_bloco_contexto_news`/`_linha_relatorio` (RESEARCH): a causa raiz do
  bloco repetido não era "falta de deduplicação visual" — era a função
  ser chamada por RELATÓRIO dentro de um loop por TICKER, com o
  gate "resumo já existe" satisfeito pra cada um. Fix: parâmetro
  `mostrar_contexto_news` (default `True`, preserva o Research Radar
  sem mudança) + `_linha_relatorio` passa a retornar se exibiu resumo,
  pra `_painel_watchlist` decidir 1x por ticker, não em cada chamada.
- `_data_publicacao_brt` (Genial Lives): a data crua do feed (UTC) só
  "erra o dia" perto da virada de meia-noite UTC (~21h BRT) — o teste
  de regressão (`test_1a2`) usa exatamente esse horário-limite
  (01:30 UTC = 22:30 BRT do dia anterior) pra provar a correção, não
  um horário qualquer onde o bug não se manifestaria.

**Validação**: suíte completa (14 arquivos de teste, incluindo 4 novos:
`test_cvm.py`, `test_mercado.py`, `test_news_tickers.py`,
`test_news_relevancia.py`) + `compileall` limpos. `pyflakes` rodado
manualmente nos arquivos tocados (achou 3 imports/variáveis mortas só
nos testes novos escritos nesta sessão — corrigidos antes do commit).
Validação de nível Streamlit via harness `AppTest` único
(`/tmp/.../scratchpad/apptest_fase4.py`, fora do repo) cobrindo as 6
telas tocadas (CALENDÁRIO, NEWS, VISÃO GERAL ×2, RESEARCH, CVM) — todas
renderizam sem exceção com o fragment/cache/timezone novos; inclui
asserção de conteúdo (CDI mostra "+0,05%" calculado, não mais "+0,00%"
fixo; expander de histórico aparece com 2+ snapshots). **Nota de
validação visual (honesta, mesma limitação de fases anteriores)**: este
ambiente não tem Playwright/Chromium configurado contra o app Streamlit
completo — o harness `AppTest` prova que renderiza sem exceção e o
conteúdo calculado está correto, não prova como fica visualmente na
tela (cor exata, densidade, alinhamento). Pendência real pro Rodrigo
confirmar em `pregao.streamlit.app` depois do deploy.

**Arquivos alterados**: `data/eventos.py`, `data/cvm.py`,
`data/mercado.py`, `data/news.py`, `data/research/genial_lives.py`,
`app.py`, `ui/calendario_tab.py`, `ui/news_tab.py`, `ui/research_tab.py`,
`ui/visao_geral.py`, `ui/workspace.py`, `MANUAL.md` + testes novos/
estendidos listados acima. Nenhuma mudança em `auth.py`, `config.py`,
`coletor_local.py`, schema SQL, ou nos módulos CVM/MACRO não citados.

## FASE 8/9 — pós-V1, melhoria contínua controlada (2026-10-08)

Continuação explicitamente escopada do ciclo anterior: só tratar os
itens que ficaram no BACKLOG.md ("Auditoria 2026-10-08") depois da
rodada pós-FASE 3, sem refazer a auditoria nem reabrir o que já tinha
sido decidido lá. Partiu do commit `cb868c6` (já em main).

**Decisões de implementação que valem registrar**:

- **N+1 da sidebar/EQUITY**: o BACKLOG já tinha identificado que
  `obter_cotacao` por ticker continuava em 2 lugares (sidebar, EQUITY
  comparativo), e que o comparativo também buscava `obter_indicadores`
  por ticker. Investigação confirmou que só a parte de COTAÇÃO tem
  forma segura de lote (`data/mercado.py:obter_cotacoes_lote`, já
  existente e testado desde a rodada anterior) — `obter_indicadores`
  vem de `yf.Ticker().info`, que o yfinance não expõe em lote (só
  `fast_info`/`download` de OHLCV são batcháveis). Decisão: migrar só a
  cotação nos 2 pontos, documentar explicitamente por que indicadores
  continua por ticker (não é uma pendência disfarçada, é um limite real
  da fonte) — já cacheado 12h por ticker, então o impacto prático é
  baixo mesmo sem lote.
- **Coluna `modelo` do cache de IA**: a tarefa pedia "corrigir somente
  se for seguro determinar o modelo efetivamente usado, nunca inventar,
  preservar NULL se não disponível". Investigação em
  `data/research/resumir.py:resumir_com_groq` achou que essa informação
  JÁ é calculada internamente (`_chamar_groq_com_fallback` retorna
  `usou_fallback`) mas era descartada com `_` antes de chegar no dict
  salvo — ou seja, não era um caso de "informação indisponível", era
  informação disponível e jogada fora. Corrigido propagando
  `usou_fallback` até o dict que `data/ia_cache.py` lê, com `None`
  (nunca um valor chutado) no único caminho defensivo onde a chave
  poderia faltar. `data/news.py:_gerar_resumo_grupo` é mais simples
  (sem fallback de modelo ali — sempre 1 modelo só, zero ambiguidade),
  só precisava parar de OMITIR a chave, nunca teve risco de "inventar".
  Efeito colateral limpo: `config.obter_modelo_groq()` (wrapper de 1
  linha) ficou sem nenhum chamador depois da correção em
  `_gerar_resumo` — removido (código morto).
- **Testes de dedup de NEWS** (`_agrupar`/`_mesmo_grupo`): ao escrever
  os cenários "notícias distintas não podem se fundir", 2 das minhas
  primeiras tentativas de fixture (mesma empresa com baixa similaridade
  de texto; 2 bancos com manchete de estrutura idêntica) na verdade SE
  FUNDIRAM ao rodar contra o código real — não por bug nos testes
  acharem um problema novo, mas porque minha intuição sobre o limiar de
  similaridade/janela de entidade estava errada. Investigando a fundo:
  o nome da própria empresa sozinho ("Petrobras", capitalizado, 5+
  letras) já conta como "entidade em comum" em `_extrair_entidades`
  (`_ENTIDADE_IGNORAR` só lista termos genéricos, não nomes de empresa)
  - dentro da janela de 24h, isso basta pra fundir 2 fatos DIFERENTES da
  mesma empresa. Por instrução explícita da tarefa ("não alterar a
  regra sem evidência de bug"), **não mudei a heurística** - corrigi as
  fixtures dos testes pra reflotar o comportamento real (ou empurrar a
  diferença de horário além de 24h, ou escolher conteúdo realmente
  distinto) e documentei o comportamento do nome-sozinho-como-entidade
  num teste dedicado (`test_3b`), não como falha.
- **`_cache_eventos()`**: antes de decidir "poda ou não", fiz a conta
  real em vez de supor - cresce ~1 entrada por `(ticker, período)` já
  calculado (4/ano por ticker, já que o período muda por trimestre),
  é `st.cache_resource` de 1 processo só (terminal pessoal, não
  multi-tenant), e nenhuma entrada antiga é lida de novo (lookup é
  sempre pelo período ATUAL). Concluí que é seguro e não implementei
  poda - a tarefa foi explícita que "se o cache já estiver seguro, não
  alterar apenas por estética".
- **Link CVM→CALENDÁRIO**: não implementado por restrição REAL de
  arquitetura, não falta de tempo - `app.py` só permite escrever
  `st.session_state["secao_ativa"]` ANTES do `st.segmented_control` do
  nav ser instanciado no mesmo rerun (erro documentado no próprio
  código: `StreamlitWidgetAlreadyInstantiatedError`), e CVM renderiza
  bem depois desse ponto no fluxo do script. Fazer esse link exigiria
  mudar a ordem de renderização ou um mecanismo de navegação diferido -
  isso é arquitetura nova, que a tarefa pediu explicitamente pra não
  criar.
- **Chave de `session_state` MERCADO/VISÃO GERAL**: a tarefa pedia só
  alterar "se o código/teste confirmar bug real". Testei na prática
  (setar a chave do lado de MERCADO, ler do lado de VISÃO GERAL) e
  CONFIRMEI que a interferência é real (não é só suspeita do BACKLOG
  antigo) - mas também confirmei que isso nunca produz dado ERRADO (as
  duas abas sempre mostram a janela selecionada corretamente, só
  compartilham QUAL janela está ativa). Como a tarefa distinguiu
  explicitamente "bug real" de "escolha intencional que não causa
  comportamento incorreto", e este é o segundo caso, não alterei -
  registrei a confirmação no BACKLOG como decisão de produto pendente,
  não como bug.

**Validação**: suíte completa (17 arquivos de teste, 3 novos:
`test_news_dedup.py`, `test_news_contexto_research.py`,
`test_resumir_modelo.py`) + `compileall` + `pyflakes` (repo inteiro,
não só os arquivos tocados) limpos. As 2 correções de N+1 em `app.py`
vivem em closures que exigem login real (`auth.py`) pra executar via
Streamlit de verdade - mesma limitação "impossível de automatizar" já
documentada em fases anteriores, confirmada de novo ao tentar (sem
`user=` disponível em `AppTest.run()` nesta versão do Streamlit
instalada) - validadas por revisão de código (compatibilidade exata de
campos com `obter_cotacoes_lote`, já testado) + `compileall`/`pyflakes`,
não por harness `AppTest` dedicado (diferença honesta registrada no
CHANGELOG, não escondida).

**Arquivos alterados**: `app.py`, `config.py`, `data/news.py`,
`data/research/resumir.py`, `BACKLOG.md`, `CHANGELOG.md` + testes
novos (`test_news_dedup.py`, `test_news_contexto_research.py`,
`test_resumir_modelo.py`). Nenhuma mudança em `data/ia_cache.py`,
`data/mercado.py`, `data/eventos.py`, `ui/*`, schema SQL, ou em
qualquer regra financeira/dado exibido ao usuário.

## Rotina autônoma — ciclo de 4 partes, parte 1/4 (2026-10-08)

Sessão agendada, isolada (clone próprio), continuação do ciclo de
melhoria contínua. Partiu do commit `2e2a101` (já em `main`), lendo
PROGRESSO.md/CHANGELOG.md/BACKLOG.md da sessão anterior pra não repetir
investigação já feita (CALENDÁRIO/ROXO34/mobile, todas já fechadas).

**Trabalho desta parte**:

1. **`tests/test_eventos.py` — 10 falhas sob `pytest` (deixadas pela
   sessão anterior como "confirmado pré-existente, não investigado")**:
   causa raiz encontrada — arquivo escrito pra um runner próprio
   (`python tests/test_eventos.py`), com o mock de `obter_cnpj`
   (necessário desde a correção de `periodo_pendente` em 2026-10-08)
   vivendo só dentro do `if __name__ == "__main__"`, que o `pytest`
   nunca executa. Sob `pytest`, isso fazia `calcular_proximo_resultado`
   devolver `None` sempre (chamando o `obter_cnpj` real, sem rede
   aqui), quebrando 10 testes com erro de `NoneType`. Fix: fixture
   `autouse=True` que replica o mesmo mock padrão do runner, sem tocar
   em nenhum teste nem em `data/eventos.py`. Validado nos dois modos de
   invocação (`pytest` e `python tests/test_eventos.py` direto) — os
   dois passam 100%.
2. **Curva pré (MACRO) — item do BACKLOG, legenda "sobreposta/cortada"
   nunca confirmada**: reproduzida com Playwright/Chromium (pré-
   instalado neste ambiente) + dados sintéticos (rede bloqueia ANBIMA
   aqui) usando o layout real do painel, nos 3 breakpoints. Não
   reproduziu em nenhum — Plotly já encolhe a área do gráfico pra
   caber a legenda quebrada em 2-3 linhas sem cortar nada. Não alterei
   código (nada a corrigir sem bug confirmado); documentei a
   investigação + uma hipótese não testável aqui no BACKLOG.md, pra não
   reabrir sem evidência nova.

**Decisão de escopo**: com o tempo restante da janela de ~1h gasto
nessas duas investigações (a primeira era um item concreto e
específico já apontado pela sessão anterior; a segunda era o próximo
item de prioridade razoável do BACKLOG), não iniciei uma 3ª frente
nova — preferi fechar as duas com evidência real (testes passando,
screenshots reais) a abrir uma 3ª investigação pela metade.

**Validação**: suíte completa 249/249 (Python 3.12, venv
`/tmp/venv312` recriado nesta sessão — efêmero, não é o mesmo arquivo
de sessões anteriores); `compileall` e `pyflakes` limpos nos arquivos
tocados.

**Arquivos alterados**: `tests/test_eventos.py`, `BACKLOG.md`,
`CHANGELOG.md`, `PROGRESSO.md`. Nenhuma mudança em código de produção
(`data/*.py`, `ui/*.py`, `app.py`).

**Pendências pra próxima parte (2/4)**: nenhuma pendência bloqueante
desta parte. Continuar pela ordem de prioridade original do Rodrigo a
partir do que a auditoria de UX (item 5) e cobertura/mobile (item 6)
ainda não fecharam por completo (ver nota "Não fiz" na sessão anterior,
2026-10-08 "continuação — UX/hierarquia/mobile/performance percebida"):
revisão visual completa de NEWS/CVM/RESEARCH/TOP MERCADO/EQUITY nos 3
breakpoints com dados mockados (só MERCADO recebeu harness dedicado até
agora); auditoria de hierarquia visual (signal→context→detail) das 9
telas ainda não foi feita formalmente.

## Rotina autônoma — ciclo de 4 partes, parte 2/4 (2026-10-08)

Sessão agendada, isolada (clone próprio), continuação do ciclo. Partiu
do commit `de8eae8` (já em `main`, fim da parte 1/4). Baseline
confirmado antes de qualquer mudança: suite completa 249/249, sem
regressão herdada.

**Trabalho desta parte** (2 bugs reais, ambos reproduzidos antes de
corrigir, não hipótese):

1. **MACRO — curva pré (ETTJ ANBIMA) usava `date.today()` do servidor
   (UTC) em vez do fuso de Brasília**: achado lendo
   `ui/macro_tab.py:_painel_curva_pre` com o item 1 da ordem de
   prioridade do Rodrigo em mente ("verificar datas, timezone
   America/Sao_Paulo"). `hoje = date.today()` é o fuso do processo -
   UTC no Streamlit Cloud. Reproduzido analiticamente (simulação de
   horário UTC real): entre 21h e 23h59 em Brasília, `date.today()` já
   retorna amanhã em UTC - nessa janela diária todo dia, a curva
   publicada HOJE pela ANBIMA seria rotulada "Última" por engano, e as
   janelas de "1 semana atrás"/"1 mês atrás" ficariam deslocadas em 1
   dia. Achado reforçado por um precedente direto: a MESMA classe de bug
   já tinha sido corrigida em `data/eventos.py:periodo_pendente` nesta
   mesma data (2026-10-08) por outra sessão - só não tinha sido
   replicada aqui. Corrigido com `datetime.now(data.macro.TZ).date()`
   (America/Sao_Paulo, `TZ` já exportado por `data/macro.py`, mesmo fuso
   usado no resto do projeto). Validado com teste direto da comparação
   `eh_hoje` (dado sintético com `data_referencia` = hoje em BRT) -
   confirma `True` depois da correção; AppTest do painel sem exceção;
   suite completa 249/249 depois da mudança.
2. **CVM — tabela DATA/TICKER/TIPO/ASSUNTO ilegível em mobile/tablet**:
   pendência explícita deixada pela parte 1/4 ("revisão visual completa
   ... só MERCADO recebeu harness dedicado até agora"). Construído
   harness Playwright isolado (`render_cvm` com dados sintéticos, sem
   login, mesmo padrão já usado pra MERCADO numa sessão anterior),
   screenshot real nos 3 breakpoints (390/768/1280px) via
   Chromium pré-instalado neste ambiente. **Confirmado visualmente**
   (não suspeita): a 390px, DATA/TICKER/badge de TIPO ficavam
   sobrepostos uns aos outros linha a linha (texto ilegível, "garbled");
   a 768px, data e ticker colavam sem espaço ("08/10/2026PETR4"). Causa
   raiz: `.cvm-data`/`.cvm-ticker` eram as ÚNICAS peças da tabela sem
   `overflow:hidden`/`text-overflow:ellipsis` (o botão de assunto e o
   cabeçalho já tratavam disso) - em telas estreitas, onde `st.columns`
   não empilha (confirmado: só encolhe, via `min-width:0` global em
   `style.css`), o texto `white-space:nowrap` sem contenção vazava
   visualmente por cima da coluna seguinte. Corrigido com a mesma
   técnica já usada em todo o resto do app (ellipsis nos 4 elementos +
   `overflow-x:hidden` no bloco de colunas como rede de segurança) e
   rebalanceamento de `_COLS` (`[9,8,16,55]` → `[12,10,14,50]` - TIPO
   tinha folga de sobra, nunca precisou de 16/88 pro rótulo mais longo
   "FATO RELEVANTE"; realocada pra DATA/TICKER sem reduzir ASSUNTO, que
   continua dominando a largura por pedido explícito original).
   Confirmado com nova screenshot nos 3 breakpoints, antes E depois:
   zero sobreposição, zero scroll horizontal (`stHorizontalBlock` sem
   overflow em nenhum dos 3), tablet/desktop com data+ticker completos e
   espaçados corretamente.
3. **Varredura por bugs irmãos (mesmo padrão)**: busca de todo
   `st.columns` com pesos fixos no projeto
   (`calendario_tab.py`/`news_tab.py`/`graficos.py`/`paineis.py`/
   `app.py`) por `white-space:nowrap` sem `overflow`/`ellipsis` - mesmo
   padrão da causa raiz do bug da CVM. **Nenhum outro caso encontrado**:
   os demais usos têm proporções bem mais folgadas (`[4,1]`, `[3,1]`,
   `[1,9]`) ou já tratam overflow corretamente (NEWS, auditado com o
   mesmo método Playwright numa sessão anterior). Não alterado (nada a
   corrigir sem bug confirmado).

**Nota de ambiente**: mesma limitação de sessões anteriores - rede deste
sandbox bloqueia Yahoo Finance/B3/ANBIMA/CVM (reconfirmado nesta sessão
com teste direto de conectividade HTTPS). Toda validação visual usou
harness Playwright isolado com dados sintéticos plausíveis (fora do
`app.py` real, sem login - os dois bugs encontrados são de LAYOUT/CSS,
não de dado, então dado sintético plausível é suficiente pra reproduzir
e validar a correção). Python 3.12 (`/tmp/venv312`, recriado nesta
sessão - efêmero, mesma razão de sempre: sintaxe de f-string que exige
3.12+).

**Validação**: suite completa 249/249 (baseline antes de mexer, e de
novo depois de cada uma das 2 correções); `compileall`/`pyflakes`
limpos nos arquivos tocados (`ui/macro_tab.py`, `ui/cvm_tab.py`);
screenshots reais (Chromium) nos 3 breakpoints, antes E depois, pro bug
da CVM - evidência de before/after, não só "renderiza sem exceção".

**Arquivos alterados**: `ui/macro_tab.py`, `ui/cvm_tab.py`,
`CHANGELOG.md`, `PROGRESSO.md`.

**Pendências pra próxima parte (3/4)**: a auditoria visual formal
(signal→context→detail) das 9 telas continua pendente, assim como a
revisão com dados mockados de NEWS/RESEARCH/TOP MERCADO/EQUITY/
CALENDÁRIO nos 3 breakpoints (agora MERCADO e CVM têm harness dedicado;
as outras 5 ainda não). O harness Playwright isolado usado aqui pra CVM
é reaproveitável como padrão pras próximas (copiar a estrutura de
`cvm_harness.py`/`shoot_cvm.py` do scratchpad desta sessão - não ficou
no repositório, era só validação, mas o padrão está documentado aqui e
no CHANGELOG). Nenhum outro P0/P1 óbvio identificado nesta sessão na
camada de dados/confiabilidade além dos 2 corrigidos - próxima parte
pode seguir direto pra cobertura de mercado (item 2) ou fontes/coleta
(item 3) se a auditoria visual não render mais achados rápidos.

## Rotina autônoma — ciclo de 4 partes, parte 4/4 (2026-10-08)

Sessão agendada, isolada (clone próprio), última parte do ciclo de hoje.
Partiu do commit `fa27dca` (já em `main`, fim da parte 3/4). `HEAD`
estava detached no início (clone fresco) - resolvido com `git checkout
main && git pull` antes de qualquer trabalho, sem perda de commits
(fast-forward simples, mesmo padrão já documentado em sessões
anteriores). Baseline confirmado antes de mexer: suite completa
249/249.

**Trabalho desta parte**:

1. **Hardening - `pyflakes` no repositório inteiro** (não só arquivos
   tocados recentemente, prática já usada nesta rodada pela parte 3/4):
   achou 4 avisos reais, todos código morto, zero bug de comportamento -
   `data/ir_sources.py` importava `_HEADERS`/`_TIMEOUT` de `data/cvm.py`
   sem usar (a função reaproveitada, `_baixar_csv_do_zip`, já cuida
   disso internamente); `tests/test_prices.py` e
   `tests/test_news_fase3.py` importavam `MagicMock` sem usar (só
   `patch` é usado nos dois); `tests/test_ia_cache.py:test_7` atribuía
   o retorno de `obter_resumo_com_cache` a uma variável nunca lida.
   Corrigidos os 4 (remoção de import/atribuição morta, nenhuma mudança
   de lógica). `compileall`/suite completa confirmados limpos antes e
   depois.
2. **Continuação da auditoria visual Playwright pendente (NEWS/
   RESEARCH/TOP MERCADO/EQUITY/CALENDÁRIO)**: construído harness
   isolado (`render_news` com dados sintéticos + `style.css`/CSS
   próprio reais, mesma técnica já validada pra MERCADO/CVM em partes
   anteriores), 3 breakpoints. **Achado visual real, confirmado com
   evidência** (zoom pixel a pixel + medição de DOM via
   `getBoundingClientRect`, reproduzido em 2 breakpoints e sobrevive a
   reload completo da página): a linha de metadados de cada card de
   notícia (`_meta_noticia_html` - selo/veículo/hora/ticker(s)/nº de
   fontes/link "↗ abrir") fica parcialmente coberta pelo divisor do
   próximo item quando o texto quebra pra 2 linhas - o
   `stElementContainer` do Streamlit (1.64.0, mesma versão de produção)
   que envolve esse `st.markdown` mede uma altura ~13px menor que o
   conteúdo real renderizado, e esse valor não é "auto" (CSS computado
   trava num px fixo), nem se recalcula depois.
   **Duas tentativas de correção testadas e descartadas**: (a) forçar
   `height:auto !important` no container via seletor `:has()` - sem
   efeito, a altura continuou travada no mesmo valor; (b) impedir a
   quebra de linha na origem (`white-space:nowrap` + ellipsis em
   `.news-item-meta`, reiniciando o servidor Streamlit do zero pra
   testar de verdade, não só injeção JS tardia) - **piorou** a
   renderização (quase todo o conteúdo da linha ficou invisível dentro
   de um container ainda menor) - revertida imediatamente, `git diff`
   conferido limpo antes de seguir pra qualquer outra coisa (nenhum
   resíduo ficou no repositório).
   **Decisão (regra 1 de autonomia + "causa raiz > workaround")**: não
   forcei um fix sem entender o mecanismo real - as duas tentativas
   mostraram que o sintoma não é simplesmente "texto quebrando em 2
   linhas" (mexer nisso não ajudou, e piorou numa tentativa), pode ser
   um comportamento mais profundo do próprio Streamlit (cache de altura
   via `ResizeObserver` medido num momento diferente do layout final) ou
   um artefato específico deste harness isolado (sandbox sem internet,
   sem a fonte real "IBM Plex Mono" carregada via Google Fonts, só
   fallback monospace genérico - métricas de caractere diferentes das
   de produção). Investigar mais a fundo exigiria acesso ao bundle JS do
   Streamlit (fora do escopo de uma correção cirúrgica) ou confirmação
   ao vivo em `pregao.streamlit.app` com navegador real - nenhuma das
   duas era viável nesta janela. Documentado em detalhe no BACKLOG.md
   (mecanismo investigado, o que já foi tentado e descartado, pendência
   concreta de confirmação em produção) em vez de arriscar uma segunda
   regressão visual. Confirmado por leitura de código que o estilo
   "wire" mais antigo (`_linha_noticia`/`_renderizar_lista`, usado por
   TOP MERCADO e pelo bloco compacto de NEWS da aba EQUITY) usa colunas
   de largura fixa com ellipsis (nunca quebra linha) e **não tem este
   problema** - o risco é específico do estilo "editorial" (cards, Fase
   3) usado só no feed principal de `render_news`.

**Validação**: suite completa 249/249 (baseline e após a limpeza do
pyflakes); `compileall`/`pyflakes` limpos no repositório inteiro (zero
avisos depois da limpeza). `git status`/`git diff` conferidos limpos
antes do commit final (confirmando que a investigação da NEWS não
deixou nenhuma mudança de código pra trás, só documentação).

**Arquivos alterados**: `data/ir_sources.py`, `tests/test_prices.py`,
`tests/test_news_fase3.py`, `tests/test_ia_cache.py` (hardening),
`BACKLOG.md`, `CHANGELOG.md`, `PROGRESSO.md` (documentação). Nenhuma
mudança em código de produção além da limpeza de import morto (sem
efeito de comportamento).

---

## Rotina autônoma — ciclo de 4 partes, RELATÓRIO CONSOLIDADO (2026-10-08)

Relatório final cobrindo as 4 partes do ciclo autônomo de hoje (partes
1/4 a 4/4, ~70min de espaçamento entre cada uma, sessões isoladas e
independentes), conforme pedido explícito do Rodrigo pra última parte.

### 1. Commits realizados (todas as partes)

Partindo de `2e2a101` (estado de `main` antes da parte 1/4) até o commit
final desta parte 4/4:

- `9702fa7` fix: `test_eventos.py` quebrava sob pytest (10 falsos-falhos
  pré-existentes) — **parte 1/4**
- `de8eae8` docs: registra parte 1/4 (fix de testes + investigação curva
  pré) — **parte 1/4**
- `99cb357` fix: curva pré (MACRO) usava `date.today()` do servidor
  (UTC) em vez do fuso de Brasília — **parte 2/4**
- `d062db2` fix: CVM (tabela DATA/TICKER/TIPO) ilegível em mobile/tablet
  — **parte 2/4**
- `86d70cd` docs: registra parte 2/4 (fix timezone MACRO + mobile CVM)
  — **parte 2/4**
- `fa27dca` fix: MERCADO/VISÃO GERAL sem feedback de carregamento em
  consulta fria — **parte 3/4**
- `c4b2b59` chore: limpa 4 avisos do pyflakes (imports/variável não
  usados) — **parte 4/4**
- (commit de documentação desta parte 4/4, ver abaixo)

Todos os commits foram enviados (`push`) pra `origin/main` ao final de
cada parte, sem force-push, sem reescrita de histórico. Nenhum conflito
real encontrado entre partes (cada sessão fez `git fetch`/`pull` antes
de começar e checou `git diff` contra `origin/main` antes do push, como
pedido).

### 2. Problemas reais encontrados (e corrigidos)

1. **`tests/test_eventos.py` sob pytest** — 10 falhas falsas por um mock
   de `obter_cnpj` vivendo só no bloco `__main__`, nunca executado pelo
   pytest (parte 1/4).
2. **Curva pré (MACRO) com timezone errado** — `date.today()` do
   servidor (UTC) em vez de `America/Sao_Paulo`, rotulando "Hoje" por
   engano numa janela de ~3h todo dia (21h-23h59 BRT) (parte 2/4).
3. **CVM ilegível em mobile/tablet** — colunas DATA/TICKER sem
   `overflow:hidden`/ellipsis, único ponto da tabela sem essa proteção,
   causando sobreposição de texto confirmada visualmente (parte 2/4).
4. **MERCADO/VISÃO GERAL sem feedback de carregamento** — `yf.download`
   real com `show_spinner=False` e nenhum spinner manual, tela parada
   sem aviso numa consulta fria (parte 3/4).
5. **4 avisos reais de `pyflakes`** (código morto - imports/variável sem
   uso) no repositório inteiro (parte 4/4).

### 3. Correções feitas

Todas as 5 acima foram corrigidas, testadas (suite completa +
`compileall`/`pyflakes`, screenshot real via Playwright/Chromium quando
aplicável) e commitadas. Nenhuma correção ficou pela metade.

### 4. Melhorias de UX

- Feedback de carregamento (spinner com texto) no MERCADO/VISÃO GERAL,
  mesma classe de correção já aplicada em CVM/NEWS/MACRO/RESEARCH em
  ciclos anteriores — agora as 5 telas que fazem chamada de rede real
  têm indicação visual de "carregando".
- Rótulo honesto na curva pré do MACRO ("Última (dd/mm)" em vez de
  "Hoje" quando a publicação não é de fato de hoje), evitando o usuário
  interpretar um dado desatualizado como atual.

### 5. Melhorias de performance

Nenhuma nesta rodada de 4 partes — o foco identificado pela auditoria
foi majoritariamente confiabilidade de dados/timezone e legibilidade
mobile, não performance (já endereçada em ciclos anteriores: paralelismo
do TOP MERCADO, cache de cotações em lote, etc. — ver seções anteriores
deste arquivo).

### 6. Melhorias de dados/coleta

- Timezone da curva pré (ANBIMA ETTJ) corrigido pra `America/Sao_Paulo`
  de ponta a ponta, consistente com a correção equivalente já feita em
  `data/eventos.py:periodo_pendente` no mesmo dia por outra sessão.

### 7. Cobertura/mobile

- CVM: tabela DATA/TICKER/TIPO/ASSUNTO corrigida nos 3 breakpoints
  (390/768/1280px), confirmado com screenshot antes/depois.
- Varredura por bugs irmãos (mesmo padrão de `white-space:nowrap` sem
  `overflow`/ellipsis) em todo `st.columns` do projeto — nenhum outro
  caso real encontrado (parte 2/4).
- NEWS (feed editorial): investigação real, com evidência (screenshots +
  medição de DOM), de um problema visual na linha de metadados dos
  cards quebrando pra 2 linhas — **não corrigido** por falta de certeza
  sobre a causa raiz (ver seção 9 abaixo e BACKLOG.md).

### 8. Testes executados e resultados

- Suite completa (`pytest`): 249/249 em todas as 4 partes, confirmada
  ANTES e DEPOIS de cada mudança (baseline limpo sempre verificado
  primeiro).
- `python -m compileall .`: limpo em todas as 4 partes.
- `pyflakes` (repositório inteiro, não só arquivos tocados): limpo ao
  final da parte 4/4 (4 avisos reais encontrados e corrigidos).
- Validação visual real (Playwright/Chromium, 390/768/1280px, dados
  sintéticos plausíveis — rede deste sandbox bloqueia Yahoo
  Finance/B3/ANBIMA/CVM/Google News em todas as 4 partes, limitação de
  ambiente já documentada em ciclos anteriores): usada nas partes 2/4
  (CVM, antes/depois) e 4/4 (NEWS, investigação sem fix).
- Python 3.12 usado em todas as partes (venv efêmero recriado a cada
  sessão — `/tmp/venv312` não sobrevive entre sessões isoladas), já que
  o projeto usa sintaxe que exige 3.12+.

### 9. Investigado mas corretamente NÃO alterado

- **Legenda da curva pré "sobreposta/cortada"** (BACKLOG antigo) — não
  reproduzida com Playwright/dados sintéticos em nenhum dos 3
  breakpoints (parte 1/4); hipótese não descartada mas não testável sem
  sessão autenticada real.
- **E-mail do usuário "some" no header em telas estreitas** — conta de
  largura confere matematicamente, mas sem confirmação visual real em
  produção (parte 3/4).
- **Acentuação perdida em nomes de empresa em produção** — nenhuma causa
  nova encontrada no código (funções de normalização só usadas pra
  busca/dedup, nunca pro texto exibido); permanece como limitação
  específica do ambiente de produção, não reproduzível aqui (parte 3/4).
- **Chave de `session_state` compartilhada entre MERCADO/VISÃO GERAL**
  (seletores DIA/SEMANA/MÊS) — confirmado que é intencional/sem bug de
  corretude, decisão de produto pendente pro Rodrigo (ciclo anterior,
  reconfirmado nesta rodada via BACKLOG.md).
- **NEWS — overlap visual no feed editorial** (achado novo desta parte
  4/4): investigado a fundo, 2 tentativas de correção testadas e
  descartadas (uma delas piorou e foi revertida) — não há certeza
  suficiente sobre a causa raiz (Streamlit internals vs. artefato do
  harness de teste) pra arriscar um 3º fix sem confirmação em produção
  real. Documentado em detalhe no BACKLOG.md.

### 10. Principais pontos que ainda merecem atenção do Rodrigo

1. **NEWS — confirmar em produção real** se o card de notícia (feed da
   aba NOTÍCIAS, não TOP MERCADO) mostra o selo/ticker/link "↗ abrir"
   cortado ou sobreposto pela linha do próximo item, numa tela estreita
   ou tablet, com uma notícia de manchete longa + 2+ tickers + veículo
   com nome longo (mais chance de quebrar pra 2 linhas). Se confirmado,
   é um bug real de produção que precisa de uma 3ª tentativa de correção
   — melhor com navegador real (fontes carregando de verdade) em vez de
   só o harness isolado deste sandbox.
2. **Auditoria visual Playwright ainda incompleta** — RESEARCH, TOP
   MERCADO, EQUITY e CALENDÁRIO continuam sem harness dedicado (só
   MERCADO, CVM e agora NEWS parcialmente receberam). Candidato natural
   pro próximo ciclo autônomo.
3. **EQUITY não é "Company 360"** (contexto de Research/preço-alvo
   integrado à ficha do ativo) — iniciativa de produto de maior escopo,
   já registrada em ciclos anteriores, não é uma tarefa pequena.
4. **BTG/Itaú BBA/Santander/BB/Safra/Ágora/Inter Research** — fontes
   ainda não integradas (bloqueio de IP/API fechada/SPA sem API óbvia),
   ver detalhe em BACKLOG.md seção Research.
5. **Lives da Genial no YouTube** — implementado tecnicamente, mas
   desligado por respeito ao `robots.txt` do YouTube; decisão de
   risco/ToS que fica pro Rodrigo (religar é 1 linha, ver PROGRESSO.md
   "FILA2-T8").
6. **Layout de painéis arrastável/redimensionável** — decisão
   arquitetural grande, deliberadamente não implementada (ver "FILA2-T5"
   acima), com uma sugestão de caminho intermediário mais barato já
   registrada.

---

## FASE 5 — correções pós-auditoria (2026-10-08, rotina autônoma)

Pedido explícito do Rodrigo: investigar e corrigir o que ainda for real
da Fase 4/auditorias anteriores, sem reabrir o que já foi validado.
Partiu do commit `4c87269` (já em `main`). Baseline confirmado antes de
mexer: suite completa 249/249, `compileall`/`pyflakes` limpos.

### 1. NEWS — bug visual do card (selo/ticker sobreposto pelo divisor)

Item do BACKLOG.md com 2 tentativas anteriores já descartadas (uma
piorou e foi revertida) — só reaberto porque consegui uma hipótese
técnica NOVA, não uma repetição. Reconstruí o harness Playwright
isolado de sessões anteriores (`render_news`/`_cartao_noticia` reais,
importados diretamente de `ui/news_tab.py` — não reescritos à mão, pra
garantir que o HTML/CSS testado é exatamente o de produção), dados
sintéticos, `style.css` real, 390/768/1280px.

Reproduzi o bug (confirmado de novo: container do Streamlit ~13-16px
menor que o conteúdo real, overlap visual confirmado em screenshot) e,
em vez de tentar mais uma variação de CSS "no escuro", instrumentei
cada nível da árvore DOM entre `.news-item-meta`/`.news-item-resumo` e o
`stElementContainer` (altura computada + bounding box de CADA wrapper
intermediário, via Playwright). Achei 2 causas raiz reais e específicas,
nunca identificadas antes:

1. O wrapper `stMarkdown > div[display:flex;flex-direction:row;
   flex-wrap:nowrap] > stMarkdownContainer` (estrutura interna do
   próprio Streamlit 1.64.0, não nosso HTML) calcula a altura "auto" do
   flex container com base na largura ANTES do texto do único filho
   quebrar linha — bug conhecido de flexbox (flex-row + filho único
   cujo conteúdo depende da própria largura pra decidir altura). Medido
   diretamente: esse wrapper tinha `height:27.75px` enquanto o
   `stMarkdownContainer` dentro dele já media `43.75px` de verdade.
2. `[data-testid="stMarkdownContainer"]` do próprio Streamlit vem com
   `margin-bottom:-16px` embutido na folha de estilo gerada (emotion) —
   serve pra compensar a margem padrão de parágrafo `<p>` quando o
   markdown é texto comum formatado pelo Streamlit. Nosso HTML aqui é
   um `<div>` cru sem `<p>` nenhum — não há margem de parágrafo pra
   compensar, então essa margem negativa só colapsa pra dentro do
   `stElementContainer` (o container que a interface usa pra medir a
   altura real do card), encolhendo-o ~16px a menos que o conteúdo
   renderizado de verdade. Essa é a causa raiz concreta do "container
   menor que o conteúdo" que as 2 sessões anteriores já tinham medido
   (13-16px, mesma ordem de grandeza) mas não tinham conseguido
   explicar.

**Correção**: 2 regras CSS novas em `ui/news_tab.py` (`_CSS_WIRE`),
escopadas com `:has(.news-item-meta, .news-item-resumo)` — só afeta o
card de notícia/resumo, não mexe em nenhum outro markdown do app:
o wrapper flex vira `display:block` (único filho, ocupa 100% da
largura de qualquer jeito — visualmente idêntico, só muda o cálculo de
altura) e a margem negativa é zerada nesse escopo.

**Validação**: harness Playwright isolado (mesmas funções reais
importadas de `ui/news_tab.py`), 390/768/1280px, ANTES e DEPOIS da
correção — medição de `getBoundingClientRect` de cada card confirma
`container_height >= conteúdo_height` em todos os casos (texto de 1 e 2
linhas na linha de metadados, resumo com line-clamp de 2-3 linhas, com
e sem tickers/CVM confirmada) e screenshot visual confirma a linha
completa (badge do ticker + "NF" + "↗ abrir") sem nenhuma sobreposição
pelo divisor, nos 3 breakpoints — antes mostrava claramente o fim da
linha cortado. `git diff` revisado: só as 2 regras CSS novas, nenhum
outro efeito colateral. Suite completa 249/249, `compileall`/`pyflakes`
limpos em `ui/news_tab.py`. Item removido do BACKLOG.md.

### 2. Fidelidade dos resumos (NEWS e Research/Morning Call)

Pedido do Rodrigo: resumo deve dizer o que aconteceu, números e por que
importa, sem inventar causalidade/consenso/impacto/próximos passos, sem
tratar hipótese como fato.

**Research/Morning Call** (`data/research/resumir.py`): li o prompt de
sistema real por completo. Já é bem mais rigoroso do que o mínimo
pedido — separação explícita FATO vs VISÃO DA CASA/ANALISTA vs LEITURA
DO SISTEMA (com atribuição obrigatória), lista de "REGRAS ABSOLUTAS"
que já proíbe explicitamente inventar causalidade/impacto
setorial/consenso/opinião de analista, e `_extrair_dados_estruturados`
só preenche preço-alvo/recomendação quando EXPLICITAMENTE escritos no
texto (nunca estimados/calculados/deduzidos — instrução explícita no
próprio prompt, com exemplo do que fazer na dúvida: `NAO_IDENTIFICADO`).
Nenhum problema de fidelidade real encontrado — não alterado (já
funciona, não é componente pra refazer).

**NEWS** (`data/news.py:_PROMPT_SISTEMA_RESUMO`/
`_PROMPT_SISTEMA_RESUMO_MANCHETES`): achado real — o formato fixo de 4
campos (O QUE ACONTECEU/NÚMEROS/IMPACTO/PRÓXIMOS PASSOS) só tinha uma
instrução genérica de "nunca invente, escreva 'não informado' se faltar
informação". IMPACTO e PRÓXIMOS PASSOS são exatamente os 2 campos mais
propensos a especulação de um LLM sob esse tipo de formato rígido (a
tendência é preencher "impacto" com uma previsão plausível de mercado,
e "próximos passos" com uma recomendação genérica, mesmo sem a fonte
ter dito nada disso) — exatamente a categoria de problema que o Rodrigo
descreveu. Corrigido trazendo a mesma régua do prompt do Research pra
cá: regra explícita por campo (IMPACTO só conta reação/consequência que
a FONTE relata como já acontecida, nunca previsão do resumo; PRÓXIMOS
PASSOS só conta com data/ação explícita na fonte, nunca recomendação
genérica) e proibição explícita de causa->consequência não conectada
pela fonte, consenso não citado e hipótese tratada como fato. Formato e
nomes dos 4 campos mantidos inalterados de propósito — `ui/
news_tab.py:_CAMPOS_TEASER` e os testes de `tests/test_news_fase3.py`
dependem do formato exato `CAMPO: valor`, e mudar os nomes seria
reescrever um componente que já funciona (teaser do card) sem motivo.
Suite completa 249/249 depois da mudança (os testes de teaser usam
texto de resumo fixo nos fixtures, não o prompt em si — não afetados).

### 3. Cards de notícia / feed editorial (item 4)

Conferido o estado atual antes de considerar mudar algo (instrução
explícita: "se ainda não estiver implementado"). Já está implementado
desde a FASE 3 (`ui/news_tab.py`): card compacto com foto (quando
cacheada — `obter_resumos_prontos`, 1 leitura em lote pra tela inteira,
nunca requisição de imagem nova por render), título, fonte, data/hora,
resumo curto (teaser com line-clamp) e tickers relacionados
(`_cartao_noticia`); Morning Call/lives da Genial aparecem
cronologicamente intercalados no MESMO feed, em card próprio
(`_cartao_live`, combinado por `_montar_feed` com ordenação
cronológica real via `_dt_ordenacao`, não a string de data crua — já
testado). Fallback discreto de imagem ausente (iniciais do veículo)
via `_thumb_html`, com `onerror` cobrindo falha de carregamento no
navegador também. Nada a mudar aqui — já é o componente pedido.

### 4. Research — coleta e extração (item 5)

Delegado a uma sub-rotina de investigação dedicada
(`data/research/*.py`, `data/eventos*.py`), em paralelo ao resto desta
sessão, por falta de tempo pra fazer os dois em série dentro da janela
de ~1h. Leu os 8 arquivos linha a linha, comparando com o que
BACKLOG.md/PROGRESSO.md já documentavam como investigado/fechado, sem
relitigar nada.

**Bug real encontrado e corrigido**:
`data/research/genial.py:obter_recomendacoes` extraía o ticker com
`it["url"].rsplit("/", 1)[-1]` — uma URL terminada em "/" (ex:
`/acoes/PETR4/`) devolve `""` como ticker, que nunca bate com nenhum
ticker real em `ui/research_tab.py:363` (`r["ticker"] == ticker`),
perdendo silenciosamente a recomendação/preço-alvo REAL daquele papel
— exatamente a classe de falha pedida ("preserva número/tese/
recomendação/preço-alvo só quando explicitamente presentes"). O
próprio projeto já tinha esse cuidado simétrico em
`data/research/xp.py:obter_texto_aberto` (`link.rstrip("/")` antes do
`rsplit`), só faltava em `genial.py`. Corrigido extraindo a lógica pra
`_ticker_da_url_recomendacao(url)` com `rstrip("/")` antes do
`rsplit`. 2 testes de regressão novos em `tests/test_research.py`
(unitário + fim-a-fim com `_buscar_next_data` mockado, 2 tickers — um
com barra final, outro sem — confirmando que nenhum perde dado nem
embaralha entre tickers). Confirmado que o teste de fato pega o bug
(quebra revertendo só `genial.py`). Suite completa 251/251 depois
(249 + 2 novos), `compileall`/`pyflakes` limpos.

**Investigado, não alterado por falta de confirmação** (mesmo padrão
de cautela desta rodada - nunca arriscar um fix especulativo sem
conseguir confirmar o cenário real): o regex que extrai ticker do LINK
de um relatório (`_TICKER_NO_LINK = r"^/acoes/([A-Z0-9]{4,6})(?:/|$)"`,
usado por `_ticker_do_link`, distinto do bug acima) é case-sensitive —
se a Genial usar minúsculas no slug da URL em algum relatório real
(não confirmável sem acesso de rede ao domínio, bloqueado neste
sandbox, nem amostra salva no repo), a atribuição se perderia do mesmo
jeito, silenciosamente, pra TODO relatório de ações/estratégia/macro.
Pendência concreta pro Rodrigo: abrir um relatório de ações em
produção e confirmar se a URL tem o ticker em maiúscula (ex:
`/acoes/PETR4/...`) ou minúscula (`/acoes/petr4/...`); se for
minúscula, o fix é trivial e seguro (mesmo padrão de `.upper()` já
usado em `xp.py:_tickers_do_class_list`).

Demais arquivos auditados (`genial_lives.py`, `store.py`,
`historico.py`, `base.py`, `xp.py`, `data/eventos.py`,
`data/eventos_coleta.py`) — sem outra falha de corretude confirmada;
`data/eventos.py` já muito bem auditado em ciclos recentes, nada novo
encontrado. Risco teórico de falso-positivo em
`historico._mudou` (comparação `!=` se o Postgrest devolver `numeric`
como string em algum cenário) e o risco genérico de ambiguidade de
nome de empresa em `eventos_coleta.py:tentar_news` (mitigado pela
mesma janela de sanidade de data que o módulo já usa, por design) —
ambos de impacto baixo e não verificáveis sem acesso real ao Supabase/
rede, não alterados.

### Pendências pra próxima fase (FASE 6)

1. Auditoria visual Playwright formal continua faltando harness
   dedicado pra RESEARCH, TOP MERCADO, EQUITY e CALENDÁRIO (só MERCADO,
   CVM e agora NEWS têm harness próprio) — candidato natural pro
   próximo ciclo.
2. Itens já conhecidos de ciclos anteriores continuam de pé sem
   mudança: EQUITY não é "Company 360" (iniciativa de produto maior),
   fontes de Research ainda não integradas (BTG/Itaú BBA/Santander/
   BB/Safra/Ágora/Inter — bloqueio de IP/API fechada/SPA sem API
   óbvia, ver BACKLOG.md), lives da Genial no YouTube desligadas por
   respeito ao `robots.txt` (decisão de risco/ToS do Rodrigo).
