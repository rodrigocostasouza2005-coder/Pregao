# -*- coding: utf-8 -*-
"""Cobertura do caminho SMTP de jobs/email_utils.py - provedor padrão
(EMAIL_PROVIDER ausente/"smtp") sem nenhum teste dedicado até aqui.
Mocka smtplib.SMTP inteiro (nunca abre conexão real).

`destinatario` é sempre passado explicitamente nas chamadas de
enviar_email() (nunca via env EMAIL_TO - fallback removido em
2026-10-26, auditoria "Radar/Morning Call: consentimento") - mesma
convenção real de jobs/morning_call.py e jobs/radar_quedas.py."""
import socket
import ssl
from unittest.mock import MagicMock

from jobs import email_utils

_DESTINATARIO = "destino@example.com"


def _smtp_mock(monkeypatch):
    smtp_instancia = MagicMock()
    smtp_instancia.__enter__.return_value = smtp_instancia
    smtp_cls = MagicMock(return_value=smtp_instancia)
    monkeypatch.setattr(email_utils.smtplib, "SMTP", smtp_cls)
    return smtp_instancia


def test_smtp_envia_anexo_com_tipo_mime_correto(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "segredo")
    smtp_instancia = _smtp_mock(monkeypatch)

    resultado = email_utils.enviar_email(
        "Assunto", "Texto", "<p>HTML</p>", destinatario=_DESTINATARIO,
        anexos=[{"nome": "mc.pdf", "conteudo": b"%PDF-conteudo", "tipo_mime": "application/pdf"}],
    )

    assert resultado == {"ok": True, "erro": None}
    msg_enviada = smtp_instancia.send_message.call_args[0][0]
    anexos = [p for p in msg_enviada.iter_attachments()]
    assert len(anexos) == 1
    assert anexos[0].get_filename() == "mc.pdf"
    assert anexos[0].get_content_type() == "application/pdf"
    assert anexos[0].get_content() == b"%PDF-conteudo"


def test_smtp_sem_anexos_nao_adiciona_parte_extra(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "segredo")
    smtp_instancia = _smtp_mock(monkeypatch)

    email_utils.enviar_email("Assunto", "Texto", "<p>HTML</p>", destinatario=_DESTINATARIO)

    msg_enviada = smtp_instancia.send_message.call_args[0][0]
    assert list(msg_enviada.iter_attachments()) == []


def test_smtp_anexo_vazio_e_ignorado_sem_quebrar_envio(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "segredo")
    smtp_instancia = _smtp_mock(monkeypatch)

    resultado = email_utils.enviar_email(
        "Assunto", "Texto", destinatario=_DESTINATARIO, anexos=[{"nome": "vazio.pdf", "conteudo": b""}],
    )

    assert resultado == {"ok": True, "erro": None}
    msg_enviada = smtp_instancia.send_message.call_args[0][0]
    assert list(msg_enviada.iter_attachments()) == []


def _env_smtp(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "segredo")


def test_smtp_falha_informa_a_etapa_e_nao_reenvia(monkeypatch):
    """Regressao do envio real de 21/10/2026: o erro so' dizia 'read
    operation timed out', sem dizer se foi login ou envio do anexo."""
    import smtplib

    _env_smtp(monkeypatch)
    smtp_instancia = _smtp_mock(monkeypatch)
    smtp_instancia.send_message.side_effect = smtplib.SMTPServerDisconnected(
        "Connection unexpectedly closed: The read operation timed out")

    resultado = email_utils.enviar_email("Assunto", "Texto", destinatario=_DESTINATARIO)

    assert resultado["ok"] is False
    assert "etapa SMTP: envio da mensagem" in resultado["erro"]
    assert smtp_instancia.send_message.call_count == 1  # nunca reenvia sozinho


def test_smtp_falha_no_login_e_identificada(monkeypatch):
    import smtplib

    _env_smtp(monkeypatch)
    smtp_instancia = _smtp_mock(monkeypatch)
    smtp_instancia.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")

    resultado = email_utils.enviar_email("Assunto", "Texto", destinatario=_DESTINATARIO)

    assert "etapa SMTP: login" in resultado["erro"]
    assert not smtp_instancia.send_message.called


def test_smtp_usa_timeout_de_60s(monkeypatch):
    _env_smtp(monkeypatch)
    smtp_instancia = MagicMock()
    smtp_instancia.__enter__.return_value = smtp_instancia
    smtp_cls = MagicMock(return_value=smtp_instancia)
    monkeypatch.setattr(email_utils.smtplib, "SMTP", smtp_cls)

    email_utils.enviar_email("Assunto", "Texto", destinatario=_DESTINATARIO)

    assert smtp_cls.call_args.kwargs["timeout"] == 60


def test_smtp_starttls_valida_certificado_do_servidor(monkeypatch):
    """Google Workspace exige TLS explícito COM validação de certificado
    (requisito da auditoria SMTP) - smtp.starttls() sem `context` usa
    ssl._create_stdlib_context() (CERT_NONE, sem checar hostname), então
    o código precisa passar um ssl.SSLContext que valide a cadeia."""
    _env_smtp(monkeypatch)
    smtp_instancia = _smtp_mock(monkeypatch)

    email_utils.enviar_email("Assunto", "Texto", destinatario=_DESTINATARIO)

    assert smtp_instancia.starttls.call_count == 1
    contexto_usado = smtp_instancia.starttls.call_args.kwargs.get("context")
    assert isinstance(contexto_usado, ssl.SSLContext)
    assert contexto_usado.verify_mode == ssl.CERT_REQUIRED
    assert contexto_usado.check_hostname is True


