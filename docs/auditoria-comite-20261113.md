# Auditoria do Comitê de Investimentos — arquitetura híbrida (determinístico + IA real)

Data: 2026-11-13 · Branch: `feat/auditoria-comite-ia-hibrida-20261113` (a partir de `origin/main` atualizado) · Worktree isolado: `pregao-fase4-comite`.

Escopo: verificar se o Comitê de Investimentos (Market Researcher, Model Builder, Earnings Reviewer, Valuation Reviewer, Coordenador Central, RAG/Memória de Research e demais especialistas) é uma arquitetura híbrida **funcional** — cálculo determinístico auditável + IA real para interpretação qualitativa — e não só nomes bonitos chamando funções vazias. Leitura de código real (`data/coordenador_central/*`, `data/market_researcher.py`, `data/research/*`, `jobs/comite_noturno.py`, `jobs/coordenador.py`, `ui/coordenador_tab.py`) + teste ponta a ponta real (sem mock de rede/IA/Supabase) com PETR4.

Histórico já validado antes desta auditoria (não redescoberto): PR #308 (síntese qualitativa real), PR #307 (validação Groq real), PR #299 (unifica escala de confiança + prova de fluxo e2e com fronteiras de rede mockadas), PR #242 (Model Builder/Valuation Reviewer).

## Por que PETR4

Ticker líquido da B3, com cobertura de research real (Monte Bravo ativo na lista de casas monitoradas), CNPJ mapeado na CVM (ITR/DFP disponíveis), e um calendário de resultados recente (2T2026) para validar o Earnings Reviewer com números reais. Também expôs, por acidente, um caso real de mismatch de moeda (yfinance reporta `financialCurrency=USD` para os fundamentos de Petrobras, mas a cotação é em BRL) — útil para confirmar que o Model Builder se recusa corretamente a inventar uma conversão.

## Metodologia do teste ponta a ponta

Execução direta de `data.coordenador_central.fluxos.analisar_ticker("PETR4", premissas_dcf=..., sintese_ia=True)` num processo Python real, usando as credenciais reais do worktree (`.streamlit/secrets.toml`: Supabase + Groq), **sem mockar nenhuma camada de negócio** — yfinance, CVM (dados.cvm.gov.br), Google News RSS, Supabase e Groq foram todos chamados de verdade. 3 execuções completas, nenhuma com dado simulado:

1. **1ª execução** (timeout padrão do executor, 30s por grupo): expôs um achado real — ver seção "Achado corrigido".
2. **2ª execução** (timeout elevado para 180s, validação intermediária): confirmou a causa raiz.
3. **3ª execução** (timeout elevado para 240s, após o fix): produziu um resultado quase completo, com evidência real de todos os especialistas exceto os dois bloqueados por um motivo legítimo (mismatch de moeda, não falha).

## Achado corrigido (bug real, baixo risco) — timeout do executor incompatível com a CVM em cache frio

`data/coordenador_central/executor.py:_TIMEOUT_PADRAO_SEG = 30`. Na 1ª execução real, `analise_ticker` e `resultados_corporativos` retornaram `motivo_indisponivel="timeout"` — não porque a fonte estava fora do ar, mas porque `historico_fundamentos` (via `earnings_reviewer.serie_historica_br` → `montar_nota_br`) baixa o ZIP consolidado ITR/DFP/DFC da CVM (todas as companhias de 1 ano, não só o ticker pedido) sempre que o ano não está no cache em memória do processo (`@st.cache_data`, que começa vazio em toda execução nova do job — inclusive a cada rodada do GitHub Actions). Medido isoladamente nesta auditoria: **138,7s** só para `historico_fundamentos`; a soma sequencial dos 5 sub-blocos de `analise_ticker` isolada ficou perto de **176s**. Com o teto de 30s, esses dois especialistas timeoutavam quase sempre em cache frio — não é falha da fonte, é o timeout cortando uma chamada que terminaria com sucesso.

