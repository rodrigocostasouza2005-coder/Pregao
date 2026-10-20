# -*- coding: utf-8 -*-
"""Camada de dados do painel administrativo USUÁRIOS (ver ui/usuarios_tab.py).

Autorização aplicada AQUI, não só na navegação/renderização - mesmo que
alguém chame estas funções diretamente (bug de UI, novo código, etc.),
um e-mail fora de config.obter_emails_admin() nunca recebe nenhum dado
real de volta (None, igual a "indisponível"). Reutiliza a MESMA tabela
user_prefs já usada pelas preferências/assinantes do Morning Call (ver
data/user_prefs.py) - nenhuma tabela nem lista paralela de usuários.
"""

import config
from data.supabase_client import obter_cliente

_TAMANHO_PAGINA_USUARIOS = 500


def _admin_autorizado(email_admin: str) -> bool:
    return bool(email_admin) and email_admin.lower() in [
        e.lower() for e in config.obter_emails_admin()
    ]


def obter_usuarios_admin(email_admin: str, cliente=None) -> list[dict] | None:
    """Lista normalizada de usuários (1 dict por `sub`) pro painel admin.

    None quando: `email_admin` não está em config.obter_emails_admin()
    (nunca chega a consultar o banco - a checagem de autorização vem
    ANTES de qualquer query), Supabase indisponível, ou a consulta
    lançar excessão. Lista [] é o caso real "banco disponível, zero
    linhas em user_prefs ainda" - mesma distinção None/[] já usada em
    data/user_prefs.py:listar_assinantes_morning_call, pelo mesmo motivo
    (quem chama nunca deve ler None como "zero usuários")."""
    if not _admin_autorizado(email_admin):
        return None
    cliente = cliente if cliente is not None else obter_cliente()
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


def diagnosticar_usuarios_admin(email_admin: str, cliente=None) -> dict:
    """Causa REAL de obter_usuarios_admin ter voltado None - achado real
    (2026-10-19): a UI (ui/usuarios_tab.py) mostrava sempre a mesma
    mensagem genérica "Supabase indisponível" pra qualquer motivo de
    falha, inclusive os que NÃO são o Supabase estar fora do ar (ex:
    `created_at`/`last_seen_at` são colunas adicionadas em
    sql/schema.sql - "alter table ... add column if not exists" -
    nunca aplicadas automaticamente; se ninguém rodou essa migração no
    banco de produção, o SELECT falha com "column does not exist", um
    erro real do Postgres/PostgREST que fica indistinguível de
    "Supabase caiu" pra quem olha só a mensagem genérica). Não repete a
    consulta inteira - um SELECT mínimo (1 linha) já expõe o mesmo erro
    de schema/RLS que a consulta paginada completa encontraria.

    Retorna {"ok": bool, "etapa": str, "detalhe": str}. etapa in
    ("NAO_ADMIN", "SEM_CREDENCIAL", "CONSULTA"). Nunca lança exceção -
    é só diagnóstico, não deve derrubar a página por conta própria."""
    if not _admin_autorizado(email_admin):
        return {"ok": False, "etapa": "NAO_ADMIN", "detalhe": "e-mail fora da lista de administradores"}
    cliente = cliente if cliente is not None else obter_cliente()
    if cliente is None:
        return {"ok": False, "etapa": "SEM_CREDENCIAL",
                "detalhe": "obter_cliente() retornou None - SUPABASE_URL/SUPABASE_SECRET_KEY ausentes ou chave pública"}
    try:
        cliente.table("user_prefs").select("sub,email,preferencias,created_at,last_seen_at").limit(1).execute()
    except Exception as exc:
        return {"ok": False, "etapa": "CONSULTA", "detalhe": repr(exc)}
    return {"ok": True, "etapa": "", "detalhe": ""}
