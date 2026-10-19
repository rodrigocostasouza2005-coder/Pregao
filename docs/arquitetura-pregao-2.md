# PREGÃO 2.0 — arquitetura de navegação

Inventário (Fase Zero), matriz de correspondência e decisões da reorganização
em 7 áreas + MAIS. Fonte de verdade da navegação: `ui/navegacao.py` (modelo
puro) + despacho em `app.py` (`if rota == (área, subaba)`).

## 1. Estado anterior (main em `e111394`, 19/10/2026)

- **Entrada:** `app.py` (Streamlit 1.64), login Google nativo (`auth.py`),
  preferências por usuário no Supabase (`data/user_prefs.py`, tabela `user_prefs`).
- **Navegação:** um único `st.segmented_control` (`key="secao_ativa"`) com 10 abas
  configuráveis (`config.ABAS_DISPONIVEIS`: VISÃO GERAL, RADAR, EQUITY, MACRO,
  RESEARCH, NEWS, CVM, CALENDÁRIO, TOP MERCADO, MERCADO) + CONFIG + SISTEMA e
  SAÚDE DOS DADOS (admin). Só a aba ativa executa. Sem rota na URL.
- **Personalização:** workspace com arrastar/redimensionar (`ui/workspace.py`) em
  VISÃO GERAL, MERCADO e MACRO; ordem/visibilidade de painéis em CONFIG; abas
  visíveis por usuário (`abas_visiveis`, migração `abas_conhecidas`).
- **Morning Call:** só job agendado (`jobs/morning_call.py`, e-mail + PDF), log em
  `morning_call_execucoes`; no app, apenas o toggle de inscrição em CONFIG.
- **Coleta:** desacoplada da UI (GitHub Actions `coletores-nuvem.yml`,
  `radar-morning-call.yml`, `coletor_local.py`), leitura com cache.
- **Testes:** 908 testes passando na base (`python -m pytest -q`).

## 2. Matriz de correspondência

| Área atual | Funcionalidades existentes | Destino | Dependências | Risco | Ação |
|---|---|---|---|---|---|
| VISÃO GERAL | workspace: mercado agora, Ibovespa, altas/baixas, mais negociados, setorial, market news, globais, watchlist | MERCADO › Visão Geral (+ linha de atalhos para Radar/Notícias/Agenda/Setores/Morning Call) | `ui/visao_geral.py`, workspace | Baixo | Manter + integrar |
| MERCADO | workspace: termômetro, altas/baixas, mais negociados, setorial, treemap, globais | MERCADO › Painel (layout do usuário preservado, mesma chave `MERCADO`) | `ui/mercado_tab.py`, workspace | Baixo | Manter |
| MERCADO (painel globais) + MACRO (cenário global) | índices globais, commodities, Treasuries, VIX | MERCADO › Mercados Globais | mesmos painéis | Baixo | Reorganizar (composição) |
| CALENDÁRIO | agenda de resultados corporativos (status confirmado/estimado/prazo CVM) | MERCADO › Agenda | `ui/calendario_tab.py` | Baixo | Manter |
| TOP MERCADO | ranking de manchetes por região/setor | NOTÍCIAS › Destaques (TUDO), Brasil, Internacional — região vira subaba | `ui/top_mercado_tab.py` (parâmetros `regiao_fixa`/`setor_fixo`) | Baixo | Reorganizar |
| NEWS | feed editorial da watchlist (filtro ticker/selo, lives Genial, resumos IA em cache, imagens com fallback) | NOTÍCIAS › Empresas | `ui/news_tab.py` | Baixo | Manter |
| CVM | documentos oficiais da watchlist | NOTÍCIAS › Documentos CVM (5ª subaba: destino mais próximo de “cobertura de empresas” sem misturar com jornalismo) | `ui/cvm_tab.py` | Baixo | Reorganizar |
| RADAR (quedas) | regra, cobertura das casas, monitorados agora, alertas registrados | RADAR › Alertas (regra + alertas + monitorados) e RADAR › Carteiras Recomendadas (cobertura) | `ui/radar_tab.py` (blocos extraídos, `render_radar` preservado) | Baixo | Reorganizar |
| RESEARCH | recomendações da watchlist, research radar, feed de relatórios | RADAR › Carteiras Recomendadas (abaixo da cobertura) | `ui/research_tab.py` | Baixo | Integrar |
| RADAR (inteligência da watchlist) | mudanças de tese, catalisadores, evidências | RADAR › Oportunidades | `data/radar.py` | Baixo | Reorganizar |
| RADAR (risco) + alertas 90d da watchlist | stub honesto de risco, histórico | RADAR › Acompanhamento | `data/radar_quedas.py` | Baixo | Reorganizar |
| RADAR (valuation) | múltiplos x pares | ANÁLISES › Valuation | `data/radar.py` | Baixo | Reorganizar |
| RADAR (evidências + copiloto) | base de evidências, perguntas sugeridas | ANÁLISES › Teses | `data/radar.py` | Baixo | Reorganizar |
| EQUITY | seletor de ticker, comparativo, preços, indicadores, gráfico, notícias e CVM do ticker | ANÁLISES › Empresas (+ barra de vínculos: notícias, radar, fundamentos, valuation, setor) | código em `app.py` (miolo intocado) | Médio (bloco grande) | Manter + integrar |
| — (indicadores já coletados) | `obter_indicadores` | ANÁLISES › Fundamentos (tabela da watchlist) | `data/prices.py` | Baixo | Desenvolver (composição) |
| MACRO | workspace: resumo, curva pré, IPCA, Selic×CDI, cenário global | MACRO › Indicadores (workspace preservado) | `ui/macro_tab.py` | Baixo | Manter |
| MACRO (painéis) | Selic×CDI, curva pré, Focus | MACRO › Juros (+ expectativas Focus separadas do realizado, + setores sensíveis a juros) | mesmos painéis | Baixo | Reorganizar |
| config.INDICES_TICKER_TAPE + cenário global | dólar/euro, commodities | MACRO › Câmbio e Commodities | mesmos dados | Baixo | Reorganizar |
| — | Copom vigente (`obter_selic_meta_copom`, plano B já existente), Focus | MACRO › Calendário Econômico (agenda de divulgações declarada indisponível) | `data/macro.py` | Baixo | Desenvolver (parcial) |
| MERCADO (setorial/treemap) | desempenho setorial, mapa | SETORES › Mapa Setorial | mesmos painéis | Baixo | Reorganizar |
| `data/news_setores.py` + `data/radar_setorial.CATALOGO` | taxonomia de notícias por setor, textos editoriais do Morning Call | SETORES › Visão por Setor / Catalisadores | coleta existente | Baixo | Integrar |
| Morning Call (job) | texto do e-mail, PDF, log de execuções | MORNING CALL › Edição Atual / Relatório Completo / Histórico | `data/morning_call_historico.py` (só leitura), `jobs/morning_call*.py` | Médio (PDF sob demanda é pesado) | Integrar |
| CONFIG (toggle Morning Call) | opt-in por e-mail | MORNING CALL › Preferências (CONFIG mostra o estado e um atalho) | `prefs.morning_call_email_ativo` | Baixo | Reorganizar |
| CONFIG | tema, densidade, painéis, módulos visíveis, casas de research, diagnóstico de fontes (admin) | MAIS › Configurações | — | Baixo | Manter |
| Sidebar WATCHLIST | adicionar/remover, cotações | sidebar (mantida) + MAIS › Watchlist (visão compacta + atalhos) | — | Baixo | Manter + integrar |
| SISTEMA / SAÚDE DOS DADOS | changelog/manual; monitor de coletores | MAIS › Sistema / Saúde dos Dados (admin, reconfirmado no despacho) | `config.obter_emails_admin` | Médio (segurança) | Manter |

