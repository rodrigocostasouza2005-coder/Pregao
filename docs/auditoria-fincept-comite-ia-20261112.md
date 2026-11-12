# Auditoria do Fincept Terminal — lógica de agentes de IA do Comitê de Investimentos

Data: 2026-11-12 · Agente: FINCEPT-C · Branch: `feat/fincept-comite-ia-20261112` (a partir de `origin/main` @ `36dda39`)

Escopo desta auditoria (distinto das auditorias em paralelo #289 coletores, #290 arquitetura geral, #291 consolidação): como o Fincept Terminal implementa agentes de IA/pesquisa/análise financeira automatizada, comparado ponto a ponto com o Comitê de Investimentos real do Pregão (`data/coordenador_central/*`, `jobs/coordenador.py`, `jobs/comite_noturno.py`).

**Nota de licença (AGPL-3.0-or-later):** nenhum trecho de código do Fincept foi copiado, adaptado ou colado neste repositório. O clone usado para a auditoria (`git clone --depth 1`) ficou inteiramente fora do worktree do Pregão, em `%TEMP%/.../scratchpad/fincept`, e não foi referenciado por nenhum import ou arquivo deste repositório. Tudo abaixo é descrição de arquitetura/conceito (reimplementação independente), nunca transcrição de implementação.

## Metodologia

Clone raso de `github.com/Fincept-Corporation/FinceptTerminal` (branch default). Leitura direta de:
- `fincept-qt/scripts/agents/finagent_core/` — `core_agent.py`, `super_agent.py`, `modules/output_models.py`, `modules/workflow_module.py`, `agentic/reflector.py`, `configs/*.json` (11+ agentes analistas macro/setoriais).
- `fincept-qt/scripts/agents/deepagents/` — `agent.py`, `subagents.py`, `orchestrator.py`.
- `fincept-qt/scripts/agents/TraderInvestorsAgent/configs/agent_definitions.json` — 11 agentes "persona de investidor" (Buffett, Graham, Lynch, Munger, Klarman, Marks, Greenblatt, Einhorn, Miller, Eveillard, Whitman).
- `fincept-qt/scripts/agents/{EconomicAgents,GeopoliticsAgents}/configs/agent_definitions.json`.
- `fincept-qt/src/storage/sqlite/migrations/v003_data_mcp_agents.cpp`, `v052_coding_agents.cpp` (schema de persistência, só `CREATE TABLE`).

Achado de contexto (compartilhado com a auditoria #290): o Fincept pivotou pra um desktop nativo C++20/Qt6; a camada de agentes de IA é Python (`fincept-qt/scripts/agents/`), separada do core C++, chamada via subprocesso/MCP. A comparação abaixo é "padrão de agente" contra "padrão de agente", não stack contra stack.

## 1. Como o Fincept estrutura agentes de IA

| Aspecto | Fincept Terminal | Observação |
|---|---|---|
| **Unidade de agente** | `CoreAgent` único e configurável via dict (`finagent_core/core_agent.py:16-116`) — model/instructions/tools/memory/knowledge/reasoning entram por config, nunca uma classe nova por agente | Mais de 20 "agentes" no catálogo são, na prática, o MESMO runtime + um JSON de config diferente (`configs/*.json`, `TraderInvestorsAgent/configs/agent_definitions.json`) |
| **Orquestração multi-agente** | `CoreAgent.run_team()`/`TeamModule` (times com 1 coordinator model) e `CoreAgent.run_workflow()`/`WorkflowModule` (passos sequenciais) — primitivas genéricas de um framework de terceiros ("Agno") | Não há fan-out paralelo nativo com reconciliação automática — quem monta um "comitê" precisa compor `team_config["agents"]` manualmente |
| **Roteamento** | `SuperAgent` (`super_agent.py`) classifica a intenção da pergunta do usuário por palavra-chave (`QueryIntent.PORTFOLIO`, `GEOPOLITICS`, etc., linhas 86-108) e escolhe 1 agente/config pra responder | É um ROTEADOR (escolhe 1 especialista), não um comitê que aciona vários e cruza respostas |
| **"Deep agents"** | 1 agente pai delega a subagentes (`deepagents/subagents.py`): `research`, `data-analyst`, `trading`, cada um com `system_prompt` próprio, dentro da MESMA thread de raciocínio (`deepagents/orchestrator.py`) | A reconciliação de subagentes que discordam é implícita — fica a cargo do LLM pai sintetizar, sem checagem determinística de código |
| **Autocrítica de passo** | `Reflector` (`agentic/reflector.py:1-100`) — padrão Reflexion (Shinn et al. 2023): 1 chamada de LLM crítica decide `continue/replan/question/done` após cada passo de UM agente | Controla o loop de UM agente sobre seus próprios passos; não arbitra entre dois agentes com vereditos opostos |
| **"Casas de research"/personas** | 11 agentes-persona de investidor (`TraderInvestorsAgent/configs/agent_definitions.json`: Buffett, Graham, Lynch, Munger, Klarman, Marks, Greenblatt, Einhorn, Miller, Eveillard, Whitman), cada um com `scoring_weights` e framework de prompt próprio | Mais perto do que seria "comparação entre casas" — mas **nenhum código localizado roda os 11 e agrega/compara vereditos**; cada persona é chamada isoladamente (via `SuperAgent` ou diretamente), a comparação entre personas fica a cargo do usuário lendo múltiplas respostas |
| **Saída estruturada** | Pydantic (`modules/output_models.py:74-91`): `TradeSignal.confidence: float = Field(..., ge=0, le=1)` — número de probabilidade bruto, sem calibração declarada | Contraste direto com a regra explícita do Rodrigo pro Pregão ("confiança categórica, NUNCA número de probabilidade sem calibração") |
| **Cenários otimista/base/pessimista** | Não encontrado como funcionalidade estruturada. Existe só `Sentiment` (enum `VERY_BEARISH..VERY_BULLISH`, `output_models.py:59-65`) — uma classificação de 1 eixo, não 3 cenários de valuation com premissas numéricas distintas | O Pregão já tem isso — DCF em 3 cenários explícitos (ver seção 2) — Fincept não tem equivalente |
| **Divergência entre fontes/agentes** | Busca por `conflict/disagree/consensus/debate/reconcile/vote/weight` nos módulos de agente retornou só: (a) palavras-chave de classificação de intenção (`"conflict"` como sinônimo de guerra/geopolítica), (b) `"weight"`/`"overweight"` em heurística de rebalanceamento de portfólio, (c) instrução de PROMPT pedindo ao modelo pra "não escurecer o conflito em prosa" dentro de UM parecer (ver próxima linha) | **Nenhum mecanismo de código (determinístico ou por LLM) encontrado que compare vereditos de 2+ agentes/personas e sinalize divergência real.** Isso é o gap mais relevante pra esta missão — ver seção 3 |
| **Anti-contradição dentro de 1 parecer** | O prompt do Warren Buffett Agent tem uma seção "DO NOT" explícita: *"Combine bullish signal with < 50% margin of safety and hide the conflict in prose."* (`agent_definitions.json`, dentro de `instructions`) | Boa prática de PROMPT (força o próprio modelo a admitir quando seus critérios internos se contradizem) — mas é auto-checagem de 1 agente sobre si mesmo, não cross-check entre agentes |
| **Persistência** | SQLite local (`v003_data_mcp_agents.cpp`: `mcp_servers`, `mcp_tools`, `mcp_tool_usage_logs`, `agent_configs`; `v052_coding_agents.cpp`: `coding_agent_runs/events/schedules`) | Schema é sobre conexões MCP/execuções de agente de CÓDIGO, não sobre histórico de análises financeiras com evidência/confiança por ticker — sem equivalente ao `coordenador_analises`/`coordenador_execucoes` do Pregão |

**Conclusão da seção**: o Fincept tem uma biblioteca grande e bem organizada de *personas* de LLM (boas pra inspirar PROMPTS individuais — a seção "DO NOT" do Buffett Agent é um padrão de prompting genuinamente bom), mas nenhuma camada de **consolidação determinística e auditável** entre vereditos de agentes diferentes. A responsabilidade de notar "o Agente X disse compra, o Agente Y disse venda" fica com o usuário humano lendo as respostas, nunca com o sistema.

## 2. Como o Comitê do Pregão funciona hoje (antes desta auditoria)

Pipeline real, 100% determinístico na camada de consolidação (`data/coordenador_central/consolidacao.py:1-6`: *"ZERO chamada de IA nova aqui"*):

1. **Executor com isolamento real** (`executor.py`): cada especialista roda em thread própria, com timeout de 30s via `ThreadPoolExecutor`, nunca propaga exceção pro chamador (`executar_especialista`/`executar_varios`).
2. **Registro de especialistas** (`registro.py`): 9 especialistas catalogados (`comparador`, `memoria_research`, `analise_ticker`, `noticias`, `calendario`, `catalisadores`, `resultados_corporativos`, `model_builder`, `valuation_reviewer`, `radar_x`), cada um envolvendo função JÁ existente, nunca reescrita.
3. **DCF em 3 cenários explícitos** (`dcf.py:12-134`): `pessimista`/`base`/`otimista`, Gordon Growth no valor terminal, nunca inventa premissa (recusa calcular sem WACC/crescimento/dívida/ações explícitos) — isto é exatamente o "cenário otimista/base/pessimista" que o Fincept não tem.
4. **Revisão independente do DCF** (`modelagem.py:34-62`, `valuation_reviewer`): reauditoria determinística do DCF do Model Builder (ordem pessimista≤base≤otimista, rastreabilidade de fonte/data-base, disponibilidade de sensibilidade) — nunca recalcula com premissas próprias.
5. **Pareceres por especialista** (`pareceres.py`): `market_researcher`, `earnings_reviewer`, `valuation_comparables` produzem `recomendacao` numa escala comparável (COMPRA/VENDA/NEUTRO/INSUFICIENTE); `model_builder` (MODELADO/INSUFICIENTE) e `valuation_reviewer` (APROVADO/COM RESSALVAS/INSUFICIENTE) respondem perguntas diferentes, fora dessa escala.
6. **Cross-check entre 2 fontes EXTERNAS** (`consolidacao.py:_divergencia_cross_comparador_memoria`): compara recomendação/preço-alvo por casa entre o comparador estruturado e a memória de research (RAG) — já existia, cobre divergência entre DUAS FONTES, nunca entre os PRÓPRIOS especialistas do Comitê.
7. **Confiança categórica** (`consolidacao.py:_confianca`): nunca número de probabilidade — `ALTA/MEDIA/BAIXA/INSUFICIENTE` com justificativa textual, calculada (antes desta auditoria) só pela proporção de especialistas que trouxeram evidência real.
8. **Checagem equivalente, já existente, em OUTRA camada** (`data/market_researcher.py:23-29,141-147`): contradição de recomendação entre casas EXTERNAS de research (quando ≥2 casas têm o campo estruturado preenchido) — já cobre "casa A vs. casa B"; e `data/research/sinal.py:114-133`: dentro do motor de sinal quantitativo, um voto majoritário entre casas independentes de research (excluindo XP/Genial) alimenta 1 dos 6 critérios de pontuação.

**Gap real identificado (pré-existente, não documentado antes)**: havia 3 camadas de "cross-check" (comparador×memória de research; casa×casa externa; voto majoritário de casas dentro do sinal quantitativo) mas **nenhuma comparava os vereditos dos PRÓPRIOS especialistas do Comitê entre si** (`market_researcher` vs. `valuation_comparables` vs. `earnings_reviewer`). Era possível (e eu reproduzi com um fixture de teste real) o Market Researcher dizer COMPRA e o Valuation por Múltiplos dizer VENDA a partir dos MESMOS dados de entrada, sem que `confianca`, `pontos_atencao` ou `conclusao` nunca mencionassem isso — a UI mostraria "ALTA confiança" ao lado de dois pareceres que se contradizem.

## 3. Melhoria implementada (escopo contido, backend apenas)

Arquivo: `data/coordenador_central/consolidacao.py`. Nenhum arquivo de UI (`ui/coordenador_tab.py`), nenhum coletor (`data/research/*.py`) tocado.

### O que foi adicionado

1. `_divergencia_entre_analistas_comite(pareceres)` (nova função): compara a `recomendacao` dos especialistas cuja escala é comparável (`COMPRA`/`VENDA`/`NEUTRO` — exclui automaticamente `model_builder`/`valuation_reviewer`, que respondem perguntas diferentes, e qualquer `INSUFICIENTE`). `None` quando há menos de 2 comparáveis (não há o que comparar — nunca "concordam por falta de dado"). Nunca decide quem está certo; só expõe a discordância com atribuição por especialista.
2. Nova chave `divergencias.entre_analistas_comite` no dict consolidado (sibling de `cross_comparador_memoria`, que já existia) — **nenhuma chave de topo nova** foi adicionada (os testes que travam o contrato de 8 chaves continuam passando sem alteração).
3. `_confianca()` agora rebaixa `ALTA → MEDIA` explicitamente quando há divergência real entre especialistas, com justificativa textual (nunca um número) — *"volume de evidência não substitui consenso de leitura"*.
4. `_pontos_atencao()` e `_conclusao()` passam a citar a divergência quando ela existe, seguindo o mesmo padrão de rótulo `[FATO]` e a mesma frase de neutralidade já usada pro cross-check externo (*"este módulo não decide qual especialista está certo"*).

### Por que essa é a melhoria certa pra esta missão

- É exatamente o gap que a auditoria do Fincept expôs por contraste: nem o Fincept (LLM-persona + roteador, sem reconciliação automática) nem o Pregão (antes desta mudança) comparavam vereditos de agentes/especialistas distintos entre si de forma determinística. O Pregão agora tem algo que o Fincept não tem em nenhuma camada encontrada.
- Mantém 100% a filosofia existente do módulo: zero chamada de IA nova, nunca infere "quem está certo", nunca produz número de probabilidade, degrada explicitamente quando não há dado suficiente.
- Escopo contido: 1 arquivo de lógica (`consolidacao.py`), nenhuma mudança de contrato de topo, nenhum especialista novo, nenhuma UI tocada.

### Teste antes/depois (evidência real, não hipotética)

Fixture: fundamentos com ROE 25%, margem 20%, dívida líq./EBITDA 0,5x, FCF positivo (tudo favorável → Market Researcher = **COMPRA**) e P/L 30x contra mediana setorial de 10x (prêmio relativo severo → Valuation por Múltiplos = **VENDA**) — mesmos dados de entrada, dois pareceres opostos.

- **Antes** (comportamento confirmado via `consolidacao._confianca(resultados, divergencia_comite=None)` no teste `test_confianca_rebaixada_de_alta_para_media_quando_comite_diverge`): com 3 de 4 especialistas acionados trazendo evidência real, a confiança seria classificada **ALTA** — sem qualquer menção à contradição entre Market Researcher e Valuation.
- **Depois**: `consolidacao.consolidar(...)["confianca"]["categoria"] == "MEDIA"`, com justificativa citando a divergência; `pontos_atencao` ganha a linha `"comitê: 2 especialista(s) ... DIVERGEM entre si (market_researcher=COMPRA; valuation_comparables=VENDA)"`; `conclusao` ganha uma linha `[FATO]` equivalente.
- Teste de controle (`test_confianca_nao_rebaixa_quando_comite_concorda_mesmo_com_muita_evidencia`): mesmo volume de evidência, mas fundamentos alinhados (P/L 10x vs. mediana 18x) → ambos COMPRA → confiança permanece **ALTA**, sem rebaixamento espúrio.
- Teste de guarda (`test_model_builder_e_valuation_reviewer_nunca_entram_na_divergencia_entre_analistas`): `model_builder`/`valuation_reviewer` nunca entram nessa comparação, mesmo quando disponíveis — evita falso positivo por comparar escalas diferentes.

Testes novos em `tests/test_coordenador_central_consolidacao.py`: `test_divergencia_entre_analistas_do_comite_quando_recomendacoes_comparaveis_discordam`, `test_sem_divergencia_entre_analistas_do_comite_quando_recomendacoes_concordam`, `test_divergencia_entre_analistas_do_comite_none_quando_menos_de_dois_comparaveis`, `test_confianca_rebaixada_de_alta_para_media_quando_comite_diverge`, `test_confianca_nao_rebaixa_quando_comite_concorda_mesmo_com_muita_evidencia`, `test_model_builder_e_valuation_reviewer_nunca_entram_na_divergencia_entre_analistas`.

### Comandos executados e resultado

```
python -m pytest tests/ -k coordenador -q   →  190 passed
python -m pytest tests/ -q                  →  2345 passed (suíte inteira, 0 regressão)
```

Não há dependência de rede/Supabase/IA em nenhum dos testes novos (mesmo padrão dos testes existentes do módulo) — nada disso pôde nem precisou ser validado contra Supabase/produção real; é lógica pura sobre dicts, assim como o resto de `consolidacao.py` já era.

## 4. Oportunidades identificadas, NÃO implementadas (documentação apenas)

Fora do escopo contido desta missão — registradas aqui pra decisão futura do Rodrigo, nenhuma linha de código criada pra elas:

1. **Divergência entre os 3 preços-alvo que já coexistem em `sinal_comite`** (`preco_alvo_modelo` do DCF, `preco_alvo_pl_setorial` do múltiplo setorial, `preco_alvo_consenso` das casas externas) — hoje nenhum cross-check numérico entre eles (ex.: DCF 40% acima do consenso das casas seria um sinal relevante de atenção, hoje silencioso). Maior que o escopo de hoje porque tocaria `sinal_comite`, usado por `web/lib/server/dominio/coordenador.ts` — precisaria auditoria de paridade Streamlit×Vercel antes de mudar o shape.
2. **Padrão de prompt "não escurecer o conflito em prosa"** do Warren Buffett Agent do Fincept (fora do `data/`): útil como princípio pra qualquer especialista do Pregão que UM DIA venha a gerar texto livre via IA (hoje nenhum especialista do Comitê faz isso — é tudo heurística sobre dados estruturados) — registrar o princípio, não há código pra aplicar ainda.
3. **`scoring_weights` explícitos e nomeados por dimensão** (presente nos 20+ configs JSON do Fincept) — o motor `data/research/sinal.py:calcular_sinal_comite` já pontua por dimensão (rentabilidade/alavancagem/caixa/crescimento/valuation/research), mas os pesos estão implícitos no range de pontos de cada `if/elif` (ex.: `2 if roe >= 18 else...`), não documentados centralmente. Tornar isso uma tabela de pesos nomeada deixaria auditoria de calibração mais fácil — não implementado porque `sinal.py` é `data/research/*`, fora do escopo de arquivo autorizado pra este agente.
4. **Unificar as duas escalas de "confiança" que já coexistem**: `consolidacao._confianca` usa `ALTA/MEDIA/BAIXA/INSUFICIENTE`; `sinal.calcular_sinal_comite` usa `ALTA/MÉDIA/INSUFICIENTE/BAIXA` (com acento, calculado por critério diferente). Não são a mesma coisa nem usam a mesma grafia — gap de consistência pré-existente, fora do escopo de arquivo autorizado (`sinal.py`) pra corrigir agora.

## 5. Resumo — implementado de fato vs. só documentado

**Implementado e testado** (backend do Comitê, dentro do escopo autorizado):
- `data/coordenador_central/consolidacao.py`: nova checagem determinística de divergência entre os pareceres do próprio Comitê (`_divergencia_entre_analistas_comite`), nova chave `divergencias.entre_analistas_comite`, rebaixamento explícito de confiança `ALTA→MEDIA` quando há divergência real, menções em `pontos_atencao`/`conclusao`.
- `tests/test_coordenador_central_consolidacao.py`: 6 testes novos cobrindo discordância real, concordância, ausência de base comparável, rebaixamento de confiança, não-rebaixamento espúrio, e exclusão correta de `model_builder`/`valuation_reviewer` da comparação.
- Suíte inteira (2345 testes) e suíte do coordenador (190 testes) passam sem regressão.

**Só documentado como oportunidade futura** (seção 4 acima): cross-check entre os 3 preços-alvo de `sinal_comite`; princípio de prompt anti-contradição-em-prosa (sem especialista de IA generativa hoje pra aplicar); pesos nomeados centralizados em `sinal.py`; unificação das duas grafias/escalas de confiança — nenhum requer código novo nesta entrega porque todos tocam arquivos fora do escopo autorizado (`sinal.py`, `web/`) ou exigiriam decisão de produto do Rodrigo antes de mudar um contrato consumido pela web.

Nenhum agente existente (Market Researcher, Model Builder, Earnings Reviewer, Valuation Reviewer, Coordenador) foi substituído ou teve seu comportamento calculado alterado — a mudança é estritamente aditiva sobre o que `montar_pareceres` já produzia.
