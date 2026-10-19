# PREGÃO 2.0 — validação visual da navegação (2026-10-19)

Capturas de um harness local (Streamlit + Playwright/Chromium) rodando o
`app.py` **real** desta branch, com login simulado e preferências em memória
(sem Supabase, sem secrets, sem e-mail). O sandbox não tem acesso de rede às
fontes externas (Yahoo, Google News, BCB recusados pelo proxy), então todas as
telas mostram os **estados de indisponibilidade** — nenhum dado de exemplo foi
injetado. A validação com dados reais depende do deploy.

Percurso automatizado das 32 rotas (`?aba=…&sub=…`) em 1366px e em 390px
(mobile): 64/64 sem exceção do Streamlit e sem rolagem horizontal da página;
área e subaba ativas conferidas em cada rota. Usuário comum abrindo
`?aba=mais&sub=sistema` cai em MAIS › Watchlist; admin vê Sistema/Saúde.

Interações conferidas no navegador: clique em área e subaba (URL atualizada),
vínculo SETORES › Visão por Setor → ITUB4 em ANÁLISES › Empresas, voltar e
avançar do navegador, recarregar mantendo a rota, Enter via teclado com foco
visível.

| Arquivo | Tela |
|---|---|
| `desktop_mercado_visao_geral.png` | MERCADO › Visão Geral (workspace preservado) |
| `desktop_radar_alertas_foco_teclado.png` | RADAR › Alertas, foco de teclado na área |
| `desktop_analises_empresas.png` | ANÁLISES › Empresas com barra de vínculos |
| `desktop_setores_visao_por_setor.png` | SETORES › Visão por Setor |
| `desktop_morning_call_edicao.png` | MORNING CALL › Edição Atual (banco indisponível) |
| `desktop_admin_mais_sistema.png` | MAIS › Sistema (admin) |
| `mobile_analises_empresas.png` | Empresas a 390px (vínculos em grade 2×2) |
| `mobile_macro_calendario.png` | MACRO › Calendário Econômico a 390px |
| `mobile_noticias_empresas.png` | NOTÍCIAS › Empresas a 390px (carregando) |
