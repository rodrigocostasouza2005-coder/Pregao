# -*- coding: utf-8 -*-
"""Testes da FASE 3 (expansao B3 + EUA, auditoria 2026-10-09): cadastro
unificado de ativos (config.info_ativo/ATIVOS_CADASTRO_US), normalizacao
de ticker pro yfinance (data/prices.py:_para_symbol_yf - antes colava
'.SA' em QUALQUER ticker, quebrando tickers US), formatacao de valor
por moeda (config.formatar_valor_mercado) e escolha do indice de
referencia pro beta por mercado (data/prices.py:_calcular_beta). Mocka
yf.Ticker - nunca faz chamada de rede real.

Grupo-piloto: NVDA/AAPL/MSFT (EUA). Regressao BR: PETR4/VALE3/ITUB4/
WEGE3 (nenhum desses esta' em ATIVOS_CADASTRO_US de proposito - testa
que o caminho padrao B3 continua intacto).

Uso: python tests/test_ativos_us.py (python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import data.prices as prices_mod
from data.prices import _calcular_beta, _para_symbol_yf

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        # 2026-10-10: faz a checagem REALMENTE falhar sob pytest (antes so'
        # imprimia e guardava em _FALHAS, lido so' pelo runner `__main__` -
        # sob pytest toda funcao test_* passava mesmo com condicao=False,
        # a menos que outra linha lancasse excecao por acidente; ver
        # investigacao registrada no relatorio da auditoria 2026-10-10)
        raise AssertionError(f"{nome} {detalhe}".strip())


# ============================================================
# 1. cadastro unificado (config.info_ativo)
# ============================================================

def test_1_ticker_br_nao_cadastrado_cai_no_default_b3():
    for ticker in ("PETR4", "VALE3", "ITUB4", "WEGE3"):
        info = config.info_ativo(ticker)
        _checar(f"1 {ticker} default B3/BRL", info == {
            "ticker": ticker, "mercado": "B3", "pais": "Brasil", "moeda": "BRL", "simbolo_provedor": ticker,
        })


def test_2_ticker_us_piloto_tem_mercado_moeda_corretos():
    info = config.info_ativo("NVDA")
    _checar("2a NVDA mercado NASDAQ", info["mercado"] == "NASDAQ")
    _checar("2b NVDA moeda USD", info["moeda"] == "USD")
    _checar("2c NVDA simbolo_provedor sem sufixo", info["simbolo_provedor"] == "NVDA")


def test_3_info_ativo_normaliza_minuscula_e_espaco():
    _checar("3 ' nvda ' normalizado -> NVDA", config.info_ativo(" nvda ")["ticker"] == "NVDA")


# ============================================================
# 2. normalizacao de simbolo pro yfinance (_para_symbol_yf)
# ============================================================

def test_4_ticker_br_continua_ganhando_sufixo_sa():
    for ticker in ("PETR4", "VALE3", "ITUB4", "WEGE3"):
        _checar(f"4 {ticker} -> {ticker}.SA (regressao B3 intacta)", _para_symbol_yf(ticker) == f"{ticker}.SA")


def test_5_ticker_us_piloto_nao_ganha_sufixo_sa():
    for ticker in ("NVDA", "AAPL", "MSFT"):
        _checar(f"5 {ticker} -> {ticker} sem .SA", _para_symbol_yf(ticker) == ticker)


def test_6_indice_e_moeda_continuam_sem_sufixo():
    _checar("6a ^BVSP inalterado", _para_symbol_yf("^BVSP") == "^BVSP")
    _checar("6b USDBRL=X inalterado", _para_symbol_yf("USDBRL=X") == "USDBRL=X")


def test_7_ticker_us_ja_com_sufixo_sa_e_preservado():
    """Caso de borda: se algum dia um ticker US piloto vier com '.SA' (nao
    deveria, mas a funcao checa isso ANTES de consultar o cadastro) -
    garante que o guard-clause de sufixo existente continua tendo
    prioridade, sem comportamento ambiguo."""
    _checar("7 'NVDA.SA' preservado (guard clause de sufixo primeiro)", _para_symbol_yf("NVDA.SA") == "NVDA.SA")


# ============================================================
# 3. formatacao de valor por moeda
# ============================================================

def test_8_formatar_valor_mercado_brl_igual_a_sempre():
    _checar("8a BRL bilhoes (regressao)", config.formatar_valor_mercado(660_600_000_000) == "R$ 660,6 bi")
    _checar("8b BRL milhoes (regressao)", config.formatar_valor_mercado(45_200_000) == "R$ 45,2 mi")
    _checar("8c None -> '—' (regressao)", config.formatar_valor_mercado(None) == "—")


def test_9_formatar_valor_mercado_usd():
    _checar("9a USD bilhoes", config.formatar_valor_mercado(45_200_000_000, moeda="USD") == "US$ 45,2 bi")


def test_10_formatar_valor_mercado_trilhoes_nao_quebra_br():
    """NVDA/AAPL/MSFT passam de 1 trilhao de valor de mercado - faixa que
    nao existia antes (maior bracket era 'bi'). Confirma que o numero sai
    legivel (nao 'US$ 3.000,0 bi') sem quebrar o caso BRL equivalente."""
    _checar("10a USD trilhoes", config.formatar_valor_mercado(3_000_000_000_000, moeda="USD") == "US$ 3,0 tri")
    _checar("10b BRL trilhoes (mesma faixa, moeda default)", config.formatar_valor_mercado(1_200_000_000_000) == "R$ 1,2 tri")


# ============================================================
# 4. beta usa o indice de referencia certo por mercado
# ============================================================

class _TickerRegistraSimbolo:
    """yf.Ticker(symbol) que registra qual symbol foi pedido, devolve
    historico vazio (sem rede real) - so' pra confirmar qual indice
    _calcular_beta tenta buscar pra cada mercado."""
    chamados = []

    def __init__(self, symbol, *_a, **_k):
        _TickerRegistraSimbolo.chamados.append(symbol)

    def history(self, *_a, **_k):
        import pandas as pd
        return pd.DataFrame({"Close": []})


def test_11_beta_br_usa_ibov_como_benchmark():
    _TickerRegistraSimbolo.chamados = []
    with patch.object(prices_mod.yf, "Ticker", _TickerRegistraSimbolo):
        _calcular_beta("PETR4")
    _checar("11 PETR4 consulta ^BVSP (regressao)", "^BVSP" in _TickerRegistraSimbolo.chamados,
            f"(chamados={_TickerRegistraSimbolo.chamados})")


def test_12_beta_us_usa_sp500_como_benchmark_nao_ibov():
    _TickerRegistraSimbolo.chamados = []
    with patch.object(prices_mod.yf, "Ticker", _TickerRegistraSimbolo):
        _calcular_beta("NVDA")
    _checar("12a NVDA consulta ^GSPC (S&P 500)", "^GSPC" in _TickerRegistraSimbolo.chamados,
            f"(chamados={_TickerRegistraSimbolo.chamados})")
    _checar("12b NVDA NUNCA consulta ^BVSP", "^BVSP" not in _TickerRegistraSimbolo.chamados,
            f"(chamados={_TickerRegistraSimbolo.chamados})")


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
    print("TODOS OS TESTES DE ATIVOS BR/US (FASE 3) PASSARAM")
