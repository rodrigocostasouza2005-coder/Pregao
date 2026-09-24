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

## Tarefas bloqueadas

(preenchido se alguma falhar 2x)

## Decisões registradas (regra 1 de autonomia)

(preenchido conforme surgirem dúvidas)

## Ações manuais pendentes

### Colar em `.streamlit/secrets.toml` (local) e no App settings → Secrets do Streamlit Cloud
```toml
[admin]
emails = ["rodrigo.costa.souza2005@gmail.com"]
```
Até colar isso, o painel DIAGNÓSTICO DE FONTES continua funcionando
normalmente (usa o fallback fixo em `config._EMAILS_ADMIN_PADRAO`) — não
é bloqueante, só uma ação de segurança pra repo público.
