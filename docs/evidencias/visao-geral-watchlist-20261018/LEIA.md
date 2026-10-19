# MINHA WATCHLIST (VISÃO GERAL) — ticker clicável (2026-10-18)

Capturas geradas com um harness local (Streamlit + Playwright) chamando
`ui.visao_geral._painel_watchlist_compacta` real com **dados de exemplo**
(não são dados de produção: este ambiente não tem acesso ao Yahoo Finance
nem ao Supabase).

- `depois_desktop.png` / `depois_mobile.png` — depois da correção
  (`audit/redesign-360-20261018`): o ticker virou um `st.button` real
  (`on_click=_ir_para_equity`, mesmo mecanismo já usado no ranking de
  MERCADO), em vez de um `<span style="color:var(--destaque)">` sem
  nenhum destino (achado da auditoria 360 — ver
  `docs/auditoria-redesign-360.md`, seção "Falsa affordance de clique").

Confirmado com Playwright: o botão existe de verdade (role=button),
clicar não gera erro de console, e o layout mobile (390px) não sobrepõe
mais preço/variação com o botão da linha seguinte (bug real encontrado e
corrigido durante esta mesma sessão — a 1ª tentativa de correção usava
margem menor que o row-gap entre colunas empilhadas, ainda ambígua sobre
a quem pertencia cada linha de preço).

A validação com dados reais de produção (preço/variação de verdade,
clique navegando até EQUITY dentro do app completo) depende do deploy
(Streamlit Cloud) — login Google impossível de automatizar neste
ambiente.
