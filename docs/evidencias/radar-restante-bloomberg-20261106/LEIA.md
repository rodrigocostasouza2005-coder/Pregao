# RADAR — telas restantes (Alertas/Oportunidades/Acompanhamento/Preferências) — evidências

Missão: aplicar o passe visual "Bloomberg âmbar" (2026-11-06) nas 4 subabas de RADAR que
ainda não tinham sido tocadas hoje (Carteiras Recomendadas foi a PR #265, Valuation foi a
PR #269 — ambas no mesmo arquivo `ui/radar_tab.py`, fora do escopo desta missão).

## O que foi investigado antes de editar

`ui/radar_tab.py` já tinha, desde revisões de outubro/2026 (bem antes da fundação
`ui/design_system.py` de hoje), seu próprio design denso "terminal Bloomberg" completo:
classes `.rq-*`/`.radar-*`/`.acomp-*` já usam `var(--borda)`/`var(--alta)`/`var(--baixa)`,
`tabular-nums`, bordas finas como divisor, tabelas densas, chips de estado coloridos — ver
`_CSS_RADAR` no topo do arquivo. As 4 funções desta missão (`render_radar_alertas`,
`render_radar_oportunidades`, `render_radar_acompanhamento`, `render_preferencias`) são,
em si, orquestração fina: quase todo o HTML denso vem de funções auxiliares (`_bloco_alertas`,
`_secao_risco`, `_tabela_alertas_html` etc.) que **não foram tocadas** — são compartilhadas
com `render_valuation`/`render_teses` (fora do escopo) e já seguem o mesmo padrão visual.
Por isso o diff é deliberadamente pequeno: o trabalho real aqui foi (1) consistência de
rótulos dentro do que as 4 funções realmente controlam e (2) um bug visual real encontrado
na validação.

## Mudanças

- `render_radar_oportunidades`: rótulos dos `st.expander` normalizados para CAIXA ALTA
  (`"PRÓXIMOS CATALISADORES"`, `"RESEARCH COM EVIDÊNCIAS"`) — mesma convenção já usada nos
  títulos irmãos (`"O QUE MUDOU?"`, `"ONDE VALE INVESTIGAR"`) e no expander idêntico de
  `render_teses` (`"RESEARCH COM EVIDÊNCIAS"`, reuso da mesma seção).
- `render_radar_acompanhamento`: rótulo do expander normalizado
  (`"O QUE PODE DAR ERRADO — RISCO DA CARTEIRA"`, era com case misto).
- `render_preferencias`: adicionado `st.caption` de destino (`Destino: {email} · ...`),
  paridade com o mesmo toggle em `ui/morning_call_tab.py:render_preferencias`, que já tinha
  essa linha e este não tinha.
- **Bug real encontrado e corrigido** em `render_radar_oportunidades`: o aviso
  "Sinais para investigar, não recomendações" (`_AVISO_SINAL`) renderizava sobreposto aos
  pills de janela/escopo logo abaixo (texto ilegível, pills por cima) — mesma classe de bug
  já documentada e corrigida 2x neste arquivo (`.radar-stub`, `.valrad-nota`): o wrapper que
  o Streamlit gera ao redor de HTML customizado mede uma altura menor que o conteúdo real
  quando o texto quebra em 2 linhas. Fix: mesma técnica (respiro no elemento seguinte via
  seletor CSS escopado a um marcador próprio, `.radar-opor-aviso`), sem tocar em `.rq-nota`
  compartilhada nem em `_AVISO_SINAL` (usado também, sem este problema, no fim de
  `render_radar_alertas` — lá não há elemento seguinte pra sobrepor). Ver
  `desktop-1440-oportunidades.png` (depois do fix, sem sobreposição).

## Validação

- `pytest` completo: **2244 passed**, 0 falhas, 0 skips novos.
- Visual real (Playwright, não AppTest) via harness local sem login/Supabase
  (`harness_radar_restante.py`, dado mockado em `data/radar.py`, `data/radar_quedas.py`,
  `data/posicoes.py` — mesmo padrão de `docs/evidencias/responsividade-bloomberg-20261106/`):
  8 screenshots, desktop 1440px e iPad 1024px com `has_touch=True` (RADAR teve bug real de
  toque em iPad corrigido hoje, PR #270, em `_bloco_carteiras_detalhadas`/`style.css`) × 4
  telas. `style.css` tem diff zero contra `origin/main` nesta branch — o fix de toque do
  PR #270 não foi tocado nem revertido.
- Limitação: dado mockado, sem Supabase/Yahoo reais; validação em produção (Streamlit Cloud)
  depende de deploy, não feita aqui.

## Arquivos

- `harness_radar_restante.py` — harness isolado das 4 rotas (mock de dado).
- `shot.py` — script Playwright que gera os 8 PNGs (rode `streamlit run
  harness_radar_restante.py --server.port 8733` antes).
- `desktop-1440-*.png` / `ipad-1024-touch-*.png` — screenshots finais, 4 telas × 2 breakpoints.
