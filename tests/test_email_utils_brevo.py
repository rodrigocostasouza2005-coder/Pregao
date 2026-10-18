import base64
import json
from urllib.error import HTTPError
from unittest.mock import MagicMock

from jobs import email_utils


def test_brevo_envia_texto_e_html(monkeypatch):
    response = MagicMock()
    response.status = 201
    response.__enter__.return_value = response
    capturado = {}

    def fake_urlopen(request, timeout):
        capturado["request"] = request
        capturado["timeout"] = timeout
        return response

    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("BREVO_API_KEY", "xkeysib_test_secret")
    monkeypatch.setenv("EMAIL_FROM", "pregaoresumos@gmail.com")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    monkeypatch.setattr(email_utils, "urlopen", fake_urlopen)

    resultado = email_utils.enviar_email("Assunto", "Texto", "<p>HTML</p>")

    request = capturado["request"]
    payload = json.loads(request.data.decode("utf-8"))
    assert resultado == {"ok": True, "erro": None}
    assert request.full_url == "https://api.brevo.com/v3/smtp/email"
    assert request.get_header("Api-key") == "xkeysib_test_secret"
    assert capturado["timeout"] == 20
    assert payload["sender"] == {"email": "pregaoresumos@gmail.com"}
    assert payload["to"] == [{"email": "destino@example.com"}]
    assert payload["textContent"] == "Texto"
    assert payload["htmlContent"] == "<p>HTML</p>"


def test_brevo_envia_anexo_em_base64(monkeypatch):
    response = MagicMock()
    response.status = 201
    response.__enter__.return_value = response
    capturado = {}

    def fake_urlopen(request, timeout):
        capturado["request"] = request
        return response

    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("BREVO_API_KEY", "xkeysib_test_secret")
    monkeypatch.setenv("EMAIL_FROM", "pregaoresumos@gmail.com")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    monkeypatch.setattr(email_utils, "urlopen", fake_urlopen)

    resultado = email_utils.enviar_email(
        "Assunto", "Texto", "<p>HTML</p>",
        anexos=[{"nome": "mc.pdf", "conteudo": b"%PDF-conteudo", "tipo_mime": "application/pdf"}],
    )

    payload = json.loads(capturado["request"].data.decode("utf-8"))
    assert resultado == {"ok": True, "erro": None}
    assert payload["attachment"] == [
        {"name": "mc.pdf", "content": base64.b64encode(b"%PDF-conteudo").decode("ascii")}
    ]


def test_brevo_sem_anexos_nao_inclui_a_chave_no_payload(monkeypatch):
    response = MagicMock()
    response.status = 201
    response.__enter__.return_value = response
    capturado = {}

    def fake_urlopen(request, timeout):
        capturado["request"] = request
        return response

    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("BREVO_API_KEY", "xkeysib_test_secret")
    monkeypatch.setenv("EMAIL_FROM", "pregaoresumos@gmail.com")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    monkeypatch.setattr(email_utils, "urlopen", fake_urlopen)

    email_utils.enviar_email("Assunto", "Texto")

    payload = json.loads(capturado["request"].data.decode("utf-8"))
    assert "attachment" not in payload


def test_brevo_sem_chave_retorna_erro_sem_tentar_rede(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    monkeypatch.setenv("EMAIL_FROM", "pregaoresumos@gmail.com")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")

    resultado = email_utils.enviar_email("Assunto", "Texto")

    assert resultado["ok"] is False
    assert "BREVO_API_KEY" in resultado["erro"]


def test_brevo_http_error_nao_expoe_chave(monkeypatch):
    erro = HTTPError(
        url="https://api.brevo.com/v3/smtp/email",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=None,
    )
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("BREVO_API_KEY", "nao-deve-aparecer")
    monkeypatch.setenv("EMAIL_FROM", "pregaoresumos@gmail.com")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    monkeypatch.setattr(email_utils, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(erro))

    resultado = email_utils.enviar_email("Assunto", "Texto")

    assert resultado["ok"] is False
    assert "401" in resultado["erro"]
    assert "nao-deve-aparecer" not in resultado["erro"]


def test_provedor_invalido_cita_as_tres_opcoes_validas(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "mailgun")
    monkeypatch.setenv("EMAIL_FROM", "pregaoresumos@gmail.com")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")

    resultado = email_utils.enviar_email("Assunto", "Texto")

    assert resultado["ok"] is False
    assert "smtp" in resultado["erro"] and "resend" in resultado["erro"] and "brevo" in resultado["erro"]
