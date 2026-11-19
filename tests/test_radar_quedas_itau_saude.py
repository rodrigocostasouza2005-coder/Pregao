# -*- coding: utf-8 -*-
"""Teste de jobs/radar_quedas.py:_registrar_tentativas_por_casa - bug
real encontrado em auditoria (2026-11-02, validação pós-merge da PR
#223): o coletor Itaú Top 5 (data/research/itau_carteiras.py) já
funciona de verdade (confirmado com execução real), mas
`_NOME_PAINEL_POR_CASA` não mapeava "Itaú Investimentos" (CASA_ITAU) -
`.get(casa)` devolvia None e o loop fazia `continue`, então o status
real do coletor NUNCA chegava a `registrar_tentativa`. O coletor ficava
permanentemente invisível na SAÚDE DOS DADOS, sem nenhum jeito de
detectar se ele parasse de funcionar. Corrigido adicionando a entrada
que faltava."""

from unittest.mock import patch

from data.radar_quedas import CASAS_MONITORADAS
from jobs import radar_quedas


def test_itau_investimentos_mapeado_no_painel():
    """Regressão direta do bug: a chave usada por data/radar_quedas.py
    (CASA_ITAU = 'Itaú Investimentos') precisa estar em
    _NOME_PAINEL_POR_CASA, senão o status dela nunca chega ao painel."""
    assert "Itaú Investimentos" in radar_quedas._NOME_PAINEL_POR_CASA
    nome_painel = radar_quedas._NOME_PAINEL_POR_CASA["Itaú Investimentos"]
    assert nome_painel in radar_quedas._FONTE_POR_CASA
    # nunca pode colidir com a casa de RESEARCH "Itaú BBA Research" nem
    # com nenhuma outra casa já registrada (mesmo motivo documentado pra
    # Genial Analisa/Safra Corretora - upsert por nome sobrescreveria)
    assert nome_painel not in ("Itaú BBA Research", "Genial Analisa", "Safra Corretora")


def test_status_do_itau_chega_a_registrar_tentativa_com_sucesso():
    chamadas = []

    def _fake_registrar(nome, fonte, **kwargs):
        chamadas.append((nome, fonte, kwargs))

    with patch.object(radar_quedas, "registrar_tentativa", side_effect=_fake_registrar):
        radar_quedas._registrar_tentativas_por_casa({"Itaú Investimentos": "ok (5 recomendações)"})

    assert len(chamadas) == 1
    nome, fonte, kwargs = chamadas[0]
    assert nome == "Itaú Investimentos (carteiras)"
    assert kwargs.get("execucao_ok") is True
    assert kwargs.get("persistencia_ok") is True
    assert kwargs.get("registros_novos") == 5


def test_status_do_itau_fonte_indisponivel_chega_como_falha():
    chamadas = []

    def _fake_registrar(nome, fonte, **kwargs):
        chamadas.append((nome, fonte, kwargs))

    with patch.object(radar_quedas, "registrar_tentativa", side_effect=_fake_registrar):
        radar_quedas._registrar_tentativas_por_casa({"Itaú Investimentos": "fonte indisponível"})

    assert len(chamadas) == 1
    nome, fonte, kwargs = chamadas[0]
    assert nome == "Itaú Investimentos (carteiras)"
    assert kwargs.get("execucao_ok") is False


def test_as_3_casas_monitoradas_tem_entrada_no_mapa_de_painel():
    """CASAS_MONITORADAS (Itaú, Safra, Genial) precisa bater 1:1 com
    _NOME_PAINEL_POR_CASA - nenhuma casa monitorada pode ficar sem
    mapeamento (mesma classe de bug que acabou de ser corrigida)."""
    for casa in CASAS_MONITORADAS:
        assert casa in radar_quedas._NOME_PAINEL_POR_CASA, f"{casa} sem entrada em _NOME_PAINEL_POR_CASA"
