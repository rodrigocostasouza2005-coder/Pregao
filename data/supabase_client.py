# -*- coding: utf-8 -*-
"""Cliente Supabase compartilhado (singleton) - usado por user_prefs.py e
data/research/store.py. Centralizado aqui pra nao duplicar a checagem de
secrets em cada modulo que precisa do banco."""

import streamlit as st

try:
    from supabase import create_client
except ImportError:
    create_client = None


@st.cache_resource(show_spinner=False)
def obter_cliente():
    """Cliente Supabase (singleton). None se a lib estiver ausente ou os
    secrets nao estiverem preenchidos - quem chama trata esse caso como
    'banco fora do ar' (degrada graciosamente, nunca quebra o app)."""
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
