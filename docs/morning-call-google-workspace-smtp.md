# Morning Call via Google Workspace SMTP

O job automático do Morning Call usa exclusivamente SMTP do Gmail/Google Workspace. O job do Radar de quedas mantém sua configuração de provedor independente.

## GitHub Actions secrets

Em **Settings → Secrets and variables → Actions**, configure:

- `SMTP_USER`: endereço completo da conta Google Workspace que enviará os e-mails.
- `SMTP_PASSWORD`: senha de app dessa conta, quando exigida pelo Google. Nunca use nem compartilhe a senha normal da conta.
- `EMAIL_FROM` (opcional): remetente; se omitido, o código usa `SMTP_USER`. Recomenda-se usar o mesmo endereço da conta autenticada.
- `SMTP_HOST` (opcional): padrão `smtp.gmail.com`.
- `SMTP_PORT` (opcional): padrão `587`.

O workflow define `EMAIL_PROVIDER=smtp` apenas no job `morning-call` e usa os padrões de host/porta acima. Não é necessário configurar `EMAIL_PROVIDER`, `RESEND_API_KEY` ou `BREVO_API_KEY` para o Morning Call.

## Antes do primeiro envio

1. Confirme com o administrador do Google Workspace que SMTP autenticado está permitido para a conta.
2. Habilite a verificação em duas etapas e crie uma senha de app, se a política da organização permitir. Algumas organizações desativam senhas de app; nesse caso, o administrador deve aprovar um método de autenticação compatível antes de ativar o envio.
3. Adicione os secrets acima no GitHub. Não os coloque no código, em arquivos versionados, logs ou mensagens.
4. Execute o workflow manualmente com um destinatário de teste explícito. O campo `teste_destinatario` envia apenas para o endereço informado e não substitui a lista de assinantes opt-in.
5. Confirme a entrega na caixa de entrada e nos logs do job antes de considerar o envio operacional.

O CI usa mocks e nunca faz login real nem envia e-mails. A entrega real só pode ser confirmada depois que o proprietário configurar os secrets e executar o teste manual.
