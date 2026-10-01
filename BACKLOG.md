# BACKLOG — PREGÃO

Pendências conhecidas, para resolver depois (ajustes visuais adiados
enquanto avançamos nas próximas fases).

## Auditoria 2026-09-30 — itens revistos (releitura do código real)

Vários itens abaixo listados em sessões anteriores já tinham sido
corrigidos como efeito colateral de outras tarefas, mas o BACKLOG não
tinha sido limpo. Confirmado lendo o código atual (não só memória):

- **Beta** já é calculado localmente desde a correção registrada em
  MANUAL.md (`data/prices.py:_calcular_beta`, cov/var 2 anos vs
  `^BVSP`) — item antigo removido daqui.
- **MM20 na mesma cor da linha de preço (modo LINHA)**: já corrigido —
  `app.py` usa `tema["neutro"]` pra MM20 em LINHA/AREA e só
  `tema["destaque"]` em CANDLE (onde não colide, preço vira barra sem
  cor própria). Candle confirmado com `increasing_line_color`/
  `decreasing_line_color` corretos.
- **Barra de ferramentas do Plotly em MACRO**: já está com
  `config={"displayModeBar": False}` em todos os `st.plotly_chart` de
  `ui/macro_tab.py` — item resolvido.
- **Eixo X do IPCA em mês/ano**: já implementado
  (`ui/macro_tab.py:_eixo_x_mes_ano`, ex: "ago/2026").
- **Cabeçalho de tabela cortado (PREÇOS/RESUMO) + espaço vazio
  embaixo** e **título "INDICADORES" sumindo + scrollbar interna**:
  mesma causa raiz provável — a regra
  `[data-testid="stMarkdown"]:has(table) { overflow-x: auto;
  overflow-y: hidden; }` em `style.css` foi adicionada depois (o
  comentário no próprio CSS já cita "RESUMO e INDICADORES" como motivo)
  especificamente pra evitar que `overflow-x:auto` sozinho virasse scroll
  vertical indevido — mecanismo idêntico ao que cortava o cabeçalho da
  PREÇOS, já que ambas são tabela dentro de `st.markdown`. **Ainda
  pendente confirmação visual** (sem acesso à extensão do Chrome nesta
  sessão) — se reaparecer, é outra causa, não essa.

## Visual / layout
- E-mail do usuário sumiu do header (só aparece o botão SAIR). Causa
  mais provável (2026-09-30): o botão SAIR usava `width="stretch"` e
  texto que não quebra linha, brigando por espaço com o chip de e-mail
  dentro de uma coluna estreita — a disputa deixava quase nada pro
  `pregao-user-chip`, que então cortava quase tudo via ellipsis
  (parecendo "sumido"). **Correção aplicada**: `col_user` ganhou mais
  largura relativa (1.35→1.7, `col_busca` cedeu um pouco), proporção
  interna foi de `[3,1]` pra `[4,1]`, e o botão SAIR perdeu o
  `width="stretch"` (fica do tamanho do próprio texto). Pendente
  confirmação visual real (print/inspeção) — se persistir, próximo
  passo é investigar `.block-container{overflow-x:clip}` recortando o
  header fixo quando a sidebar está expandida (ver comentário em
  `style.css` sobre `.block-container`).
- Limpeza de nome de empresa parece remover acentos em produção (ex:
  "Ginástica e Dança" → "Ginástica e Danca"). Testado localmente
  (`obter_nome_yf('SMFT3')`) e o resultado veio com acento correto —
  `longName` do yfinance e a função de limpeza não mexem em
  maiúscula/minúscula nem em encoding, só cortam o sufixo jurídico do
  final. Suspeita: diferença de locale/encoding entre o ambiente local e
  o container do Streamlit Cloud, não bug na lógica em si — investigar
  direto em produção (não reproduz local).

