# PREGÃO 2.1 — Agente D: interface restante (2026-11-13)

Missão: revisar as 8 telas apontadas pela missão anterior (PR #301,
`docs/evidencias/agente-a-redesign-estrutural-20261112/LEIA.md`) como
"sem redesign estrutural, so' revisadas no codigo" — MACRO, SETORES, CVM,
TOP MERCADO, SISTEMA, USUÁRIOS, NOTÍCIAS › Empresas, MORNING CALL.
Pedido explícito do Rodrigo: **primeiro confirmar se há problema
estrutural real antes de mexer** — nada de redesign cosmético por
redesign. Veredito tela a tela abaixo; só 2 subabas (dentro de MACRO)
tinham problema real confirmado por screenshot (Playwright real, Chromium,
desktop 1440px + iPad 1024px).

## Método

Pra cada tela: leitura completa do código (`ui/*.py`) procurando os
sintomas pedidos (espaço vazio desperdiçado, informação importante em
expander fechado por padrão, `st.columns()` sequenciais mal distribuídos,
cards genéricos, densidade baixa onde deveria ser alta) + confirmação
visual via harness Streamlit real (sem login/Supabase) renderizado com
Playwright real. Harnesses de CVM e MORNING CALL são novos (não existia
evidência visual anterior pra essas 2 telas); os demais reaproveitam
harness/screenshot já existente da missão "Bloomberg âmbar" de 2026-11-06
(`docs/evidencias/macro-bloomberg-20261106/`,
`docs/evidencias/setores-bloomberg-20261106/`,
`docs/evidencias/mais-admin-bloomberg-20261106/`,
`docs/evidencias/experiencia-design-system-20261111/`) — confirmado via
`git log` que o código dessas telas não mudou desde aquela captura, então
o screenshot antigo ainda representa o estado atual (exceto as 2 subabas
de MACRO corrigidas aqui, re-capturadas depois da mudança).

## Veredito por tela

### MACRO › Indicadores — já adequada, não mexida
Workspace modular (`ui/workspace.py`, mesmo mecanismo de MERCADO/RADAR,
já validado em produção): RESUMO fixo no topo (Selic/CDI/IPCA/Juro real +
Focus) seguido de painéis arrastáveis (Curva Pré, IPCA, Selic x CDI).
Empilhamento vertical aqui é intencional (gráficos Plotly precisam de
largura cheia pra legibilidade) e o usuário pode rearranjar em grade via
drag-and-drop — não é uma lacuna de redesign, é a mesma arquitetura
dashboard já usada e aprovada em MERCADO. Screenshot:
`docs/evidencias/macro-bloomberg-20261106/harness_macro_indicadores.png`.

### MACRO › Juros — já adequada, não mexida
3 painéis empilhados (Selic x CDI, Curva Pré, Expectativas) + atalhos de
setor. Cada painel tem conteúdo genuinamente alto (2 gráficos de série
temporal + 1 tabela de 6 linhas) — largura total é a escolha certa aqui,
diferente de Câmbio/Calendário (ver abaixo). Screenshot:
`docs/evidencias/macro-bloomberg-20261106/harness_macro_juros.png`.

### MACRO › Câmbio e Commodities — PROBLEMA REAL, corrigido
**Antes** (`antes_macro_cambio_1440.png`, re-capturado agora - código
idêntico ao de 2026-11-06): painel CÂMBIO (2 pares, DOLAR/EURO) e painel
CENÁRIO GLOBAL (6 itens fixos) empilhados, cada um ocupando uma linha de
~1440px de largura pra só 2-6 cartões compactos — sobravam ~1100px
(68% da tela) de preto vazio abaixo dos 2 painéis, e o próprio painel
CÂMBIO usava só ~25% da largura disponível. Isso é exatamente o sintoma
"espaço vazio desperdiçado" que o Rodrigo pediu pra caçar.

