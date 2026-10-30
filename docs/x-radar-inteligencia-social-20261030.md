# RADAR X — INTELIGÊNCIA SOCIAL (2026-10-30)

Pedido explícito do Rodrigo: transformar publicações relevantes do X
(Twitter) sobre o mercado financeiro brasileiro em informação
estruturada que alimente Research/Radar/Análises/Coordenador.

## 1. Estado da credencial (verificado, não presumido)

**Não há credencial configurada hoje** (`X_BEARER_TOKEN` ausente de
qualquer env/secrets do projeto, confirmado em 2026-10-30).

Isso já tinha sido investigado antes: FASE 4 da auditoria de
2026-10-09 (ver `PROGRESSO.md` linha ~4016, `BACKLOG.md`) pesquisou a
API do X e concluiu que não há caminho viável sem orçamento novo:

- O tier gratuito pra desenvolvedor novo foi descontinuado em
  06/02/2026 (o antigo já não incluía `/search`, só ~50 leituras/dia).
- O tier Basic ($200/mês fixo) foi forçado pra cobrança por uso
  (pay-per-use, ~US$0,005/leitura) e **não aceita mais assinante
  novo**.
- Busca/descoberta de posts recentes (`/2/tweets/search/recent` —
  exatamente o que este radar precisa, não só ler um post específico)
  parece exigir tier **Enterprise (a partir de US$42.000/mês)** ou uma
  camada paga específica — nenhuma fonte encontrada confirma acesso de
  busca incluído no pay-per-use básico.
- Scraping não-oficial (contornar login/API privada) foi descartado —
  viola os Termos de Serviço do X, mesmo princípio já aplicado a
  outras fontes do projeto (robots.txt é respeitado em todo coletor).

Reconfirmado em 2026-10-30: nada mudou nesses 21 dias.

**Decisão**: entregar a implementação completa e preparada (conector,
classificação, relevância/credibilidade, cruzamento, persistência,
UI, testes), com o conector desligado e documentado, sem simular
nenhuma coleta real — exatamente como pedido na seção 11 do pedido
original. `data/x_signals.py:status_credencial()` faz a verificação
real (1 chamada mínima) **só quando** `X_BEARER_TOKEN` existir — nunca
antes disso.

## 2. O que falta pra ligar de verdade

1. Decidir orçamento: Basic pay-per-use (se abrir pra novo assinante)
   ou Enterprise (~US$42k+/mês) — nenhum dos dois confirmado como
   suficiente pra busca sem teste real.
2. Confirmar com o provedor (ou testando direto) se o tier escolhido
   inclui `/2/tweets/search/recent` com volume suficiente pro universo
   monitorado (ver `data/x_radar/__init__.py`: ~16 tickers, 7 contas
   institucionais, termos/setores/macro).
3. Configurar `X_BEARER_TOKEN` (env var) ou
   `st.secrets["x"]["bearer_token"]` (ver `.streamlit/secrets.toml.example`).
4. Rodar `sql/x_radar.sql` no Supabase (idempotente, até pode ser
   rodado antes da credencial existir — a tabela só fica vazia).

Nenhuma mudança de código é necessária além de configurar a
credencial — `data/x_signals.py:status_credencial()` detecta e valida
sozinho na próxima execução do `jobs/coordenador.py`.

## 3. Arquitetura (reuso, não duplicação)

- `data/x_signals.py` — contrato de dados (já existia, FASE 4) +
  conector real (paginação/dedup/rate-limit, novo) — só chama rede se
  `status_credencial()` confirmar acesso real.
- `data/x_radar/` (novo pacote) — único importador de
  `data.x_signals` (ver `tests/test_x_signals.py` teste 7):
  - `__init__.py` — universo configurável (contas/termos/tickers/
    setores/macro, edição sem migração) + `executar_ciclo()`.
  - `conector.py` — monta a query do universo, delega pro conector.
  - `classificador.py` — reusa `config.obter_credenciais_groq()` +
    `data/ia_cache.py` (cache global já existente) — zero arquitetura
    de IA nova.
  - `relevancia.py` — relevância (explicável, soma de fatores) e
    credibilidade (nunca inventada sem histórico) separadas.
  - `cruzamento.py` — reusa `data/market_researcher.py:
    cobertura_cruzada_casas` e `data/news.py:obter_noticias` — nunca
    promove sozinho pra "confirmado", só contexto.
  - `store.py` — persistência (`sql/x_radar.sql`), nunca persiste
    classificação que falhou como "sem relevância".
- `jobs/coordenador.py` — 3ª função independente
  (`executar_ciclo_radar_x`), mesmo padrão de backoffice/síntese —
  indisponível-e-documentado não conta como falha do job.
- `ui/research_tab.py:render_radar_x` — nova subaba RESEARCH › Radar X
  (`ui/navegacao.py`), sempre mostra a saúde real do conector no topo.

## 4. Contas e termos configurados inicialmente

Ver `data/x_radar/__init__.py` (editável sem migração):

- 16 tickers foco (PETR4, VALE3, ITUB4, BBDC4, ABEV3, WEGE3, B3SA3,
  RENT3, SUZB3, GGBR4, CSNA3, PRIO3, RAIL3, LREN3, MGLU3, BBAS3).
- 5 casas de research já presentes no projeto (Genial, XP, BTG, Nord,
  Monte Bravo) + Banco Central + CVM.
- Gestores/investidores pessoa física: lista vazia de propósito —
  adicionar um handle sem verificar se é conta real/pública seria
  inventar fonte; Rodrigo preenche depois de validar cada uma.
- Termos de ações, setores e assuntos macro conforme pedido (seções
  3.A/3.D/3.E do pedido original).

## 5. Custo e limites a considerar antes de aprovar

| Tier | Custo | Busca/descoberta confirmada? |
|---|---|---|
| Free (novo dev) | — | Descontinuado 06/02/2026 |
| Basic | US$200/mês fixo → pay-per-use (~US$0,005/leitura) | Não aceita assinante novo; busca não confirmada no pay-per-use |
| Enterprise | A partir de ~US$42.000/mês | Provável, não confirmado sem contato comercial |

Nenhum destes foi testado com credencial real — os valores vêm de
pesquisa pública (2026-10-09, reconfirmada 2026-10-30), não de uma
tentativa de compra.
