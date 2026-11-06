# -*- coding: utf-8 -*-
"""Regressão: validação visual real (Playwright, desktop 1440px e iPad
1024px touch) encontrou que as tabelas de ESPECIALISTAS e EXECUÇÕES
(ui/coordenador_tab.py:render_especialistas/render_execucoes) eram as
únicas, entre todas as tabelas HTML deste módulo, sem o wrapper
`.coord-tabela-wrap` (overflow-x: auto já definido em style.css local
deste arquivo, _CSS_COORDENADOR) - usado em toda outra tabela do mesmo
módulo (_render_execucoes_agendadas, _render_casas_research, tabelas de
premissas/DCF/sensibilidade). Sem o wrapper, uma tabela mais larga que a
viewport (ex: Especialistas, 9 colunas) era cortada pelo container do
Streamlit sem nenhuma barra de rolagem - conteúdo real (status,
execuções, último erro técnico) ficava inacessível, pior ainda em
telas estreitas (iPad 1024px). Este teste garante que o HTML de saída
das duas funções sempre inclui o wrapper, prevenindo a regressão."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_tabela_especialistas_tem_wrapper_de_rolagem_horizontal():
    from streamlit.testing.v1 import AppTest

    script = '''
from unittest.mock import patch
import ui.coordenador_tab as coord
from data.coordenador_central import persistencia

with patch.object(persistencia, "metricas_especialistas", return_value={}):
    coord.render_especialistas({})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    htmls = [m.value for m in at.markdown]
    tabela = next(h for h in htmls if "ESPECIALISTA" in h.upper() and "<table" in h)
    assert "coord-tabela-wrap" in tabela, (
        "tabela de Especialistas sem .coord-tabela-wrap - volta a cortar "
        "colunas sem rolagem em telas estreitas/tabelas largas (regressão "
        "da validação visual 2026-11-06)."
    )


def test_tabela_execucoes_tem_wrapper_de_rolagem_horizontal():
    from streamlit.testing.v1 import AppTest

    script = '''
from unittest.mock import patch
import ui.coordenador_tab as coord
from data.coordenador_central import persistencia

analises = [{
    "id": "abc123", "solicitacao": "Analisar PETR4", "tipo_fluxo": "analise_ticker",
    "iniciado_em": "2026-11-05T10:00:00Z", "status": "CONCLUIDA", "duracao_ms": 1200, "erro": None,
}]

with patch.object(persistencia, "listar_analises_recentes", return_value=analises):
    coord.render_execucoes({})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    htmls = [m.value for m in at.markdown]
    tabela = next(h for h in htmls if "<table" in h and "Analisar PETR4" in h)
    assert "coord-tabela-wrap" in tabela, (
        "tabela de Execuções sem .coord-tabela-wrap - mesma regressão "
        "potencial da tabela de Especialistas."
    )
