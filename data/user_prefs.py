# -*- coding: utf-8 -*-
"""Preferencias do usuario, persistidas no Supabase (tabela user_prefs)."""

import streamlit as st

from config import PREFS_PADRAO

try:
    from supabase import create_client
except ImportError:
    create_client = None


@st.cache_resource(show_spinner=False)
def _cliente():
    """Cliente Supabase (singleton). None se lib ausente ou secrets nao preenchidos."""
    if create_client is None:
        return None
    try:
        url = st.secrets["supabase"]["url"]
        secret_key = st.secrets["supabase"]["secret_key"]
        if not url or not secret_key or "SEU-PROJETO" in url or "COLE_AQUI" in secret_key:
            return None
        return create_client(url, secret_key)
    except Exception:
        return None


def obter_prefs(sub: str) -> tuple[dict, bool]:
    """Busca preferencias do usuario pelo sub. Retorna (prefs, banco_disponivel)."""
    prefs = dict(PREFS_PADRAO)
    cliente = _cliente()
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
    cliente = _cliente()
    if cliente is None:
        return False
    try:
        cliente.table("user_prefs").upsert(
            {"sub": sub, "email": email.lower(), "preferencias": prefs}
        ).execute()
        return True
    except Exception:
        return False
