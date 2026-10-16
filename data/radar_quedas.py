# -*- coding: utf-8 -*-
"""Radar persistente de quedas em carteiras recomendadas.

Fontes estruturadas habilitadas: recomendações públicas da Genial Analisa
e a carteira mensal pública "Top 10 Ações" da Safra Corretora (2026-10-16
- ver data/research/safra_carteiras.py pra evidência real de que essa
fonte é acessível, diferente de Genial/XP/BTG, bloqueadas na borda
Akamai mesmo fora do sandbox). Cada casa é tratada de forma INDEPENDENTE
em processar_monitoramento(): uma fonte bloqueada nunca invalida nem
desativa as recomendações vigentes de outra fonte que respondeu
normalmente. Outras casas só entram quando houver coletor de carteiras
públicas acessível e dados de validade confiáveis.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from data.prices import obter_cotacao
from data.research.genial_carteiras import coletar_carteiras as _coletar_genial
from data.research.safra_carteiras import coletar_carteiras as _coletar_safra
from data.supabase_client import obter_cliente

TZ_SP = ZoneInfo("America/Sao_Paulo")
LIMIAR_VARIACAO = -4.0
# Carteiras aqui sao produtos MENSAIS (Genial/Safra) - uma linha "vigente"
# cuja ultima confirmacao real (verificado_em) passou desse limite quer
# dizer que a fonte ficou fora do ar por tempo demais pra continuar
# confiando nela como "carteira atual" (ver listar_carteiras). Folga de
# ~10 dias alem do ciclo mensal de 30/31 dias pra nao expirar por um
# fim de semana prolongado ou alguns dias de bloqueio pontual da fonte.
IDADE_MAXIMA_CARTEIRA_DIAS = 40
CASA_GENIAL = "Genial Analisa"
CASA_SAFRA = "Safra Corretora"


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
    return _coletar_genial()


def coletar_carteiras_safra():
    """Coleta a carteira mensal pública "Top 10 Ações" da Safra Corretora."""
    return _coletar_safra()


def salvar_carteiras(casa, itens):
    """Upsert + reativação ESCOPADOS a uma única casa - uma falha ou
    ausência de outra casa nunca desativa as recomendações vigentes
    desta (ver processar_monitoramento, que chama isto por fonte)."""
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
        ).eq("casa", casa).execute()
        chaves = {(i["ticker"], i["carteira"]) for i in itens}
        # Reativa somente as recomendações confirmadas nesta coleta.
        for ticker, carteira in chaves:
            cliente.table("radar_carteiras_recomendadas").update(
                {"vigente": True, "verificado_em": datetime.now(timezone.utc).isoformat(),
                 "status_coleta": "COLETADO"}
            ).eq("casa", casa).eq("ticker", ticker).eq("carteira", carteira).execute()
        return True
    except Exception as exc:
        print(f"[radar_quedas] falha ao persistir carteiras ({casa}): {exc!r}")
        return False


def _carteira_expirada(linha, agora=None):
    """True se `verificado_em` da linha passou de IDADE_MAXIMA_CARTEIRA_DIAS
    - a fonte confirmou essa recomendação pela última vez há tempo demais
    pra continuar tratando como carteira atual (ver constante acima).
    Campo ausente/malformado -> False (fail open, mesmo espírito do resto
    do projeto: nunca trava por um dado opcional malformado)."""
    agora = agora or datetime.now(timezone.utc)
    verificado = linha.get("verificado_em")
    if not verificado:
        return False
    try:
        quando = datetime.fromisoformat(str(verificado).replace("Z", "+00:00"))
    except ValueError:
        return False
    return (agora - quando) > timedelta(days=IDADE_MAXIMA_CARTEIRA_DIAS)


def listar_carteiras():
    """Recomendações vigentes (todas as casas), excluindo as EXPIRADAS
    (ver _carteira_expirada) - uma carteira mensal cuja fonte parou de
    confirmar há tempo demais não é apresentada como atual, mesmo que a
    flag `vigente` no banco ainda esteja True (ela só vira False quando a
    PRÓPRIA fonte confirma uma mudança - ver salvar_carteiras)."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (cliente.table("radar_carteiras_recomendadas").select("*")
                .eq("vigente", True).order("casa").execute())
        linhas = resp.data or []
    except Exception as exc:
        print(f"[radar_quedas] falha ao ler carteiras: {exc!r}")
        return None
    agora = datetime.now(timezone.utc)
    return [linha for linha in linhas if not _carteira_expirada(linha, agora)]


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
        "variacao_pct": variacao, "cotacao_em": cotacao.get("cotacao_em") or agora.isoformat(),
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
    """Atualiza cada fonte de carteira de forma INDEPENDENTE e avalia as
    recomendações vigentes resultantes. Envio fica no worker.

    coleta_ok=True se PELO MENOS UMA fonte persistiu uma composição
    válida nesta execução (ver `status_fontes` no retorno pro detalhe por
    casa) - uma fonte bloqueada/vazia/com falha de persistência NUNCA
    impede a avaliação das recomendações de outra fonte que respondeu
    normalmente, nem desativa as recomendações vigentes da própria fonte
    que falhou agora (permanecem vigentes até ELA MESMA confirmar uma
    mudança real numa execução futura - mesmo motivo de salvar_carteiras
    só desativar/reativar pela própria casa). Só retorna coleta_ok=False
    (monitoramento totalmente suspenso) quando TODAS as fontes
    configuradas falharem/forem rejeitadas nesta execução."""
    status_fontes = {}
    pelo_menos_uma_ok = False
    for casa, coletor in ((CASA_GENIAL, coletar_carteiras_genial), (CASA_SAFRA, coletar_carteiras_safra)):
        snapshot = coletor()
        if snapshot is None:
            status_fontes[casa] = "fonte indisponível"
            continue
        # Uma resposta vazia pode indicar mudança no HTML/PDF ou coleta
        # parcial. Não desativa a última carteira válida DESTA casa até
        # confirmar que a fonte entregou uma composição real; isso evita
        # transformar falha de parsing em "zero ativos".
        if not snapshot:
            status_fontes[casa] = "snapshot vazio, rejeitado (carteira anterior preservada)"
            continue
        if not salvar_carteiras(casa, snapshot):
            status_fontes[casa] = "falha ao persistir (carteira anterior preservada)"
            continue
        status_fontes[casa] = f"ok ({len(snapshot)} recomendações)"
        pelo_menos_uma_ok = True

    resumo_fontes = "; ".join(f"{casa}: {status}" for casa, status in status_fontes.items())
    if not pelo_menos_uma_ok:
        return {
            "coleta_ok": False, "alertas_novos": [],
            "erro": f"Todas as fontes de recomendações indisponíveis ou rejeitadas nesta execução. {resumo_fontes}",
            "fontes": status_fontes,
        }
    recomendacoes = listar_carteiras()
    if recomendacoes is None:
        return {"coleta_ok": True, "alertas_novos": [], "erro": f"Supabase indisponível para leitura. {resumo_fontes}", "fontes": status_fontes}
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
    parcial = any(not status.startswith("ok") for status in status_fontes.values())
    return {
        "coleta_ok": True, "alertas_novos": novos, "total_tickers": len(tickers),
        "fontes": status_fontes,
        "erro": (f"Execução parcial: {resumo_fontes}" if parcial else None),
    }


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
