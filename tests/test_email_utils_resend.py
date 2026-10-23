import base64
import json
from urllib.error import HTTPError
from unittest.mock import MagicMock

from jobs import email_utils


def test_resend_envia_texto_e_html(monkeypatch):
    response = MagicMock()
    response.status = 200
    response.__enter__.return_value = response
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
    assert capturado["timeout"] == 20
    assert payload["to"] == ["destino@example.com"]
    assert payload["text"] == "Texto"
    assert payload["html"] == "<p>HTML</p>"


def test_resend_envia_anexo_em_base64(monkeypatch):
    response = MagicMock()
    response.status = 200
    response.__enter__.return_value = response
    capturado = {}

    def fake_urlopen(request, timeout):
        capturado["request"] = request
        return response

    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_secret")
    monkeypatch.setenv("EMAIL_FROM", "Pregao <alerts@example.com>")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    monkeypatch.setattr(email_utils, "urlopen", fake_urlopen)

    resultado = email_utils.enviar_email(
        "Assunto", "Texto", "<p>HTML</p>",
        anexos=[{"nome": "mc.pdf", "conteudo": b"%PDF-conteudo", "tipo_mime": "application/pdf"}],
    )

    payload = json.loads(capturado["request"].data.decode("utf-8"))
    assert resultado == {"ok": True, "erro": None}
    assert payload["attachments"] == [
        {"filename": "mc.pdf", "content": base64.b64encode(b"%PDF-conteudo").decode("ascii")}
    ]


def test_resend_sem_anexos_nao_inclui_a_chave_no_payload(monkeypatch):
    response = MagicMock()
    response.status = 200
    response.__enter__.return_value = response
    capturado = {}

    def fake_urlopen(request, timeout):
        capturado["request"] = request
        return response

    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_secret")
    monkeypatch.setenv("EMAIL_FROM", "alerts@example.com")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    monkeypatch.setattr(email_utils, "urlopen", fake_urlopen)

    email_utils.enviar_email("Assunto", "Texto")

    payload = json.loads(capturado["request"].data.decode("utf-8"))
    assert "attachments" not in payload


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


def test_resend_http_error_403_extrai_mensagem_do_corpo_json(monkeypatch):
    """Caminho real de produção (achado na auditoria dos coletores,
    22/10/2026): Resend devolve 403 com corpo JSON
    {"message": "...", "name": "..."} quando o domínio de EMAIL_FROM não
    está verificado - jobs/email_utils.py:_enviar_resend lê exc.read() e
    extrai corpo["message"] nesse caso (branch nunca exercitado pelos
    testes anteriores, que só cobriam HTTPError sem corpo/fp=None - o
    `except Exception: pass` ao redor do parse do JSON escondia
    silenciosamente uma regressão nesse caminho). Mensagem real vista em
    produção: "The gmail.com domain is not verified. Please, add and
    verify your domain on https://resend.com/domains" - EMAIL_FROM
    configurado pelo dono aponta pra um domínio que o Resend nunca vai
    conseguir verificar (gmail.com não pertence ao projeto); reproduzida
    aqui com um corpo genérico equivalente, não o segredo real."""
    import io

    corpo_json = json.dumps({
        "message": "The example.com domain is not verified. Please, add and verify your domain on https://resend.com/domains",
        "name": "validation_error",
    }).encode("utf-8")
    erro = HTTPError(
        url="https://api.resend.com/emails",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=io.BytesIO(corpo_json),
    )
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "nao-deve-aparecer")
    monkeypatch.setenv("EMAIL_FROM", "alerts@example.com")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    monkeypatch.setattr(email_utils, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(erro))

    resultado = email_utils.enviar_email("Assunto", "Texto")

    assert resultado["ok"] is False
    assert resultado["erro"] == (
        "Resend HTTP 403: The example.com domain is not verified. Please, add and "
        "verify your domain on https://resend.com/domains"
    )
    assert "nao-deve-aparecer" not in resultado["erro"]


def test_resend_http_error_com_corpo_nao_json_nunca_quebra(monkeypatch):
    """Corpo de erro que não é JSON válido (HTML de página de erro, texto
    cru etc) não pode lançar exceção pro chamador - cai no
    `except Exception: pass` e devolve só o código HTTP, sem detalhe."""
    import io

    erro = HTTPError(
        url="https://api.resend.com/emails",
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=io.BytesIO(b"<html>not json</html>"),
    )
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "chave")
    monkeypatch.setenv("EMAIL_FROM", "alerts@example.com")
    monkeypatch.setenv("EMAIL_TO", "destino@example.com")
    monkeypatch.setattr(email_utils, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(erro))

    resultado = email_utils.enviar_email("Assunto", "Texto")

    assert resultado == {"ok": False, "erro": "Resend HTTP 500"}
