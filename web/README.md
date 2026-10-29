# Pregão — nova interface (Next.js)

Aplicação Next.js (App Router, TypeScript, Tailwind CSS) da reformulação do
Pregão. Fica neste diretório `web/`, separada da aplicação Python/Streamlit
da raiz, que continua funcionando durante a migração.

## Rodar localmente

```bash
cd web
npm install
npm run dev        # http://localhost:3000
npm run build      # build de produção
npm run typecheck
```

## Deploy na Vercel

No projeto da Vercel: **Settings → Build and Deployment**

- **Root Directory:** `web`
- **Framework Preset:** Next.js (detectado automaticamente)
- Build Command, Output Directory e Install Command: padrão (deixe vazios)
- **Node.js Version:** 20.x ou 22.x

Variáveis de ambiente (opcionais): ver `.env.example`. Nenhum segredo do
Streamlit (`.streamlit/secrets.toml`) é usado aqui.

## Estado atual

- Estrutura do terminal (cabeçalho, navegação lateral, painéis) pronta.
- **Nenhum dado real conectado ainda:** a tabela de mercado mostra "—" e as
  áreas estão marcadas como demonstrativas. O ponto de integração das
  cotações é `lib/mercado.ts` (`obterCotacoes`).
