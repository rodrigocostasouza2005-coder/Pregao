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
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import data.mercado as mercado_mod
import data.prices as prices_mod
import ui.visao_geral as visao_geral_mod
from data.prices import (
    _TIMEOUT_YF, _calcular_beta, _historico_semanal_indice, obter_cotacao,
    obter_cotacao_indice, obter_historico, obter_historico_intraday, obter_indicadores, validar_ticker,
)

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


def test_4_historico_semanal_indice_timeout_retorna_none():
    with patch.object(prices_mod.yf, "Ticker", _TickerTimeout):
        resultado = _historico_semanal_indice("^BVSP")
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
        "_coletado_em": "2026-10-14T15:00:00+00:00",
    }
    with patch.object(prices_mod.yf, "Ticker", _TickerTimeout):
        resultado = obter_cotacao_indice(nome, "^TESTEFB")
    _checar("9a timeout com fallback disponivel -> retorna o ultimo valor valido (nao erro)", resultado.get("erro") is None)
    _checar("9b valor do fallback e' o gravado anteriormente", resultado.get("preco") == 105.0, f"(resultado={resultado})")
    _checar("9c fallback e' explicitamente sinalizado", resultado.get("_fallback_cache") is True)
    _checar("9d timestamp original e' preservado quando existe", resultado.get("_coletado_em") == "2026-10-14T15:00:00+00:00")


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
            try:
                fn()
            except AssertionError:
                pass  # ja' registrado em _FALHAS por _checar

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE TIMEOUT/FALLBACK DE PRICES/MERCADO PASSARAM")


def test_17_status_cotacao_indice_sinaliza_idade_do_fallback():
    """A UI deve identificar valor reaproveitado e nunca renovar sua idade."""
    antigo = "2026-10-14T15:00:00+00:00"
    with patch.object(prices_mod, "datetime") as mock_datetime:  # critério vive em data/prices.py
        mock_datetime.now.return_value = datetime.fromisoformat("2026-10-14T17:30:00+00:00")
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        status = visao_geral_mod._status_cotacao_indice({
            "_fallback_cache": True, "_coletado_em": antigo,
            "_barra_em": "2026-10-13T00:00:00-03:00",
        })
    _checar("17a fallback antigo mostra idade em horas", status == "EM CACHE • 2H 30MIN • BARRA 13/10", f"(status={status})")


def test_18_status_cotacao_indice_nao_marca_coleta_atual_como_cache():
    _checar("18a coleta atual nao recebe aviso de cache",
            visao_geral_mod._status_cotacao_indice({"_fallback_cache": False}) is None)
    _checar("18b fallback legado sem timestamp continua explicito",
            visao_geral_mod._status_cotacao_indice({"_fallback_cache": True}) == "VALOR EM CACHE")


def test_19_status_cotacao_indice_mantem_idade_sem_data_da_barra():
    """Fallbacks legados sem timestamp de candle devem continuar legiveis."""
    antigo = "2026-10-14T15:00:00+00:00"
    with patch.object(prices_mod, "datetime") as mock_datetime:  # critério vive em data/prices.py
        mock_datetime.now.return_value = datetime.fromisoformat("2026-10-14T17:30:00+00:00")
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        status = visao_geral_mod._status_cotacao_indice({
            "_fallback_cache": True, "_coletado_em": antigo,
        })
    _checar("19a fallback sem data de barra preserva idade", status == "EM CACHE • 2H 30MIN", f"(status={status})")


