# Morning Call via Google Workspace SMTP

O job automático do Morning Call usa SMTP do Gmail/Google Workspace por padrão
(`jobs/email_utils.py:enviar_email`, `EMAIL_PROVIDER=smtp` - ver
`.github/workflows/radar-morning-call.yml`). O job do Radar de quedas
compartilha o mesmo código, mesmo default.

## GitHub Actions secrets

Em **Settings → Secrets and variables → Actions**, configure:

- `SMTP_USER`: endereço completo da conta Google Workspace que enviará os e-mails.
- `SMTP_PASSWORD`: senha de app dessa conta, quando exigida pelo Google. Nunca use nem compartilhe a senha normal da conta.
- `EMAIL_FROM` (opcional): remetente; se omitido, o código usa `SMTP_USER`.
- `SMTP_HOST` (opcional): padrão `smtp.gmail.com`.
- `SMTP_PORT` (opcional): padrão `587`.

Não é necessário configurar `EMAIL_PROVIDER`, `RESEND_API_KEY` ou
`BREVO_API_KEY` para usar SMTP - o código já cai em `smtp` quando
`EMAIL_PROVIDER` não está definido.

## Antes do primeiro envio

1. Confirme com o administrador do Google Workspace que SMTP autenticado está permitido para a conta.
2. Habilite a verificação em duas etapas e crie uma senha de app, se a política da organização permitir. Algumas organizações desativam senhas de app; nesse caso, o administrador deve aprovar um método de autenticação compatível antes de ativar o envio.
3. Adicione os secrets acima no GitHub. Não os coloque no código, em arquivos versionados, logs ou mensagens.
4. Execute o workflow manualmente com um destinatário de teste explícito (`workflow_dispatch`, campo `teste_destinatario`). Esse campo envia apenas para o endereço informado e não substitui a lista de assinantes opt-in.
5. Confirme a entrega na caixa de entrada e nos logs do job antes de considerar o envio operacional.

O CI usa mocks e nunca faz login real nem envia e-mails. A entrega real só
pode ser confirmada depois que o proprietário executar o teste manual acima -
nenhuma sessão automatizada deve disparar um envio real sem essa autorização
explícita.
