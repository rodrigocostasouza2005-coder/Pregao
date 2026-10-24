# -*- coding: utf-8 -*-
"""Regressão do incidente real (23/10/2026): todos os 15 ativos da
watchlist mostravam "indisponível agora" em P/L/P-VP/DY/etc, com
cotação funcionando normalmente. Causa identificada por auditoria de
código (sem acesso a logs de produção nesta sessão - ver PR/changelog
para a ressalva completa): o fallback de data/prices.py:obter_indicadores
(_ultimo_indicadores_valido, @st.cache_resource) só vive na MEMÓRIA do
processo - um restart do Streamlit Cloud (acontece a cada push pra
main) zera esse fallback. Se o Yahoo Finance estiver bloqueando tk.info
(.info) bem depois de um restart, TODOS os tickers ficam sem nenhum
valor-base, mesmo tendo funcionado minutos antes do deploy.

Estes testes cobrem o novo fallback persistido (sql/indicadores_fallback.sql,
data/prices.py:_ler_fallback_persistido/_salvar_fallback_persistido) -
sem rede/banco real, Supabase sempre mockado."""
from datetime import datetime, timezone
from unittest.mock import patch

import data.prices as prices_mod
from data.prices import obter_indicadores


class _TabelaFake:
    def __init__(self, cliente):
        self.cliente = cliente
        self._op = None
        self._filtros = {}
        self._payload = None

    def select(self, *_a, **_k):
        self._op = "select"
        return self

    def upsert(self, payload):
        self._op = "upsert"
        self._payload = dict(payload)
        return self

    def eq(self, campo, valor):
        self._filtros[campo] = valor
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        if self._op == "upsert":
            self.cliente.linhas[self._payload["ticker"]] = dict(self._payload)
            return _RespostaFake([self._payload])
        if self._op == "select":
            linha = self.cliente.linhas.get(self._filtros.get("ticker"))
            return _RespostaFake([linha] if linha else [])
        return _RespostaFake([])


class _RespostaFake:
    def __init__(self, data):
        self.data = data


class _ClienteFake:
    def __init__(self):
        self.linhas = {}

    def table(self, _nome):
        return _TabelaFake(self)


def test_coleta_bem_sucedida_persiste_o_fallback_sem_beta_nem_coletado_em():
    ticker = "TESTE_FALLBACK_PERSISTE_1"
    cliente = _ClienteFake()
    with patch.object(prices_mod, "obter_cliente", return_value=cliente), \
         patch.object(prices_mod, "_tk_info_com_retry", return_value={"trailingPE": 12.0}), \
         patch.object(prices_mod, "_calcular_beta", return_value=0.8), \
         patch.object(prices_mod, "_dividend_yield_12m", return_value=None):
        obter_indicadores(ticker)
    linha = cliente.linhas[ticker]
    assert linha["dados"]["pl"] == 12.0
    assert "beta" not in linha["dados"]
    assert "_coletado_em" not in linha["dados"]
    assert linha["coletado_em"] is not None


def test_falha_total_sem_fallback_em_memoria_usa_o_persistido():
    """O cenário real do incidente: processo recém-reiniciado
    (_ultimo_indicadores_valido em memória está vazio pra este ticker),
    Yahoo bloqueando .info agora - mas o Supabase tem o último valor
    bom persistido antes do restart."""
    ticker = "TESTE_FALLBACK_PERSISTE_2"
    cliente = _ClienteFake()
    cliente.linhas[ticker] = {
        "ticker": ticker,
        "dados": {"valor_mercado": 100.0, "pl": 9.5, "pvp": 1.5, "dividend_yield": 4.0,
                  "roe": 20.0, "margem_liquida": 10.0, "margem_operacional": 12.0,
                  "margem_ebitda": 15.0, "divida_liquida": 30.0, "divida_liquida_ebitda": 1.0},
        "coletado_em": "2026-10-20T10:00:00+00:00",
    }
    with patch.object(prices_mod, "obter_cliente", return_value=cliente), \
         patch.object(prices_mod, "_tk_info_com_retry", return_value={}), \
         patch.object(prices_mod, "_calcular_beta", return_value=None):
        resultado = obter_indicadores(ticker)
    assert resultado["pl"] == 9.5
    assert resultado["roe"] == 20.0
    assert resultado["_coletado_em"] == "2026-10-20T10:00:00+00:00"  # nunca "agora"


def test_fallback_em_memoria_tem_prioridade_sobre_o_persistido():
    """Dentro do MESMO processo, o fallback em memória (mais recente,
    sem round-trip de rede) continua vindo primeiro - o persistido é
    só pra quando a memória está vazia (pós-restart)."""
    ticker = "TESTE_FALLBACK_PERSISTE_3"
    prices_mod._ultimo_indicadores_valido()[ticker] = {
        "valor_mercado": 1.0, "pl": 1.0, "pvp": None, "dividend_yield": None, "beta": None,
        "roe": None, "margem_liquida": None, "margem_operacional": None, "margem_ebitda": None,
        "divida_liquida": None, "divida_liquida_ebitda": None, "_coletado_em": "2026-10-23T08:00:00+00:00",
    }
    cliente = _ClienteFake()
    cliente.linhas[ticker] = {
        "ticker": ticker, "dados": {"pl": 999.0}, "coletado_em": "2026-01-01T00:00:00+00:00",
    }
    with patch.object(prices_mod, "obter_cliente", return_value=cliente), \
         patch.object(prices_mod, "_tk_info_com_retry", return_value={}), \
         patch.object(prices_mod, "_calcular_beta", return_value=None):
        resultado = obter_indicadores(ticker)
    assert resultado["pl"] == 1.0  # memória, não o 999.0 do persistido


def test_sem_fallback_nenhum_nunca_lanca_excecao_e_fica_todo_none():
    ticker = "TESTE_FALLBACK_PERSISTE_4"
    with patch.object(prices_mod, "obter_cliente", return_value=None), \
         patch.object(prices_mod, "_tk_info_com_retry", return_value={}), \
         patch.object(prices_mod, "_calcular_beta", return_value=None):
        resultado = obter_indicadores(ticker)
    assert all(v is None for v in resultado.values())


def test_leitura_persistida_com_banco_fora_do_ar_e_none_nunca_excecao():
    assert prices_mod._ler_fallback_persistido("QUALQUER3") is None  # obter_cliente real sem secrets neste ambiente


def test_leitura_persistida_com_erro_de_rede_degrada_pra_none():
    cliente = _ClienteFake()
    with patch.object(cliente, "table", side_effect=RuntimeError("timeout")):
        with patch.object(prices_mod, "obter_cliente", return_value=cliente):
            assert prices_mod._ler_fallback_persistido("QUALQUER4") is None


def test_salvar_fallback_com_erro_de_rede_nunca_lanca_excecao():
    cliente = _ClienteFake()
    with patch.object(cliente, "table", side_effect=RuntimeError("timeout")):
        with patch.object(prices_mod, "obter_cliente", return_value=cliente):
            prices_mod._salvar_fallback_persistido(
                "QUALQUER5", {"pl": 1.0, "beta": 0.5, "_coletado_em": datetime.now(timezone.utc).isoformat()}
            )  # não deve lançar
