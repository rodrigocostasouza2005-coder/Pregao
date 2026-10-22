# Fontes de research — investigação de novas casas (2026-10-22)

Frente C: aumentar o número de casas de research coletáveis de forma
legítima, reaproveitando a arquitetura existente (`CASAS` em
`data/research/__init__.py`, rodando pelo `coletor_local.py`, sem
agendador novo).

## Resultado desta rodada

**Nenhum coletor novo foi implementado.** A regra da frente era só
implementar casa com **amostra real** de resposta (feed/API) provando
conteúdo de research público e atual — e, deste ambiente, não foi
possível obter nenhuma amostra real:

- **Shell/sandbox:** sem saída de rede para os sites das casas — o proxy
  de saída recusa o túnel (`curl https://www.infomoney.com.br/feed/` →
  `CONNECT tunnel failed, response 403`, 22/10 ~19:07 UTC).
- **Ferramenta WebFetch:** falhou para **todos** os hosts testados com
  `getaddrinfo ENOTFOUND`, inclusive hosts de controle sem relação com
  research (`www.python.org`, `content.btgpactual.com`) — ou seja, falha
  de DNS da própria ferramenta, não bloqueio das casas. Hosts testados:
  `blog.toroinvestimentos.com.br/feed/`, `blog.orama.com.br/feed/`,
  `www.economiaemdia.com.br`, `riconnect.rico.com.vc/feed/`,
  `blog.itau.com.br/privateinsights/feed`,
  `oespecialista.safra.com.br/feed/` (22/10, 19:06–19:15 UTC).
- **Ferramenta WebSearch:** funcionou, mas só devolve títulos/URLs
  indexados e resumos — **não** é amostra de resposta do feed/API, não
  serve de fixture e não prova que o endpoint responde. Foi usada só
  para mapear candidatos e datas aproximadas do último conteúdo visto.

Escrever coletor "às cegas" (formato de feed suposto, fixture inventada)
violaria a regra de nunca inventar dados e criaria código frágil — por
isso a decisão foi documentar e deixar a implementação para quando houver
amostra real (ver "Próximos passos").

Persistência em produção: **não verificada** a partir deste ambiente
(nada novo foi ligado em `CASAS`; as casas existentes seguem sendo
verificadas pela próxima execução do workflow `coletores-nuvem` no
GitHub Actions).

## Tabela de candidatos

Legenda de resultado:
- **implementada** — já existe coletor ativo;
- **bloqueada** — feed/API existe mas o acesso é negado (WAF/403/auth);
- **só cliente** — conteúdo restrito a clientes/login/app;
- **sem conteúdo público** — nada público e atual encontrado;
- **inacessível pela ferramenta** — há indício de conteúdo público, mas
  não deu para capturar amostra deste ambiente (pendente de verificação).

Evidência = URL vista via WebSearch em 22/10/2026 + data do item mais
recente que apareceu (data do slug/título/resumo; **não** confirmada por
leitura direta da página).

