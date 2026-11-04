# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from jobs import comite_noturno as job


class _Resposta:
    def __init__(self, data):
        self.data = data


class _Tabela:
    def __init__(self, cliente):
        self.cliente = cliente
        self.operacao = None
        self.payload = None
        self.filtro = None

    def insert(self, payload):
        self.operacao, self.payload = "insert", dict(payload)
        return self

    def update(self, payload):
        self.operacao, self.payload = "update", dict(payload)
        return self

    def eq(self, _campo, valor):
        self.filtro = valor
        return self

    def execute(self):
        if self.operacao == "insert":
            linha = {"id": 1, **self.payload}
            self.cliente.linhas[1] = linha
            return _Resposta([linha])
        if self.operacao == "update":
            self.cliente.linhas[self.filtro].update(self.payload)
            return _Resposta([self.cliente.linhas[self.filtro]])
        return _Resposta([])


class _Cliente:
    def __init__(self):
        self.linhas = {}

    def table(self, _nome):
        return _Tabela(self)


def test_montar_universo_deduplica_e_prioriza_watchlists():
    universo, origens = job._montar_universo(
        {"petr4", "VALE3", "PETR4"},
        [{"ticker": "VALE3"}, {"ticker": "WEGE3"}, {"ticker": "WEGE3"}],
    )
    assert universo == ["PETR4", "VALE3", "WEGE3"]
    assert origens["PETR4"] == {"watchlist"}
    assert origens["VALE3"] == {"watchlist", "carteira_recomendada"}
    assert origens["WEGE3"] == {"carteira_recomendada"}


def test_executar_sem_supabase_cancela_sem_acionar_comite():
    with patch.object(job, "obter_cliente", return_value=None), \
         patch.object(job, "analisar_ticker") as analisar:
        assert job.executar() == 1
    analisar.assert_not_called()


def test_executar_pula_analises_recentes_e_roda_universo_deduplicado():
    cliente = _Cliente()
    resultados = [
        {"status_execucao": "CONCLUIDA", "_analise_id": "a1"},
        {"status_execucao": "CONCLUIDA", "_analise_id": "a2"},
    ]
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "uniao_watchlists_todos_usuarios", return_value={"PETR4", "VALE3"}), \
         patch.object(job, "listar_carteiras", return_value=[{"ticker": "VALE3"}, {"ticker": "WEGE3"}]), \
         patch.object(job, "_tickers_com_analise_recente", return_value={"PETR4"}), \
         patch.object(job, "analisar_ticker", side_effect=resultados) as analisar:
        assert job.executar() == 0
    assert [c.args[0] for c in analisar.call_args_list] == ["VALE3", "WEGE3"]
    linha = cliente.linhas[1]
    assert linha["tipo"] == "comite_noturno"
    assert linha["status"] == "OK"
    assert "analisados=2" in linha["resumo"]
    assert "recentes_pulados=1" in linha["resumo"]


def test_executar_respeita_limite_e_marca_parcial_quando_ha_fila():
    cliente = _Cliente()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "uniao_watchlists_todos_usuarios", return_value={"PETR4", "VALE3", "ITUB4"}), \
         patch.object(job, "listar_carteiras", return_value=[]), \
         patch.object(job, "_tickers_com_analise_recente", return_value=set()), \
         patch.object(job, "analisar_ticker", return_value={"status_execucao": "CONCLUIDA"}) as analisar:
        assert job.executar(limite=2) == 0
    assert [c.args[0] for c in analisar.call_args_list] == ["ITUB4", "PETR4"]
    assert cliente.linhas[1]["status"] == "PARCIAL"
    assert "aguardando_proxima_rodada=1" in cliente.linhas[1]["resumo"]


def test_executar_interrompe_se_consulta_de_idempotencia_falhar():
    cliente = _Cliente()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "uniao_watchlists_todos_usuarios", return_value={"PETR4"}), \
         patch.object(job, "listar_carteiras", return_value=[]), \
         patch.object(job, "_tickers_com_analise_recente", return_value=None), \
         patch.object(job, "analisar_ticker") as analisar:
        assert job.executar() == 1
    analisar.assert_not_called()
    assert cliente.linhas[1]["status"] == "ERRO"


def test_falha_de_um_ticker_nao_impede_os_demais():
    cliente = _Cliente()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "uniao_watchlists_todos_usuarios", return_value={"PETR4", "VALE3"}), \
         patch.object(job, "listar_carteiras", return_value=[]), \
         patch.object(job, "_tickers_com_analise_recente", return_value=set()), \
         patch.object(job, "analisar_ticker", side_effect=[RuntimeError("falha isolada"), {"status_execucao": "CONCLUIDA"}]):
        assert job.executar() == 0
    assert cliente.linhas[1]["status"] == "PARCIAL"
    assert "falhas=1" in cliente.linhas[1]["resumo"]
