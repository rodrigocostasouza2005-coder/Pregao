# SAÚDE DOS DADOS — resumo compacto no topo (2026-10-19)

Missão de redesign + performance, seção 3.6 ("resumo compacto com métricas
reais disponíveis"). A tela já ia direto pras tabelas por categoria, sem
nenhum "estado geral" visível sem rolar/ler tudo.

`depois_desktop.png` / `depois_mobile.png` — captura real via Playwright
(harness local, dados sintéticos — sem Supabase neste ambiente de
desenvolvimento, estado real da produção não verificado aqui). Linha
compacta logo abaixo do botão ATUALIZAR: contagem por estado (SAUDÁVEL/
EM ATENÇÃO/EM FALHA/NÃO COMPROVADO) + total de coletores monitorados,
usando a MESMA classificação `_COR_POR_ESTADO` já aplicada por linha nas
tabelas abaixo — nenhuma métrica nova/paralela, só agregação do que já
existe.

Bug real encontrado e corrigido durante a própria escrita do teste
(`tests/test_saude_dados_tab.py`): a pluralização de "SAUDÁVEL" concatenava
o sufixo "EIS" direto no fim da palavra singular, produzindo "SAUDÁVELEIS"
em vez de "SAUDÁVEIS" com 2+ coletores saudáveis — pego pelo teste antes de
qualquer captura visual.

**Achado não corrigido nesta sessão** (pré-existente, não é regressão desta
mudança): nas tabelas por categoria, em telas estreitas (mobile) as colunas
ÚLTIMO SUCESSO/REGISTROS NOVOS ficam fora da área visível no screenshot
`full_page` — o container tem `overflow-x:auto` (scroll horizontal real
funciona no dispositivo), mas não há nenhuma affordance visual indicando
que dá pra arrastar lateralmente. Registrado como pendência pra uma próxima
sessão (candidato: layout em cards empilhados abaixo de um breakpoint, ou
indicador de scroll), não implementado agora por já envolver uma decisão de
layout maior que o escopo deste ciclo (resumo compacto).
