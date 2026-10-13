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
    except Exception as e:
        # log (nunca excecao pro chamador) - visivel no log do Streamlit
        # Cloud ("Manage app"); achado real 2026-10-13: sem isto, uma
        # tabela ausente (mesma classe de bug do PGRST205 ja confirmado em
        # eventos_resultados, 4c17876) fica 100% invisivel - o painel so'
        # mostra NUNCA_EXECUTADO, indistinguivel de "coletor nunca rodou".
        print(f"[coletores_status] registrar_tentativa({nome!r}) falhou: {e!r}")
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
    except Exception as e:
        print(f"[coletores_status] obter_status({nome!r}) falhou: {e!r}")
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
    except Exception as e:
        print(f"[coletores_status] obter_todos_status() falhou: {e!r}")
        return {}


def tabela_disponivel() -> bool | None:
    """Diagnostico (mesmo padrao de data/eventos_coleta.py:
    tabela_eventos_disponivel, achado real 2026-10-05: a tabela
    eventos_resultados nao existia em producao porque sql/eventos.sql
    nunca tinha sido rodado la' - PGRST205 'Could not find the table' -
    e tanto a leitura quanto a escrita degradavam em silencio pro mesmo
    'nada encontrado', escondendo o problema). Aplicado aqui porque a
    missao de 2026-10-13 encontrou TODOS os coletores instrumentados
    (sem fallback hibrido) mostrando NUNCA_EXECUTADO simultaneamente em
    producao - o padrao classico de 'tabela coletores_status tambem
    nunca migrada', nao de coletores quebrados individualmente.

    True se a tabela responde a uma consulta trivial, False se existir
    cliente Supabase mas a consulta falhar (tabela/schema ausente, RLS
    bloqueando, coluna renomeada etc - qualquer erro aqui JA significa
    que registrar_tentativa/obter_status tambem falham, pelo mesmo
    motivo), None se o Supabase em si estiver fora do ar
    (obter_cliente()=None, indistinguivel de 'sem credencial'). So' pra
    diagnostico/UI (ver ui/saude_dados_tab.py) - nunca usada pelos
    coletores em si, que continuam degradando com seguranca
    independente disso."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        cliente.table(_TABELA).select("nome").limit(1).execute()
        return True
    except Exception:
        return False
