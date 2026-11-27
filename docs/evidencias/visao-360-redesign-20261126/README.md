# Validação visual real — ANÁLISES > Visão 360 (redesign 2026-11-26)

Evidência da missão `visao-360-redesign-20261126` (reformulação completa da
tela de análise individual de um ativo, `ui/visao_360_tab.py`).

## Como foi feito

`AppTest` do Streamlit **não** executa CSS nem layout — overflow, grade que
não reflui e sobreposição só aparecem num navegador real (lição já
registrada em `docs/evidencias/validacao-visual-real-20261117`). Então:

1. `harness_v360.py` — sobe a tela de verdade num Streamlit local, sem
   login/credenciais, com `style.css` + as variáveis do tema AMBAR
   exatamente como `app.py` monta, e com **todas** as fontes de rede/Supabase
   mockadas com dado realista (cotação, múltiplos, perfil de research,
   consolidado do Comitê com 5 pareceres, comparativo de 3 casas, notícias).
   Inclui a fita de ticker da rota real (`st.container(key="v360_fita_ticker")`).

   ```
   streamlit run docs/evidencias/visao-360-redesign-20261126/harness_v360.py --server.port 8599
   ```

2. `captura_v360.py` — Playwright real (Chromium) em 3 larguras:
   **1920×1200 (desktop)**, **1440×900 (notebook)** e **1024×900 (tablet
   largo — o mesmo breakpoint já estabelecido no projeto)**. Mede, em cada
   largura e em cada seção do andar de aprofundamento:
   `document.body.scrollWidth` / `documentElement.scrollWidth` contra o
   viewport (scroll horizontal da página = reprovação) e **todo elemento com
   `right > viewport` ou `left < 0`**. Falha com `exit 1` se achar qualquer
   um. Screenshots de página inteira ficam neste diretório; as medidas em
   `medidas.json`.

3. `probe_overlap.py` — sonda pontual de geometria usada para achar a causa
   raiz da sobreposição descrita abaixo (mantida porque o achado vale para
   qualquer tela nova do app).

## Resultado final

`=== OK: nenhuma largura com overflow horizontal ou elemento fora do viewport ===`

Screenshots conferidas uma a uma: cabeçalho com preço dominante, veredito do
Comitê com recomendação e confiança visualmente separadas, perfil executivo
em 2×2, indicadores por categoria, valuation com cenários bear/base/bull, e
as 5 seções do aprofundamento (pareceres, research, evidências, notícias,
histórico) — nas 3 larguras, sem corte de texto, sobreposição ou coluna
desproporcional.

## Achados reais corrigidos nesta rodada (todos medidos, nenhum "no olho")

1. **Sobreposição de 16px entre bloco de HTML e o widget seguinte.** O
   Streamlit aplica `margin-bottom: -16px` em todo
   `[data-testid="stMarkdownContainer"]` para cancelar a margem de 1rem de um
   `<p>` de markdown. Quando o bloco é HTML cru e termina numa `<div>` (sem
   margem), sobra um `-16px` real: medido, o `stMarkdown` do cabeçalho tinha
   **83px de altura para 99px de conteúdo**, e a faixa de ações rápidas subia
   e cobria a linha de status da cotação. Corrigido devolvendo `1rem` apenas
   quando uma classe do design system é o último filho do container (ver
   `style.css`, seção "COMPENSAÇÃO DO -1rem DO STREAMLIT") — nenhum bloco
   antigo do app muda de espaçamento.
2. **Rótulos gigantes no perfil e nos pareceres.** `st.markdown("**texto**")`
   é a única forma de conteúdo que renderiza no tamanho PADRÃO do Streamlit;
   cada pergunta do perfil saía com um título enorme no meio de texto de
   0.78rem. Migrados para `design_system.subtitulo()`.
3. **Valor composto cortado a 1024px.** "MÁX/MÍN DIA" e "52 SEMANAS" perdiam
   o segundo número com reticências — largura mínima da métrica subiu para
   168px e a *nota* da métrica passou a quebrar linha (o valor continua sem
   quebra, de propósito).
4. **Colunas numéricas encostando na coluna de texto** (`R$ 52,002026-11-18`)
   — `.ds-tabela` ganhou respiro nos dois lados de cada célula.
5. **Botões de ação rápida** esticados a 1920px e com rótulo cortado a
   1024px — cada coluna passou a encolher para o tamanho do próprio botão,
   com quebra de linha.

## Limites desta validação (declarados)

- O harness usa **dados mockados**, não produção: o worktree desta sessão não
  tem `.streamlit/secrets.toml` (Supabase/Groq) nem login Google. O que está
  validado é **layout/CSS/responsividade e a composição da tela** com o shape
  real de cada fonte — não a latência, nem o conteúdo vindo do banco real.
- Dois defeitos apareceram na 1ª captura e eram **do mock, não da tela**:
  notícia sem as chaves `score`/`regras` (KeyError dentro do `@st.fragment` de
  `ui/news_tab.py`) e selo `"NAO CONFIRMADA"` sem acento (não casava com
  `_SELO_ABREV`). Os mocks foram corrigidos para o shape real de
  `data/news.py`.
