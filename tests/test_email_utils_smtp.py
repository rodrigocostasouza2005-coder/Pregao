# -*- coding: utf-8 -*-
"""Cobertura do caminho SMTP de jobs/email_utils.py - provedor padrão
(EMAIL_PROVIDER ausente/"smtp") sem nenhum teste dedicado até aqui.
Mocka smtplib.SMTP inteiro (nunca abre conexão real)."""
from unittest.mock import MagicMock

from jobs import email_utils


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
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    smtp_instancia = _smtp_mock(monkeypatch)

    resultado = email_utils.enviar_email(
        "Assunto", "Texto", "<p>HTML</p>",
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
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    smtp_instancia = _smtp_mock(monkeypatch)

    email_utils.enviar_email("Assunto", "Texto", "<p>HTML</p>")

    msg_enviada = smtp_instancia.send_message.call_args[0][0]
    assert list(msg_enviada.iter_attachments()) == []


def test_smtp_anexo_vazio_e_ignorado_sem_quebrar_envio(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "segredo")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    smtp_instancia = _smtp_mock(monkeypatch)

    resultado = email_utils.enviar_email(
        "Assunto", "Texto", anexos=[{"nome": "vazio.pdf", "conteudo": b""}],
    )

    assert resultado == {"ok": True, "erro": None}
    msg_enviada = smtp_instancia.send_message.call_args[0][0]
    assert list(msg_enviada.iter_attachments()) == []


def _env_smtp(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "segredo")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")


def test_smtp_falha_informa_a_etapa_e_nao_reenvia(monkeypatch):
    """Regressao do envio real de 21/10/2026: o erro so' dizia 'read
    operation timed out', sem dizer se foi login ou envio do anexo."""
    import smtplib

    _env_smtp(monkeypatch)
    smtp_instancia = _smtp_mock(monkeypatch)
    smtp_instancia.send_message.side_effect = smtplib.SMTPServerDisconnected(
        "Connection unexpectedly closed: The read operation timed out")

    resultado = email_utils.enviar_email("Assunto", "Texto")

    assert resultado["ok"] is False
    assert "etapa SMTP: envio da mensagem" in resultado["erro"]
    assert smtp_instancia.send_message.call_count == 1  # nunca reenvia sozinho


def test_smtp_falha_no_login_e_identificada(monkeypatch):
    import smtplib

    _env_smtp(monkeypatch)
    smtp_instancia = _smtp_mock(monkeypatch)
    smtp_instancia.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")

    resultado = email_utils.enviar_email("Assunto", "Texto")

    assert "etapa SMTP: login" in resultado["erro"]
    assert not smtp_instancia.send_message.called


def test_smtp_usa_timeout_de_60s(monkeypatch):
    _env_smtp(monkeypatch)
    smtp_instancia = MagicMock()
    smtp_instancia.__enter__.return_value = smtp_instancia
    smtp_cls = MagicMock(return_value=smtp_instancia)
    monkeypatch.setattr(email_utils.smtplib, "SMTP", smtp_cls)

    email_utils.enviar_email("Assunto", "Texto")

    assert smtp_cls.call_args.kwargs["timeout"] == 60
