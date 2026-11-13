# Validação visual — Agente A (2026-11-12/13)

Missão: redesign estrutural de RADAR › Alertas/Carteiras Recomendadas/
Acompanhamento + ANÁLISES › Valuation/Teses, mais a Central de
Inteligências nova. Harnesses no mesmo padrão de
`docs/evidencias/agente-d-redesign-estrutural-20261112/` (chamam os
`render_*` reais com dado mockado representativo, sem login/Supabase
real). `streamlit run harness_*.py -- <aba>`, screenshot via Playwright
real (Chromium) em desktop (1440px) e iPad (1024px).

## RADAR › Alertas (`render_radar_alertas`)

`antes_alertas_{1440,1024}.png` vs `depois_alertas_{1440,1024}.png`:
**antes**, a tela abria com o título seguido IMEDIATAMENTE do parágrafo
de metodologia ("Alerta quando um ativo..."), e só depois a tabela de
alertas — nenhum número de resumo visível antes de ler o parágrafo
inteiro. **Depois**: uma faixa `RESUMO` logo abaixo do título mostra
"1 abaixo do gatilho agora · 1 em atenção agora · 1 alerta(s) nos
últimos 7 dias · 3 ativo(s) monitorado(s)" (reusa dado já lido por
`_bloco_alertas`/`_bloco_monitorados`, zero chamada nova) — a metodologia
desce pra um expander fechado ("Metodologia do Radar de Quedas") no fim
da tela.

## RADAR › Carteiras Recomendadas (`render_radar_carteiras`)

`depois_carteiras_{1440,1024}.png`: a legenda "ATUALIZADA/DESATUALIZADA/
INDISPONÍVEL" (texto de referência, não dado) virou um expander fechado
logo após a tabela COBERTURA, em vez de texto sempre visível entre a
cobertura e COMPARAR CARTEIRAS.

## RADAR › Acompanhamento (`render_radar_acompanhamento`)

`depois_acompanhamento_{1440,1024}.png`: "O QUE PODE DAR ERRADO — RISCO
DA CARTEIRA" (ação, pessoal) agora vem ANTES de "ALERTAS ANTERIORES"
(referência histórica, 90 dias) — ordem antiga era cronológica de
implementação, não de importância pra decisão.

## ANÁLISES › Valuation (`render_valuation`)

`depois_valuation_{1440,1024}.png`: a legenda de proveniência do dado
(selos FATO/CÁLCULO INTERNO + parágrafo "isto não é preço-alvo...") virou
expander fechado ("Como ler esta tabela") logo abaixo do título, antes
dos pills de escopo.

## ANÁLISES › Teses (`render_teses`)

`antes_teses_{1440,1024}.png` vs `depois_teses_{1440,1024}.png`:
**antes**, "MINHA TESE" (conteúdo principal da subaba) era 1 de 3
`st.expander` sequenciais, no MESMO nível visual que "RESEARCH COM
EVIDÊNCIAS"/"COPILOTO DE RESEARCH" (seções de apoio). **Depois**: Minha
Tese é conteúdo direto, sem expander; as 2 seções de apoio viram 2
colunas lado a lado (`radar_grid_teses`, mesmo mecanismo responsivo já
validado em RADAR › Oportunidades — stack automático abaixo de 900px via
regra CSS já existente em `style.css`, prefixo `st-key-radar_grid_`).

## COORDENADOR › Central de Inteligências (nova, `ui/central_inteligencias_tab.py`)

`depois_central_{1440,1024}.png`: console novo, read-only, cruzando
`registro.listar_especialistas()` + `persistencia.metricas_especialistas()`
(tabela ESPECIALISTAS DO COMITÊ: agente/função/motor/status/execuções/
taxa de sucesso/tempo médio/última execução/último erro) com
`persistencia.listar_analises_recentes()` (HISTÓRICO DE ANÁLISES,
expansível por análise, mostrando resumo/fontes por especialista quando
persistidos) e `data/ia_cache.py:estatisticas_modelos()` (nova, aditiva,
read-only — RESUMOS GERADOS POR IA, por origem/modelo real). Achado real
nesta própria validação: a 1ª versão da tabela de especialistas não
limitava a largura da coluná FUNÇÃO (texto livre, >150 caracteres) e
empurrava MOTOR/STATUS/EXECUÇÕES pra fora da viewport, só visíveis
rolando horizontalmente mesmo em 1440px — corrigido (`white-space:normal`
+ `max-width` na coluna), confirmado nos screenshots finais com as 9
colunas visíveis sem rolagem em 1440px (1024px ainda precisa de rolagem
horizontal pra ver ÚLTIMA EXECUÇÃO/ÚLTIMO ERRO — mesmo padrão de
degradação já usado por `.coord-tabela-wrap`/`.rq-scroll` no resto do
app, não é regressão).

## Suíte de testes

`python -m pytest tests/ -q` ao final (ver PR) — nenhuma regressão
introduzida por esta frente. 2 falhas pré-existentes confirmadas (via
`git stash` revertendo as mudanças desta missão e rodando a MESMA
combinação de arquivos) e documentadas na PR: flakiness de ordem/estado
compartilhado do `AppTest` em `test_radar_acompanhamento_redesign_ui.py`
e `test_pregao2_modulos.py::test_appteste_morning_call_historico_e_preferencias`
— já existiam em `origin/main`, nenhuma delas tocada por esta missão.

## Fora de escopo desta validação visual

MACRO, SETORES, CVM, TOP MERCADO, SISTEMA, USUÁRIOS, NOTÍCIAS › Empresas,
MORNING CALL: revisados no código (ver PR) mas sem mudança estrutural
aplicada nesta frente — já tinham hierarquia razoável (faixas de métrica,
grades, tabs) de missões anteriores; sem screenshot novo.
