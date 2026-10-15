# -*- coding: utf-8 -*-
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
import jobs.morning_call as mc


def test_morning_call_independente_sem_news_e_macro():
    with patch.object(mc, "_linha_cotacao", side_effect=lambda nome, ticker: f"- {nome}: indisponível"), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=ZoneInfo("America/Sao_Paulo")))
    assert "MORNING CALL" in texto
    assert "CENÁRIOS CONDICIONAIS" in texto
    assert "carteira" not in texto.lower()
    assert "alerta" not in texto.lower()


def test_executar_registra_tentativa_no_painel_saude(monkeypatch):
    """Regressao 2026-10-15: o job rodava no GitHub Actions e persistia em
    morning_call_execucoes, mas nunca aparecia no painel SAUDE DOS DADOS
    (nenhuma linha em coletores_status) - sem isso, uma falha de envio so'
    era visivel no log do Actions, nunca na UI do Pregao."""
    chamadas = []
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *_a, **_k: {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "obter_cliente", lambda: None)
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    codigo = mc.executar()

    assert codigo == 0
    assert len(chamadas) == 1
    args, kwargs = chamadas[0]
    assert args[0] == "MORNING CALL"
    assert kwargs["execucao_ok"] is True
    assert kwargs["erro"] is None


def test_executar_registra_falha_quando_envio_nao_funciona(monkeypatch):
    chamadas = []
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *_a, **_k: {"ok": False, "erro": "Resend HTTP 401"})
    monkeypatch.setattr(mc, "obter_cliente", lambda: None)
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    codigo = mc.executar()

    assert codigo == 1
    assert chamadas[0][1]["execucao_ok"] is False
    assert chamadas[0][1]["erro"] == "Resend HTTP 401"
