# -*- coding: utf-8 -*-
"""Preferencias do usuario, persistidas no Supabase (tabela user_prefs)."""

from config import PREFS_PADRAO
from data.supabase_client import obter_cliente


def obter_prefs(sub: str) -> tuple[dict, bool]:
    """Busca preferencias do usuario pelo sub. Retorna (prefs, banco_disponivel)."""
    prefs = dict(PREFS_PADRAO)
    cliente = obter_cliente()
    if cliente is None:
        return prefs, False
    try:
        resp = cliente.table("user_prefs").select("preferencias").eq("sub", sub).limit(1).execute()
        if resp.data:
            prefs.update(resp.data[0].get("preferencias") or {})
        return prefs, True
    except Exception:
        return prefs, False


def salvar_prefs(sub: str, email: str, prefs: dict) -> bool:
    """Grava preferencias no Supabase (upsert por sub). True se salvou."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        cliente.table("user_prefs").upsert(
            {"sub": sub, "email": email.lower(), "preferencias": prefs}
        ).execute()
        return True
    except Exception:
        return False


def listar_assinantes_morning_call() -> list[dict] | None:
    """[{"sub", "email"}] dos usuarios com preferencias["morning_call_email"]
    True e email valido (sempre e', `email` e' NOT NULL em user_prefs - ver
    sql/schema.sql) - fonte de verdade do opt-in (2026-10-16): nunca um
    destinatario fixo/EMAIL_TO, so' quem marcou explicitamente na aba
    CONFIG (e pode desmarcar a qualquer momento, mesmo controle).

    None se o banco estiver fora do ar - quem chama (jobs/morning_call.py)
    NUNCA deve tratar None como "ninguem assinou" (enviaria pra zero
    pessoas silenciosamente); lista vazia [] e' o caso real de "ninguem
    assinou ainda", distinto de "nao deu pra saber".

    Busca TODAS as linhas e filtra em Python (nao via filtro JSON do
    PostgREST) de proposito: `preferencias` e' um jsonb de schema livre
    (todas as outras prefs do CONFIG moram no mesmo dict) - um filtro
    `.eq("preferencias->>morning_call_email", "true")` dependeria de tipo
    exato armazenado (bool vs string) e seria mais fragil que checar o
    valor Python direto depois de decodificado. Escala de usuarios deste
    projeto (pessoal/pequeno grupo) torna isso irrelevante em custo."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = cliente.table("user_prefs").select("sub,email,preferencias").execute()
    except Exception:
        return None
    assinantes = []
    for linha in resp.data or []:
        prefs = linha.get("preferencias") or {}
        email = (linha.get("email") or "").strip()
        sub = linha.get("sub")
        if prefs.get("morning_call_email") is True and email and sub:
            assinantes.append({"sub": sub, "email": email})
    return assinantes
