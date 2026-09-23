# -*- coding: utf-8 -*-
"""Persistencia dos itens de research no Supabase (tabela research_itens,
ver sql/research.sql). So metadados do relatorio + resumo por IA com
palavras proprias sao gravados - nunca o texto completo do relatorio
original."""

from datetime import datetime, timedelta, timezone

from data.supabase_client import obter_cliente

TTL_RECOLETA_MIN = 30


def _linha_para_item(linha: dict) -> dict:
    """Converte uma linha do banco pro mesmo formato que os coletores
    (data/research/genial.py etc.) retornam, mais resumo/modelo_resumo
    quando ja tiverem sido gerados."""
    return {
        "casa": linha["casa"], "titulo": linha["titulo"], "data": linha.get("data") or "",
        "autor": linha.get("autor") or "", "tipo": linha["tipo"],
        "tickers": linha.get("tickers") or [], "link": linha["link"],
        "resumo": linha.get("resumo"), "modelo_resumo": linha.get("modelo_resumo"),
    }


def listar_itens(casas: list) -> list | None:
    """Itens salvos das casas dadas (nomes, ex: 'Genial Analisa'), mais
    recentes primeiro. None se o banco estiver fora do ar."""
    if not casas:
        return []
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (
            cliente.table("research_itens")
            .select("*")
            .in_("casa", casas)
            .order("data", desc=True)
            .execute()
        )
        return [_linha_para_item(r) for r in resp.data]
    except Exception:
        return None


def ultima_coleta_em(casa: str) -> datetime | None:
    """Timestamp da coleta mais recente salva pra uma casa. None se nao
    houver nenhum item salvo ou o banco estiver fora do ar."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (
            cliente.table("research_itens")
            .select("coletado_em")
            .eq("casa", casa)
            .order("coletado_em", desc=True)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return datetime.fromisoformat(resp.data[0]["coletado_em"])
    except Exception:
        return None


def precisa_recoletar(casa: str, minutos: int = TTL_RECOLETA_MIN) -> bool:
    """True se a casa nunca foi coletada ou a ultima coleta salva tem mais
    de `minutos`. Se o banco estiver fora do ar (ultima_coleta_em -> None
    de forma indistinguivel de 'nunca coletado'), tambem retorna True -
    quem chama decide o que fazer se a coleta/gravacao falhar de novo."""
    ultima = ultima_coleta_em(casa)
    if ultima is None:
        return True
    return (datetime.now(timezone.utc) - ultima) > timedelta(minutes=minutos)


def salvar_itens(itens: list) -> bool:
    """Upsert em lote por link. So envia as colunas de metadado (nunca
    resumo/modelo_resumo) - o upsert do PostgREST so mexe nas colunas
    presentes no payload, entao resumos ja salvos de uma coleta anterior
    nao sao apagados quando o item e' recoletado.

    Deduplica por link antes de enviar (mantem a ultima ocorrencia) - um
    upsert com o mesmo link repetido dentro do MESMO lote falha inteiro
    no Postgres ("ON CONFLICT DO UPDATE command cannot affect row a
    second time"); pode acontecer se a fonte listar o mesmo relatorio em
    mais de uma categoria (confirmado em teste com a XP)."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    if not itens:
        return True
    itens = list({it["link"]: it for it in itens}.values())
    agora = datetime.now(timezone.utc).isoformat()
    linhas = [
        {
            "link": it["link"], "casa": it["casa"], "titulo": it["titulo"],
            "data": it.get("data") or None, "autor": it.get("autor") or None,
            "tipo": it["tipo"], "tickers": it.get("tickers") or [],
            "coletado_em": agora,
        }
        for it in itens
    ]
    try:
        cliente.table("research_itens").upsert(linhas, on_conflict="link").execute()
        return True
    except Exception:
        return False


def salvar_resumo(link: str, resumo: str, modelo: str) -> bool:
    """Grava o resumo (palavras proprias, nunca o texto original) de um
    item ja existente. True se salvou."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        cliente.table("research_itens").update(
            {"resumo": resumo, "modelo_resumo": modelo}
        ).eq("link", link).execute()
        return True
    except Exception:
        return False
