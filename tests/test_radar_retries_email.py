# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.research import genial_carteiras
from jobs import email_utils
from jobs.email_utils import enviar_email


def test_coletor_tenta_cliente_alternativo_apos_timeout(monkeypatch):
    monkeypatch.setattr(genial_carteiras, "permitido", lambda _url: True)
    monkeypatch.setattr(genial_carteiras.time, "sleep", lambda _segundos: None)
    monkeypatch.setattr(
        genial_carteiras.cffi_requests,
        "get",
        Mock(side_effect=TimeoutError("timeout simulado")),
    )
    resposta = Mock(status_code=200, text="<html>" + ("x" * 600) + "</html>")
    requisicao_padrao = Mock(return_value=resposta)
    monkeypatch.setattr(genial_carteiras.standard_requests, "get", requisicao_padrao)

    html = genial_carteiras._get("https://analisa.genialinvestimentos.com.br/teste")

    assert html == resposta.text
    assert requisicao_padrao.call_count == 1


def test_porta_smtp_vazia_usa_padrao_587(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_PORT", "")
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASSWORD", "")
    monkeypatch.setenv("EMAIL_FROM", "")
    monkeypatch.setenv("EMAIL_TO", "")

    resultado = enviar_email("teste", "corpo")

    assert resultado["ok"] is False
    assert "precisam estar configurados" in resultado["erro"]


def test_porta_smtp_invalida_retorna_erro_claro(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "abc")
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "senha")
    monkeypatch.setenv("EMAIL_FROM", "sender@example.com")
    monkeypatch.setenv("EMAIL_TO", "recipient@example.com")

    resultado = enviar_email("teste", "corpo")

    assert resultado["ok"] is False
    assert "SMTP_PORT" in resultado["erro"]


def test_email_provider_vazio_cai_no_padrao_smtp(monkeypatch):
    """Regressao real (auditoria pos-merge 2026-10-17, CI run 39073788370,
    commit 2e821ad): no GitHub Actions, um "env: EMAIL_PROVIDER:
    ${{ secrets.EMAIL_PROVIDER }}" sem o secret configurado define a
    variavel como string VAZIA, nao ausente - os.getenv("EMAIL_PROVIDER",
    "smtp") so' usa "smtp" quando a chave esta' fora de os.environ, entao
    EMAIL_PROVIDER="" caia direto no branch de erro "deve ser 'smtp',
    'resend' ou 'brevo'" mesmo com as credenciais SMTP completas e
    corretas presentes - bloqueava o Morning Call de verdade. Mesma
    classe de bug que test_porta_smtp_vazia_usa_padrao_587 acima ja
    cobria pra SMTP_PORT; faltava cobrir pra EMAIL_PROVIDER."""
    monkeypatch.setenv("EMAIL_PROVIDER", "")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "senha")
    monkeypatch.setenv("EMAIL_FROM", "sender@example.com")
    monkeypatch.setenv("EMAIL_TO", "recipient@example.com")

    smtp_instancia = MagicMock()
    smtp_instancia.__enter__.return_value = smtp_instancia
    smtp_cls = Mock(return_value=smtp_instancia)
    monkeypatch.setattr(email_utils.smtplib, "SMTP", smtp_cls)

    resultado = enviar_email("teste", "corpo")

    assert resultado == {"ok": True, "erro": None}
    smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=20)
    smtp_instancia.login.assert_called_once_with("sender@example.com", "senha")
    smtp_instancia.send_message.assert_called_once()
