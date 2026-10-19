# MERCADO/VISÃO GERAL — Mais Negociados: ticker clicável (2026-10-18)

Capturas geradas com um harness local (Streamlit + Playwright) chamando
`ui.mercado_tab._painel_mais_negociados` real com **dados de exemplo** (não
são dados de produção: este ambiente não tem acesso ao Yahoo Finance).

- `depois_desktop.png` / `depois_mobile.png` — depois da correção
  (`fix/mercado-mais-negociados-clicavel-20261018`): o ticker virou um
  `st.button` real (`on_click=_ir_para_equity`, mesmo mecanismo já usado no
  ranking de Maiores Altas/Baixas), em vez de `<td>{ticker}</td>` cru dentro
  de uma tabela HTML sem nenhum destino.

Esse painel é reaproveitado por **duas** abas (`ui/mercado_tab.py` e
`ui/visao_geral.py`, registro `("mais_negociados", "Mais negociados",
_painel_mais_negociados)`) — a correção vale pras duas ao mesmo tempo, sem
duplicar código.

Confirmado com Playwright nos 2 breakpoints (1280px/390px): botão existe de
verdade (role=button), clique não gera erro de console, layout mobile não
sobrepõe linhas (lição aplicada preventivamente da correção anterior do
painel MINHA WATCHLIST, mesma auditoria: margem entre linhas maior que o
row-gap global de colunas empilhadas, 1.1rem > 0.7rem).

A validação com dados reais de produção (clique navegando até EQUITY dentro
do app completo) depende do deploy (Streamlit Cloud) — login Google
impossível de automatizar neste ambiente.
