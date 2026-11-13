# Revisão de interface Bloomberg — auditoria das 15 áreas (2026-11-13)

Missão: revisar visual e funcionalmente (evidência real de navegador, não
suposição) as 15 áreas pedidas pelo Rodrigo — HOME, MERCADO, RADAR,
ANÁLISES, INTELIGÊNCIAS, CARTEIRAS, NOTÍCIAS, CALENDÁRIO, MORNING CALL,
MACRO, SETORES, CVM, TOP MERCADO, SISTEMA, USUÁRIOS — contra a direção
"Bloomberg/Fincept" (preto/âmbar, monoespaçado, denso) e corrigir bugs
reais de baixo risco com evidência antes/depois.

Regra do projeto (CLAUDE.md, regra 7: "sem auditoria repetida") seguida à
risca: 9 destas 15 áreas já tinham auditoria visual completa e recente
(Playwright real, Chromium, 2026-11-06 a 2026-11-13) com o MESMO código
desta worktree (confirmado por `git log`, nenhum arquivo dessas áreas
mudou desde a última captura) — reaproveitadas, não refeitas. Esforço
novo desta frente concentrado em: (1) reconfirmar com screenshot FRESCO
HOME/MERCADO (áreas com harness existente, mas sem captura recente nesta
worktree), (2) cobrir CALENDÁRIO, que nunca tinha harness/screenshot
dedicado, (3) corrigir o achado real mais significativo da missão —
CARTEIRA RECOMENDADA era a única área do app sem nenhum traço do design
system.

## Achado 1 (corrigido) — CARTEIRA RECOMENDADA sem design system

`app.py` tinha, pra toda a área CARTEIRA RECOMENDADA (Visão Geral +
Histórico), um render MÍNIMO direto no dispatcher: `st.title`/
`st.caption`/`st.write`/`st.expander` puro — zero `classe_sinal`,
`numero_financeiro_html`, `painel-titulo` (ver `ui/design_system.py`).
Era a única área de CONTEÚDO do app sem nenhum traço do terminal
Bloomberg — comentário no próprio código confirmava ser proposital
("Render MÍNIMO funcional... a interface completa é tarefa do Agente A"),
mas esse trabalho nunca foi feito em nenhuma PR anterior (confirmado:
nenhuma menção a "carteira" em `docs/evidencias/agente-a-redesign-
estrutural-20261112/LEIA.md`).

Pior ainda, confirmado só com o screenshot real (não era óbvio lendo o
código): `st.write(dict)` do HISTÓRICO renderizava cada linha como um
componente JSON colapsado, SEM NENHUM TEXTO VISÍVEL na tela sem clicar
pra expandir (ver `antes_hist_1440.png` — 3 caixas cinza vazias).

**Correção** (`ui/carteira_recomendada_tab.py`, módulo novo + `app.py`
só troca a chamada): tabela densa (1 linha por ativo, sempre visível —
ticker/setor/peso/sinal com badge colorido/confiança/preço de
referência/preço-alvo/retorno do cenário base/próxima revisão) + faixa
de métricas de resumo (ativos/peso total/setores cobertos/concentração
máxima) + diversificação setorial + cenário macro (Selic/CDI/Focus) +
expander de DETALHE por ativo (tese/riscos/cenários completos/critério
de saída — suplementar, nunca escondendo a decisão primária, que já está
na tabela). Histórico vira tabela densa (registrado em/ativo/campo/valor
anterior/valor novo/motivo) em vez de `st.write` de dict cru. Zero campo
novo, zero cálculo novo — mesmo shape de
`data/carteira_recomendada.py:montar_carteira_recomendada()`/
`listar_historico_alteracoes()`, só reorganizado em APRESENTAÇÃO.

Evidência: `antes_vg_{1440,1024,390}.png` / `depois_vg_{1440,1024,390}.png`
(Visão Geral), `antes_hist_*.png` / `depois_hist_*.png` (Histórico) —
harnesses `harness_carteira_antes.py` (reproduz literalmente o código
antigo, só pra registro visual) / `harness_carteira_depois.py`, dado
mockado compartilhado em `_dados_carteira.py`.

Bug menor encontrado e corrigido NO PRÓPRIO MÓDULO NOVO durante a
validação: a linha "Horizonte: ..." (resumo) nascia colada/sobreposta ao
cabeçalho da tabela (sem margem suficiente entre os dois elementos) —
corrigido com margem explícita nos dois lados (`.cart-scroll { margin-
top:0.8rem }` + `margin:0.5rem 0 1rem 0` na linha de horizonte).

## Achado 2 (corrigido) — grade do CALENDÁRIO empilha em 1 coluna no celular

