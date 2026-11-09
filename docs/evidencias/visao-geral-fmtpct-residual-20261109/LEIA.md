# Evidência — resíduo do `_fmt_pct` em VISÃO GERAL (2026-11-09)

Rodrigo reportou visualmente que a VISÃO GERAL (MERCADO›Visão Geral) "não
foi reformatada" após a onda de design system Bloomberg âmbar de
2026-11-06 (PR #258 + frentes #263-278). Auditoria do código confirmou: o
arquivo `ui/visao_geral.py` já importava `design_system` e usava
`classe_sinal`/`divisor_html` em 2 painéis, mas o helper antigo `_fmt_pct`
(linha 53, montagem manual `sinal = "+" if valor >= 0 else ""` — exatamente
o padrão que a fundação do design system (PR #258) cita como duplicado)
nunca foi removido, e ainda era chamado em 3 lugares:

1. `_painel_altas_baixas_resumo` (PRINCIPAIS ALTAS E BAIXAS) — painel bem
   visível, segunda seção da tela.
2. `_painel_mapa_setorial_compacto` (MAPA SETORIAL) — valor de cada bloco
   setorial.
3. Mesmo painel, linha "Maior dispersão: ... méd."

Corrigido substituindo as 3 chamadas por `design_system.variacao_html`
(painel 1, onde a cor por item já fazia sentido) ou
`design_system.numero_financeiro_html(..., com_sinal=True)` (painéis 2 e
3, onde a cor já vinha de fora via `classe_sinal`/CSS inline — evita
colorir 2x). `_fmt_pct` foi removida do arquivo (sem mais chamadores).

Zero mudança de dado/cálculo — só formatação visual, mesmo escopo das
frentes anteriores.

## Validação

- Reuso do harness já existente (`docs/evidencias/validacao-independente-home-mercado-20261106/harness_home.py`),
  sem nenhuma mudança — mesmos mocks, zero dado novo.
- Suíte completa `pytest`: 2250 passed, sem regressão.
- Screenshot real (Playwright, desktop 1440px): `depois.png`, confirma
  tabular-nums alinhado e sinal correto em ALTAS E BAIXAS e MAPA SETORIAL
  (ex: "Maior dispersão: Varejo (7 papel(éis), -3,80% méd.)").

## Não validado

Produção/Streamlit Cloud — só harness local.
