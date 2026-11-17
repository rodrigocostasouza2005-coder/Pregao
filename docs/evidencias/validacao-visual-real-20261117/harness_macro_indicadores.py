# Harness visual LOCAL (sem login/auth) - valida a reformulacao Bloomberg
# ambar de MACRO > Indicadores (render_macro, ui/macro_tab.py). Mesmo
# padrao de docs/evidencias/validacao-independente-home-mercado-20261106/
# harness_mercado.py (render_mercado(prefs, persistir_fn=None) direto, sem
# precisar de sessao Supabase/login real). ZERO dado novo - so' mocka as
# mesmas fontes de data/macro.py ja usadas pela aba.
import pandas as pd
from unittest.mock import patch

from _tema import preparar_pagina

import config
import ui.macro_tab as mt

preparar_pagina("harness macro indicadores")

PREFS = dict(config.PREFS_PADRAO)
PREFS["formato_numerico"] = "BR"
PREFS["tema"] = "AMBAR"

_DATAS = pd.date_range("2026-08-10", periods=60, freq="D")

_SELIC = pd.DataFrame({"data": _DATAS, "selic_meta_pct": [13.75] * 60})
_CDI = pd.DataFrame({"data": _DATAS, "cdi_anualizado_pct": [13.65] * 60})
_IPCA = pd.DataFrame({
    "data": _DATAS,
    "ipca_mensal_pct": [0.35 + 0.05 * (i % 5 - 2) for i in range(60)],
    "ipca_12m_pct": [4.3 + 0.02 * i for i in range(60)],
})
_FOCUS_IPCA = pd.DataFrame({
    "ano_referencia": [2026, 2027, 2028],
    "mediana_pct": [4.52, 4.10, 3.80],
    "media_pct": [4.55, 4.15, 3.85],
    "numero_respondentes": [98, 95, 72],
    "data_calculo": pd.to_datetime(["2026-11-03"] * 3),
})
_FOCUS_SELIC = pd.DataFrame({
    "ano_referencia": [2026, 2027, 2028],
    "mediana_pct": [13.75, 11.50, 10.00],
    "media_pct": [13.70, 11.60, 10.10],
    "numero_respondentes": [98, 95, 72],
    "data_calculo": pd.to_datetime(["2026-11-03"] * 3),
})
_CURVA = pd.DataFrame({
    "dias_uteis": [21, 126, 252, 504, 1260, 2520],
    "taxa_aa_pct": [13.9, 13.2, 12.6, 12.1, 11.8, 11.6],
    "data_referencia": [pd.Timestamp("2026-11-06")] * 6,
})
_CENARIO_GLOBAL = [
    {"nome": "Ouro", "preco": 2650.30, "variacao_pct": 1.25},
    {"nome": "Brent", "preco": 74.10, "variacao_pct": -0.82},
    {"nome": "WTI", "preco": 70.40, "variacao_pct": -0.65},
    {"nome": "Minério de Ferro", "preco": 108.50, "variacao_pct": 0.44},
    {"nome": "Treasuries 10A", "preco": 4.32, "variacao_pct": 0.0},
    {"nome": "VIX", "preco": 15.80, "variacao_pct": -3.10},
]

with patch.object(mt, "obter_selic_meta", return_value=_SELIC), \
     patch.object(mt, "obter_cdi", return_value=_CDI), \
     patch.object(mt, "obter_ipca", return_value=_IPCA), \
     patch.object(mt, "obter_focus_ipca", return_value=_FOCUS_IPCA), \
     patch.object(mt, "obter_focus_selic", return_value=_FOCUS_SELIC), \
     patch.object(mt, "obter_curva_pre", return_value=_CURVA), \
     patch.object(mt, "obter_cenario_global", return_value=_CENARIO_GLOBAL):
    mt.render_macro(PREFS, persistir_fn=None)
