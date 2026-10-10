# -*- coding: utf-8 -*-
"""Testes de data/mercado.py e ui/mercado_tab.py:_cor_treemap - ate
2026-10-08 esse modulo nao tinha NENHUM teste automatizado, apesar de
ser a fonte de MERCADO/VISAO GERAL (altas/baixas, termometro,
desempenho setorial, treemap) e ja ter tido um bug real documentado
(treemap mostrando "+NaN%" em nos agregados, ver PROGRESSO.md). Cobre:

- _linha_papel: papel com 1 candle so' (fica de fora, nunca quebra);
  fechamento_anterior zerado (fica de fora, nunca divide por zero).
- obter_altas_baixas/obter_termometro/obter_desempenho_setorial: papel
  sem dado na janela fica de fora (nunca inventa numero); setor sem
  NENHUM papel valido na janela nao aparece (nunca media de lista
  vazia -> ZeroDivisionError/NaN).
- obter_cotacoes_lote (fix N+1 2026-10-08): lote falho/ticker ausente
  do lote degradam com erro, nunca quebram.
- _cor_treemap: limite=0 nao gera NaN/excecao; variacao 0 fica neutra.

Mocka yf.download/_baixar_lote/obter_panorama_ibovespa - nunca faz
chamada de rede. Uso: python tests/test_mercado.py (venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import data.mercado as mercado_mod
import ui.mercado_tab as mercado_tab_mod

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


def _df_simples(symbol, closes, volumes=None):
    """DataFrame multi-nivel no MESMO formato que yf.download(group_by='ticker')
    devolve pra 1 symbol - indice de data, colunas (campo, symbol)."""
    idx = pd.date_range("2026-09-01", periods=len(closes), freq="D")
    volumes = volumes or [1000.0] * len(closes)
    sub = pd.DataFrame({"Close": closes, "Volume": volumes}, index=idx)
    return pd.concat({symbol: sub}, axis=1)


def test_1_linha_papel_com_1_candle_so_fica_de_fora():
    df = _df_simples("PETR4.SA", [30.0])
    linha = mercado_mod._linha_papel(df, "PETR4", "PETR4.SA")
    _checar("1 papel com 1 candle so' -> None (nunca variacao sem base de comparacao)", linha is None)


def test_2_linha_papel_fechamento_anterior_zero_fica_de_fora():
    df = _df_simples("XPTO4.SA", [0.0, 10.0])
    linha = mercado_mod._linha_papel(df, "XPTO4", "XPTO4.SA")
    _checar("2 fechamento anterior zerado -> None (nunca divide por zero)", linha is None)


def test_3_linha_papel_normal_calcula_variacao_e_janelas():
    # 40 dias flat em 10.0 (cobre as bases de 7d E 30d atras, ambas = 10.0)
    # + os 2 ultimos candles (ontem=20, hoje=22) pra variacao do dia.
    closes = [10.0] * 40 + [20.0, 22.0]
    df = _df_simples("TEST3.SA", closes)
    linha = mercado_mod._linha_papel(df, "TEST3", "TEST3.SA")
    _checar("3a papel normal nao fica de fora", linha is not None)
    _checar("3b variacao_pct do dia calculada certo (20->22 = +10%)",
            linha is not None and abs(linha["variacao_pct"] - 10.0) < 0.01, f"(linha={linha})")
    _checar("3c variacao_mes_pct calculada contra a base de ~30 dias (10->22 = +120%)",
            linha is not None and linha["variacao_mes_pct"] is not None
            and abs(linha["variacao_mes_pct"] - 120.0) < 1.0, f"(linha={linha})")
    _checar("3d variacao_semana_pct calculada contra a base de ~7 dias (10->22 = +120%)",
            linha is not None and linha["variacao_semana_pct"] is not None
            and abs(linha["variacao_semana_pct"] - 120.0) < 1.0, f"(linha={linha})")


def test_4_obter_cotacoes_lote_lote_indisponivel_degrada_com_erro():
    with patch.object(mercado_mod, "_baixar_lote", return_value=None):
        resultado = mercado_mod.obter_cotacoes_lote(("PETR4", "VALE3"))
    _checar("4a lote indisponivel -> todos os tickers com erro (nunca quebra)",
            all(resultado[t].get("erro") for t in ("PETR4", "VALE3")), f"(resultado={resultado})")


def test_5_obter_cotacoes_lote_ticker_ausente_do_lote_degrada_isolado():
    df = _df_simples("PETR4.SA", [30.0, 31.0])  # so' PETR4 no lote, VALE3 nao veio
    with patch.object(mercado_mod, "_baixar_lote", return_value=df):
        resultado = mercado_mod.obter_cotacoes_lote(("PETR4", "VALE3"))
    _checar("5a PETR4 (no lote) tem cotacao real", resultado["PETR4"].get("erro") is None)
    _checar("5b VALE3 (ausente do lote) degrada isolado, sem quebrar PETR4",
            resultado["VALE3"].get("erro") is not None, f"(resultado={resultado})")


def test_6_obter_cotacoes_lote_vazio_nunca_bate_na_fonte():
    chamadas = []
    with patch.object(mercado_mod, "_baixar_lote", side_effect=lambda t: chamadas.append(t) or None):
        resultado = mercado_mod.obter_cotacoes_lote(())
    _checar("6 tickers vazio -> {} sem nenhuma chamada ao lote", resultado == {} and chamadas == [])


def _papel(ticker, setor, variacao_dia=None):
    return {"ticker": ticker, "setor": setor, "variacao_pct": variacao_dia,
            "variacao_semana_pct": None, "variacao_mes_pct": None,
            "volume": 100.0, "volume_financeiro": 1000.0}


def test_7_altas_baixas_papel_sem_dado_na_janela_fica_de_fora():
    papeis = [_papel("A", "Bancos", 5.0), _papel("B", "Bancos", None), _papel("C", "Bancos", -3.0)]
    with patch.object(mercado_mod, "obter_panorama_ibovespa", return_value=papeis):
        altas, baixas = mercado_mod.obter_altas_baixas(n=10, janela="dia")
    _checar("7a papel sem dado na janela (B) nunca aparece em altas nem baixas",
            all(p["ticker"] != "B" for p in altas + baixas))
    _checar("7b A em altas, C em baixas", altas[0]["ticker"] == "A" and baixas[0]["ticker"] == "C")


def test_8_termometro_conta_so_quem_tem_dado_valido():
    papeis = [_papel("A", "Bancos", 1.0), _papel("B", "Bancos", -1.0), _papel("C", "Bancos", None)]
    with patch.object(mercado_mod, "obter_panorama_ibovespa", return_value=papeis):
        termo = mercado_mod.obter_termometro(janela="dia")
    _checar("8 total exclui o papel sem dado (2, nao 3)", termo["total"] == 2, f"(termo={termo})")


def test_9_desempenho_setorial_setor_sem_nenhum_papel_valido_nao_aparece():
    papeis = [
        _papel("A", "Bancos", 4.0), _papel("B", "Bancos", 2.0),
        _papel("C", "Varejo", None),  # unico papel do setor Varejo, sem dado -> setor nao deveria aparecer
    ]
    with patch.object(mercado_mod, "obter_panorama_ibovespa", return_value=papeis):
        setorial = mercado_mod.obter_desempenho_setorial(janela="dia")
    setores = {s["setor"] for s in setorial}
    _checar("9a setor 'Varejo' (nenhum papel valido) nunca aparece (nunca media de lista vazia)",
            "Varejo" not in setores, f"(setores={setores})")
    bancos = next(s for s in setorial if s["setor"] == "Bancos")
    _checar("9b media do setor Bancos calculada certo ((4+2)/2=3.0)", abs(bancos["variacao_media_pct"] - 3.0) < 0.01)


def test_10_cor_treemap_limite_zero_nunca_quebra_nem_gera_nan():
    tema = config.TEMAS["AMBAR"]
    try:
        cor = mercado_tab_mod._cor_treemap(5.0, limite=0, tema=tema)
        ok = True
    except Exception as e:
        ok = False
        print("      excecao:", e)
    _checar("10a limite=0 nao lanca excecao", ok)
    _checar("10b limite=0 cai na cor neutra (cinza, t=0.0)", cor == tema["cinza"].lower() if ok else False, f"(cor={cor if ok else None})")


def test_11_cor_treemap_variacao_zero_fica_neutra():
    tema = config.TEMAS["AMBAR"]
    cor = mercado_tab_mod._cor_treemap(0.0, limite=2.0, tema=tema)
    _checar("11 variacao 0% fica exatamente na cor neutra (cinza)", cor == tema["cinza"].lower(), f"(cor={cor})")


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
    print("TODOS OS TESTES DE DATA/MERCADO.PY PASSARAM")
