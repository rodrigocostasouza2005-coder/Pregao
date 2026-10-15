# -*- coding: utf-8 -*-
"""Entrega de e-mail via Resend API ou SMTP, configurada por ambiente."""
import json
import os
import smtplib
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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
    provedor = os.getenv("EMAIL_PROVIDER", "smtp").strip().lower()
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

    if provedor != "smtp":
        return {"ok": False, "erro": "EMAIL_PROVIDER deve ser 'smtp' ou 'resend'."}

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
