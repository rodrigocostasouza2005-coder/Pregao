# -*- coding: utf-8 -*-
"""Aba SISTEMA > AGENDAMENTOS (ui/sistema_tab.py) - missão "agendamento"
2026-11-13: smoke-test real via streamlit.testing.v1.AppTest (mesmo
padrão de tests/test_morning_call_tab_ui.py) confirmando que a aba
renderiza sem excecao tanto com dado real (OK/atrasado/sem dado) quanto
com as 3 fontes indisponíveis - nunca finge status quando não há dado."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit.testing.v1 import AppTest

_LINHAS_MISTAS = """
from unittest.mock import patch
import ui.sistema_tab as st_mod
with patch.object(st_mod, "saude_agendamentos", return_value=[
    {"rotulo": "Morning Call", "ultima_tentativa_em": None, "ultimo_sucesso_em": None,
     "ultimo_erro": None, "execucao_ok": None, "disponivel": False, "atrasado": None, "motivo_atraso": None},
    {"rotulo": "Radar de Quedas", "ultima_tentativa_em": "2026-11-13T14:00:00+00:00",
     "ultimo_sucesso_em": "2026-11-13T14:00:00+00:00", "ultimo_erro": None, "execucao_ok": True,
     "disponivel": True, "atrasado": False, "motivo_atraso": None},
    {"rotulo": "Comite de Investimentos (analise noturna)", "ultima_tentativa_em": "2026-11-12T22:45:00+00:00",
     "ultimo_sucesso_em": None, "ultimo_erro": "falhou", "execucao_ok": False, "disponivel": True,
     "atrasado": True, "motivo_atraso": "sem rodada hoje"},
]):
    st_mod.render_sistema({})
"""


def test_aba_agendamentos_renderiza_sem_excecao_com_estados_mistos():
    at = AppTest.from_string(_LINHAS_MISTAS)
    at.run()
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "SEM DADO" in textos  # Morning Call indisponível
    assert "EM DIA" in textos  # Radar OK
    assert "ATRASADO" in textos  # Comitê atrasado
    assert "sem rodada hoje" in textos  # motivo_atraso aparece


def test_aba_agendamentos_renderiza_sem_excecao_tudo_indisponivel():
    script = """
from unittest.mock import patch
import ui.sistema_tab as st_mod
with patch.object(st_mod, "saude_agendamentos", return_value=[
    {"rotulo": r, "ultima_tentativa_em": None, "ultimo_sucesso_em": None, "ultimo_erro": None,
     "execucao_ok": None, "disponivel": False, "atrasado": None, "motivo_atraso": None}
    for r in ("Morning Call", "Radar de Quedas", "Comite de Investimentos (analise noturna)")
]):
    st_mod.render_sistema({})
"""
    at = AppTest.from_string(script)
    at.run()
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert textos.count("SEM DADO") == 4  # 3 badges de linha + 1x na legenda (st.caption, achado real: também cai em at.markdown)
    assert textos.count("🔘 SEM DADO") == 3  # contagem robusta: só os badges de linha usam esse emoji


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