| Casa | Fonte oficial candidata | Tipo | Resultado | Evidência (último item visto) | Observações |
|---|---|---|---|---|---|
| BTG Pactual | `content.btgpactual.com` (API content-hub) | API JSON | **implementada** | coletor ativo (`btg.py`) | Filtra `tier == AREA_PUBLICA`. |
| Genial (lives) | YouTube RSS do canal | RSS | **implementada** | coletor ativo (`genial_lives.py`) | Exceção deliberada de robots já documentada; não replicar. |
| Genial Analisa | `analisa.genialinvestimentos.com.br` | HTML/`__NEXT_DATA__` | **bloqueada** (timeout/WAF no Cloud) | coletor existente | Só via `coletor_local.py`. |
| XP | `conteudos.xpi.com.br/wp-json/wp/v2` | WP REST | **bloqueada** (Akamai 403) | coletor existente | Idem. |
| Itaú BBA / Itaú Macro | `blog.itau.com.br/privateinsights/` e `itau.com.br/investimentos/analises/` | blog (provável WordPress) / páginas | **inacessível pela ferramenta** — candidato nº 1 | `blog.itau.com.br/privateinsights/focus-inflacao-pib-revisa-cenario-itau-bba-el-nino-31-08-26` (31/08/2026); `itau.com.br/investimentos/analises/macro-visao-atividade-decepciona-2t26` (~17/08/2026) | Conteúdo macro público e recorrente (revisões de cenário do Itaú BBA). Feed não confirmado; em 2026-09-23 a raiz `itau.com.br/itaubba-pt` deu 403 do sandbox (BACKLOG.md). |
| Safra | `oespecialista.safra.com.br` | WordPress | **inacessível pela ferramenta** (REST bloqueada) | `oespecialista.safra.com.br/wp-content/uploads/2026/02/Safra-Report-Fevereiro-2026.pdf` (02/2026); `.../safra-bens-de-capital-2026/` | REST API fechada por plugin ("Only authenticated users", BACKLOG.md 2026-09-23). `/feed/` nunca testado — se responder, é o caminho legítimo. Portal se declara jornalístico (mistura notícia e research). Carteira Top 10 já coberta por `safra_carteiras.py`. |
| BB Investimentos (BB-BI) | `investalk.bb.com.br/noticias/onde-investir/` | HTML | **bloqueada** (`/feed/` e `/wp-json/` 403 em 2026-09-23) | `investalk.bb.com.br/noticias/onde-investir/carteira-fundamentalista-outubro-26` (atualizada 30/09/2026) | Conteúdo público e atual existe, mas a casa fechou feed/API deliberadamente; raspar HTML exigiria checar robots e estabilidade do markup — não feito sem amostra. |
| Santander | `investimentos.santander.com.br/materiais/relatorios/`, `cms.santander.com.br/.../carteiravalor*.pdf` | PDF avulso | **sem feed** / **inacessível pela ferramenta** | `cms.santander.com.br/.../26-08-31_223434_carteiravalorsetembro2026.pdf` (31/08/2026) | Só PDFs mensais de carteira, sem índice legível por máquina encontrado; raiz `santandercorretora.com.br` deu 403 em 2026-09-23. |
| Ágora / Bradesco | `insights.agorainvestimentos.com.br/conteudo` | SPA/HTML | **inacessível pela ferramenta** | Republicações em terceiros: `acionista.com.br/wp-content/uploads/2026/07/210726-aberturademercado-Agora.pdf` (21/07/2026) | Conteúdo existe, mas o que foi indexado é republicação de terceiro (Clube Acionista), não a fonte oficial. Sem feed/API confirmado. |
| Bradesco BBI | — | — | **só cliente** | Apenas cobertura de imprensa (ex.: `monitormercantil.com.br/bradesco-bbi-classifica-...`) | Relatórios institucionais distribuídos a clientes. |
| Bradesco DEPEC | `economiaemdia.com.br` | HTML | **inacessível pela ferramenta** | nada indexado recente | Não foi possível confirmar se o portal segue ativo. |
| Inter Invest | `interinvest.inter.co`, `blog.inter.co` | SPA React | **sem conteúdo público** identificado | nenhum item de research do próprio Inter indexado | Só cobertura de terceiros sobre a ação INBR32. |
| Rico | `riconnect.rico.com.vc/blog/category/economia-e-analises/` | WordPress (provável) | **inacessível pela ferramenta** | página "Onde investir no 2º semestre de 2026" | Grupo XP — risco de mesmo bloqueio Akamai da XP (não verificado). `/feed/` de categoria é o caminho a testar. |
| Toro | `blog.toroinvestimentos.com.br` | WordPress (provável) | **inacessível pela ferramenta** | último item indexado de 2025 (carteiras mensais) | Conteúdo mais educacional/marketing; carteira em parceria com Santander. |
| Monte Bravo (fora da lista original) | `montebravo.com.br` | WordPress (PDFs em `wp-content`) | **inacessível pela ferramenta** | `montebravo.com.br/wp-content/uploads/2026/06/Carteira-de-FIIs-Monte-Bravo-Junho-2026.pdf` (06/2026) | Publica "Monte Bravo Analisa" em PDF aberto; feed não testado. |
| Ativa | `ativainvestimentos.com.br` | — | **inacessível pela ferramenta** | Republicações em terceiros: `acionista.com.br/hapvida-hapv3-atualizacao-pos-2t26/` (26/08/2026) | Nada do site oficial indexado. |
| NuInvest / Nubank | — | app | **só cliente** | carteira mais recente indexada de 2022 | Research dentro do app. |
| Warren | `warren.com.br` | — | **sem conteúdo público** atual | último "Warren Semanal" indexado: 11/11/2022 | |
| Órama | `orama.com.br` | — | **sem conteúdo público** encontrado | nenhum resultado relevante | |
| Guide | — | — | **sem conteúdo público** atual | último material citado de 2024 | Em negociação de venda ao Safra (imprensa). |
| Empiricus | `empiricus.com.br` | assinatura | **só cliente** (paywall) | — | Não contornar paywall. |
| Clear, Modalmais | — | — | **sem conteúdo público** encontrado | — | |
| Necton | — | — | **só cliente** | republicações no Clube Acionista atrás de cadastro | |

