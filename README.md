# PREGÃO

Terminal de mercado pessoal (B3), 100% gratuito. Estética inspirada em terminal financeiro: fundo preto, texto âmbar, fonte mono.

## Como rodar

```bash
cd pregao
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`.

## Fase atual: 4 — Research (Genial Analisa)

- Login com Google (`st.login`/`st.user`); sem login só aparece a tela de apresentação.
- Preferências por usuário (tema, densidade, fonte, watchlist, config. de gráfico, casas de research ativas) salvas no Supabase, chave = `st.user.sub`. Se o banco cair, tudo funciona só na sessão, com aviso.
- Painel **CONFIG** (última aba): tema (ÂMBAR/FÓSFORO/AZUL/CLARO), densidade, fonte, tipo de gráfico, período padrão, médias móveis, abas visíveis, formato numérico, casas de research.
- Sidebar: adicionar/remover tickers da B3 (ex: `PETR4`, `VALE3`), validados via yfinance, com variação do dia.
- Aba **EQUITY**: cotação, candlestick/linha/área com volume e médias móveis 20/50/200, seletor de período.
- Aba **MACRO**: DI futuro, CDI/Selic, IPCA (Banco Central/Focus/ANBIMA).
- Aba **RESEARCH**: relatórios da Genial Analisa (ações, estratégia, macro, newsletter), recomendações e swing trade destacados pra quem está na sua watchlist, resumo automático por IA (Groq, opcional) sob demanda — resumo cacheado em memória enquanto o app estiver no ar, nunca salvo em banco. BTG Research está mapeado mas indisponível (bloqueado por bot-detection).
- Abas **NEWS**, **CVM**: placeholders, chegam nas próximas fases.

Configuração necessária antes de rodar: preencher `.streamlit/secrets.toml` (veja `secrets.toml.example`) com as credenciais OAuth do Google, do Supabase e (opcional, só pro resumo de research) da Groq; e rodar `sql/schema.sql` no Supabase.

Se alguma fonte de dados falhar (yfinance, Supabase, Genial, Groq), aparece um aviso no painel — o resto do app continua funcionando.