def test_cotacao_indice_ignora_barra_de_fim_de_semana_do_cambio():
    """Caso real (USDBRL=X, 18/10/2026): o Yahoo publica barra de domingo
    com cotação indicativa; a variação comparava domingo x sexta e, na
    segunda, seria segunda x domingo. Barras de sábado/domingo saem."""
    import pandas as pd
    indice = pd.DatetimeIndex(["2026-10-15", "2026-10-16", "2026-10-18"], tz="Europe/London")
    hist = pd.DataFrame({"Close": [5.0800, 5.0966, 5.0645]}, index=indice)

    class _TickerFds:
        def __init__(self, *_a, **_k):
            # formato real do yfinance 1.7: Timestamp ja' no fuso da bolsa
            self.history_metadata = {"regularMarketTime": pd.Timestamp("2026-10-16T23:10:00+01:00").tz_convert("Europe/London")}

        def history(self, *_a, **_k):
            return hist

    with patch.object(prices_mod.yf, "Ticker", _TickerFds):
        r = obter_cotacao_indice("TESTE_FDS_USDBRL", "USDBRL=X")
    assert r["preco"] == 5.0966
    assert abs(r["variacao_pct"] - (5.0966 / 5.0800 - 1) * 100) < 1e-9
    assert r["_barra_em"].startswith("2026-10-16")
    assert r["_negocio_em"].startswith("2026-10-16T23:10")


def test_cotacao_indice_horario_de_negocio_de_outro_dia_e_ignorado():
    import pandas as pd
    indice = pd.DatetimeIndex(["2026-10-15", "2026-10-16"], tz="America/New_York")
    hist = pd.DataFrame({"Close": [100.0, 101.0]}, index=indice)

    class _Ticker:
        def __init__(self, *_a, **_k):
            self.history_metadata = {"regularMarketTime": int(pd.Timestamp("2026-10-17T10:00:00-04:00").timestamp())}

        def history(self, *_a, **_k):
            return hist

    with patch.object(prices_mod.yf, "Ticker", _Ticker):
        r = obter_cotacao_indice("TESTE_NEGOCIO_OUTRO_DIA", "ES=F")
    assert r["_negocio_em"] is None
    assert r["variacao_pct"] == 1.0


def test_obter_cotacao_rejeita_preco_nan_ou_infinito():
    class _TickerCotacaoInvalida:
        def __init__(self, *_a, **_k):
            self.fast_info = {"lastPrice": float("nan"), "previousClose": 10.0}

    with patch.object(prices_mod.yf, "Ticker", _TickerCotacaoInvalida):
        resultado = obter_cotacao("TESTE_COTACAO_NAN_20261020")
    assert "preco" not in resultado
    assert resultado.get("erro")


def test_obter_cotacao_rejeita_fechamento_anterior_nao_finito():
    class _TickerFechamentoInvalido:
        def __init__(self, *_a, **_k):
            self.fast_info = {"lastPrice": 10.0, "previousClose": float("inf")}

    with patch.object(prices_mod.yf, "Ticker", _TickerFechamentoInvalido):
        resultado = obter_cotacao("TESTE_FECHAMENTO_INF_20261020")
    assert "preco" not in resultado
    assert resultado.get("erro")


def test_obter_cotacao_normaliza_campos_auxiliares_invalidos():
    class _TickerCamposAuxiliares:
        def __init__(self, *_a, **_k):
            self.fast_info = {
                "lastPrice": 11.0, "previousClose": 10.0,
                "dayHigh": float("nan"), "dayLow": 0,
                "lastVolume": float("inf"), "yearHigh": float("nan"),
                "yearLow": float("inf"),
            }

    with patch.object(prices_mod.yf, "Ticker", _TickerCamposAuxiliares):
        resultado = obter_cotacao("TESTE_AUXILIARES_INVALIDOS_20261020")
    assert resultado["preco"] == 11.0
    assert resultado["variacao_pct"] == 10.0
    assert resultado["maxima_dia"] is None
    assert resultado["minima_dia"] is None
    assert resultado["volume"] is None
    assert resultado["maxima_52s"] is None
    assert resultado["minima_52s"] is None


