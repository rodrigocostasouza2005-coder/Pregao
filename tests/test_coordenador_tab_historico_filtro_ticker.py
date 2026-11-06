# -*- coding: utf-8 -*-
"""Filtro por ticker em render_historico (ui/coordenador_tab.py,
reformulação visual 2026-11-06, pedido do Rodrigo). persistencia.py
ainda não tem uma função dedicada de busca por ticker (outra frente
trabalha nesse arquivo em paralelo) - o filtro aqui é client-side,
sobre a lista já carregada por listar_analises_recentes(), sem tocar
em persistencia.py.

AppTest real (nunca AppTest.from_string tocando rede: persistência
100% mockada)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _analises_fake():
    return [
        {
            "id": "aaa111", "solicitacao": "Analisar PETR4", "tipo_fluxo": "analise_ticker",
            "ticker": "PETR4", "iniciado_em": "2026-11-05T10:00:00Z", "status": "CONCLUIDA",
            "duracao_ms": 1200, "resultado": {"resumo_executivo": "x", "sinal_comite": {}, "confianca": {}, "visao_especialistas": {}, "evidencias": [], "divergencias": {}, "pontos_atencao": [], "conclusao": [], "pareceres_analistas": {"analistas": [], "casas_research": [], "preco_alvo_consenso": {}}},
        },
        {
            "id": "bbb222", "solicitacao": "Comparar casas sobre VALE3", "tipo_fluxo": "comparar_casas",
            "ticker": "VALE3", "iniciado_em": "2026-11-04T10:00:00Z", "status": "CONCLUIDA",
            "duracao_ms": 900, "resultado": {"resumo_executivo": "y", "sinal_comite": {}, "confianca": {}, "visao_especialistas": {}, "evidencias": [], "divergencias": {}, "pontos_atencao": [], "conclusao": [], "pareceres_analistas": {"analistas": [], "casas_research": [], "preco_alvo_consenso": {}}},
        },
    ]


def _rodar(filtro: str | None):
    from streamlit.testing.v1 import AppTest

    analises_fake = _analises_fake()
    script = f'''
from unittest.mock import patch
import ui.coordenador_tab as coord
from data.coordenador_central import persistencia

analises_fake = {analises_fake!r}

with patch.object(persistencia, "listar_analises_recentes", return_value=analises_fake), \\
     patch.object(persistencia, "obter_analise", side_effect=lambda id_: next((a for a in analises_fake if a["id"] == id_), None)):
    coord.render_historico({{}})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    if filtro is not None:
        at.text_input(key="coord_historico_filtro_ticker").set_value(filtro).run()
    return at


def test_sem_filtro_mostra_as_duas_analises_no_seletor():
    at = _rodar(None)
    assert not at.exception
    opcoes = at.selectbox(key="coord_historico_escolha").options
    assert len(opcoes) == 2


def test_filtro_por_ticker_restringe_o_seletor_a_1_analise():
    at = _rodar("VALE3")
    assert not at.exception
    opcoes = at.selectbox(key="coord_historico_escolha").options
    assert len(opcoes) == 1
    assert "VALE3" in opcoes[0]


def test_filtro_case_insensitive_e_com_espacos():
    at = _rodar("  petr4  ")
    assert not at.exception
    opcoes = at.selectbox(key="coord_historico_escolha").options
    assert len(opcoes) == 1
    assert "PETR4" in opcoes[0]


def test_filtro_sem_correspondencia_mostra_aviso_sem_quebrar():
    at = _rodar("ITUB4")
    assert not at.exception
    avisos = " ".join(i.value for i in at.info)
    assert "Nenhuma análise encontrada para o ticker 'ITUB4'" in avisos
