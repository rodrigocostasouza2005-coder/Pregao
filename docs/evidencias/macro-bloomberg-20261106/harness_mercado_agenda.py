# Harness visual LOCAL (sem login/auth) - MERCADO > Agenda
# (ui/secoes.py:render_agenda). render_agenda e' so' um texto de
# desambiguacao + render_calendario(prefs) (ui/calendario_tab.py, fora do
# escopo desta missao - so' MOCKADO aqui pra a tela renderizar) - ver
# docstring de render_agenda. ZERO dado novo: mocka as mesmas fontes que
# tests/test_calendario_ui.py ja usa (calcular_calendario_cacheado,
# obter_snapshot_calendario) + universo_calendario/obter_documentos_cvm/
# obter_noticias/listar_itens (contexto do evento selecionado).
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from _tema import preparar_pagina

import config
import ui.calendario_tab as calendario_tab_mod
import ui.secoes as secoes
from data.eventos import STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM

preparar_pagina("harness mercado agenda")

PREFS = dict(config.PREFS_PADRAO)
PREFS["formato_numerico"] = "BR"
PREFS["tema"] = "AMBAR"
PREFS["watchlist"] = ["PETR4", "VALE3", "ITUB4"]

_HOJE = datetime.now(calendario_tab_mod._TZ_SP).date()


def _evento(ticker, empresa, periodo, status, dias_a_partir_de_hoje, fonte="fonte teste", horario=None):
    return {
        "ticker": ticker, "empresa": empresa, "periodo": periodo,
        "data": _HOJE + timedelta(days=dias_a_partir_de_hoje), "horario": horario,
        "status": status, "fonte": fonte, "origem_url": None, "tipo_evento": "RESULTADO",
        "coletado_em": None,
    }


_EVENTOS = [
    _evento("PETR4", "Petróleo Brasileiro S.A.", "3T26", STATUS_CONFIRMADO, 2, fonte="Petrobras RI", horario="18h00"),
    _evento("VALE3", "Vale S.A.", "3T26", STATUS_ESTIMADO, 5, fonte="Consenso de mercado"),
    _evento("ITUB4", "Itaú Unibanco", "3T26", STATUS_PRAZO_CVM, 12, fonte="CVM (prazo regulatório)"),
]

_SNAPSHOT = {
    "eventos": _EVENTOS,
    "atualizado_em": (datetime.now(timezone.utc) - timedelta(minutes=18)).isoformat(),
}

with patch.object(calendario_tab_mod, "calcular_calendario_cacheado", return_value=_EVENTOS), \
     patch.object(calendario_tab_mod, "obter_snapshot_calendario", return_value=_SNAPSHOT), \
     patch.object(calendario_tab_mod, "universo_calendario", return_value=list(range(509))), \
     patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[]), \
     patch.object(calendario_tab_mod, "obter_noticias", return_value=[]), \
     patch.object(calendario_tab_mod, "listar_itens", return_value=[]):
    secoes.render_agenda(PREFS)
