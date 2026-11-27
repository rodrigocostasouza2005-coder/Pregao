# Lacunas estruturais encontradas no redesign da Visão 360 (2026-11-26)

Registro das coisas que a missão `visao-360-redesign-20261126` **encontrou e
NÃO corrigiu**, por decisão explícita do escopo: aquela missão era redesenho
de apresentação, e as regras eram claras — "não alterar cálculos financeiros
durante o redesign visual", "não alterar a lógica/cálculo do Comitê", "se
identificar lacuna estrutural importante, documentar e propor implementação
separadamente".

Cada item abaixo é um achado real, visto no código ou na tela com dado real
de shape; nenhum é hipótese sobre código que não foi lido.

---

## 1. Não existe modelo de valuation setorial — banco, seguradora e utility
   usam o mesmo DCF genérico

**Onde:** `data/coordenador_central/dcf.py` (motor único: FCF + crescimento +
WACC → Gordon Growth, líquido de dívida) e
`data/coordenador_central/pareceres.py` (Model Builder).

**O que acontece:** o mesmo DCF roda para qualquer ticker. Para banco, o
conceito de "fluxo de caixa livre da firma" e "dívida líquida" não tem o
mesmo significado (dívida é insumo operacional, não estrutura de capital), e
o preço justo sai metodologicamente torto — não errado por bug, errado por
modelo. O pedido do redesign lista "modelos específicos por setor" como algo
a ser *apresentado quando existir*; hoje não existe nenhum.

**Proposta (missão separada):** um registro de modelo por setor
(`DDM`/`excesso de retorno` para bancos, `P/VP vs ROE` para seguradoras,
`EV/EBITDA regulado` para utilities), escolhendo o modelo pela classificação
setorial que já existe (`config.IBOVESPA_SETORES`). A tela já está pronta
para listar mais de um modelo lado a lado — a seção "Modelos de avaliação"
da Visão 360 hoje exibe DCF, P/L setorial, consenso e DCF interativo
separados; um modelo setorial entraria como mais um bloco, sem redesenho.

**Risco de não fazer:** usuário lê "PREÇO JUSTO · DCF R$ X" para um banco e
trata como comparável ao de uma petroleira.

---

## 2. Indicadores de CRESCIMENTO só existem se o Comitê já tiver rodado

**Onde:** `data/prices.py:obter_indicadores` (ponto atual do yfinance) não
traz nenhum campo de crescimento; receita YoY e ROIC trimestral só aparecem
em `pareceres.py:_parecer_market` → `analista["indicadores"]`, ou seja, só
depois de uma análise do Comitê, e só para empresas brasileiras (série
trimestral da CVM).

**O que acontece na tela:** a categoria "Crescimento" dos indicadores
fundamentalistas fica com 0 ou 1 indicador para a maioria dos tickers. A
Visão 360 diz o motivo real (não finge que o dado não existe), mas a
categoria é estruturalmente anêmica.

**Proposta (missão separada):** expor `revenueGrowth`/`earningsGrowth` do
`tk.info` do yfinance em `obter_indicadores` (zero requisição nova — o dict
já é buscado) e deixar claro na UI que é o ponto do provedor, não a série da
CVM. Precisa de validação contra dado real antes de confiar nos campos
(mesmo cuidado que foi tomado com `freeCashflow` em 2026-10-30).

---

## 3. Dois "preços-alvo" do Comitê sem potencial próprio no consolidado

**Onde:** `consolidado["sinal_comite"]` traz `upside_modelo_pct` (do DCF),
mas **não** traz o potencial de `preco_alvo_pl_setorial` nem de
`preco_alvo_consenso`.

**O que a tela faz hoje:** calcula o potencial dessas duas referências com
`ui/analises_tab.py:potencial_pct` — o mesmo helper já usado em produção para
o preço-alvo das casas — e rotula explicitamente como "potencial
indicativo". Não é cálculo novo, mas é cálculo **na camada de UI**, que é o
lugar errado para ele morar.

**Proposta (missão separada):** `consolidacao.py` passar a devolver
`upside_pl_setorial_pct` e `upside_consenso_pct` junto dos respectivos
preços-alvo, e a UI só exibir. Mudança no retorno de `consolidar()` → exige
revisão de quem mais consome o dict.

---

## 4. "Confiança" e "recomendação" podem se contradizer sem nenhum freio

**Onde:** `data/coordenador_central/consolidacao.py` — o sinal quantitativo
(`sinal_comite`, score sobre ROE/margem/dívida/FCF/crescimento/P/L relativo)
e a confiança (`_confianca`, baseada em quantos especialistas trouxeram
evidência) são calculados de forma **independente**.

