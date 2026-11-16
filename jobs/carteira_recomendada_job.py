# -*- coding: utf-8 -*-
"""Job diário de persistência da CARTEIRA RECOMENDADA.

Plugado no Comitê de Investimentos noturno (jobs/comite_noturno.py), que
já roda 1x/dia (seg-sex, 19h45 BRT) via o workflow "Comitê de
Investimentos — análise noturna" (.github/workflows/comite-noturno.yml) -
reaproveita o mesmo agendamento em vez de propor um cron novo.

Fecha o ciclo "ao vivo -> persistido -> acompanhado" descrito em
data/carteira_recomendada.py, cujas funções de persistência já existem e
são testadas isoladamente, mas que nenhum caller de produção ainda
chamava (confirmado por busca no código antes desta missão):

1. Monta a carteira do momento (montar_carteira_recomendada) - a partir
   das análises REAIS já concluídas pelo Comitê na mesma rodada noturna.
   Se vier vazia/indisponível (Comitê sem análises concluídas suficientes
   OU Supabase indisponível na leitura), NADA é persistido - uma carteira
   vazia nunca é gravada como se fosse uma "saída de todos os ativos"
   real; só um log explicando por quê.
2. Lê o snapshot ANTERIOR persistido (obter_ultima_carteira_persistida)
   ANTES de sobrescrever - é a única forma de saber o que de fato mudou
   nesta rodada.
3. Persiste o snapshot novo (salvar_carteira) - upsert por ticker, nunca
   um DELETE em massa (regra do projeto).
4. Compara o snapshot anterior com o novo (calcular_revisoes, função pura
   e testável sem rede) e grava em carteira_recomendada_historico só os
   campos que de fato mudaram (peso_pct/tese/preco_alvo/criterio_saida) +
   entrada/saída de ticker - nunca um campo que ficou igual.
5. Grava o acompanhamento do dia (registrar_acompanhamento) pra cada
   ticker da carteira atual: preço de referência da recomendação (já
   conhecido, capturado pelo Comitê) x preço real de hoje
   (data/prices.py:obter_cotacao) - upsert por (ticker, data_referencia),
   já idempotente por desenho da tabela (UNIQUE) e da função: reexecutar
   no mesmo dia sobrescreve só a checagem daquele dia, nunca duplica.

Nunca derruba o resto do Comitê noturno se falhar - mesmo padrão
try/except-com-log do resto do projeto (ver jobs/comite_noturno.py):
`executar()` nunca lança, sempre devolve True/False.
"""
from datetime import datetime, timezone

from data.carteira_recomendada import (
    montar_carteira_recomendada,
    obter_ultima_carteira_persistida,
    registrar_acompanhamento,
    registrar_revisao,
    salvar_carteira,
)
from data.prices import obter_cotacao

# Campos monitorados para o histórico de revisão - mesma lista pedida pela
# missão: peso do ativo, tese, preço-alvo e critério de saída. Entrada e
# saída de ticker são tratadas separadamente (não são um "campo" do item).
_CAMPOS_MONITORADOS = ("peso_pct", "tese", "preco_alvo", "criterio_saida")
_CAMPOS_NUMERICOS = {"peso_pct", "preco_alvo"}

_MOTIVO_ATUALIZACAO = "Atualização automática da rodada diária da Carteira Recomendada (jobs/carteira_recomendada_job.py)."
_MOTIVO_ENTRADA = "Ativo incluído na carteira recomendada nesta rodada."
_MOTIVO_SAIDA = "Ativo removido da carteira recomendada nesta rodada."


def _agora_utc(agora=None):
    agora = agora or datetime.now(timezone.utc)
    if agora.tzinfo is None:
        return agora.replace(tzinfo=timezone.utc)
    return agora.astimezone(timezone.utc)


def _numeros_iguais(a, b, eps=1e-6):
    if a is None or b is None:
        return a == b
    try:
        return abs(float(a) - float(b)) < eps
    except (TypeError, ValueError):
        return a == b


def _campo_mudou(campo, valor_anterior, valor_novo):
    if campo in _CAMPOS_NUMERICOS:
        return not _numeros_iguais(valor_anterior, valor_novo)
    return valor_anterior != valor_novo


