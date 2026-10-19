# -*- coding: utf-8 -*-
"""qualidade_texto (data/news.py:_gerar_resumo_grupo) tem 2 niveis dentro
do mesmo "parcial" - partial_text (trechos REAIS de outra materia sobre
o mesmo fato) e snippet_only (so' manchetes, nenhum texto baixado). Ate'
2026-10-19 o modal (ui/news_tab.py:_abrir_card) mostrava a MESMA nota
genérica pros dois casos, escondendo que um tem evidencia real por tras
e o outro nao. Este teste confere que a nota agora diferencia os 2."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.news_tab as news_tab_mod

_N_BASE = {
    "titulo": "Empresa X anuncia resultado trimestral", "fontes": [{"veiculo": "Fonte A", "link": "https://a.com"}],
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
        # ScriptRunContext real) nao executa o corpo - precisa de
        # __wrapped__ (ver memoria feedback_streamlit_fragment_bare_mode).
        news_tab_mod._abrir_card.__wrapped__(_N_BASE, [])
    return "\n".join(blocos)


def test_partial_text_cita_trecho_real_de_outra_materia():
    resultado = {"resumo": "RESUMO:\nA empresa reportou crescimento.", "imagem": None, "parcial": True,
                 "qualidade_texto": "partial_text", "motivo_indisponivel": None}
    texto = _render_com_resultado(resultado)
    assert "trechos reais extraídos" in texto
    assert "só a partir das manchetes" not in texto


def test_snippet_only_avisa_que_nenhum_texto_foi_acessado():
    resultado = {"resumo": "RESUMO:\nFontes reportam mudança na diretoria.", "imagem": None, "parcial": True,
                 "qualidade_texto": "snippet_only", "motivo_indisponivel": None}
    texto = _render_com_resultado(resultado)
    assert "só a partir das manchetes" in texto
    assert "trechos reais extraídos" not in texto


def test_resultado_sem_qualidade_texto_cai_na_nota_generica():
    """Compatibilidade com cache/fixture anterior a ABA 5 (sem a chave)."""
    resultado = {"resumo": "RESUMO:\nAlgo aconteceu.", "imagem": None, "parcial": True,
                 "motivo_indisponivel": None}
    texto = _render_com_resultado(resultado)
    assert "texto completo da matéria não foi acessado" in texto


def test_full_text_nao_mostra_nenhuma_nota_de_parcial():
    resultado = {"resumo": "RESUMO:\nTexto completo da matéria.", "imagem": None, "parcial": False,
                 "qualidade_texto": "full_text", "motivo_indisponivel": None}
    texto = _render_com_resultado(resultado)
    assert "news-parcial-nota" not in texto