def test_obter_cotacao_indice_rejeita_close_nan_e_infinito():
    import pandas as pd

    def _rodar(close):
        hist = pd.DataFrame(
            {"Close": [100.0, close]},
            index=pd.DatetimeIndex(["2026-10-19", "2026-10-20"], tz="America/Sao_Paulo"),
        )

        class _Ticker:
            history_metadata = {}
            def __init__(self, *_a, **_k):
                pass
            def history(self, *_a, **_k):
                return hist

        with patch.object(prices_mod.yf, "Ticker", _Ticker):
            return obter_cotacao_indice(f"TESTE_INDICE_INVALIDO_{close}", "TESTE=X")

    for valor in (float("nan"), float("inf"), 0.0, -1.0):
        resultado = _rodar(valor)
        assert "preco" not in resultado
        assert resultado.get("erro")


def test_obter_cotacao_indice_rejeita_fechamento_anterior_nao_finito():
    import pandas as pd
    hist = pd.DataFrame(
        {"Close": [float("nan"), 101.0]},
        index=pd.DatetimeIndex(["2026-10-19", "2026-10-20"], tz="America/Sao_Paulo"),
    )

    class _Ticker:
        history_metadata = {}
        def __init__(self, *_a, **_k):
            pass
        def history(self, *_a, **_k):
            return hist

    with patch.object(prices_mod.yf, "Ticker", _Ticker):
        resultado = obter_cotacao_indice("TESTE_FECHAMENTO_NAN", "TESTE=X")
    assert "preco" not in resultado
    assert resultado.get("erro")


def test_obter_cotacao_preserva_preco_quando_campos_auxiliares_ausentes():
    class _TickerSemCamposAuxiliares:
        def __init__(self, *_a, **_k):
            self.fast_info = {"lastPrice": 11.0, "previousClose": 10.0}

    with patch.object(prices_mod.yf, "Ticker", _TickerSemCamposAuxiliares):
        resultado = obter_cotacao("TESTE_SEM_AUXILIARES_20261020")
    assert resultado["preco"] == 11.0
    assert resultado["variacao_pct"] == 10.0
    assert resultado["maxima_dia"] is None
    assert resultado["minima_dia"] is None
    assert resultado["volume"] is None
    assert resultado["maxima_52s"] is None
    assert resultado["minima_52s"] is None


# ============================================================
# REGRESSAO (auditoria de performance, 2026-10-23): obter_cotacao_indice
# nao tinha @st.cache_data proprio - a ticker tape (app.py, TODA pagina,
# a cada run_every) e paineis de MERCADO/VISAO GERAL/MACRO chamavam essa
# funcao pros MESMOS indices (IBOVESPA/DOLAR/EURO) sem compartilhar
# cache nenhum, batendo no Yahoo repetidamente pro mesmo dado dentro da
# mesma janela de 30s. Este teste prova que 2 chamadas com os mesmos
# argumentos, dentro do TTL, resultam em SO' 1 chamada real a
# yf.Ticker(...).history() - nao so' "o decorator existe no codigo".
# ============================================================

def test_obter_cotacao_indice_e_cacheada_entre_chamadas_com_mesmo_argumento():
    chamadas = {"n": 0}
    hist = pd.DataFrame(
        {"Close": [100.0, 102.0]},
        index=pd.DatetimeIndex(["2026-10-21", "2026-10-22"], tz="America/Sao_Paulo"),
    )

    class _TickerContador:
        history_metadata = {}

        def __init__(self, *_a, **_k):
            pass

        def history(self, *_a, **_k):
            chamadas["n"] += 1
            return hist

    obter_cotacao_indice.clear()
    with patch.object(prices_mod.yf, "Ticker", _TickerContador):
        primeira = obter_cotacao_indice("TESTE_CACHE_INDICE_2X", "TESTE_CACHE=X")
        segunda = obter_cotacao_indice("TESTE_CACHE_INDICE_2X", "TESTE_CACHE=X")
    assert chamadas["n"] == 1, f"esperava 1 chamada real (cache compartilhado), teve {chamadas['n']}"
    assert primeira == segunda
    assert primeira.get("erro") is None


