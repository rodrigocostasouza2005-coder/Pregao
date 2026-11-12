# Auditoria de arquitetura — Fincept Terminal como referência pro PREGÃO

**Data:** 2026-11-12
**Agente:** FINCEPT-A (missão isolada de auditoria, zero implementação)
**Repo auditado:** [github.com/Fincept-Corporation/FinceptTerminal](https://github.com/Fincept-Corporation/FinceptTerminal) — clone local (`--depth 1`, HEAD de `main` em 2026-11-12, release pública mais recente **v4.5.2**)
**Repo de referência:** `~/Projects/pregao` (worktree principal do Rodrigo, estado lido em 2026-11-12)

---

## Aviso de licença — AGPL-3.0-or-later

O Fincept Terminal é licenciado **AGPL-3.0-or-later** (confirmado no `LICENSE` e no README do repo). Isso importa diretamente pro PREGÃO:

- AGPL tem cláusula de **network use**: se código AGPL (mesmo adaptado) for incorporado a um serviço acessado via rede — e o PREGÃO é exatamente isso, roda no Streamlit Cloud e é acessado pelo navegador — o serviço inteiro passa a ter obrigação de liberar seu código-fonte sob AGPL também.
- **Nenhuma linha de código do Fincept foi copiada, adaptada ou transcrita para este relatório ou para qualquer arquivo do PREGÃO.** Tudo abaixo é extração de **ideias, padrões e decisões de arquitetura** (o "como" e o "por quê"), descritas em prosa própria, para eventual **reimplementação 100% independente** no PREGÃO — sem nenhum trecho do código-fonte original envolvido.
- Trechos de código do Fincept citados neste documento (ex.: assinaturas de método, nomes de campos de struct) são citações mínimas de identificadores/estrutura para fins de descrição factual da arquitetura, não cópia funcional — e mesmo assim nenhum desses identificadores foi levado ao PREGÃO.
- Esta missão **não implementou nada** — é só este documento.

---

## Descoberta de contexto crítica: o Fincept não é mais um webapp Python

A missão partiu da hipótese de um dashboard Python (scheduler, cron, jobs, schema de dados) parecido em espírito com o PREGÃO. **Isso não corresponde mais à realidade do repo.** Desde a v4, o Fincept Terminal é um **desktop binário nativo em C++20/Qt6** ("Bloomberg-style multi-window financial workstation"), com Python 3.11 **embutido apenas como camada de scripts de dados/analytics**, chamado via subprocess. Não há Streamlit, não há framework web, não há deploy em nuvem do runtime principal — é instalador por SO (Windows/macOS/Linux), ~342.000 linhas de C++ e ~1.423 scripts Python.

Isso muda o enquadramento da auditoria: **não dá pra comparar "stack com stack"** (Streamlit vs. Qt6 é night-and-day, e o Rodrigo foi explícito: nada de migrar pra C++/Qt/Electron). O valor real está nos **padrões arquiteturais internos** que são independentes de linguagem/UI — pub/sub com cache e freshness, contrato padronizado de conectores de dados, migrations versionadas, CI que trava regressão de dívida técnica, task state durável para agentes de IA, e documentação viva de arquitetura. Todos esses são **portáveis para Python/Streamlit/Supabase sem trocar nada de stack**, e é nisso que este relatório foca.

Escala do repo (do próprio `docs/ARCHITECTURE.md`, v5.0.0-draft, atualizado 2026-05-15): ~1.626 arquivos C++, ~342k linhas C++, ~1.423 scripts Python, 54 telas, ~50 serviços, 16 corretoras + 2 exchanges cripto, 26 repositórios tipados, 40+ ferramentas MCP.

---

## Stack tecnológica completa do Fincept (para registro)

| Camada | Tecnologia |
|---|---|
| Linguagem core | C++20 |
| UI | Qt6 Widgets + Qt6 Charts, docking via ADS (Advanced Docking System) |
| Rede | Qt6 Network (HTTP/TLS), Qt6 WebSockets |
| Persistência | Qt6 Sql + SQLite — **dois bancos físicos** (`Database` principal, `CacheDatabase` separado pra cache efêmero) |
| Migrations | Versionadas forward-only, `storage/sqlite/migrations/v001...v0NN` + `MigrationRunner` |
| Segredos | SQLite + AES-256-GCM (`SecureStorage`), chave derivada de `machineUniqueId`; **não** usa keychain do SO de propósito |
| Python embutido | 3.11.9, gerenciado via `uv`, dois venvs (`venv-numpy1` legado, `venv-numpy2` padrão) |
| Build | CMake 3.20+ (hoje um `CMakeLists.txt` monolítico de ~3.300 LOC, com plano de modularizar) |
| IA/LLM | Bring-your-own-key (OpenAI, Anthropic, Gemini, Groq, DeepSeek, OpenRouter, Ollama); 37 agentes (trader/investidor, econômicos, geopolítica) |
| MCP | Bridge próprio (`McpService`/`McpProvider`/`McpManager`) expondo ~40+ ferramentas internas + servidor MCP externo para agentes de pesquisa |
| Dados | 100+ conectores (FRED, IMF, World Bank, DBnomics, AkShare, BCB, Polygon, Kraken, Yahoo Finance, etc.), cada um um script Python standalone |
| Deploy | Instalador nativo por SO (exe/dmg/deb/rpm), **sem** servidor web nem nuvem no core aberto |
| CI | GitHub Actions: build C++ multiplataforma, lint, "architecture ratchet", gate de PR, release, tradução automática de README |

Isso **não é comparável 1:1** ao PREGÃO (Streamlit + Supabase/Postgres + GitHub Actions, sem Qt/C++, sem instalador). A comparação de valor está nos padrões abaixo.

---

## Achados

### Achado 1 — DataHub: camada de cache/pub-sub com freshness explícita

**(1) Como funciona no Fincept:** `fincept-qt/src/datahub/DataHub.h` implementa um hub de pub/sub **em processo**, "one-fetch/many-subscribers", organizado por tópicos hierárquicos (`market:quote:AAPL`, `news:symbol:PETR4`, `agent:stream:<run_id>`). Cada tópico tem uma `TopicPolicy` (TTL, intervalo mínimo entre refreshs, flag push-only) e um `TopicStats` com `subscriber_count`, `total_publishes`, `total_errors`, `last_error`, `in_flight`, `age_ms` desde a última publicação. Uma tela assina um tópico; se o cache estiver fresco, recebe na hora; se estiver stale, o hub aciona o "producer" (serviço que sabe buscar aquele dado) e todo mundo que assina recebe a atualização de uma vez só. Em erro do producer, o hub **mantém o último valor bom visível** (`publish_error` nunca apaga o cache) e emite um sinal de erro separado pra UI decidir como sinalizar. Há também eviction de tópicos ociosos (sem assinante há muito tempo) pra não crescer memória sem limite, e coalescing de rajadas de requisição numa janela de 100ms. Existe até uma tela de devtools (`DataHubInspector`) e 4 ferramentas MCP (`datahub_list_topics`, `datahub_peek`, `datahub_request`, `datahub_subscribe_briefly`) que deixam um agente de IA **perguntar ao próprio hub** se um feed está vivo, qual o valor mais recente, ou observar um tópico por alguns segundos — documentado em `fincept-qt/docs/agents/datahub-guide.md`.

**(2) Tecnologia:** C++/Qt (QHash, QMutex, QTimer, sinais/slots) — mas a ideia é agnóstica de linguagem.

**(3) Equivalente no PREGÃO hoje:** Parcial e fragmentado. `data/coletores_status.py` registra tentativas de coleta (sucesso/falha/parcial/erro/idade) numa tabela Supabase, e `data/saude_dados.py` classifica isso em estados (`SUCESSO_COM_NOVIDADE`, `FONTE_INDISPONIVEL`, `DADOS_DESATUALIZADOS` etc.) pra alimentar a aba Saúde dos Dados (`ui/saude_dados_tab.py`) — isso já é **pull-based e honesto** (nunca inventa "verde" sem evidência, documentado explicitamente no código). Só que é: (a) **por coletor**, não por "tópico de dado" — não há um conceito único de freshness por item de dado individual (ex. "cotação da PETR4 tem X segundos"); (b) só é calculado quando a aba é aberta, não mantido vivo; (c) cache de conteúdo (`st.cache_data`/`st.cache_resource`) é espalhado pelos módulos sem TTL unificado nem registro central de "quem está em voo agora" (equivalente a `in_flight`) — então duas chamadas simultâneas podem disparar a mesma busca cara em paralelo. A única exceção notável é `data/ia_cache.py`, que já implementa manualmente, só para resumos de IA, uma reserva anti-duplicação (INSERT exclusivo por `chave_documento`, com timeout de abandono de 120s) — ou seja, o PREGÃO já reinventou um pedaço pequeno da mesma ideia, mas ad hoc e não generalizada.

**(4) O que podemos melhorar:** Formalizar um registro central de freshness por item de dado (não por coletor): uma tabela/dict com `{topico, ultimo_valor_ts, ultimo_erro, ttl_esperado, em_voo}` que qualquer módulo de `data/*.py` consulta antes de buscar de novo, e que a aba Saúde dos Dados e um futuro "inspector" (até uma aba de debug simples) possam ler ao vivo. O padrão "last-known-good nunca é apagado por um erro" já existe em `coletores_status.registrar_tentativa` — vale generalizar esse princípio pro cache de conteúdo também, não só pro metadado de tentativa.

**(5) Adaptável sem migrar stack:** Sim, totalmente. Isso é um módulo Python puro (`data/freshness.py` ou extensão de `data/coletores_status.py`) + `st.cache_data`/`st.session_state` pra estado em memória do processo Streamlit, com a tabela Supabase existente servindo de fallback persistente entre processos/instâncias. Não exige fila externa nem Redis — Supabase já serve de "banco de estado" como o SQLite do Fincept serve pro `CacheDatabase`.

**(6) Impacto esperado:** Reduz chamadas duplicadas a fontes externas sob concorrência (hoje só protegido manualmente pra IA), dá uma base única pra "está atualizado?" em qualquer tela nova sem reinventar a roda por módulo, e abre caminho pra uma aba de debug "o que está vivo agora" útil tanto pro Rodrigo quanto pros 5 agentes trabalhando em paralelo.

---

### Achado 2 — Conectores de dados com contrato padronizado e catálogo autogerado

**(1) Como funciona no Fincept:** Cada fonte de dado é um script Python standalone em `fincept-qt/scripts/<fonte>_data.py` (ex.: `bcb_data.py` para o Banco Central do Brasil, `fred_data.py`, `akshare_*.py` — ~1.037 scripts `.py` no total). Documentado em `docs/PYTHON_CONTRIBUTOR_GUIDE.md`, o contrato é rígido: (a) **docstring no topo** com os comandos aceitos e variáveis de ambiente de API key — é a única documentação que um agente de IA vê; (b) despacho de comando por `sys.argv[1]`; (c) **um único documento JSON no stdout**, nunca mais; logs vão pro stderr; (d) falha é sempre `{"error": "<mensagem>"}` — nunca exceção não tratada, nunca exit code como único sinal; (e) proibido `NaN`/`Infinity` no JSON (`allow_nan=False`, quebraria o parser C++); (f) segredos e inputs grandes vão por stdin, nunca por argv (visível a outros processos do mesmo usuário). Um script auxiliar (`.github/scripts/gen_data_connectors.py`) **lê a docstring de cada conector e gera automaticamente** o catálogo de fontes de dados (`data_connectors.json`) — com um modo `--check` que falha o CI se o catálogo ficar desatualizado em relação ao código. Dentro de cada conector, uma camada de metadado declarativo (ex. em `bcb_data.py`: um dict `SERIES` com `id`, `name`, `category`, `unit`, `freq` por série, e `GROUPS` agrupando séries relacionadas) documenta a taxonomia do dado no próprio código.

**(2) Tecnologia:** Python puro + convenção de CLI/JSON; nenhuma dependência de C++ aqui, é 100% portável.

**(3) Equivalente no PREGÃO hoje:** Os módulos de `data/*.py` (ex. `cvm.py`, `macro.py`, `mercado.py`, `news.py`) já são divididos por fonte e já têm bastante metadado interno, mas **não há um contrato uniforme de saída nem catálogo autogerado**. Cada módulo expõe funções Python chamadas diretamente (sem subprocess/JSON), o que é adequado porque não existe fronteira C++/Python a cruzar — mas significa que não existe hoje um jeito automático de perguntar "quais fontes de dado o PREGÃO tem, que categoria/unidade/frequência cada uma declara". `docs/research-fontes-20261022.md` e `PROGRESSO.md` cumprem esse papel manualmente, escritos à mão.

**(4) O que podemos melhorar:** Não o mecanismo de transporte (stdin/stdout/JSON não faz sentido pro PREGÃO, que não tem fronteira de processo entre UI e dados) — mas sim a **ideia de metadado declarativo uniforme + catálogo gerado**: cada módulo de `data/*.py` exportar um dict padronizado (`FONTES = {"selic": {"categoria": "...", "unidade": "...", "frequencia": "...", "funcao": selic}}`) e um script (`scripts/gerar_catalogo_fontes.py`) que lê esses dicts de todos os módulos e regenera um `docs/catalogo-fontes.md` automaticamente, com checagem `--check` no CI de `testes.yml` pra nunca ficar desatualizado.

**(5) Adaptável sem migrar stack:** Sim — é só convenção Python + um gerador, roda dentro do próprio `testes.yml` existente.

**(6) Impacto esperado:** Documentação de fontes sempre sincronizada com o código (hoje depende de o humano/agente lembrar de atualizar o `.md` à mão); facilita auditorias futuras como esta; dá uma base de dados estruturada pra eventual chatbot/IA responder "quais indicadores macro o PREGÃO cobre".

---

### Achado 3 — Migrations SQL versionadas e forward-only, com runner

**(1) Como funciona no Fincept:** `fincept-qt/src/storage/sqlite/migrations/` tem arquivos `v001_initial.cpp` até `v028_fii_dii.cpp` (28 migrations no momento da auditoria), cada um uma mudança de schema isolada e nomeada por intenção, aplicada por um `MigrationRunner` que sabe qual versão o banco local já tem e aplica só o que falta, em ordem, uma vez. Forward-only — nunca editam uma migration já publicada.

**(2) Tecnologia:** SQLite + runner C++ próprio; o padrão (numeração sequencial + runner que rastreia versão aplicada) é agnóstico de banco.

**(3) Equivalente no PREGÃO hoje:** `sql/` tem arquivos soltos por domínio (`schema.sql`, `cvm.sql`, `eventos.sql`, `coletores_status.sql`, `ia_cache.sql`, `radar_research.sql`, `research.sql`) — **sem numeração, sem runner, sem rastreamento de quais já foram aplicados em produção**. O próprio histórico do PREGÃO documentado no `BACKLOG.md`/`PROGRESSO.md` (citado dentro do código, ex. em `data/coletores_status.py` e `data/ia_cache.py`) registra **pelo menos 2 incidentes reais** causados exatamente por isso: tabelas (`eventos_resultados`, `resumos_ia_cache`) usadas em código há semanas antes de alguém rodar o `.sql` correspondente em produção — silenciosamente mascarado porque "tabela ausente" e "credencial inválida" geravam o mesmo sintoma (isso já foi corrigido no nível de diagnóstico, não no nível de prevenção).

**(4) O que podemos melhorar:** Não precisa de um runner C++; só precisa de **disciplina de numeração + um registro de "o que já rodou em produção"**. Mais simples ainda: uma tabela `schema_migrations(nome, aplicado_em)` no próprio Supabase, e um script Python pequeno que lista os arquivos `sql/NNN_descricao.sql` ainda não registrados nessa tabela e os aplica (ou ao menos avisa quais faltam rodar manualmente, já que Supabase Cloud não dá acesso de superusuário irrestrito para todo DDL). Isso teria prevenido os dois incidentes documentados.

**(5) Adaptável sem migrar stack:** Sim — é puramente convenção de nomenclatura de arquivo + uma tabela de controle + um script Python curto usando o `supabase-py` já existente em `data/supabase_client.py`.

**(6) Impacto esperado:** Elimina a classe de bug "feature já diz que depende de uma tabela que ninguém rodou o `.sql` em produção" — que já causou pelo menos 2 incidentes reais documentados no próprio código do PREGÃO.

---

### Achado 4 — "Architecture ratchet" no CI: contadores de dívida técnica que nunca podem crescer

**(1) Como funciona no Fincept:** `.github/workflows/arch-ratchet.yml` roda em todo PR que toca `fincept-qt/src/**` e executa `.github/scripts/arch_ratchet.py`, que conta ocorrências de padrões ruins conhecidos (ex.: `setStyleSheet` inline fora do sistema de tema, `setStyleSheet` dentro de loop — reparse de CSS por linha por tick —, strings literais não traduzíveis) e compara contra uma baseline (`arch_ratchet_baseline.json`). Se o contador **subir**, o PR falha. Se baixar (dívida foi paga), a baseline é regenerada manualmente — nunca pra deixar passar uma violação nova, só pra travar o novo nível mais baixo. O comentário no workflow explica a razão de ser ratchet e não gate absoluto: há ~5.200/~460/~120 violações pré-existentes hoje, então um gate rígido quebraria todo PR no primeiro dia e a equipe removeria o check — "a ratchet people keep beats a gate they remove".

**(2) Tecnologia:** Python puro + JSON de baseline + GitHub Actions — zero dependência de C++/Qt no mecanismo em si.

**(3) Equivalente no PREGÃO hoje:** Não existe. `testes.yml` roda pytest e gera um PDF de prévia do Morning Call, o que é ótimo pra regressão funcional, mas não há nenhum controle automatizado sobre dívida técnica estrutural (ex.: número de `except Exception` genéricos sem log, número de `print()` fora de contexto de debug, número de módulos em `data/*.py` que ainda não usam o padrão de diagnóstico de tabela_disponivel, tamanho de arquivos acima de N linhas).

**(4) O que podemos melhorar:** Dado que o PREGÃO está crescendo com 5 agentes em paralelo tocando `data/research/*.py` e `ui/*.py` nesta mesma semana, esse é um padrão de **alto valor e baixo custo de implementação** pra evitar que dívida técnica se acumule silenciosamente nesses pontos de maior concorrência de edição. Exemplos de contadores candidatos pro PREGÃO: número de `except Exception:` sem `print`/log associado; número de acessos diretos a `st.secrets` fora de `data/supabase_client.py`/`config.py`; número de módulos em `data/research/` que não seguem o padrão de erro-classificado já estabelecido em `coletores_status.py`/`ia_cache.py` (hoje esse padrão de classificação de erro já está **duplicado** em pelo menos esses dois arquivos — um candidato natural de contador "número de cópias do mesmo bloco de sinais de erro" até ser extraído pra um módulo compartilhado).

**(5) Adaptável sem migrar stack:** Sim — é um script Python de ~100-200 linhas rodando dentro do `testes.yml` já existente, sem nenhuma infraestrutura nova.

**(6) Impacto esperado:** Dá visibilidade objetiva (não subjetiva) de quando um PR está piorando um padrão estrutural específico, especialmente valioso justamente porque hoje há *múltiplos agentes de IA* editando o mesmo código em paralelo sem revisão humana linha-a-linha de cada um.

---

### Achado 5 — Estado durável de tarefas de agente (resumable, com streaming)

**(1) Como funciona no Fincept:** Quando um agente de IA é iniciado (ex. "hedge fund agent"), o `AgentService` dispara um script Python como subprocesso que emite eventos por etapa como linhas JSON no stdout. Cada evento é **persistido numa tabela SQLite (`agent_tasks`)** e também publicado num tópico do DataHub (`agent:<kind>:run:<id>`) pra UI acompanhar em tempo real. Como o estado vive no banco, não na memória do processo, uma tarefa de agente é **crash-resumable**: se o app fechar no meio, o progresso sobrevive e pode ser retomado lendo a última etapa persistida.

**(2) Tecnologia:** SQLite + subprocess + DataHub; o padrão em si (checkpoint de progresso em storage durável + stream de eventos) é agnóstico de stack.

**(3) Equivalente no PREGÃO hoje:** Existe uma versão rudimentar: `coletor_local.py` grava arquivos de checkpoint simples (`coletor_local_checkpoint_calendario.txt`, `coletor_local_checkpoint_news.txt` — confirmados no diretório raiz do worktree principal) com, aparentemente, um único valor/timestamp — não uma sequência estruturada de etapas, nem uma tabela consultável, nem visibilidade de progresso em tempo real pra quem está olhando a UI enquanto a coleta roda.

**(4) O que podemos melhorar:** Trocar os arquivos `.txt` soltos por uma tabela Supabase (`coletor_checkpoints` ou estender `coletores_status`) com uma linha por execução contendo etapas percorridas, e permitir que a aba Saúde dos Dados mostre progresso granular de uma coleta em andamento, não só o resultado final da última tentativa. Isso é incremento sobre o que já existe, não substituição.

**(5) Adaptável sem migrar stack:** Sim — é extensão natural do padrão já usado em `coletores_status.registrar_tentativa`, só que por etapa em vez de por execução completa.

**(6) Impacto esperado:** Menor — é refinamento de algo que já funciona (os checkpoints `.txt` já cumprem o papel básico de não reprocessar do zero). Prioridade baixa frente aos outros achados.

---

### Achado 6 — Documentação viva de arquitetura (current vs. target, dívidas nomeadas)

**(1) Como funciona no Fincept:** `docs/ARCHITECTURE.md` é um documento de ~500 linhas, versionado (`5.0.0-draft`, "Status: Living document"), que descreve a arquitetura **como ela é hoje** e, em seções explicitamente marcadas `(target)`, pra onde está indo — com uma tabela inteira ("Known weaknesses and their owners") listando cada dívida técnica conhecida, seu impacto, e a fase do plano de refatoração que a resolve. Existe também uma pasta `docs/adr/` pro processo de Architecture Decision Records (decisões de arquitetura registradas quando revertidas/refinadas).

**(2) Tecnologia:** Markdown — zero dependência técnica.

**(3) Equivalente no PREGÃO hoje:** Parcial — `docs/arquitetura-pregao-2.md` existe, e `BACKLOG.md`/`PROGRESSO.md`/`CHANGELOG.md` são enormes e detalhados (143k, 437k, 146k respectivamente), mas são **históricos cronológicos**, não um mapa current/target consolidado com uma lista explícita de dívidas conhecidas e donos. Achar "o que está quebrado e por quê" hoje exige grep nesses arquivos gigantes.

**(4) O que podemos melhorar:** Não é prioridade alta de infraestrutura, mas é baixo custo e alto valor justamente pelo cenário atual (6 agentes em paralelo, cada um possivelmente sem contexto completo do estado dos outros): uma seção curta e viva "dívidas conhecidas" dentro de `docs/arquitetura-pregao-2.md`, atualizada a cada PR que resolve ou introduz uma, no estilo da tabela do Fincept.

**(5) Adaptável sem migrar stack:** Sim, é só prática de documentação.

**(6) Impacto esperado:** Reduz retrabalho e descoberta repetida do mesmo problema por agentes diferentes (o padrão já aparece nos comentários do próprio código do PREGÃO, que cita "auditoria 2026-10-13", "achado real 2026-10-15" etc. — ou seja, o hábito de documentar achados já existe, só que disperso em comentários de código em vez de consolidado).

---

## O que foi visto e **não** é recomendado trazer

- **Qualquer coisa de C++/Qt6/CMake/instalador nativo.** O Rodrigo foi explícito: não migrar de Streamlit. Sem debate aqui.
- **Infra de trading multi-corretora (16 brokers), exchanges cripto, paper trading.** Fora do escopo do PREGÃO (terminal de research B3, não executor de ordens).
- **Framework de 37 agentes de IA com personas/`super_agent.py`.** Interessante como inspiração distante, mas é um investimento de engenharia muito maior que o que o PREGÃO precisa hoje; não vale a pena extrair agora.
- **MCP server completo com 40+ ferramentas.** Só faria sentido se o PREGÃO expusesse uma interface de agente externo — não é o caso hoje.
- **SecureStorage com AES-256-GCM local.** O PREGÃO já delega segredos a `st.secrets`/variáveis de ambiente do Streamlit Cloud/GitHub Actions; não há "disco local do usuário" a proteger da mesma forma que um app desktop tem.

---

## Resumo para priorização

| Achado | Esforço estimado | Valor | Prioridade sugerida |
|---|---|---|---|
| 3. Migrations SQL numeradas + tabela de controle | Baixo | Alto (já causou 2 incidentes reais) | **1** |
| 4. Architecture ratchet no CI | Baixo | Alto (protege contra os 5 agentes paralelos agora) | **2** |
| 1. Registro central de freshness/cache (versão simplificada) | Médio | Médio-alto | **3** |
| 2. Metadado declarativo + catálogo de fontes autogerado | Médio | Médio (documentação sempre sincronizada) | **4** |
| 6. Seção "dívidas conhecidas" na doc de arquitetura | Baixo | Médio | **5** |
| 5. Checkpoints estruturados por etapa | Médio | Baixo (já existe versão básica) | **6** |

Nenhum desses itens foi implementado nesta missão — ficam como recomendação para o Rodrigo priorizar e, se aprovado, delegar a um agente de implementação dedicado (fora dos 5 que já tocam `data/research/*.py` e `ui/*.py`).
