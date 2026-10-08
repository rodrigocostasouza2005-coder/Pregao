# -*- coding: utf-8 -*-
"""Testes de timeout/falha de fonte (2026-10-05, bloqueador #1 da
auditoria do Terminal V1): data/prices.py e data/mercado.py agora
passam timeout= explicito em toda chamada yfinance que aceita o
parametro (.history()/yf.download()). Testes aqui confirmam que (1) o
timeout e' de fato repassado pra lib (nao so' cosmetico) e (2) quando a
chamada falha/estoura tempo, o comportamento e' EXATAMENTE o mesmo de
antes - cai pro fallback existente quando ha' um, retorna None/erro sem
inventar preco quando nao ha'. Mocka yf.Ticker/yf.download - nao faz
chamada de rede real.

Uso: python tests/test_prices.py (python do .venv do projeto)."""
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import data.mercado as mercado_mod
import data.prices as prices_mod
import ui.visao_geral as visao_geral_mod
from data.prices import (
    _TIMEOUT_YF, _calcular_beta, _historico_semanal_ibov, obter_cotacao, obter_cotacao_indice,
    obter_historico, obter_historico_intraday, obter_indicadores, validar_ticker,
)

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


class _TickerTimeout:
    """yf.Ticker(...) cujo .history()/.fast_info/.info/.dividends
    sempre estoura timeout - simula o cenario real que o timeout
    explicito existe pra limitar (Yahoo pendurando a conexao)."""
    def __init__(self, *_a, **_k):
        pass

    def history(self, *_a, **kwargs):
        raise TimeoutError("timed out")

    @property
    def fast_info(self):
        raise TimeoutError("timed out")

    @property
    def info(self):
        raise TimeoutError("timed out")

    @property
    def dividends(self):
        raise TimeoutError("timed out")


# ============================================================
# 1. timeout e' REPASSADO pra lib (nao so' existe no papel)
# ============================================================

def test_1_historico_passa_timeout_explicito_pro_yfinance():
    chamada = {}

    class _TickerCapturaKwargs:
        def __init__(self, *_a, **_k):
            pass

        def history(self, *_a, **kwargs):
            chamada.update(kwargs)
            raise TimeoutError("timed out")

    with patch.object(prices_mod.yf, "Ticker", _TickerCapturaKwargs):
        obter_historico("TESTE_TIMEOUT_KW_1", "1M")
    _checar("1a timeout= repassado pra yf.Ticker(...).history()", chamada.get("timeout") == _TIMEOUT_YF,
             f"(kwargs={chamada})")


def test_1b_download_passa_timeout_explicito_pro_yfinance():
    chamada = {}

    def _download_fake(*_a, **kwargs):
        chamada.update(kwargs)
        raise TimeoutError("timed out")

    with patch.object(mercado_mod.yf, "download", side_effect=_download_fake):
        mercado_mod._baixar_lote(("TESTE_TIMEOUT_KW2",))
    _checar("1b timeout= repassado pra yf.download() (_baixar_lote)", chamada.get("timeout") == mercado_mod._TIMEOUT_YF,
             f"(kwargs={chamada})")

    chamada.clear()
    with patch.object(mercado_mod.yf, "download", side_effect=_download_fake):
        mercado_mod._baixar_lote_bruto(("^TESTE_KW3",))
    _checar("1c timeout= repassado pra yf.download() (_baixar_lote_bruto)", chamada.get("timeout") == mercado_mod._TIMEOUT_YF,
             f"(kwargs={chamada})")


# ============================================================
# 2. timeout/excecao nunca propaga, nunca inventa preco
# ============================================================

def test_2_obter_cotacao_timeout_retorna_erro_sem_inventar_preco():
    with patch.object(prices_mod.yf, "Ticker", _TickerTimeout):
        resultado = obter_cotacao("TESTE_TIMEOUT_COTACAO_1")
    _checar("2a timeout nao propaga (sem excecao)", True)
    _checar("2b nenhum preco inventado (campo 'preco' ausente)", "preco" not in resultado)
    _checar("2c motivo do erro presente", resultado.get("erro") not in (None, ""))


def test_3_validar_ticker_timeout_retorna_false_sem_quebrar():
    with patch.object(prices_mod.yf, "Ticker", _TickerTimeout):
        resultado = validar_ticker("TESTE_TIMEOUT_VALIDAR")
    _checar("3 timeout em validar_ticker -> False (nunca assume ticker valido)", resultado is False)


