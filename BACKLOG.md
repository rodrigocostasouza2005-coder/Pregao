# BACKLOG — PREGÃO

Pendências conhecidas, para resolver depois (ajustes visuais adiados
enquanto avançamos nas próximas fases).

## Visual / layout
- E-mail do usuário sumiu do header (só aparece o botão SAIR). Causa
  provável identificada e corrigida uma vez (`.block-container{overflow-x:hidden}`
  cortando a coluna), mas o problema voltou — investigar de novo com
  mais cuidado, idealmente com print/inspeção real da página.
- Cabeçalho da tabela PREÇOS (linha com o nome da empresa) aparece
  cortado ao meio, e sobra um espaço vazio logo abaixo da tabela.
  Ajustes já tentados (wrapper com `overflow-x:auto`, reset no
  `st.fragment`) não resolveram por completo — investigar a causa real,
  de preferência com inspeção visual. Mesmo sintoma confirmado também no
  cabeçalho da tabela do painel RESUMO (aba MACRO) — provavelmente a
  mesma causa raiz, ainda não identificada; corrigir os dois juntos.
- Título "INDICADORES" sumiu do painel (o painel em si continua
  aparecendo, só o cabeçalho com o nome não).
- Painel INDICADORES ficou com barra de rolagem interna (altura fixa)
  em vez de crescer conforme o conteúdo.
- Limpeza de nome de empresa parece remover acentos em produção (ex:
  "Ginástica e Dança" → "Ginástica e Danca"). Testado localmente
  (`obter_nome_yf('SMFT3')`) e o resultado veio com acento correto —
  `longName` do yfinance e a função de limpeza não mexem em
  maiúscula/minúscula nem em encoding, só cortam o sufixo jurídico do
  final. Suspeita: diferença de locale/encoding entre o ambiente local e
  o container do Streamlit Cloud, não bug na lógica em si — investigar
  direto em produção (não reproduz local).

## Gráfico
- Modo LINHA: a linha de preço e a MM20 saem na mesma cor (ambas usam
  `tema["destaque"]`), ficam indistinguíveis. Trocar a cor de uma das
  duas.
- Confirmar se o modo CANDLE (padrão) está com as cores corretas de
  alta/baixa e sem o mesmo problema de sobreposição de cor.

## Indicadores
- Beta: hoje vem direto do campo `beta` do yfinance, que para ações da
  B3 costuma estar mal calculado (referência de mercado errada, período
  curto etc.). Recalcular localmente: retornos semanais de 2 anos do
  ticker vs. `^BVSP` (Ibovespa), beta = cov(ret_ticker, ret_ibov) /
  var(ret_ibov). Até lá, a coluna BETA fica escondida no painel
  INDICADORES (não mostrar número que pode estar errado).
- Dividend yield: conferir se o histórico de dividendos do yfinance
  (`Ticker.dividends`) não duplica pagamentos de JCP (juros sobre
  capital próprio) com o dividendo declarado — se duplicar, o DY
  calculado (soma 12m / preço atual) fica inflado.

## Macro
- Curva pré (ETTJ ANBIMA): a fonte só guarda ~5-6 pregões de histórico
  rolante — comparação de "1 mês atrás" não funciona (testado, confirma
  o limite). Para viabilizar essa comparação, salvar um snapshot diário
  da curva no Supabase via GitHub Actions (Fase 7 do roadmap original,
  coleta automática).
- Curva pré: legenda (Hoje / 1 semana atrás / 1 mês atrás) aparece
  sobreposta/cortada no gráfico.
- Barra de ferramentas do Plotly não está escondida nos gráficos da aba
  MACRO (`displayModeBar: False` já existe em app.py, faltou aplicar em
  `ui/macro_tab.py`).
- IPCA: eixo X do gráfico 12 meses deveria mostrar mês/ano (ex:
  "ago/2026") em vez do formato padrão do Plotly.
- Conferir se os avisos (fonte indisponível etc.) na aba MACRO estão
  usando o mesmo estilo fino/compacto do resto do app.

## Research
- BTG Research: API pública em
  `https://content.btgpactual.com/api/research/public-router/<servico>/api/<servico>/public/v1/...`
  (ex. que funciona: `.../media-research/.../medias/lives?status=LIVE&pageNumber=1&pageSize=8`).
  A lista de relatórios (requisição "ALL?pageNumber=1&pageSize=9&channel=...")
  deu 404 na home e não apareceu em /acoes/ultimos-relatorios; pode ser
  restrita a clientes. Próximo passo: procurar "public-router" nos bundles
  JS para mapear as rotas, ou testar a área aberta content.btgpactual.us.

## Fases futuras
- Morning Call da Genial: transcrição + resumo automático. Fase futura,
  ainda não desenhada (fonte, formato do resumo, frequência de
  atualização etc. — definir quando chegar a vez).
