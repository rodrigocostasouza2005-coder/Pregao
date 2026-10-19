# MORNING CALL (web) — leitura estruturada em vez de bloco monoespaçado (2026-10-19)

Missão de redesign + performance (Bloomberg-like), prioridade 3.5. Capturas
geradas com harness local (Streamlit + Playwright), texto de exemplo com a
MESMA estrutura real de `jobs/morning_call.py:montar_morning_call` — dados
sintéticos (sem rede/Supabase neste harness), não é captura de produção.

- `antes_desktop.png` — comportamento anterior: `ui/morning_call_tab.py:_exibir_texto`
  jogava o texto inteiro (o mesmo texto plano do e-mail) num único
  `<div style="white-space:pre-wrap">`, sem nenhuma hierarquia — exatamente o
  "bloco monoespaçado" do screenshot do Rodrigo.
- `depois_desktop.png` / `depois_mobile.png` — `_exibir_edicao_estruturada`
  (nova): mesmo texto, mesmos números/fontes/links, agora com cabeçalho
  (título/subtítulo/metadados), seções com título destacado, bullets de
  direção (alta/queda) com cor semântica, `[INTERPRETAÇÃO]` com selo próprio
  e tratamento itálico (nunca misturado com fato), manchetes com link viram
  "abrir ↗" (sem URL crua no texto), linha de contexto sem "- " (ex. intro da
  AGENDA DE HOJE) sem marcador de bullet. Expander "Ver texto original" no
  fim preserva o texto puro pra conferência, sem esconder nada.

Nenhum conteúdo, número, fonte ou link foi alterado — só a apresentação.
Usado em `render_edicao_atual` (edição publicada + prévia ao vivo) e
`render_historico` (cada edição do histórico).

Bug real encontrado e corrigido durante a própria validação: a primeira
versão emitia 1 `st.markdown()` por seção, o que fazia `.mc-secao-titulo:
first-child` (CSS) zerar a margem superior de TODAS as seções (cada uma era
"primeira filha" da própria div), não só da primeira de verdade — sem
respiro visual entre seções. Corrigido emitindo o corpo inteiro num único
`st.markdown()`.
