# Harness visual LOCAL (sem login/auth) - MACRO > Calendário Econômico
# (render_macro_calendario, ui/macro_tab.py).
from datetime import date
import pandas as pd
from unittest.mock import patch

from _tema import preparar_pagina

import config
import ui.macro_tab as mt

preparar_pagina("harness macro calendario")

PREFS = dict(config.PREFS_PADRAO)
PREFS["formato_numerico"] = "BR"
PREFS["tema"] = "AMBAR"

_COPOM = {"valor": 13.75, "vigente_desde": date(2026, 9, 17), "reuniao": 281}
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

with patch.object(mt, "_copom_vigente", return_value=_COPOM), \
     patch.object(mt, "obter_focus_ipca", return_value=_FOCUS_IPCA), \
     patch.object(mt, "obter_focus_selic", return_value=_FOCUS_SELIC):
    mt.render_macro_calendario(PREFS)
