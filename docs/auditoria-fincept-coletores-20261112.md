# Auditoria: técnicas de coleta do Fincept Terminal vs. Pregão (2026-11-12)

## Aviso de licença — leia antes de aplicar qualquer coisa deste documento

O [Fincept Terminal](https://github.com/Fincept-Corporation/FinceptTerminal) é
licenciado **AGPL-3.0-or-later**. O Pregão é um serviço de rede (Streamlit
Cloud) — se copiássemos código-fonte do Fincept pra dentro do Pregão, a AGPL
provavelmente obrigaria o Pregão inteiro (todo o código servido aos usuários
via rede) a virar AGPL também, o que muda a natureza do projeto.

**Por isso nada neste documento é código copiado.** Tudo abaixo é
IDEIA/ESTRATÉGIA (quais fontes usar, como descobrir documento novo, como
deduplicar, como classificar, como registrar confiabilidade) extraída por
leitura do repositório, pra reimplementação independente em Python/Streamlit
com a cara do Pregão. Nenhum arquivo do Fincept foi colado; nenhum trecho
abaixo é um diff aplicável — é descrição em prosa do mecanismo.

Clone de auditoria: `git clone https://github.com/Fincept-Corporation/FinceptTerminal`
feito fora do worktree do Pregão (pasta temporária), apagável a qualquer
momento — nunca foi commitado neste repositório.

## O que o Fincept é, de fato

Não é um terminal Python standalone como o Pregão. É um app **C++/Qt**
(`fincept-qt/`) que roda ~200 scripts Python como *subprocessos* — cada
`*_data.py` é uma CLI isolada que recebe `<command> [args]` e imprime um
único JSON no stdout (`{"error": "..."}` em caso de falha; nunca `NaN`/
`Infinity`). O C++ nunca importa Python; só o invoca e lê o JSON. Isso é uma
diferença estrutural grande (Pregão é 100% Python/Streamlit, sem fronteira de
processo entre coleta e UI) — a maior parte da arquitetura de orquestração do
Fincept não se aplica diretamente.

**Não existe no Fincept nenhum equivalente a "casas de research" (BTG/XP/
Genial/JPM/BofA/...).** Ele não coleta relatórios de banco de investimento.
O que ele chama de "analyst targets / recommendations / upgrades-downgrades"
vem todo de `yfinance` (campos agregados que o Yahoo Finance já consolida de
várias casas, sem acesso ao relatório original). Isso limita bastante a
comparabilidade direta com o problema central do Pregão (coletar o dado
*primário* de cada casa) — a técnica mais próxima e transferível está nas
camadas de **confiabilidade/proveniência de dado**, **cache/degradação** e
**catalogação automática de conectores**, não na coleta de research em si.

## Provedores de dados financeiros integrados

`fincept-qt/scripts/` tem ~200 arquivos `*_data.py`, cobrindo bancos
centrais/macro, estatística governamental, mercados/equities, cripto,
energia/clima, geoespacial/geopolítica, academia. Mistura:
- **Oficiais gratuitos sem chave**: SEC EDGAR, FRED, bancos centrais (ECB,
  BoE, BoJ, BCB...), estatísticas de governo (Census, Eurostat, IBGE-like
  por país).
- **Gratuitos com chave**: Alpha Vantage, FMP, EODHD, CoinGecko Pro etc.
  (`key_required: true` registrado por conector — ver seção de saúde).
  **Pagos/dados de terceiro via scraping leve**: yfinance (não-oficial, mas
  estável), TradingView, alguns `*_api.py` de governo com HTML.
- Nenhuma dessas fontes é "research de banco" — é dado de mercado/macro
  bruto. O design de descoberta é quase todo **API estruturada** (JSON/XBRL/
  SDMX), não scraping de HTML com sitemap como o Pregão faz pra casas de
  research (BTG, bancos globais etc.) — o Fincept simplesmente não enfrenta o
  problema "este banco não publica nada em formato de máquina".

## Notícias e eventos corporativos

- `fetch_company_news.py`: wrapper fino sobre a lib `GNews` (Google News
  RSS). Normaliza data RFC-822 → ISO, filtra descrição redundante (quando é
  só o título repetido), ordena por `published_date` decrescente. **Não tem
  deduplicação nem estratégia de descoberta própria** — delega 100% pro
  Google News. Mais simples que o que o Pregão já tem em `data/news.py`
  (que, pela auditoria de `qualidade.py`, já faz checagem de
  causalidade-sem-evidência e contradição título-resumo). Não há técnica aqui
  que valha trazer.
- `economic_calendar.py` (Forex Factory): a técnica real está no **cache de
  dois níveis com degradação graciosa** — serve uma cópia "fresca" (≤15 min)
  normalmente; se a fonte responder 429 (rate limit) ou cair, serve uma
  cópia de até 6 horas em vez de falhar (comentário explícito no código:
  "rate-limited / offline: a few hours old is still this week"). Escreve o
  cache com `tmp + os.replace` (atômico — nunca lê um arquivo de cache
  truncado por uma escrita interrompida).

## Dados fundamentalistas e normalização

- **SEC EDGAR** (`sec_data.py`, `sec_xbrl_data.py`, `fincept_mcp/edgar/`):
  usa a API oficial `data.sec.gov`. Pontos de disciplina que valem nota:
  - User-Agent obrigatório e descritivo com e-mail de contato (a SEC bloqueia
    quem não identifica o cliente) + `time.sleep(0.1)` entre requisições pra
    respeitar o limite de taxa — isso é exigido pela própria SEC, não
    opcional.
  - CIK normalizado pra 10 dígitos com zero-padding antes de montar qualquer
    URL (`_normalize_cik`).
  - Lista fixa de ~19 *tags* da taxonomia US-GAAP (`Revenues`,
    `NetIncomeLoss`, `Assets`...) como vocabulário canônico pra pedir fatos
    financeiros estruturados (XBRL) — uma forma de normalizar "qual campo eu
    peço" entre empresas diferentes.
  - Dicionário fixo de códigos de transação de insider trading (A/C/D/.../Z
    → significado em texto) pra nunca expor o código bruto pro usuário.
  - `HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=3)` —
    reaproveita conexão e tenta de novo automaticamente em erro transitório.
- **yfinance** (`relationship_map.py`, `fetch_peers.py`): não normaliza nada
  de especial (usa os campos que o Yahoo já entrega), mas tem duas ideias de
  proveniência que valem destaque (seção seguinte).

## Monitoramento de saúde/falha de coletor

Duas peças, nenhuma delas tão robusta quanto o que o Pregão **já tem** em
`data/coletores_status.py` (classificação de causa de erro por palavra-chave
— tabela ausente / credencial-ou-conexão / desconhecido —, preservação do
`ultimo_sucesso_em` em falha pontual, nunca lança excepion), mas com uma
diferença estrutural interessante:

1. **`connector_overrides.json`**: arquivo único, versionado, com decisão
   humana por conector. Dois campos relevantes:
   - `"key_required": true|false` — nunca adivinhado; o gerador (ver item 2)
     **falha o build** se um conector com chave de API não tiver essa decisão
     registrada ("a new keyed script cannot ship unreviewed").
   - `"broken": "<motivo>, checked YYYY-MM-DD"` — texto curto, datado,
     explicando por que uma fonte não funciona (ex.: UNCTADstat exige
     client-id/secret e só oferece bulk em 7z). O conector **continua
     navegável na UI** mas sem ferramenta de IA associada. É um registro
     estruturado e versionado em git, revisado por humano, bem menor que a
     prosa riquíssima que o Pregão já mantém no docstring de
     `data/research/__init__.py` — mas sendo um campo de dado (não só prosa),
     é *consultável por código* sem parsear texto.

2. **`.github/scripts/gen_data_connectors.py`**: lê todo `*_data.py` com
   `ast` (nunca importa/executa o script) e **gera automaticamente** o
   catálogo (`data_connectors.json`) que a UI, as ferramentas de IA (MCP) e
   os nós de workflow leem — descrição (docstring do módulo), lista de
   comandos aceitos, dica de argumento por comando, variáveis de ambiente de
   credencial realmente usadas (lidas E referenciadas depois — uma variável
   lida e nunca usada é descartada do catálogo). Roda com `--check` em CI:
   falha o pipeline se o catálogo gerado estiver desatualizado em relação aos
   scripts. Efeito prático: é estruturalmente impossível a documentação de
   "quais comandos o coletor X aceita" ficar desalinhada do código, porque
   ela é derivada do código, não escrita à mão em paralelo.

## Comparação direta com o estado real do Pregão (origin/main, 2026-11-12)

Auditado via `git show origin/main:<path>` (não o checkout local, que pode
estar defasado):

| Dimensão | Fincept | Pregão hoje |
|---|---|---|
| Unidade de coleta | subprocesso Python isolado por fonte, contrato JSON fixo | módulo Python por casa em `data/research/*.py`, chamado in-process |
| Descoberta de doc novo | quase sempre API estruturada (JSON/XBRL) | sitemap + BeautifulSoup + fixture real por casa (BTG tem API própria) |
| Dedupe | nenhuma central (delega a cada fonte) | `store.salvar_itens` deduplica por `link` antes do upsert, cobre o caso de upsert duplicado no mesmo lote (achado real com a XP) |
| Saúde/falha | `connector_overrides.json` (`broken`, `key_required`, datado) + nenhum histórico de tentativa | `coletores_status.py`: histórico por tentativa, classificação de causa de erro, preserva último sucesso — mais robusto que o Fincept nisso |
| Qualidade do resumo/extração por IA | não existe equivalente (não há "research" pra resumir) | `qualidade.py`: gate determinístico contra alucinação (número sem base, ticker sem base, causalidade sem evidência) antes de persistir — mais robusto que qualquer coisa vista no Fincept |
| Catálogo de capacidades | gerado automaticamente via AST + CI `--check` | nenhum — a lista de casas/comandos vive só no docstring de `__init__.py` e no código de cada módulo |
| Cache com degradação graciosa sob rate-limit | sim (`economic_calendar.py`, 15min fresco / 6h fallback, write atômico) | cooldown de 10 min após falha (`_COOLDOWN_FALHA_S`) que apenas **para de tentar** — não serve dado staleado como substituto |
| Proveniência de dado derivado/fallback | `peer_source: "industry:X"` vs `"generic_fallback"`, com aviso explícito de não usar fallback em valuation relativa | não observado um campo equivalente nos coletores atuais |

## As 5 técnicas mais valiosas pra trazer pro Pregão (depois do lote atual mergear)

1. **Catálogo de conectores gerado automaticamente + gate de CI.** Com 15+
   casas (BTG, Genial, XP, Safra + 4 bancos globais + o lote do Agente B:
   Goldman/UBS/Barclays/HSBC/Deutsche/Jefferies + Itaú BBA/Bradesco BBI/
   Santander/BB/Ágora/Guide), o risco real é a lista em
   `data/research/__init__.py` (CASAS) e qualquer tabela de status na UI
   divergirem silenciosamente do que cada módulo realmente faz. Um script
   `scripts/gen_research_catalogo.py` que lê (via `ast`, sem importar) cada
   `data/research/<casa>.py`, extrai docstring + `disponivel`/motivo de
   bloqueio + nome de função coletora, e falha em CI se o catálogo commitado
   estiver desatualizado, fecha essa lacuna de forma estrutural — mesmo
   padrão do Fincept, aplicado ao vocabulário do Pregão.
2. **Registro estruturado (não só prosa) de "por que esta fonte está
   desativada", datado.** O docstring de `__init__.py` hoje é excelente em
   riqueza de investigação, mas é texto livre — a aba SAÚDE DOS DADOS não
   pode consultá-lo por código sem parsear. Um campo por casa (ex. em
   `CASAS` ou numa tabela nova) como `bloqueio: {motivo: str,
   checado_em: date}` deixaria essa informação já pesquisada
   *consultável* pela UI sem reparsear a investigação toda vez.
3. **Cache de degradação graciosa pra fontes de calendário/evento
   corporativo com rate limit conhecido.** Hoje o cooldown de 10 min
   (`_COOLDOWN_FALHA_S`) só evita martelar uma fonte quebrada — não tem
   fallback de "serve o que tinha antes, mesmo staleado, em vez de nada".
   Pra fontes tipo calendário de earnings/eventos (se vier a existir um
   coletor desse tipo), vale o padrão de dois TTLs (fresco curto, fallback
   bem mais longo só acionado em erro) com escrita atômica de cache.
4. **Proveniência explícita em dado derivado/fallback.** Onde o Pregão hoje
   classifica setor/empresa/peer por heurística (quando a IA ou a fonte não
   confirma diretamente), marcar explicitamente a origem do dado (ex.:
   `origem: "casa"` vs `origem: "inferido"`) e, no caso de inferência,
   impedir ou avisar antes de usá-la em comparação direta — mesmo princípio
   do `peer_source: generic_fallback` do Fincept, que existe justamente pra
   impedir comparação errada.
5. **Disciplina de identificação e paginação respeitosa em fontes oficiais
   tipo API (SEC-like).** Pro caso de o Pregão vir a consumir uma API
   regulatória/oficial direta (ex. CVM/B3 se existir endpoint estruturado),
   vale copiar o padrão: User-Agent descritivo com contato, delay fixo por
   requisição, `HTTPAdapter` com `max_retries` e pool de conexão — reduz
   risco de bloqueio por comportamento de scraper agressivo.

## O que o Pregão já faz melhor (pra não subestimar o que existe)

- `qualidade.py` (gate anti-alucinação do resumo via número/ticker/
  causalidade sem base) não tem equivalente no Fincept — o Fincept nem
  resume texto original via LLM nesse fluxo.
- `coletores_status.py` classifica a CAUSA real de uma falha (tabela
  ausente vs credencial/RLS vs desconhecido) por sinal de texto, com
  histórico de tentativa por nome; o Fincept só tem um campo estático
  `broken` com motivo e data, sem histórico de tentativas.
- Checagem de `robots.txt` antes de qualquer coleta HTML (`base.py:
  permitido`) é mais rigorosa do que qualquer coisa observada nos
  conectores do Fincept auditados (que são, em sua maioria, APIs
  estruturadas, não scraping de HTML institucional).
- `store.salvar_itens` já deduplica por link dentro do mesmo lote (achado
  real com a XP) e faz retry sem a coluna nova quando o schema do usuário
  está desatualizado — mais defensivo que o upsert simples visto no
  Fincept.

## Arquivos do Fincept citados nesta auditoria

Todos em `FinceptTerminal/fincept-qt/` (exceto o gerador, que é raiz do
repo) — citados só como referência de leitura, nada copiado:
- `scripts/README.md` — arquitetura dos conectores e contrato de saída.
- `scripts/connector_overrides.json` — decisões humanas por conector
  (`key_required`, `broken`, `docs_url`).
- `.github/scripts/gen_data_connectors.py` — gerador estático do catálogo.
- `scripts/fetch_company_news.py` — wrapper de notícias (sem dedupe própria).
- `scripts/economic_calendar.py` — cache de dois níveis com fallback.
- `scripts/sec_data.py`, `scripts/sec_xbrl_data.py` — EDGAR/XBRL, CIK,
  taxonomia, códigos de transação de insider.
- `scripts/relationship_map.py`, `scripts/fetch_peers.py` — proveniência de
  peer (`peer_source`) e `data_quality` por chamada.

## Arquivos do Pregão auditados (origin/main)

- `data/research/__init__.py`, `data/research/store.py`,
  `data/research/base.py`, `data/research/qualidade.py`,
  `data/research/resumir.py`, `data/coletores_status.py`.
