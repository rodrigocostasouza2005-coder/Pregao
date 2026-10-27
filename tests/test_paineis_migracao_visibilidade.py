# -*- coding: utf-8 -*-
"""Cobre o bug real (PR #182, 2026-10-27): paineis novos adicionados ao
REGISTRO_PAINEIS de uma aba ficavam ocultos pra sempre pra quem ja tinha
uma lista de paineis_visiveis salva pra essa aba (lista salva = "mundo
fechado" em ui/paineis.py:_pid_visivel_salvo)."""

from ui.paineis import migrar_visibilidade_paineis_novos

NOVOS_MERCADO = ["metricas_principais", "grafico_ibov", "leitura_rapida", "noticias_resumo"]


def test_usuario_sem_customizacao_nao_precisa_migrar():
    # paineis_visiveis['MERCADO'] nunca foi salvo (None) = tudo visivel
    # por padrao ja, sem precisar de migracao nenhuma.
    prefs = {"paineis_visiveis": {}}
    mudou = migrar_visibilidade_paineis_novos("MERCADO", NOVOS_MERCADO, prefs)
    assert mudou is False
    assert prefs["paineis_visiveis"] == {}


def test_usuario_que_escondeu_painel_antigo_ganha_os_novos():
    # ja escondeu "mapa do mercado" (treemap) antes do PR #182 - lista
    # salva so tinha os paineis antigos.
    prefs = {"paineis_visiveis": {"MERCADO": ["altas_baixas", "mais_negociados", "setorial", "globais"]}}
    mudou = migrar_visibilidade_paineis_novos("MERCADO", NOVOS_MERCADO, prefs)
    assert mudou is True
    visiveis = prefs["paineis_visiveis"]["MERCADO"]
    for pid in NOVOS_MERCADO:
        assert pid in visiveis
    # painel antigo escondido de proposito continua fora (nunca reaparece)
    assert "treemap" not in visiveis


def test_nao_duplica_se_rodar_duas_vezes():
    prefs = {"paineis_visiveis": {"MERCADO": ["altas_baixas"]}}
    migrar_visibilidade_paineis_novos("MERCADO", NOVOS_MERCADO, prefs)
    visiveis_apos_1a = list(prefs["paineis_visiveis"]["MERCADO"])
    mudou_2a = migrar_visibilidade_paineis_novos("MERCADO", NOVOS_MERCADO, prefs)
    assert mudou_2a is False
    assert prefs["paineis_visiveis"]["MERCADO"] == visiveis_apos_1a


def test_nao_afeta_outra_aba():
    prefs = {"paineis_visiveis": {"MACRO": ["selic"]}}
    mudou = migrar_visibilidade_paineis_novos("MERCADO", NOVOS_MERCADO, prefs)
    assert mudou is False
    assert prefs["paineis_visiveis"] == {"MACRO": ["selic"]}
