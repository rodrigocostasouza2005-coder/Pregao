# Plano consolidado — auditoria do Fincept Terminal como referência pro PREGÃO

**Data:** 2026-11-12
**Agente:** FINCEPT-E (consolidação — não reabriu nenhum clone do Fincept, trabalhou só sobre os 3 relatórios já produzidos)
**Entradas:** PR #290 (Fincept-A, arquitetura/infra), PR #289 (Fincept-B, coletores), PR #288 (Fincept-D, UX). **Fincept-C (agentes de IA/comitê) não produziu PR** — ver nota no final.
**Repo auditado pelas 3 missões:** [github.com/Fincept-Corporation/FinceptTerminal](https://github.com/Fincept-Corporation/FinceptTerminal), licença **AGPL-3.0-or-later**.

---

## Resumo executivo

As três auditorias (arquitetura, coletores, UX) chegaram à mesma conclusão de fundo por caminhos independentes: o Fincept Terminal **não é mais comparável "stack com stack"** com o PREGÃO — desde a v4 é um app desktop nativo C++20/Qt6 com Python embutido só como scripts de subprocesso, não um webapp. Isso invalida qualquer ideia de copiar módulos inteiros ou arquitetura de transporte, mas **não invalida os padrões internos**, que são agnósticos de linguagem: catálogo de conectores gerado por código (não escrito à mão), registro estruturado de saúde/bloqueio de fonte, cache com degradação graciosa sob rate-limit, migrations numeradas com runner, "architecture ratchet" no CI, e composição visual densa por particionamento em muitos widgets pequenos (não fonte menor).

**Nenhuma linha de código, texto ou asset do Fincept foi copiada para o PREGÃO** em nenhuma das três auditorias — verificado diretamente nos diffs das PRs #288/#289/#290 (ver seção de licenciamento), não só no relato de cada agente.

Achado transversal importante, repetido nas três auditorias: em vários pontos específicos o PREGÃO **já é mais robusto** que o Fincept hoje (gate anti-alucinação em `qualidade.py`, classificação de causa de erro em `coletores_status.py`, checagem de `robots.txt`, dedupe de research por link). A lista abaixo não é "o Fincept é melhor, copiar" — é "o Fincept generalizou/estruturou um princípio que o PREGÃO já pratica localmente mas de forma dispersa ou ad hoc".

Das PRs de implementação do lote atual (A–F, missão de 2026-11-11), **todas as 6 já estão mergeadas** (#281–#286). O único trabalho de implementação ainda em voo nesta data é a **PR #287** (Agente C, extração de PDF/OCR + classificação de ticker no corpo + confirmação do comparador), que toca só `data/research/classificacao.py`, `data/research/resumir.py`, `requirements.txt` e testes — **nenhuma recomendação abaixo colide com esses arquivos**, o que libera a maioria dos itens de baixo risco para seguir já.

---

## 1. Análise de licenciamento (AGPL-3.0-or-later)

### O que a AGPL exige

A AGPL-3.0-or-later é a licença **copyleft mais forte** do ecossistema GPL. Dois pontos centrais:

1. **Copyleft forte (herdado da GPLv3):** qualquer obra derivada que incorpore código licenciado AGPL — incluindo versões modificadas, trechos colados, ou combinações que formem uma "obra combinada" sob a definição da própria licença — deve ser distribuída inteira sob a mesma licença AGPL, com código-fonte disponível para quem recebe a obra.
2. **Cláusula de network use (Seção 13, o diferencial da AGPL em relação à GPL comum):** se o programa (ou uma obra derivada dele) é modificado e **executado para interagir com usuários remotamente por uma rede** — exatamente o caso de um serviço acessado via navegador, como o PREGÃO rodando no Streamlit Community Cloud —, o detentor do serviço é obrigado a oferecer aos usuários remotos uma forma de obter o código-fonte correspondente, sob a mesma licença AGPL. Isso é o que diferencia AGPL de GPL: a GPL comum só aciona a obrigação de liberar código na *distribuição* de binário/pacote; a AGPL aciona a obrigação também quando o software é só **servido via rede**, sem nunca ser "distribuído" no sentido tradicional — é desenhada precisamente para fechar essa lacuna do modelo SaaS.

**Consequência prática para o PREGÃO:** se o PREGÃO incorporasse código-fonte real do Fincept (um módulo copiado, uma função adaptada, um trecho de lógica não-trivial transcrito), e isso fosse considerado parte da "obra combinada" rodando no serviço, o PREGÃO inteiro — todo o código servido aos usuários via Streamlit Cloud, não só o trecho copiado — provavelmente passaria a ter que ser liberado sob AGPL também. Isso mudaria a natureza do projeto (hoje presumivelmente proprietário/privado) de forma irreversível e não é uma decisão que um agente de auditoria pode tomar ou mitigar silenciosamente.

**O que NÃO aciona essa obrigação:** reimplementação independente a partir de **conceitos, padrões e ideias de arquitetura** — descritos em prosa própria, sem copiar código-fonte, texto literal de documentação, ou assets (imagens, ícones, CSS/QSS) — é uma obra nova, não uma obra derivada. Ler como um sistema funciona e escrever, do zero, um sistema próprio que resolve o mesmo problema de forma equivalente (mesmo que inspirado) não é coberto por copyleft de nenhuma licença — isso é a distinção clássica entre "ideia" (não protegida por direito de autor/licença de software) e "expressão" (código-fonte literal, protegida e sujeita à licença).

### Verificação feita nas 3 PRs (não só o relato de cada agente)

Rodei `gh pr diff` nas três PRs e inspecionei o diff completo, não apenas os resumos:

| PR | Arquivos alterados | Blocos de código (` ``` `) no diff | Conclusão |
|---|---|---|---|
| #290 (arquitetura) | só `docs/auditoria-fincept-arquitetura-20261112.md` (novo arquivo) | **zero** | Nenhum código citado literalmente; nomes de classes/arquivos do Fincept citados em prosa (ex. `DataHub.h`, `TopicPolicy`) como referência factual, não como trecho de código funcional |
| #289 (coletores) | só `docs/auditoria-fincept-coletores-20261112.md` (novo arquivo) | **zero** | Mesmo padrão — descrição em prosa de contratos/convenções, nenhum trecho de script Python do Fincept colado |
| #288 (UX) | só `docs/auditoria-fincept-ux-20261112.md` (novo arquivo) | **zero** | Descrição de composição visual em prosa; nenhum QSS/CSS/HTML do Fincept copiado |

Confirmação adicional: os três documentos citam explicitamente, na própria abertura, que o clone do Fincept foi feito fora do worktree do PREGÃO (pasta temporária, nunca commitada) e que nada foi copiado — e essa afirmação **se sustenta** na inspeção direta do diff, não é só autodeclaração do agente. As três missões também foram estritamente documentais: nenhuma delas tocou `ui/*.py` ou `data/research/*.py` (confirmado pela lista de arquivos alterados de cada PR, que contém apenas o próprio arquivo `.md` novo).

**Veredito:** as três auditorias são seguras sob a ótica de licenciamento — zero exposição a obrigação de AGPL. A recomendação de todas as três é a mesma, e deve continuar valendo para qualquer implementação futura baseada nelas: **reimplementar os padrões do zero, nunca copiar/adaptar código-fonte, texto de documentação, ou assets visuais do Fincept**. Isso vale também para qualquer paleta de cor/ícone específico eventualmente visto em screenshot — a inspiração deve parar na composição/princípio, nunca em pixels ou arquivos reais.

---

## 2. Lista consolidada e priorizada de oportunidades

Itens duplicados entre as auditorias foram mesclados (ex. "catálogo de conectores autogerado" apareceu tanto na auditoria de arquitetura quanto na de coletores — é a mesma ideia, mesclada no item 1 abaixo). Critério de priorização: impacto × esforço × risco de colisão com o lote de implementação em voo (hoje, só a PR #287 aberta — ver seção 3).

### Prioridade 1 — Implementar já (sem colisão, baixo esforço, alto valor)

**1. Migrations SQL numeradas + tabela de controle de versão aplicada**
*(origem: Achado 3 do PR #290)*
`sql/` hoje tem 20 arquivos soltos por domínio, sem numeração nem registro de quais já foram aplicados em produção. Isso já causou **2 incidentes reais documentados** no próprio código (`eventos_resultados`, `resumos_ia_cache` usadas em código antes do `.sql` correspondente rodar em produção, mascarado porque "tabela ausente" e "credencial inválida" geram o mesmo sintoma). Proposta: renomear convenção para `sql/NNN_descricao.sql`, criar tabela `schema_migrations(nome, aplicado_em)` no Supabase, e um script Python curto (usando `data/supabase_client.py` já existente) que lista migrations pendentes.
*Colisão com PR #287: nenhuma (287 não toca `sql/`).* **Ressalva:** isso é uma mudança de convenção de schema/produção — por política já registrada (aprovação antes de merge em produção para tudo que toca schema/migration/dado real), a implementação deve ir a PR aberta e **esperar aprovação explícita do Rodrigo antes do merge**, mesmo que o código possa ser escrito já.

**2. "Architecture ratchet" no CI**
*(origem: Achado 4 do PR #290)*
Script Python (~100-200 linhas) dentro de `testes.yml` que conta ocorrências de padrões ruins conhecidos (ex.: número de `except Exception:` sem log associado, número de módulos em `data/research/*.py` sem o padrão de erro-classificado já estabelecido em `coletores_status.py`) contra uma baseline — falha o PR só se o contador **subir**. Valor alto justamente agora, com múltiplos agentes editando os mesmos diretórios em paralelo sem revisão humana linha-a-linha.
*Colisão: nenhuma — é infraestrutura de CI, não toca código de produção.* Risco baixo, não precisa de aprovação prévia (não é schema/dado real).

**3. Catálogo de conectores de research gerado por AST + gate de CI**
*(origem: mesclado — Achado 2 do PR #290 + achado #1 da lista final do PR #289, mesma ideia)*
Script (`scripts/gen_research_catalogo.py`) que lê via `ast` (nunca importa) cada `data/research/<casa>.py`, extrai docstring + disponibilidade/motivo de bloqueio + nome da função coletora, e regenera um catálogo versionado — com modo `--check` que falha o CI se o catálogo commitado estiver desatualizado. Hoje a lista de casas/comandos vive só no docstring de `data/research/__init__.py`, escrita e mantida à mão.
*Colisão: nenhuma — PR #287 não toca `data/research/__init__.py` nem módulos de casa.* Puramente aditivo (novo script + novo doc gerado), seguro para seguir em paralelo com #287.

**4. Seção "dívidas conhecidas" viva na documentação de arquitetura**
*(origem: Achado 6 do PR #290)*
Curto, baixo custo: uma seção dentro de `docs/arquitetura-pregao-2.md` com tabela de dívidas técnicas conhecidas, impacto e dono/plano — atualizada a cada PR que resolve ou introduz uma. Reduz retrabalho e descoberta repetida do mesmo problema por agentes diferentes (hoje disperso em comentários de código do tipo "achado real 2026-10-15").
*Colisão: nenhuma, é só edição de doc.*

### Prioridade 2 — Implementar depois do lote atual mergear

**5. Registro estruturado (não só prosa) de "por que esta fonte está desativada"**
*(origem: Achado 1 do PR #289)*
Campo consultável por código (ex. `bloqueio: {motivo: str, checado_em: date}` em `CASAS` ou tabela nova) em vez de só o docstring rico em texto livre de `data/research/__init__.py` hoje. Depende logicamente do item 3 (catálogo) para fazer sentido de verdade — por isso vem depois, mesmo sem colisão de arquivo direta. Toca o mesmo módulo central (`data/research/__init__.py`) que outras frentes (B-expansão de casas) tendem a editar com frequência — menor risco esperar o ritmo de PRs de expansão de casas estabilizar.

**6. Cache de 2 níveis com degradação graciosa sob rate-limit**
*(origem: Achado 1 do PR #289, técnica "economic_calendar.py")*
Hoje o cooldown de 10 min (`_COOLDOWN_FALHA_S`) só evita martelar uma fonte quebrada — não serve um valor staleado como substituto. Proposta: dois TTLs (fresco curto / fallback mais longo só acionado em erro), escrita atômica de cache (`tmp` + `os.replace`). Mais valioso quando houver coletor de calendário/evento com rate-limit conhecido — vale esperar a expansão de casas definir se esse padrão de coletor vai existir.

**7. Registro central de freshness/cache por item de dado (versão simplificada do DataHub)**
*(origem: Achado 1 do PR #290)*
Tabela/dict `{topico, ultimo_valor_ts, ultimo_erro, ttl_esperado, em_voo}` consultável por qualquer módulo de `data/*.py`, generalizando o padrão que `data/ia_cache.py` já faz ad hoc (reserva anti-duplicação por `chave_documento`). Esforço médio, toca potencialmente vários módulos de coleta ao mesmo tempo — melhor depois que a onda atual de edição em `data/research/` esfriar, para não competir por revisão/merge com PRs de expansão de fonte.

**8. Proveniência explícita em dado derivado/fallback**
*(origem: Achado 5 da lista final do PR #289, padrão `peer_source`)*
Marcar explicitamente `origem: "casa"` vs `origem: "inferido"` onde o PREGÃO já classifica setor/empresa/peer por heurística, e avisar/impedir uso de inferência em comparação direta. Depende de onde a classificação heurística vive hoje (parte dela está em `data/research/classificacao.py`, que a PR #287 **está editando agora** — colisão direta). Esperar #287 mergear antes de tocar esse arquivo.

**9. Disciplina de identificação/paginação em APIs oficiais tipo SEC**
*(origem: Achado 5 final do PR #289)*
User-Agent descritivo com contato, delay fixo por requisição, `HTTPAdapter` com retry/pool de conexão — só relevante **se e quando** o PREGÃO vier a consumir uma API regulatória estruturada (CVM/B3). Não há gatilho concreto hoje; guardar como padrão de referência para quando aparecer.

**10. Badges/pills de classificação de impacto/sinal**
*(origem: seção 4 do PR #288)*
Pill pequena ("ALTA/BAIXA/NEUTRA", "IMPACTO ALTO/MÉDIO/BAIXO") ao lado de título em listas — relevante direto para o painel de teses do PR #166 (Casas de Análise) e para Radar/Notícias. Puro HTML/CSS sobre infraestrutura de design system já existente, mas toca exatamente as telas que a frente de redesign visual (D) está trabalhando agora — esperar essa frente definir a composição final antes de inserir um elemento novo de UI que ela teria que reconciliar depois.

**11. Barra inline dentro de célula de ranking**
*(origem: seção 7 do PR #288, achado #1 da lista final de UX)*
`<div style="width:NN%">` em célula de tabela HTML para peso setorial/score/volume relativo — marcado pelo próprio Fincept-D como o achado "mais barato e com maior ganho de legibilidade imediato". Mesma lógica do item 10: espera a frente de redesign visual estabilizar a composição de tabela antes de inserir.

**12. Particionamento em múltiplos widgets pequenos por tela**
*(origem: seção 1 do PR #288, achado #3 da lista final de UX)*
Mudança de composição de layout (muitos widgets de 150-250px lado a lado, não fonte menor) — é exatamente o tipo de mudança estrutural que a missão de redesign já em andamento está endereçando; não faz sentido uma segunda frente tocar o mesmo layout em paralelo. Esperar a reformulação estrutural atual definir a grade antes de aplicar esse princípio.

**13. Filtro inline + paginação explícita em tabelas longas**
*(origem: seção 5 do PR #288)* Mesma lógica de espera — toca composição de tabela que o redesign visual está tocando.

**14. Seletor de período como linha de abas acima do gráfico (não dropdown)**
*(origem: seção 6 do PR #288)* Pequeno, mas toca `ui/graficos.py`, que já teve mudança recente (RSI/MACD/Bollinger, PR #282); aguardar qualquer PR de gráfico em voo.

**15. Matriz de correlação / gauge como HTML simples em vez de Plotly**
*(origem: seção 6 do PR #288)* Ganho de performance/consistência, não de funcionalidade nova — baixa urgência, mesma dependência de `ui/graficos.py` do item 14.

**16. Checkpoints estruturados por etapa (substituindo os `.txt` soltos de `coletor_local.py`)**
*(origem: Achado 5 do PR #290)* O próprio Fincept-A já classificou como prioridade 6/6 e impacto baixo ("já existe versão básica que cumpre o papel"). Mantém-se baixa prioridade na consolidação; só vale revisitar se o volume de coleta crescer a ponto de "não reprocessar do zero" passar a importar de verdade.

### Prioridade 3 — Não vale o esforço/risco agora

- **Qualquer coisa de C++/Qt6/CMake/instalador nativo** — fora de escopo por decisão explícita já registrada (não migrar de Streamlit).
- **Framework de 37 agentes de IA com personas / MCP server completo com 40+ ferramentas** — investimento de engenharia muito maior que o problema atual do PREGÃO; só faria sentido se o PREGÃO expusesse uma interface de agente externo, que não é o caso.
- **SecureStorage com AES-256-GCM local** — o PREGÃO já delega segredos a `st.secrets`/variáveis de ambiente; não há "disco local do usuário" a proteger como um app desktop tem.
- **Unificar busca de ativo + navegação num único campo de comando** (seção 8 do PR #288) — a própria auditoria de UX concluiu que a solução atual do PREGÃO (`st.selectbox` sem round-trip de rede por tecla) já é tecnicamente melhor em custo que o command bar do Fincept; registrar como ideia de longo prazo, não ação.
- **Navegação em dois níveis / proibição de cards genéricos / tabular-nums / RSI-MACD-Bollinger inline** — já implementados, as próprias auditorias confirmam como validação, não como gap.

---

## 3. Estado real das PRs na data da consolidação (2026-11-12)

Verificado com `gh pr list` no momento da consolidação:

| PR | Descrição | Estado |
|---|---|---|
| #290 | Fincept-A — auditoria de arquitetura | OPEN (insumo desta consolidação) |
| #289 | Fincept-B — auditoria de coletores | OPEN (insumo desta consolidação) |
| #288 | Fincept-D — auditoria de UX | OPEN (insumo desta consolidação) |
| **Fincept-C (agentes de IA/comitê)** | auditoria do framework de agentes do Fincept | **não encontrada** — nenhuma PR nem branch remota com esse padrão de nome além das 3 acima. Consolidação segue sem esse insumo; se Fincept-C ainda estiver rodando em outra sessão, seus achados devem ser mesclados manualmente nesta lista depois |
| #287 | Agente C (missão 2026-11-12) — extração de PDF/OCR + classificação de ticker + confirmação do comparador | OPEN, mergeável, toca `data/research/classificacao.py`, `data/research/resumir.py`, `requirements.txt`, testes |
| #281–#286 | Lote de 6 agentes (A–F) da missão de 2026-11-11 (coletores/gráficos/comitê/design system/home-watchlist/casas prioritárias) | **todas MERGED** — nenhuma colisão pendente desse lote |

**Conclusão de colisão:** na data desta consolidação, o único trabalho de implementação ainda aberto é a PR #287, com escopo estreito (2 arquivos de `data/research/` + testes). Isso é o que fundamenta a maioria dos itens de Prioridade 1 poderem avançar já — a superfície de colisão real hoje é pequena. Os itens de Prioridade 2 que mencionam dependência de "lote atual" referem-se às frentes de trabalho vivas (expansão de casas, redesign visual, processamento/comparador) que devem gerar novas PRs em seguida, não necessariamente à #287 especificamente — o risco ali é de frente-de-trabalho, não de arquivo literal em conflito nesta data exata.

---

## 4. O que esta missão NÃO fez

Esta é uma missão de consolidação documental. Nenhum arquivo de código (`data/*.py`, `ui/*.py`, `sql/*.sql`, `.github/workflows/*.yml`) foi criado ou alterado. A única entrega é este documento. Qualquer item da lista de Prioridade 1/2 acima que envolva schema/migration/dado real de produção deve, antes de merge, passar por uma PR dedicada com aprovação explícita do Rodrigo — itens puramente visuais/CI/documentação podem seguir o fluxo autônomo normal.
