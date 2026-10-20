# -*- coding: utf-8 -*-
"""Bug real corrigido 2026-10-19: o modal de noticia (ui/news_tab.py:
_abrir_card) mostrava a nota de ressalva (.news-parcial-nota) tambem pra
qualidade_texto == "full_text" - full_text e' justamente o caso em que o
texto INTEGRAL da materia foi acessado, nao deveria carregar nenhum
aviso de leitura parcial/incompleta. Este teste confere os 4 niveis
(full_text/partial_text/snippet_only/sem-chave) e garante que so' o
full_text fica sem nota."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.news_tab as news_tab_mod

_N_BASE = {
    "titulo": "Empresa X anuncia resultado trimestral",
    "fontes": [{"veiculo": "Fonte A", "link": "https://a.com"}],
    "titulos": None, "veiculos": ["Fonte A"], "link": "https://a.com", "data": "2026-10-19T10:00:00+00:00",
    "fontes_count": 1, "tickers": [], "selo": "", "score": 50, "regras": [], "cvm_confirmacao": None,
}


def _render_com_resultado(resultado):
    blocos = []
    with patch.object(news_tab_mod, "obter_resumo_grupo", return_value=resultado), \
         patch.object(news_tab_mod, "ordenar_fontes_para_resumo", return_value=_N_BASE["fontes"]), \
         patch.object(news_tab_mod, "_renderizar_capa"), \
         patch.object(news_tab_mod, "_bloco_contexto_research"), \
         patch.object(news_tab_mod, "_vinculos_noticia"), \
         patch.object(news_tab_mod.st, "markdown", side_effect=lambda t, **_k: blocos.append(t)), \
         patch.object(news_tab_mod.st, "caption", side_effect=lambda t, **_k: blocos.append(t)), \
         patch.object(news_tab_mod.st, "link_button"), \
         patch.object(news_tab_mod.st, "spinner"):
        # @st.dialog e' da mesma familia de @st.fragment: em bare mode (sem
        # ScriptRunContext real) nao executa o corpo sem __wrapped__ (ver
        # memoria feedback_streamlit_fragment_bare_mode).
        news_tab_mod._abrir_card.__wrapped__(_N_BASE, [])
    return "\n".join(blocos)


def test_full_text_nao_mostra_nenhum_aviso_de_parcial():
    resultado = {"resumo": "RESUMO:\nTexto completo da matéria.", "imagem": None, "parcial": False,
                 "qualidade_texto": "full_text", "motivo_indisponivel": None}
    texto = _render_com_resultado(resultado)
    assert "news-parcial-nota" not in texto


def test_partial_text_nao_afirma_que_texto_completo_foi_acessado():
    resultado = {"resumo": "RESUMO:\nA empresa reportou crescimento.", "imagem": None, "parcial": True,
                 "qualidade_texto": "partial_text", "motivo_indisponivel": None}
    texto = _render_com_resultado(resultado)
    assert "news-parcial-nota" in texto
    assert "fragmentos de texto extraídos" in texto
    assert "matéria completa" not in texto or "não representa necessariamente" in texto


def test_snippet_only_informa_que_usa_so_manchetes():
    resultado = {"resumo": "RESUMO:\nFontes reportam mudança na diretoria.", "imagem": None, "parcial": True,
                 "qualidade_texto": "snippet_only", "motivo_indisponivel": None}
    texto = _render_com_resultado(resultado)
    assert "news-parcial-nota" in texto
    assert "apenas manchetes" in texto


def test_resultado_sem_qualidade_texto_mas_parcial_ainda_mostra_nota():
    """Compatibilidade com cache/resultado anterior a' introducao de
    qualidade_texto - so' tinha o booleano "parcial"."""
    resultado = {"resumo": "RESUMO:\nAlgo aconteceu.", "imagem": None, "parcial": True,
                 "motivo_indisponivel": None}
    texto = _render_com_resultado(resultado)
    assert "news-parcial-nota" in texto


def test_resultado_sem_qualidade_texto_e_sem_parcial_nao_mostra_nota():
    resultado = {"resumo": "RESUMO:\nAlgo aconteceu.", "imagem": None, "parcial": False,
                 "motivo_indisponivel": None}
    texto = _render_com_resultado(resultado)
    assert "news-parcial-nota" not in texto