def test_4_historico_semanal_ibov_timeout_retorna_none():
    with patch.object(prices_mod.yf, "Ticker", _TickerTimeout):
        resultado = _historico_semanal_ibov()
    _checar("4 timeout -> None (nunca inventa historico)", resultado is None)


def test_5_calcular_beta_timeout_retorna_none():
    with patch.object(prices_mod.yf, "Ticker", _TickerTimeout):
        resultado = _calcular_beta("TESTE_TIMEOUT_BETA")
    _checar("5 timeout -> None (nunca inventa beta)", resultado is None)


def test_6_obter_historico_timeout_retorna_none():
    with patch.object(prices_mod.yf, "Ticker", _TickerTimeout):
        resultado = obter_historico("TESTE_TIMEOUT_HIST", "1M")
    _checar("6 timeout -> None (nunca inventa historico/grafico)", resultado is None)


def test_7_obter_historico_intraday_timeout_retorna_none():
    with patch.object(prices_mod.yf, "Ticker", _TickerTimeout):
        resultado = obter_historico_intraday("TESTE_TIMEOUT_INTRADAY", "1D")
    _checar("7 timeout -> None (intraday nunca inventa)", resultado is None)


def test_8_baixar_lote_timeout_retorna_none_sem_quebrar():
    with patch.object(mercado_mod.yf, "download", side_effect=TimeoutError("timed out")):
        resultado = mercado_mod._baixar_lote(("TESTE_TIMEOUT_LOTE",))
    _checar("8 timeout em yf.download (lote) -> None, nunca quebra", resultado is None)


# ============================================================
# 3. fallback EXISTENTE continua funcionando com timeout
# ============================================================

def test_9_cotacao_indice_timeout_cai_pro_ultimo_valor_valido():
    """Prime o cache de ultimo-valor-bom diretamente (mesmo mecanismo que
    uma chamada bem-sucedida anterior gravaria) - testa so' o
    COMPORTAMENTO DE FALLBACK sob timeout, nao a chamada de sucesso em
    si (ja coberta pelo smoke test ao vivo rodado antes deste arquivo
    existir)."""
    nome = "TESTE_TIMEOUT_INDICE_FALLBACK"
    prices_mod._ultima_cotacao_indice_valida()[nome] = {
        "nome": nome, "preco": 105.0, "variacao": 5.0, "variacao_pct": 5.0, "erro": None,
    }
    with patch.object(prices_mod.yf, "Ticker", _TickerTimeout):
        resultado = obter_cotacao_indice(nome, "^TESTEFB")
    _checar("9a timeout com fallback disponivel -> retorna o ultimo valor valido (nao erro)", resultado.get("erro") is None)
    _checar("9b valor do fallback e' o gravado anteriormente", resultado.get("preco") == 105.0, f"(resultado={resultado})")


def test_10_cotacao_indice_timeout_sem_fallback_retorna_erro():
    with patch.object(prices_mod.yf, "Ticker", _TickerTimeout):
        resultado = obter_cotacao_indice("TESTE_TIMEOUT_INDICE_SEM_FALLBACK", "^TESTESF")
    _checar("10a timeout sem fallback anterior -> erro explicito (nunca inventa)", resultado.get("erro") is not None)
    _checar("10b nenhum campo 'preco' presente", "preco" not in resultado)


def test_11_indicadores_timeout_total_sem_fallback_retorna_campos_none():
    ticker = "TESTE_TIMEOUT_INDICADORES_1"
    with patch.object(prices_mod, "_tk_info_com_retry", return_value={}), \
         patch.object(prices_mod, "_calcular_beta", return_value=None):
        resultado = obter_indicadores(ticker)
    _checar("11a sem info nenhuma -> todos os campos None (nunca inventa)",
             all(v is None for v in resultado.values()))


def test_12_indicadores_timeout_cai_pro_fallback_anterior():
    ticker = "TESTE_TIMEOUT_INDICADORES_2"
    anterior = {
        "valor_mercado": 1000.0, "pl": 10.0, "pvp": 2.0, "dividend_yield": 5.0, "beta": 0.9,
        "roe": 15.0, "margem_liquida": 20.0, "margem_operacional": 18.0, "margem_ebitda": 25.0,
        "divida_liquida": 50.0, "divida_liquida_ebitda": 1.2,
    }
    prices_mod._ultimo_indicadores_valido()[ticker] = anterior

    with patch.object(prices_mod, "_tk_info_com_retry", return_value={}), \
         patch.object(prices_mod, "_calcular_beta", return_value=None):
        resultado = obter_indicadores(ticker)
    _checar("12a timeout total mas com fallback anterior -> reusa os valores antigos (nao vira None)",
             resultado["pl"] == 10.0 and resultado["roe"] == 15.0, f"(resultado={resultado})")


