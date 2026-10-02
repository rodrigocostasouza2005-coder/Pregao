# -*- coding: utf-8 -*-
"""Testes da fase RESEARCH <-> NEWS (contexto por ativo, 2026-10-01):
ui.research_tab._bloco_contexto_news. Mocka data.news.obter_noticias
(ja' importado por nome em ui.research_tab) - nao faz chamada de rede
nem de IA, roda em qualquer maquina sem secrets.

Uso: python tests/test_research_news_context.py (python do .venv)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.research_tab as research_tab_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


def _noticia(ticker, data, titulo, link=None):
    return {
        "ticker": ticker, "titulo": titulo, "data": data,
        "link": link or f"https://exemplo.com/{titulo}", "selo": "MENÇÃO", "score": 1,
        "veiculos": ["Veiculo Teste"], "tickers": [ticker],
    }


def test_1_research_com_ticker_mostra_noticias_relacionadas():
    noticias = [_noticia("PETR4", "2026-10-01", "Petrobras anuncia X")]
    with patch.object(research_tab_mod, "obter_noticias", return_value=noticias) as mock:
        research_tab_mod._bloco_contexto_news(["PETR4"])
    mock.assert_called_once_with("PETR4")
    _checar("1 obter_noticias chamado com o ticker certo do research", True)


def test_2_research_sem_noticias_nao_quebra():
    with patch.object(research_tab_mod, "obter_noticias", return_value=[]):
        try:
            research_tab_mod._bloco_contexto_news(["PETR4"])
            ok = True
        except Exception as e:
            ok = False
            print("      excecao:", e)
    _checar("2 sem noticias (lista vazia) nao lanca excecao", ok)

    with patch.object(research_tab_mod, "obter_noticias", return_value=None):
        try:
            research_tab_mod._bloco_contexto_news(["PETR4"])
            ok2 = True
        except Exception as e:
            ok2 = False
            print("      excecao:", e)
    _checar("2b fonte indisponivel (None) nao lanca excecao", ok2)


def test_3_multiplas_noticias_ordenadas_por_data_e_limitadas():
    noticias = [
        _noticia("PETR4", "2026-09-28", "Noticia mais antiga"),
        _noticia("PETR4", "2026-10-01", "Noticia mais recente"),
        _noticia("PETR4", "2026-09-30", "Noticia do meio"),
        _noticia("PETR4", "2026-09-15", "Noticia 4"),
        _noticia("PETR4", "2026-09-10", "Noticia 5"),
        _noticia("PETR4", "2026-09-05", "Noticia 6 (deve ficar de fora - limite 5)"),
    ]
    capturado = []
    with patch.object(research_tab_mod, "obter_noticias", return_value=noticias), \
         patch.object(research_tab_mod.st, "markdown", side_effect=lambda html, **k: capturado.append(html)):
        research_tab_mod._bloco_contexto_news(["PETR4"])
    linhas_noticia = [c for c in capturado if "exemplo.com" in c]
    _checar("3a limite de 5 noticias respeitado", len(linhas_noticia) == research_tab_mod._LIMITE_CONTEXTO_NEWS,
             f"(qtd={len(linhas_noticia)})")
    _checar("3b ordenado por data DESC (mais recente primeiro)",
             "Noticia mais recente" in linhas_noticia[0] and "Noticia mais antiga" not in linhas_noticia[0])
    _checar("3c a noticia mais antiga (6ª, fora do limite) nao aparece",
             not any("deve ficar de fora" in l for l in linhas_noticia))


def test_4_noticia_de_ticker_diferente_nao_aparece():
    """obter_noticias(ticker) ja' filtra por ticker na origem (mesma
    funcao/identificador que NEWS usa) - este teste confirma que
    _bloco_contexto_news NUNCA pede noticia de um ticker que nao foi
    passado (nunca mistura tickers do item de research com outros)."""
    chamadas = []

    def _fake_obter_noticias(ticker):
        chamadas.append(ticker)
        if ticker == "PETR4":
            return [_noticia("PETR4", "2026-10-01", "Noticia da Petrobras")]
        return [_noticia("VALE3", "2026-10-01", "Noticia da Vale - NAO deveria aparecer pra PETR4")]

    with patch.object(research_tab_mod, "obter_noticias", side_effect=_fake_obter_noticias):
        research_tab_mod._bloco_contexto_news(["PETR4"])
    _checar("4 so' chama obter_noticias com o(s) ticker(s) do item (PETR4), nunca VALE3",
             chamadas == ["PETR4"], f"(chamadas={chamadas})")


def test_5_ticker_inexistente_ou_nulo_nao_chama_fonte():
    chamadas = []
    with patch.object(research_tab_mod, "obter_noticias", side_effect=lambda t: chamadas.append(t)):
        research_tab_mod._bloco_contexto_news([])
        research_tab_mod._bloco_contexto_news(None)
    _checar("5 tickers vazio/None nunca chama obter_noticias (nenhum ticker pra buscar)",
             chamadas == [], f"(chamadas={chamadas})")


def test_6_nao_ha_n_mais_1_queries():
    """1 item de research com 1 ticker -> exatamente 1 chamada a
    obter_noticias (nunca 1 por noticia nem 1 por linha da lista)."""
    chamadas = []

    def _fake_obter_noticias(ticker):
        chamadas.append(ticker)
        return [_noticia(ticker, "2026-10-01", f"Noticia {i}") for i in range(3)]

    with patch.object(research_tab_mod, "obter_noticias", side_effect=_fake_obter_noticias):
        research_tab_mod._bloco_contexto_news(["PETR4"])
    _checar("6 exatamente 1 chamada a obter_noticias por ticker do item (3 noticias retornadas, so' 1 chamada)",
             len(chamadas) == 1, f"(chamadas={chamadas})")

    # multiplos tickers no MESMO item (ex: relatorio setorial) -> 1 chamada POR TICKER, nunca mais
    chamadas.clear()
    with patch.object(research_tab_mod, "obter_noticias", side_effect=_fake_obter_noticias):
        research_tab_mod._bloco_contexto_news(["PETR4", "VALE3"])
    _checar("6b 2 tickers no item -> exatamente 2 chamadas (1 por ticker, nao mais)",
             chamadas == ["PETR4", "VALE3"], f"(chamadas={chamadas})")


def test_7_nenhum_resumo_de_ia_e_chamado():
    chamadas_ia = []
    with patch.object(research_tab_mod, "obter_noticias", return_value=[_noticia("PETR4", "2026-10-01", "Noticia")]), \
         patch.object(research_tab_mod, "obter_resumo", side_effect=lambda *a, **k: chamadas_ia.append("research_resumo")):
        research_tab_mod._bloco_contexto_news(["PETR4"])
    _checar("7 _bloco_contexto_news nunca chama nenhuma funcao de resumo de IA",
             chamadas_ia == [], f"(chamadas_ia={chamadas_ia})")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE CONTEXTO RESEARCH<->NEWS PASSARAM")
