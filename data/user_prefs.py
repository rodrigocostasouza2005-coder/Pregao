# -*- coding: utf-8 -*-
"""Preferencias do usuario, persistidas no Supabase (tabela user_prefs)."""

import re

from config import PREFS_PADRAO
from data.supabase_client import obter_cliente

_RE_EMAIL_VALIDO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TAMANHO_PAGINA_ASSINANTES = 500


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


def email_valido(email: str) -> bool:
    """Validacao simples (formato "algo@algo.algo") - suficiente pra
    filtrar lixo/string vazia antes de tentar enviar; o provedor de
    e-mail (Resend) e' a fonte de verdade final sobre entregabilidade."""
    return bool(_RE_EMAIL_VALIDO.match((email or "").strip()))


def listar_assinantes_morning_call(cliente=None) -> list[str]:
    """E-mails (minusculos, deduplicados) de usuarios com a preferencia
    'morning_call_email_ativo'=True em user_prefs E e-mail em formato
    valido - usado por jobs/morning_call.py pra decidir quem recebe o
    envio automatico (NUNCA usado pelo envio administrativo/teste, que
    usa um destinatario fixo passado explicitamente).

    Pagina a leitura (range) em blocos de ate'
    _TAMANHO_PAGINA_ASSINANTES linhas - continua funcionando mesmo se a
    tabela user_prefs crescer bem alem de uma unica pagina default do
    PostgREST. cliente=None (chamador pode passar um cliente ja' obtido
    pra nao abrir 2 conexoes) -> obtem um sozinho; Supabase indisponivel
    ou qualquer falha na consulta -> [] (nunca inventa assinante, nunca
    quebra o job - mesmo espirito de obter_prefs/salvar_prefs acima)."""
    cliente = cliente if cliente is not None else obter_cliente()
    if cliente is None:
        return []
    assinantes = {}
    try:
        inicio = 0
        while True:
            fim = inicio + _TAMANHO_PAGINA_ASSINANTES - 1
            resp = (
                cliente.table("user_prefs")
                .select("email,preferencias")
                .range(inicio, fim)
                .execute()
            )
            linhas = resp.data or []
            for linha in linhas:
                preferencias_usuario = linha.get("preferencias") or {}
                if not preferencias_usuario.get("morning_call_email_ativo"):
                    continue
                email = (linha.get("email") or "").strip().lower()
                if not email_valido(email):
                    continue
                assinantes[email] = True
            if len(linhas) < _TAMANHO_PAGINA_ASSINANTES:
                break
            inicio += _TAMANHO_PAGINA_ASSINANTES
    except Exception as exc:
        print(f"[user_prefs] falha ao listar assinantes do Morning Call: {exc!r}")
        return []
    return sorted(assinantes.keys())
