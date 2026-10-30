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


## E-mails automatizados (Radar e Morning Call)

Os envios aceitam três provedores, escolhidos por `EMAIL_PROVIDER`. Configure em **GitHub → Settings → Secrets and variables → Actions**:

**`EMAIL_PROVIDER=brevo`** (recomendado quando o remetente é um e-mail comum, ex. Gmail, sem domínio próprio) — Brevo verifica o remetente só com um código de 6 dígitos enviado pro próprio e-mail, sem exigir DNS. Free tier: 300 e-mails/dia, sem expiração.
- `BREVO_API_KEY`: chave gerada em app.brevo.com (SMTP & API → API Keys)
- `EMAIL_FROM`: o e-mail verificado na conta Brevo (Senders → Add a sender → confirmar o código recebido)

**`EMAIL_PROVIDER=resend`** (exige domínio próprio verificado por DNS):
- `RESEND_API_KEY`: chave secreta gerada na conta Resend
- `EMAIL_FROM`: remetente de um domínio autorizado e verificado no Resend (não aceita domínios de provedor gratuito como gmail.com)

**`EMAIL_PROVIDER=smtp`** (ou deixe a variável ausente — é o default): configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` (senha de app, se o provedor exigir 2FA) e `EMAIL_FROM`.

Nenhuma chave/senha deve ir pro código nem em mensagens — sempre via GitHub Secret. A troca de provedor não altera a lógica do Radar nem do Morning Call. Os envios só serão efetivos depois que os secrets e um remetente verificado estiverem configurados. Não existe mais `EMAIL_TO`: desde a auditoria "Radar/Morning Call: consentimento" (2026-10-26), nenhum envio automático usa um destinatário fixo de ambiente — configurá-lo não tem efeito nenhum.

### Destinatários automáticos (opt-in por usuário, um para cada fluxo)

O Radar de Quedas (`jobs/radar_quedas.py:executar`) e o Morning Call (`jobs/morning_call.py:executar`) são disparados pelo mesmo workflow (`.github/workflows/radar-morning-call.yml`) mas **cada um resolve sua própria lista de destinatários, de forma independente** — ligar um nunca liga o outro:

- Morning Call: `data/user_prefs.py:listar_assinantes_morning_call` busca em `user_prefs` (Supabase) todo usuário autenticado (login Google) com o toggle **"RECEBER MORNING CALL POR E-MAIL"** (aba MORNING CALL › Preferências) ativado.
- Radar de Quedas: `data/user_prefs.py:listar_assinantes_radar_quedas` busca, na mesma tabela, quem ativou **"RECEBER ALERTAS DO RADAR POR E-MAIL"** (aba RADAR › Preferências).

Os dois filtram por e-mail em formato válido e deduplicam. O default de ambas as preferências é **desligado**: sem opt-in explícito, nenhum usuário (novo ou já existente) recebe e-mail automático de nenhum dos dois fluxos. Sem nenhum destinatário autorizado, a execução termina normalmente sem enviar nada (não é tratado como falha); já não conseguir CONSULTAR quem autorizou (Supabase fora do ar) é tratado como falha de execução, visível no painel SAÚDE DOS DADOS. Uma falha de envio para um assinante não impede a tentativa para os demais, nem é reportada como sucesso total. Logs de execução referenciam cada destinatário só por um hash curto (nunca o e-mail completo).

Envio de teste manual (nunca usa a lista de assinantes, nunca dispara pros assinantes reais): `python -c "from jobs.morning_call import enviar_teste; print(enviar_teste('seu-email-de-teste@exemplo.com'))"`, ou via GitHub Actions → **Radar e Morning Call** → Run workflow → `teste_destinatario`.
