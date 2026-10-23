# RESEARCH institucional — reorganização + gate de fidelidade (23/10/2026)

Branch `feat/research-area-20261023` (base `main@d4681cf`, inclui PR #134/#135/#136).
Missão: transformar MINHA TESE numa plataforma de Equity Research institucional.

## 1. Diagnóstico — o que já existia (reaproveitado, não duplicado)

Antes de programar, mapeei o repositório real e achados de sessões concorrentes do
mesmo dia:

| Peça já existente | Onde | O que faz |
|---|---|---|
| Coleta de 5 casas (Genial Analisa, XP, BTG, Monte Bravo, Genial Lives) | `data/research/__init__.py:CASAS` + `genial.py`/`xp.py`/`btg.py`/`montebravo.py`/`genial_lives.py` | Coleta real (JSON embutido/API/RSS), upsert por link, nunca inventa dado |
| Feed/Revisões/Por ativo | `ui/research_tab.py:render_research` (antes em RADAR › Research) | Feed filtrável, Research Radar (NOVO/MUDANÇA DE RECOMENDAÇÃO), painel por ticker da watchlist, fontes clicáveis |
| Saúde dos coletores de Research | `data/saude_dados.py` (PR #136, mesmo dia) | Categoria "Research" já instrumentada p/ as 5 casas - estado real (nunca inflado), antes só visível em MAIS › Saúde dos Dados (admin) |
| Levantamento de casas candidatas | `docs/research-fontes-20261022.md` (mesma data, outra sessão) | Itaú BBA/Safra/Rico/Ágora/BB Investalk etc. investigados com evidência real (runner do GitHub Actions) - todos bloqueados ou sem feed |
| Padrão de versionamento/dedup/FATO-vs-INTERPRETAÇÃO | `data/earnings/reviewer.py` (PR #136, "Módulo 2") | Referência de estilo reaproveitada no desenho do gate de qualidade (não código compartilhado - `earnings` cobre resultados trimestrais via CVM/SEC, domínio diferente de research de corretora) |
| Market Researcher da Anthropic | `docs/market-researcher-integracao.md` (sessão anterior, mesmo projeto) | Confirmado de novo: é prompt/skill pra Claude Code com MCP de CapIQ/FactSet - nada instalável em produção. Não refeito aqui. |

**Conclusão**: a maior parte da "plataforma de research" pedida já tinha peças reais
e testadas, espalhadas em 3 áreas de navegação diferentes sem nenhum lugar que as
organizasse como "RESEARCH". O trabalho de maior valor era consolidar essas peças e
fechar o gap real que faltava: nenhum gate de fidelidade entre resumo e texto
original.

## 2. O que foi implementado

### 2.1 Gate de fidelidade do resumo (`data/research/qualidade.py`)

Três checagens determinísticas (zero chamada de IA nova), hookadas em
`resumir.py:_gerar_resumo` **no momento da geração** - única janela em que o texto
original existe (o projeto nunca persiste o relatório completo, só o resumo):

1. `numeros_sem_base`: todo número com unidade financeira (%, R$, US$) no resumo
   precisa ter base no texto original (tolerante a `,`/`.` como decimal, intolerante
   a número realmente novo).
2. `tickers_sem_base`: todo ticker citado no resumo precisa aparecer no texto
   original ou no título.
3. `causalidade_sem_evidencia`: toda cláusula causal explícita ("impulsionado por",
   "devido a" etc.) precisa ter palavra de conteúdo em comum com o original -
   adaptado do mesmo padrão já comprovado em produção em `data/news.py`
   (`_causalidade_sem_evidencia`, achou um bug real em 2026-10-18), reescrito aqui
   (não importado) pra não tocar num arquivo com 3 PRs abertos concorrentes hoje.

Resumo reprovado: nunca é cacheado nem persistido - `motivo_indisponivel` genérico
("indisponivel") pra UI, motivo detalhado só no log técnico (nunca expõe trecho do
resumo pro usuário final).

**Dois bugs reais encontrados e corrigidos ao escrever os testes** (antes de
qualquer commit): (1) número no fim de frase ("R$ 48,00.") engolia o ponto final no
match da regex, corrompendo a normalização decimal; (2) a própria palavra do
conector causal ("impulsionado") entrava na comparação de evidência, mascarando uma
causa realmente inventada que usava o mesmo verbo em outro lugar do texto.

### 2.2 Casas de Análise (`data/research/casas_status.py` + UI)

Camada de leitura pura - zero coleta nova, zero tabela nova: combina `CASAS`
(método de acesso, se a coleta roda no Cloud) com `saude_dados.obter_painel_saude()`
filtrado pra categoria "Research" (já existia, só não tinha exposição não-admin).
Casas candidatas não implementadas **não aparecem aqui** - ficam só no
`docs/research-fontes-20261022.md`, pra não duplicar/inflar cobertura.

### 2.3 Nova área RESEARCH (reorganização de navegação, `ui/navegacao.py`)

- `radar > research` → `research > feed` (mesmo `render_research`, zero mudança de
  conteúdo).
- `analises > teses` → `research > teses`, rotulada **"Minha Tese"** (secundária,
  como pedido - permanece a mesma implementação de PR #134, não PR #138 que ainda
  está em revisão separada).
- `research > casas` (nova).
- `analises` perde "Teses", fica só Empresas/Fundamentos/Valuation (múltiplos não é
  conteúdo de casa de research, mantido separado de propósito).

## 3. Casas avaliadas — status real (não inflado)

| Casa | Acesso | Estado real (painel de saúde, categoria Research) |
|---|---|---|
| Genial Analisa | só via `coletor_local.py` (bloqueada no Cloud - WAF) | depende da última execução local do Rodrigo |
| XP Investimentos | só via `coletor_local.py` (bloqueada no Cloud - Akamai 403) | idem |
| Genial (Lives) | automática (Cloud + local) | YouTube RSS, exceção documentada de robots.txt |
| BTG Pactual Research | automática (Cloud + local) | API pública, filtra tier AREA_PUBLICA |
| Monte Bravo | automática (Cloud + local) | adicionada 22/10/2026, feed RSS público |
| Itaú BBA, Safra, Rico, Ágora, BB Investalk, outras | — | **investigadas e bloqueadas** (403/sem feed) - ver `docs/research-fontes-20261022.md`, não reinvestigado aqui |

Não executei nenhuma coleta real nesta sessão (sem acesso de rede às fontes neste
sandbox) - o painel reflete o que `coletores_status` já tem persistido de execuções
reais anteriores (Streamlit Cloud/GitHub Actions/`coletor_local.py` do Rodrigo).

## 4. Claude Market Researcher — confirmação, não nova investigação

Reconfirmado o achado da sessão anterior (`docs/market-researcher-integracao.md`):
os plugins `market-researcher`/`equity-research` da Anthropic são prompts/skills
para Claude Code com `mcp__capiq__*`/`mcp__factset__*` - nada para "instalar" em
produção. Nenhuma chamada à API da Claude foi introduzida (o projeto usa Groq,
gratuito, em toda a pipeline de IA - `config.obter_credenciais_groq()`). O gate de
qualidade desta sessão é **determinístico** (regex/comparação de tokens), não uma
chamada de modelo nova - funciona com ou sem Claude/Groq disponível.

## 5. Banco de dados

**Nenhuma alteração de schema.** Nenhum `.sql` novo, nenhuma tabela nova, nenhuma
migration. `casas_status.py` e `qualidade.py` são camadas de leitura/validação
puras sobre dados já persistidos.

## 6. Pendência avaliada e não implementada: preservar revisão de `research_itens`

**Gap real identificado** (Fase 5 da missão): `store.salvar_itens` faz upsert por
`link` - se uma casa revisar um relatório no MESMO link (resumo/preço-alvo/
recomendação mudam), a versão anterior é sobrescrita sem deixar rastro (diferente
de `research_recomendacoes_historico`, que só cobre preço-alvo/recomendação
estruturados da Genial, não o resumo/título como um todo).

**Decisão**: documentar, não implementar nesta sessão. Motivo: exigiria uma tabela
nova (ex: `research_itens_revisoes`, mesmo padrão append-only de
`earnings_reviews`) - mudança de schema real, e o tempo restante da sessão foi
priorizado pro gate de fidelidade (gap mais crítico e já sem nenhuma cobertura) e
pela reorganização de navegação (pedido explícito da Fase 2). Design recomendado
pra uma sessão futura: hook em `store.salvar_itens`, antes do upsert, comparando
`resumo`/`titulo`/`preco_alvo`/`recomendacao` atuais vs. novos pro mesmo link; se
diferentes, INSERT da versão antiga em `research_itens_revisoes` antes do upsert
sobrescrever.

## 7. Testes executados

- `data/research/qualidade.py`: 12 testes (`tests/test_research_qualidade.py`) -
  números/tickers/causalidade com e sem base, formatos de número equivalentes,
  prioridade de rejeição, casos vazios.
- Integração do gate em `resumir.py`: 3 testes
  (`tests/test_research_resumir_gate.py`) - resumo reprovado nunca é persistido,
  resumo fiel é persistido normalmente, motivo detalhado nunca vaza pra UI.
- `data/research/casas_status.py`: 5 testes (`tests/test_research_casas_status.py`).
- `ui/research_tab.py:render_casas_analise`: 4 testes
  (`tests/test_research_casas_analise_ui.py`, bare-mode com `.__wrapped__`).
- `ui/navegacao.py`: 2 testes atualizados (ordem/subabas das áreas) +
  `test_preferencia_antiga_de_abas_esconde_subabas` ajustado pro novo
  comportamento (área RESEARCH sobrevive só com "Casas de Análise", que não
  depende de aba antiga).
- Validação visual real (Playwright, não AppTest): Casas de Análise em 1366×768 e
  390×844 - confirmado **sem overflow horizontal da página** (`document.body.
  scrollWidth == clientWidth == 390`, tabela densa rola só internamente, mesmo
  padrão já usado em `.rq-tabela`/RADAR DE QUEDAS). Achado e corrigido durante a
  validação: timestamps de exemplo no harness geravam "há -429min" (fixture datada
  no futuro, não bug de produção) - corrigido pra timestamps relativos ao momento
  real do teste.
- `python -m pytest -q`: **1321 passed** (rodado 2x pra confirmar - uma rodada
  isolada teve 7 falhas em arquivos que eu não toquei, não reproduziu numa segunda
  rodada limpa; registrado como flakiness pré-existente da suíte, não investigado
  a fundo por não ser desta mudança).
- `python -m compileall`: limpo.
- CI (`testes.yml`): a confirmar no próprio PR.

## 8. Riscos e pendências

1. **Conflito esperado com PR #138** (ainda não mergeado, também mexe em
   `ui/radar_tab.py:render_teses` e no despacho de `analises > teses`) - este PR
   só move a ROTA (`app.py`/`navegacao.py`), não o conteúdo de `render_teses`;
   ainda assim, os dois PRs tocam `app.py` na mesma região e vão conflitar em
   rebase/merge. Resolução fica pra quem mergear por último.
2. Validação end-to-end em produção (Supabase real, coleta real) não foi feita -
   sem credencial/rede neste sandbox.
3. Revisão de `research_itens` (seção 6) documentada, não implementada.
4. Normalização de recomendação (COMPRA/NEUTRO/VENDA a partir do texto livre da
   fonte) não foi implementada nesta sessão - ficou de fora do escopo priorizado.
5. Gate de qualidade roda só pra resumos NOVOS a partir de agora - resumos já
   persistidos antes desta mudança não são reavaliados retroativamente (consistente
   com o projeto nunca guardar o texto original pra reavaliar depois).

## 9. Branch, SHA e PR

Branch `feat/research-area-20261023`. PR será aberto nesta mesma sessão - link e
SHA final registrados no corpo do PR. **Sem merge automático**, aguardando
autorização.
