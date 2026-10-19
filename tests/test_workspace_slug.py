# -*- coding: utf-8 -*-
"""ui/workspace.py: regressao do achado real da missao de redesign
2026-10-19 - aba_id com espaco/acento (so' "VISÃO GERAL", entre as 3
abas que usam o workspace modular - MERCADO/MACRO sao so' ASCII) fazia
o Streamlit sanitizar o key= de um jeito (confirmado inspecionando a
classe real no DOM: "VISÃO GERAL" -> "VIS-O-GERAL") e o CSS/JS gerados
aqui buscarem por outro (aba_id cru, nunca sanitizado) - o seletor
nunca batia, e o workspace inteiro (posicao/altura/overflow via CSS,
drag/resize via JS) ficava silenciosamente inerte so' nessa aba, sem
nenhum erro visivel (o navegador cai pro fluxo normal, que nao
"parece" quebrado)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.workspace as workspace


def test_slug_aba_preserva_ascii_puro_sem_mudar_nada():
    assert workspace._slug_aba("MERCADO") == "MERCADO"
    assert workspace._slug_aba("MACRO") == "MACRO"


def test_slug_aba_sanitiza_acento_e_espaco_igual_ao_streamlit_de_verdade():
    # "VIS-O-GERAL" confirmado inspecionando a classe real no DOM
    # (getComputedStyle/className), nao suposto - ver evidencia da
    # missao de redesign 2026-10-19.
    assert workspace._slug_aba("VISÃO GERAL") == "VIS-O-GERAL"


def test_gerar_css_usa_o_slug_nunca_o_aba_id_cru():
    layout = {"p1": {"x": 0.0, "y": 0.0, "w": 100.0, "h": 18.0}}
    css = workspace._gerar_css("VISÃO GERAL", layout, {"p1"})
    assert "VIS-O-GERAL" in css
    assert "VISÃO GERAL" not in css  # seletor cru nunca bateria com a classe real


def test_script_js_usa_o_slug_nunca_o_aba_id_cru():
    script = workspace._script_js("VISÃO GERAL", ["p1"], {"p1": {"x": 0.0, "y": 0.0, "w": 100.0, "h": 18.0}})
    assert "VIS-O-GERAL" in script
    assert "VISÃO GERAL" not in script


def test_bridge_key_usa_o_slug():
    assert workspace._bridge_key("VISÃO GERAL") == "workspace_bridge_VIS-O-GERAL"