# ============================================================
# INSTRUMENTACAO DE SAUDE DOS DADOS pra data/prices.py:_tk_info_com_retry
# (incidente 2026-10-23: P/L, P/VP e DY em branco simultaneamente em
# toda a watchlist, sem NENHUM jeito de confirmar em producao se foi
# excecao de rede, Yahoo respondendo vazio sem excecao, ou outra causa -
# esse caminho nunca registrava nada em data/saude_dados.py). Testes
# aqui cobrem os 4 desfechos possiveis (sucesso, resposta vazia,
# excecao/timeout, mistura) + a garantia de que um CAMPO individual
# ausente (ex: DY) nunca conta como falha, so' a ausencia TOTAL de
# `.info`. Mockam yf.Ticker e registrar_tentativa - nunca tocam rede ou
# Supabase de verdade.
# ============================================================

def _fake_ticker_class(desfechos: list):
    """Classe de yf.Ticker falsa cuja propriedade .info consome 1 item
    de `desfechos` por instanciacao (1 instancia por tentativa de sessao
    em _tk_info_com_retry) - item Exception -> .info lanca; item dict ->
    .info retorna. Instanciacoes alem da lista configurada (ex: o
    yf.Ticker(symbol) extra que obter_indicadores cria pra
    _dividend_yield_12m) recebem {} e .dividends vazio - nunca usadas
    pelos testes abaixo, so' pra nao quebrar por instanciacao a mais.
    Fila fechada sobre a lista (nao e' estado de classe compartilhado
    entre testes)."""
    fila = list(desfechos)

    class _FakeTicker:
        def __init__(self, *_a, **_k):
            self._desfecho = fila.pop(0) if fila else {}

        @property
        def info(self):
            if isinstance(self._desfecho, BaseException):
                raise self._desfecho
            return self._desfecho

        @property
        def dividends(self):
            return pd.Series(dtype=float)

    return _FakeTicker


def test_tk_info_sucesso_na_primeira_tentativa_registra_execucao_ok():
    FakeTicker = _fake_ticker_class([{"trailingPE": 10.0, "priceToBook": 2.0}])
    with patch.object(prices_mod.yf, "Ticker", FakeTicker), \
         patch.object(prices_mod, "registrar_tentativa") as mock_reg:
        info = prices_mod._tk_info_com_retry("PETR4.SA")
    assert info == {"trailingPE": 10.0, "priceToBook": 2.0}
    assert mock_reg.call_count == 1
    assert mock_reg.call_args.args[0] == "EQUITY (Fundamentos)"
    assert mock_reg.call_args.kwargs.get("execucao_ok") is True
    assert mock_reg.call_args.kwargs.get("categoria") == "Fundamentos"


def test_tk_info_resposta_vazia_sem_excecao_e_distinta_de_erro_de_conexao():
    # as 2 tentativas respondem {} SEM lancar nenhuma excecao - cenario
    # mais provavel do incidente real (bloqueio/rate-limit silencioso).
    FakeTicker = _fake_ticker_class([{}, {}])
    with patch.object(prices_mod.yf, "Ticker", FakeTicker), \
         patch.object(prices_mod, "registrar_tentativa") as mock_reg:
        info = prices_mod._tk_info_com_retry("PETR4.SA")
    assert info == {}
    assert mock_reg.call_count == 1
    kwargs = mock_reg.call_args.kwargs
    assert kwargs.get("execucao_ok") is False
    erro = (kwargs.get("erro") or "").lower()
    assert "vazio" in erro or "sem indicadores" in erro
    # nao deve conter nenhuma palavra-chave de erro de CONEXAO (ver
    # data/saude_dados.py:_TERMOS_INDISPONIBILIDADE) - senao o painel
    # classificaria como FONTE_INDISPONIVEL/erro de rede, escondendo que
    # na verdade foi uma resposta vazia sem excecao nenhuma.
    from data.saude_dados import _TERMOS_INDISPONIBILIDADE
    for termo in _TERMOS_INDISPONIBILIDADE:
        assert termo not in erro, f"mensagem de resposta vazia nao deveria conter {termo!r}: {erro!r}"