**Duplicações reais:** nenhuma remoção. Mesmos painéis aparecem em mais de um
lugar só como *composição* (ex.: Selic×CDI no workspace de Indicadores e em
Juros) — mesma função, mesmo cache, sem coleta extra.

## 3. Decisões

1. **Dois níveis de `segmented_control` + rota na URL** (`?aba=…&sub=…`), em vez de
   `st.navigation`: preserva o cabeçalho fixo atual, o mecanismo “só a seção ativa
   executa”, os callbacks já existentes e o workspace. `st.navigation(position="top")`
   esconderia as subabas em menus suspensos e exigiria reescrever todos os vínculos.
2. **Subnavegação fora do cabeçalho fixo** (rola com a página): o cabeçalho já ocupa
   ~10rem; uma quarta faixa fixa reduziria demais a área útil no celular.
3. **Cada área lembra a última subaba** (memória em `nav_sub_<área>_valido`, chave
   comum — sobrevive ao descarte de estado de widgets não renderizados).
4. **`abas_visiveis` continua valendo** (rotulado “módulos visíveis”): esconde as
   subabas cujo conteúdo vem de um módulo oculto; CONFIG nunca some.
5. **Vínculos só com dados já identificados**: ticker citado explicitamente na notícia
   (`n["tickers"]`), setor classificado na coleta (`n["setores"]`), setor de empresa só
   por lista curada (`data/news_setores.SETORES`), relação macro→setor só por texto
   editorial já revisado (`CATALOGO`). Nada por semelhança de nome.
6. **Ticker aberto por vínculo e fora da watchlist** entra como opção temporária em
   ANÁLISES › Empresas com botão “adicionar à watchlist” (nada é salvo sem pedido).
7. **Voltar/avançar do navegador:** cada troca de rota grava uma entrada no
   histórico (`st.query_params.from_dict`, uma atualização só), mas o Streamlit
   não reexecuta no `popstate`; um listener (mesma técnica de `st.iframe` +
   `window.parent` já usada pelo workspace) recarrega a página e a rota da URL
   volta a mandar. Custo: o voltar recarrega a sessão (preferências vêm do banco).
8. **Morning Call no app nunca envia nem grava**: lê `morning_call_execucoes` sem a
   coluna `destinatario`; prévia/PDF só por botão, com cache de 30 min.

## 4. Pendências (desenvolvimento posterior)

