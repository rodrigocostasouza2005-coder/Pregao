# -*- coding: utf-8 -*-
"""Coletor da Monte Bravo (data/research/montebravo.py) com o feed real
capturado pelo runner em 22/10/2026 (tests/fixtures/research/)."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import data.research as research
import data.research.montebravo as mb

_FIXTURE = Path(__file__).parent / "fixtures" / "research" / "montebravo_feed_20261022.xml"


def _resp(status=200, conteudo=None, tipo="application/rss+xml; charset=UTF-8"):
    return SimpleNamespace(status_code=status, content=conteudo if conteudo is not None else _FIXTURE.read_bytes(),
                           headers={"content-type": tipo})


def test_feed_real_so_traz_research_com_campos_normalizados():
    itens = mb.parse_feed(_FIXTURE.read_bytes())
    titulos = [i["titulo"] for i in itens]
    # 6 itens no feed: análise de empresa + carta mensal entram; imprensa,
    # evento, institucional e opinião eleitoral (seção investimentos) ficam fora
    assert titulos == ["Monte Bravo Analisa — Resultado WEG 3T26", "Carta Mensal — Outubro/2026"]
    weg = itens[0]
    assert weg["casa"] == "Monte Bravo" and weg["data"] == "2026-10-22"
    assert weg["publicado_em"] == "2026-10-22T12:43:45+00:00"
    assert weg["tickers"] == ["WEGE3"]  # citado no corpo do post (content:encoded)
    assert weg["tipo"] == "ACOES" and weg["setor"] == "Análise de Empresas"
    assert weg["link"] == "https://www.montebravo.com.br/blog/analise/analise-de-empresas/resultado-weg-3t26/"
    assert itens[1]["tipo"] == "MACRO"


def test_link_canonico_sem_rastreamento_e_dedup():
    xml = _FIXTURE.read_text(encoding="utf-8").replace(
        "carta-mensal/outubro-2026/</link>", "carta-mensal/outubro-2026/?utm_source=rss#x</link>")
    xml = xml.replace("</channel>", "<item><title>Carta Mensal — Outubro/2026</title>"
                      "<link>https://www.montebravo.com.br/blog/analise/carta-mensal/outubro-2026/</link>"
                      "<pubDate>Thu, 15 Oct 2026 13:39:54 +0000</pubDate></item></channel>")
    itens = mb.parse_feed(xml.encode("utf-8"))
    links = [i["link"] for i in itens]
    assert links.count("https://www.montebravo.com.br/blog/analise/carta-mensal/outubro-2026/") == 1


def test_item_sem_data_e_descartado_nunca_inventa_data():
    xml = _FIXTURE.read_text(encoding="utf-8").replace("<pubDate>Thu, 15 Oct 2026 13:39:54 +0000</pubDate>", "")
    titulos = [i["titulo"] for i in mb.parse_feed(xml.encode("utf-8"))]
    assert "Carta Mensal — Outubro/2026" not in titulos


def test_pagina_de_erro_ou_bloqueio_nao_vira_research():
    with patch.object(mb, "permitido", return_value=True), \
         patch.object(mb.requests, "get", return_value=_resp(403, b"<html>Access Denied</html>", "text/html")):
        assert mb.obter_relatorios() is None
    assert "HTTP 403" in mb.motivo_ultima_falha()
    with patch.object(mb, "permitido", return_value=True), \
         patch.object(mb.requests, "get", return_value=_resp(200, b"<html><body>login</body></html>", "text/html")):
        assert mb.obter_relatorios() is None
    assert "não é um feed" in mb.motivo_ultima_falha()


def test_robots_e_rede():
    with patch.object(mb, "permitido", return_value=False):
        assert mb.obter_relatorios() is None
    assert "robots" in mb.motivo_ultima_falha()
    with patch.object(mb, "permitido", return_value=True), \
         patch.object(mb.requests, "get", side_effect=TimeoutError("lento")):
        assert mb.obter_relatorios() is None
    with patch.object(mb, "permitido", return_value=True), patch.object(mb.requests, "get", return_value=_resp()):
        assert len(mb.obter_relatorios()) == 2 and mb.motivo_ultima_falha() is None


def test_casa_registrada_e_coletada_pelo_fluxo_existente():
    casa = next(c for c in research.CASAS if c["id"] == "montebravo")
    assert casa["disponivel"] and casa["obter_relatorios"] is mb.obter_relatorios
    salvos = []
    with patch.object(mb, "permitido", return_value=True), patch.object(mb.requests, "get", return_value=_resp()), \
         patch.object(research.store, "salvar_itens", side_effect=lambda itens: salvos.extend(itens) or True), \
         patch.object(research, "registrar_tentativa", lambda *a, **k: None):
        n, ok = research.coletar_casa(casa)
    assert ok and n == 2 and {i["casa"] for i in salvos} == {"Monte Bravo"}
