# -*- coding: utf-8 -*-
"""Testes de data/earnings/editorial.py - a ponte entre o Earnings
Reviewer e a sintese editorial do Morning Call (Modulo 3). Usa as
MESMAS notas reais de test_earnings_reviewer.py (Vale/Apple) pra
verificar que a chamada editorial sai com numero real, fonte e formato
de bullet compativel com jobs/morning_call.py."""

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from data.earnings import cvm_dre, editorial, reviewer, sec_xbrl

_DIR = Path(__file__).parent / "fixtures" / "earnings"
_VALE_CSV = pd.read_csv(_DIR / "cvm_itr_dre_con_vale3_2026.csv", sep=";", encoding="latin1")


def _fake_serie_conceito_aapl(cik, tag):
    caminho = _DIR / f"sec_aapl_{tag}.json"
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)["units"]["USD"]


@pytest.fixture(autouse=True)
def _limpa_cache():
    cvm_dre._dre_itr_ano.clear()
    yield
    cvm_dre._dre_itr_ano.clear()


@pytest.fixture
def nota_vale():
    with patch.object(cvm_dre, "obter_cnpj", return_value="33.592.510/0001-54"), \
         patch.object(cvm_dre, "_baixar_csv_do_zip", return_value=_VALE_CSV):
        return reviewer.montar_nota_br("VALE3", 2026, 2)


@pytest.fixture
def nota_aapl():
    with patch.object(sec_xbrl, "obter_cik", return_value=320193), \
         patch.object(sec_xbrl, "_serie_conceito", side_effect=_fake_serie_conceito_aapl):
        return reviewer.montar_nota_internacional("AAPL", "2026-03-29", "2026-06-27", "2025-03-30", "2025-06-28")


def test_chamada_vale_tem_numero_real_e_variacao_a_a_e_t_t(nota_vale):
    chamada = editorial.montar_chamada_editorial(nota_vale)
    assert chamada is not None
    assert chamada["ticker"] == "VALE3"
    assert "VALE S.A." in chamada["titulo"]
    assert "R$53,0 bi" in chamada["resumo"] or "R$53.0 bi" in chamada["resumo"]
    assert "a/a" in chamada["resumo"] and "t/t" in chamada["resumo"]
    assert chamada["link"] == nota_vale["fontes"][0]["url"]


def test_chamada_aapl_tem_numero_real_em_dolar(nota_aapl):
    chamada = editorial.montar_chamada_editorial(nota_aapl)
    assert chamada is not None
    assert "US$109,4 bi" in chamada["resumo"].replace(".", ",") or "US$109.4 bi" in chamada["resumo"]
    assert chamada["link"].startswith("https://data.sec.gov")


def test_chamada_nota_indisponivel_devolve_none():
    assert editorial.montar_chamada_editorial({"disponivel": False}) is None


def test_chamada_sem_nenhum_numero_devolve_none():
    nota = {
        "disponivel": True, "ticker": "X3", "empresa": "X", "periodo_label": "1T2026",
        "moeda": "REAL", "escala_moeda": "MIL", "metricas": {
            "receita_liquida": {"atual": None}, "lucro_liquido_consolidado": {"atual": None},
        },
        "fontes": [{"url": "https://x", "nome": "X"}], "interpretacoes": [],
    }
    assert editorial.montar_chamada_editorial(nota) is None


def test_montar_chamadas_editoriais_filtra_indisponiveis(nota_vale):
    chamadas = editorial.montar_chamadas_editoriais([nota_vale, {"disponivel": False}])
    assert len(chamadas) == 1
    assert chamadas[0]["ticker"] == "VALE3"


def test_bullet_tem_formato_compativel_com_morning_call(nota_vale):
    chamada = editorial.montar_chamada_editorial(nota_vale)
    bullet = editorial.chamada_para_bullet(chamada)
    assert bullet.startswith("- ")
    assert " — https://" in bullet


def test_fmt_moeda_bi_mi_e_sinal_negativo():
    assert editorial._fmt_moeda(5_000_000.0, "REAL", "MIL") == "R$5.0 bi"
    assert editorial._fmt_moeda(-5_000_000.0, "REAL", "MIL") == "-R$5.0 bi"
    assert editorial._fmt_moeda(None, "REAL", "MIL") == "indisponível"


def test_fmt_variacao_direcao_correta():
    assert "alta" in editorial._fmt_variacao(10.0, "a/a")
    assert "queda" in editorial._fmt_variacao(-10.0, "a/a")
    assert editorial._fmt_variacao(None, "a/a") is None
