# -*- coding: utf-8 -*-
"""Teste do achado real (2026-10-08): data/news.py:_tickers_no_titulo
(usado pro TOP MERCADO marcar tickers citados na manchete, exibido como
tag no card/dialog - ver ui/news_tab.py:_abrir_card/_meta_noticia_html)
casava qualquer "4 letras + 1-2 digitos" como se fosse ticker da B3,
incluindo codigo de contrato futuro (ex: WDOV26, WINV26, DOLV26 - mesma
forma de uma acao/BDR). Corrigido filtrando pelo sufixo numerico REAL de
ticker B3 (3/4/5-8 acao, 11 units/FIIs, 32-39 BDR).

Sem rede/IA. Uso: python tests/test_news_tickers.py (venv do projeto)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.news import _tickers_no_titulo

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


def test_1_acao_real_e_reconhecida():
    tickers = _tickers_no_titulo("PETR4 anuncia novo investimento e VALE3 sobe no pregão")
    _checar("1 PETR4/VALE3 (sufixos 4/3, acoes reais) reconhecidos", tickers == ["PETR4", "VALE3"], f"(tickers={tickers})")


def test_2_bdr_e_reconhecido():
    tickers = _tickers_no_titulo("AAPL34 fecha em alta na B3 após resultado trimestral")
    _checar("2 AAPL34 (sufixo 34, BDR real) reconhecido", tickers == ["AAPL34"])


def test_3_unit_e_reconhecido():
    tickers = _tickers_no_titulo("KLBN11 distribui proventos extraordinários")
    _checar("3 KLBN11 (sufixo 11, unit real) reconhecido", tickers == ["KLBN11"])


def test_4_codigo_de_contrato_futuro_nunca_e_tratado_como_ticker():
    # WDOV26/WINV26 (dolar/Ibovespa futuro, vencimento out/2026) tem a
    # MESMA forma regex (4 letras + 2 digitos) de um ticker, mas sufixo
    # "26" nao e' nenhum tipo de classe de acao/BDR/unit valido na B3.
    tickers = _tickers_no_titulo("WDOV26 e WINV26 recuam após decisão do Copom, PETR4 também cai")
    _checar("4 WDOV26/WINV26 (contrato futuro) NUNCA aparecem como ticker",
             "WDOV26" not in tickers and "WINV26" not in tickers, f"(tickers={tickers})")
    _checar("4b PETR4 (acao real na mesma manchete) continua reconhecido", "PETR4" in tickers)


def test_5_sufixo_invalido_generico_e_descartado():
    tickers = _tickers_no_titulo("ABCD99 é um código qualquer sem sentido na B3")
    _checar("5 sufixo '99' (nenhuma classe real de acao/BDR/unit) e' descartado", tickers == [], f"(tickers={tickers})")


def test_6_sem_nenhum_ticker_na_manchete():
    tickers = _tickers_no_titulo("Ibovespa fecha em queda nesta sessão")
    _checar("6 manchete sem nenhum ticker -> lista vazia", tickers == [])


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE TICKERS-NA-MANCHETE (NEWS) PASSARAM")
