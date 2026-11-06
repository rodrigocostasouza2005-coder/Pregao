# -*- coding: utf-8 -*-
"""Regressão: ui/coordenador_tab.py chamava calcular_sensibilidade_dcf()
no bloco legado de exibição do DCF do Valuation Reviewer (dentro de
_render_consolidado, caminho "valuation_reviewer" com dcf disponível)
sem importar a função - NameError latente que nunca disparava em
nenhum teste existente porque nenhum deles exercitava uma análise
consolidada com DCF do Valuation Reviewer DISPONÍVEL (achado real,
2026-11-06). A função correta mora em
data/coordenador_central/dcf.py:calcular_sensibilidade_dcf.

AppTest real (nunca AppTest.from_string tocando rede: persistência
100% mockada - nada é escrito em nenhum log de produção por este
teste). calcular_dcf/calcular_sensibilidade_dcf são usados DE VERDADE
(não mockados) para que o teste exercite a renderização exatamente
como em produção."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


_PREMISSAS_DCF = {
    "fcf_base": 1_000_000.0,
    "wacc": 0.12,
    "g_terminal": 0.03,
    "divida_liquida": 500_000.0,
    "acoes": 100_000.0,
    "crescimento_fcf_otimista": 0.08,
    "crescimento_fcf_base": 0.05,
    "crescimento_fcf_pessimista": 0.02,
    "fonte_premissas": "Relatório anual 2025, página 42",
    "data_base": "2025-12-31",
    "moeda": "R$",
}


def _consolidado_com_dcf_disponivel() -> dict:
    from data.coordenador_central.dcf import calcular_dcf

    preco_atual = 18.50
    dcf = calcular_dcf(_PREMISSAS_DCF, preco_atual=preco_atual)
    assert dcf["disponivel"], "premissas de teste precisam produzir um DCF válido"

    analista_valuation = {
        "id": "valuation_reviewer", "nome": "Valuation Reviewer",
        "especialidade": "Revisão independente de cenários, premissas e sensibilidade",
        "metodo": "DCF de 5 anos + Gordon Growth.",
        "vies": "APROVADO", "recomendacao": "APROVADO",
        "tese": "Revisão concluída; ver achados e limitações.",
        "pros": [], "contras": [],
        "preco_alvo": (dcf["cenarios"]["base"]["preco_alvo"]),
        "upside_pct": (dcf["cenarios"]["base"]["upside_pct"]),
        "preco_atual": preco_atual,
        "dcf": dcf,
    }
    return {
        "resumo_executivo": "Análise consolidada para PETR4.",
        "sinal_comite": {},
        "visao_especialistas": {}, "evidencias": [],
        "divergencias": {"cross_comparador_memoria": None},
        "pontos_atencao": [], "conclusao": [],
        "confianca": {"categoria": "MEDIA", "justificativa": "x"},
        "pareceres_analistas": {
            "analistas": [analista_valuation],
            "casas_research": [],
            "preco_alvo_consenso": {},
        },
    }


def test_render_consolidado_com_dcf_disponivel_nao_quebra_e_mostra_sensibilidade():
    """Antes do fix: NameError (calcular_sensibilidade_dcf não importado)
    estourava aqui e at.exception não ficaria vazio."""
    from streamlit.testing.v1 import AppTest

    consolidado = _consolidado_com_dcf_disponivel()
    script = f'''
import ui.coordenador_tab as coord

coord._render_consolidado({consolidado!r})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception

    textos = " ".join(m.value for m in at.markdown)
    assert "Sensibilidade do cenário-base" in textos
    assert "PREÇO-ALVO PRINCIPAL" in textos


def test_render_historico_abre_analise_com_dcf_disponivel_sem_quebrar():
    """Mesmo caminho, mas através de render_historico (fluxo real de
    produção: usuário abre uma análise antiga pelo seletor)."""
    from streamlit.testing.v1 import AppTest

    consolidado = _consolidado_com_dcf_disponivel()
    analise_fake = {
        "id": "abc123def456", "solicitacao": "Analisar PETR4",
        "tipo_fluxo": "analise_ticker", "ticker": "PETR4",
        "iniciado_em": "2026-11-05T10:00:00Z", "status": "CONCLUIDA",
        "duracao_ms": 2345, "resultado": consolidado,
    }
    script = f'''
from unittest.mock import patch
import ui.coordenador_tab as coord
from data.coordenador_central import persistencia

analises_fake = [{analise_fake!r}]
analise_fake = {analise_fake!r}

with patch.object(persistencia, "listar_analises_recentes", return_value=analises_fake), \\
     patch.object(persistencia, "obter_analise", return_value=analise_fake):
    coord.render_historico({{}})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "Sensibilidade do cenário-base" in textos
