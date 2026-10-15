# -*- coding: utf-8 -*-
"""Cliente Supabase compartilhado.

No Streamlit Cloud, lê as credenciais de st.secrets. Em tarefas externas
(GitHub Actions), aceita as mesmas credenciais por variáveis de ambiente,
sem exigir arquivos locais de configuração.
"""

import base64
import json
import os
import streamlit as st

try:
    from supabase import create_client
except ImportError:
    create_client = None


def _classificar_formato_chave(secret_key: str) -> str:
    """Confere se a CHAVE (nunca o segredo em si) tem formato claramente
    PUBLICO (sem privilegio de escrita/bypass de RLS) antes de sequer
    tentar usa-la - achado real (auditoria 2026-10-15): sem isso, uma
    chave publica colada por engano no lugar da secret key gera 1
    excecao "new row violates row-level security policy" POR TABELA/
    POR COLETOR (8+ linhas de erro identicas e confusas no log), em vez
    de 1 diagnostico claro na raiz.

    Supabase tem 2 sistemas de chave:
    - legado (JWT, comeca com "eyJ"): o 2o segmento (payload) e' so'
      base64 SEM assinatura - ler o claim "role" dele NUNCA expoe o
      segredo de assinatura do projeto (e' informacao que o proprio
      token carrega pra quem o recebe decidir o que fazer).
    - novo (opaco, "sb_publishable_..." ou "sb_secret_..."): o prefixo
      por si so' ja' diz o papel, sem decodificar nada.

    Retorna "PRIVILEGIADA", "PUBLICA" ou "DESCONHECIDO" (formato novo
    nunca visto, ou JWT sem claim "role" decodificavel - nesses casos,
    deixa a tentativa real de uso decidir, nunca bloqueia por engano)."""
    if not secret_key:
        return "DESCONHECIDO"
    if secret_key.startswith("sb_secret_"):
        return "PRIVILEGIADA"
    if secret_key.startswith("sb_publishable_"):
        return "PUBLICA"
    if secret_key.startswith("eyJ"):
        try:
            partes = secret_key.split(".")
            if len(partes) != 3:
                return "DESCONHECIDO"
            payload_b64 = partes[1] + "=" * (-len(partes[1]) % 4)
            papel = json.loads(base64.urlsafe_b64decode(payload_b64)).get("role")
            if papel == "service_role":
                return "PRIVILEGIADA"
            if papel in ("anon", "authenticated"):
                return "PUBLICA"
        except Exception:
            pass
    return "DESCONHECIDO"


@st.cache_resource(show_spinner=False)
def obter_cliente():
    """Cliente Supabase (singleton); None quando faltam credenciais OU
    quando a credencial presente e' claramente a chave publica (nunca
    cria um cliente fadado a falhar em toda escrita - quem chama ja'
    trata None exatamente como "Supabase indisponivel", sem inventar
    sucesso nem apagar dado valido, ver callers em data/*.py)."""
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
        if _classificar_formato_chave(secret_key) == "PUBLICA":
            print(
                "[supabase_client] SUPABASE_SECRET_KEY parece ser uma chave PUBLICA "
                "(publishable/anon) - nunca tem privilegio de escrita/bypass de RLS. "
                "Configure a chave 'secret' (sb_secret_...) ou 'service_role' do painel "
                "Supabase (Settings > API) no secret SUPABASE_SECRET_KEY."
            )
            return None
        return create_client(url, secret_key)
    except Exception:
        return None
