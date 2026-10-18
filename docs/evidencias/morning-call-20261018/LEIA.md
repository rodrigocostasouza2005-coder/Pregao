# Morning Call em PDF — redesenho editorial (2026-10-18)

Gerado pelo renderer final (`jobs/morning_call_pdf.py`) com as edições de
amostra de `tests/morning_call_amostras.py` — manchetes reais de 17/10/2026
(log de produção), resumos/cotações/agenda de EXEMPLO (o ambiente onde isto
foi feito não alcança Yahoo, BCB nem Google News). Páginas rasterizadas com
`pdftoppm` a 110 dpi e inspecionadas.

- `comparativo_capa.png`, `comparativo_interna.png` — antes (renderer do
  `main` em 9fb2867) x depois, com o MESMO conteúdo.
- `tipica-todas.png` — edição típica (3 páginas).
- `cheia-todas.png` — volume máximo (6 páginas), testa quebra de coluna/página.
- `vazia-todas.png` — coleta falhou (2 páginas), sem inventar conteúdo.
- `edicao_amostra.pdf` — o PDF da edição típica.

Pra gerar com dados reais (na máquina com rede): `python -m jobs.morning_call_pdf saida.pdf`
(não envia e-mail).
