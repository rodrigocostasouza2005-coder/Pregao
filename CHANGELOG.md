# CHANGELOG — PREGÃO

Entradas curtas por commit, em português simples: o que mudou e por quê.
Mais recente primeiro.

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
