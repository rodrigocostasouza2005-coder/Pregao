# -*- coding: utf-8 -*-
"""Testes de data/research/casas_status.py - combina CASAS (registro
estático) com data.saude_dados.obter_painel_saude() (status real,
categoria Research). Mocka só o painel de saúde (sem rede/Supabase)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.casas_status as casas_status_mod
from data.research import CASAS


def test_uma_linha_por_casa_cadastrada():
    with patch.object(casas_status_mod.saude_dados, "obter_painel_saude", return_value=[]):
        resultado = casas_status_mod.obter_status_casas()
    assert len(resultado) == len(CASAS)
    assert {r["nome"] for r in resultado} == {c["nome"] for c in CASAS}


def test_casa_sem_evidencia_no_painel_aparece_como_nao_comprovado():
    with patch.object(casas_status_mod.saude_dados, "obter_painel_saude", return_value=[]):
        resultado = casas_status_mod.obter_status_casas()
    for item in resultado:
        assert item["codigo_estado"] == "NAO_COMPROVADO"
        assert item["ultimo_sucesso_em"] is None


def test_casa_com_status_real_reflete_o_painel_de_saude():
    painel_fake = [{
        "nome": "Genial Analisa", "fonte": "analisa.genialinvestimentos.com.br",
        "categoria": "Research", "frequencia_esperada": "x", "instrumentado": True,
        "codigo_estado": "SUCESSO_COM_NOVIDADE", "rotulo_estado": "Coleta OK - dados novos (5)",
        "status_bruto": {"ultimo_sucesso_em": "2026-10-22T10:00:00+00:00", "registros_novos": 5},
        "alerta": False, "desconhecido": False,
    }]
    with patch.object(casas_status_mod.saude_dados, "obter_painel_saude", return_value=painel_fake):
        resultado = casas_status_mod.obter_status_casas()
    genial = next(r for r in resultado if r["nome"] == "Genial Analisa")
    assert genial["codigo_estado"] == "SUCESSO_COM_NOVIDADE"
    assert genial["ultimo_sucesso_em"] == "2026-10-22T10:00:00+00:00"
    assert genial["registros_novos_ultima_coleta"] == 5


def test_casas_bloqueadas_no_cloud_sao_identificadas():
    """Genial Analisa e XP tem tentar_coleta_automatica=False (bloqueio
    de WAF confirmado) - nunca devem aparecer como coleta automatica."""
    with patch.object(casas_status_mod.saude_dados, "obter_painel_saude", return_value=[]):
        resultado = casas_status_mod.obter_status_casas()
    por_nome = {r["nome"]: r for r in resultado}
    assert por_nome["Genial Analisa"]["coleta_automatica_cloud"] is False
    assert por_nome["XP Investimentos"]["coleta_automatica_cloud"] is False
    assert por_nome["BTG Pactual Research"]["coleta_automatica_cloud"] is True


def test_nunca_lanca_excecao_mesmo_com_painel_incompleto():
    with patch.object(casas_status_mod.saude_dados, "obter_painel_saude", return_value=[{"categoria": "Noticias", "nome": "NEWS"}]):
        resultado = casas_status_mod.obter_status_casas()
    assert len(resultado) == len(CASAS)


def test_casas_investigadas_em_20261030_registram_motivo_verificavel():
    """Agora/Ativa/Andbank/Planner foram investigadas (pedido explicito do
    Rodrigo) e nenhuma virou coletor - cada uma precisa de disponivel=False
    com motivo_indisponivel especifico (rastreabilidade: por que, nao so
    que esta indisponivel)."""
    por_id = {c["id"]: c for c in CASAS}
    esperado_substring = {
        "agora_insights": "descoberta",
        "ativa_investimentos": "borda",
        "andbank_brasil": "robots.txt",
        "planner_investimentos": "robots.txt",
    }
    for casa_id, trecho in esperado_substring.items():
        assert casa_id in por_id, f"casa {casa_id} nao encontrada em CASAS"
        casa = por_id[casa_id]
        assert casa["disponivel"] is False
        assert casa["ativa_por_padrao"] is False
        assert casa["extrator_texto"] is None
        assert casa.get("motivo_indisponivel"), f"{casa_id} sem motivo_indisponivel"
        assert trecho in casa["motivo_indisponivel"], (
            f"{casa_id}: motivo_indisponivel nao cita '{trecho}' "
            f"({casa['motivo_indisponivel']!r})"
        )
