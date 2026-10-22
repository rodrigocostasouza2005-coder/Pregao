# -*- coding: utf-8 -*-
"""Cotação de cache nunca aparece como atual. obter_cotacao_indice devolve o
último valor válido (_fallback_cache=True) quando a fonte falha; só a VISÃO
GERAL sinalizava isso - o letreiro do topo, o MERCADO, o Câmbio e o e-mail do
Morning Call mostravam o valor antigo como se fosse desta tentativa."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import data.prices as prices
import jobs.morning_call as mc

RAIZ = Path(__file__).parent.parent


def _cache(horas_atras=3):
    coletado = (datetime.now(timezone.utc) - timedelta(hours=horas_atras)).isoformat()
    return {"nome": "IBOVESPA", "preco": 205120.0, "variacao": 1100.0, "variacao_pct": 0.54, "erro": None,
            "_fallback_cache": True, "_coletado_em": coletado, "_barra_em": "2026-10-20T00:00:00-03:00"}


def test_rotulo_so_para_fallback():
    assert prices.rotulo_cotacao_em_cache({"preco": 1, "erro": None}) is None
    assert prices.rotulo_cotacao_em_cache(_cache()).startswith("EM CACHE • 3H")


def test_email_marca_valor_de_cache():
    with patch.object(mc, "obter_cotacao_indice", return_value=_cache()):
        _cot, linha = mc._obter_cotacao_fmt("Ibovespa", "^BVSP")
    assert "último valor válido" in linha and "em cache" in linha


def test_email_nao_expoe_excecao_quando_fonte_falha():
    with patch.object(mc, "obter_cotacao_indice",
                      return_value={"nome": "Ibovespa", "erro": "HTTPSConnectionPool(host='query1.finance.yahoo.com')"}):
        _cot, linha = mc._obter_cotacao_fmt("Ibovespa", "^BVSP")
    assert linha == "- Ibovespa: indisponível nesta edição (a fonte não respondeu)"
    assert "HTTPSConnectionPool" not in linha


def test_letreiro_e_mercado_consultam_o_rotulo():
    """O letreiro vive dentro de um fragment do app.py (exige login real);
    conferido estaticamente que ele e o MERCADO passam pelo critério único."""
    app = (RAIZ / "app.py").read_text(encoding="utf-8")
    trecho_tape = app.split("def _ticker_tape():", 1)[1].split("cotacoes_watchlist", 1)[0]
    assert "rotulo_cotacao_em_cache(cot)" in trecho_tape
    mercado = (RAIZ / "ui" / "mercado_tab.py").read_text(encoding="utf-8")
    assert "rotulo_cotacao_em_cache(ibov)" in mercado


def test_appteste_cambio_mostra_rotulo_e_sem_cor_de_movimento():
    from streamlit.testing.v1 import AppTest

    script = '''
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import ui.macro_tab as mt
cot = {"nome": "DOLAR", "preco": 5.02, "variacao": 0.01, "variacao_pct": 0.2, "erro": None, "_fallback_cache": True,
       "_coletado_em": (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat()}
with patch.object(mt, "_cotacao_cambio", return_value=cot), patch.object(mt, "obter_cenario_global", return_value=[]):
    mt.render_macro_cambio_commodities({"formato_numerico": "BR", "tema": "AMBAR"})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "EM CACHE • 40 MIN" in html
    assert "class='alta'" not in html
