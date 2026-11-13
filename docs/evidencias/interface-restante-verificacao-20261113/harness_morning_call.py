# Harness visual LOCAL (sem login/auth/Supabase/rede/IA) pra
# render_edicao_atual (ui/morning_call_tab.py), chamado via
# `streamlit run harness_morning_call.py`. Mocka obter_sintese_mercado/
# listar_edicoes/_alertas_confiabilidade_cacheados com dado representativo
# (mesmo shape de data/sintese_mercado.py:obter_sintese_mercado) - o resto
# (HTML/CSS dos blocos A/C/F/G) e' o componente real.
from datetime import datetime, timedelta
from unittest.mock import patch

from _tema import preparar_pagina

import config
import ui.morning_call_tab as mc

preparar_pagina("harness morning call - edicao atual")

_SINTESE = {
    "ok": True,
    "atual": True,
    "dados": {
        "resumo_executivo": {
            "texto": "Ibovespa fecha em alta de 0,8%, puxado por bancos e mineradoras, em dia de agenda "
                     "esvaziada no exterior. Dólar recua para R$ 5,42 com fluxo estrangeiro positivo na B3.",
            "ressalvas": "Volume 15% abaixo da média dos últimos 20 pregões.",
        },
        "o_que_nao_sabemos": [
            "Resultado da reunião do Copom de dezembro (ainda sem data confirmada)",
            "Desfecho da negociação comercial EUA-China sobre tarifas de aço",
        ],
        "movimentos": [
            {
                "evento": "VALE3 +3,2%", "fonte": "Yahoo Finance", "data_fonte": "hoje",
                "confianca": "alta",
                "por_que_importa": "Minério de ferro em Qingdao sobe 2,1% após dado de produção industrial "
                                    "chinesa acima do esperado.",
                "impacto_possivel": "Pode sustentar o setor de mineração na abertura de quinta-feira.",
            },
            {
                "evento": "PETR4 -1,1%", "fonte": "Yahoo Finance", "data_fonte": "hoje", "confianca": "média",
                "por_que_importa": "Brent recua 0,9% com expectativa de aumento de oferta da OPEP+.",
                "impacto_possivel": None,
            },
        ],
        "oportunidades_riscos": [
            {
                "ativo_ou_setor": "Bancos (ITUB4/BBDC4)", "fonte": "Research interno", "data_fonte": "hoje",
                "catalisador": "Temporada de resultados do 4T começa em janeiro",
                "argumento_favoravel": "Inadimplência em queda há 3 trimestres consecutivos.",
                "argumento_contrario": "Múltiplos já próximos da média histórica de 5 anos.",
                "acompanhar": "Guidance de carteira de crédito 2027 nas teleconferências.",
            },
        ],
        "cenarios": [
            {
                "tipo": "principal",
                "cenario": "Alta gradual com rotação para cíclicas: mercado doméstico segue absorvendo "
                           "fluxo estrangeiro positivo, com rotação de defensivas para cíclicas domésticas.",
                "condicao": "Fluxo estrangeiro na B3 continua positivo por mais 2-3 semanas.",
                "sinalizadores": "Volume do fluxo estrangeiro diário (B3), DXY abaixo de 104.",
            },
            {
                "tipo": "alternativo",
                "cenario": "Correção por reprecificação de juros nos EUA: dado de inflação americano acima "
                           "do esperado reacende aposta de Fed mais hawkish, pressionando emergentes.",
                "condicao": "PCE de sexta-feira vem acima do consenso.",
                "sinalizadores": None,
            },
        ],
        "observar_proximas_sessoes": [
            {"item": "Ata do Copom", "motivo": "Sinaliza ritmo dos próximos cortes", "fonte": "BCB", "data_fonte": "quinta-feira"},
            {"item": "PCE americano", "motivo": "Indicador preferido do Fed para inflação", "fonte": "BEA", "data_fonte": "sexta-feira"},
        ],
    },
}

_EDICOES = [
    {
        "data": (datetime.now() - timedelta(days=0)).date(),
        "status": "ENVIADA",
        "executado_em": datetime.now(mc.TZ_SP) - timedelta(hours=3),
        "conteudo": "Edição de hoje — Ibovespa fecha em alta de 0,8%...\n\nBRASIL\nIbovespa: 128.320 pts; +0,8%.",
    },
]

PREFS = dict(config.PREFS_PADRAO)
PREFS["formato_numerico"] = "BR"
PREFS["tema"] = "AMBAR"

with patch.object(mc, "obter_sintese_mercado", return_value=_SINTESE), \
     patch.object(mc, "_alertas_confiabilidade_cacheados", return_value=[]), \
     patch.object(mc, "listar_edicoes", return_value=_EDICOES):
    mc.render_edicao_atual(PREFS)
