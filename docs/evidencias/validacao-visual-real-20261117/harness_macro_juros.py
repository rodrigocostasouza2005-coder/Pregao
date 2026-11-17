# Harness visual LOCAL (sem login/auth) - MACRO > Juros (render_macro_juros,
# ui/macro_tab.py). Mesmo padrao dos outros harnesses desta pasta - zero
# dado novo, so' mocka as mesmas fontes de data/macro.py.
import pandas as pd
from unittest.mock import patch

from _tema import preparar_pagina

import config
import ui.macro_tab as mt

preparar_pagina("harness macro juros")

PREFS = dict(config.PREFS_PADRAO)
PREFS["formato_numerico"] = "BR"
PREFS["tema"] = "AMBAR"

_DATAS = pd.date_range("2026-08-10", periods=60, freq="D")
_SELIC = pd.DataFrame({"data": _DATAS, "selic_meta_pct": [13.75] * 60})
_CDI = pd.DataFrame({"data": _DATAS, "cdi_anualizado_pct": [13.65] * 60})
_CURVA = pd.DataFrame({
    "dias_uteis": [21, 126, 252, 504, 1260, 2520],
    "taxa_aa_pct": [13.9, 13.2, 12.6, 12.1, 11.8, 11.6],
    "data_referencia": [pd.Timestamp("2026-11-06")] * 6,
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

with patch.object(mt, "obter_selic_meta", return_value=_SELIC), \
     patch.object(mt, "obter_cdi", return_value=_CDI), \
     patch.object(mt, "obter_curva_pre", return_value=_CURVA), \
     patch.object(mt, "obter_focus_ipca", return_value=_FOCUS_IPCA), \
     patch.object(mt, "obter_focus_selic", return_value=_FOCUS_SELIC):
    mt.render_macro_juros(PREFS)
