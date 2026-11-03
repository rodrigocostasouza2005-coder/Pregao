# Execução Geral — PREGÃO

Arquivo central de acompanhamento da operação de recuperação/evolução/finalização do PREGÃO, pedida pelo Rodrigo em 2026-11-02 (superprompt de 18 frentes, executado em ondas). Evita relatórios repetidos — cada onda atualiza sua seção aqui em vez de gerar um doc novo.

## ONDA 1 — Recuperação e Integração (2026-11-02)

**Escopo:** triagem de todas as PRs abertas, decisão objetiva por PR (mergear / fechar como obsoleta com motivo / deixar pendente), sem tocar nas demais frentes do superprompt (RAG, Radar, Morning Call, frontend, segurança/RLS — essas ficam para ondas seguintes).

### Estado da `main` antes da onda
`629e85c` (Calendário: prioriza watchlists e protege filtro TODOS, #222).

### PRs triadas

| PR | Título | Status antes | Decisão | Motivo | Status depois |
|---|---|---|---|---|---|
| #223 | feat(radar): integra Itaú Top 5 com fallback para última publicação | OPEN, CI verde (testes/Vercel/Vercel Preview Comments), `CLEAN`/`MERGEABLE` | **Mergeado** | Mesmo escopo do #85 (arquivos idênticos), implementação mais recente e sem conflito | MERGED — commit `2ab609d` |
| #85 | feat(radar): add public Itaú Investimentos Top 5 collector | DRAFT, `CONFLICTING` desde 19/10 | **Fechado** | Substituído pelo #223 (mesmo conjunto de arquivos: `data/radar_quedas.py`, `data/research/itau_carteiras.py`, `jobs/radar_quedas.py` + testes) | CLOSED, comentário linkando #223 |
| #175 | docs: padroniza fluxo de execução, revisão e merge | OPEN, CI verde, `mergeable=true`/`clean` | **Mergeado** | Cria `CLAUDE.md` na raiz — regras operacionais pequenas, aditivas, sem conflito | MERGED — commit `7fbe08e` |
| #189 | feat(web): inicia migração Next.js + TypeScript (Visão Geral) | OPEN, `CONFLICTING` desde 28/10 | **Fechado** | Scaffold inicial (1 página, sem rotas/login/middleware) — `main` já tem a migração Next.js muito mais avançada (route groups `(terminal)/{agenda,ativo,busca,...}`, API routes, login, middleware), fruto de várias PRs mergeadas depois desta | CLOSED, comentário explicando a supersessão |
| #168 | fix(news): correção cirúrgica do modal de NOTÍCIA | OPEN, `CONFLICTING` desde 25/10 | **Fechado** | Função `_renderizar` que a PR introduz não existe mais em `ui/news_tab.py` — o modal foi reconstruído (`_abrir_card`/`abrir_card_noticia`/`_meta_line_dialog`) com fallback de imagem, truncamento e controle de overflow já maduros | CLOSED, comentário explicando a supersessão |
| #137 | fix(news): corrige corte de imagens no modal e refina a formatação editorial | OPEN, `CONFLICTING` desde 22/10 | **Fechado** | Mesmo escopo/arquivos do #168, mesma supersessão | CLOSED, comentário linkando o motivo do #168 |
| #84 | Morning Call: página 2 analítica (fim do layout de agregador) | OPEN, `CONFLICTING` desde 19/10, base = PR #81 (fechado) | **Fechado** | Base inexistente em `main` (PR #81 fechado, não mergeado); o conceito de "página 2 analítica" foi substituído pela arquitetura de "briefing profissional" (`data/morning_call_briefing.py`), já em `main` | CLOSED, comentário explicando a supersessão |

### Resultado
- **Mergeados:** #223 (`2ab609d`), #175 (`7fbe08e`).
- **Fechados como obsoletos** (todos com comentário explicando o motivo, nenhum tinha conteúdo exclusivo não integrado): #85, #189, #168, #137, #84.
- **Pendente:** nenhuma PR aberta restante no momento desta checagem (`gh pr list --state open` vazio após a triagem).
- `main` após a onda: inclui o coletor Itaú Top 5 com fallback (#223) e o `CLAUDE.md` de regras operacionais (#175).

### Observação registrada durante a onda (fora de escopo desta onda, fica para a onda de Automações/Morning Call)
O workflow agendado "Radar e Morning Call" apresentou 4 falhas consecutivas em `main` nas execuções mais recentes (visto em `gh run list`, não investigado a fundo — pertence à Onda 4 do superprompt do Rodrigo).

### Próxima execução
Onda 2 (Dados e Coletores) — Nord/Genial/XP/BTG/Monte Bravo/Safra, conforme pedido do Rodrigo, começando pela divergência relatada no coletor Nord (status de sucesso sem registros correspondentes em `research_itens`).
