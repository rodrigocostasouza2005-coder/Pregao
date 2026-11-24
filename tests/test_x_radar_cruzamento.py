# -*- coding: utf-8 -*-
"""Cruzamento com outras fontes (data/x_radar/cruzamento.py, secao 6 do
pedido) - mocka cobertura_cruzada_casas/obter_noticias/
existe_chave_acontecimento (nenhuma chamada de rede real). Cobre:
NUNCA promove pra CONFIRMADO so' por achar contexto (so' contexto ->
EM_VERIFICACAO no maximo), mesma_origem detecta duplicata por
chave_acontecimento (post persistido OU dentro do mesmo lote)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent / "fixtures"))

import data.x_radar.cruzamento as cruzamento_mod
from x_radar_posts import SINAL_DUPLICADO_A, SINAL_DUPLICADO_B, SINAL_RUMOR


def test_sem_contexto_fica_nao_confirmado():
    with patch.object(cruzamento_mod, "_contexto_research", return_value=[]), \
         patch.object(cruzamento_mod, "_contexto_news", return_value=[]), \
         patch("data.x_radar.store.existe_chave_acontecimento", return_value=False):
        resultado = cruzamento_mod.cruzar_fontes(SINAL_RUMOR, {"ok": True, "categoria": "rumor_nao_confirmado", "ticker": None, "tema": "rumor"}, chaves_ja_vistas=set())
    assert resultado["nivel_evidencia"] == "nivel_1_sinal_social"
    assert resultado["evidencias_confirmacao"] == []


def test_contexto_encontrado_sobe_pra_em_verificacao_nunca_pra_confirmado():
    contexto_research = [{"fonte": "research_casa", "casa": "Genial Analisa", "link": "https://x/y", "data": "2026-10-29"}]
    with patch.object(cruzamento_mod, "_contexto_research", return_value=contexto_research), \
         patch.object(cruzamento_mod, "_contexto_news", return_value=[]), \
         patch("data.x_radar.store.existe_chave_acontecimento", return_value=False):
        resultado = cruzamento_mod.cruzar_fontes(
            SINAL_RUMOR, {"ok": True, "categoria": "tese_investimento", "ticker": "WEGE3", "tema": "guidance"},
            chaves_ja_vistas=set(),
        )
    assert resultado["nivel_evidencia"] == "nivel_2_corroboracao_parcial"
    assert resultado["evidencias_confirmacao"] == []  # contexto nunca vira "confirmacao" automatica
    assert resultado["fontes_cruzadas"] == contexto_research


def test_mesma_origem_detectada_dentro_do_mesmo_lote():
    classificacao_a = {"ok": True, "categoria": "noticia", "ticker": "WEGE3", "tema": "guidance investor day"}
    classificacao_b = {"ok": True, "categoria": "noticia", "ticker": "WEGE3", "tema": "guidance investor day"}
    chaves = set()
    with patch.object(cruzamento_mod, "_contexto_research", return_value=[]), \
         patch.object(cruzamento_mod, "_contexto_news", return_value=[]), \
         patch("data.x_radar.store.existe_chave_acontecimento", return_value=False):
        resultado_a = cruzamento_mod.cruzar_fontes(SINAL_DUPLICADO_A, classificacao_a, chaves_ja_vistas=chaves)
        resultado_b = cruzamento_mod.cruzar_fontes(SINAL_DUPLICADO_B, classificacao_b, chaves_ja_vistas=chaves)
    assert resultado_a["mesma_origem"] is False  # primeiro a chegar
    assert resultado_b["mesma_origem"] is True   # mesma chave_acontecimento, chegou depois
    assert resultado_a["chave_acontecimento"] == resultado_b["chave_acontecimento"]


def test_mesma_origem_detectada_contra_o_que_ja_esta_persistido():
    with patch.object(cruzamento_mod, "_contexto_research", return_value=[]), \
         patch.object(cruzamento_mod, "_contexto_news", return_value=[]), \
         patch("data.x_radar.store.existe_chave_acontecimento", return_value=True):
        resultado = cruzamento_mod.cruzar_fontes(
            SINAL_DUPLICADO_A, {"ok": True, "categoria": "noticia", "ticker": "WEGE3", "tema": "guidance"},
            chaves_ja_vistas=set(),
        )
    assert resultado["mesma_origem"] is True


def test_contexto_news_falha_e_logada_e_degrada_pra_lista_vazia(capsys):
    """Achado real (auditoria de continuação, 2026-11-23): esta exceção
    degradava em silêncio (diferente de data/research/store.py, que
    sempre loga em falha) - direção conservadora (nivel_evidencia nunca
    é inflado por isso), mas sem rastro de diagnóstico. Agora loga a
    causa sem mudar o fallback."""
    with patch.object(cruzamento_mod, "obter_noticias", side_effect=RuntimeError("Google News indisponível")):
        resultado = cruzamento_mod._contexto_news("WEGE3")
    assert resultado == []
    saida = capsys.readouterr().out
    assert "_contexto_news" in saida and "Google News indisponível" in saida


def test_existe_chave_acontecimento_falha_e_logada_e_trata_como_nao_persistido(capsys):
    """Mesmo achado acima, no outro bloco except de cruzamento.py: uma
    falha real na consulta de duplicata (ex: Supabase fora do ar)
    degradava pra 'não está duplicado' sem nenhum log."""
    with patch.object(cruzamento_mod, "_contexto_research", return_value=[]), \
         patch.object(cruzamento_mod, "_contexto_news", return_value=[]), \
         patch("data.x_radar.store.existe_chave_acontecimento", side_effect=RuntimeError("Supabase fora do ar")):
        resultado = cruzamento_mod.cruzar_fontes(
            SINAL_RUMOR, {"ok": True, "categoria": "noticia", "ticker": "WEGE3", "tema": "guidance"},
            chaves_ja_vistas=set(),
        )
    assert resultado["mesma_origem"] is False  # mesmo fallback de antes
    saida = capsys.readouterr().out
    assert "existe_chave_acontecimento" in saida and "Supabase fora do ar" in saida


def test_classificacao_sem_relevancia_fica_nao_confirmado_mesmo_com_contexto():
    contexto_research = [{"fonte": "research_casa", "casa": "XP", "link": "https://x/y", "data": "2026-10-29"}]
    with patch.object(cruzamento_mod, "_contexto_research", return_value=contexto_research), \
         patch.object(cruzamento_mod, "_contexto_news", return_value=[]), \
         patch("data.x_radar.store.existe_chave_acontecimento", return_value=False):
        resultado = cruzamento_mod.cruzar_fontes(
            SINAL_RUMOR, {"ok": True, "categoria": "sem_relevancia", "ticker": "PETR4", "tema": "spam"},
            chaves_ja_vistas=set(),
        )
    assert resultado["nivel_evidencia"] == "nivel_1_sinal_social"
