# Evidência visual real - MAPA DO MERCADO (treemap), 2026-10-26

Capturado com Playwright real (Chromium) contra um harness isolado
(`ui.mercado_tab._painel_treemap` + `ui.workspace.renderizar_workspace`,
mesmo módulo/função/CSS/tema da aba MERCADO real - sem auth real do
Google nesse ambiente, por isso um harness fora do `app.py`, nunca uma
cópia da lógica do painel) - `obter_panorama_ibovespa()` chamado de
verdade (yfinance real, sem mock).

## Causa raiz confirmada

`antes_desktop.png`: o treemap real (420px de altura de figura) aparece
recortado dentro de uma caixa de ~288px (`_ALTURA_PADRAO_REM` genérico
de `ui/workspace.py`, usado porque `render_mercado()` não passava
`alturas_padrao` pra `renderizar_workspace`) - só os 2 primeiros grupos
de setor aparecem, o resto fica atrás de scroll interno
(`overflow:auto` da div absoluta do painel). Esse é o bug "mapa aparece
pequeno" relatado.

`antes_mobile.png`: no celular o container já cai pra `height:auto`
(fallback mobile do workspace, `@media max-width:640px`), então não há
recorte - mas os blocos saem pequenos porque a figura inteira ainda era
só 420px de altura.

## Depois do fix

`depois_desktop.png` / `depois_desktop_scroll.png`: com
`alturas_padrao={"treemap": 46.0}` repassado pra `renderizar_workspace`
(mesmo mecanismo já usado em MACRO pra um gráfico alto - ver
`ui/macro_tab.py:_ALTURAS_PADRAO`) e a figura Plotly maior
(`_ALTURA_TREEMAP_PX=580`, cabendo dentro do container de 46rem/736px),
o mapa inteiro (76 papéis, todos os setores) aparece sem nenhum corte
nem scroll interno, ocupando a largura útil do painel. Título de cada
setor visível com divisória (barra cinza), ticker+variação% legíveis em
cada bloco, legenda de escala de cor (-58,2% a +58,2%) visível no
rodapé, horário real da última coleta ("Atualizado há 1min · 76
papéis" - `data/mercado.py:obter_momento_panorama()`, nunca um horário
inventado).

`depois_mobile.png`: mesma melhora no celular - blocos maiores,
legenda de horário/contagem, texto legível nos blocos que cabem (Plotly
já esconde texto nos blocos pequenos demais pra caber, comportamento
nativo do `go.Treemap`, sem CSS/JS extra).

## O que NÃO mudou (decisão deliberada)

Os blocos mostram **ticker + variação%**, nunca um logo de empresa: o
projeto não tem nenhuma fonte legítima de logo por ticker da B3 hoje
(conferido - só existe lógica pra REJEITAR logo/favicon como foto de
notícia, nunca pra buscar logo de empresa). Inventar uma URL de CDN de
logo externo pra cada ticker violaria a mesma regra de "nunca URL
inventada" que o resto do projeto já segue, e criaria um sistema
paralelo de logos não pedido. O ticker em destaque (fonte maior,
`textfont size=13`) é o "fallback elegante" - aqui ele é o estado
normal do bloco, não só um caso de erro.
