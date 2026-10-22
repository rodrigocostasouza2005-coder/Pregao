# -*- coding: utf-8 -*-
"""Regressão da subaba ANÁLISES › Teses (ui/radar_tab.py:render_teses) após
a integração Market Researcher/equity-research da Anthropic (2026-10-22,
ver docs/market-researcher-integracao.md): nova seção "MINHA TESE" lendo
data/research/tese.py, sem tocar nas seções já existentes (RESEARCH COM
EVIDÊNCIAS/COPILOTO DE RESEARCH).

Bare mode (sem ScriptRunContext real) - mesmo padrão de
tests/test_radar_tab_fontes_ui.py: render_teses é @st.fragment, então
chamar render_teses(...) direto não executaria o corpo nenhum - precisa
de .__wrapped__. st.selectbox também não tem valor real em bare mode,
por isso é mockado pra sempre devolver a primeira opção."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.radar_tab as radar_tab_mod

_PREFS = {"formato_numerico": "BR", "watchlist": ["PETR4"]}
_USUARIO = {"sub": "user-teste", "email": "teste@example.com"}


def _capturar_render(scorecard, historico=None, snapshot_casa=None):
    blocos = []
    with patch.object(radar_tab_mod.tese, "scorecard", return_value=scorecard), \
         patch.object(radar_tab_mod.tese, "historico_tese", return_value=historico or []), \
         patch.object(radar_tab_mod, "ultimo_snapshot", return_value=snapshot_casa), \
         patch.object(radar_tab_mod.st, "selectbox", side_effect=lambda label, options, **k: options[0]), \
         patch.object(radar_tab_mod.st, "pills", return_value=None), \
         patch.object(radar_tab_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)):
        radar_tab_mod.render_teses.__wrapped__(_PREFS, _USUARIO)
    return "\n".join(b for b in blocos if not b.lstrip().startswith("<style>"))


def test_sem_tese_mostra_estado_vazio_sem_quebrar():
    html_render = _capturar_render(scorecard=None)
    assert "Nenhuma tese registrada" in html_render


def test_tese_existente_mostra_premissas_riscos_catalisadores_e_conviccao():
    sc = {
        "ticker": "PETR4", "tese_atual": "Long PETR4 - dividendos consistentes",
        "posicao": "LONG", "premissas": ["Dividend yield alto"], "riscos": ["Preço do petróleo"],
        "catalisadores": ["Resultado trimestral"], "conviccao": "ALTA", "preco_alvo_tese": 42.5,
        "registrado_em": "2026-10-20T10:00:00+00:00", "n_versoes": 1,
    }
    html_render = _capturar_render(scorecard=sc)
    assert "Long PETR4" in html_render
    assert "Dividend yield alto" in html_render
    assert "Preço do petróleo" in html_render
    assert "Resultado trimestral" in html_render
    assert "convicção ALTA" in html_render


def test_preco_alvo_da_tese_e_marcado_como_hipotese_nunca_como_fato():
    sc = {
        "ticker": "PETR4", "tese_atual": "Long", "posicao": "LONG", "premissas": [], "riscos": [],
        "catalisadores": [], "conviccao": "MEDIA", "preco_alvo_tese": 42.5,
        "registrado_em": "2026-10-20T10:00:00+00:00", "n_versoes": 1,
    }
    html_render = _capturar_render(scorecard=sc)
    assert "radar-selo-hipotese" in html_render
    assert "HIPÓTESE DO ANALISTA" in html_render


def test_preco_alvo_da_casa_de_research_e_marcado_como_estimativa_de_terceiro():
    sc = {
        "ticker": "PETR4", "tese_atual": "Long", "posicao": "LONG", "premissas": [], "riscos": [],
        "catalisadores": [], "conviccao": "MEDIA", "preco_alvo_tese": None,
        "registrado_em": "2026-10-20T10:00:00+00:00", "n_versoes": 1,
    }
    snapshot = {"recomendacao": "COMPRA", "preco_alvo": 45.0, "capturado_em": "2026-10-19T10:00:00+00:00"}
    html_render = _capturar_render(scorecard=sc, snapshot_casa=snapshot)
    assert "radar-selo-estimativa" in html_render
    assert "ESTIMATIVA DE TERCEIRO" in html_render
    assert "Genial Analisa" in html_render


def test_historico_com_mais_de_uma_versao_fica_disponivel_num_expander():
    sc = {
        "ticker": "PETR4", "tese_atual": "V2", "posicao": "LONG", "premissas": [], "riscos": [],
        "catalisadores": [], "conviccao": "ALTA", "preco_alvo_tese": None,
        "registrado_em": "2026-10-20T10:00:00+00:00", "n_versoes": 2,
    }
    historico = [
        {"tese": "V2", "conviccao": "ALTA", "preco_alvo_tese": None, "registrado_em": "2026-10-20T10:00:00+00:00"},
        {"tese": "V1", "conviccao": "BAIXA", "preco_alvo_tese": None, "registrado_em": "2026-10-10T10:00:00+00:00"},
    ]
    html_render = _capturar_render(scorecard=sc, historico=historico)
    assert "V1" in html_render and "V2" in html_render


def test_watchlist_vazia_nao_quebra():
    blocos = []
    with patch.object(radar_tab_mod.st, "pills", return_value=None), \
         patch.object(radar_tab_mod.st, "info", side_effect=lambda texto, **_k: blocos.append(texto)), \
         patch.object(radar_tab_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)):
        radar_tab_mod.render_teses.__wrapped__({"formato_numerico": "BR", "watchlist": []}, _USUARIO)
    html_render = "\n".join(blocos)
    assert "Adicione tickers" in html_render
