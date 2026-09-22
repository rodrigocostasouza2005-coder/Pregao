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

## Fase atual: 1B — Login + Preferências

- Login com Google (`st.login`/`st.user`); sem login só aparece a tela de apresentação.
- Preferências por usuário (tema, densidade, fonte, watchlist, config. de gráfico) salvas no Supabase, chave = `st.user.sub`. Se o banco cair, tudo funciona só na sessão, com aviso.
- Painel **CONFIG** (aba 6): tema (ÂMBAR/FÓSFORO/AZUL/CLARO), densidade, fonte, tipo de gráfico, período padrão, médias móveis, abas visíveis, formato numérico.
- Sidebar: adicionar/remover tickers da B3 (ex: `PETR4`, `VALE3`), validados via yfinance, com variação do dia.
- Aba **EQUITY**: cotação, candlestick/linha/área com volume e médias móveis 20/50/200, seletor de período.
- Abas **MACRO**, **RESEARCH**, **NEWS**, **CVM**: placeholders, chegam nas próximas fases.

Configuração necessária antes de rodar: preencher `.streamlit/secrets.toml` (veja `secrets.toml.example`) com as credenciais OAuth do Google e do Supabase, e rodar `sql/schema.sql` no Supabase.

Se alguma fonte de dados falhar (yfinance, Supabase), aparece um aviso no painel — o resto do app continua funcionando.