**O que acontece:** é perfeitamente possível sair "COMPRA / CONFIANÇA
INSUFICIENTE" — recomendação direcional sustentada por quase nenhuma
evidência. O redesign tratou isso **só na apresentação** (a confiança virou
um medidor visual separado da recomendação, e a combinação direcional + baixa
confiança recebe um aviso dedicado de "hipótese a confirmar"), porque a
missão proibia mexer na lógica do Comitê.

**Pergunta em aberto para o dono do projeto (não é correção proposta):**
deveria existir um piso de confiança abaixo do qual o Comitê **não emite**
COMPRA/VENDA, devolvendo INCONCLUSIVO? Isso é decisão de produto, não de
implementação.

---

## 5. `render_perfil_empresa_tab` e `render_consolidado` emitiam markup sem o
   CSS do próprio módulo

**Status: CORRIGIDO nesta missão** (fica registrado porque é causa raiz de
parte do "parece relatório bruto"): só as 5 subabas de COMITÊ chamavam
`_injetar_css`, então `.coord-nota`/`.coord-badge`/`.coord-tabela`
renderizavam **sem estilo** em ANÁLISES > Perfil da Empresa e em ANÁLISES >
Visão 360. Agora existe `coordenador_tab.injetar_css()` público e as duas
telas o chamam.

---

## 6. Sobreposição de 16px em qualquer bloco de HTML cru do app

**Status: corrigido só para as classes novas do design system.** O Streamlit
aplica `margin-bottom: -16px` em todo `stMarkdownContainer`; blocos de HTML
cru que terminam numa `<div>` perdem 16px e o elemento seguinte sobe por
cima do último conteúdo (medido com Playwright, ver
`docs/evidencias/visao-360-redesign-20261126/README.md`).

A correção foi deliberadamente restrita às classes `.ds-*`/`.v360-*` (código
novo) para não mexer no espaçamento de todas as telas antigas de uma vez.
**Outras abas provavelmente têm o mesmo defeito**, em menor escala — vale uma
varredura própria, com medição antes/depois tela a tela.

---

## Achados adicionais da revisão independente de 2026-11-27 (correções do PR #365)

Os 4 itens abaixo vieram de uma segunda rodada de revisão (correção dos
defeitos reais encontrados nesta PR — "None" literal, cache ausente,
notícia curada perdida, indicador desaparecendo, link de histórico
enterrado e rótulo divergente, todos corrigidos na própria branch). Estes 4
são de baixo risco e foram deliberadamente **documentados em vez de
corrigidos**, porque a correção de verdade teria escopo maior que "rápido":

### 7. `render_perfil_posicionamento` continua sem nenhuma chamada externa

**Onde:** `ui/coordenador_tab.py:1671`.

**Status:** o item irmão, `render_perfil_noticias` (linha 1684), **deixou de
ser dead code** nesta rodada de correções — agora é chamado de
`ui/visao_360_tab.py:_render_noticias` (reincorporação da lista curada de
notícias, item 3 da revisão). `render_perfil_posicionamento` continua sem
nenhum chamador fora do próprio módulo (só a função privada
`_render_perfil_posicionamento` é usada, internamente, por
`render_perfil_empresa_tab`). Baixo risco - função pública wrapper sem uso,
não lógica morta de verdade (a implementação privada roda normalmente em
ANÁLISES > Perfil da Empresa). Remover o wrapper público ou usá-lo em algum
outro ponto de composição são as 2 saídas; nenhuma foi tomada aqui por não
ser pedida.

### 8. Padrão de seletor CSS repetido 4x em `style.css`

**Onde:** `[data-testid="stButtonGroup"] button[aria-checked="true"], ...
[aria-pressed="true"]`, nas linhas ~655, ~704, ~744 e ~789.

**Por que não foi unificado:** os 4 blocos repetem a MESMA estrutura de
seletor (pills genéricas, navegação principal, subnavegação, fita de
tickers da Visão 360), mas cada escopo tem valores DIFERENTES de
background/borda/cor (sólido âmbar vs. `color-mix` transparente vs.
sublinhado sem fundo). Unificar de verdade exigiria introduzir variáveis
CSS por escopo (`--sc-ativo-bg`/`--sc-ativo-borda`/`--sc-ativo-cor`) na regra
genérica e sobrescrevê-las em cada `.st-key-*` - mudança que toca a
navegação principal do app inteiro (não só a Visão 360), fora do escopo
desta PR e sem validação visual Playwright de todas as telas afetadas.

### 9. Escape-hatch `ds-bloco` existe em CSS mas sem helper Python

**Onde:** `style.css:1795` já inclui `.ds-bloco` na lista de seletores que
recebem a compensação do `margin-bottom:-16px` (ver item 6 acima) - a classe
já está pronta pra qualquer bloco de HTML cru novo se marcar com ela. Mas
nenhuma função de `ui/design_system.py` hoje gera
`<div class="ds-bloco">...</div>` - quem precisar dela tem que escrever a
classe à mão no HTML literal. Proposta (rápida, mas não feita aqui por não
ter nenhum chamador real no momento): um helper
`ds.bloco_html(conteudo_html: str) -> str` que embrulha com a classe.

