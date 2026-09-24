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