### YouTube para novas casas

Não usado. O `robots.txt` do YouTube proíbe `/feeds/videos.xml` para
`User-agent: *` (já documentado em `data/research/genial_lives.py`); a
exceção da Genial (Lives) é única e deliberada, e esta frente não pode
criar exceções novas de robots — portanto canais de YouTube de outras
casas ficam fora.

## Próximos passos (para quem tiver rede)

Ordem sugerida, todos via `requests` com `base.HEADERS` e `permitido()`,
de uma máquina/runner com saída de rede (ex.: um passo de diagnóstico no
próprio `coletores-nuvem`, sem coletor novo):

1. `https://blog.itau.com.br/privateinsights/feed` (e `robots.txt`) —
   se for RSS válido com itens de 2026, é o melhor candidato (macro
   público recorrente, autoria Itaú BBA).
2. `https://oespecialista.safra.com.br/feed/` — o REST está fechado, mas o
   feed RSS padrão do WordPress pode estar aberto; filtrar por categoria
   de análise (o portal mistura notícia e research).
3. `https://www.montebravo.com.br/feed/`.
4. `https://riconnect.rico.com.vc/blog/category/economia-e-analises/feed/`
   (checar se não cai no mesmo bloqueio da XP).

Com a resposta real em mãos: salvar em `tests/fixtures/research/` com a
data de captura no nome, implementar `data/research/<casa>.py` no mesmo
formato de `btg.py`/`genial_lives.py` (timeout, `motivo_ultima_falha()`,
link canônico sem `utm_*`, data em BRT sem inventar, dedup por link,
rejeição de página de erro/login) e registrar em `CASAS`.

## Sondagem real a partir do runner do GitHub Actions (22/10/2026 19:11 UTC)

O sandbox e as ferramentas de busca não alcançam os sites; a sondagem foi feita por um workflow temporário
(`scripts/sondar_fontes.py`, só leitura, sem secrets) no runner do GitHub, que tem rede. Resultado medido:

| Fonte | robots.txt | Resposta do feed | Conclusão |
|---|---|---|---|
| Monte Bravo `www.montebravo.com.br/feed/` | `User-agent: * / Disallow:` (tudo permitido) | HTTP 200 `application/rss+xml`, 10 itens, mais recente 22/10/2026 ("Resultado WEG 3T26", com recomendação e alvo) | **implementado** (`data/research/montebravo.py`) |
| Itaú Private Insights / Itaú Análises | HTTP 403 | HTTP 403 | bloqueado para o runner |
| Safra O Especialista | HTTP 403 | HTTP 403 | bloqueado |
| Rico (economia-e-análises) | HTTP 403 | HTTP 403 | bloqueado |
| Ativa | HTTP 403 | HTTP 403 | bloqueado |
| BB Investalk | permite (com exceções por URL) | HTTP 200, mas **HTML**, não feed | sem feed; avaliar página pública noutra sessão |
| Ágora | permite | HTTP 404 | sem feed |
| Inter | permite | HTTP 404 (redireciona para blog.inter.co) | sem feed |
| Warren | permite | HTTP 503 | indisponível |
| Órama | — | DNS não resolve | domínio inexistente |
| Toro | permite (exceto /wp-json/, PDFs) | HTTP 200, 10 itens | conteúdo educativo de day trade, **não é research** — não implementado |
| Bradesco DEPEC (economiaemdia) | HTTP 200 vazio | HTTP 200 HTML | sem feed |

Monte Bravo: o feed mistura análise com imprensa e eventos; o coletor só aceita a seção `/blog/analise/` ou
categoria de análise/carta mensal. Na amostra real: 2 de 6 itens (análise WEG 3T26, Carta Mensal de outubro).
Persistência em produção: verificada pela execução seguinte do **Coletores na nuvem** (ver relatório da sessão).