## Indicadores
- Dividend yield: investigado em 2026-09-30 — não há evidência de bug.
  `Ticker.dividends` do yfinance registra cada evento de distribuição
  (dividendo OU JCP) como uma linha própria por data-ex; o cálculo atual
  (`data/prices.py:_dividend_yield_12m`) só soma essas linhas na janela
  de 12 meses, sem nenhum ponto óbvio de dupla contagem. Não dá pra
  confirmar com 100% de certeza sem comparar contra a relação oficial de
  proventos de um ticker específico (CVM não traz valor pago, só
  metadado do documento) — manter como item de baixa prioridade, não
  reabrir sem um caso concreto de DY visivelmente inflado.

## Macro
- Curva pré (ETTJ ANBIMA): a fonte só guarda ~5-6 pregões de histórico
  rolante — comparação de "1 mês atrás" não funciona (testado, confirma
  o limite). Para viabilizar essa comparação, salvar um snapshot diário
  da curva no Supabase via GitHub Actions (Fase 7 do roadmap original,
  coleta automática). Já degrada graciosamente (aviso explícito na UI
  quando a comparação de 1 mês não está disponível).
- Curva pré: legenda (Hoje / 1 semana atrás / 1 mês atrás) aparece
  sobreposta/cortada no gráfico — ainda não investigado a fundo, precisa
  de inspeção visual real.

## Research
- BTG Research: API pública em
  `https://content.btgpactual.com/api/research/public-router/<servico>/api/<servico>/public/v1/...`
  (ex. que funciona: `.../media-research/.../medias/lives?status=LIVE&pageNumber=1&pageSize=8`).
  A lista de relatórios (requisição "ALL?pageNumber=1&pageSize=9&channel=...")
  deu 404 na home e não apareceu em /acoes/ultimos-relatorios; pode ser
  restrita a clientes. Próximo passo: procurar "public-router" nos bundles
  JS para mapear as rotas, ou testar a área aberta content.btgpactual.us.
- XP Investimentos: implementada (`data/research/xp.py`), API pública do
  WordPress (`conteudos.xpi.com.br/wp-json/wp/v2/{rel-acoes-fund,
  rel-artigo-aloc,rel-acoes-tec}`). IP deste sandbox de dev é bloqueado
  pelo CDN da XP (confirmado com `requests` e com `curl_cffi
  impersonate="chrome"` - mesmo Reference ID de bloqueio, então é IP/geo,
  não fingerprint de TLS); coletor testado só com dados mockados aqui,
  `ativa_por_padrao=False` até confirmar em produção/local.
- Reconhecimento rápido das 6 casas restantes (2026-09-23, sem
  implementar nada ainda):
  - **Itaú BBA** (`itau.com.br/itaubba-pt/analises-economicas`) e
    **Santander** (`santandercorretora.com.br`): domínio bloqueado (403)
    já na raiz, deste sandbox - não deu pra investigar mais.
  - **BB Investimentos** (`investalk.bb.com.br/relatorios-e-analises`):
    site acessível, mas `/wp-json/` e `/feed/` retornam 403 - API
    deliberadamente fechada.
  - **Safra** (`oespecialista.safra.com.br`): é WordPress de verdade
    (`/wp-json/` existe), mas a REST API está bloqueada por plugin
    ("DRA: Only authenticated users can access the REST API").
  - **Ágora/Bradesco** (`insights.agorainvestimentos.com.br/conteudo`) e
    **Inter** (`interinvest.inter.co`): site acessível, mas sem
    WordPress/JSON óbvio no HTML de superfície (Inter parece SPA React -
    `data-react-helmet`). Precisariam do mesmo trabalho de arqueologia de
    bundle JS feito pro BTG pra confirmar se têm API interna usável - não
    investigado a fundo ainda.

## Fases futuras
- Morning Call da Genial: transcrição + resumo automático. Fase futura,
  ainda não desenhada (fonte, formato do resumo, frequência de
  atualização etc. — definir quando chegar a vez).
