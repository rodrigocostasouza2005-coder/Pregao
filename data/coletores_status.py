# -*- coding: utf-8 -*-
"""Registro de TENTATIVAS de coleta (tabela coletores_status) - metadado
de execucao (quando tentou, deu certo, persistiu, quantos registros
novos, erro), separado do DADO coletado em si (que cada modulo guarda
na sua propria tabela). Existe pra sustentar a aba SAUDE DOS DADOS
(ui/saude_dados_tab.py) sem inventar status: hoje nenhum coletor
registra isso (ver BACKLOG.md/PROGRESSO.md, auditoria 2026-10-09) - os
coletores que chamam `registrar_tentativa` abaixo passam a ter
historico real; os que ainda nao chamam ficam como NAO_COMPROVADO/
derivado-so-do-ultimo-dado-persistido em data/saude_dados.py, nunca
como "verde" fabricado."""

from datetime import datetime, timezone

from data.supabase_client import obter_cliente

_TABELA = "coletores_status"


def registrar_tentativa(
    nome: str,
    fonte: str,
    execucao_ok: bool,
    persistencia_ok: bool = True,
    registros_novos: int = 0,
    erro: str = None,
    categoria: str = "",
    parcial: bool = False,
) -> bool:
    """Grava o resultado de UMA tentativa de coleta (upsert por `nome`).
    `ultimo_sucesso_em` so' avanca quando execucao_ok E persistencia_ok -
    uma falha pontual nunca apaga o ultimo sucesso real, so deixa de
    atualiza-lo (mesmo espirito de salvar_snapshot_calendario). Nunca
    lanca excecao - banco fora do ar/lib ausente degrada pra False, quem
    chama (o proprio coletor) nunca deve travar por causa disso."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        agora = datetime.now(timezone.utc).isoformat()
        sucesso_agora = bool(execucao_ok and persistencia_ok)
        ultimo_sucesso_em = agora if sucesso_agora else None
        if not sucesso_agora:
            existente = (
                cliente.table(_TABELA)
                .select("ultimo_sucesso_em")
                .eq("nome", nome)
                .limit(1)
                .execute()
            )
            if existente.data:
                ultimo_sucesso_em = existente.data[0].get("ultimo_sucesso_em")
        cliente.table(_TABELA).upsert({
            "nome": nome,
            "fonte": fonte,
            "categoria": categoria,
            "execucao_ok": bool(execucao_ok),
            "persistencia_ok": bool(persistencia_ok),
            "parcial": bool(parcial),
            "registros_novos": int(registros_novos) if sucesso_agora else 0,
            "ultimo_erro": None if sucesso_agora else (erro or "erro nao especificado"),
            "ultima_tentativa_em": agora,
            "ultimo_sucesso_em": ultimo_sucesso_em,
        }).execute()
        return True
    except Exception:
        return False


def obter_status(nome: str) -> dict | None:
    """Ultima tentativa registrada pra um coletor. None se nunca
    registrou ou o banco estiver fora do ar - indistinguivel de
    propósito (quem chama trata os dois casos como NAO_COMPROVADO)."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = cliente.table(_TABELA).select("*").eq("nome", nome).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def obter_todos_status() -> dict:
    """Todas as tentativas registradas, indexadas por nome. {} se o
    banco estiver fora do ar (nunca lanca excecao)."""
    cliente = obter_cliente()
    if cliente is None:
        return {}
    try:
        resp = cliente.table(_TABELA).select("*").execute()
        return {linha["nome"]: linha for linha in (resp.data or [])}
    except Exception:
        return {}
