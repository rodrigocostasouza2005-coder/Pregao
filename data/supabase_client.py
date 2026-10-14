# -*- coding: utf-8 -*-
"""Cliente Supabase compartilhado.

No Streamlit Cloud, lê as credenciais de st.secrets. Em tarefas externas
(GitHub Actions), aceita as mesmas credenciais por variáveis de ambiente,
sem exigir arquivos locais de configuração.
"""

import os
import streamlit as st

try:
    from supabase import create_client
except ImportError:
    create_client = None


@st.cache_resource(show_spinner=False)
def obter_cliente():
    """Cliente Supabase (singleton); None quando faltam credenciais."""
    if create_client is None:
        return None
    try:
        # Variáveis de ambiente têm prioridade para workers sem Streamlit.
        url = os.getenv("SUPABASE_URL", "").strip()
        secret_key = os.getenv("SUPABASE_SECRET_KEY", "").strip()

        # Compatibilidade com a configuração já usada pelo app Streamlit.
        if not url or not secret_key:
            try:
                url = url or str(st.secrets["supabase"]["url"]).strip()
                secret_key = secret_key or str(st.secrets["supabase"]["secret_key"]).strip()
            except Exception:
                pass

        if (
            not url
            or not secret_key
            or "SEU-PROJETO" in url
            or "COLE_AQUI" in secret_key
        ):
            return None
        return create_client(url, secret_key)
    except Exception:
        return None
