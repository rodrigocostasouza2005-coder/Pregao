# Fase 6 — Interface, UX e consolidação do produto (2026-11-23)

Continuação de uma sessão anterior que perdeu o transcript (limite de
sessão) com trabalho parcial já salvo aqui (capturas de responsividade,
fluxo principal, DCF). Esta sessão revisou o que já existia antes de
recapturar/corrigir qualquer coisa.

## Os 3 pontos herdados da sessão anterior (confirmados por imagem, não por suposição)

1. **MACRO > Indicadores, eixo Y do IPCA sobreposto** — **FALSO ALARME
   hoje**: já foi corrigido no PR #332 (`c1d333c`), que é ancestral do
   HEAD desta branch (`git merge-base --is-ancestor c1d333c HEAD` →
   sim). As capturas `resp_macro_indicadores_*.png` desta pasta já são
   a evidência PÓS-fix (eixo "Mensal" na esquerda, "12 meses" na
   direita, sem sobreposição) — a sessão anterior só estava
   revalidando com a paleta nova, não havia bug novo pra corrigir.
   Nenhuma ação necessária.
2. **CALENDÁRIO, rótulo de status cortado pela borda da célula** —
   **BUG REAL, CONFIRMADO E CORRIGIDO nesta sessão**. Era um achado
   MENOR já registrado na auditoria 2026-11-17
   (`docs/evidencias/validacao-visual-real-20261117/LEIA.md`) e ainda
   não corrigido. Ver seção própria abaixo.
3. **MERCADO > Visão Geral em 390px** — sem bug novo encontrado.
   `responsivo_fase6_resultado.json` confirma `overflow: false` em
   todas as rotas/breakpoints testados (sem overflow horizontal de
   página). A tabela "MAIS NEGOCIADOS (VOLUME)" parece cortada na
   borda direita da tela no screenshot estático, mas o código
   (`ui/visao_geral.py:_painel_desempenho_tabela`) já envolve a tabela
   em `<div style='overflow-x:auto;'>` — é rolagem horizontal
   intencional (mesmo padrão usado em outras tabelas largas do app,
   ex. COMITÊ), não um corte real. Screenshot estático não mostra
   rolagem por natureza.

## Bug corrigido: rótulo de status cortado na célula do CALENDÁRIO

**Arquivo**: `ui/calendario_tab.py` (CSS apenas, zero mudança de
lógica/dado).

**Reprodução**: harness local sem login/rede
(`harness_calendario_fix_rotulo.py`, adaptado do harness da auditoria
2026-11-17, mesma técnica: mocka só
`calcular_calendario_cacheado`/`universo_calendario`/etc., chama
`render_calendario.__wrapped__` direto). `streamlit run` real +
Playwright real (não AppTest) — ver `calendario_rotulo_ANTES_1440.png`:
o texto "CONFIRMADO"/"ESTIMADO" da última linha de cada evento no grid
mensal aparece com a borda inferior da célula cruzando o meio das
letras.

**Causa raiz** (medida via `getBoundingClientRect`/`getComputedStyle`
real no Chromium, não suposição): o wrapper interno que o Streamlit
gera para cada `st.markdown` (classe `st-emotion-cache-*`, não-estável
entre builds) termina ~16-21px antes da altura real do conteúdo quando
o markdown tem 3+ `<div>`s empilhados dentro de uma célula
`st.container` que por sua vez é um item flex. Testado
exaustivamente: `height`/`min-height`/`max-height`/`flex-shrink`/
`flex-basis` com `!important` — inclusive setados via JS diretamente no
elemento, bypassando CSS por completo — **não mudam esse número**.
Não é um `height` CSS controlável; o conteúdo apenas transborda
visualmente (overflow:visible confirmado em toda a cadeia de
ancestrais) sem que a caixa do wrapper cresça. Não foi possível
identificar a causa exata dentro do motor de layout do
Streamlit/Emotion nesta sessão (ver histórico de investigação se
precisar continuar).

**Fix aplicado**: a única alavanca que respondeu normalmente a CSS foi
o `padding-bottom` da célula EXTERNA (`[class*="st-key-cal_cel_"]`,
que não sofre o mesmo problema) — compensação empírica, validada com
1 e com 4 eventos no mesmo dia (3 mostrados + "+1 evento(s)"), em
1440px e 390px (touch), via `getBoundingClientRect` real (não só
visual):
- Desktop/tablet (regra genérica): `padding-bottom` 0.55rem → 1.1rem
  (~2.6px de folga real).
- Mobile (`@media max-width:640px`): `padding-bottom` 0.3rem → 1.15rem
  (~3.4px de folga real).

**Validado**: `calendario_rotulo_DEPOIS_1440.png` e
`calendario_rotulo_DEPOIS_390.png` (mesmo harness, contra o arquivo já
corrigido) — texto totalmente legível, sem cruzar a borda, em nenhum
dos dois breakpoints, com 1 e com 4 eventos no dia.

**Testes**: `pytest tests/ -k calendario` → 61 passed (sem regressão;
mudança é só CSS). `pytest tests/test_smoke_todas_abas.py` → 11 passed.

**Limitação honesta**: a causa raiz dentro do Streamlit/Emotion não foi
isolada (não é um bug de lógica do PREGÃO, parece ser uma interação de
layout do próprio framework com HTML multi-linha dentro de
`st.container` flex) — o fix é uma compensação empírica validada
numérica e visualmente em 2 cenários (1 e 4 eventos) e 2 breakpoints,
não uma correção da causa raiz. Se o Streamlit mudar a estrutura
interna desses wrappers em uma atualização futura, vale re-validar.

## Achado NOVO (fora do escopo desta correção, registrado para o Rodrigo decidir)