def test_tk_info_excecao_nas_2_tentativas_registra_falha_com_detalhe():
    FakeTicker = _fake_ticker_class([TimeoutError("conexao estourou o tempo"), ConnectionError("conexao recusada")])
    with patch.object(prices_mod.yf, "Ticker", FakeTicker), \
         patch.object(prices_mod, "registrar_tentativa") as mock_reg:
        info = prices_mod._tk_info_com_retry("PETR4.SA")
    assert info == {}
    assert mock_reg.call_count == 1
    kwargs = mock_reg.call_args.kwargs
    assert kwargs.get("execucao_ok") is False
    erro = (kwargs.get("erro") or "")
    assert "conexao recusada" in erro  # excecao da ULTIMA tentativa
    assert "excecao" in erro.lower()


def test_tk_info_erro_de_excecao_e_truncado_e_nunca_vaza_dado_bruto_enorme():
    excecao_enorme = Exception("X" * 5000)
    FakeTicker = _fake_ticker_class([excecao_enorme, excecao_enorme])
    with patch.object(prices_mod.yf, "Ticker", FakeTicker), \
         patch.object(prices_mod, "registrar_tentativa") as mock_reg:
        prices_mod._tk_info_com_retry("PETR4.SA")
    erro = mock_reg.call_args.kwargs.get("erro") or ""
    assert len(erro) <= 350  # prefixo da mensagem + str(e)[:300], mesmo padrao de data/macro.py


def test_tk_info_mistura_excecao_e_vazio_prioriza_resposta_vazia():
    # 1a tentativa lanca excecao, 2a responde {} sem excecao - o vazio-
    # sem-excecao e' o sinal mais forte (prova que o servidor respondeu),
    # entao deve vencer a mensagem registrada, nao a excecao da 1a.
    FakeTicker = _fake_ticker_class([TimeoutError("timeout na 1a tentativa"), {}])
    with patch.object(prices_mod.yf, "Ticker", FakeTicker), \
         patch.object(prices_mod, "registrar_tentativa") as mock_reg:
        prices_mod._tk_info_com_retry("PETR4.SA")
    erro = (mock_reg.call_args.kwargs.get("erro") or "").lower()
    assert "vazio" in erro or "sem indicadores" in erro
    assert "timeout na 1a tentativa" not in erro


def test_tk_info_campo_individual_ausente_nunca_conta_como_falha():
    # info NAO vazio (tem regularMarketPrice), mas SEM trailingPE/
    # priceToBook/dividendYield nenhum - exatamente o caso que o pedido
    # de instrumentacao avisou pra nao confundir com falha: um indicador
    # individual ausente (DY, por exemplo) e' decidido em
    # obter_indicadores() a partir do dict, nunca aqui.
    FakeTicker = _fake_ticker_class([{"regularMarketPrice": 33.5}])
    with patch.object(prices_mod.yf, "Ticker", FakeTicker), \
         patch.object(prices_mod, "registrar_tentativa") as mock_reg:
        info = prices_mod._tk_info_com_retry("ITSA4.SA")
    assert info == {"regularMarketPrice": 33.5}
    assert mock_reg.call_count == 1
    assert mock_reg.call_args.kwargs.get("execucao_ok") is True


def test_obter_indicadores_registra_1x_por_cache_miss_e_0x_em_cache_hit():
    # garante que a instrumentacao nao fica mais "tagarela" do que o
    # cache ja permite: 2 chamadas pro MESMO ticker dentro do TTL de 12h
    # devem gerar so' 1 escrita em SAUDE DOS DADOS (a 2a e' cache hit do
    # proprio obter_indicadores, nunca chega a chamar _tk_info_com_retry).
    obter_indicadores.clear()
    FakeTicker = _fake_ticker_class([{"trailingPE": 10.0}])
    with patch.object(prices_mod.yf, "Ticker", FakeTicker), \
         patch.object(prices_mod, "_calcular_beta", return_value=None), \
         patch.object(prices_mod, "registrar_tentativa") as mock_reg:
        primeira = obter_indicadores("TESTE_SAUDE_CACHE_HIT")
        segunda = obter_indicadores("TESTE_SAUDE_CACHE_HIT")
    assert primeira == segunda
    assert mock_reg.call_count == 1, f"esperava 1 escrita (so' no cache miss), teve {mock_reg.call_count}"


