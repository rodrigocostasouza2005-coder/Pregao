# Auditoria — 20 execuções EM_ANDAMENTO órfãs em `coordenador_analises`

Data: 2026-11-13 · Agente: PREGÃO 2.1 / Agente F · Branch: `feat/21-f-estabilidade-20261113` (a partir de `origin/main` @ `eedd8c9`)

Escopo: investigar (achado de auditoria QA anterior, só leitura, não corrigido) 20 execuções em `coordenador_analises` travadas em `status='EM_ANDAMENTO'` desde 2026-11-05. Esta auditoria é só leitura contra o Supabase real de produção (consulta direta via `data.supabase_client.obter_cliente()`, credenciais de `.streamlit/secrets.toml`) — nenhuma escrita foi feita contra produção.

## Resultado — são órfãs de verdade, com causa raiz confirmada

**Quantas**: exatamente 20 linhas com `status='EM_ANDAMENTO'` na tabela inteira (nenhuma outra data, nenhuma outra quantidade).

**De quando**: todas de 2026-11-05, `iniciado_em` entre `02:51:07.322265+00:00` e `02:53:16.301592+00:00` UTC — uma janela de ~2min09s. Isso bate exatamente com uma única rodada de `jobs/comite_noturno.py` (`LIMITE_TICKERS_RODADA = 20`), que processa até 20 tickers sequencialmente por execução.

**Quais tickers**: AAPL34, ALPA4, ASAI3, B3SA3, BBAS3, BBSE3, BEEF3, BPAC11, EZTC3, ITUB4, JBSS32, MELI34, NFLX34, PETR4, RENT3, ROXO34, SBFG3, SMFT3, VALE3, VIVA3 — mix de ações B3 e BDRs (AAPL34/MELI34/NFLX34/ROXO34), todos `tipo_fluxo='analise_ticker'`.

**Idade atual**: ~203 horas (~8.5 dias) no momento desta auditoria — comparado a uma amostra de 100 análises `CONCLUIDA` mais recentes em produção, cuja `duracao_ms` varia entre **3842ms e 21047ms** (média ~10.1s). Uma análise real nunca leva dias; estas 20 estão ordens de magnitude além de qualquer execução em andamento plausível.

**O processo que as criou já morreu**: `jobs/comite_noturno.py` roda via GitHub Actions agendado, processo curto que termina ao fim da rodada — não há nada "ainda rodando" há 8 dias.

**Evidência de que o processamento rodou até o fim**: cada uma das 20 `analise_id` já tem exatamente **6 execuções de especialista** registradas em `coordenador_especialistas_execucoes` (telemetria completa, gravada durante a análise). Isso confirma que `analisar_ticker()` executou os especialistas normalmente — a falha foi isolada ao UPDATE final que fecha a linha em `coordenador_analises`.

## Causa raiz (bug real, já documentado no próprio código, já corrigido — mas não retroativamente)

`data/coordenador_central/persistencia.py` já registra, em comentário (linhas ~26-38), exatamente este incidente: o cliente HTTP do supabase-py (httpx) serializa o payload do UPDATE com `json.dumps` padrão, sem encoder para `date`/`datetime`. Sempre que o `resultado` consolidado de uma análise contém uma data pura (comum no especialista `catalisadores`, que devolve `datetime.date` quando há evento na janela coberta), o UPDATE completo de `concluir_analise` falhava de forma **100% determinística** (nunca transitória — por isso o retry de `_TENTATIVAS_UPDATE` nunca ajudava).

Esse bug foi corrigido em produção no mesmo dia, poucas horas depois, pelo commit `4aa50a8` ("fix(coordenador_central): serializa date/datetime antes do UPDATE no Supabase", 2026-11-05 20:14 -03) via `_serializar_jsonb()`. As 20 linhas desta auditoria são **anteriores** à correção (rodada das 02:51-02:53 UTC = 23:51-23:53 -03 do dia 04/11, antes do fix do dia 05/11 à noite) e, como o processo que as criou (`comite_noturno.py`) já terminou, nunca mais foram reprocessadas por nenhum caminho de código — mesmo com o bug já corrigido para análises futuras, não existe nenhum mecanismo que revisite e feche análises antigas já travadas.

