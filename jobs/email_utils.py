# -*- coding: utf-8 -*-
"""Entrega de e-mail via SMTP, configurada exclusivamente por variáveis de ambiente."""
import os
import smtplib
from email.message import EmailMessage


def enviar_email(assunto, texto, html=None, destinatario=None):
    host = os.getenv("SMTP_HOST", "").strip()
    usuario = os.getenv("SMTP_USER", "").strip()
    senha = os.getenv("SMTP_PASSWORD", "")
    remetente = os.getenv("EMAIL_FROM", usuario).strip()
    destinatario = (destinatario or os.getenv("EMAIL_TO", "")).strip()
    porta = int(os.getenv("SMTP_PORT", "587"))
    if not all((host, usuario, senha, remetente, destinatario)):
        return {"ok": False, "erro": "SMTP_HOST, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM e EMAIL_TO precisam estar configurados."}
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
