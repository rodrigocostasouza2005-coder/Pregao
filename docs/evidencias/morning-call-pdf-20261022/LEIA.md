# Morning Call — PDF gerado com dados reais (22/10/2026, 16:31 BRT)

Gerado no runner do GitHub Actions (o sandbox não tem rede) por um workflow temporário, **sem secrets**: cotações
(Yahoo Finance), BCB/Focus, CVM e Google News reais; **sem** resumos de IA (`GROQ_API_KEY` ausente) e **sem** as
fotos/resumos do cache do Supabase. Nada foi enviado nem gravado.

- `previa-dados-reais-20261022-1631.pdf` — o arquivo gerado (4 páginas).
- `pagina-1.png` … `pagina-4.png` — renderização (pdftoppm, 70 dpi) usada na inspeção.

Inspeção página a página: sem sobreposição, sem caracteres quebrados, sem página vazia, tabelas inteiras, links
clicáveis. Capa e editorias só com veículos confiáveis (Money Times, Valor, InfoMoney, Reuters, CNBC, MarketWatch,
Bloomberg); Mundo com aviso de manchetes no idioma original; masthead marca "fora do horário previsto" (gerado às
16:31). Limitações desta prévia: matérias só com manchete (sem IA), sem fotos (sem acesso ao cache), agenda dos
próximos dias vazia (o calendário persistido fica no Supabase).
