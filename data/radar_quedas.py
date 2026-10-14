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
from data.research.genial_carteiras import coletar_carteiras
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
    """Coleta somente carteiras mensais oficiais e validadas da Genial."""
    return coletar_carteiras()

