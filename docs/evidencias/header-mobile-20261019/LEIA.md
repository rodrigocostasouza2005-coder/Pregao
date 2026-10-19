# CABEÇALHO (camada1_header) — espaço vertical excessivo no celular (2026-10-19)

Missão de redesign + performance, prioridade 2 ("Cabeçalho global, busca, ticker
de mercado"). Partiu de uma captura REAL já existente de hoje
(`docs/evidencias/pregao-2-navegacao-20261019/mobile_noticias_empresas.png`,
harness oficial do PR #82) — não foi um problema inventado: antes de qualquer
conteúdo aparecer, o usuário via CTRL K (sem sentido em touch) + 3 botões de
ação cada um ocupando a LARGURA INTEIRA da tela (4 faixas cheias), empurrando
tudo pra baixo.

Reproduzido fielmente num harness isolado com o MESMO bloco de código de
`app.py:413-468` (mesmo `st.columns`, mesmas chaves, mesmo CSS real do
projeto) — sem precisar de login.

**Causa raiz (confirmada por inspeção real do DOM, `getComputedStyle`, não por
suposição):** 2 fatores, não 1 —
1. os 3 botões de ação (`↗`/`▣`/`+`) usam `width="stretch"`;
2. nesta largura o Streamlit comuta `stHorizontalBlock` pra
   `flex-direction: column`, e `align-items: stretch` (padrão) vira largura
   total no eixo cruzado (que em `column-direction` é a LARGURA) — corrigir só
   o botão não bastava, a coluna ao redor continuava esticando.

**Correção** (só CSS, dentro do `@media (max-width: 640px)` já existente em
`style.css`, nenhuma mudança de comportamento/Python):
- `CTRL K` escondido no celular (é dica de atalho de teclado físico — sem
  sentido em touch; o atalho em si, via `st.iframe`+JS, continua funcionando
  normalmente para quem tiver teclado bluetooth/dobrável).
- As 3 colunas dos botões de ação ganham `align-self: flex-start` (não
  esticam no eixo cruzado) + os botões ganham largura real (`min-content`) —
  cabem lado a lado numa única linha compacta.

`antes_mobile.png` / `depois_mobile.png` / `depois_desktop.png` — Playwright,
harness isolado reproduzindo o código real. Desktop confirmado sem mudança
(regra só dispara ≤640px). 982 testes passando (mudança é pura CSS, nenhum
teste de Python tocado).
