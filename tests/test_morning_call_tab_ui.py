# -*- coding: utf-8 -*-
"""Aba MORNING CALL (ui/morning_call_tab.py): horário fora do previsto
explícito (21/10/2026 a edição saiu às ~12:58 BRT), cores do tema e um
botão por ação."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import ui.morning_call_tab as mc

TZ = ZoneInfo("America/Sao_Paulo")


def test_aviso_de_atraso_so_depois_do_horario_previsto():
    assert mc.aviso_atraso(datetime(2026, 10, 21, 8, 3, tzinfo=TZ)) is None
    assert mc.aviso_atraso(datetime(2026, 10, 21, 9, 7, tzinfo=TZ)) is None
    aviso = mc.aviso_atraso(datetime(2026, 10, 21, 12, 58, tzinfo=TZ))
    assert aviso and "fora do horário previsto" in aviso
    # registro em UTC (como vem do banco) é convertido antes de comparar
    assert mc.aviso_atraso(datetime(2026, 10, 21, 11, 5, tzinfo=ZoneInfo("UTC"))) is None


def test_html_do_briefing_usa_as_cores_do_tema():
    html = mc._bloco_editorial_html("1. RESUMO EXECUTIVO\n- [INTERPRETAÇÃO] Juros devem seguir altos.\n- Fato.")
    assert "var(--destaque)" in html and "var(--painel-bg)" in html and "var(--borda)" in html
    fonte = Path(mc.__file__).read_text(encoding="utf-8")
    trecho = fonte.split("def _bloco_editorial_html", 1)[1].split("def _exibir_texto", 1)[0]
    import re
    assert not re.search(r"#[0-9A-Fa-f]{3,6}\b", trecho), "cor fixa ignora o tema do usuário (CLARO fica ilegível)"


def test_appteste_edicao_atrasada_mostra_aviso_e_botao_unico():
    from streamlit.testing.v1 import AppTest

    script = '''
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
import ui.morning_call_tab as mc
ed = {"data": datetime(2026, 10, 21).date(), "executado_em": datetime(2026, 10, 21, 15, 58, tzinfo=ZoneInfo("UTC")),
      "conteudo": "1. RESUMO EXECUTIVO\\n- Ibovespa abriu em alta.", "status": "ENVIADA"}
with patch.object(mc, "listar_edicoes", return_value=[ed]):
    mc.render_edicao_atual({})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "gerada às 12:58" in textos and "fora do horário previsto" in textos
    rotulos = [b.label for b in at.button]
    assert rotulos.count("GERAR PRÉVIA") == 1
    assert not any("ATUALIZAR" in r for r in rotulos)  # sem prévia ainda, só a ação de gerar
