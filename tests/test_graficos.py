"""Testes determinísticos pros indicadores técnicos novos de
ui/graficos.py (RSI/MACD/Bandas de Bollinger, 2026-11-11 - antes só havia
médias móveis). São funções puras (só pandas, zero st.*) de propósito -
rodam sem precisar de uma sessão Streamlit real, construindo séries de
preço sintéticas onde o resultado esperado é conhecido analiticamente
(preço constante -> sem volatilidade/sem variação; preço monotônico ->
só ganho ou só perda), em vez de só checar "não quebra"."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.graficos import calcular_bollinger, calcular_macd, calcular_rsi  # noqa: E402


def _df_precos(valores):
    return pd.DataFrame({"Close": list(valores)})


# === RSI =====================================================================

def test_rsi_so_ganhos_vale_100():
    """Série estritamente crescente (nenhuma perda) - sem perda nenhuma,
    o RSI tem que saturar em 100 (força máxima), nunca ficar indefinido."""
    df = _df_precos(range(1, 41))  # 1,2,3,...,40 - só alta, todo dia
    rsi = calcular_rsi(df, periodo=14)
    assert rsi.iloc[-1] == pytest.approx(100.0)
    # a partir do periodo+1 (primeira leitura com janela completa) o
    # resultado já está saturado - não é só o último ponto por acaso.
    assert rsi.iloc[15:].sub(100.0).abs().max() < 1e-6


def test_rsi_so_perdas_vale_proximo_de_zero():
    """Série estritamente decrescente (nenhum ganho) -> RSI deve cair
    pra bem perto de 0 (força mínima)."""
    df = _df_precos(range(40, 0, -1))
    rsi = calcular_rsi(df, periodo=14)
    assert rsi.iloc[-1] == pytest.approx(0.0, abs=1e-6)


def test_rsi_preco_constante_vale_50_neutro():
    """Preço nunca muda (delta sempre 0) -> nem ganho nem perda - RSI
    tem que ser 50 (neutro), não 100 nem NaN (0/0 sem o guard-rail)."""
    df = _df_precos([100.0] * 30)
    rsi = calcular_rsi(df, periodo=14)
    assert rsi.iloc[-1] == pytest.approx(50.0)


def test_rsi_tamanho_do_resultado_bate_com_o_df():
    df = _df_precos([10, 11, 12, 11, 13, 14, 12, 15, 16, 14, 17, 18, 16, 19, 20])
    rsi = calcular_rsi(df)
    assert len(rsi) == len(df)


# === MACD ====================================================================

def test_macd_preco_constante_fica_todo_zero():
    """EMA rápida e EMA lenta de uma série constante convergem pro
    próprio valor constante desde o primeiro ponto (ewm adjust=False
    começa exatamente no valor inicial) - MACD, sinal e histograma têm
    que ser 0 em toda a série, nunca "quase zero" por erro de ponto
    flutuante relevante."""
    df = _df_precos([50.0] * 40)
    macd_df = calcular_macd(df)
    assert (macd_df["MACD"].abs() < 1e-9).all()
    assert (macd_df["MACD_SINAL"].abs() < 1e-9).all()
    assert (macd_df["MACD_HIST"].abs() < 1e-9).all()


def test_macd_tendencia_de_alta_fica_positivo():
    """Série em alta constante -> EMA rápida (reage mais rápido) fica
    ACIMA da EMA lenta -> MACD positivo (momentum de alta real, não
    just um sinal arbitrário)."""
    df = _df_precos(range(1, 61))
    macd_df = calcular_macd(df)
    assert macd_df["MACD"].iloc[-1] > 0


def test_macd_histograma_e_a_diferenca_macd_menos_sinal():
    df = _df_precos([10, 12, 11, 13, 15, 14, 16, 18, 17, 19, 21, 20, 22, 24, 23])
    macd_df = calcular_macd(df)
    diferenca = macd_df["MACD"] - macd_df["MACD_SINAL"]
    assert (macd_df["MACD_HIST"] - diferenca).abs().max() < 1e-9


# === Bandas de Bollinger =====================================================

def test_bollinger_preco_constante_bandas_colapsam_na_media():
    """Desvio-padrão de uma série constante é 0 -> superior/média/
    inferior têm que ser exatamente o mesmo valor (banda com largura
    zero), nunca um valor divergente por erro de cálculo."""
    df = _df_precos([80.0] * 25)
    bb = calcular_bollinger(df, periodo=20)
    ultimo = bb.iloc[-1]
    assert ultimo["BB_SUPERIOR"] == pytest.approx(80.0)
    assert ultimo["BB_MEDIA"] == pytest.approx(80.0)
    assert ultimo["BB_INFERIOR"] == pytest.approx(80.0)


def test_bollinger_superior_sempre_acima_da_media_que_fica_acima_da_inferior():
    df = _df_precos([10, 12, 9, 14, 11, 13, 10, 15, 12, 16, 11, 14, 13, 17, 12, 15, 14, 18, 13, 16, 15, 19])
    bb = calcular_bollinger(df, periodo=20).dropna()
    assert not bb.empty
    assert (bb["BB_SUPERIOR"] >= bb["BB_MEDIA"]).all()
    assert (bb["BB_MEDIA"] >= bb["BB_INFERIOR"]).all()


def test_bollinger_antes_da_janela_minima_vale_nan():
    """Com menos barras que `periodo`, a rolling window ainda não tem
    dado suficiente - tem que vir NaN (ausência explícita), nunca um
    valor inventado a partir de uma janela incompleta."""
    df = _df_precos([10, 11, 12, 13, 14])  # 5 barras, periodo padrao = 20
    bb = calcular_bollinger(df, periodo=20)
    assert bb["BB_MEDIA"].isna().all()
