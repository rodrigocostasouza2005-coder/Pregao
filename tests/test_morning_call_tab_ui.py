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


def test_aviso_quando_a_edicao_de_hoje_nao_saiu():
    from datetime import date
    quinta_11h40 = datetime(2026, 10, 22, 11, 40, tzinfo=TZ)
    aviso = mc.aviso_edicao_de_hoje_ausente(date(2026, 10, 21), quinta_11h40)
    assert aviso and "22/10" in aviso and "21/10" in aviso
    # ainda dentro do horário previsto, com edição de hoje, ou fim de semana: nada
    assert mc.aviso_edicao_de_hoje_ausente(date(2026, 10, 21), datetime(2026, 10, 22, 9, 0, tzinfo=TZ)) is None
    assert mc.aviso_edicao_de_hoje_ausente(date(2026, 10, 22), quinta_11h40) is None
    assert mc.aviso_edicao_de_hoje_ausente(date(2026, 10, 23), datetime(2026, 10, 24, 11, 0, tzinfo=TZ)) is None
    assert "ainda não foi gerada" in mc.aviso_edicao_de_hoje_ausente(None, quinta_11h40)


def test_noticia_vira_manchete_clicavel_e_marca_traducao():
    html_pt = mc._bloco_editorial_html(
        "MORNING CALL — 22/10/2026\nGerado em 22/10/2026 08:03\n\n3. EXTERIOR\n"
        "- Inflação do Reino Unido sobe (original: UK inflation jumps) — https://www.cnbc.com/a\n"
        "- IBM stock falls [em inglês - tradução indisponível nesta edição] — https://www.marketwatch.com/b\n")
    assert "href='https://www.cnbc.com/a'" in html_pt and ">Inflação do Reino Unido sobe</a>" in html_pt
    assert "TRADUZIDO" in html_pt and "original: UK inflation jumps" in html_pt
    assert "EN · SEM TRADUÇÃO" in html_pt and "tradução indisponível nesta edição]" not in html_pt
    assert "cnbc.com ↗" in html_pt
    # cabeçalho sem a caixa "BRIEFING" repetindo o título; "Gerado em" fica como texto discreto
    assert "BRIEFING" not in html_pt and "MORNING CALL — 22/10/2026" not in html_pt
    assert "Gerado em 22/10/2026 08:03" in html_pt


def test_linha_sem_link_continua_texto_e_html_e_escapado():
    out = mc._bloco_editorial_html("1. RESUMO EXECUTIVO\n- Ibovespa <b>sobe</b> 1%\n")
    assert "&lt;b&gt;sobe&lt;/b&gt;" in out
    assert mc._item_noticia_html("Ibovespa sobe 1%") is None