def test_obter_indicadores_resultado_identico_com_e_sem_instrumentacao_ativa():
    # a instrumentacao nunca deve alterar os VALORES calculados - mesmo
    # dict de entrada, mesma saida, com registrar_tentativa real
    # (sem Supabase configurado neste teste, vira no-op) ou mockado.
    obter_indicadores.clear()
    FakeTicker = _fake_ticker_class([{}])
    with patch.object(prices_mod.yf, "Ticker", FakeTicker), \
         patch.object(prices_mod, "_calcular_beta", return_value=0.9), \
         patch.object(prices_mod, "registrar_tentativa") as mock_reg:
        com_mock = obter_indicadores("TESTE_SAUDE_RESULTADO_A")

    obter_indicadores.clear()
    FakeTicker2 = _fake_ticker_class([{}])
    with patch.object(prices_mod.yf, "Ticker", FakeTicker2), \
         patch.object(prices_mod, "_calcular_beta", return_value=0.9):
        # registrar_tentativa real (sem mock) - sem secrets de Supabase
        # neste ambiente de teste, obter_cliente() retorna None e a
        # funcao degrada pra False sem nenhuma chamada de rede/banco.
        sem_mock = obter_indicadores("TESTE_SAUDE_RESULTADO_B")

    for campo in ("valor_mercado", "pl", "pvp", "dividend_yield", "beta", "roe",
                  "margem_liquida", "margem_operacional", "margem_ebitda",
                  "divida_liquida", "divida_liquida_ebitda"):
        assert com_mock[campo] == sem_mock[campo], f"campo {campo} divergiu com instrumentacao mockada vs real"
    assert mock_reg.called  # confirma que a instrumentacao de fato rodou no primeiro caso


def test_obter_indicadores_fallback_para_ultimo_valor_valido_continua_intacto():
    # regressao direta: a instrumentacao vive dentro de _tk_info_com_retry,
    # ANTES do fallback de _ultimo_indicadores_valido em obter_indicadores -
    # este teste confirma que o mecanismo de fallback (ja' testado em
    # test_12 acima) continua funcionando sem alteracao depois da mudanca.
    ticker = "TESTE_SAUDE_FALLBACK_INTACTO"
    anterior = {
        "valor_mercado": 500.0, "pl": 8.0, "pvp": 1.5, "dividend_yield": 4.0, "beta": 1.1,
        "roe": 12.0, "margem_liquida": 10.0, "margem_operacional": 9.0, "margem_ebitda": 15.0,
        "divida_liquida": 20.0, "divida_liquida_ebitda": 1.0,
    }
    prices_mod._ultimo_indicadores_valido()[ticker] = anterior
    obter_indicadores.clear()
    FakeTicker = _fake_ticker_class([{}, {}])
    with patch.object(prices_mod.yf, "Ticker", FakeTicker), \
         patch.object(prices_mod, "_calcular_beta", return_value=None), \
         patch.object(prices_mod, "registrar_tentativa") as mock_reg:
        resultado = obter_indicadores(ticker)
    assert resultado["pl"] == 8.0 and resultado["roe"] == 12.0
    # a falha (info vazio) FOI registrada em SAUDE DOS DADOS mesmo o
    # usuario tendo recebido um valor util via fallback - a UI nunca
    # mente, mas o painel de saude tambem nunca finge que a coleta DE
    # AGORA funcionou so' porque havia um valor antigo bom.
    assert mock_reg.call_count == 1
    assert mock_reg.call_args.kwargs.get("execucao_ok") is False
