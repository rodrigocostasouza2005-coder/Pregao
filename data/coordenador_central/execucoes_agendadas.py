# -*- coding: utf-8 -*-
"""Leitura de `coordenador_execucoes` (sql/coordenador.sql) - log do
SCHEDULER puro via cron (jobs/coordenador.py,
.github/workflows/coletores-nuvem.yml), escrita lá, só lida aqui.

NÃO confundir com coordenador_analises / coordenador_especialistas_execucoes
(essas são data/coordenador_central/persistencia.py, orquestração SOB
DEMANDA disparada pela UI - formato incompatível, ver docstring de
persistencia.py: "nunca reaproveitando coordenador_execucoes"). Este
módulo é só leitura: o único escritor de coordenador_execucoes é
jobs/coordenador.py.

Mesmo padrão de web/lib/server/dominio/backoffice.ts:ultimasExecucoes()
(já em produção no painel "Status dos especialistas" da versão web, ver
web/app/(terminal)/inteligencia/page.tsx) - aqui é o equivalente em
Python/Streamlit, que até 2026-11-05 não tinha nenhum.

Mesmo padrão try/except do resto do projeto: nunca lança; None é
distinto de [] (Supabase indisponível vs. tabela ainda sem nenhuma
linha - ver ui/coordenador_tab.py)."""

from data.supabase_client import obter_cliente

_TABELA = "coordenador_execucoes"

# Mesmos rótulos de web/app/(terminal)/inteligencia/page.tsx:rotinasAgendadas
# (consistência entre as duas superfícies) - usado só pela UI pra
# nomear cada `tipo`, nunca pra filtrar/validar o que vem do Supabase.
ROTULOS_TIPO = {
    "backoffice": "Backoffice (achados)",
    "sintese": "Síntese (IA)",
    "radar_x": "Radar X (sinais sociais)",
    "embeddings": "Memória de Research (embeddings)",
    "comite_noturno": "Comitê de Investimentos (análise noturna)",
}


def listar_ultimas_execucoes(limite: int = 50) -> list | None:
    """Última linha de cada `tipo` em coordenador_execucoes, ordenada
    por iniciado_em desc (o tipo com a rodada mais recente aparece
    primeiro) - mesma lógica do lado web, só em Python.

    None se o Supabase estiver indisponível; [] se a tabela existir mas
    ainda não tiver nenhuma linha. `limite` só limita quantas linhas
    BRUTAS são lidas antes de reduzir por tipo (não é o número de tipos
    devolvidos) - 50 é suficiente pros ~5 tipos conhecidos hoje mesmo
    com rodadas frequentes."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (
            cliente.table(_TABELA).select("*")
            .order("iniciado_em", desc=True).limit(limite).execute()
        )
        linhas = resp.data or []
    except Exception as exc:
        print(f"[coordenador_central] listar_ultimas_execucoes falhou: {exc!r}")
        return None

    por_tipo: dict[str, dict] = {}
    for linha in linhas:
        tipo = linha.get("tipo")
        if not tipo or tipo in por_tipo:
            continue
        por_tipo[tipo] = linha
    return list(por_tipo.values())
