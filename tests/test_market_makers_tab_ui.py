# -*- coding: utf-8 -*-
"""UI da aba MARKET MAKERS (ui/market_makers_tab.py) - bare mode (sem
ScriptRunContext real), mesmo padrão de tests/test_radar_tab_fontes_ui.py:
st.markdown funciona fora de sessão Streamlit, só avisa no log."""
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import ui.market_makers_tab as mm_tab

TZ_SP = ZoneInfo("America/Sao_Paulo")
_PREFS_SEM_WATCHLIST = {"formato_numerico": "BR", "watchlist": []}
_PREFS_COM_WATCHLIST = {"formato_numerico": "BR", "watchlist": ["PETR4", "VALE3"]}


def _capturar_render(prefs, dados=None, exc=None):
    blocos = []

    def _fake_inteligencia(tickers):
        if exc:
            raise exc
        return dados

    with patch.object(mm_tab, "inteligencia_mercado", side_effect=_fake_inteligencia), \
         patch.object(mm_tab.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)), \
         patch.object(mm_tab.st, "caption", side_effect=lambda texto, **_k: blocos.append(texto)), \
         patch.object(mm_tab.st, "info", side_effect=lambda texto, **_k: blocos.append(texto)), \
         patch.object(mm_tab.st, "warning", side_effect=lambda texto, **_k: blocos.append(texto)), \
         patch.object(mm_tab.st, "container") as container_mock:
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        mm_tab.render_market_makers(prefs, "visao-geral")
    return "\n".join(b for b in blocos if not b.lstrip().startswith("<style>"))


def _dados(mudancas=None, catalisadores=None, riscos=None):
    return {
        "gerado_em": datetime(2026, 10, 23, 8, 0, tzinfo=TZ_SP),
        "tickers": ("PETR4", "VALE3"), "janela": "7 DIAS",
        "mudancas": mudancas or [], "catalisadores": catalisadores or [], "riscos": riscos or {},
    }


def test_sem_watchlist_pede_para_cadastrar_e_nunca_consulta_nada():
    with patch.object(mm_tab, "inteligencia_mercado", side_effect=AssertionError("não deveria consultar")):
        html_render = _capturar_render(_PREFS_SEM_WATCHLIST)
    assert "Adicione tickers na watchlist" in html_render


def test_sem_nenhuma_evidencia_mostra_os_3_estados_vazios_honestos():
    html_render = _capturar_render(_PREFS_COM_WATCHLIST, dados=_dados())
    assert "Nenhuma mudança de tese/CVM verificada" in html_render
    assert "Nenhum catalisador" in html_render
    assert "Nenhum alerta de qualidade" in html_render


def test_mudanca_de_tese_real_aparece_com_fonte_e_selo_de_fato():
    mudanca = {"ticker": "PETR4", "categoria": "Research — recomendação/preço-alvo",
               "descricao": "Genial revisou de NEUTRO para COMPRA", "data_evento": date(2026, 10, 20),
               "fonte_url": "https://genial.com.br", "fonte_label": "Genial Analisa",
               "tipo_evidencia": "FATO"}
    html_render = _capturar_render(_PREFS_COM_WATCHLIST, dados=_dados(mudancas=[mudanca]))
    assert "Genial revisou de NEUTRO para COMPRA" in html_render
    assert "href='https://genial.com.br'" in html_render
    assert "FATO" in html_render


def test_catalisador_nao_confirmado_nunca_aparece_como_fato():
    catalisador = {"ticker": "VALE3", "categoria": "Resultado corporativo", "data": date(2026, 11, 14),
                   "status_label": "PRAZO CVM", "confirmado": False, "fonte_label": "CVM", "fonte_url": None}
    html_render = _capturar_render(_PREFS_COM_WATCHLIST, dados=_dados(catalisadores=[catalisador]))
    assert "ESTIMATIVA DE TERCEIRO" in html_render
    assert "VALE3" in html_render


def test_risco_de_qualidade_lista_o_alerta_real():
    html_render = _capturar_render(
        _PREFS_COM_WATCHLIST, dados=_dados(riscos={"PETR4": ["dívida/EBITDA acima do histórico"]}))
    assert "dívida/EBITDA acima do histórico" in html_render


def test_fonte_indisponivel_avisa_e_nao_lanca_excecao():
    html_render = _capturar_render(_PREFS_COM_WATCHLIST, exc=RuntimeError("Supabase fora do ar"))
    assert "indisponível" in html_render
