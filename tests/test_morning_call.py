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
