# Reformulação estrutural — VISÃO GERAL (2026-11-09)

Pedido explícito da Rodrigo: não só estética, reorganizar de verdade a
distribuição dos módulos de MERCADO›Visão Geral, que tinha "grandes áreas
vazias na tela" e módulos curtos presos ao lado de módulos longos.

## Causa raiz confirmada no código

`render_visao_geral()` encadeava **4 `st.columns()` em sequência**, um por
"linha lógica" (`vg_grid_principal`, `vg_grid_exploracao`,
`vg_grid_desempenho`, `vg_grid_globais`). No Streamlit, um `st.columns()`
força TODAS as colunas daquela chamada a reservar a altura da coluna mais
alta, e a próxima chamada só começa depois que essa termina — não existe
masonry/grid real nativo.

**Medição real** (`medir_paineis.py`, Playwright contra dados mockados
realistas, não suposição):

| Painel | Altura medida (ANTES) |
|---|---|
| Principais Altas e Baixas | 191px |
| Destaques do Dia (mesma linha) | 353px |
| Mapa Setorial (mesma linha) | 218px |
| Mais Negociados | 261px |
| Resultados da Watchlist (mesma linha) | 212px |
| Mercados Globais | 155px |
| Minha Watchlist (mesma linha) | 212px |

Confirma o relato: ~140px de espaço vazio sob Altas-e-Baixas/Setorial até
a linha de Destaques terminar, e gaps menores nas outras duas linhas.

## O que mudou

Trocado 4 chamadas de `st.columns()` por **3 regiões** (`vg_grid_grafico_noticias`,
`vg_grid_oportunidades`, `vg_grid_watchlists`), cada uma com colunas que
**empilham múltiplos painéis** em vez de 1 painel por coluna por linha —
dentro de uma coluna o Streamlit empilha com altura livre; só o conjunto
de colunas de uma MESMA chamada força altura igual entre si. Agrupamento
escolhido por altura medida, pareando painel curto com painel curto:

- **Gráfico + Notícias**: Gráfico (protagonista) | Destaques do Dia —
  os dois crescem independente, sem painel curto preso do lado.
- **Oportunidades**: [Para Investigar + Altas e Baixas] | [Mapa Setorial
  + Mais Negociados] — ambas colunas somam altura parecida.
- **Watchlists**: Resultados da Watchlist | Mercados Globais | Minha
  Watchlist — as 3 já eram parecidas (155-212px), 3 colunas simples não
  cria buraco.

Ordem de leitura também revisada pra bater com a hierarquia pedida
(situação geral → indicadores → gráfico → notícias → oportunidades →
watchlists/complementar): Destaques do Dia subiu pra perto do gráfico;
Para Investigar desceu pra região de oportunidades.

Zero painel novo, zero painel removido, zero mudança de cálculo/fonte de
dado/Supabase — as mesmas 10 funções de sempre, só reagrupadas.

## Responsividade

As 3 regiões usam o mesmo prefixo de chave (`vg_grid_*`) das regiões
antigas — reaproveita a regra responsiva **já existente** em `style.css`
(`[class*="st-key-vg_grid_"] [data-testid="stHorizontalBlock"]`: ≤900px,
ou ≤1200px com sidebar aberta, as colunas da região viram 100% de largura
e empilham). **Zero CSS novo.** Confirmado em `820_depois.png` (abaixo de
900px, tudo empilha corretamente).

## Bugs reais achados e corrigidos no processo

1. **Overlap hora×manchete em Destaques do Dia.** A coluna ficou mais
   estreita no novo agrupamento (par com Gráfico) e o split interno
   `st.columns([0.11, 0.89])` de `_painel_noticias_resumo` não cabia mais
   o formato `dd/mm HH:MM` nos 11% — sobrepunha o início da manchete.
   Corrigido empilhando hora+meta ABAIXO do botão da manchete (full
   width) em vez de ao lado — robusto a qualquer largura de coluna.
   Função local a `ui/visao_geral.py`, não compartilhada com NOTÍCIAS.
2. **Quebra de linha feia em Resultados da Watchlist a 1024px.** Split
   3-vias igual (0.34/0.33/0.33) deixou pouca largura pro componente
   compartilhado `_painel_proximos_watchlist` (não modificado por ser
   reusado) — "CONFIRMADO"/"ESTIMADO" quebravam pra linha própria,
   desconectados do ponto de status. Corrigido rebalanceando pra
   `[0.40, 0.30, 0.30]` (agenda precisa de mais largura que os outros
   dois, que são mais curtos em conteúdo).

## Validação

- Suíte completa `pytest`: **2250 passed**, sem regressão.
- Screenshots reais (Playwright, dados mockados realistas via
  `docs/evidencias/validacao-independente-home-mercado-20261106/harness_home.py`,
  reusado sem alteração) em 3 larguras — `1440_antes.png`/`1440_depois.png`,
  `1280_antes.png`/`1280_depois.png`, `1024_antes.png`/`1024_depois.png`
  — e uma 4ª em `820_depois.png` confirmando o wrap responsivo abaixo de
  900px.
- Altura total de página medida (scrollHeight real do container interno
  do Streamlit): 1440px 1918→1861px, 1280px 1969→1861px, 1024px
  1829→1663px. Redução modesta de altura total, mas o ganho real é a
  ELIMINAÇÃO do espaço vazio sob os painéis curtos (o problema relatado),
  não só menos scroll.

## Não validado

- Produção/Streamlit Cloud — só harness local.
- **As duas imagens de referência que a Rodrigo mencionou no pedido não
  chegaram no contexto desta sessão** — a reorganização foi fundamentada
  na descrição textual detalhada do pedido + medição real de altura, não
  nas imagens. Se o resultado não bater com o que ela tinha em mente,
  uma rodada de ajuste é esperada assim que ela puder compartilhá-las.
