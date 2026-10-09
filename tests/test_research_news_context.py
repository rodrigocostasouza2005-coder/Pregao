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


# ============================================================
# bug real corrigido (2026-10-08): _painel_watchlist mostrava o bloco
# CONTEXTO RECENTE · NEWS 1x por RELATORIO com resumo cacheado, nao 1x
# por TICKER - um ticker com 2+ relatorios repetia o mesmo bloco de
# noticias 2+ vezes na tela.
# ============================================================

def _relatorio(ticker, titulo, resumo="Resumo ja cacheado."):
    return {
        "ticker": ticker, "tickers": [ticker], "titulo": titulo, "casa": "Casa Teste",
        "tipo": "ACOES", "data": "2026-10-01", "autor": "", "link": f"https://exemplo.com/{titulo}",
        "resumo": resumo,
    }


def test_8_contexto_news_aparece_so_1x_por_ticker_mesmo_com_varios_relatorios():
    relatorios = [
        _relatorio("PETR4", "Relatorio 1"),
        _relatorio("PETR4", "Relatorio 2"),
        _relatorio("PETR4", "Relatorio 3"),
    ]
    chamadas = []
    prefs = {"watchlist": ["PETR4"], "formato_numerico": "BR"}
    with patch.object(research_tab_mod, "_bloco_contexto_news", side_effect=lambda tickers: chamadas.append(list(tickers))), \
         patch.object(research_tab_mod.st, "markdown"), patch.object(research_tab_mod, "_bloco_resumo"), \
         patch.object(research_tab_mod, "_bloco_o_que_mudou"):
        research_tab_mod._painel_watchlist(prefs, relatorios, [], [], [])
    _checar("8a _bloco_contexto_news chamado exatamente 1 vez (nao 1 por relatorio)",
            len(chamadas) == 1, f"(chamadas={chamadas})")
    _checar("8b chamado com o ticker certo (PETR4)", chamadas == [["PETR4"]], f"(chamadas={chamadas})")


def test_9_contexto_news_nunca_aparece_sem_nenhum_resumo_exibido():
    relatorios = [_relatorio("VALE3", "Relatorio sem resumo ainda", resumo=None)]
    chamadas = []
    prefs = {"watchlist": ["VALE3"], "formato_numerico": "BR"}
    with patch.object(research_tab_mod, "_bloco_contexto_news", side_effect=lambda tickers: chamadas.append(list(tickers))), \
         patch.object(research_tab_mod.st, "markdown"), patch.object(research_tab_mod.st, "button", return_value=False), \
         patch.object(research_tab_mod, "_bloco_o_que_mudou"):
        research_tab_mod._painel_watchlist(prefs, relatorios, [], [], [])
    _checar("9 sem nenhum resumo exibido pro ticker -> CONTEXTO RECENTE nunca aparece",
            chamadas == [], f"(chamadas={chamadas})")


# ============================================================
# historico de recomendacao exposto na UI (2026-10-08): so' existia na
# camada de dado (data/research/historico.py:historico_ticker), nunca
# chamado por nenhuma tela - achado real desta sessao.
# ============================================================

class _ExpanderFake:
    def __init__(self, chamadas, titulo):
        chamadas.append(titulo)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_10_historico_recomendacao_nao_aparece_com_menos_de_2_snapshots():
    chamadas_expander = []
    with patch.object(research_tab_mod, "historico_ticker", return_value=[{"recomendacao": "COMPRA", "preco_alvo": 40.0, "capturado_em": "2026-10-01T10:00:00+00:00"}]), \
         patch.object(research_tab_mod.st, "expander", side_effect=lambda t: _ExpanderFake(chamadas_expander, t)):
        research_tab_mod._expander_historico_recomendacao("PETR4", "BR")
    _checar("10 so' 1 snapshot -> nenhum expander (nao ha' 'evolucao' pra mostrar)", chamadas_expander == [])


