# -*- coding: utf-8 -*-
"""Preferencias do usuario, persistidas no Supabase (tabela user_prefs)."""

import re
from datetime import datetime, timedelta, timezone

from config import PREFS_PADRAO
from data.supabase_client import obter_cliente

_RE_EMAIL_VALIDO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TAMANHO_PAGINA_ASSINANTES = 500

# intervalo minimo entre 2 escritas de last_seen_at pro MESMO usuario -
# evita escrever no Supabase em toda rerun/fragment/interacao irrelevante
# (ver registrar_acesso); 30min e' suficiente pra "ativo nos ultimos
# N dias" (granularidade diaria no painel admin) sem gerar 1 UPDATE por
# clique numa sessao tipica de uso do terminal.
_INTERVALO_MIN_REGISTRO_ACESSO = timedelta(minutes=30)


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


def deve_oferecer_morning_call(prefs: dict) -> bool:
    """True so' quando o usuario AINDA NAO respondeu a oferta de
    inscricao no Morning Call por e-mail (nem aceitou, nem recusou) -
    usada pelo banner de onboarding em app.py pra decidir se mostra a
    pergunta. Quem ja' aceitou (morning_call_email_ativo=True) ou ja'
    recusou explicitamente (morning_call_email_perguntado=True, ver
    config.PREFS_PADRAO) nunca ve' a oferta de novo."""
    return not (
        prefs.get("morning_call_email_ativo", False)
        or prefs.get("morning_call_email_perguntado", False)
    )


def registrar_acesso(sub: str, email: str, cliente=None) -> None:
    """Marca que `sub` acessou o Pregao agora - cria a linha em
    user_prefs se ainda nao existir (created_at = 1o acesso identificado,
    ver sql/schema.sql pro aviso sobre linhas anteriores a esta
    migracao) ou atualiza last_seen_at numa linha existente.

    Rate-limitada: so' escreve se last_seen_at for nulo ou mais antigo
    que _INTERVALO_MIN_REGISTRO_ACESSO - NAO chama isto a cada rerun do
    Streamlit (ver app.py: guarda de st.session_state que chama isto so'
    1x por sessao); esta funcao e' a segunda camada de proteção contra
    escrita excessiva (multiplas abas/sessoes do mesmo usuario no mesmo
    dia), nao a unica.

    Sem retorno de sucesso/falha de proposito: isto e' telemetria de uso
    pro painel admin, nunca deve bloquear ou avisar o usuario comum se
    falhar (Supabase indisponivel so' significa "essa visita nao conta
    pras metricas", nada mais)."""
    cliente = cliente if cliente is not None else obter_cliente()
    if cliente is None:
        return
    try:
        resp = cliente.table("user_prefs").select("last_seen_at").eq("sub", sub).limit(1).execute()
        agora = datetime.now(timezone.utc)
        linhas = resp.data or []
        if not linhas:
            try:
                # insert puro (NAO upsert): se outra requisicao criou a
                # linha entre o select acima e este insert (2 abas do
                # mesmo usuario na primeira visita), a PK (sub) rejeita
                # com conflito - cai no except e so' atualiza
                # last_seen_at, nunca sobrescreve preferencias ja
                # existentes por engano.
                cliente.table("user_prefs").insert(
                    {
                        "sub": sub,
                        "email": (email or "").lower(),
                        "preferencias": dict(PREFS_PADRAO),
                        "created_at": agora.isoformat(),
                        "last_seen_at": agora.isoformat(),
                    }
                ).execute()
            except Exception:
                cliente.table("user_prefs").update({"last_seen_at": agora.isoformat()}).eq("sub", sub).execute()
            return
        ultimo_raw = linhas[0].get("last_seen_at")
        if ultimo_raw:
            ultimo = datetime.fromisoformat(str(ultimo_raw).replace("Z", "+00:00"))
            if agora - ultimo < _INTERVALO_MIN_REGISTRO_ACESSO:
                return
        cliente.table("user_prefs").update({"last_seen_at": agora.isoformat()}).eq("sub", sub).execute()
    except Exception as exc:
        print(f"[user_prefs] falha ao registrar acesso: {exc!r}")


def email_valido(email: str) -> bool:
    """Validacao simples (formato "algo@algo.algo") - suficiente pra
    filtrar lixo/string vazia antes de tentar enviar; o provedor de
    e-mail (Resend) e' a fonte de verdade final sobre entregabilidade."""
    return bool(_RE_EMAIL_VALIDO.match((email or "").strip()))


def listar_assinantes_morning_call(cliente=None) -> list[str] | None:
    """E-mails (minusculos, deduplicados) de usuarios com a preferencia
    'morning_call_email_ativo'=True em user_prefs E e-mail em formato
    valido - usado por jobs/morning_call.py pra decidir quem recebe o
    envio automatico (NUNCA usado pelo envio administrativo/teste, que
    usa um destinatario fixo passado explicitamente).

    Pagina a leitura (range) em blocos de ate'
    _TAMANHO_PAGINA_ASSINANTES linhas - continua funcionando mesmo se a
    tabela user_prefs crescer bem alem de uma unica pagina default do
    PostgREST. cliente=None (chamador pode passar um cliente ja' obtido
    pra nao abrir 2 conexoes) -> obtem um sozinho.

    None (nao []) se Supabase estiver indisponivel ou a consulta lancar
    excecao - quem chama (jobs/morning_call.py:executar) NUNCA deve
    tratar None como "ninguem assinou": enviaria pra zero pessoas e
    reportaria sucesso quando na verdade a causa foi uma falha de
    infraestrutura. Lista [] e' o caso real "ninguem assinou ainda",
    distinto de "nao deu pra saber" - distincao trazida da comparacao
    com o PR concorrente #42 durante a consolidacao (2026-10-17)."""
    cliente = cliente if cliente is not None else obter_cliente()
    if cliente is None:
        return None
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
        return None
    return sorted(assinantes.keys())
