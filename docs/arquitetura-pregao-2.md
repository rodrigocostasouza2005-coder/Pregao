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

## 5. Compatibilidade com PRs abertos (19/10/2026)

- **#72 (USUÁRIOS admin + oferta de Morning Call):** a aba USUÁRIOS vira
  `Subaba("usuarios", "Usuários", admin=True)` em MAIS, com despacho
  `if rota == ("mais", "usuarios"):` reconfirmando `_eh_admin`. A linha
  `prefs["morning_call_email_perguntado"] = True` do toggle passa a ir em
  `ui/morning_call_tab.py:render_preferencias`.
- **#70 (atalho CTRL K):** independente da navegação; o bloco entra no cabeçalho
  sem mudança.
- **#76 (MAIS NEGOCIADOS clicável):** usa `_ir_para_equity`, que agora navega para
  ANÁLISES › Empresas; conflito só no texto do `help`.
- **#75, #77, #79, #80, #71, #78:** sem sobreposição relevante.
