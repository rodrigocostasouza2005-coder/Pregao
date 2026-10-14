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