**Fix aplicado**: `data/coordenador_central/fluxos.py` passa agora `timeout_seg=240` (constante `_TIMEOUT_GRUPO_PRINCIPAL_SEG`, com a justificativa completa documentada no código) para o grupo de 6 especialistas de `analisar_ticker`. Teto por grupo, não por especialista individual, porque todos rodam em paralelo no mesmo `ThreadPoolExecutor` — o teto mais alto nunca atrasa quem responde rápido, só evita classificar como indisponível um especialista lento-mas-saudável. Validado na 3ª execução real: `resultados_corporativos` (66,4s), `comparador` (102,6s) e `analise_ticker` (118,9s) passaram a responder com sucesso dentro do novo teto.

**Limitação residual, documentada e não escondida**: mesmo com 240s, contenção real de CPU entre threads concorrentes (parsing pesado de CSV da CVM via pandas, que retém o GIL) pode em tese ainda empurrar `analise_ticker`/`comparador` perto do teto sob carga extrema do host — este ajuste resolve o caso medido (cache frio comum), não é uma garantia absoluta sob qualquer contenção.

Teste de regressão: `tests/test_coordenador_central_fluxos.py::test_analisar_ticker_usa_timeout_maior_pro_grupo_principal` — trava o teto explícito pra ele nunca voltar a cair silenciosamente para o default de 30s. Suíte completa re-executada sem regressão (ver seção "Validação").

## Achado crítico (não é bug de código, é um gap de produto) — a camada híbrida de IA nunca é acionada em produção

`fluxos.analisar_ticker(ticker, premissas_dcf=None, sintese_ia=False)` só aciona `market_researcher.sintese_qualitativa_research` e `sintese_ia.sintetizar_leitura_comite` quando chamado com `sintese_ia=True`. Busca em todo o repositório pelos únicos chamadores reais:

```
data/coordenador_central/fluxos.py:194   # a própria definição/docstring
data/coordenador_central/fluxos.py:232   # a própria definição/docstring
tests/test_coordenador_central_fluxos.py:452
tests/test_coordenador_central_fluxos.py:467
```

**Nenhum caminho de produção passa `sintese_ia=True`**: `jobs/comite_noturno.py` chama `analisar_ticker(ticker)` sem o parâmetro (default `False`); `ui/coordenador_tab.py:1277-1279` chama `funcao_fluxo(ticker_executar, premissas_dcf=premissas_dcf)` ou `funcao_fluxo(ticker_executar)` — nunca com `sintese_ia=True`, e não existe nenhum checkbox/toggle na tela "Analisar" para o analista habilitar isso manualmente.

Ou seja: a camada de IA real (Groq, prompt rigoroso, nunca inventa número, só interpreta o que já foi calculado) está **implementada corretamente e comprovadamente funcional** (ver evidência real abaixo) — mas está **dormente em todo uso real do produto**, tanto na rodada noturna automática quanto na tela manual do analista. Isso não foi corrigido nesta auditoria porque habilitar `sintese_ia=True` por padrão é uma decisão de produto/custo (chamadas reais à Groq a cada análise, inclusive em até 20 tickers/noite no Comitê Noturno), não um "bug de baixo risco" — fica registrado aqui para o Rodrigo decidir, não decidido unilateralmente por este agente.

## Achados menores (ambiente, não código)

