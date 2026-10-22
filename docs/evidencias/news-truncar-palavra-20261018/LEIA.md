# NEWS — corte de manchete nunca no meio de uma palavra (2026-10-18)

Capturas geradas com um harness local (Streamlit + Playwright) chamando
`ui.news_tab._linha_noticia` real (componente do feed "wire") com
**dados de exemplo** (não são dados de produção).

## O que foi corrigido

`_truncar` (`ui/news_tab.py`, usada pra cortar manchete no feed wire —
limite 92 caracteres — e teaser/resumo em outros 3 pontos do arquivo —
limite 320) cortava por **contagem de caracteres pura**
(`texto[:limite-1]`), sem respeitar fronteira de palavra. Uma manchete
real demonstrou o problema: "...aprovação unanime do conselho..." virava
"...aprovação u…" — cortando "unanime" até sobrar só a letra "u".

Corrigido: recua até o último espaço dentro do limite antes de cortar;
só mantém o corte duro quando não há nenhum espaço pra recuar (token
único sem espaço, ex. URL/hashtag longo — corte duro continua melhor que
devolver string vazia).

## Testes

Teste de reprodução escrito e confirmado **falhando no código antigo**
(a última "palavra" do resultado truncado não era uma palavra real do
texto original) antes da correção. Suíte completa: 894 passed — nenhum
teste existente que depende de `_truncar` (manchete do wire, teaser
editorial, teaser live) quebrou, confirmando a correção é compatível com
todos os pontos de uso.

## Validação visual

Validado com Playwright (harness isolado) em 2 breakpoints (1280px/390px):
texto corta em fronteira de palavra, reticências renderizam corretamente,
sem erro de console.

**Observação (não é regressão desta correção):** no breakpoint mobile, a
própria célula do botão (CSS da coluna, não `_truncar`) também aplica seu
próprio corte visual por largura — visível no screenshot mobile mesmo na
manchete curta ("Manchete curta e normal, sem precisar co…"), que
`_truncar` nem chega a tocar (bem abaixo do limite de 92 caracteres). É
um mecanismo de truncamento **separado**, em CSS, não tocado por esta
correção — fora do escopo desta PR.