`ui/calendario_tab.py` (MERCADO › Agenda) usa `st.columns(7)` por semana
dentro de `st.container(key="cal_grade_area")`. A regra GENÉRICA de
mobile em `style.css` (`@media (max-width:640px)`, topo do arquivo)
empilha QUALQUER `st.columns` em 100% de largura — exatamente o mesmo bug
já corrigido antes para `.st-key-mercado_ranking_lista` (ver comentário
em `style.css`), mas a mesma exceção nunca foi adicionada para a grade do
calendário. Resultado real a 390px (`calendario_390_antes_bug_grade_
mobile.png`): a grade de 7 colunas virava uma lista vertical de ~35
células cheias (dias do mês anterior/seguinte incluídos), cada uma
ocupando a largura inteira — o dia da semana deixava de corresponder à
posição, perdendo o sentido de "calendário". O próprio CSS do módulo já
tinha ajustes de fonte/padding específicos pra célula estreita (comentário
"bug real corrigido 2026-10-10"), confirmando que a intenção sempre foi
manter as 7 colunas lado a lado no celular — só faltava a regra de
`flex-wrap:nowrap`.

**Correção** (`style.css`, novo bloco `@media (max-width:640px)` logo
após a exceção do ranking): `.st-key-cal_grade_area div[data-testid=
"stHorizontalBlock"] { flex-wrap:nowrap !important; column-gap:4px
!important; }` + colunas-filhas com `min-width:0`. Confirmado em
`calendario_390.png` (depois): 7 colunas lado a lado, dia da semana
correto, texto truncado com reticências nas células com evento (regra já
existente), sem sobreposição. Regressão coberta por
`tests/test_calendario_grade_mobile_nowrap.py` (asserção estática sobre o
texto do CSS, sem precisar de Chromium pra pegar quem remover a regra no
futuro).

## Harness novo

- `harness_calendario.py`: MERCADO › Agenda nunca tinha harness/screenshot
  dedicado nesta pasta de evidências — mocka só
  `calcular_calendario_cacheado`/`obter_snapshot_calendario`/
  `universo_calendario`/`obter_documentos_cvm`/`obter_noticias`/
  `listar_itens`, zero rede real. `render_calendario` é `@st.fragment`
  (chamado via `.__wrapped__`, mesma técnica já documentada no projeto
  pra fragment em modo "bare").

## Achado à parte (não é bug, documentado) — cold-start do Playwright

Duas capturas iniciais (`home_1440.png`, `calendario_1440.png` numa 1ª
tentativa) saíram em branco/incompletas com o `shot.py` padrão (`load` +
4s de espera) — mesmo sintoma de cold-start já documentado antes neste
projeto (Agente D, regressão de toque 2026-11-12: "1ª tentativa teve
falso-negativo por cold-start"). Recapturado com `networkidle` + 8s de
espera (ajuste permanente em `shot.py` desta pasta) e o conteúdo apareceu
completo e correto — não é bug de produto, é limitação da captura a
frio com muitos widgets/gráficos Plotly na primeira renderização.

## Veredito por área (resumo — detalhe completo na resposta final)

| Área | Veredito |
|---|---|
| HOME | Consistente (reconfirmado, screenshot fresco) |
| MERCADO | Consistente (reconfirmado, screenshot fresco) |
| RADAR | Consistente (redesenhado e validado 2026-11-12/13, reaproveitado) |
| ANÁLISES | Consistente (Valuation/Fundamentos validados antes; Empresas revisado por código) |
| INTELIGÊNCIAS (Coordenador) | Consistente (Visão Geral/Central redesenhados e validados; Especialistas/Execuções revisados por código) |
| CARTEIRAS (Carteira Recomendada) | Inconsistência encontrada e corrigida (achado 1) |
| NOTÍCIAS | Consistente (reaproveitado, validado 2026-11-06/11) |
| CALENDÁRIO | Inconsistência encontrada e corrigida (achado 2) |
| MORNING CALL | Consistente (validado 2026-11-13) |
| MACRO | Consistente (2 subabas corrigidas em 2026-11-13, reaproveitado) |
| SETORES | Consistente (reaproveitado, validado 2026-11-06) |
| CVM | Consistente (validado 2026-11-13) |
| TOP MERCADO | Consistente (reaproveitado, validado 2026-11-11) |
| SISTEMA | Consistente, com 1 pendência de CSS já documentada (overflow do `max-height`, fora do escopo desta missão — ver auditoria 2026-11-13 anterior) |
| USUÁRIOS | Consistente (reaproveitado, validado 2026-11-06) |

## Testes

`python -m pytest tests/ -q` — ver resultado completo na PR.
`python -m pytest tests/test_carteira_recomendada_tab_ui.py
tests/test_calendario_grade_mobile_nowrap.py -q` → 9 passed (testes
novos desta missão).
