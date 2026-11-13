# Harness visual LOCAL (sem login/auth/Supabase/rede) pra render_cvm
# (ui/cvm_tab.py), chamado via `streamlit run harness_cvm.py` -- mocka so'
# obter_documentos_watchlist (data/cvm.py) com dado representativo, o
# resto (tabela/destaques/paginacao/busca) e' o componente real.
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from _tema import preparar_pagina

import config
import ui.cvm_tab as cvm_tab

preparar_pagina("harness cvm")

_TIPOS = ["FATO_RELEVANTE", "COMUNICADO", "RESULTADOS", "PROVENTOS", "CALENDARIO"]
_LABEL = {
    "FATO_RELEVANTE": "FATO RELEVANTE", "COMUNICADO": "COMUNICADO",
    "RESULTADOS": "RESULTADOS", "PROVENTOS": "PROVENTOS", "CALENDARIO": "CALENDÁRIO",
}
_TICKERS = ["PETR4", "VALE3", "ITUB4", "BBDC4", "WEGE3"]
_ASSUNTOS = [
    "Comunicado ao Mercado - Esclarecimentos sobre noticia veiculada na midia",
    "Fato Relevante - Aprovação de aumento de capital social mediante subscrição particular",
    "Resultado do 3º Trimestre de 2026 (ITR)",
    "Aviso aos Acionistas - Pagamento de Juros sobre Capital Próprio (JCP)",
    "Calendário de Eventos Corporativos 2027",
    "Ata de Reunião do Conselho de Administração realizada em 10/11/2026",
]

_DOCS = []
_agora = datetime.now(timezone.utc)
for i in range(37):
    tipo = _TIPOS[i % len(_TIPOS)]
    ticker = _TICKERS[i % len(_TICKERS)]
    _DOCS.append({
        "ticker": ticker, "tipo": tipo, "tipo_label": _LABEL[tipo],
        "categoria_original": _LABEL[tipo].title(),
        "assunto": _ASSUNTOS[i % len(_ASSUNTOS)],
        "data": (_agora - timedelta(days=i)).isoformat(),
        "data_referencia": (_agora - timedelta(days=i)).isoformat(),
        "link": f"https://www.rad.cvm.gov.br/documento-{i}",
    })

PREFS = dict(config.PREFS_PADRAO)
PREFS["formato_numerico"] = "BR"
PREFS["tema"] = "AMBAR"
PREFS["watchlist"] = _TICKERS

with patch.object(cvm_tab, "obter_documentos_watchlist", return_value=(_DOCS, [])):
    cvm_tab.render_cvm.__wrapped__(PREFS)
