# PREGÃO

Terminal de mercado pessoal (B3), 100% gratuito. Estética inspirada em terminal financeiro: fundo preto, texto âmbar, fonte mono, alta densidade de informação.

## Como rodar

```bash
cd pregao
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`.

## Abas

- **VISÃO GERAL**: home do terminal — em segundos, entender o que está acontecendo no mercado. Composição de painéis que já existem nas outras abas (MERCADO, MACRO, NEWS), sem coleta própria.
- **EQUITY**: cotação, candlestick/linha/área com volume e médias móveis 20/50/200, indicadores fundamentalistas (P/L, P/VP, dividend yield, beta, ROE, margens), seletor de período.
- **MACRO**: DI futuro, CDI/Selic, IPCA (Banco Central/Focus), curva pré (ANBIMA).
- **RESEARCH**: relatórios da Genial Analisa e XP (ações, estratégia, macro, newsletter, transcrição de lives), preço-alvo/recomendação extraídos automaticamente quando o relatório traz isso de forma explícita, resumo por IA (Groq) sob demanda. BTG Research está mapeado mas indisponível (bloqueado por bot-detection).
- **NEWS**: feed de notícias "wire" por ticker/watchlist, agrupado por fato, com selo de confiabilidade (CONFIRMADA/MENÇÃO) e resumo por IA sob demanda.
- **CVM**: documentos oficiais (fato relevante, comunicado ao mercado, resultados, proventos) das empresas da watchlist, com busca/filtro e resumo por IA sob demanda.
- **CALENDÁRIO**: agenda de resultados corporativos — grade mensal/semanal com painel lateral de detalhe. Cada evento é CONFIRMADO (data anunciada pela própria empresa, via RI), ESTIMADO (notícia de fonte confiável) ou PRAZO CVM (prazo regulatório máximo, nunca a data real de divulgação — a UI deixa isso explícito). Alimentado por um snapshot persistido no Supabase, atualizado por um coletor agendado (não recalcula ao navegar).
- **TOP MERCADO**: ranking de notícias mais relevantes do momento (Brasil/Internacional), por estimativa de regras (sem fonte pública de "mais lida").
- **MERCADO**: visão ampla do pregão — altas/baixas, mais negociados, termômetro, mapa de calor setorial, mercados globais. Universo de tickers vem da composição oficial do Ibovespa (B3), com fallback pra lista curada se a B3 falhar.
- **CONFIG**: tema (ÂMBAR/FÓSFORO/AZUL/CLARO), densidade, fonte, tipo de gráfico, período padrão, médias móveis, abas visíveis, formato numérico, casas de research ativas.

Login com Google (`st.login`/`st.user`); sem login só aparece a tela de apresentação. Sidebar: adicionar/remover tickers da B3 (ex: `PETR4`, `VALE3`), validados via yfinance, com variação do dia. Workspace modular (arrastar/redimensionar painéis) disponível em MERCADO/VISÃO GERAL/MACRO.

## Persistência (Supabase)

Preferências por usuário (tema, densidade, watchlist, casas de research ativas etc.) são salvas por `st.user.sub`. Se o banco cair, tudo continua funcionando só na sessão, com aviso.

Resumos de IA (Research/News/CVM) são persistidos — tanto por documento específico em `research_itens` (Research) quanto num cache **global** compartilhado entre usuários (`resumos_ia_cache`): o primeiro usuário a abrir um documento gera o resumo via Groq; qualquer outro usuário que abrir o mesmo documento depois reaproveita o resumo já salvo, sem gastar cota de IA de novo.

Tabelas usadas (rodar os `.sql` correspondentes uma vez no SQL Editor do Supabase, todos idempotentes):

| Arquivo | Tabela | Pra quê |
|---|---|---|
| `sql/schema.sql` | `user_prefs` | preferências por usuário |
| `sql/research.sql` | `research_itens` | relatórios de research coletados + resumo |
| `sql/eventos.sql` | `eventos_resultados` | datas CONFIRMADO/ESTIMADO do calendário |
| `sql/calendario_snapshot.sql` | `calendario_snapshot` | snapshot do calendário (lido pela UI, escrito pelo coletor) |
| `sql/ia_cache.sql` | `resumos_ia_cache` | cache global de resumos de IA |

(`sql/cvm.sql` é só histórico — a fase CVM acabou reaproveitando `research_itens`, não precisa ser rodado.)

## Configuração necessária antes de rodar

Preencher `.streamlit/secrets.toml` (veja `secrets.toml.example`) com as credenciais OAuth do Google, do Supabase e (opcional, só pros resumos de IA) da Groq; e rodar as tabelas acima no Supabase.

## Coleta em background

`coletor_local.py` (rodado localmente, fora do Streamlit Cloud, via agendador do sistema) coleta fontes bloqueadas por bot-detection no Cloud (Genial/XP), atualiza o histórico de recomendações, e persiste o snapshot do CALENDÁRIO — tudo gravado no mesmo Supabase que o app lê.

## Resiliência

Se alguma fonte de dados falhar (yfinance, Supabase, Genial/XP, CVM, Groq), aparece um aviso no painel ou o último dado válido conhecido é reaproveitado — o resto do app continua funcionando. O projeto nunca inventa um valor quando a fonte real não responde.
