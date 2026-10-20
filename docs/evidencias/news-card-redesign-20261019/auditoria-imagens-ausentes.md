# Auditoria: por que ainda há notícias sem imagem (2026-10-19)

## Método

Rodei `data.news.avaliar_imagem_grupo` (a função real de produção, sem
mock nenhum) contra 8 matérias reais de hoje, com acesso de rede real
(ambiente desta sessão tem internet; `genial`/`cnbc`/`yahoo finance`
ficam bloqueados mesmo assim, `uol`/`infomoney`/sites BR em geral
respondem normal).

## Resultado

| Matéria | Status real |
|---|---|
| UBS eleições EUA (InfoMoney) | `confirmada` |
| IGP-10 FGV (Valor/Globo) | `confirmada` |
| Ouro Treasuries (MoneyTimes) | `confirmada` |
| MOVI3 preço-alvo (Acionista) | `confirmada` |
| Fed chip stocks (Reuters) | `erro_temporario` (HTTPError real ao baixar a página) |
| OpenAI Saudi (Financial Times) | `erro_temporario` (HTTPError real ao baixar a página) |
| Dow/Nasdaq (MarketWatch) | `confirmada` |
| Flávio Bolsonaro (Folha/UOL) | `confirmada` |

**6/8 confirmadas, 2/8 bloqueadas na origem (HTTP, não é bug nosso).**
Nenhuma rejeitada por validação/associação incorreta nesta amostra.

## Causa real identificada e corrigida

`_MAX_FONTES_IMAGEM` estava em **2**: `avaliar_imagem_grupo` só tentava
as 2 fontes mais prioritárias do grupo (`_fontes_para_imagem`) antes de
desistir. Um grupo cujas 2 fontes mais bem rankeadas calharem de ser
sempre as mesmas bloqueadas (Reuters/FT, confirmado real acima) nunca
chegava a tentar uma 3ª fonte do MESMO fato — mesmo que ela tivesse
imagem perfeitamente acessível. Subi pra **3**, com teste novo
confirmando que a 3ª fonte é tentada e um teto (ainda existe, não virou
"tenta todas") confirmando que a 4ª não é — ver
`tests/test_news_imagens_pipeline.py::test_08c2_*`/`test_08c3_*`.

## Causas que NÃO são bug (não corrigidas, por design)

- **Bloqueio HTTP real na origem** (Reuters/FT confirmados acima) - a
  tarefa veda explicitamente usar proxy/evasão de bloqueio. A política
  de reavaliação já existente (`_TTL_REAVALIAR_IMAGEM`) tenta de novo
  em 2h pra esse caso.
- **Atraso de backfill**: o registro de imagem independente do resumo
  (`pregerar_imagens_news`) só existe desde hoje (PR #89, mergeada
  21:05). Roda em lotes de até 30 grupos por execução do coletor
  periódico - cache antigo (de antes da correção) só ganha imagem
  depois de passar pelo coletor de novo. Não consegui medir o atraso
  real de produção (sem acesso ao Supabase de produção nesta sessão).

## Limitação desta auditoria

Sem credenciais de Supabase, não consegui consultar o estado REAL do
cache de produção (quantas notícias aparecem sem imagem agora, nem
quantas melhoraram desde o merge de hoje). A amostra acima é real
(rede real, função real de produção), mas pequena (8 matérias) e não
é uma contagem da produção.
