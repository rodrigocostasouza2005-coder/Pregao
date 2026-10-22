# Sprint 22/10/2026 — evidências visuais

Harness local (Streamlit + Playwright/Chromium) rodando o `app.py` real com login
simulado e preferências em memória. O sandbox não alcança Yahoo/Google News/BCB nem o
Supabase; a aba Morning Call recebeu **uma edição de exemplo** (marcada
`[EXEMPLO DE LAYOUT]` no próprio texto) só para avaliar o layout. Nada disso existe
em produção.

As capturas "antes" foram tiradas depois do aviso de horário (mesma sprint), mas antes das
mudanças de cabeçalho e de posição do banner — o que elas comparam é o layout do menu.

| Arquivo | O que mostra |
|---|---|
| `antes_mobile_morning_call.png` | 390 px antes: banner de inscrição acima do logo e cabeçalho com "CTRL K" + 3 botões em largura total ocupando a tela inteira |
| `depois_mobile_morning_call.png` | 390 px depois: ações numa linha, sem "CTRL K"; menu e subabas na primeira tela; banner depois do menu |
| `antes_desktop_morning_call.png` | 1366 px antes: banner entre a navegação principal e as subabas |
| `depois_desktop_morning_call.png` | 1366 px depois: menu contínuo; edição gerada às 12:58 marcada "fora do horário previsto (08h)" |
