# Cobertura de research — auditoria e fechamento da rodada (2026-10-23)

Continuação de `docs/research-fontes-20261022.md` (Frente C). Pedido:
expandir a cobertura de ~5 pra ~25 casas, priorizando BTG, XP, Itaú BBA,
J.P. Morgan, Goldman Sachs, Safra, Genial e Santander, só contabilizando
como operacional quem entrega conteúdo real e recorrente.

## Estado atual (`data/research/__init__.py` → `CASAS`)

| Casa | Fonte | Tipo | Status |
|---|---|---|---|
| BTG Pactual Research | `content.btgpactual.com` (API, filtrada por `tier==AREA_PUBLICA`) | API JSON | ativa |
| XP Investimentos | `conteudos.xpi.com.br` (WP REST) | API JSON | ativa (bloqueada no Cloud, roda via `coletor_local.py`) |
| Genial Analisa | `analisa.genialinvestimentos.com.br` | HTML/`__NEXT_DATA__` | ativa (idem XP) |
| Genial (Lives) | YouTube RSS do canal | RSS | ativa (exceção de robots já aprovada, não replicável) |
| Monte Bravo | `montebravo.com.br/feed/` | RSS WordPress | ativa (adicionada 22/10) |

Adjacentes, corretamente fora de `CASAS` (são carteira recomendada, não
research de ações — alimentam `data/radar_quedas.py`): Genial Carteiras,
Safra Carteiras.

## Re-verificação de hoje (requisição real, deste ambiente — rede
disponível hoje, diferente de ontem)

### Casas pedidas explicitamente como prioridade

| Casa | Teste | Resultado |
|---|---|---|
| Itaú BBA | `blog.itau.com.br/privateinsights/feed` | HTTP 403 (confirma achado de ontem via runner do GitHub Actions) |
| Safra | `oespecialista.safra.com.br/feed/` | HTTP 403 |
| Santander | `santander.com.br/feed/` e raiz | HTTP 403; único conteúdo público é PDF mensal avulso de carteira, sem índice navegável |
| J.P. Morgan | busca por feed/blog público de research Brasil | sem fonte pública — research institucional sell-side é restrito a cliente sob contrato (compliance/MiFID-like, tiering de distribuição); não há endpoint a testar, não é um bloqueio técnico contornável |
| Goldman Sachs | idem | mesmo caso — sem infraestrutura pública de distribuição |

BTG, XP, Genial: já ativas (ver tabela acima).

### Candidatos de expansão (bancos/corretoras)

| Casa | Teste | Resultado |
|---|---|---|
| Rico | `riconnect.rico.com.vc/.../feed/` | HTTP 403 (grupo XP, mesmo WAF) |
| Ativa | `/feed/` | HTTP 403 |
| Modal Mais | `/feed/` | HTTP 403 |
| BB Investalk | `investalk.bb.com.br/noticias/onde-investir` | robots.txt permite; página é Next.js renderizada no cliente (sem `__NEXT_DATA__`/JSON no HTML servido, sem artigos no HTML estático) — raspagem exigiria navegador headless, padrão já descartado no projeto pra research pela fragilidade (ver tentativas de Playwright contra `btgpactual.com/acoes/ultimos-relatorios`, 0/8) |
| Ágora | `/feed/` | HTTP 404 — sem feed |
| Inter | `/feed/` | HTTP 404 — sem feed |
| Warren | `/feed/` | HTTP 200, mas é o shell do SPA de cadastro (`<title>Cadastro</title>`), não um feed — falso positivo |
| Órama | `/feed/` | HTTP 200, mas redireciona pro app de varejo do BTG (`investimentos.btgpactual.com`) — mesmo SPA, não é a API de research já coberta (`content.btgpactual.com`) |

### Candidatos independentes/conteúdo

| Casa | Teste | Resultado |
|---|---|---|
| Suno | `suno.com.br/feed/` | feed RSS real, mas conteúdo é educacional/geral ("guia de finanças pessoais"), sem ticker/recomendação/preço-alvo; rotas dedicadas de ações (`/category/acoes/feed/`, `/relatorios/feed/`) retornam 404 — o produto real de research (Suno Research) é pago |
| Clube do Valor | `clubedovalor.com.br/feed/` | feed RSS real, mesmo perfil: conteúdo educacional de curso, não research institucional |
| InfoMoney | `/feed/` | feed real, mas é portal de notícia — categoria errada (já é notícia, não casa de research; ver `data/news.py` se cobertura de notícia for o objetivo) |
| Acionista.com.br | `/feed/` | feed real, mas republica PDFs de outras casas (Bradesco BBI, Ágora, Ativa) — não é fonte original, risco de atribuição errada de autoria |

## Conclusão

Depois de ~20 candidatos testados (ontem via runner do GitHub Actions
com rede real, hoje de novo direto deste ambiente), **nenhum 6º coletor
novo é legítimo e tecnicamente viável agora**. Não é lacuna de esforço de
implementação — é estrutural:

- bancos de investimento (Itaú, Safra, Santander, Rico, Ativa, Modal)
  fecham deliberadamente a distribuição pública (WAF/403);
- bulge-bracket global (J.P. Morgan, Goldman Sachs) não tem canal público
  de distribuição de research sell-side — é cliente institucional sob
  contrato, não um bloqueio técnico;
- os "feeds reais" que sobram (Suno, Clube do Valor, InfoMoney, Acionista)
  são de categoria errada (educacional/notícia/republicação), não research
  de ações com recomendação e preço-alvo verificáveis na fonte original.

**Decisão (confirmada com o Rodrigo em 2026-10-23): fechar esta rodada
com as 5 casas já ativas.** Sem coletor novo nesta frente — implementar
contra uma das fontes acima seria ou inventar dado sem amostra real, ou
contornar paywall/bloqueio deliberado, ou aceitar um coletor frágil
(headless browser) fora do padrão já descartado no projeto. Reabrir esta
frente se alguma casa destravar (ex.: mudar de WAF, abrir feed novo) ou se
a definição de "casa de research" mudar por pedido explícito.
