import json
from urllib.error import HTTPError
from unittest.mock import Mock

from jobs import email_utils


def test_resend_envia_texto_e_html(monkeypatch):
    response = Mock()
    response.status = 200
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    capturado = {}

    def fake_urlopen(request, timeout):
        capturado["request"] = request
        capturado["timeout"] = timeout
        return response

    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_secret")
    monkeypatch.setenv("EMAIL_FROM", "Pregao <alerts@example.com>")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    monkeypatch.setattr(email_utils, "urlopen", fake_urlopen)

    resultado = email_utils.enviar_email("Assunto", "Texto", "<p>HTML</p>")

    request = capturado["request"]
    payload = json.loads(request.data.decode("utf-8"))
    assert resultado == {"ok": True, "erro": None}
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_header("Authorization") == "Bearer re_test_secret"
    assert payload["to"] == ["destino@example.com"]
    assert payload["text"] == "Texto"
    assert payload["html"] == "<p>HTML</p>"


def test_resend_sem_chave_retorna_erro_sem_tentar_rede(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("EMAIL_FROM", "alerts@example.com")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")

    resultado = email_utils.enviar_email("Assunto", "Texto")

    assert resultado["ok"] is False
    assert "RESEND_API_KEY" in resultado["erro"]


def test_resend_http_error_nao_expoe_chave(monkeypatch):
    erro = HTTPError(
        url="https://api.resend.com/emails",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=None,
    )
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "nao-deve-aparecer")
    monkeypatch.setenv("EMAIL_FROM", "alerts@example.com")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    monkeypatch.setattr(email_utils, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(erro))

    resultado = email_utils.enviar_email("Assunto", "Texto")

    assert resultado["ok"] is False
    assert "401" in resultado["erro"]
    assert "nao-deve-aparecer" not in resultado["erro"]