def test_smtp_sem_host_retorna_erro_sem_tentar_conexao(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "segredo")
    smtp_cls = MagicMock()
    monkeypatch.setattr(email_utils.smtplib, "SMTP", smtp_cls)

    resultado = email_utils.enviar_email("Assunto", "Texto", destinatario=_DESTINATARIO)

    assert resultado["ok"] is False
    assert "SMTP_HOST, SMTP_USER e SMTP_PASSWORD" in resultado["erro"]
    assert not smtp_cls.called


def test_smtp_sem_senha_retorna_erro_sem_tentar_conexao(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    smtp_cls = MagicMock()
    monkeypatch.setattr(email_utils.smtplib, "SMTP", smtp_cls)

    resultado = email_utils.enviar_email("Assunto", "Texto", destinatario=_DESTINATARIO)

    assert resultado["ok"] is False
    assert "SMTP_HOST, SMTP_USER e SMTP_PASSWORD" in resultado["erro"]
    assert not smtp_cls.called


def test_smtp_porta_invalida_retorna_erro_sem_tentar_conexao(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "segredo")
    monkeypatch.setenv("SMTP_PORT", "nao-e-numero")
    smtp_cls = MagicMock()
    monkeypatch.setattr(email_utils.smtplib, "SMTP", smtp_cls)

    resultado = email_utils.enviar_email("Assunto", "Texto", destinatario=_DESTINATARIO)

    assert resultado["ok"] is False
    assert "SMTP_PORT deve ser uma porta numérica" in resultado["erro"]
    assert not smtp_cls.called


def test_smtp_falha_de_conexao_e_identificada_na_etapa_conexao(monkeypatch):
    """Timeout/recusa de conexão (host/porta errados, firewall) acontece
    ANTES do STARTTLS - etapa deve continuar "conexão", nunca mascarada
    como sucesso."""
    _env_smtp(monkeypatch)
    smtp_cls = MagicMock(side_effect=socket.timeout("timed out"))
    monkeypatch.setattr(email_utils.smtplib, "SMTP", smtp_cls)

    resultado = email_utils.enviar_email("Assunto", "Texto", destinatario=_DESTINATARIO)

    assert resultado["ok"] is False
    assert "etapa SMTP: conexão" in resultado["erro"]


def test_smtp_corpo_com_caracteres_em_portugues_e_preservado(monkeypatch):
    _env_smtp(monkeypatch)
    smtp_instancia = _smtp_mock(monkeypatch)
    texto = "Resumo do pregão: ação cai após balanço; inflação em alta."
    html = "<p>Resumo do pregão: ação cai após balanço; inflação em alta.</p>"

    resultado = email_utils.enviar_email("Édição de hoje", texto, html=html, destinatario=_DESTINATARIO)

    assert resultado == {"ok": True, "erro": None}
    msg_enviada = smtp_instancia.send_message.call_args[0][0]
    assert msg_enviada.get_body(preferencelist=("plain",)).get_content().strip() == texto
    corpo_html = msg_enviada.get_body(preferencelist=("html",)).get_content()
    assert texto.split(":")[0] in corpo_html


def test_gmail_workspace_smtp_usa_starttls_login_e_remetente_da_conta(monkeypatch):
    """Configuração Google Workspace: SMTP Gmail, STARTTLS, login e From coerente."""
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "pregao@example-workspace.com")
    monkeypatch.setenv("SMTP_PASSWORD", "senha-de-app-ficticia")
    monkeypatch.delenv("EMAIL_FROM", raising=False)
    smtp_instancia = _smtp_mock(monkeypatch)

    resultado = email_utils.enviar_email("Morning Call", "Resumo do pregão", destinatario="assinante@example.com")

    assert resultado == {"ok": True, "erro": None}
    smtp_cls = email_utils.smtplib.SMTP
    assert smtp_cls.call_args.args == ("smtp.gmail.com", 587)
    assert smtp_instancia.starttls.call_count == 1
    smtp_instancia.login.assert_called_once_with(
        "pregao@example-workspace.com", "senha-de-app-ficticia"
    )
    msg_enviada = smtp_instancia.send_message.call_args.args[0]
    assert msg_enviada["From"] == "pregao@example-workspace.com"
    assert msg_enviada["To"] == "assinante@example.com"


def test_sem_destinatario_e_sem_env_to_retorna_erro_sem_tentar_conexao(monkeypatch):
    """EMAIL_TO deixou de ser fallback (2026-10-26, auditoria
    "Radar/Morning Call: consentimento") - sem `destinatario` explícito,
    o envio falha mesmo que EMAIL_TO esteja definido no ambiente."""
    _env_smtp(monkeypatch)
    monkeypatch.setenv("EMAIL_TO", "nao-deveria-ser-usado@example.com")
    smtp_cls = MagicMock()
    monkeypatch.setattr(email_utils.smtplib, "SMTP", smtp_cls)

    resultado = email_utils.enviar_email("Assunto", "Texto")

    assert resultado["ok"] is False
    assert "precisam estar configurados" in resultado["erro"]
    assert not smtp_cls.called
