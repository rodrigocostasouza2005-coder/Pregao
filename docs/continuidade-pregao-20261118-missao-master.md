# Continuidade PREGÃO — MISSÃO MASTER (reconstrução completa), 2026-11-18

Relatório de fechamento da "MISSÃO MASTER — RECONSTRUÇÃO COMPLETA DO PREGÃO TERMINAL": diagnóstico em 6 frentes paralelas (Fase 0), seguido de implementação em fases (1-5) sem pausa pra autorização a cada etapa, por pedido explícito do Rodrigo. Este documento resume o que foi decidido/feito/verificado, pra quem retomar depois não precisar reconstruir o contexto.

## Estado no fechamento desta missão

- HEAD: `18fd749` (PR #336), 100% sincronizado com `origin/main`, 0 PRs abertas.
- Suíte completa (`pytest`) verde nesta mesma revisão de `main` (2722 testes — ver seção "Validação" abaixo).
- Todas as PRs desta missão (#326 a #336, listadas abaixo) mergeadas; nenhuma pendente de revisão. #336 foi fechada numa sessão de continuidade (2026-11-19), não no mesmo dia do disparo — único item que tinha ficado pendente no fechamento original.

## O que mudou, por fase

### Fase 0 — Diagnóstico (6 agentes paralelos, só leitura)

Evidência visual real das 12 áreas então existentes, capturada via Playwright antes de qualquer mudança de código (PRs #323/#324/#325, docs-only). Único achado CRÍTICO de toda a varredura: tabela do DCF Operacional com fundo branco quebrando a paleta (fix entrou nas fases seguintes, junto da reformulação de paleta). Achados MÉDIO/MENOR documentados e, na maioria, corrigidos nas fases seguintes (ver `docs/evidencias/validacao-visual-real-20261117/LEIA.md`, que concentra todo o histórico de evidência visual desta sessão, incluindo a revalidação final da Fase 4).

### Fase 1 — Design system e estrutura global (PR #326)

Paleta revisada (fundo quase-preto `#080A0D`, 3ª camada tonal "grafite" `#11151A`/`#171C22` pra header/sidebar/métricas, âmbar `#FFA028` como destaque, verde/vermelho/ciano recalibrados). As 4 variações de tema (ÂMBAR/FÓSFORO/AZUL/CLARO) ganharam a chave `grafite`, cada uma com valor próprio e consistente com sua matiz.

Nesta fase também: truncamento de `st.metric` corrigido (o wrapper interno do Streamlit, não só o elemento externo, precisava da regra `overflow:visible`).

### Fase 2 — Reconstrução de navegação (PRs #327, #328, #329)

- `COORDENADOR` → renomeada `COMITÊ` (sem a sub-aba `analisar` solta — unificada no fluxo normal).
- Nova área `CALENDÁRIO` (sub-abas Corporativo/Econômico, antes espalhadas em MERCADO/MACRO).
- Nova área `VALUATION` (sub-abas Parecer/Simulador, antes espalhadas em ANÁLISES/COMITÊ).
- Área `SETORES` dissolvida: "Mapa Setorial" removido (duplicata pura de outro painel já existente), "Visão por Setor"/"Catalisadores" migrados pra dentro de NOTÍCIAS.
- Área `MORNING-CALL` dissolvida: suas 4 sub-abas migraram pra dentro de RESEARCH.
- Zero função de render alterada nestas 3 PRs — só rota mudou. Confirmado por teste automatizado que as 45 rotas de `ui/navegacao.py` têm dispatch correspondente em `app.py` (sem rota órfã).

### Fase 3 — Inteligência visível (PRs #330, #331, #333, #334)

- **Divergência entre especialistas do Comitê** (PR #330): o campo já era calculado (`consolidacao.py:_divergencia_entre_analistas_comite`) mas nunca aparecia na UI — agora tem painel dedicado em COMITÊ, mostrando só `n_analistas_comparados`/`divergente`/`resumo` (nunca fabrica um "vencedor").
- **Cards por especialista corrigidos** (PR #333): o card do Model Builder mostrava "Pontos favoráveis/contrários" vazio/enganoso (esse campo não existe no schema dele) — agora cada especialista só mostra os campos que realmente tem; Valuation Reviewer ganhou renderização própria pros seus campos estruturados (`achados`/`limitações`).
- **3º motor de DCF duplicado removido** (PR #331): `ui/analises_tab.py` tinha sua própria function de cálculo de DCF, redundante com `data/coordenador_central/dcf.py`. Eliminada; o simulador inline agora usa o motor oficial (ganho real: passou a descontar dívida líquida e mostrar matriz de sensibilidade, que o motor duplicado não tinha).
- **Camada analítica em MACRO e CARTEIRA RECOMENDADA** (PR #334): as duas únicas áreas que ainda não tinham leitura textual junto do dado bruto (MERCADO/NOTÍCIAS/RADAR já tinham) ganharam `_leitura_macro`/`_leitura_carteira`, reaproveitando limiares/campos já existentes (ex. o mesmo limiar de concentração de 25% já definido em `data/radar.py`), sem inventar threshold novo.

### Fase 4 — Validação visual real (PR #335)

Recaptura de 17 telas (34 PNGs) depois de toda a reconstrução, com revisão pessoal de cada imagem (não só execução do harness). Achados:

- 2 flakes de captura (`home`/`calendário` em 1440px vinham 100% pretos — viewport redimensionado e screenshot tirado antes do repaint; confirmado comparando com a versão 1024px dos mesmos dados, que veio correta). Recapturados e corrigidos antes do commit.
- Tabela vazia em VALUATION › Parecer investigada a fundo: **não é bug** — a função que a alimenta (`radar.valuation_radar`) bate em yfinance ao vivo e não estava mockada no harness usado; reproduzido isolado (trava >25s neste sandbox, mesma instabilidade de rede já documentada no teste `test_compatibilidade_render_mercados_globais_e_render_research_e_fatores`). Nenhum PR desta missão tocou essa função — só a rota dela mudou.
- Nenhum CRÍTICO novo. Detalhe completo em `docs/evidencias/validacao-visual-real-20261117/LEIA.md`.

### Pedido adicional do Rodrigo durante a missão — Perfil da Empresa

Pedido literal: ver, junto do preço atual de uma empresa, um resumo da história/momento atual + opinião dos analistas, e poder acessar "o modelo que os agentes do Pregão fizeram".

Achado-chave: **já existia uma camada de dados pronta e testada pra isso, nunca conectada a nenhuma tela** — `data/empresa_perfil.py` (`obter_perfil_empresa`, 18 perguntas de equity research, cada uma com fonte/evidência rastreável, construída em 2026-11-12/13, testada em `tests/test_empresa_perfil.py`, mas **zero referência em qualquer arquivo de `ui/*.py`** até esta missão). "O modelo que os agentes fizeram" já era acessível via COMITÊ › HISTÓRICO (reabre qualquer análise salva: recomendação, preços-alvo, pareceres por especialista, divergências) — isso não precisou de mudança nova, só ficou confirmado nesta auditoria.

**Fechado em sessão de continuidade (2026-11-19, mesmo escopo de missão): PR #336, mergeada.** Implementação completa: novo painel "Perfil da empresa — resumo do negócio e momento atual" dentro de `_render_consolidado` (COMITÊ), logo após o cabeçalho de decisão, consumindo `obter_perfil_empresa` sem alterar a camada de dados em si. Revisão independente (regra 4 do `CLAUDE.md`) encontrou 1 achado real antes do merge — `comparar_ticker`/`listar_premissas` (Supabase) não tinha cache, reconsultando a cada rerun do Streamlit enquanto o painel estivesse na tela — corrigido na própria PR com `@st.cache_data(ttl=1h)` em `obter_perfil_empresa` (+ fixture de limpeza de cache nos testes existentes de `tests/test_empresa_perfil.py`, que quebravam por cache cruzado entre casos). 14 testes novos/atualizados em `tests/test_coordenador_tab_perfil_empresa.py`. Suíte completa: 2722/2722, 0 regressão. CI verde, mergeada via squash, branch remota deletada, checkout principal sincronizado (HEAD `18fd749`).

## Validação

- Suíte completa rodada mais de uma vez ao longo da missão (2679 testes); única falha observada em qualquer execução foi a flakiness de rede já conhecida (`VALE3.SA possibly delisted`, yfinance), nunca uma regressão de código desta missão.
- CI (Vercel/build) verde em todas as PRs mergeadas.
- Nenhuma migração de banco, credencial ou custo de API nova nesta missão — só UI/apresentação + 1 camada de consolidação de dado já existente sendo conectada à UI (Perfil da Empresa).

## Decisões a preservar (não redescobrir em sessão futura)

- `_secao_valuation`/`radar.valuation_radar` depende de yfinance ao vivo sem cache mockável nos harnesses locais — qualquer evidência visual futura desta tela precisa rodar com rede real disponível, ou aceitar a tabela vazia como limitação do harness, não do produto.
- Saúde dos Dados continua frente isolada (regra 8 do `CLAUDE.md`) — não foi tocada nesta missão.
- `data/empresa_perfil.py` é função pura, zero chamada de IA nova — qualquer expansão futura da UI que a consome deve continuar nesse princípio (nunca inventar texto pra pergunta com `disponivel=False`).

## Pendências em aberto (fora do escopo desta missão, não resolvidas aqui)

- `valuation_parecer`: validar em produção real (fora deste sandbox) se a chamada a yfinance responde dentro de um tempo aceitável pro usuário final — se não, pode precisar de cache/timeout dedicado (investigação nova, não incluída nesta missão).
- Pendências administrativas já listadas em `docs/continuidade-pregao-20261114.md` (GROQ_API_KEY nos Actions, Morning Call externo, etc.) seguem sem mudança — não fizeram parte do escopo desta missão.
