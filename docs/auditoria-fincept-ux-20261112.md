# Auditoria UX — Fincept Terminal como referência pro PREGÃO

**Data:** 2026-11-12
**Autor:** Agente FINCEPT-D (auditoria, zero edição de `ui/*.py` ou `data/research/*.py`)
**Repo auditado:** [Fincept-Corporation/FinceptTerminal](https://github.com/Fincept-Corporation/FinceptTerminal) (clone raso, fora do worktree, não commitado)
**Licença do Fincept:** AGPL-3.0-or-later — nenhum código ou asset foi copiado. Tudo abaixo é descrição de conceito/composição, reimplementável do zero com a identidade visual própria do PREGÃO (preto/grafite/âmbar `#FFA028`, monoespaçado).

---

## 0. O que o Fincept realmente é (correção de premissa)

Antes de comparar pixel a pixel: o Fincept **não é web nem TUI** — é um app **desktop nativo C++20 + Qt6** (`fincept-qt/`, CMake + Ninja, binário único, sem Electron/Node). Isso significa:

- O que é **diretamente transferível**: composição visual, hierarquia, densidade, nomenclatura de padrões (tudo isso é CSS/QSS + layout, reimplementável em HTML/CSS dentro de qualquer `st.markdown` do Streamlit).
- O que **não é transferível**: a mecânica de interação nativa (docking de janelas Qt arrastável, atalhos de teclado globais do SO, multi-threading C++ para live data) — Streamlit não tem equivalente e não vale tentar simular.
- Conclusão: o relatório abaixo foca em **princípios de organização/densidade/hierarquia**, não em "copiar comportamento de app desktop pra web". Em nenhum achado a recomendação é sair do Streamlit.

Evidência verificada (não assumida): `README.md` do repo confirma "native C++20 desktop terminal for financial research — Qt6 UI, embedded Python 3.11". A árvore `fincept-qt/src/` tem ~190 diretórios organizados em `screens/` (41+ módulos: dashboard, markets, portfolio, news, watchlist, screener, geopolitics, maritime, node_editor, ai_quant_lab...), `ui/` (theme, tables, command, navigation, formatting, workspace) e `core/panel/` (registry de painéis dockáveis). Há 8 screenshots reais em `images/` (Dashboard, Equity Research, Portfolio, News, Node Editor, Geopolitics, Maritime, Research) que foram inspecionados diretamente.

---

## 1. Densidade de informação

**Fincept:** a tela de Dashboard mostra simultaneamente 7 widgets lado a lado (Global Indices, Forex-Major Pairs, Commodities, Market News + vídeo embutido, Quote de um ativo, Market Pulse com Fear&Greed + breadth NYSE/NASDAQ/S&P + Top Gainers/Losers, barra de status de mercado) — tudo em uma única tela, sem scroll, cada widget com cabeçalho compacto (texto pequeno maiúsculo + barra colorida lateral) e linhas de dado com `line-height` mínimo. A tela de Equity Research empilha ~25 pontos de dado em 3 colunas (Today's Trading, Valuation, Share Stats | gráfico + tabs | Analyst Targets, 52-Week Range, Profitability, Growth Rates) sem nenhum espaço vazio decorativo.

**Equivalente hoje no PREGÃO:** já existe a classe `.ds-compacto` (`ui/design_system.py`) pra blocos de linha densos, e a regra explícita no design system contra "espaço vazio grande" e "cards genéricos de SaaS". Ou seja, o princípio já está formalizado — o que falta é aplicação mais agressiva da composição em **múltiplos widgets pequenos lado a lado por tela**, não a densidade de uma linha isolada.

**O que adaptar (sem sair do Streamlit):** o ganho real do Fincept não é "fonte menor", é **particionamento espacial**: muitos widgets de 150-250px de altura cada, lado a lado, em vez de poucos painéis altos e largos. Isso é 100% fazível com `st.columns` aninhadas + o `st.container(border=True)` que o projeto já usa em `ui/paineis.py`, só exige que o LAYOUT (não o conteúdo) seja repensado por tela — que é exatamente o que a missão de redesign estrutural em andamento já está fazendo.

**Impacto esperado:** alto — densidade de informação por tela é o diferencial mais citado de terminal Bloomberg-like, e é o que mais contrasta com "dashboard genérico".

---

## 2. Organização de painéis/módulos (grid real vs. lista)

**Fincept:** arquitetura de painéis dockáveis de verdade — `src/core/panel/{PanelRegistry, PanelHandle, PanelMaterialiser}` + comandos de texto no command bar pra manipular o dock: digitar `markets add settings` adiciona um painel, `markets replace news` substitui, `markets remove` remove (visto literalmente na assinatura do sinal `dock_command(action, primary, secondary)` em `CommandBar.h`). Ou seja, reorganizar o grid de painéis é um **comando digitado inline**, não um formulário de configuração separado.

**Equivalente hoje no PREGÃO:** já existe o conceito central — `ui/paineis.py` (registro de painéis reordenáveis/ocultáveis via CONFIG) e `ui/workspace.py` (MVP de posição/tamanho livres via drag/resize, arquitetura Workspace → Layout Manager → Panel Container → Panel Content). É estruturalmente o mesmo conceito (registro + materialização de painel), só que a edição de layout no PREGÃO vive em CONFIG/drag, não em um campo de comando.

**O que adaptar:** já há uma preferência registrada do Rodrigo (`feedback_inline_controls`) de ajustar config no próprio elemento, não em formulário à parte — o padrão `dock_command` do Fincept é literalmente isso aplicado à reorganização de painéis. Não é prioridade imediata (grande mudança de interação), mas é munição concreta se a reformulação estrutural decidir ir nessa direção: um campo de texto único que aceita tanto busca de ativo quanto comandos de layout.

**Impacto esperado:** médio — conceitualmente já coberto por `ui/paineis.py`/`workspace.py`; o ganho estaria na UNIFICAÇÃO do controle, não na criação de um sistema novo.

---

## 3. Navegação entre módulos

**Fincept:** dois níveis de abas — uma barra horizontal de módulos top-level (DASHBOARD · MARKETS · CRYPTO · PORTFOLIO · NEWS · AI CHAT · BACKTEST · ALGO · NODES · CODE · QUANT LAB · ...) e, dentro de cada módulo aberto, uma segunda linha de abas de contexto (ex.: dentro de Equity Research: OVERVIEW · FINANCIALS · ANALYSIS · TECHNICALS · TALIPP · PEERS · NEWS · SENTIMENT). Módulos abertos viram tabs que podem ficar lado a lado (visto no screenshot "Equity Research" + "Trade Viz" docados simultaneamente). Navegação alternativa: um command bar universal no topo ("Enter Command...") que aceita nome de tela por texto.

**Equivalente hoje no PREGÃO:** estrutura equivalente já existe — `ui/navegacao.py` documenta "7 áreas + menu MAIS, cada uma com subabas próprias", e cada área lembra a última subaba aberta (`nav_sub_{area_id}`). É o mesmo padrão de dois níveis (área → subaba) que o Fincept usa (módulo → tab de contexto).

**O que adaptar:** nada estrutural novo aqui — o padrão já está implementado. Achado principal é **confirmação de que a abordagem atual do PREGÃO está alinhada com a referência**, não uma lacuna.

**Impacto esperado:** baixo (já coberto) — citar como validação do que já existe, não como pendência.

---

## 4. Hierarquia visual

**Fincept:** destaque via peso+tamanho (preço grande em negrito, ex. `$443.20`) + cor semântica (verde/vermelho só na variação, nunca a linha toda) + títulos de seção em CAIXA ALTA pequena com barra vertical colorida à esquerda (ex. "▎TODAY'S TRADING", "▎VALUATION") — nunca caixa com sombra/gradiente. Badges/tags coloridas de classificação (ex. no News: "BREAKING", "BEARISH", "MAJOR", "MARKETS" como pills pequenas ao lado da manchete) comunicam categoria sem depender só da cor do texto.

**Equivalente hoje no PREGÃO:** o design system já proíbe explicitamente "cards genéricos de SaaS (caixa com sombra/gradiente/ícone decorativo)" e define `classe_sinal()`/`variacao_html()` pra cor semântica consistente — ou seja, o princípio de hierarquia por cor/tipografia (não por caixa) já é regra documentada.

**O que adaptar:** o elemento que falta é o **padrão de badge/tag de classificação** (tipo "BREAKING"/"BEARISH"/sentimento) — útil especificamente para a aba de Casas de Análise (PR #166, painel de teses com recomendação/preço-alvo) e para RADAR/NOTÍCIAS, onde sinalizar "impacto ALTO/MÉDIO/BAIXO" ou "tese ALTA/BAIXA/NEUTRA" como uma pill pequena ao lado do título é mais rápido de escanear que só cor de texto.

**Impacto esperado:** médio — ganho de escaneabilidade em telas de lista/feed (Notícias, Radar, Research), baixo esforço de implementação (é puro HTML/CSS, já existe infraestrutura pra isso no design system).

---

## 5. Tabelas financeiras

**Fincept:** números alinhados à direita com fonte tabular (mesmo princípio de `numero_financeiro_html()` do PREGÃO); cor só na célula de variação, nunca na linha inteira; rodapé de tabela com paginação explícita ("Showing 1-10 of 12", "Page 1 of 2", seletor de linhas por página) e campo de filtro inline logo acima da tabela ("Filter positions..."), não em um formulário separado. Um padrão extra notável: holdings da carteira aparecem primeiro como **grid de mini-cards por ticker** (tile colorido com ticker + variação%) antes da tabela detalhada de posições — serve de resumo visual rápido, a tabela embaixo é o detalhe.

**Equivalente hoje no PREGÃO:** já implementado — `numero_financeiro_html()` em `ui/design_system.py` já aplica `tabular-nums` + alinhamento à direita, e é regra documentada (ponto 3 do design system) pra nunca reinventar isso por aba.

**O que adaptar:** dois detalhes pontuais que não estão confirmados como existentes: (a) filtro de texto inline acima de tabelas longas (watchlist, carteira, radar) em vez de só scroll; (b) grid de mini-tiles por ticker como resumo visual da carteira/watchlist antes da tabela detalhada — ambos são HTML/CSS simples, sem biblioteca nova.

**Impacto esperado:** médio — filtro inline ajuda em telas com lista longa (Carteiras, Watchlist); o grid de tiles é mais estético que funcional, mas barato de testar.

---

## 6. Gráficos

**Fincept:** seletor de período como **linha de abas acima do gráfico** (1M · 3M · 6M · 1Y · 5Y, a selecionada em destaque sólido), não dropdown; candlestick com linhas de referência (preço médio/alvo) sobrepostas; donut de alocação setorial com legenda em lista vertical compacta (não legenda horizontal grande); **matriz de correlação como tabela** (nomes × nomes, diagonal 1.00) em vez de heatmap gráfico — mais barato de renderizar e igualmente legível; indicador tipo Fear&Greed mostrado como número + barra horizontal fina (gradiente), não como gauge radial.

**Equivalente hoje no PREGÃO:** já avançado nessa direção — RSI/MACD/Bollinger inline no gráfico de preço (PR #282, já commitado) e reset de zoom reutilizável (`ui/graficos.py`). O princípio de "gráfico denso mas não poluído" já está em aplicação.

**O que adaptar:** dois padrões especificamente baratos de replicar em Streamlit sem Plotly: (a) matriz de correlação como **tabela HTML comum** em vez de heatmap Plotly, quando o uso é mais "consulta de valor exato" que "padrão visual"; (b) indicador tipo gauge como **barra horizontal HTML** (`<div>` com largura % + gradiente CSS) em vez de `go.Indicator` do Plotly — mais leve e mais fácil de alinhar com o design system de cor existente.

**Impacto esperado:** baixo/médio — ganho mais de performance/consistência visual que de funcionalidade nova, já que o princípio de densidade em gráfico já está sendo seguido.

---

## 7. Watchlists e rankings

**Fincept:** Top Gainers/Top Losers aparecem como lista compacta de 2 colunas (ticker + variação%) empilhada dentro do MESMO widget "Market Pulse", não como tela própria. No módulo Geopolitics, o ranking "HOTSPOTS" mostra um **mini-bar inline na própria célula** (barra horizontal curta ao lado do número, proporcional ao valor) — um jeito barato de dar leitura visual de ranking sem gráfico de barras completo.

**Equivalente hoje no PREGÃO:** não verificado em detalhe neste escopo de auditoria (zero edição/leitura profunda de `ui/*_tab.py` de watchlist/radar foi feita além do necessário pra comparação) — mas o `lista_compacta()`/`.ds-compacto` do design system já dá a base de lista compacta.

**O que adaptar:** o padrão de **barra inline dentro da célula de ranking** (peso setorial, score de hotspot, volume relativo) é o achado mais exportável desta seção — é só um `<div>` com `width: {pct}%` dentro de uma célula de tabela HTML, sem nenhuma lib nova, e comunica magnitude relativa muito mais rápido que só o número.

**Impacto esperado:** médio-alto — barato, visualmente forte, aplicável em qualquer ranking existente (Top Ganhadores, peso setorial, Radar).

---

## 8. Busca/pesquisa de ativo

**Fincept:** o command bar é **o único ponto de entrada** tanto pra navegação entre telas quanto pra busca de ativo, via uma gramática de prefixo `/`: digitar `/` abre um seletor de tipo de ativo (`/stock`, `/fund`, `/index`...), escolher o tipo ativa busca ao vivo (debounced) por símbolo via API; texto sem `/` busca por nome de tela/atalho/palavra-chave (lista de comandos com fuzzy match). O campo também persiste rascunho (o texto digitado sobrevive a fechar/reabrir a tela).

**Equivalente hoje no PREGÃO:** `ui/busca.py` já resolve o problema de forma mais simples e sem custo de rede por tecla — `st.selectbox` nativo sobre um universo curado (composição oficial do Ibovespa + setores + aliases BDR + watchlist atual), com navegação por teclado de graça e zero chamada de API por tecla digitada. É deliberadamente **escopado por aba** (campo de busca de ativo), não um campo universal de navegação+busca combinadas como o do Fincept.

**O que adaptar:** a diferença conceitual real é que o Fincept une "ir para uma tela" e "achar um ativo" no mesmo campo; o PREGÃO mantém os dois separados (navegação por abas/subabas, busca de ativo por `buscar_ativo()` dentro de cada aba). Unificar isso seria uma mudança de interação grande (não recomendado agora, é exatamente o tipo de mudança "estrutural" que a outra missão de redesign já está endereçando) — mas vale registrar como ideia de longo prazo, não ação imediata.

**Impacto esperado:** baixo para ação imediata (a solução atual do PREGÃO já é tecnicamente melhor em custo — zero round-trip por tecla); registrar como ideia de arquitetura futura, não gap a corrigir agora.

---

## Resumo — achados mais aproveitáveis pro redesign em andamento

Ordenados por relação custo (baixo esforço, sem lib nova) / impacto visual:

1. **Barra inline dentro de célula de ranking** (seção 7) — `<div style="width:NN%">` pra peso setorial, score, volume relativo. Mais barato e com maior ganho de legibilidade imediato.
2. **Badges/pills de classificação** (seção 4) — "ALTA/BAIXA/NEUTRA", "IMPACTO ALTO/MÉDIO/BAIXO" como pill pequena, relevante direto pro painel de teses do PR #166 (Casas de Análise) e pro Radar.
3. **Particionamento em múltiplos widgets pequenos por tela** (seção 1) — o ganho de densidade real do Fincept vem de MUITOS widgets de 150-250px lado a lado, não de reduzir fonte; é o princípio que mais sustenta a reclamação recorrente do Rodrigo de que reformulações anteriores "não mudaram nada de verdade" — é mudança de composição, não de token.
4. **Filtro inline + paginação explícita em tabelas longas** (seção 5) — watchlist/carteira/radar.
5. **Seletor de período como linha de abas acima do gráfico, não dropdown** (seção 6) — pequeno, mas mais rápido de usar.
6. **Matriz de correlação / gauge como HTML simples em vez de Plotly** (seção 6) — ganho de performance e consistência, não de funcionalidade.

Achados que confirmam que o caminho atual já está certo (não são gaps): navegação em dois níveis (área→subaba, seção 3), proibição de cards genéricos no design system (seção 4), `numero_financeiro_html()` com tabular-nums (seção 5), RSI/MACD/Bollinger inline (seção 6), arquitetura de painéis registrados + workspace livre (seção 2), busca sem round-trip por tecla (seção 8) — todos já alinhados com o que o Fincept faz de melhor, nenhum precisa de retrabalho.

**Nenhum arquivo em `ui/*.py` ou `data/research/*.py` foi editado nesta auditoria.** Este documento é a única entrega.
