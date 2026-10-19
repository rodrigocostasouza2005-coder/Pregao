# -*- coding: utf-8 -*-
"""Leitura (somente leitura) das edicoes ja' publicadas do Morning Call,
a partir do log que o proprio job grava (jobs/morning_call.py:executar ->
tabela morning_call_execucoes, sql/radar_research.sql). Nenhuma escrita,
nenhuma geracao nova: e' o mesmo texto que foi enviado por e-mail.

`destinatario` existe na tabela mas NUNCA e' selecionado aqui - a tela
de historico e' de todos os usuarios, e quem recebeu o e-mail nao e'
informacao deles. O texto (conteudo) e' identico pra todo assinante da
mesma execucao (montado 1x por execucao)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from data.supabase_client import obter_cliente

TZ_SP = ZoneInfo("America/Sao_Paulo")
_LIMITE_LINHAS = 500


def agrupar_por_dia(linhas: list) -> list:
    """Uma edicao por dia (fuso de Brasilia), mais recente primeiro.
    Texto = o da ultima execucao do dia que tem conteudo; status =
    ENVIADA se pelo menos 1 envio deu certo, senao o status da ultima
    tentativa (ex: FALHA_ENVIO) - nunca promove falha a sucesso."""
    por_dia = {}
    for linha in linhas or []:
        bruto = linha.get("executado_em")
        if not bruto:
            continue
        try:
            quando = datetime.fromisoformat(str(bruto).replace("Z", "+00:00")).astimezone(TZ_SP)
        except ValueError:
            continue
        por_dia.setdefault(quando.date(), []).append((quando, linha.get("status"), linha.get("conteudo")))
    edicoes = []
    for dia, tentativas in por_dia.items():
        tentativas.sort(key=lambda t: t[0], reverse=True)
        com_texto = next((t for t in tentativas if t[2]), None)
        enviada = any(t[1] == "ENVIADO" for t in tentativas)
        edicoes.append({
            "data": dia,
            "executado_em": (com_texto or tentativas[0])[0],
            "conteudo": com_texto[2] if com_texto else None,
            "status": "ENVIADA" if enviada else (tentativas[0][1] or "DESCONHECIDO"),
        })
    return sorted(edicoes, key=lambda e: e["data"], reverse=True)


@st.cache_data(ttl=300, show_spinner=False)
def listar_edicoes() -> list | None:
    """Edicoes publicadas (mais recente primeiro); None = banco
    indisponivel (diferente de [] = nenhuma edicao registrada)."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (
            cliente.table("morning_call_execucoes")
            .select("executado_em,status,conteudo")
            .order("executado_em", desc=True)
            .limit(_LIMITE_LINHAS)
            .execute()
        )
    except Exception:
        return None
    return agrupar_por_dia(resp.data or [])
