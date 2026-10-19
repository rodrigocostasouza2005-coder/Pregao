# WORKSPACE — "VISÃO GERAL" nunca aplicava CSS/drag-resize de verdade (2026-10-19)

Missão de redesign + performance. Achado durante a investigação do painel
"MAIORES ALTAS/BAIXAS" em MERCADO: ao medir a mesma coisa em VISÃO GERAL
(home do Pregão, primeira tela que o usuário vê), nenhum painel tinha
`overflow-y: auto` aplicado — diferente de MERCADO/MACRO, onde o mecanismo
funciona. Investigado até a causa raiz, não só contornado.

**Causa raiz confirmada por inspeção real do DOM (`className`, não
suposição):** `ui/workspace.py:_gerar_css`/`_script_js` constroem os
seletores CSS/JS usando `aba_id` **cru** (`f'...{aba_id}...'`). O Streamlit
sanitiza o `key=` real no lado dele antes de virar classe CSS, trocando cada
caractere fora de `[A-Za-z0-9_-]` por `-`. Para `aba_id="MERCADO"`/`"MACRO"`
(só ASCII) isso não muda nada, e por acaso sempre funcionou. Para
`aba_id="VISÃO GERAL"` (acento + espaço — a ÚNICA das 3 abas que usa o
workspace modular com esse problema), a classe real vira
`st-key-...VIS-O-GERAL...`, mas o seletor gerado aqui continuava pedindo
`...VISÃO GERAL...` literal — nunca batia. Resultado: CSS de
posição/altura/overflow nunca aplicava (painéis caíam de volta pro fluxo
normal do navegador — por isso nunca "parecia" quebrado) **e** o script de
arrastar/redimensionar (`_script_js`) nunca achava os elementos — a feature
de workspace inteira (a PRIMEIRA tela do app) ficava silenciosamente inerte,
apesar do texto "Arraste pelo título pra mover..." continuar visível,
prometendo uma interação que não funcionava.

**Correção:** `ui/workspace.py` ganhou `_slug_aba(aba_id)` (sanitização
idêntica à observada no DOM real), aplicado em TODO lugar que constrói um
`key=` de widget desta aba ou um seletor CSS/JS a partir dela — garante que
a classe real sempre bate com o seletor gerado, sem depender de replicar
o algoritmo exato do Streamlit internamente.

**Efeito colateral esperado e corrigido na mesma sessão:** corrigir o slug
expôs a MESMA lacuna já corrigida em MERCADO (altura genérica de 18rem
cortando conteúdo) — agora que o CSS passa a aplicar de verdade em VISÃO
GERAL, 4 dos 8 painéis (IBOVESPA, MAIORES ALTAS/BAIXAS, MAIS NEGOCIADOS,
DESEMPENHO SETORIAL) cortariam conteúdo sem um `_ALTURAS_PADRAO` próprio.
Adicionado em `ui/visao_geral.py`, reaproveitando os mesmos valores já
calibrados pra MERCADO onde as funções são literalmente as mesmas
(`_painel_altas_baixas`/`_painel_mais_negociados`/`_painel_setorial`,
importadas direto de `ui/mercado_tab.py`).

`depois_desktop.png` / `depois_mobile.png` — Playwright, dados reais (B3 +
Yahoo Finance). `clientHeight == scrollHeight` confirmado em todos os 8
painéis depois da correção (medição via `getComputedStyle`/`scrollHeight`).

5 testes novos em `tests/test_workspace_slug.py` (a única cobertura de
`ui/workspace.py` nesta branch — `tests/test_workspace.py`, cobrindo a
lógica pura de `layout_efetivo`, segue como PR #78 separado, ainda não
mergeado) confirmam que `_slug_aba`/`_gerar_css`/`_script_js`/`_bridge_key`
usam o slug, nunca o `aba_id` cru.
