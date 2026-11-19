# -*- coding: utf-8 -*-
"""Testes de data/agendamentos_saude.py - saúde de EXECUÇÃO dos 3
workflows agendados (Morning Call, Radar de Quedas, Comitê Noturno).
Mocka as duas fontes de leitura já existentes (coletores_status.
obter_status e execucoes_agendadas.listar_ultimas_execucoes) - nenhuma
chamada de rede, nenhum teste de verdade no Supabase.

Uso: python tests/test_agendamentos_saude.py (python do .venv do
projeto) ou pytest tests/test_agendamentos_saude.py."""
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.agendamentos_saude as ag

TZ_SP = ZoneInfo("America/Sao_Paulo")

# 2026-11-13 é sexta-feira; 2026-11-14 é sábado (ver contexto da missão).
_SEXTA = lambda h, m=0: datetime(2026, 11, 13, h, m, tzinfo=TZ_SP)
_SABADO = lambda h, m=0: datetime(2026, 11, 14, h, m, tzinfo=TZ_SP)


def _status_cs(**kwargs):
    base = {
        "ultima_tentativa_em": None, "ultimo_sucesso_em": None,
        "ultimo_erro": None, "execucao_ok": None,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------- MORNING CALL

def test_morning_call_sem_dado_quando_supabase_indisponivel():
    with patch.object(ag.coletores_status, "obter_status", return_value=None):
        saude = ag.saude_morning_call(_SEXTA(10))
    assert saude["disponivel"] is False
    assert saude["atrasado"] is None


def test_morning_call_antes_do_horario_previsto_nao_atrasado():
    status = _status_cs()  # nenhum sucesso nunca
    with patch.object(ag.coletores_status, "obter_status", return_value=status):
        saude = ag.saude_morning_call(_SEXTA(6, 0))  # 06h00, antes das 07h30
    assert saude["disponivel"] is True
    assert saude["atrasado"] is None


def test_morning_call_fim_de_semana_nunca_atrasado():
    status = _status_cs()
    with patch.object(ag.coletores_status, "obter_status", return_value=status):
        saude = ag.saude_morning_call(_SABADO(10))
    assert saude["atrasado"] is None


def test_morning_call_atrasado_sem_sucesso_hoje_depois_do_horario():
    status = _status_cs(ultimo_sucesso_em="2026-11-12T09:30:00+00:00")  # ontem
    with patch.object(ag.coletores_status, "obter_status", return_value=status):
        saude = ag.saude_morning_call(_SEXTA(8, 0))
    assert saude["atrasado"] is True
    assert "sem edição enviada hoje" in saude["motivo_atraso"]


def test_morning_call_atrasado_depois_do_corte_de_envio():
    status = _status_cs(ultimo_sucesso_em="2026-11-12T09:30:00+00:00")
    with patch.object(ag.coletores_status, "obter_status", return_value=status):
        saude = ag.saude_morning_call(_SEXTA(18, 0))  # depois das 17h BRT
    assert saude["atrasado"] is True
    assert "corte de envio agendado" in saude["motivo_atraso"]


def test_morning_call_em_dia_quando_enviado_hoje():
    # 09:08 BRT de 13/11 = 12:08 UTC de 13/11
    status = _status_cs(ultimo_sucesso_em="2026-11-13T12:08:00+00:00")
    with patch.object(ag.coletores_status, "obter_status", return_value=status):
        saude = ag.saude_morning_call(_SEXTA(14, 0))
    assert saude["atrasado"] is False


# ---------------------------------------------------------------- RADAR

def test_radar_fora_do_horario_de_pregao_nunca_atrasado():
    status = _status_cs()
    with patch.object(ag.coletores_status, "obter_status", return_value=status):
        saude = ag.saude_radar(_SEXTA(20, 30))  # depois das 18h BRT
    assert saude["atrasado"] is None


def test_radar_sem_tentativa_no_pregao_e_atrasado():
    status = _status_cs()
    with patch.object(ag.coletores_status, "obter_status", return_value=status):
        saude = ag.saude_radar(_SEXTA(11, 0))
    assert saude["atrasado"] is True


def test_radar_gap_pequeno_nao_e_atrasado():
    # última tentativa há 10min (dentro de 10h-18h BRT)
    status = _status_cs(ultima_tentativa_em="2026-11-13T13:50:00+00:00")
    with patch.object(ag.coletores_status, "obter_status", return_value=status):
        saude = ag.saude_radar(_SEXTA(11, 0))  # 11h BRT = 14h UTC
    assert saude["atrasado"] is False


def test_radar_gap_grande_e_atrasado():
    # última tentativa há 2h, dentro da janela de pregão
    status = _status_cs(ultima_tentativa_em="2026-11-13T12:00:00+00:00")
    with patch.object(ag.coletores_status, "obter_status", return_value=status):
        saude = ag.saude_radar(_SEXTA(11, 0))  # 11h BRT = 14h UTC
    assert saude["atrasado"] is True
    assert "última tentativa há" in saude["motivo_atraso"]


# ---------------------------------------------------------------- COMITÊ NOTURNO

def test_comite_sem_dado_quando_supabase_indisponivel():
    with patch.object(ag.execucoes_agendadas, "listar_ultimas_execucoes", return_value=None):
        saude = ag.saude_comite_noturno(_SEXTA(22))
    assert saude["disponivel"] is False
    assert saude["atrasado"] is None


def test_comite_antes_do_limite_de_alerta_nao_atrasado():
    with patch.object(ag.execucoes_agendadas, "listar_ultimas_execucoes", return_value=[]):
        saude = ag.saude_comite_noturno(_SEXTA(20, 0))  # antes das 21h
    assert saude["disponivel"] is True
    assert saude["atrasado"] is None


def test_comite_atrasado_sem_rodada_hoje_depois_do_limite():
    execucoes = [{
        "tipo": "comite_noturno", "status": "OK",
        "iniciado_em": "2026-11-12T22:45:00+00:00", "concluido_em": "2026-11-12T23:10:00+00:00",
    }]
    with patch.object(ag.execucoes_agendadas, "listar_ultimas_execucoes", return_value=execucoes):
        saude = ag.saude_comite_noturno(_SEXTA(22, 0))
    assert saude["atrasado"] is True
    assert "nenhuma rodada iniciada hoje" in saude["motivo_atraso"]


def test_comite_em_dia_quando_rodou_hoje():
    # 19:47 BRT de 13/11 = 22:47 UTC de 13/11
    execucoes = [{
        "tipo": "comite_noturno", "status": "OK",
        "iniciado_em": "2026-11-13T22:47:00+00:00", "concluido_em": "2026-11-13T23:05:00+00:00",
    }]
    with patch.object(ag.execucoes_agendadas, "listar_ultimas_execucoes", return_value=execucoes):
        saude = ag.saude_comite_noturno(_SEXTA(23, 0))
    assert saude["atrasado"] is False
    assert saude["execucao_ok"] is True


def test_comite_erro_recente_fica_visivel_mesmo_em_dia():
    execucoes = [{
        "tipo": "comite_noturno", "status": "ERRO",
        "iniciado_em": "2026-11-13T22:47:00+00:00", "erro": "Supabase indisponível; execução cancelada.",
    }]
    with patch.object(ag.execucoes_agendadas, "listar_ultimas_execucoes", return_value=execucoes):
        saude = ag.saude_comite_noturno(_SEXTA(23, 0))
    assert saude["execucao_ok"] is False
    assert saude["ultimo_erro"] == "Supabase indisponível; execução cancelada."


# ---------------------------------------------------------------- AGREGADO

def test_saude_agendamentos_devolve_as_3_linhas_na_ordem():
    with patch.object(ag.coletores_status, "obter_status", return_value=None), \
         patch.object(ag.execucoes_agendadas, "listar_ultimas_execucoes", return_value=None):
        linhas = ag.saude_agendamentos(_SEXTA(10))
    assert [l["rotulo"] for l in linhas] == [
        "Morning Call", "Radar de Quedas", "Comitê de Investimentos (análise noturna)",
    ]
    assert all(l["disponivel"] is False for l in linhas)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
