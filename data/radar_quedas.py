# -*- coding: utf-8 -*-
"""Radar persistente de quedas em carteiras recomendadas.

Fonte estruturada habilitada nesta primeira versão: recomendações públicas
estruturadas da Genial. Outras casas só entram quando houver coletor de
carteiras públicas acessível e dados de validade confiáveis.
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from data.prices import obter_cotacao
from data.research import genial
from data.supabase_client import obter_cliente

TZ_SP = ZoneInfo("America/Sao_Paulo")
LIMIAR_VARIACAO = -4.0
CASA_GENIAL = "Genial Analisa"


def calcular_queda(preco_atual, fechamento_anterior):
    """Retorna variação percentual válida; None para valores inválidos."""
    try:
        atual, anterior = float(preco_atual), float(fechamento_anterior)
    except (TypeError, ValueError):
        return None
    if atual <= 0 or anterior <= 0:
        return None
    variacao = round((atual / anterior - 1) * 100, 8)
    return variacao if variacao == variacao and abs(variacao) != float("inf") else None


def deve_alertar(variacao_pct):
    """Regra estrita: -4,00% não alerta; -4,01% alerta."""
    try:
        return float(variacao_pct) < LIMIAR_VARIACAO
    except (TypeError, ValueError):
        return False


def normalizar_ticker(valor):
    ticker = str(valor or "").strip().upper()
    return ticker if ticker and len(ticker) <= 12 else ""


def coletar_carteiras_genial():
    """Snapshot das recomendações estruturadas que a Genial publica.

    A fonte pode estar bloqueada no ambiente de nuvem; None significa falha/
    indisponibilidade, nunca uma carteira vazia confirmada.
    """
    itens = genial.obter_recomendacoes()
    if itens is None:
        return None
    agora = datetime.now(timezone.utc).isoformat()
    saida = []
    for item in itens:
        ticker = normalizar_ticker(item.get("ticker"))
        if not ticker:
            continue
        saida.append({
            "casa": CASA_GENIAL,
            "carteira": str(item.get("setor") or "Recomendações Genial"),
            "ticker": ticker,
            "empresa": str(item.get("empresa") or ""),
            "recomendacao": str(item.get("recomendacao") or ""),
            "preco_alvo": item.get("preco_alvo"),
            "data_publicacao": item.get("data") or None,
            "validade_ate": None,
            "fonte_url": str(item.get("link") or "https://analisa.genialinvestimentos.com.br/"),
            "verificado_em": agora,
            "status_coleta": "COLETADO",
        })
    return saida


def salvar_carteiras(itens):
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        if itens:
            cliente.table("radar_carteiras_recomendadas").upsert(
                itens, on_conflict="casa,ticker,carteira"
            ).execute()
        cliente.table("radar_carteiras_recomendadas").update(
            {"vigente": False}
        ).eq("casa", CASA_GENIAL).execute()
        chaves = {(i["ticker"], i["carteira"]) for i in itens}
        # Reativa somente as recomendações confirmadas nesta coleta.
        for ticker, carteira in chaves:
            cliente.table("radar_carteiras_recomendadas").update(
                {"vigente": True, "verificado_em": datetime.now(timezone.utc).isoformat(),
                 "status_coleta": "COLETADO"}
            ).eq("casa", CASA_GENIAL).eq("ticker", ticker).eq("carteira", carteira).execute()
        return True
    except Exception as exc:
        print(f"[radar_quedas] falha ao persistir carteiras: {exc!r}")
        return False


def listar_carteiras():
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (cliente.table("radar_carteiras_recomendadas").select("*")
                .eq("vigente", True).order("casa").execute())
        return resp.data or []
    except Exception as exc:
        print(f"[radar_quedas] falha ao ler carteiras: {exc!r}")
        return None


def avaliar_ticker(ticker, cotacao, recomendacoes, agora=None):
    """Gera um evento candidato se preço e fechamento anterior forem válidos."""
    agora = agora or datetime.now(TZ_SP)
    if not isinstance(cotacao, dict) or cotacao.get("erro"):
        return None
    preco = cotacao.get("preco")
    anterior = cotacao.get("fechamento_anterior")
    if anterior is None:
        # O provedor existente expõe previousClose internamente, mas o retorno
        # padrão não o publica. Não substituímos por preço estimado.
        return None
    variacao = calcular_queda(preco, anterior)
    if variacao is None or not deve_alertar(variacao):
        return None
    relacionados = [r for r in recomendacoes if normalizar_ticker(r.get("ticker")) == ticker]
    if not relacionados:
        return None
    return {
        "ticker": ticker, "empresa": next((r.get("empresa") for r in relacionados if r.get("empresa")), ""),
        "preco_atual": float(preco), "fechamento_anterior": float(anterior),
        "variacao_pct": variacao, "cotacao_em": cotacao.get("_coletado_em") or agora.isoformat(),
        "tipo_cotacao": cotacao.get("tipo_cotacao") or "ATRASADA/PROVEDOR GRATUITO",
        "pregao": agora.date().isoformat(),
        "casas": sorted({r.get("casa", "") for r in relacionados if r.get("casa")}),
        "carteiras": sorted({r.get("carteira", "") for r in relacionados if r.get("carteira")}),
        "fontes": sorted({r.get("fonte_url", "") for r in relacionados if r.get("fonte_url")}),
        "status": "PENDENTE_ENVIO",
    }


def registrar_alerta(alerta):
    """Idempotência no banco por ticker + pregão; não duplica entre carteiras."""
    cliente = obter_cliente()
    if cliente is None:
        return False, None
    try:
        existente = (cliente.table("radar_alertas_queda").select("id")
                     .eq("ticker", alerta["ticker"]).eq("pregao", alerta["pregao"])
                     .limit(1).execute())
        if existente.data:
            return True, None
        resp = cliente.table("radar_alertas_queda").insert(alerta).execute()
        return bool(resp.data), (resp.data[0].get("id") if resp.data else None)
    except Exception as exc:
        print(f"[radar_quedas] falha ao registrar alerta: {exc!r}")
        return False, None


def processar_monitoramento():
    """Atualiza fontes e avalia as recomendações ativas. Envio fica no worker."""
    snapshot = coletar_carteiras_genial()
    coleta_ok = snapshot is not None
    if not coleta_ok:
        return {"coleta_ok": False, "alertas_novos": [], "erro": "Fonte de recomendações indisponível; monitoramento suspenso para evitar usar carteiras desatualizadas."}
    # Uma resposta vazia pode indicar mudança no HTML/API ou coleta parcial.
    # Não desativar a última carteira válida até confirmar que a fonte entregou
    # uma composição real; isso evita transformar falha de parsing em "zero ativos".
    if not snapshot:
        return {"coleta_ok": False, "alertas_novos": [], "erro": "A fonte retornou zero recomendações; snapshot rejeitado e carteiras anteriores preservadas."}
    if not salvar_carteiras(snapshot):
        return {"coleta_ok": False, "alertas_novos": [], "erro": "Falha ao persistir a coleta; monitoramento suspenso para evitar usar recomendações desatualizadas."}
    recomendacoes = listar_carteiras()
    if recomendacoes is None:
        return {"coleta_ok": coleta_ok, "alertas_novos": [], "erro": "Supabase indisponível"}
    tickers = sorted({normalizar_ticker(r.get("ticker")) for r in recomendacoes} - {""})
    novos = []
    for ticker in tickers:
        cotacao = obter_cotacao(ticker)
        alerta = avaliar_ticker(ticker, cotacao, recomendacoes)
        if alerta:
            ok, alerta_id = registrar_alerta(alerta)
            if ok and alerta_id is not None:
                alerta["id"] = alerta_id
                novos.append(alerta)
    return {"coleta_ok": coleta_ok, "alertas_novos": novos, "total_tickers": len(tickers)}


@st.cache_data(ttl=60, show_spinner=False)
def alertas_recentes(limite=100):
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (cliente.table("radar_alertas_queda").select("*")
                .order("alertado_em", desc=True).limit(int(limite)).execute())
        return resp.data or []
    except Exception:
        return None