## O que NÃO existe (confirmado por busca no código): mecanismo de timeout/limpeza automática

Busca por qualquer rotina de expiração/timeout/limpeza associada a `coordenador_analises` (`EXPIRAD`, `limpar_analises`, `timeout.*analise`, `stale`, `travad.*analise`) não encontrou nenhum resultado relevante no projeto. O único controle relacionado é `jobs/comite_noturno.py:_tickers_com_analise_recente`, que usa uma janela de 18h (`JANELA_ANALISE_RECENTE_HORAS`) só para decidir se um ticker deve ser **reprocessado** na próxima rodada (evita duplicidade) — isso não fecha a linha antiga, só para de "contar" ela como recente depois de 18h, deixando-a visível como EM_ANDAMENTO indefinidamente em qualquer tela/consulta que não filtre por data.

**Conclusão**: é uma lacuna real (nenhum watchdog fecha análises travadas), não um bug de lógica adicional — a causa raiz do travamento em si (serialização de data) já está corrigida desde 2026-11-05 à noite.

## Proposta de encerramento seguro — pronta, NÃO executada

Script: `scripts/encerrar_analises_orfas.py` (criado nesta missão, versionado nesta PR).

Características:
- **Dry-run por padrão** — sem `--aplicar`, só lista o que seria alterado (testado e confirmado seguro: roda contra produção, zero escrita).
- **Dupla confirmação pra escrever**: exige `--aplicar` **e** `--confirmo EXECUTAR-EM-PRODUCAO` (frase exata) juntos; testado que `--aplicar` sozinho, ou com `--confirmo` incorreto, aborta sem escrever nada.
- **Nunca deleta** — só atualiza `status` (para `ERRO`, reaproveitando o enum de status já existente — `EM_ANDAMENTO/CONCLUIDA/PARCIAL/ERRO`, nunca um status novo, seguindo a convenção já explícita no próprio `persistencia.py`), `concluido_em` e `erro` (mensagem clara explicando o fechamento retroativo e citando a causa raiz). `resultado` nunca é preenchido — não existe mais o dado real da análise original.
- **Reaproveita código já testado**: usa `data.coordenador_central.persistencia.concluir_analise()` (já tem retry + fallback mínimo embutido) em vez de reinventar o UPDATE.
- **Limiar configurável** (`--limiar-horas`, default 2h — bem acima do máximo real observado de 21s, com margem grande).

### Validação feita nesta missão (nenhuma escrita em produção)

```
python scripts/encerrar_analises_orfas.py                                        → lista as 20 linhas corretamente, DRY-RUN, zero escrita
python scripts/encerrar_analises_orfas.py --aplicar                              → aborta sem escrever (falta --confirmo exato)
python scripts/encerrar_analises_orfas.py --aplicar --confirmo errado            → aborta sem escrever (frase não bate)
```

Confirmado por reconsulta direta ao Supabase após os três comandos acima: as 20 linhas continuam `EM_ANDAMENTO`, inalteradas.

**Este script NÃO foi executado com `--aplicar --confirmo EXECUTAR-EM-PRODUCAO`.** Alterar registro real de produção — mesmo um registro órfão, mesmo preservando o histórico — exige aprovação explícita do Rodrigo à parte da autorização geral de merge desta missão. Fica pronto, revisado e testado em dry-run, esperando essa aprovação específica.

## Frentes 2 e 3 desta missão (contexto, sem relação com produção)

- **pdfplumber**: já estava corretamente declarado em `requirements.txt` (`pdfplumber>=0.11`) — a falha era só o `.venv` local estar fora de sincronia com o `requirements.txt` (ambiente de desenvolvimento, não um bug de código nem de dependência mal declarada). Instalado `pdfplumber==0.11.10` no `.venv` do projeto; `tests/test_research_resumir_extracao_pdf.py` (15 testes, incluindo `test_pdfplumber_extrai_texto_real_de_pdf_real`) passa 100%. Nenhuma mudança de código/requirements.txt foi necessária.
- **Suite completa**: `python -m pytest tests/ -q` (síncrono) → **2591 passed**, 0 falhas, 0 skips, ~5min14s.
