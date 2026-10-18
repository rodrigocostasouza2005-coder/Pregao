# RESEARCH — rótulo "gerado por IA" no bloco de resumo (2026-10-18)

Capturas geradas com um harness local (Streamlit + Playwright) chamando
`ui.research_tab._bloco_resumo` real com **dados de exemplo**.

## O que foi corrigido

`_bloco_resumo` (usada em 5 pontos de `ui/research_tab.py`: relatório
completo, painel da watchlist, feed geral — todos resumos gerados via
`data/research/resumir.py:obter_resumo`, sempre sintetizado por IA/Groq)
mostrava o texto do resumo **sem nenhum rótulo**, nem "Resumo" nem
qualquer indicação de origem. Mesmo princípio de risco já corrigido no
Morning Call (P0, card de EMPRESAS) e no modal de documento da CVM
(PR #77, mesma auditoria) — aqui a lacuna era ainda maior, pois nem um
rótulo "Resumo" simples existia.

Corrigido: adicionado "RESUMO (GERADO POR IA)" acima do texto, mesma
convenção visual já usada no CVM.

## Testes

Teste de reprodução escrito e confirmado **falhando no código antigo**
(nenhuma menção a IA no HTML renderizado) antes da correção. Suíte
completa: 889 passed — os testes existentes que mockam `_bloco_resumo`
(`tests/test_research_news_context.py`) não foram afetados (continuam
mockando a função inteira, não dependem do HTML interno).

## Validação visual

Validado com Playwright (harness isolado) em 2 breakpoints (1280px/390px):
rótulo legível, sem corte, sem erro de console.

## Escopo

Mudança isolada em `ui/research_tab.py` (1 função, compartilhada pelos 5
pontos de uso) + teste novo em arquivo próprio
(`tests/test_research_resumo_ia.py`, para não conflitar textualmente com
o PR #75, que já altera `tests/test_research_news_context.py` nesta
mesma sessão).
