# -*- coding: utf-8 -*-
"""pregerar_resumos_news cobre os mesmos pools que o Morning Call publica
(Brasil e internacional separados), não só o TOP MERCADO combinado."""
from unittest.mock import patch

import data.news as news


def _grupo(titulo, link):
    return {"titulo": titulo, "titulos": [titulo], "fontes": [{"veiculo": "V", "link": link}], "link": link}


def test_pregerar_inclui_pool_internacional_fora_do_top_combinado():
    combinado = [_grupo("Notícia Brasil", "https://br/1")]
    brasil = [_grupo("Notícia Brasil", "https://br/1")]
    mundo = [_grupo("Wall Street closes higher", "https://int/1")]
    pedidos = []

    def resumo(titulo, *_a, **_k):
        pedidos.append(titulo)
        return {"resumo": None, "motivo_indisponivel": "teste"}

    with patch.object(news.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news.config, "obter_credenciais_groq", return_value=("chave-de-teste", "modelo")), \
         patch.object(news, "obter_top_mercado_tudo", return_value=combinado), \
         patch.object(news, "obter_top_mercado", return_value=brasil), \
         patch.object(news, "obter_top_mercado_internacional", return_value=mundo), \
         patch.object(news.ia_cache, "obter_varios", return_value={}), \
         patch.object(news, "obter_resumo_grupo", side_effect=resumo):
        stats = news.pregerar_resumos_news([])
    assert stats["grupos_considerados"] == 2  # o grupo repetido entra 1x
    assert sorted(pedidos) == ["Notícia Brasil", "Wall Street closes higher"]
    # sem resumo real, nada é contado como gerado (nunca resumo fictício)
    assert stats["gerados"] == 0 and stats["indisponiveis"] == 2


def test_pregerar_sem_chave_groq_nao_coleta_nem_chama_ia():
    with patch.object(news.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news.config, "obter_credenciais_groq", return_value=(None, None)), \
         patch.object(news, "obter_top_mercado_tudo", side_effect=AssertionError("não deveria coletar")), \
         patch.object(news, "obter_resumo_grupo", side_effect=AssertionError("não deveria chamar IA")):
        stats = news.pregerar_resumos_news(["PETR4"])
    assert stats["groq_configurado"] is False
    assert stats["gerados"] == 0


def test_falha_de_um_pool_nao_impede_os_outros():
    mundo = [_grupo("Wall Street closes higher", "https://int/1")]
    with patch.object(news.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news.config, "obter_credenciais_groq", return_value=("chave-de-teste", "modelo")), \
         patch.object(news, "obter_top_mercado_tudo", side_effect=RuntimeError("google fora")), \
         patch.object(news, "obter_top_mercado", return_value=None), \
         patch.object(news, "obter_top_mercado_internacional", return_value=mundo), \
         patch.object(news.ia_cache, "obter_varios", return_value={}), \
         patch.object(news, "obter_resumo_grupo", return_value={"resumo": None, "motivo_indisponivel": "x"}):
        stats = news.pregerar_resumos_news([])
    assert stats["grupos_considerados"] == 1
