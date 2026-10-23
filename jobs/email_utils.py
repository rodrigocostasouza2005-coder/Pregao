# -*- coding: utf-8 -*-
"""Entrega de e-mail via Resend API, Brevo API ou SMTP, configurada por ambiente."""
import base64
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _anexos_base64(anexos):
    """Normaliza `anexos` (lista de {"nome", "conteudo" (bytes), "tipo_mime"})
    pra uma lista de dicts com o conteudo em base64 - formato aceito tanto
    pelo Resend quanto pelo Brevo (so' muda o nome das chaves, aplicado por
    quem chama). None/lista vazia -> lista vazia, nunca quebra o envio por
    causa de um anexo ausente/opcional."""
    out = []
    for anexo in anexos or []:
        conteudo = anexo.get("conteudo")
        if not conteudo:
            continue
        out.append({
            "nome": anexo.get("nome") or "anexo",
            "tipo_mime": anexo.get("tipo_mime") or "application/octet-stream",
            "base64": base64.b64encode(conteudo).decode("ascii"),
        })
    return out


def _enviar_brevo(assunto, texto, html, remetente, destinatario, api_key, anexos=None):
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
    anexos_b64 = _anexos_base64(anexos)
    if anexos_b64:
        payload["attachment"] = [
            {"name": a["nome"], "content": a["base64"]} for a in anexos_b64
        ]
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


def _enviar_resend(assunto, texto, html, remetente, destinatario, api_key, anexos=None):
    payload = {
        "from": remetente,
        "to": [destinatario],
        "subject": assunto,
        "text": texto,
    }
    if html:
        payload["html"] = html
    anexos_b64 = _anexos_base64(anexos)
    if anexos_b64:
        payload["attachments"] = [
            {"filename": a["nome"], "content": a["base64"]} for a in anexos_b64
        ]
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


_TIMEOUT_SMTP_S = 60


def enviar_email(assunto, texto, html=None, destinatario=None, anexos=None):
    """`anexos` (opcional): lista de {"nome": str, "conteudo": bytes,
    "tipo_mime": str} - ex. o PDF editorial do Morning Call
    (jobs/morning_call_pdf.py). Anexo ausente/None nunca muda o
    comportamento de quem já chamava enviar_email sem esse parâmetro
    (ex. jobs/radar_quedas.py)."""
    # Bug real (achado 2026-10-17, 1a execucao que passou da checagem de
    # EMAIL_FROM/EMAIL_TO): os.getenv(key, default) so' usa o default
    # quando a chave esta' AUSENTE do ambiente - no GitHub Actions,
    # `env: EMAIL_PROVIDER: ${{ secrets.EMAIL_PROVIDER }}` com o secret
    # NAO configurado ainda define a variavel, so' que com valor ""
    # (presente, vazia) - entao o default "smtp" nunca era aplicado,
    # provedor virava "" e caia no erro "deve ser smtp/resend/brevo"
    # mesmo sem ninguem ter configurado EMAIL_PROVIDER=qualquer-coisa-
    # invalida de proposito. `or` cobre os dois casos (ausente E vazia).
    provedor = (os.getenv("EMAIL_PROVIDER") or "smtp").strip().lower()
    usuario = os.getenv("SMTP_USER", "").strip()
    # Mesma classe de bug do provedor acima: EMAIL_FROM "presente mas
    # vazio" (secret nao configurado no GitHub Actions) nao pode travar
    # o fallback pro SMTP_USER - os.getenv(key, default) so' aplicaria
    # o default se a chave estivesse AUSENTE, nao vazia.
    remetente = (os.getenv("EMAIL_FROM") or usuario).strip()
    destinatario = (destinatario or os.getenv("EMAIL_TO", "")).strip()

    if not remetente or not destinatario:
        return {"ok": False, "erro": "EMAIL_FROM e EMAIL_TO precisam estar configurados."}

    if provedor == "resend":
        api_key = os.getenv("RESEND_API_KEY", "").strip()
        if not api_key:
            return {"ok": False, "erro": "RESEND_API_KEY precisa estar configurada para EMAIL_PROVIDER=resend."}
        return _enviar_resend(assunto, texto, html, remetente, destinatario, api_key, anexos)

    if provedor == "brevo":
        api_key = os.getenv("BREVO_API_KEY", "").strip()
        if not api_key:
            return {"ok": False, "erro": "BREVO_API_KEY precisa estar configurada para EMAIL_PROVIDER=brevo."}
        return _enviar_brevo(assunto, texto, html, remetente, destinatario, api_key, anexos)

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
    for anexo in anexos or []:
        conteudo = anexo.get("conteudo")
        if not conteudo:
            continue
        tipo_mime = anexo.get("tipo_mime") or "application/octet-stream"
        maintype, _, subtype = tipo_mime.partition("/")
        msg.add_attachment(
            conteudo, maintype=maintype or "application", subtype=subtype or "octet-stream",
            filename=anexo.get("nome") or "anexo",
        )
    # etapa registrada no erro (achado real 21/10/2026, run 39630028404):
    # o log so' dizia "SMTPServerDisconnected: ... The read operation
    # timed out" - mensagem de timeout DENTRO do TLS ja' estabelecido, ou
    # seja, falhou no login ou no envio (PDF de ~165 KB anexo), nao na
    # conexao. Sem a etapa nao dava pra saber qual. Timeout 20s -> 60s:
    # o servidor so' responde ao fim do DATA depois de processar o anexo.
    # Sem reenvio automatico de proposito: timeout depois do DATA pode
    # significar mensagem ja' aceita - reenviar duplicaria o e-mail.
    etapa = "conexão"
    try:
        with smtplib.SMTP(host, porta, timeout=_TIMEOUT_SMTP_S) as smtp:
            etapa = "STARTTLS"
            # smtp.starttls() sem `context` usa ssl._create_stdlib_context()
            # (CERT_NONE, sem checagem de hostname) - TLS sem validar o
            # certificado do servidor, vulnerável a MITM. Google Workspace
            # exige TLS explícito COM validação (requisito #4 da auditoria);
            # ssl.create_default_context() valida cadeia e hostname contra
            # as CAs do sistema.
            smtp.starttls(context=ssl.create_default_context())
            etapa = "login"
            smtp.login(usuario, senha)
            etapa = "envio da mensagem"
            smtp.send_message(msg)
        return {"ok": True, "erro": None}
    except Exception as exc:
        return {"ok": False, "erro": f"{type(exc).__name__} (etapa SMTP: {etapa}): {exc}"}