**Depois** (`depois_macro_cambio_1440.png` / `_1024.png`): os 2 painéis
lado a lado (`st.columns([1, 2])` — proporção estável porque as contagens
de `config.INDICES_TICKER_TAPE`/`config.CENARIO_GLOBAL` são fixas, não
crescem com dado de usuário). Corta o espaço vazio pela metade e usa a
largura de verdade. Confirmado também em 1024px (iPad): colunas continuam
lado a lado, sem sobreposição nem corte de texto.

Zero dado/cálculo novo — só reorganização de `with st.container(border=True)`
sequencial pra `st.columns` + `with container` dentro de cada coluna.

### MACRO › Calendário Econômico — PROBLEMA REAL, corrigido
**Antes** (`antes_macro_calendario_1440.png`, código idêntico ao de
2026-11-06): 3 painéis empilhados — "ÚLTIMA DECISÃO DO COPOM" (1 linha de
destaque + 1 linha de metadado), "EXPECTATIVAS DE MERCADO" (tabela de 6
linhas), "PRÓXIMAS DIVULGAÇÕES" (1 parágrafo dizendo que o dado não
existe). Os 2 primeiros/último são curtos mas cada um tomava uma linha
inteira de 1440px — de novo, grande área preta vazia abaixo do conteúdo.

**Depois** (`depois_macro_calendario_1440.png` / `_1024.png`): ÚLTIMA
DECISÃO DO COPOM e PRÓXIMAS DIVULGAÇÕES (os 2 blocos curtos) lado a lado
(`st.columns(2)`); EXPECTATIVAS DE MERCADO (a tabela, que precisa de
largura real pras colunas MEDIANA/MÉDIA/RESPONDENTES) continua em largura
total, abaixo dos 2. Confirmado em 1024px também.

Zero dado/cálculo novo — mesma reorganização de composição, nenhuma
função de `data/macro.py` tocada.

### SETORES › Mapa Setorial / Visão por Setor / Catalisadores — já adequadas, não mexidas
Mapa Setorial reusa os painéis DESEMPENHO SETORIAL/MAPA DO MERCADO de
MERCADO (treemap denso, largura cheia, zero espaço vazio). Visão por
Setor já é uma grade 2 colunas (empresas+contexto editorial | notícias do
setor). Catalisadores já é denso (eventos corporativos + texto editorial
+ 2 botões de atalho). Nenhum expander escondendo informação relevante,
nenhuma coluna desproporcional. Screenshots:
`docs/evidencias/setores-bloomberg-20261106/harness_{mapa,visao,catalisadores}.png`.

### CVM — já adequada, não mexida
Harness novo (`harness_cvm.py`, 37 documentos mockados): faixa de
destaques (fatos relevantes/ticker mais ativo/último documento) logo
abaixo do título, busca + pills de ticker/tipo inline, tabela densa
DATA/TICKER/TIPO/ASSUNTO com paginação. Zero espaço vazio, zero expander
escondendo conteúdo — já é o resultado de várias iterações reais
anteriores (busca, paginação, correção de largura de coluna). Confirmado
em 1440px e 1024px (`cvm_1440.png`, `cvm_1024.png`) — texto trunca com
reticências corretamente em 1024px, sem sobreposição.

### TOP MERCADO — já adequada, não mexida
Ranking denso de 1 coluna (lista, não cards), legenda de metodologia
antes dos filtros, filtros região+setor numa única linha, contador antes
da lista. Screenshot:
`docs/evidencias/experiencia-design-system-20261111/top_mercado_desktop-1440.png`.

### SISTEMA — já adequada, não mexida
3 tabs (CHANGELOG/PROGRESSO/MANUAL), cada documento num painel com
tipografia própria (cabeçalhos do Markdown não saem no tamanho padrão do
Streamlit). Observação à parte (fora do escopo desta missão - não é
sintoma de composição/hierarquia, é um detalhe de CSS): o `max-height:
32rem` pensado pra limitar a altura visível do painel com scroll interno
não está sendo aplicado na prática (`sistema_fresh_1440.png` mostra o
documento inteiro sem corte) — reportando pro Rodrigo decidir se vale
uma frente própria de CSS, mas não mexi nisso aqui porque é bug de
overflow, não problema de estrutura/hierarquia que esta missão pediu pra
caçar.

