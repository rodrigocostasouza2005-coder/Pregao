# PREGÃO · Web (Next.js)

Migração gradual do terminal PREGÃO de Streamlit/Python para Next.js +
TypeScript, hospedado na Vercel. **O app Streamlit original (raiz do
repositório) continua em produção, intocado** - este diretório é um
frontend novo e independente, não uma substituição.

Primeira tela migrada: **Mercado › Visão Geral** (`app/page.tsx`).

## Rodando localmente

```bash
npm install
npm run dev
```

Abre em http://localhost:3000.

```bash
npm run build   # build de produção
npm run lint    # ESLint
npm run test    # Vitest (lógica de cálculo em lib/)
```

## Arquitetura

- **`lib/yahoo.ts`** — cliente do endpoint público "chart" do Yahoo
  Finance (mesma fonte gratuita que o app Python usa via `yfinance`,
  implementado aqui independentemente - o coletor Python **não foi
  migrado nem alterado**, continua servindo o Streamlit).
- **`lib/mercado.ts`** — funções de dado server-side (indicadores,
  histórico, panorama do Ibovespa) + cálculos puros (altas/baixas,
  desempenho setorial, mais negociados, concentração setorial) -
  testados em `lib/__tests__/`.
- **`lib/setores.ts`** — mapa ticker→setor, porção direta de
  `config.IBOVESPA_SETORES` (app Python).
- **`app/page.tsx`** — Server Component, busca os dados direto (sem
  round-trip de API) e renderiza a tela inteira no servidor.
- **`app/api/mercado/historico/route.ts`** — única rota de API real
  desta 1ª versão, usada pelo seletor de período do gráfico (client
  component precisa poder reconsultar sem recarregar a página).

Nenhum dado é inventado: painéis sem integração real ainda (notícias,
síntese por IA, agenda/teses da watchlist, mercados globais, watchlist,
"para investigar") mostram uma mensagem explícita de pendência em vez de
conteúdo simulado.

## Variáveis de ambiente

Nenhuma é necessária pra esta 1ª versão (Yahoo Finance e BCB/SGS são
endpoints públicos, sem chave). Documentando desde já pro próximo
incremento (autenticação + dados do Supabase - research/agenda/
watchlist), que vai precisar delas:

| Variável | Onde usar | Observação |
|---|---|---|
| `SUPABASE_URL` | Server-only (Route Handlers/Server Components) | Mesmo projeto Supabase do app Python |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only, **nunca** `NEXT_PUBLIC_*` | Todas as tabelas têm RLS ativado **sem nenhuma policy** (ver `sql/*.sql` na raiz do repo) - só a service role consegue ler/escrever. A chave anon pública não teria acesso a nada, então não dá pra usar Supabase direto do client; precisa de uma rota server-side agindo como proxy, igual ao backend Python faz hoje. |

Configurar como **Environment Variables** do projeto na Vercel (nunca
commitar num `.env` versionado) - ver seção abaixo.

## Conectar à Vercel (preview, sem afetar produção)

1. Em https://vercel.com/new, importar o repositório
   `rodrigocostasouza2005-coder/Pregao`.
2. Em **Root Directory**, apontar pra `web` (o Next.js fica num
   subdiretório do mesmo repo - a Vercel suporta isso nativamente).
3. Framework Preset: Next.js (detecta sozinho).
4. **Não é preciso nenhuma env var ainda** pra esse primeiro build.
5. Deploy. A Vercel gera uma URL de preview própria (não mexe no domínio
   de produção nem no app Streamlit) pra cada push nesta branch.
6. A partir daqui, qualquer novo push na branch
   `feat/migracao-nextjs-vercel-20261027` (ou na PR aberta a partir
   dela) gera um novo preview automático - não precisa reconectar nada.

## Pendências (próximos incrementos)

- Autenticação (hoje é `st.login`/Google no Python) - decidir se migra
  pra NextAuth/Auth.js com o mesmo provedor Google, ou outra estratégia.
- Dados dependentes de login: watchlist, agenda da watchlist, teses de
  research da watchlist, preferências (tema/densidade/etc).
- Síntese por IA (`data/sintese_mercado.py`) - decidir se a lógica migra
  pra uma função server-side em TS (chamando o Groq direto) ou se
  continua só no Python, com o Next.js consumindo um resultado já
  pronto salvo no Supabase.
- Feed de notícias (`data/news.py`, scraping RSS) - mesma decisão:
  reimplementar em TS ou reaproveitar o que o coletor Python já salva.
- Mercados globais - mesma fonte Yahoo Finance já integrada aqui, só
  falta escolher os índices e ligar.
- Demais abas (Mercado › Painel, Macro, Setores, Research, Morning
  Call, Radar) - fora do escopo desta 1ª etapa.
