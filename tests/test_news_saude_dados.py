# -*- coding: utf-8 -*-
"""Testes de instrumentacao de SAUDE DOS DADOS em
data/news.py:obter_noticias_watchlist - achado real (auditoria missao
coletores, 2026-10-13): a linha "NEWS" do painel (data/saude_dados.py)
so' refletia obter_top_mercado_tudo (pool BRASIL+INTERNACIONAL); a
busca POR TICKER (o que a aba NOTICIAS de verdade usa pra watchlist)
nunca chamava registrar_tentativa - se quebrasse isolada, o painel
continuava mostrando "NEWS: Coleta OK" com a aba principal vazia.
Corrigido com uma linha separada ("NEWS (watchlist)", mesma categoria
Noticias) - ver REGISTRO_COLETORES em data/saude_dados.py.

Mocka obter_noticias/registrar_tentativa - nunca faz chamada de rede.

Uso: python tests/test_news_saude_dados.py (venv)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.news as news_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


def test_1_todos_os_tickers_ok_registra_sucesso_nao_parcial():
    def _fake_obter_noticias(ticker):
        return [{"ticker": ticker, "titulo": f"noticia de {ticker}", "data": "2026-10-13T10:00:00-03:00",
                  "titulos": [f"noticia de {ticker}"], "link": "https://x", "fontes": [], "veiculos": [],
                  "fontes_count": 0, "score": 50, "selo": "", "regras": [], "cvm_confirmacao": None, "tickers": []}]

    with patch.object(news_mod, "obter_noticias", side_effect=_fake_obter_noticias), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        todas, falhas = news_mod.obter_noticias_watchlist(["PETR4", "VALE3"])

    _checar("1a nenhuma falha reportada", falhas == [], f"(falhas={falhas})")
    _checar("1b registra NEWS (watchlist) execucao_ok=True",
            mock_reg.call_args.args[0] == "NEWS (watchlist)" and mock_reg.call_args.kwargs.get("execucao_ok") is True,
            f"(call={mock_reg.call_args})")
    _checar("1c nao marca parcial (nenhum ticker falhou)",
            mock_reg.call_args.kwargs.get("parcial") is False, f"(call={mock_reg.call_args})")


def test_2_alguns_tickers_falham_registra_sucesso_parcial():
    def _fake_obter_noticias(ticker):
        return None if ticker == "VALE3" else []

    with patch.object(news_mod, "obter_noticias", side_effect=_fake_obter_noticias), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        todas, falhas = news_mod.obter_noticias_watchlist(["PETR4", "VALE3"])

    _checar("2a so VALE3 em falhas", falhas == ["VALE3"], f"(falhas={falhas})")
    _checar("2b registra execucao_ok=True (PETR4 respondeu) E parcial=True",
            mock_reg.call_args.kwargs.get("execucao_ok") is True and mock_reg.call_args.kwargs.get("parcial") is True,
            f"(call={mock_reg.call_args})")


def test_3_todos_os_tickers_falham_registra_falha_real():
    """Bug que esta correcao previne: antes, isso nunca aparecia em
    SAUDE DOS DADOS - o painel continuava mostrando a linha "NEWS"
    (TOP MERCADO) como OK mesmo com a busca por ticker 100% quebrada."""
    with patch.object(news_mod, "obter_noticias", return_value=None), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        todas, falhas = news_mod.obter_noticias_watchlist(["PETR4", "VALE3"])

    _checar("3a todos os tickers em falhas", sorted(falhas) == ["PETR4", "VALE3"], f"(falhas={falhas})")
    _checar("3b registra NEWS (watchlist) execucao_ok=False",
            mock_reg.call_args.kwargs.get("execucao_ok") is False, f"(call={mock_reg.call_args})")


def test_4_watchlist_vazia_nao_registra_nada():
    """Watchlist vazia nao e' "falha" (nada pra buscar) - nao deve virar
    um FALHOU/NAO_COMPROVADO artificial no painel."""
    with patch.object(news_mod, "obter_noticias") as mock_obter, \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        todas, falhas = news_mod.obter_noticias_watchlist([])

    _checar("4a obter_noticias nunca chamado", mock_obter.call_count == 0)
    _checar("4b registrar_tentativa nunca chamado", mock_reg.call_count == 0)
    _checar("4c resultado vazio, sem falha", todas == [] and falhas == [])


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass  # ja' registrado em _FALHAS por _checar

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE SAUDE DOS DADOS (NEWS WATCHLIST) PASSARAM")
