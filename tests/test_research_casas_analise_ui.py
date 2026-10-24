# -*- coding: utf-8 -*-
"""Regressão da nova subaba RESEARCH › Casas de Análise
(ui/research_tab.py:render_casas_analise, 2026-10-23). Bare mode (sem
ScriptRunContext) - render_casas_analise é @st.fragment, precisa de
.__wrapped__ (mesmo padrão de tests/test_radar_tab_fontes_ui.py)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.research_tab as research_tab_mod

_PREFS = {"formato_numerico": "BR", "watchlist": []}


def _capturar_render(status_casas, prefs=None, cobertura=None):
    blocos = []
    with patch.object(research_tab_mod, "obter_status_casas", return_value=status_casas), \
         patch.object(research_tab_mod, "cobertura_cruzada_casas", side_effect=lambda t: (cobertura or {})[t]), \
         patch.object(research_tab_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)), \
         patch.object(research_tab_mod.st, "container") as container_mock:
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        research_tab_mod.render_casas_analise.__wrapped__(prefs or _PREFS)
    return "\n".join(b for b in blocos if not b.lstrip().startswith("<style>"))


def test_casa_sem_evidencia_aparece_como_nao_comprovada_nunca_como_ok():
    status = [{
        "nome": "Genial Analisa", "fonte": "analisa.genialinvestimentos.com.br",
        "coleta_automatica_cloud": False, "codigo_estado": "NAO_COMPROVADO",
        "rotulo_estado": "Não comprovado (sem linha no painel de saúde)",
        "ultimo_sucesso_em": None, "ultima_tentativa_em": None,
        "registros_novos_ultima_coleta": None, "alerta": False,
    }]
    html_render = _capturar_render(status)
    assert "Genial Analisa" in html_render
    assert "Não comprovado" in html_render
    assert "só via coletor_local.py" in html_render


def test_casa_com_sucesso_mostra_estado_e_contagem_reais():
    status = [{
        "nome": "Monte Bravo", "fonte": "montebravo.com.br (feed RSS)",
        "coleta_automatica_cloud": True, "codigo_estado": "SUCESSO_COM_NOVIDADE",
        "rotulo_estado": "Coleta OK - dados novos (3)",
        "ultimo_sucesso_em": "2026-10-23T10:00:00+00:00", "ultima_tentativa_em": "2026-10-23T10:00:00+00:00",
        "registros_novos_ultima_coleta": 3, "alerta": False,
    }]
    html_render = _capturar_render(status)
    assert "Monte Bravo" in html_render
    assert "coleta automática (Cloud + local)" in html_render
    assert ">3<" in html_render


def test_referencia_ao_levantamento_de_candidatas_esta_presente():
    """Nunca lista casas candidatas nao implementadas aqui - so' aponta
    pro documento que ja investigou isso (evita duplicar/inflar)."""
    html_render = _capturar_render([])
    assert "research-fontes-20261022.md" in html_render


def test_nenhuma_excecao_com_lista_vazia():
    assert _capturar_render([]) is not None


def test_cobertura_cruzada_mostra_quem_cobriu_e_quem_nao_cobriu():
    prefs = {"formato_numerico": "BR", "watchlist": ["WEGE3"]}
    cobertura = {"WEGE3": {
        "ticker": "WEGE3", "divergencia": None, "sem_cobertura": ["BTG Research"],
        "cobertura": [{"casa": "Genial Analisa", "data": "2026-10-20", "titulo": "WEGE3 revisão",
                       "link": "https://genial.com.br/x", "recomendacao": "COMPRA", "preco_alvo": 45.0}],
    }}
    html_render = _capturar_render([], prefs=prefs, cobertura=cobertura)
    assert "COBERTURA CRUZADA" in html_render
    assert "Genial Analisa" in html_render and "COMPRA" in html_render
    assert "BTG Research" in html_render  # listado como sem cobertura


def test_cobertura_cruzada_mostra_divergencia_quando_estruturada():
    prefs = {"formato_numerico": "BR", "watchlist": ["WEGE3"]}
    cobertura = {"WEGE3": {
        "ticker": "WEGE3", "sem_cobertura": [],
        "cobertura": [
            {"casa": "Genial Analisa", "data": "2026-10-20", "titulo": "t1", "link": "https://a", "recomendacao": "COMPRA", "preco_alvo": None},
            {"casa": "XP Investimentos", "data": "2026-10-20", "titulo": "t2", "link": "https://b", "recomendacao": "VENDA", "preco_alvo": None},
        ],
        "divergencia": {"descricao": "diverge", "por_casa": {"Genial Analisa": "COMPRA", "XP Investimentos": "VENDA"}},
    }}
    html_render = _capturar_render([], prefs=prefs, cobertura=cobertura)
    assert "Genial Analisa: COMPRA" in html_render and "XP Investimentos: VENDA" in html_render


def test_banco_indisponivel_na_cobertura_nunca_quebra_a_pagina():
    prefs = {"formato_numerico": "BR", "watchlist": ["WEGE3"]}
    cobertura = {"WEGE3": {"ticker": "WEGE3", "cobertura": None, "sem_cobertura": [], "divergencia": None}}
    html_render = _capturar_render([], prefs=prefs, cobertura=cobertura)
    assert "banco indisponível" in html_render
