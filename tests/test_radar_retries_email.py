# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.research import genial_carteiras
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

    resultado = enviar_email("teste", "corpo")

    assert resultado["ok"] is False
    assert "precisam estar configurados" in resultado["erro"]


def test_porta_smtp_invalida_retorna_erro_claro(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "abc")
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "senha")
    monkeypatch.setenv("EMAIL_FROM", "sender@example.com")

    resultado = enviar_email("teste", "corpo", destinatario="recipient@example.com")

    assert resultado["ok"] is False
    assert "SMTP_PORT" in resultado["erro"]


def test_email_provider_vazio_nao_ausente_ainda_usa_smtp_por_padrao(monkeypatch):
    """Bug real (2026-10-17, 1a execução em produção que passou da
    checagem de EMAIL_FROM/destinatario): no GitHub Actions,
    `env: EMAIL_PROVIDER: ${{ secrets.EMAIL_PROVIDER }}` com o secret
    NÃO configurado define a variável com valor "" (presente, vazia) -
    não AUSENTE. `os.getenv(chave, default)` só aplica o default quando
    a chave está ausente do ambiente, nunca quando só está vazia -
    então EMAIL_PROVIDER="" nunca caía no default "smtp", virava "" e
    o envio falhava com "EMAIL_PROVIDER deve ser 'smtp', 'resend' ou
    'brevo'" mesmo sem ninguém ter configurado nada inválido de
    propósito. Nenhum teste anterior pegou isso porque sempre deixava
    EMAIL_FROM vazio/destinatario ausente juntos, o que retorna mais
    cedo (ver test_porta_smtp_vazia_usa_padrao_587 acima) e nunca
    alcançava essa linha."""
    monkeypatch.setenv("EMAIL_PROVIDER", "")  # como fica no Actions quando o secret não existe
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "")  # só pra provar que chegou no branch smtp, não travou antes
    monkeypatch.setenv("EMAIL_FROM", "sender@example.com")

    resultado = enviar_email("teste", "corpo", destinatario="recipient@example.com")

    assert resultado["ok"] is False
    assert "SMTP_PASSWORD" in resultado["erro"], (
        f"esperava cair no branch smtp (erro de SMTP_PASSWORD ausente), "
        f"mas caiu em: {resultado['erro']!r}"
    )


def test_email_from_vazio_nao_ausente_ainda_cai_pro_smtp_user(monkeypatch):
    """Mesma classe de bug, pro fallback EMAIL_FROM -> SMTP_USER."""
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("EMAIL_FROM", "")  # presente, vazio - não ausente
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_PASSWORD", "")

    resultado = enviar_email("teste", "corpo", destinatario="recipient@example.com")

    # Se o fallback pro SMTP_USER não tivesse funcionado, teria parado
    # mais cedo com "EMAIL_FROM e um destinatário precisam estar configurados".
    assert resultado["erro"] != "EMAIL_FROM e um destinatário precisam estar configurados."
    assert "SMTP_PASSWORD" in resultado["erro"]
