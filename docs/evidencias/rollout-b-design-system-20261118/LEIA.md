# Evidência visual — missão "rollout B" do design system (2026-11-18)

Contexto: 9 dos 10 arquivos listados em
`docs/continuidade-pregao-20261114.md` ("10 arquivos de UI sem nenhum uso
do design system") foram reauditados nesta missão (`saude_dados_tab.py`
excluído de propósito — regra 8 do `CLAUDE.md`, frente isolada).

Achado: 8 dos 9 já não tinham nada a migrar (5 confirmados "limpos" numa
auditoria anterior, 2026-11-14, com a razão documentada no próprio
docstring de cada arquivo; `calendario_tab.py`/`dcf_operacional.py` já
tinham sido migrados em missões posteriores, 2026-11-06/17). O único
código real mudado foi `ui/radar_tab.py:_classe_var`, que reimplementava
o ternário alta/baixa localmente em vez de reaproveitar
`design_system.classe_sinal` — corrigido sem alterar nenhum texto/classe
exibida.

`harness_radar_acompanhamento.py`: Playwright real (Chromium, via
`streamlit run` + `docs/evidencias/validacao-visual-real-20261117/shot.py`,
mesmo padrão já estabelecido no projeto), exercitando de propósito
`render_radar_acompanhamento` → `_secao_risco` → `_linha_posicao_gerenciar`
(o código mudado) com 1 posição de lucro positivo e 1 negativo mockadas.

`acompanhamento_1440.png`: PETR4 (+12,50%) em verde (`rq-alta`), VALE3
(-6,30%) em vermelho (`rq-baixa`) — confirma visualmente que a migração
pra `classe_sinal` manteve a cor/alinhamento idênticos ao comportamento
anterior (mesma conclusão que os testes automatizados de
`tests/test_radar_acompanhamento_redesign_ui.py`, que já passavam
afirmando essas mesmas classes literais).

Os outros 8 arquivos (`busca.py`, `navegacao.py`, `paineis.py`,
`sistema_tab.py`, `top_mercado_tab.py`, `workspace.py`,
`calendario_tab.py`, `dcf_operacional.py`) não tiveram nenhuma linha de
código visual alterada nesta missão — não há "antes/depois" visual pra
capturar (nenhuma diferença esperada). Harnesses visuais já existentes
pra algumas dessas telas (`docs/evidencias/experiencia-design-system-20261111/`,
`docs/evidencias/validacao-visual-real-20261117/`) seguem válidos/
reutilizáveis caso uma sessão futura precise reconfirmar.