| Item | Motivo | O que falta |
|---|---|---|
| Agenda de divulgações econômicas (IPCA, PIB, payroll, datas futuras do Copom/Fed) | nenhuma fonte confiável integrada | escolher fonte oficial/gratuita, coletor + tabela |
| Teses persistentes (premissas, riscos, histórico) e itens salvos | exigem tabela nova (migration) | schema + RLS + UI de edição |
| Séries históricas de receita/lucro/fluxo de caixa | Yahoo só entrega o corte atual de forma confiável | coletor de DFP/ITR da CVM |
| Valuation por cenários/sensibilidade | sem modelo próprio | definir metodologia antes de exibir |
| PDF de edições anteriores do Morning Call | PDF não é armazenado | storage + gravação no job |

## 5. Compatibilidade com PRs abertos (verificado em 19/10/2026)

Cada PR aberto foi mesclado localmente sobre o #82 numa worktree isolada (nada
publicado nas branches deles) e a suíte completa rodou em cada combinação.

| PR | Merge sobre o #82 | Suíte | Observação |
|---|---|---|---|
| #70 (auditoria 360, CTRL K) | limpo | 938 ok | atalho entra no cabeçalho sem depender da navegação |
| #71 (e-mail do Morning Call) | limpo | 936 ok | só `jobs/morning_call.py` |
| #72 (USUÁRIOS + oferta de Morning Call) | **conflito em `app.py`** | 966 ok após resolução | ver plano abaixo |
| #75, #77, #79, #80 | limpo | ok | sem sobreposição |
| #76 (MAIS NEGOCIADOS clicável) | limpo | 937 ok | o botão novo usa `_ir_para_equity` (já leva a ANÁLISES › Empresas); o `help` dele ainda diz "EQUITY" — ajuste de texto no próprio #76 |
| #78 (testes do workspace) | limpo | 951 ok | — |
| #81 (Morning Call editorial) | limpo | 959 ok | altera `data/radar_setorial.py`; conferido que `CATALOGO` mantém as chaves `nome`/`importa`/`acompanhar` e os mesmos setores de `news_setores.SETORES`, que o #82 consome |

**Plano seguro para o #72** (validado localmente, 966 testes verdes). Aceitar o
lado do #72 nos hunks de navegação reintroduz `secoes`/`secao_atual`, que não
existem mais (o app quebraria com `NameError`), e **o bloco de despacho de
USUÁRIOS some** porque cai dentro de um hunk conflitante. Resolução:

1. Imports: lado do #82 + `deve_oferecer_morning_call, email_valido, registrar_acesso`
   de `data.user_prefs`; manter `from ui.usuarios_tab import render_usuarios`.
2. Banner de oferta do Morning Call (#72): manter, antes da navegação; trocar
   "em CONFIG" por "em MORNING CALL › Preferências" nos dois textos.
3. Navegação e CONFIG: lado do #82.
4. `ui/navegacao.py`: `Subaba("usuarios", "Usuários", admin=True)` em MAIS e
   `"USUÁRIOS": ("mais", "usuarios")` em `ROTA_LEGADO`.
5. `app.py`: `if rota == ("mais", "usuarios"):` com `if _eh_admin: render_usuarios(usuario)`
   senão "Acesso restrito a administradores." (o teste
   `test_app_reconfirma_admin_no_despacho` exige isso para toda subaba admin).
6. `ui/morning_call_tab.py:render_preferencias`: ao mudar o toggle, gravar também
   `prefs["morning_call_email_perguntado"] = True` (linha que o #72 punha em CONFIG).

## 6. O que foi validado e como

- **Simulado (harness local, `app.py` real, login falso, preferências em memória):**
  32 rotas em 1366px e 390px, cliques, vínculos, voltar/avançar, recarregar,
  teclado, bloqueio de rotas admin, remoção de ticker da watchlist. Sem rede para
  Yahoo/Google News/BCB e sem Supabase: todas as telas foram vistas **apenas nos
  estados de indisponibilidade**. Nenhum dado de exemplo foi injetado.
- **AppTest/unitários:** navegação, memória de subaba, URL inválida, vínculos,
  histórico do Morning Call (sem `destinatario`, só leitura), Fundamentos
  (fonte fora × campo ausente × data da coleta).
- **Não validado:** produção, dados reais, layout com dados preenchidos (tabelas
  longas, gráficos), desempenho com fontes respondendo.

## 7. Limitações conhecidas

- Voltar/avançar recarrega a página: filtros guardados só na sessão se perdem.
- Vínculo notícia → empresa só aparece quando o ticker está escrito na manchete
  (`n["tickers"]`); notícias do feed da watchlist (achadas por busca do nome da
  empresa) não ganham o botão, de propósito.
- Atalho para um módulo oculto em "módulos visíveis" não navega (a rota cai na
  subaba atual sem aviso).
- `config.ICONES_SECAO` ficou sem uso; mantido para não conflitar com o #72.
- `data/prices.py:obter_cotacao_indice` não tem cache próprio (letreiro, pré-existente);
  a subaba Câmbio usa um wrapper com cache de 60 s.
