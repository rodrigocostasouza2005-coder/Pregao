# PROGRESSO — Modo Autônomo (2026-09-23)

Log de execução da fila autônoma. Cada tarefa: implementar → `python -m
compileall .` → AppTest das abas afetadas + EQUITY → commit → push →
registro aqui.

## Tarefas concluídas

### T1 — Groq centralizado
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

### T2 — Integração TOP MERCADO/EQUITY (já estava completo)
Verificado: `config.ABAS_DISPONIVEIS` já tem "TOP MERCADO" depois de
"NEWS"; `app.py` já importa e chama `render_news`, `render_news_ticker`
(dentro do bloco EQUITY, dentro de `st.container(border=True)`, sem
coleta nova por interação — `obter_noticias` já é cacheado 20min) e
`render_top_mercado`; placeholders antigos removidos, só sobra CVM
(`_titulos_futuros = {"CVM": "Fase 5"}`). Nada a fazer — trabalho de
sessão anterior já cobriu isso. Nenhuma mudança de código.

### T3 — CSS stButtonGroup (já estava completo)
Verificado: `style.css` e `ui/news_tab.py` já usam
`[data-testid="stButtonGroup"] button` (não mais `stPills`/
`stSegmentedControl`, que não existem nesta versão do Streamlit). O
seletor já é específico o suficiente por construção: `stButtonGroup` é o
testid interno só de segmented_control/pills — botões comuns (RESUMIR,
SALVAR etc.) não usam esse testid, não são afetados. AppTest confirma
EQUITY/MACRO/NEWS/TOP MERCADO renderizando sem exceção com os widgets de
pills em uso. Nenhuma mudança de código.

## Tarefas bloqueadas

(preenchido se alguma falhar 2x)

## Decisões registradas (regra 1 de autonomia)

(preenchido conforme surgirem dúvidas)

## Ações manuais pendentes

(preenchido conforme surgirem)
