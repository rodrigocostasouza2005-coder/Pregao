# Harness "DEPOIS" - chama o modulo novo ui/carteira_recomendada_tab.py
# direto, mesmo dado mockado de _dados_carteira.py usado no "ANTES".
import sys

from _dados_carteira import carteira_mock, historico_mock
from _tema import preparar_pagina

import config
import ui.carteira_recomendada_tab as tab

preparar_pagina("harness carteira DEPOIS")

ABA = sys.argv[1] if len(sys.argv) > 1 else "visao-geral"

PREFS = dict(config.PREFS_PADRAO)
PREFS["formato_numerico"] = "BR"
PREFS["tema"] = "AMBAR"

if ABA == "visao-geral":
    tab.render_visao_geral(carteira_mock(), PREFS)
else:
    tab.render_historico(historico_mock())