# ============================================================
# DADOS STALE (2026-10-06): obter_indicadores grava "_coletado_em" so'
# quando a coleta de verdade funciona - permite a UI avisar quando um
# valor exibido veio de uma falha anterior (fallback), nao da tentativa
# de agora.
# ============================================================

def test_13_coleta_bem_sucedida_grava_coletado_em():
    ticker = "TESTE_STALE_SUCESSO"
    with patch.object(prices_mod, "_tk_info_com_retry", return_value={"trailingPE": 10.0}), \
         patch.object(prices_mod, "_calcular_beta", return_value=None), \
         patch.object(prices_mod, "_dividend_yield_12m", return_value=None):
        resultado = obter_indicadores(ticker)
    _checar("13a coleta com sucesso grava _coletado_em", "_coletado_em" in resultado)
    _checar("13b _coletado_em e' um timestamp ISO parseavel",
             datetime.fromisoformat(resultado["_coletado_em"]) is not None)


def test_14_fallback_propaga_coletado_em_original_nao_agora():
    ticker = "TESTE_STALE_FALLBACK"
    antigo_iso = "2026-09-01T12:00:00+00:00"
    prices_mod._ultimo_indicadores_valido()[ticker] = {
        "valor_mercado": 1.0, "pl": 1.0, "pvp": None, "dividend_yield": None, "beta": None,
        "roe": None, "margem_liquida": None, "margem_operacional": None, "margem_ebitda": None,
        "divida_liquida": None, "divida_liquida_ebitda": None, "_coletado_em": antigo_iso,
    }
    with patch.object(prices_mod, "_tk_info_com_retry", return_value={}), \
         patch.object(prices_mod, "_calcular_beta", return_value=None):
        resultado = obter_indicadores(ticker)
    _checar("14 fallback carrega o _coletado_em ORIGINAL (nao 'agora') - nunca disfarça dado velho de novo",
             resultado.get("_coletado_em") == antigo_iso, f"(resultado={resultado.get('_coletado_em')})")


def test_15_sem_fallback_nenhum_nao_tem_coletado_em():
    ticker = "TESTE_STALE_SEM_FALLBACK"
    with patch.object(prices_mod, "_tk_info_com_retry", return_value={}), \
         patch.object(prices_mod, "_calcular_beta", return_value=None):
        resultado = obter_indicadores(ticker)
    _checar("15 nunca houve coleta nem fallback -> sem _coletado_em (nada a declarar como 'velho')",
             "_coletado_em" not in resultado)


# ============================================================
# 16. KeyError real de producao (2026-10-08): VISAO GERAL deixava
#     selecionar "1D"/"1S" no mini-grafico do IBOV, que nao sao'
#     rotulos de PERIODOS_GRAFICO (so' os diarios/semanais - "1D"/"1S"
#     sao' intradiarios, outra tabela) -> obter_historico() estourava
#     KeyError sem cair no except (lookup e' ANTES do try). Testes
#     abaixo cobrem: (a) todos os periodos oficialmente suportados por
#     PERIODOS_GRAFICO funcionam; (b) rotulo intradiario/legado/invalido
#     nunca propaga KeyError - obter_historico() so' aceita rotulo
#     oficial, qualquer outro vira None (ultima camada de seguranca,
#     generica - nao' e' so' pro IBOV); (c) o caminho real da VISAO GERAL
#     (ui/visao_geral.py:_painel_ibov_grafico) roteia "1D"/"1S" pra
#     obter_historico_intraday() e os demais pra obter_historico(),
#     igual o grafico de MERCADO em app.py ja' fazia.
# ============================================================

class _TickerHistoricoValido:
    """yf.Ticker(...).history() sempre devolve um DataFrame OHLCV valido
    (> 200 candles, pra MM200 nao ficar vazia) - simula fonte saudavel,
    sem rede."""
    def __init__(self, *_a, **_k):
        pass

    def history(self, *_a, **kwargs):
        n = 260
        idx = pd.date_range("2024-01-01", periods=n, freq="D", name="Date")
        preco = np.linspace(100, 120, n)
        return pd.DataFrame(
            {"Open": preco, "High": preco + 1, "Low": preco - 1, "Close": preco, "Volume": 1000},
            index=idx,
        )


