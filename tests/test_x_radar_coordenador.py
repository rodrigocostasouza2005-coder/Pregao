# -*- coding: utf-8 -*-
"""data/x_radar/__init__.py:executar_ciclo - ponto de entrada unico
chamado por jobs/coordenador.py (secao 7 do pedido: 'Coordenador
existente... decide se vale acionar outras rotinas'). Cobre: sem
credencial valida NUNCA tenta coletar (verificado ANTES de qualquer
rede), erro em qualquer etapa nunca escapa sem ser registrado,
sucesso real passa pelas 4 etapas na ordem certa."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.x_radar as x_radar_mod


def test_sem_credencial_nunca_chama_conector():
    with patch("data.x_signals.status_credencial", return_value={"estado": "sem_credencial", "motivo": "falta token"}), \
         patch("data.coletores_status.registrar_tentativa") as mock_registrar, \
         patch("data.x_radar.conector.coletar") as mock_coletar:
        resultado = x_radar_mod.executar_ciclo()
    assert resultado == {"ok": False, "motivo": "falta token", "estado": "sem_credencial", "sinais_novos": 0}
    mock_coletar.assert_not_called()
    mock_registrar.assert_called_once()


def test_ciclo_completo_passa_pelas_4_etapas_na_ordem():
    ordem = []
    with patch("data.x_signals.status_credencial", return_value={"estado": "ok", "motivo": None}), \
         patch("data.coletores_status.registrar_tentativa"), \
         patch("data.x_radar.conector.coletar", side_effect=lambda: (ordem.append("coletar"), ([], {"leituras": 1}))[1]), \
         patch("data.x_radar.classificador.classificar_lote", side_effect=lambda s: (ordem.append("classificar"), [])[1]), \
         patch("data.x_radar.cruzamento.enriquecer_lote", side_effect=lambda c: (ordem.append("cruzar"), [])[1]), \
         patch("data.x_radar.relevancia.aplicar_relevancia_credibilidade", side_effect=lambda e: (ordem.append("relevancia"), [])[1]), \
         patch("data.x_radar.store.registrar_consumo"), \
         patch("data.x_radar.store.persistir_lote", side_effect=lambda e: (ordem.append("persistir"), 3)[1]):
        resultado = x_radar_mod.executar_ciclo()
    assert ordem == ["coletar", "classificar", "cruzar", "relevancia", "persistir"]
    assert resultado == {"ok": True, "sinais_novos": 3, "estado": "ok", "motivo": None}


def test_erro_inesperado_na_etapa_de_coleta_nunca_escapa():
    with patch("data.x_signals.status_credencial", return_value={"estado": "ok", "motivo": None}), \
         patch("data.coletores_status.registrar_tentativa") as mock_registrar, \
         patch("data.x_radar.conector.coletar", side_effect=RuntimeError("timeout de rede")):
        resultado = x_radar_mod.executar_ciclo()
    assert resultado["ok"] is False
    assert "RuntimeError" in resultado["motivo"]
    mock_registrar.assert_called_once()
    _, kwargs = mock_registrar.call_args
    assert kwargs["execucao_ok"] is False
