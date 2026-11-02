# Fluxo de execução, revisão e merge — PREGÃO

Regras operacionais para qualquer trabalho de implementação (humano ou agente) neste repositório. Objetivo: evitar ambiguidade sobre autorização de merge, isolar trabalho em andamento e manter revisão consistente sem gastar tokens em auditorias repetidas.

## Regras

1. **Escopo por missão.** Cada missão/tarefa tem seu próprio escopo. Autorização de merge concedida numa missão **não** se estende a outra, mesmo que sejam relacionadas ou sequenciais.
2. **Merge só com autorização explícita.** Nunca mesclar uma PR sem autorização explícita do dono do projeto *para aquela PR específica*. Abrir a PR e parar é o padrão; merge é exceção que precisa ser concedida, não assumida.
3. **Implementação isolada.** Todo trabalho de código ocorre em branch/worktree isolado, criado a partir da `main` atualizada (`git fetch origin` antes de criar o worktree). Nunca editar o checkout principal ou worktrees de outras sessões em andamento.
4. **Revisão independente para mudanças relevantes.** Mudanças não triviais (nova lógica, nova integração, novo painel/dado exposto ao usuário) devem ser revisadas por um segundo agente/sessão, separado de quem implementou — ele revisa o diff e os testes de forma independente antes da decisão de merge.
5. **Corrigir e re-testar antes de apresentar.** Problema real encontrado na revisão é corrigido na própria branch da PR, com teste de regressão, e a suíte pertinente roda de novo antes de reapresentar a PR.
6. **Transparência sobre validação.** Toda entrega informa o que foi testado (comando + resultado) e o que **não pôde** ser validado em produção (ex.: chamadas reais a Groq, Supabase, Streamlit Cloud) — nunca alegar validação de produção sem acesso real a ela.
7. **Sem auditoria repetida.** Não refazer auditorias completas já concluídas em sessão anterior; reaproveitar o que já foi validado e focar apenas no que mudou.
8. **Saúde dos Dados é frente separada.** A aba Saúde dos Dados, seus coletores e sua lógica não devem ser alterados junto de mudanças em outras abas/funcionalidades — correções nela são sempre uma frente isolada, com sua própria PR.

## Checklist de prontidão para merge

- [ ] CI verde na PR.
- [ ] Suíte de testes pertinente roda sem regressão (não só os testes novos).
- [ ] Diff restrito ao escopo da missão — nada fora do que foi pedido.
- [ ] Nenhuma dependência externa nova (API paga, conector comercial, secret novo) foi introduzida sem autorização explícita.
- [ ] Validação em produção (Groq/Supabase/Streamlit Cloud) feita, ou a limitação de não ter sido feita está declarada claramente.
