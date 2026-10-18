# Auditoria do Morning Call: edição real de 18/10/2026

Os arquivos foram gerados pelo diagnóstico temporário (workflow `_diag-morning-call.yml`
na branch `diag/morning-call-dados-20261018`, run 39142739443). O diagnóstico roda sem
secrets, então não lê nem escreve no Supabase, não envia e-mail e não chama o Groq.
A edição foi montada com o código desta branch, sobre dados reais coletados no domingo,
18/10/2026, às 12h57 (Brasília).

- `morning_call_real.pdf` e `pagina-*.png`: a edição gerada.
- `relatorio.txt`: indicadores e notícias da edição, com o resultado do filtro de cada
  notícia (`OK`/`FORA`).

Diferenças em relação a uma edição de produção:

- Sem Supabase não há resumo cacheado, então todas as matérias saem só com manchete
  (`corpo=0`).
- A agenda foi recalculada ao vivo.
- Esta saída é anterior a dois ajustes feitos depois da inspeção visual (commit 1199a42):
  1. "indisponível" quebrava em duas linhas na tabela de juros.
  2. Um anúncio de passagem aérea aparecia na editoria Brasil.
