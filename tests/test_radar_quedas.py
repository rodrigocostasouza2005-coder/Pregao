# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.radar_quedas import calcular_queda, deve_alertar, avaliar_ticker


def test_calculo_queda():
    assert round(calcular_queda(95.99, 100), 2) == -4.01
    assert calcular_queda(96, 100) == -4.0
    assert calcular_queda(0, 100) is None
    assert calcular_queda(95, None) is None


def test_limite_estrito():
    assert not deve_alertar(-3.5)
    assert not deve_alertar(-4.0)
    assert deve_alertar(-4.01)
    assert deve_alertar(-5.2)
    assert not deve_alertar(None)


def test_alerta_consolida_carteiras():
    recs = [
        {"ticker": "PETR4", "casa": "Casa A", "carteira": "Dividendos", "fonte_url": "https://a"},
        {"ticker": "PETR4", "casa": "Casa B", "carteira": "Top 10", "fonte_url": "https://b"},
    ]
    cot = {"preco": 95.9, "fechamento_anterior": 100, "variacao_pct": -4.1, "cotacao_em": "2026-10-14T12:00:00-03:00"}
    from datetime import datetime
    from zoneinfo import ZoneInfo
    alerta = avaliar_ticker("PETR4", cot, recs, datetime(2026, 10, 14, 12, tzinfo=ZoneInfo("America/Sao_Paulo")))
    assert alerta and len(alerta["casas"]) == 2 and len(alerta["carteiras"]) == 2
