# Pregão — terminal web (Next.js)

Interface Next.js (App Router, TypeScript, Tailwind) do Pregão, publicada
na Vercel (projeto `pregao`, Root Directory `web`). A aplicação
Python/Streamlit da raiz, os coletores, os jobs do GitHub Actions e o
Morning Call continuam como estão: este terminal **lê** o que eles produzem.

## Fontes de dados (todas lidas só no servidor)

| Área | Fonte |
|---|---|
| Mercado, Macro (exterior), ativo | Yahoo Finance (mesma regra de variação de `data/prices.py`) |
| Macro (Brasil) | Banco Central: SGS (Selic, CDI, IPCA, PTAX) e Boletim Focus |
| Notícias | Google News, CNBC e MarketWatch (RSS, mesmos feeds de `data/news.py`) |
| Research, CVM, Agenda, Morning Call, Inteligência, Configurações | Supabase do Pregão (tabelas alimentadas pelos coletores) |

Contratos compartilhados com o Python (lista do Ibovespa, casas de research,
registro de coletores) ficam em `contratos/` e são gerados por
`python scripts/exportar_contratos_web.py` (o teste
`tests/test_contratos_web.py` falha se ficarem desatualizados).

## Acesso

Todo o terminal exige login Google. Sem as variáveis de login configuradas,
o acesso fica **bloqueado** (falha fechada). Ver `.env.example`.

## Rodar

```bash
cd web
npm install
cp .env.example .env.local   # preencha
npm run dev
npm test          # testes da lógica (Vitest)
npm run build
```
