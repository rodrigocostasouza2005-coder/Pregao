# -*- coding: utf-8 -*-
"""Seção MARKET RESEARCHER — ACHADOS PRIORIZADOS em SAÚDE DOS DADOS
(ui/saude_dados_tab.py) - bare mode (sem ScriptRunContext), mesmo
padrão de tests/test_radar_tab_fontes_ui.py."""
from unittest.mock import patch

import ui.saude_dados_tab as sd_tab


def _painel_minimo():
    return [{"nome": "MERCADO", "fonte": "yfinance", "categoria": "Cotacoes",
             "frequencia_esperada": "sob demanda", "instrumentado": True,
             "codigo_estado": "SUCESSO_SEM_NOVIDADE", "rotulo_estado": "Coleta OK - sem novidades",
             "status_bruto": {}, "alerta": False, "desconhecido": False}]


def _capturar_render(achados):
    blocos = []
    with patch.object(sd_tab, "mr") as mr_mock, \
         patch.object(sd_tab.saude_dados, "diagnostico_infraestrutura", return_value=True), \
         patch.object(sd_tab.saude_dados, "obter_painel_saude", return_value=_painel_minimo()), \
         patch.object(sd_tab.saude_dados, "obter_painel_consumo", return_value=[]), \
         patch.object(sd_tab.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)), \
         patch.object(sd_tab.st, "caption", side_effect=lambda texto, **_k: blocos.append(texto)), \
         patch.object(sd_tab.st, "button", return_value=False), \
         patch.object(sd_tab.st, "container") as container_mock:
        mr_mock.achados_qualidade_coletores.return_value = achados
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        sd_tab.render_saude_dados()
    return "\n".join(b for b in blocos if not b.lstrip().startswith("<style>"))


def test_sem_achados_nao_mostra_a_secao():
    html_render = _capturar_render([])
    assert "MARKET RESEARCHER" not in html_render


def test_achado_critico_aparece_marcado_e_com_erro_real():
    achados = [{
        "coletor": "NEWS (Brasil)", "categoria": "Noticias", "codigo_estado": "FALHA_EXECUCAO",
        "rotulo_estado": "Falha de execucao", "critico": True,
        "evidencia": {"ultimo_sucesso_em": None, "ultima_tentativa_em": "2026-10-23T10:00:00Z",
                      "ultimo_erro": "timeout ao buscar feed"},
    }]
    html_render = _capturar_render(achados)
    assert "MARKET RESEARCHER — ACHADOS PRIORIZADOS (1)" in html_render
    assert "NEWS (Brasil)" in html_render
    assert "[CRÍTICO]" in html_render
    assert "timeout ao buscar feed" in html_render


def test_mais_de_10_achados_mostra_contagem_do_restante():
    achados = [{
        "coletor": f"coletor-{i}", "categoria": "Research", "codigo_estado": "NAO_COMPROVADO",
        "rotulo_estado": "Não comprovado", "critico": False,
        "evidencia": {"ultimo_sucesso_em": None, "ultima_tentativa_em": None, "ultimo_erro": None},
    } for i in range(12)]
    html_render = _capturar_render(achados)
    assert "+2 achado(s) adicional" in html_render
