# Harness visual LOCAL (sem login/auth) - MACRO > Câmbio e Commodities
# (render_macro_cambio_commodities, ui/macro_tab.py). Inclui um par com
# variacao positiva, um negativo e um EM CACHE (confere visualmente que o
# cinza de "em cache" nunca herda cor de sinal - mesma regra de
# tests/test_cotacao_em_cache_sinalizada.py e tests/
# test_macro_bloomberg_20261106.py, aqui so' visual).
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from _tema import preparar_pagina

import config
import ui.macro_tab as mt

preparar_pagina("harness macro cambio")

PREFS = dict(config.PREFS_PADRAO)
PREFS["formato_numerico"] = "BR"
PREFS["tema"] = "AMBAR"

_COTACOES = {
    # chaves = config.INDICES_TICKER_TAPE (DOLAR/EURO sao os unicos
    # "=X" hoje) - DOLAR em alta, EURO EM CACHE (confere visualmente
    # que o cinza de "em cache" nunca herda cor de sinal, mesmo com
    # variacao_pct positiva armazenada).
    "DOLAR": {"nome": "DOLAR", "preco": 5.4321, "variacao_pct": 0.65, "erro": None},
    "EURO": {
        "nome": "EURO", "preco": 5.8790, "variacao_pct": 0.18, "erro": None,
        "_fallback_cache": True,
        "_coletado_em": (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat(),
    },
}

_CENARIO_GLOBAL = [
    {"nome": "Ouro", "preco": 2650.30, "variacao_pct": 1.25},
    {"nome": "Brent", "preco": 74.10, "variacao_pct": -0.82},
    {"nome": "WTI", "preco": 70.40, "variacao_pct": -0.65},
    {"nome": "Minério de Ferro", "preco": 108.50, "variacao_pct": 0.44},
    {"nome": "Treasuries 10A", "preco": 4.32, "variacao_pct": 0.0},
    {"nome": "VIX", "preco": 15.80, "variacao_pct": -3.10},
]


def _fake_cotacao_cambio(nome, simbolo):
    return _COTACOES.get(nome, {"erro": "sem dado"})


with patch.object(mt, "_cotacao_cambio", side_effect=_fake_cotacao_cambio), \
     patch.object(mt, "obter_cenario_global", return_value=_CENARIO_GLOBAL):
    mt.render_macro_cambio_commodities(PREFS)
