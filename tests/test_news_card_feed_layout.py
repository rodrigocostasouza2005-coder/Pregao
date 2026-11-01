# -*- coding: utf-8 -*-
"""Redesign do card do feed editorial de NOTÍCIAS (2026-10-19, pedido
explícito: a formatação visual continuava praticamente igual à anterior
mesmo depois do redesign de conteúdo do resumo) - ui/news_tab.py:
_cartao_noticia. Cobre:

1. selo "IA" aparece no teaser com o tooltip certo por qualidade_texto
   (full_text/partial_text/snippet_only/extraction_failed/ausente).
2. nenhum selo nem teaser quando não há resumo (`resultado` None ou sem
   'resumo') - card não quebra, só não desenha essa parte.
3. miniatura sem imagem cai no fallback (iniciais), nunca quebra.
4. manchete/resumo curtos e longos não derrubam a função (regressão de
   layout, não de conteúdo - a truncagem do teaser já é testada em
   outro arquivo).

Bare mode (sem ScriptRunContext real) - mesmo padrão de
tests/test_radar_tab_fontes_ui.py: st.columns/st.button/st.markdown
funcionam fora de uma sessão Streamlit real, só avisam no log.
_cartao_noticia não é decorada (@st.fragment/@st.dialog), chama-se
direto, sem precisar de .__wrapped__."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.news_tab as news_tab_mod

_ITEM_BASE = {
    "titulo": "Alfa revisa plano de investimentos para 2027",
    "titulos": ["Alfa revisa plano de investimentos para 2027"],
    "veiculos": ["InfoMoney"],
    "fontes": [{"veiculo": "InfoMoney", "link": "https://news.google.com/alfa"}],
    "fontes_count": 1,
    "data": "2026-10-19T10:00:00-03:00",
    "link": "https://news.google.com/alfa",
    "score": 70,
    "selo": "PROVÁVEL",
    "regras": [],
    "tickers": [],
}


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _renderizar(item, resultado):
    """Chama _cartao_noticia de verdade e devolve todo o HTML passado a
    st.markdown (st.columns/st.button em bare mode não fazem nada, só
    não quebram - ver docstring do módulo)."""
    blocos = []
    with patch.object(news_tab_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)), \
         patch.object(news_tab_mod.st, "columns", side_effect=lambda *a, **k: [_FakeCtx(), _FakeCtx()]), \
         patch.object(news_tab_mod.st, "button", return_value=False):
        news_tab_mod._cartao_noticia(item, 0, False, "teste", [], resultado)
    return "\n".join(blocos)


def test_1a_ia_chip_full_text():
    resultado = {"resumo": "RESUMO:\nA Alfa anunciou revisão do plano de investimentos.",
                 "qualidade_texto": "full_text"}
    html_render = _renderizar(_ITEM_BASE, resultado)
    assert "news-ia-chip" in html_render
    assert "news-ia-chip-fraco" not in html_render
    assert "texto completo da matéria" in html_render


def test_1b_ia_chip_partial_text():
    resultado = {"resumo": "RESUMO:\nSíntese parcial.", "qualidade_texto": "partial_text"}
    html_render = _renderizar(_ITEM_BASE, resultado)
    assert "leitura parcial" in html_render.lower()
    assert "news-ia-chip-fraco" not in html_render


def test_1c_ia_chip_snippet_only_e_marcado_como_evidencia_fraca():
    resultado = {"resumo": "RESUMO:\nSó manchete.", "qualidade_texto": "snippet_only"}
    html_render = _renderizar(_ITEM_BASE, resultado)
    assert "news-ia-chip-fraco" in html_render
    assert "só manchetes" in html_render.lower()


def test_1d_ia_chip_extraction_failed_e_marcado_como_evidencia_fraca():
    resultado = {"resumo": "RESUMO:\nSem texto suficiente.", "qualidade_texto": "extraction_failed"}
    html_render = _renderizar(_ITEM_BASE, resultado)
    assert "news-ia-chip-fraco" in html_render


def test_1e_ia_chip_sem_qualidade_texto_cai_no_rotulo_generico():
    """Compatibilidade com resumo cacheado antes da qualidade_texto existir."""
    resultado = {"resumo": "RESUMO:\nTexto qualquer."}
    html_render = _renderizar(_ITEM_BASE, resultado)
    assert "class='news-ia-chip'" in html_render
    assert "title='Gerado por IA'" in html_render


def test_2a_sem_resumo_nenhum_chip_nenhum_teaser_e_nao_quebra():
    html_render = _renderizar(_ITEM_BASE, {"resumo": None, "motivo_indisponivel": "cota"})
    assert "news-ia-chip" not in html_render
    assert "news-item-resumo" not in html_render


def test_2b_resultado_none_nao_quebra():
    html_render = _renderizar(_ITEM_BASE, None)
    assert "news-ia-chip" not in html_render
    assert "news-item-resumo" not in html_render
    # sem foto cacheada nao ha miniatura (nem quadrado de iniciais): o
    # texto ocupa a largura toda; a manchete continua sendo renderizada
    assert "news-item-thumb-wrap" not in html_render


def test_3a_sem_imagem_nao_renderiza_miniatura():
    """Redesign 2026-11-01: o quadrado de iniciais do veiculo ("MO", "IN")
    em todo item sem foto era so' ruido visual - sem foto, sem miniatura."""
    html_render = _renderizar(_ITEM_BASE, {"resumo": None})
    assert "news-item-thumb-wrap" not in html_render
    assert "news-item-thumb-fallback" not in html_render
    assert "<img" not in html_render


def test_3b_com_imagem_usa_img_com_lazy_e_sem_referer():
    resultado = {"resumo": None, "imagem": "https://exemplo.com/foto.jpg"}
    html_render = _renderizar(_ITEM_BASE, resultado)
    assert "<img src='https://exemplo.com/foto.jpg'" in html_render
    assert "loading='lazy'" in html_render
    assert "referrerpolicy='no-referrer'" in html_render


def test_4a_manchete_e_resumo_longos_nao_quebram():
    item = dict(_ITEM_BASE, titulo="M" * 220, titulos=["M" * 220])
    resumo_longo = "RESUMO:\n" + ("Frase longa de teste. " * 60)
    html_render = _renderizar(item, {"resumo": resumo_longo, "qualidade_texto": "full_text"})
    assert "news-item-resumo" in html_render


def test_4b_resumo_curtissimo_nao_quebra():
    html_render = _renderizar(_ITEM_BASE, {"resumo": "RESUMO:\nCurto.", "qualidade_texto": "full_text"})
    assert "news-item-resumo" in html_render