def test_16a_obter_historico_cobre_todos_os_periodos_oficiais_de_periodos_grafico():
    with patch.object(prices_mod.yf, "Ticker", _TickerHistoricoValido):
        for rotulo in config.PERIODOS_GRAFICO:
            resultado = obter_historico(f"TESTE_PERIODO_{rotulo}", rotulo)
            _checar(f"16a '{rotulo}' (oficial de PERIODOS_GRAFICO) nunca quebra e devolve DataFrame",
                    resultado is not None and not resultado.empty, f"(rotulo={rotulo})")


def test_16b_obter_historico_com_rotulo_intradiario_ou_invalido_nunca_propaga_keyerror():
    with patch.object(prices_mod.yf, "Ticker", _TickerHistoricoValido):
        for rotulo in ["1D", "1S", "ROTULO_LEGADO_INEXISTENTE", ""]:
            try:
                resultado = obter_historico("TESTE_ROTULO_INVALIDO", rotulo)
                excecao = None
            except Exception as exc:  # pragma: no cover - e' exatamente o que nao queremos
                resultado, excecao = None, exc
            _checar(f"16b rotulo invalido '{rotulo}' nunca propaga excecao (nunca derruba a UI)",
                    excecao is None, f"(excecao={excecao})")
            _checar(f"16b rotulo invalido '{rotulo}' -> None (nunca inventa periodo)", resultado is None)


class _FakeSessionState(dict):
    pass


class _FakeStVisaoGeral:
    """Dublê mínimo de streamlit pra exercitar _painel_ibov_grafico sem
    sessão real - so' os metodos que a funcao de fato chama."""
    def __init__(self, selecao):
        self.session_state = _FakeSessionState()
        self._selecao = selecao
        self.avisos = []

    def markdown(self, *_a, **_k):
        pass

    def segmented_control(self, *_a, **_k):
        return self._selecao

    def warning(self, msg, **_k):
        self.avisos.append(msg)

    def plotly_chart(self, *_a, **_k):
        pass


def _rodar_painel_ibov_grafico(selecao):
    chamadas = {"intraday": None, "diario": None}
    fake_st = _FakeStVisaoGeral(selecao)
    with patch.object(visao_geral_mod, "st", fake_st), \
         patch.object(visao_geral_mod, "obter_historico_intraday",
                      side_effect=lambda t, p: chamadas.__setitem__("intraday", (t, p))), \
         patch.object(visao_geral_mod, "obter_historico",
                      side_effect=lambda t, p: chamadas.__setitem__("diario", (t, p))):
        visao_geral_mod._painel_ibov_grafico({"tema": "AMBAR"})
    return chamadas


def test_16c_painel_ibov_grafico_roteia_1d_pra_obter_historico_intraday():
    chamadas = _rodar_painel_ibov_grafico("1D")
    _checar("16c selecionar '1D' na VISAO GERAL chama obter_historico_intraday(IBOV, '1D')",
            chamadas["intraday"] == (config.SIMBOLO_IBOVESPA, "1D"), f"(chamadas={chamadas})")
    _checar("16c selecionar '1D' NUNCA chama obter_historico() (o bug real de producao)",
            chamadas["diario"] is None, f"(chamadas={chamadas})")


def test_16d_painel_ibov_grafico_roteia_1s_pra_obter_historico_intraday():
    chamadas = _rodar_painel_ibov_grafico("1S")
    _checar("16d selecionar '1S' na VISAO GERAL chama obter_historico_intraday(IBOV, '1S')",
            chamadas["intraday"] == (config.SIMBOLO_IBOVESPA, "1S"), f"(chamadas={chamadas})")
    _checar("16d selecionar '1S' NUNCA chama obter_historico()", chamadas["diario"] is None, f"(chamadas={chamadas})")


def test_16e_painel_ibov_grafico_roteia_periodo_diario_pro_obter_historico():
    chamadas = _rodar_painel_ibov_grafico("6M")
    _checar("16e selecionar '6M' na VISAO GERAL chama obter_historico(IBOV, '6M')",
            chamadas["diario"] == (config.SIMBOLO_IBOVESPA, "6M"), f"(chamadas={chamadas})")
    _checar("16e selecionar '6M' NUNCA chama obter_historico_intraday()",
            chamadas["intraday"] is None, f"(chamadas={chamadas})")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE TIMEOUT/FALLBACK DE PRICES/MERCADO PASSARAM")
