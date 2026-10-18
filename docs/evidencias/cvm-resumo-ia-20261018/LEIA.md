# CVM — rótulo "gerado por IA" no resumo do documento (2026-10-18)

Capturas geradas com um harness local (Streamlit + Playwright) chamando o
corpo real de `ui.cvm_tab._abrir_card` (`.__wrapped__`, fora do `@st.dialog`
decorador, que precisa de sessão completa) com **dados de exemplo** (não são
dados de produção).

## O que foi corrigido

O modal "DOCUMENTO CVM" mostra um resumo gerado por IA
(`data/cvm.py:obter_resumo_documento`, que baixa o documento oficial e
sintetiza "sempre em palavras próprias" via Groq) sob um rótulo só
"Resumo" — sem nenhuma indicação visível de que o texto foi gerado por um
modelo de linguagem, posicionado logo acima do botão "ABRIR DOCUMENTO ↗"
que leva ao documento oficial de verdade. Um usuário podia ler o "Resumo"
como se fosse um trecho/síntese oficial do próprio documento da CVM.

Corrigido: rótulo agora é "RESUMO (gerado por IA)".

## Testes

- Teste de reprodução escrito e confirmado **falhando no código antigo**
  (rótulo sem menção a IA) antes da correção.
- Suíte completa: 891 passed.

## Validação visual

Validado com Playwright (harness isolado) em 2 breakpoints (1280px/390px):
rótulo legível, sem corte, sem erro de console.

## Escopo relacionado, não corrigido nesta sessão

O mesmo gap existe em RESEARCH (`ui/research_tab.py:_bloco_resumo`) e NEWS
(resumo editorial no modal de notícia) — ambos documentados na auditoria
360, não corrigidos aqui para manter o escopo desta PR isolado (CVM é o
único arquivo tocado) e não empilhar mudanças em `ui/research_tab.py`, que
já tem outra correção em revisão (PR #75) nesta mesma sessão de trabalho.