### USUÁRIOS — já adequada, não mexida
Faixa de 6 métricas densas, busca + 2 selects de filtro na mesma linha,
tabela HTML densa, exportar CSV. Screenshot:
`docs/evidencias/mais-admin-bloomberg-20261106/harness_usuarios.png`.

### NOTÍCIAS › Empresas — já adequada, não mexida
`render_news` (`ui/news_tab.py`): título, legenda da metodologia do selo,
pills de ticker/selo na mesma linha, contador, feed de cards (mesmo
componente já validado visualmente em TOP MERCADO/CVM), botão VER MAIS.
Revisão só de código (reusa componente já confirmado visualmente em 2
outras telas desta auditoria) — risco de regressão visual é baixo o
suficiente pra não justificar harness novo dedicado.

### MORNING CALL › Edição Atual — já adequada, não mexida
Harness novo (`harness_morning_call.py`, síntese de mercado mockada):
RESUMO EXECUTIVO + RADAR DE AÇÕES + CENÁRIOS E RISCOS inline (não atrás
de expander), com "O que observar nas próximas sessões" integrado.
2 expanders no fim são deliberados, não "informação escondida": um é uma
ação cara (busca fontes ao vivo, nunca deveria disparar sozinha ao abrir
a aba) e o outro é o texto já enviado por e-mail, estritamente redundante
com o resumo executivo acima (que tem dado mais rico, "dados de agora").
Confirmado em 1440px e 1024px (`mc_edicao_1440.png`, `mc_edicao_1024.png`).

### MORNING CALL › Relatório Completo / Histórico / Preferências — já adequadas, não mexidas
Relatório Completo: ação sob demanda (gerar PDF) com preview opcional —
expander aqui também é deliberado (conteúdo custoso, não escondido por
padrão sem motivo). Histórico: métricas + filtros + lista paginada por
expander (1 item por edição passada, padrão correto pra lista histórica).
Preferências: 1 toggle, efeito imediato. Revisão só de código — nenhum
sintoma dos citados no pedido do Rodrigo.

## Suíte de testes

`python -m pytest tests/ -q` → **2591 passed** (nenhuma falha, nenhuma
flakiness pré-existente desta vez — rodada limpa).

`python -m pytest tests/test_macro_bloomberg_20261106.py -q` → 6 passed
(mesmo arquivo que cobre `render_macro_cambio_commodities`/
`render_macro_calendario` — confirma que a reorganização de
`st.container` pra `st.columns` não quebrou nenhuma asserção de
conteúdo/formatação).

## Toque em iPad (regressão de navegação, reuso)

`docs/evidencias/regressao-toque-ipad-radar-20261112/touch_regressao.py`
reexecutado contra o código atual (não toca `ui/macro_tab.py`, cobre
sidebar+navegação): **OK** — toque real chega no botão "Carteiras
Recomendadas" e navega (`sub=carteiras`). 1ª tentativa teve falso-negativo
por cold-start do Streamlit (0 botões encontrados, timing); 2ª tentativa
confirmou navegação normal, sem bug de overlay da sidebar.

## Resumo

2 de 16 subabas revisadas (dentro das 8 telas apontadas pela missão
anterior) tinham problema estrutural real confirmado visualmente (MACRO
› Câmbio e Commodities, MACRO › Calendário Econômico — ambas "espaço
vazio desperdiçado" por empilhamento de painéis compactos) e foram
corrigidas (`ui/macro_tab.py`, só composição/`st.columns`, zero dado/
cálculo novo). As outras 14 subabas (MACRO › Indicadores/Juros, SETORES
› 3 subabas, CVM, TOP MERCADO, SISTEMA, USUÁRIOS, NOTÍCIAS › Empresas,
MORNING CALL › 4 subabas) já estavam adequadas e não foram tocadas.