def calcular_revisoes(anterior: list | None, novo: list) -> list:
    """Diff puro (sem rede) entre o snapshot anterior persistido e o
    snapshot novo recém-montado - testável sem Supabase.

    Devolve 1 dict por mudança REAL ({"ticker", "campo", "valor_anterior",
    "valor_novo", "motivo"}), pronta pra virar 1 chamada de
    registrar_revisao - nunca inclui um campo que ficou igual (comparação
    numérica com tolerância pra peso_pct/preco_alvo, pra não gerar "mudou"
    por ruído de ponto flutuante/round-trip do Supabase).

    `anterior=None` (obter_ultima_carteira_persistida indisponível -
    Supabase fora OU tabela ainda ausente) devolve [] - sem uma baseline
    confiável não há o que comparar; nunca assume "tudo mudou" nesse caso.
    `anterior=[]` (tabela existe, mas é a 1a rodada que persiste algo)
    trata cada ticker do snapshot novo como entrada - comportamento
    esperado: é literalmente a 1a vez que esses ativos entram no
    histórico."""
    if anterior is None:
        return []

    anterior_por_ticker = {item.get("ticker"): item for item in anterior if item.get("ticker")}
    novo_por_ticker = {item.get("ticker"): item for item in novo if item.get("ticker")}

    revisoes = []
    for ticker, item_novo in novo_por_ticker.items():
        item_anterior = anterior_por_ticker.get(ticker)
        if item_anterior is None:
            revisoes.append({
                "ticker": ticker,
                "campo": "entrada_na_carteira",
                "valor_anterior": None,
                "valor_novo": {"peso_pct": item_novo.get("peso_pct"), "tese": item_novo.get("tese")},
                "motivo": _MOTIVO_ENTRADA,
            })
            continue
        for campo in _CAMPOS_MONITORADOS:
            valor_anterior = item_anterior.get(campo)
            valor_novo = item_novo.get(campo)
            if _campo_mudou(campo, valor_anterior, valor_novo):
                revisoes.append({
                    "ticker": ticker,
                    "campo": campo,
                    "valor_anterior": valor_anterior,
                    "valor_novo": valor_novo,
                    "motivo": _MOTIVO_ATUALIZACAO,
                })

    for ticker, item_anterior in anterior_por_ticker.items():
        if ticker not in novo_por_ticker:
            revisoes.append({
                "ticker": ticker,
                "campo": "saida_da_carteira",
                "valor_anterior": {"peso_pct": item_anterior.get("peso_pct")},
                "valor_novo": None,
                "motivo": _MOTIVO_SAIDA,
            })
    return revisoes


def _itens_com_preco_atual(itens: list, provedor_cotacao) -> list:
    """Preço de referência da recomendação (já conhecido, vem do item) x
    preço real de hoje (melhor esforço por ticker - cotação que falhar
    entra com preco_atual/retorno_pct=None, nunca derruba os demais, mesmo
    padrão de data/carteira_recomendada.py:_liquidez)."""
    resultado = []
    for item in itens:
        ticker = item.get("ticker")
        preco_referencia = item.get("preco_referencia")
        preco_atual = None
        try:
            cotacao = provedor_cotacao(ticker) or {}
            preco_atual = cotacao.get("preco")
        except Exception as exc:
            print(f"[carteira_recomendada_job] cotação indisponível para {ticker}: {exc!r}")
        retorno_pct = None
        if preco_referencia not in (None, 0) and preco_atual is not None:
            try:
                retorno_pct = round(
                    ((float(preco_atual) - float(preco_referencia)) / float(preco_referencia)) * 100, 2
                )
            except (TypeError, ValueError, ZeroDivisionError):
                retorno_pct = None
        resultado.append({
            "ticker": ticker,
            "peso_pct": item.get("peso_pct"),
            "preco_referencia": preco_referencia,
            "preco_atual": preco_atual,
            "retorno_pct": retorno_pct,
        })
    return resultado


def executar(agora=None) -> bool:
    """Roda 1x/dia dentro do Comitê noturno: monta -> lê o snapshot
    anterior -> persiste o snapshot novo -> grava no histórico só o que
    mudou -> grava o acompanhamento do dia. Nunca lança - qualquer falha
    (esperada ou inesperada) degrada para False + log, nunca derruba quem
    chamou (jobs/comite_noturno.py, que também envolve esta chamada em
    try/except por segurança adicional)."""
    try:
        agora = _agora_utc(agora)

        carteira = montar_carteira_recomendada(agora=agora)
        itens_novos = carteira.get("itens") or []
        if not itens_novos:
            print(
                "[carteira_recomendada_job] carteira vazia/indisponível nesta rodada "
                "(Comitê sem análises concluídas suficientes com sinal COMPRA, ou "
                "Supabase indisponível na montagem) - nada persistido nesta execução; "
                "uma carteira vazia nunca é gravada como 'saída de todos os ativos' real."
            )
            return False

        anterior = obter_ultima_carteira_persistida()

        ok_salvar = salvar_carteira(itens_novos, agora=agora)
        if not ok_salvar:
            print(
                "[carteira_recomendada_job] salvar_carteira falhou (tabela ausente ou "
                "Supabase indisponível) - histórico e acompanhamento não serão gravados "
                "nesta rodada."
            )
            return False

        revisoes = calcular_revisoes(anterior, itens_novos)
        for revisao in revisoes:
            registrar_revisao(
                revisao["ticker"], revisao["campo"],
                revisao["valor_anterior"], revisao["valor_novo"],
                revisao["motivo"], agora=agora,
            )
        print(
            f"[carteira_recomendada_job] {len(revisoes)} revisão(ões) de campo registrada(s) "
            f"no histórico nesta rodada (ativos na carteira: {len(itens_novos)})."
        )

        itens_acompanhamento = _itens_com_preco_atual(itens_novos, obter_cotacao)
        ok_acompanhamento = registrar_acompanhamento(agora.date(), itens_acompanhamento)
        if not ok_acompanhamento:
            print(
                "[carteira_recomendada_job] registrar_acompanhamento falhou (tabela ausente "
                "ou Supabase indisponível) - comparação calculada mas não persistida."
            )
            return False

        print(
            f"[carteira_recomendada_job] ok - {len(itens_novos)} ativo(s) persistido(s), "
            f"{len(revisoes)} revisão(ões) de histórico, acompanhamento de "
            f"{agora.date().isoformat()} gravado."
        )
        return True
    except Exception as exc:
        print(f"[carteira_recomendada_job] falhou de forma inesperada (não derruba o Comitê): {exc!r}")
        return False


if __name__ == "__main__":
    executar()