- **Schema do Supabase deste worktree está atrás das migrações já escritas no repo**: `coletores_status.tempo_ultima_execucao_s` (proposto em `sql/coletores_status_metricas.sql`, PR #292), tabela `ia_hibrida_execucoes` (proposta em `sql/ia_hibrida_execucoes.sql`, PR #308) e tabela `research_recomendacoes_historico` não existem neste banco — todas têm migração SQL já escrita e marcada explicitamente como "PROPOSTO, NÃO APLICADO por este agente" nos próprios arquivos (regra do projeto: nenhum agente aplica schema em produção por conta própria). Efeito prático observado: a telemetria de IA híbrida (`ia_hibrida_telemetria.registrar_execucao`) falhou silenciosamente-mas-logada em todas as 3 execuções reais — **isso nunca impediu a síntese de IA de funcionar** (isolada por try/except, exatamente como desenhado), só significa que o histórico de chamadas de IA não está sendo persistido neste ambiente até a migração ser aplicada.
- **`GEMINI_API_KEY` não está configurada neste worktree** (`secrets.toml` só tem `supabase` e `groq`) — `memoria_research` (RAG) degradou corretamente para busca estrutural/lexical apenas, sem busca semântica, sem lançar excecão.
- **PETR4 especificamente**: yfinance reporta `financialCurrency=USD` para os fundamentos enquanto a cotação é `BRL` — o Model Builder recusou corretamente calcular o DCF em vez de presumir uma conversão, e isso se repetiu de forma consistente nas 3 execuções. Não é um bug; é o comportamento de segurança desenhado funcionando como esperado.

## Por especialista

### Market Researcher (`data/market_researcher.py`)
- **Responsabilidade**: agregador de fundamentos + catalisadores/mudança de tese + cobertura cruzada de research + histórico trimestral + comparativo setorial para 1 ticker (`analise_ticker`), mais a camada de qualidade de coletores e a síntese qualitativa de IA.
- **Dados recebidos**: ticker. Internamente consulta `data/radar.py:linha_valuation` (yfinance), `data/market_makers.py:contexto_ticker` (catalisadores/riscos), `cobertura_cruzada_casas` (Supabase `research_itens`), `historico_fundamentos` (Earnings Reviewer/CVM), `comparaveis_setor` (yfinance, pares do setor).
- **IA real**: só em `sintese_qualitativa_research(ticker)` — Groq (`openai/gpt-oss-20b`, fallback `openai/gpt-oss-120b`), opt-in, só roda se ≥1 casa de research cobre o ticker (nunca gasta cota sem conteúdo real pra sintetizar). O resto do módulo é 100% determinístico.
- **Saída**: dict agregado com `fontes_indisponiveis` explícito por bloco; a síntese de IA devolve `sintese/convergencias/divergencias/pontos_atencao/casas_citadas`, cada afirmação atribuída a uma casa real do payload (validado em `_validar_sintese_research`, que descarta casa inventada).
- **Degradação**: cada bloco tem try/except isolado; falha de 1 fonte nunca contamina as demais. Confirmado no e2e real: para PETR4, `sintese_qualitativa_research` corretamente devolveu `disponivel=False` ("sem publicações estruturadas para este ticker") sem gastar 1 chamada de IA.
- **Auditabilidade**: evidências sempre carregam fonte/data/link reais (confirmado: notícia real da ADVFN/Seu Dinheiro com link do Google News, catalisador real com a data regulatória CVM 2026-11-14).
- **Veredito: APROVADO.**

### Model Builder (`data/coordenador_central/modelagem.py:modelar_empresa` + `data/coordenador_central/dcf.py`)
- **Responsabilidade**: DCF de 5 anos + Gordon Growth em 3 cenários (otimista/base/pessimista) + matriz de sensibilidade 5x5 WACC×crescimento.
- **Dados recebidos**: `premissas_dcf` explícitas (FCF, WACC, crescimento, dívida líquida, ações, moeda, fonte) montadas por `fluxos._anexar_premissas_dcf` a partir de fundamentos reais (yfinance) + dívida líquida da CVM quando a moeda é compatível; nunca estima nada por conta própria.
- **IA real**: **nenhuma** — 100% determinístico, matemática pura (`dcf.py` não importa nenhum cliente de IA). Confirmado: nenhuma referência a Groq/OpenAI/Anthropic no módulo.
- **Saída**: cenários com `preco_alvo`/`upside_pct`/projeção ano-a-ano, ou `disponivel=False` com `motivo`/`campos_faltantes` explícitos quando falta premissa ou moeda não confirmada.
- **Uso pelo próximo**: `Valuation Reviewer` recebe o dict completo; `pareceres.py` usa o cenário-base como preço-alvo principal quando disponível.
- **Degradação**: nunca inventa WACC/crescimento/dívida — confirmado real com PETR4 (`disponivel=False`, motivo explícito de moeda, nos 3 runs).
- **Auditabilidade**: `fonte_premissas`/`data_base`/`origem_divida_liquida` sempre presentes quando disponível.
- **Veredito: APROVADO.**

### Valuation Reviewer (`data/coordenador_central/modelagem.py:revisar_valuation`)
- **Responsabilidade**: auditoria independente do DCF do Model Builder — ordem pessimista≤base≤otimista, rastreabilidade de fonte/data-base, disponibilidade de sensibilidade. Nunca recalcula com premissas próprias.
- **Dados recebidos**: o dict de saída do Model Builder (não re-busca nada).
- **IA real**: nenhuma — determinístico, checagens de dict/comparação numérica.
- **Saída**: `aprovado`/`achados`/`limitacoes`, ou bloqueado explicitamente quando o Model Builder não entregou DCF válido (caso real do PETR4 nos 3 runs: "Model Builder não entregou um DCF válido; revisão independente bloqueada.").
- **Uso pelo próximo**: `pareceres.py` expõe os achados como pontos contrários do parecer (bug histórico real já corrigido antes desta auditoria — `analista["dcf"]` chegou a ficar sempre vazio; confirmado nesta auditoria que `pareceres.py:487-499` hoje preenche `dcf` corretamente quando a revisão está disponível).
- **Veredito: APROVADO.**

### Earnings Reviewer (`data/earnings/reviewer.py` + `cvm_dre/cvm_balanco/cvm_dfc.py`)
- **Responsabilidade**: nota estruturada do resultado trimestral mais recente (DRE/balanço/DFC consolidados da CVM) — fato vs. interpretação rotulados, ROIC real (não anualizado), série histórica com tendência.
- **Dados recebidos**: ticker + ano/trimestre (derivado automaticamente via `data/eventos.py:periodo_pendente` quando o Coordenador não informa).
- **Fontes**: `dados.cvm.gov.br` (ITR/DFP, bulk CSV dentro de ZIP anual consolidado de todas as companhias).
- **IA real**: nenhuma — cálculo de variação YoY/margem/ROIC é aritmética sobre números extraídos literalmente do plano de contas oficial da CVM.
- **Saída real confirmada no e2e (PETR4, 2T2026)**: receita líquida +42,3% YoY, EBIT +137,5% YoY, lucro líquido +96,1% YoY, margem bruta +10,4 p.p., ROIC trimestral 6,6% (não anualizado) — números específicos do trimestre, não genéricos.
- **Degradação**: bloqueia explicitamente para bancos/seguradoras (plano de contas incompatível) e nunca deriva Q4 isolado por subtração.
- **Auditabilidade**: `fontes`/`limitacoes` sempre presentes; `mudancas_desde_ultima_versao` compara contra a última nota persistida do mesmo ticker.
- **Achado de performance (não de correção)**: ver "Achado corrigido" acima — é a fonte mais lenta do Comitê em cache frio (66-112s medidos no e2e real).
- **Veredito: APROVADO.**

### Memória de Research / RAG (`data/research/embeddings.py:buscar`)
- **Responsabilidade**: busca híbrida (estrutural + semântica + lexical) na biblioteca permanente de research já coletado.
- **Dados recebidos**: ticker/casa/pergunta opcionais.
- **IA real**: embeddings do Gemini (768 dims) para a parte semântica — exige `GEMINI_API_KEY`; sem ela, degrada para estrutural/lexical (confirmado real nesta auditoria: a chave não está configurada neste worktree, e o módulo degradou sem lançar exceção).
- **Saída**: lista de publicações com `casa/link/data/premissas/riscos`, nunca texto gerado livre.
- **Veredito: APROVADO** (comportamento correto mesmo sem a credencial opcional — não foi possível validar a busca semântica real neste ambiente por falta da chave, limitação declarada, não falha).

### Comparador de Casas (`data/research/comparador.py`) e Sinal Quantitativo (`data/research/sinal.py`)
- Confirmado por grep: **zero referência a Groq/OpenAI/Anthropic** em nenhum dos dois arquivos (881 + 176 linhas) — exatamente como documentado ("100% determinístico, zero IA").
- `sinal.py:calcular_sinal_comite` é um motor de pontos auditável (ROE/margem/alavancagem/FCF/crescimento/valuation relativo) — confirmado real no e2e: PETR4 pontuou +7 em 6 dimensões, sinal COMPRA, confiança ALTA, cada critério com `justificativa` e `fonte` explícitas.
- **Veredito: APROVADO.**

### Coordenador Central — Consolidação (`data/coordenador_central/consolidacao.py`) e Pareceres (`pareceres.py`)
- **Responsabilidade**: agregar os resultados de todos os especialistas nas 7 seções fixas (resumo/visão/evidências/divergências/pontos de atenção/conclusão/confiança), comparar recomendações entre os PRÓPRIOS especialistas do Comitê (não só fonte externa) e rebaixar confiança quando eles divergem.
- **IA real**: nenhuma na consolidação (confirmado pela própria docstring e pelo código — zero import de cliente de IA). Confirmado real no e2e: com 3 especialistas comparáveis convergindo em COMPRA, `divergencias.entre_analistas_comite.divergente=False` e confiança ficou ALTA (score de evidência) sem qualquer recálculo pela IA.
- **Veredito: APROVADO.**

### Coordenador Central — Síntese de IA (`data/coordenador_central/sintese_ia.py`)
- **Responsabilidade**: explicar em prosa, citando especialista por especialista, o porquê da convergência/divergência já calculada deterministicamente — nunca recalcula recomendação/preço-alvo/confiança.
- **IA real confirmada**: Groq `openai/gpt-oss-20b`, chamada real registrada no e2e (latência real medida, resposta não-genérica — ver evidência completa abaixo).
- **Veredito: APROVADO** (correto e funcional), **mas ver achado crítico acima — nunca acionado em produção.**

### Coordenador Central — Executor/Registro/Persistência (`executor.py`, `registro.py`, `persistencia.py`)
- Isolamento real por thread + timeout real (confirmado pelo bug encontrado e corrigido nesta auditoria), 8 especialistas catalogados (incluindo `radar_x`, documentado como indisponível por falta de credencial, nunca escondido do registro).
- Persistência confirmada real: a análise do PETR4 foi gravada em `coordenador_analises` com sucesso (`persistencia_analise_ok=True`, `_analise_id` real retornado) mesmo com a telemetria de IA híbrida falhando por tabela ausente (isolamento funcionando como desenhado).
- **Veredito: APROVADO COM RESSALVAS** — a ressalva é exclusivamente o timeout (corrigido nesta auditoria) e a dependência de uma migração de schema ainda não aplicada neste ambiente (não é código quebrado, é operação pendente, fora do escopo de um agente aplicar sozinho).

## Evidência real do teste ponta a ponta (PETR4, 3ª execução, timeout corrigido)

```
STATUS_EXECUCAO: PARCIAL (só por model_builder/valuation_reviewer bloqueados por moeda — não por falha)
_duracao_ms: 126295 (≈126s)
persistencia_analise_ok: True

Por especialista (disponivel / duracao_ms):
  memoria_research:          True /    226ms
  noticias:                  True /   6655ms
  catalisadores:             True /   7630ms
  resultados_corporativos:   True /  66447ms  (CVM 2T2026 real)
  comparador:                True / 102615ms  (research consolidado real)
  analise_ticker:             True / 118879ms (fundamentos + histórico CVM real)
  model_builder:             False /      0ms (moeda USD≠BRL — bloqueio correto, não falha)
  valuation_reviewer:        False /      0ms (Model Builder sem DCF — bloqueio em cascata correto)

Pareceres (recomendação | tese real, não genérica):
  market_researcher:   COMPRA | ROE 32,2%; margem líquida 24,0%; FCF positivo; ROIC 6,6%;
                        receita +42,3% YoY; P/L 0,61x a mediana setorial.
  earnings_reviewer:    COMPRA | Resultado 2T2026 — receita +42,3%, EBIT +137,5%, lucro +96,1% YoY;
                        margem bruta +10,4 p.p.
  valuation_comparables: COMPRA | P/L 4,1x vs. mediana setorial 6,7x; alvo mecânico R$ 73,36 (+63,4%),
                        rotulado explicitamente como "não é DCF, não é alvo de research".
  model_builder:        INSUFICIENTE | "moeda de origem dos fundamentos (USD) não confirmada como
                        igual à da cotação (BRL); conversão não é presumida."
  valuation_reviewer:   INSUFICIENTE | "Model Builder não entregou um DCF válido; revisão bloqueada."

Divergência entre especialistas do Comitê: divergente=False — 3/3 comparáveis concordam em COMPRA.

Sinal quantitativo do Comitê (data/research/sinal.py, determinístico):
  sinal=COMPRA, score=+7, confiança=ALTA, 6 dimensões avaliadas, 0 critério contrário.

Síntese de IA real (Groq openai/gpt-oss-20b, chamada de rede real, ~126s de fluxo total incluindo
esta chamada — latência real, não simulada):
  "Os três especialistas que emitiram recomendações concluíram em COMPRA, sustentando a tese com
  fundamentos sólidos: o Market Researcher destaca ROE de 32,2% e margem líquida de 24,0%; o
  Earnings Reviewer aponta crescimento de receita, EBIT e lucro líquido acima de 40%, 130% e 96%
  respectivamente; o Valuation Comparables observa um P/L de 4,1x, abaixo da mediana setorial,
  sugerindo upside de cerca de 63%. [...]"
  fator_decisivo: "P/L abaixo da mediana setorial e crescimento robusto de resultados"
  especialistas_citados: [market_researcher, earnings_reviewer, valuation_comparables]

Síntese de IA real (research qualitativo): disponivel=False, "sem publicações estruturadas para
este ticker na biblioteca permanente de research" — degradação honesta, zero chamada de IA
desperdiçada (nenhuma casa cobria PETR4 na biblioteca neste momento).
```

A síntese de IA acima cita exatamente os números reais do payload (32,2%, 24,0%, 40%/130%/96%, 4,1x, ~63%) — prova de que não é um texto genérico copiável para qualquer empresa, e prova de IA real (não apenas "a função foi chamada"): a latência observada (chamada de rede real à API da Groq, não determinística byte-a-byte entre execuções) e o conteúdo específico e corretamente atribuído por especialista são evidência direta de uma chamada de modelo real, não um mock.

## Decisão final do Comitê para PETR4

**COMPRA**, com confiança ALTA no sinal quantitativo determinístico e consenso (3/3) entre os especialistas qualitativos comparáveis. A decisão é totalmente rastreável: cada ponto do score cita a métrica e a fonte (`Fundamentos atuais`/`Série trimestral CVM`/comparação setorial); a síntese de IA não introduz nenhum número novo, só organiza os já calculados. O preço-alvo de R$ 73,36 (+63,4%) é explicitamente rotulado como estimativa mecânica por P/L setorial, **não um DCF** — o DCF ficou indisponível por um motivo real e correto (mismatch de moeda nos fundamentos de origem), não por falha do motor.

**Confio na decisão como "sinal determinístico de 1ª leitura bem fundamentado e auditável", não como recomendação de investimento completa** — exatamente o que o próprio `aviso` do sinal já declara ("sinal quantitativo inicial e auditável; não é recomendação personalizada nem probabilidade de retorno"). Faltam, nesta rodada específica: o DCF (bloqueado por moeda — resolveria exigindo o analista fornecer dívida líquida/FCF em BRL manualmente), e cobertura de research externa sobre PETR4 (nenhuma casa monitorada publicou algo estruturado no momento do teste). O Comitê foi honesto sobre essas duas lacunas em vez de disfarçá-las.

## Validação (testes)

```
python -m pytest tests/test_coordenador_central_fluxos.py -q                → 26 passed
python -m pytest tests/test_coordenador_central_*.py tests/test_jobs_coordenador.py \
  tests/test_comite_noturno.py tests/test_coordenador_sintese_ia.py \
  tests/test_coordenador_dcf*.py tests/test_coordenador_modelagem.py \
  tests/test_integracao_fluxo_comite_e2e.py tests/test_coordenador_tab_*.py -q → 191 passed
python -m pytest tests/ -k "coordenador or comite or comparador or sinal or research" -q
                                                                              → 923 passed
```

Nenhuma regressão. Teste novo: `test_analisar_ticker_usa_timeout_maior_pro_grupo_principal`.

**Não validado nesta auditoria** (limitação declarada, não escondida): busca semântica real do RAG (sem `GEMINI_API_KEY` neste worktree); persistência da telemetria de IA híbrida em `ia_hibrida_execucoes` (tabela ainda não migrada neste Supabase); comportamento da rodada completa de 20 tickers do Comitê Noturno sob o novo timeout (validado só por inspeção do orçamento: 20 × até 240s de pior caso ainda cabe no limite de 120min do workflow).