def test_11_historico_recomendacao_aparece_com_2_ou_mais_snapshots():
    historico = [
        {"recomendacao": "COMPRA", "preco_alvo": 42.0, "capturado_em": "2026-10-05T10:00:00+00:00"},
        {"recomendacao": "MANTER", "preco_alvo": 40.0, "capturado_em": "2026-09-01T10:00:00+00:00"},
    ]
    chamadas_expander = []
    chamadas_historico = []
    with patch.object(research_tab_mod, "historico_ticker", side_effect=lambda casa, ticker, limite=10: (chamadas_historico.append((casa, ticker)), historico)[1]), \
         patch.object(research_tab_mod.st, "expander", side_effect=lambda t: _ExpanderFake(chamadas_expander, t)), \
         patch.object(research_tab_mod.st, "markdown"):
        research_tab_mod._expander_historico_recomendacao("PETR4", "BR")
    _checar("11a 2+ snapshots -> expander aparece", len(chamadas_expander) == 1, f"(chamadas={chamadas_expander})")
    _checar("11b historico_ticker chamado com a casa certa (Genial Analisa) e o ticker certo",
            chamadas_historico == [("Genial Analisa", "PETR4")], f"(chamadas={chamadas_historico})")


# ============================================================
# fallback pro snapshot PERSISTIDO na watchlist (bug real corrigido,
# 2026-10-09): em producao, recomendacoes AO VIVO da Genial sao
# sempre [] (tentar_coleta_automatica=False, bloqueada por WAF no
# Cloud) - sem o fallback, "Genial: recomendacao" nunca aparecia na
# watchlist em producao, mesmo com coletor_local.py ja' tendo salvo o
# dado real em research_recomendacoes_historico (ver
# data/research/historico.py:ultimo_snapshot).
# ============================================================

def test_12_watchlist_usa_snapshot_persistido_quando_recomendacao_viva_vazia():
    prefs = {"watchlist": ["PETR4"], "formato_numerico": "BR"}
    snap = {"recomendacao": "COMPRA", "preco_alvo": 48.5, "potencial_pct": 12.3}
    capturado = []
    with patch.object(research_tab_mod, "_ultimo_snapshot_cacheado", return_value=snap) as mock_snap, \
         patch.object(research_tab_mod.st, "markdown", side_effect=lambda html, **k: capturado.append(html)), \
         patch.object(research_tab_mod, "_bloco_o_que_mudou"):
        research_tab_mod._painel_watchlist(prefs, [], [], [], [])
    mock_snap.assert_called_once_with("PETR4")
    _checar("12a sem recomendacao AO VIVO, cai pro snapshot persistido (ultimo_snapshot)", True)
    _checar("12b a recomendacao do snapshot (COMPRA) aparece de verdade na tela",
             any("COMPRA" in c and "Genial" in c for c in capturado), f"(capturado={capturado})")


def test_13_watchlist_prefere_recomendacao_viva_e_nao_consulta_o_snapshot():
    prefs = {"watchlist": ["PETR4"], "formato_numerico": "BR"}
    recomendacoes_vivas = [{"ticker": "PETR4", "recomendacao": "VENDA", "preco_alvo": 30.0, "potencial_pct": -5.0}]
    with patch.object(research_tab_mod, "_ultimo_snapshot_cacheado") as mock_snap, \
         patch.object(research_tab_mod.st, "markdown"), patch.object(research_tab_mod, "_bloco_o_que_mudou"):
        research_tab_mod._painel_watchlist(prefs, [], recomendacoes_vivas, [], [])
    _checar("13 recomendacao AO VIVO disponivel -> NUNCA consulta o snapshot persistido", mock_snap.call_count == 0)


def test_14_watchlist_sem_recomendacao_viva_nem_persistida_fica_vazia():
    prefs = {"watchlist": ["PETR4"], "formato_numerico": "BR"}
    capturado = []
    with patch.object(research_tab_mod, "_ultimo_snapshot_cacheado", return_value=None), \
         patch.object(research_tab_mod.st, "markdown", side_effect=lambda html, **k: capturado.append(html)), \
         patch.object(research_tab_mod.st, "info", side_effect=lambda t: capturado.append(t)), \
         patch.object(research_tab_mod, "_bloco_o_que_mudou"):
        research_tab_mod._painel_watchlist(prefs, [], [], [], [])
    _checar("14 nem live nem snapshot -> nenhuma linha 'Genial:' inventada", not any("Genial:" in c for c in capturado),
            f"(capturado={capturado})")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE CONTEXTO RESEARCH<->NEWS PASSARAM")