**Sidebar (WATCHLIST) sobrepõe TODO o conteúdo principal em telas
touch de ~1024px** (tablet, ex. iPad), em QUALQUER aba — não é
específico do CALENDÁRIO, reproduzido em MERCADO e MACRO também (ver
`resp_mercado_visaogeral_1024.png`, `resp_macro_indicadores_1024.png`,
`resp_calendario_corporativo_1024.png` nesta mesma pasta). Ao abrir
com touch habilitado a ~1024px de largura, a sidebar nativa do
Streamlit renderiza como **overlay fixo** (`position:fixed`,
`style.css` linha ~412-417, fix intencional de 2026-11-01 pra permitir
fechar a sidebar em iPad) e **começa ABERTA** (herdado de
`initial_sidebar_state="auto"`, `app.py`, que decide aberto/fechado só
pela LARGURA da tela, sem saber se é touch) — a combinação faz a
sidebar cobrir quase toda a área útil no primeiro carregamento, e o
usuário só descobre o conteúdo se encontrar e tocar a seta "«" no
canto. Dois fixes anteriores corretos (auto-collapse por largura +
overlay fixo pra touch) se combinam mal exatamente na faixa
tablet-touch (~768-1366px com touch).

**Por que não foi corrigido nesta sessão**: `app.py` e `style.css` não
estão na lista de arquivos desta frente (Fase 6) no mapa de ownership
da missão master, e um fix robusto provavelmente exige decidir o
estado inicial da sidebar considerando touch (não só largura) — o que
tipicamente pede JS (Streamlit não expõe touch/pointer capability pro
Python em `set_page_config`) ou uma mudança de CSS que precisa de
validação cuidadosa pra não quebrar o comportamento já correto em
desktop e em celular (que hoje funciona bem). Registrado aqui pra
quem tiver ownership de `app.py`/`style.css` avaliar.

## Fluxo principal (mercado → empresa → fundamentos → notícias →
research → comitê → cenários → valuation)

Revisado via `fluxo_*.png` (1440px, app real, sem mock). Nenhuma
quebra funcional encontrada nas páginas visitadas — COMITÊ mostra
estado vazio honesto (Supabase fora do ar neste ambiente local, sem
dado fabricado), VALUATION > Parecer do Comitê mostra tabela de
múltiplos limpa e legível. Research (feed/casas) e Análises
(empresas/fundamentos/perfil) sem problema visual aparente nas
capturas disponíveis.

## Streamlit × Next.js (`web/`)

- **Terminal principal de fato hoje: Streamlit** (app.py + ~20
  abas). `web/` é deliberadamente um espelho **somente leitura**, mais
  leve, cobrindo um subconjunto de telas (mercado, macro, ativo,
  busca, agenda, cvm, empresas, inteligência, morning-call, notícias,
  research) — por design, documentado no próprio `web/README.md`
  ("este terminal lê o que [Python/coletores/jobs] produzem"). Não
  cobre COMITÊ (execução), VALUATION/DCF, RADAR, CARTEIRA
  RECOMENDADA, SETORES, TOP MERCADO — essas permanecem exclusivas do
  Streamlit.
- Sem duplicidade de plataforma "por acidente": há um mecanismo de
  contrato (`web/contratos/*.json`, gerado por
  `scripts/exportar_contratos_web.py`) + teste de paridade
  (`testes/paridade.test.ts`, 20 casos reais gerados pelo Python) que
  garante que a classificação editorial de notícias em TypeScript bate
  com o Python. Isso É o jeito certo de evitar deriva entre as duas
  implementações.
- **Risco de manutenção identificado** (não é bug, é recomendação):
  a regra de variação %/formatação de preço de Mercado/Macro/Ativo
  está **reimplementada em TypeScript** (`web/README.md`: "mesma regra
  de variação de `data/prices.py`") só por convenção de comentário —
  ao contrário da classificação editorial de notícias, **não há teste
  de paridade automatizado** cobrindo essa regra especificamente. Se
  `data/prices.py` mudar no futuro, nada quebra automaticamente no
  lado web até alguém notar visualmente a divergência. Recomendação:
  estender o mesmo padrão de `casos_editoriais.json` +
  `paridade.test.ts` pra cobrir variação%/formatação de preço, não
  precisa ser feito com urgência (nenhuma divergência observada hoje,
  os 2 lados fazem a mesma coisa na prática).
- Testes `web/` rodados nesta sessão: `npm install` + `npm test`
  (vitest) → **77 passed** (9 arquivos), sem regressão.

## Validação de navegador real

Playwright real disponível neste ambiente (`.venv` compartilhado com
PREGÃO principal, versão 1.63.0) e usado de fato: harness Streamlit
local (`streamlit run` real, sem mock de renderização, só dado mocado)
+ Chromium real via `playwright.sync_api`, screenshots reais,
`getBoundingClientRect`/`getComputedStyle` reais pra medir o bug antes
de corrigir e confirmar depois — não só AppTest, não só leitura de
código. Único ponto não validado contra o APP REAL completo (com login
Google): o mecanismo de bypass de login da sessão anterior
(`sitecustomize.py`, descrito como "fora do repo") não foi recuperado
(sessão anterior perdeu o transcript); esta sessão usou harnesses
isolados chamando os componentes de UI diretamente (mesmo padrão já
estabelecido no projeto para RADAR X e para a auditoria 2026-11-17),
o que é suficiente pra validar CSS/layout mas não substitui uma
passada completa pelo app real logado — as capturas `resp_*`/`fluxo_*`
já existentes (geradas pela sessão anterior contra o app real, via o
bypass que se perdeu) continuam sendo a única evidência "app real"
desta missão.