### 10. Decodificação dos 3 cenários do DCF duplicada em 2 arquivos

**Onde:** `ui/visao_360_tab.py:_render_cenarios_dcf` (~895-899) e
`ui/coordenador_tab.py` (~986-997, dentro do parecer completo do Model
Builder) - as duas leem `model_builder["cenarios"]` com a MESMA tupla de
chaves `("pessimista", "base", "otimista")` e o mesmo `.get(chave) or {}`.

**Por que não foi unificado:** as 2 funções renderizam de forma bem
diferente (3 cards compactos lado a lado na Visão 360 vs. tabela de 8
colunas no parecer detalhado do Comitê) - um helper comum só valeria a pena
pra extrair a ITERAÇÃO (`[(chave, cenarios.get(chave) or {}) for chave in
(...)]`), não a renderização. Baixo risco de bug (são só 3 chaves
literais, improvável de divergir sozinho), mas toca
`ui/coordenador_tab.py`, que tem cobertura de teste extensa própria -
mudar ali pedia validação maior que "rápido" permite nesta correção.

---

## PENDÊNCIA DE SCHEMA — `research_recomendacoes_historico` (auditoria completa 2026-11-26)

**Status: migration PRONTA e NÃO APLICADA. Depende de aprovação explícita do
Rodrigo — nenhum agente aplica schema em produção (CLAUDE.md).**

**O que foi investigado (Tópico 4 da auditoria completa):** a tabela
`research_recomendacoes_historico` não existe no Supabase de produção
(`PGRST205`, confirmado múltiplas vezes em sessões anteriores), embora
`PROGRESSO.md` a documente como "alimentada de verdade". A hipótese de SQL
escrito e nunca aplicado **se confirmou**: o `create table` existe desde
2026-10-01, mas estava **dentro de `sql/research.sql`** — o mesmo arquivo que
cria e altera `research_itens`, tabela que já está em produção com dado real.
Mesmo padrão do caso já documentado de `sql/carteira_recomendada.sql`
(escrito em 11/2026, aplicado só em 2026-11-14).

**O que foi preparado nesta missão:** `sql/research_recomendacoes_historico.sql`
— migration isolada, idempotente, revisada contra o código que usa a tabela
(`data/research/historico.py`: todas as colunas lidas/escritas existem no
schema — `casa`, `ticker`, `recomendacao`, `preco_alvo`, `potencial_pct`,
`capturado_em`), com RLS ativado sem policies (padrão do projeto) e **dois**
índices: o já proposto `(casa, ticker, capturado_em desc)` e um novo
`(casa, capturado_em desc)` para `_tickers_capturados_hoje`, que filtra por
casa + data sem ticker no predicado. Inclui bloco de rollback. O bloco
original em `sql/research.sql` foi mantido e passou a apontar para o arquivo
novo (os dois são equivalentes e idempotentes; aplicar o isolado é o caminho
recomendado, porque não re-roda nenhum `ALTER` contra `research_itens`).

**Nada foi aplicado em produção.** Não houve nenhuma execução de SQL, e a
ausência da tabela não foi reconfirmada nesta missão (sem acesso real ao
Supabase de produção aqui) — a conclusão se apoia nas confirmações
anteriores registradas em `sql/research.sql` e em
`docs/continuidade-pregao-20261114.md`.

**Ressalva importante para a decisão:** aplicar a migration é
**necessário, não suficiente**. Hoje não existe fonte ATIVA escrevendo nessa
tabela — `data/research/historico.py:COLETA_GENIAL_ATIVA = False` (coletor da
Genial desativado por bloqueio externo) e a Genial é a única casa com dado
estruturado de recomendação/preço-alvo pronto. Depois de aplicada, a tabela
existe e fica vazia até alguma fonte voltar a alimentá-la; nada é preenchido
retroativamente. O ganho imediato é parar de gerar `PGRST205` e sair do
estado atual de "não existe onde guardar".

**Achado adicional, não corrigido (fora do escopo da missão):**
`ui/analises_tab.py:1980` chama `historico_ticker("genial", ticker, limite=5)`
com a casa em minúsculas, enquanto todo o resto do projeto usa
`"Genial Analisa"` (`ui/research_tab.py:361`, `data/radar.py`). Como a consulta
filtra `.eq("casa", casa)`, essa chamada retornaria `[]` mesmo com histórico
salvo. Não é observável hoje (a tabela não existe, então tudo retorna vazio
de qualquer jeito) e virará um bug real no dia em que a migration for
aplicada e a tabela tiver linhas. Decisão de corrigir: do Rodrigo.
