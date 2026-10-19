# Fotos das notícias — verificação pós-deploy

Por que existe: a validação desta mudança foi feita com testes (mocks) e um
harness local com dados **sintéticos**. O ambiente de desenvolvimento não
tinha acesso aos sites de notícia nem ao Supabase, então **nenhuma imagem
real foi verificada antes do deploy**. Este roteiro faz essa verificação
depois do merge. Ele só lê dados: nenhum passo escreve no banco.

## 1. Coletor (GitHub Actions → "Coletores na nuvem")

Depois do merge, espere a próxima execução agendada (ou dispare uma
manualmente) e procure no log do passo "Executar coletores":

```
imagens de NEWS: N grupo(s), X ja' com foto, Y avaliado(s) {'confirmada': a, 'ausente': b, ...}, Z gravado(s), F falha(s)
```

- Esperado: `Y > 0` na 1ª execução, `Z == Y` e `F == 0`.
- Essa linha deve aparecer **mesmo se** a linha de resumos disser que falta
  `GROQ_API_KEY`.
- As linhas `[pregerar_imagens_news] <status> <domínio> '<título>'`
  mostram o resultado de cada matéria. Só aparecem domínio e status, nunca
  a URL da imagem.
- Se `Z < Y`: falha de gravação no Supabase. Procure `salvar_registro_imagem(...) falhou`.
- O passo "Executar coletores" já terminava com `failure` em todas as
  execuções desde 15/10, antes desta mudança. Compare a duração: antes
  ~4,5 min; com a etapa de imagens, o esperado é até ~8 min (limite do job: 20).

## 2. Banco (Supabase → SQL Editor, só SELECT)

```sql
-- quantos registros de imagem e com qual resultado
select resultado->>'imagem_status' as status, count(*)
from resumos_ia_cache where origem = 'news_imagem'
group by 1 order by 2 desc;

-- amostra pra conferência visual (abrir cada imagem e cada matéria)
select link_principal, resultado->>'imagem' as imagem, resultado->>'imagem_fonte' as fonte,
       resultado->>'imagem_status' as status, resultado->>'imagem_tentativas' as tentativas,
       atualizado_em
from resumos_ia_cache where origem = 'news_imagem'
order by atualizado_em desc limit 15;

-- a mesma foto em vários grupos (deveria virar generica_repetida na leitura)
select resultado->>'imagem' as imagem, count(*)
from resumos_ia_cache
where origem in ('news', 'news_imagem') and resultado->>'imagem' is not null
group by 1 having count(*) > 1 order by 2 desc limit 10;
```

Os registros de resumo (`origem = 'news'`) não são alterados por esta
mudança. Os de imagem usam chave própria (`news_imagem:` + chave do resumo).

## 3a. Amostra real reprodutível (qualquer máquina com internet; não precisa de credenciais)

```
python docs/evidencias/imagens-news-20261019/validar_amostra_real.py --n 10 --saida /tmp/amostra-fotos
```

- Roda o MESMO extrator e a MESMA validação do coletor contra matérias
  reais do TOP MERCADO, pegando 1 matéria por veículo antes de repetir.
- **Somente leitura, garantido no próprio script**: o cliente Supabase fica
  desligado (a coleta do TOP MERCADO gravaria em `coletores_status`), o
  registro de status vira no-op e qualquer chamada de IA levanta erro.
  Nenhum e-mail é enviado.
- Gera `amostra.csv` e `amostra.html` (foto ao lado do título, com link
  para a matéria original).
- Classificação inicial automática, **nunca "correto"**:

  | Status | Classificação inicial |
  |---|---|
  | foto validada por rede | `pendente_inspecao_visual` |
  | 401/403/429/5xx/timeout da imagem, ou página inacessível | `bloqueado` |
  | página sem foto, foto inválida (404, não imagem) ou repetida | `sem_imagem` |

- Abra o HTML e, para cada `pendente_inspecao_visual`, compare com a
  matéria original. Troque a classificação no CSV por `correto`,
  `incorreto` ou `inconclusivo` (e por `bloqueado` se a foto não carregar
  no navegador). Use a coluna `observacao` para o motivo.
- Apure:

  ```
  python docs/evidencias/imagens-news-20261019/validar_amostra_real.py --apurar /tmp/amostra-fotos/amostra.csv
  ```

  A taxa de correspondência é `correto / (correto + incorreto)`. Bloqueados,
  sem imagem e inconclusivos ficam fora do denominador. Se sobrar alguma
  linha sem classificação final, o script sai com código 3.
- Código de saída 2 na coleta = nenhuma notícia coletada (sem acesso às
  fontes). Nada foi validado.

## 3. Conferência visual (https://pregao.streamlit.app)

Escolha de 8 a 12 matérias de fontes diferentes (InfoMoney, Valor, g1,
Estadão, UOL, Reuters/Bloomberg Línea, Exame...), em TOP MERCADO (BRASIL e
INTERNACIONAL), no feed NOTÍCIAS e no modal. Para cada uma, abra a matéria
original e preencha:

| # | Título | Fonte | URL da matéria | URL da imagem | Status (banco) | Foto é da matéria? | Carregou no app? |
|---|--------|-------|----------------|---------------|----------------|--------------------|------------------|
| 1 |        |       |                |               |                |                    |                  |

Critério: "Foto é da matéria?" = **sim** só se for a mesma foto que a
matéria original exibe no topo. HTTP 200 não basta.

Também conferir:
- [ ] Nenhuma foto trocada entre matérias. Duas matérias de assuntos diferentes com a mesma foto contam como falha.
- [ ] Matéria sem foto mostra o quadrado ou capa neutros (sigla ou nome do veículo), nunca o ícone de imagem quebrada.
- [ ] Hotlink: no DevTools → Network, filtre por `Img` e procure respostas 403. Toda imagem com 403 tem que estar trocada pelo fallback no card.
- [ ] Celular (ou DevTools com 390px de largura): feed com miniatura ao lado do título; modal com capa de ~100px de altura (não uma faixa de 64px); sem rolagem horizontal; TOP MERCADO sem miniatura (oculta de propósito no celular).
- [ ] Modal de uma matéria sem resumo, mas com foto no banco: a capa mostra a foto.

## 4. Se algo der errado

- Foto errada: anote o `link_principal`, o domínio e a URL da imagem e
  abra uma tarefa. Não corrija direto no banco sem autorização.
- Muitos `erro_temporario`: provavelmente um bloqueio do site ao download
  da página. Esses itens são reavaliados sozinhos em 2h, até 4 tentativas.
- Para desativar só a etapa de imagens sem reverter o resto: remova a
  chamada `pregerar_imagens_news(...)` em `coletor_local.py`. O feed
  continua funcionando com as fotos que já vêm dos resumos.
