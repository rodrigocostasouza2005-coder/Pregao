# -*- coding: utf-8 -*-
"""Regressão da nova subaba RESEARCH › Radar X
(ui/research_tab.py:render_radar_x, 2026-10-30). Bare mode (sem
ScriptRunContext) - render_radar_x é @st.fragment, precisa de
.__wrapped__ (mesmo padrão de tests/test_research_casas_analise_ui.py)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.research_tab as research_tab_mod

_PREFS = {"formato_numerico": "BR", "watchlist": []}


class _ColunaFake:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _capturar_render(saude, sinais, *, filtros=None):
    blocos = []
    filtros = filtros or {"radarx_dias": 7, "radarx_ticker": "", "radarx_categoria": "Todas", "radarx_confirmado": "Todas"}

    def _selectbox(label, opcoes=None, index=0, key=None, **_k):
        if key == "radarx_dias":
            return 7
        if key == "radarx_categoria":
            return filtros["radarx_categoria"]
        if key == "radarx_confirmado":
            return filtros["radarx_confirmado"]
        return opcoes[index] if opcoes else None

    with patch.object(research_tab_mod, "saude_conector", return_value=saude), \
         patch.object(research_tab_mod, "listar_sinais", return_value=sinais), \
         patch.object(research_tab_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)), \
         patch.object(research_tab_mod.st, "container") as container_mock, \
         patch.object(research_tab_mod.st, "expander") as expander_mock, \
         patch.object(research_tab_mod.st, "columns", return_value=[_ColunaFake() for _ in range(4)]), \
         patch.object(research_tab_mod.st, "selectbox", side_effect=_selectbox), \
         patch.object(research_tab_mod.st, "text_input", return_value=filtros["radarx_ticker"]), \
         patch.object(research_tab_mod.st, "warning", side_effect=lambda texto: blocos.append(texto)):
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        expander_mock.return_value.__enter__ = lambda self: self
        expander_mock.return_value.__exit__ = lambda *a: False
        research_tab_mod.render_radar_x.__wrapped__(_PREFS)
    return "\n".join(b for b in blocos if not b.lstrip().startswith("<style>"))


_SAUDE_DESLIGADO = {
    "status_credencial": {"estado": "sem_credencial", "motivo": "sem token configurado", "token_presente": False},
    "total_sinais": 0, "ultima_captura": None,
}
_SAUDE_OK = {
    "status_credencial": {"estado": "ok", "motivo": None, "token_presente": True},
    "total_sinais": 2, "ultima_captura": "2026-10-30T10:00:00Z",
}

_SINAL_EXEMPLO = {
    "post_id": "1", "autor": "@analista_br", "ticker": "PETR4", "categoria": "opiniao_analista",
    "nivel_evidencia": "nivel_1_sinal_social", "relevancia": 45, "relevancia_motivo": "x",
    "credibilidade": None, "credibilidade_motivo": None, "texto": "ROIC caiu bastante este trimestre",
    "link_original": "https://x.com/analista_br/status/1", "conta_verificada": False,
    "catalisador": None, "sentimento": "negativo", "estado": "detectado",
}


def test_sem_credencial_mostra_desligado_e_nunca_chama_listar_sinais():
    with patch.object(research_tab_mod, "listar_sinais") as mock_listar:
        html_render = _capturar_render(_SAUDE_DESLIGADO, None)
    mock_listar.assert_not_called()
    assert "DESLIGADO" in html_render
    assert "sem token configurado" in html_render
    assert "Nenhum dado é simulado" in html_render


def test_titulo_da_secao_sempre_aparece():
    html_render = _capturar_render(_SAUDE_DESLIGADO, None)
    assert "RADAR X" in html_render
    assert "INTELIGÊNCIA SOCIAL" in html_render


def test_credenciado_com_sinais_mostra_tabela_de_publicacoes():
    html_render = _capturar_render(_SAUDE_OK, [_SINAL_EXEMPLO])
    assert "CONECTADO" in html_render
    assert "analista_br" in html_render
    assert "PETR4" in html_render
    assert "PUBLICAÇÕES MAIS RELEVANTES" in html_render


def test_banco_indisponivel_mostra_aviso_sem_quebrar():
    html_render = _capturar_render(_SAUDE_OK, None)  # listar_sinais retorna None = banco fora do ar
    assert "indisponível" in html_render.lower()


def test_sem_sinais_no_filtro_nao_quebra():
    html_render = _capturar_render(_SAUDE_OK, [])
    assert "Nenhuma publicação no filtro atual" in html_render


def test_catalisador_aparece_quando_presente():
    sinal_com_catalisador = dict(_SINAL_EXEMPLO, catalisador="possível fusão anunciada")
    html_render = _capturar_render(_SAUDE_OK, [sinal_com_catalisador])
    assert "CATALISADORES IDENTIFICADOS" in html_render
    assert "possível fusão anunciada" in html_render
