# -*- coding: utf-8 -*-
"""Camada de dados do painel administrativo USUÁRIOS (ver ui/usuarios_tab.py).

Autorização aplicada AQUI, não só na navegação/renderização - mesmo que
alguém chame estas funções diretamente (bug de UI, novo código, etc.),
um e-mail fora de config.obter_emails_admin() nunca recebe nenhum dado
real de volta (None, igual a "indisponível"). Reutiliza a MESMA tabela
user_prefs já usada pelas preferências/assinantes do Morning Call (ver
data/user_prefs.py) - nenhuma tabela nem lista paralela de usuários.
"""

import streamlit as st

import config
from data.supabase_client import obter_cliente

_TAMANHO_PAGINA_USUARIOS = 500


def _admin_autorizado(email_admin: str) -> bool:
    return bool(email_admin) and email_admin.lower() in [
        e.lower() for e in config.obter_emails_admin()
    ]


@st.cache_data(ttl=90, show_spinner=False)
def obter_usuarios_admin(email_admin: str, _cliente=None) -> list[dict] | None:
    """Lista normalizada de usuários (1 dict por `sub`) pro painel admin.

    None quando: `email_admin` não está em config.obter_emails_admin()
    (nunca chega a consultar o banco - a checagem de autorização vem
    ANTES de qualquer query), Supabase indisponível, ou a consulta
    lançar excessão. Lista [] é o caso real "banco disponível, zero
    linhas em user_prefs ainda" - mesma distinção None/[] já usada em
    data/user_prefs.py:listar_assinantes_morning_call, pelo mesmo motivo
    (quem chama nunca deve ler None como "zero usuários").

    @st.cache_data (ttl=90s, achado real da missão de redesign/performance
    2026-10-19): ui/usuarios_tab.py:render_usuarios chama esta função sem
    nenhum cache e tem busca/filtros interativos (st.text_input/
    st.selectbox) na MESMA tela - cada tecla digitada na busca disparava
    um rerun que refazia a varredura paginada INTEIRA de user_prefs no
    Supabase, mesmo a busca/filtro sendo em memória (_filtrar, depois da
    consulta). `_cliente` com underscore = fora da chave de cache
    (convenção do Streamlit pra parâmetro não-hasheável, ex. cliente
    MagicMock em teste) - cache é só por email_admin."""
    if not _admin_autorizado(email_admin):
        return None
    cliente = _cliente if _cliente is not None else obter_cliente()
    if cliente is None:
        return None
    usuarios = []
    try:
        inicio = 0
        while True:
            fim = inicio + _TAMANHO_PAGINA_USUARIOS - 1
            resp = (
                cliente.table("user_prefs")
                .select("sub,email,preferencias,created_at,last_seen_at")
                .range(inicio, fim)
                .execute()
            )
            linhas = resp.data or []
            for linha in linhas:
                prefs_usuario = linha.get("preferencias") or {}
                if prefs_usuario.get("morning_call_email_ativo"):
                    status_inscricao = "inscrito"
                elif prefs_usuario.get("morning_call_email_perguntado"):
                    status_inscricao = "recusou"
                else:
                    status_inscricao = "nao_respondeu"
                usuarios.append(
                    {
                        "sub": linha.get("sub"),
                        "email": (linha.get("email") or "").strip().lower(),
                        "created_at": linha.get("created_at"),
                        "last_seen_at": linha.get("last_seen_at"),
                        "status_inscricao": status_inscricao,
                    }
                )
            if len(linhas) < _TAMANHO_PAGINA_USUARIOS:
                break
            inicio += _TAMANHO_PAGINA_USUARIOS
    except Exception as exc:
        print(f"[admin_usuarios] falha ao listar usuarios: {exc!r}")
        return None
    return usuarios
