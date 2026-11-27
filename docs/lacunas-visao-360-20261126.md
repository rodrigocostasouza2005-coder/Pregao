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
