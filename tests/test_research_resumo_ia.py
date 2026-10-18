# -*- coding: utf-8 -*-
"""Cobertura de ui/research_tab.py:_bloco_resumo. Achado real da
auditoria 360 (2026-10-18, docs/auditoria-redesign-360.md): o resumo
exibido pra relatorios/lives de RESEARCH (data/research/resumir.py,
sempre gerado por IA - Groq) nao tinha NENHUM rotulo indicando que o
texto foi sintetizado por IA, diferente de uma manchete/documento
oficial reproduzido literalmente. Mesmo principio de risco do achado
P0 ja corrigido no Morning Call (card de EMPRESAS rotulado FATO pra
texto de IA) e do achado ja corrigido no modal de documento da CVM
(PR #77, mesma auditoria) - aqui a UI nem tinha rotulo nenhum (CVM pelo
menos tinha "Resumo", so' sem o "(gerado por IA)")."""
from unittest.mock import patch

import ui.research_tab as research_tab_mod


def test_bloco_resumo_indica_que_o_texto_e_gerado_por_ia():
    capturado = []
    with patch.object(research_tab_mod.st, "markdown", side_effect=lambda html, **k: capturado.append(html)):
        research_tab_mod._bloco_resumo("A empresa reportou crescimento de receita de 12% no trimestre.")
    assert len(capturado) == 1
    assert "gerado por ia" in capturado[0].lower()


def test_bloco_resumo_ainda_mostra_o_texto_do_resumo():
    capturado = []
    with patch.object(research_tab_mod.st, "markdown", side_effect=lambda html, **k: capturado.append(html)):
        research_tab_mod._bloco_resumo("Texto do resumo de teste.")
    assert any("Texto do resumo de teste." in c for c in capturado)
