# -*- coding: utf-8 -*-
"""Entrega de e-mail via Resend API, Brevo API ou SMTP, configurada por ambiente."""
import json
import os
import smtplib
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _enviar_brevo(assunto, texto, html, remetente, destinatario, api_key):
    """Brevo (ex-Sendinblue): só exige o remetente verificado por codigo de
    6 digitos enviado pro proprio e-mail (sem DNS/dominio proprio, ao
    contrario do Resend) - ver developers.brevo.com/docs/send-a-transactional-email.
    Free tier: 300 e-mails/dia, sem expiracao."""
    payload = {
        "sender": {"email": remetente},
        "to": [{"email": destinatario}],
        "subject": assunto,
        "textContent": texto,
    }
    if html:
        payload["htmlContent"] = html
    request = Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Pregao/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                return {"ok": False, "erro": f"Brevo retornou HTTP {response.status}."}
        return {"ok": True, "erro": None}
    except HTTPError as exc:
        # Não devolver headers/request: eles podem conter a chave de API.
        detalhe = ""
        try:
            corpo = json.loads(exc.read().decode("utf-8"))
            detalhe = str(corpo.get("message") or corpo.get("code") or "")[:300]
        except Exception:
            pass
        return {"ok": False, "erro": f"Brevo HTTP {exc.code}" + (f": {detalhe}" if detalhe else "")}
    except (URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "erro": f"Falha de conexão com Brevo: {type(exc).__name__}"}
    except Exception as exc:
        return {"ok": False, "erro": f"Falha no envio via Brevo: {type(exc).__name__}"}


def _enviar_resend(assunto, texto, html, remetente, destinatario, api_key):
    payload = {
        "from": remetente,
        "to": [destinatario],
        "subject": assunto,
        "text": texto,
    }
    if html:
        payload["html"] = html
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Pregao/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                return {"ok": False, "erro": f"Resend retornou HTTP {response.status}."}
        return {"ok": True, "erro": None}
    except HTTPError as exc:
        # Não devolver headers/request: eles podem conter a chave de API.
        detalhe = ""
        try:
            corpo = json.loads(exc.read().decode("utf-8"))
            detalhe = str(corpo.get("message") or corpo.get("name") or "")[:300]
        except Exception:
            pass
        return {"ok": False, "erro": f"Resend HTTP {exc.code}" + (f": {detalhe}" if detalhe else "")}
    except (URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "erro": f"Falha de conexão com Resend: {type(exc).__name__}"}
    except Exception as exc:
        return {"ok": False, "erro": f"Falha no envio via Resend: {type(exc).__name__}"}


def enviar_email(assunto, texto, html=None, destinatario=None):
    # (os.getenv(chave) or "smtp"), nao os.getenv(chave, "smtp") - achado
    # real (auditoria pos-merge 2026-10-17, run 39073788370): no GitHub
    # Actions, um "env:" que referencia um secret INEXISTENTE define a
    # variavel como string VAZIA, nao a deixa ausente - os.getenv(chave,
    # default) so' usa o default quando a chave esta' TOTALMENTE fora de
    # os.environ, entao uma EMAIL_PROVIDER="" (secret nao configurado)
    # devolvia "" em vez de cair no default "smtp", e "".strip().lower()
    # caia no branch de erro "deve ser 'smtp', 'resend' ou 'brevo'" -
    # mesma classe de problema que SMTP_PORT ja' tratava corretamente
    # algumas linhas abaixo (`os.getenv("SMTP_PORT", "587").strip() or
    # "587"`).
    provedor = (os.getenv("EMAIL_PROVIDER") or "smtp").strip().lower()
    usuario = os.getenv("SMTP_USER", "").strip()
    remetente = os.getenv("EMAIL_FROM", usuario).strip()
    destinatario = (destinatario or os.getenv("EMAIL_TO", "")).strip()

    if not remetente or not destinatario:
        return {"ok": False, "erro": "EMAIL_FROM e EMAIL_TO precisam estar configurados."}

    if provedor == "resend":
        api_key = os.getenv("RESEND_API_KEY", "").strip()
        if not api_key:
            return {"ok": False, "erro": "RESEND_API_KEY precisa estar configurada para EMAIL_PROVIDER=resend."}
        return _enviar_resend(assunto, texto, html, remetente, destinatario, api_key)

    if provedor == "brevo":
        api_key = os.getenv("BREVO_API_KEY", "").strip()
        if not api_key:
            return {"ok": False, "erro": "BREVO_API_KEY precisa estar configurada para EMAIL_PROVIDER=brevo."}
        return _enviar_brevo(assunto, texto, html, remetente, destinatario, api_key)

    if provedor != "smtp":
        return {"ok": False, "erro": "EMAIL_PROVIDER deve ser 'smtp', 'resend' ou 'brevo'."}

    host = os.getenv("SMTP_HOST", "").strip()
    senha = os.getenv("SMTP_PASSWORD", "")
    porta_texto = os.getenv("SMTP_PORT", "587").strip() or "587"
    if not all((host, usuario, senha)):
        return {"ok": False, "erro": "SMTP_HOST, SMTP_USER e SMTP_PASSWORD precisam estar configurados para EMAIL_PROVIDER=smtp."}
    try:
        porta = int(porta_texto)
        if not 1 <= porta <= 65535:
            raise ValueError
    except ValueError:
        return {"ok": False, "erro": "SMTP_PORT deve ser uma porta numérica entre 1 e 65535 (padrão 587)."}
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(host, porta, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(usuario, senha)
            smtp.send_message(msg)
        return {"ok": True, "erro": None}
    except Exception as exc:
        return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
