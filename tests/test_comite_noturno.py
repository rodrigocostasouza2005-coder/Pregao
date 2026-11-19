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


# ============================================================
# Camada hibrida de IA real (Groq) - missão "PREGÃO 2.3-B", 2026-11-13.
# DESLIGADA por padrão (config.sintese_ia_comite_ativa() == False) - ver
# config.py. Estes testes cobrem o guard de custo (_deve_usar_sintese_ia)
# e a fiação em executar(), nunca fazem chamada real de rede/IA.
# ============================================================

def test_deve_usar_sintese_ia_false_quando_desligada_por_config():
    assert job._deve_usar_sintese_ia(
        "PETR4", ia_ativa=False, limite=20, sinteses_usadas=0, tickers_com_sintese_ia=set(),
    ) is False


def test_deve_usar_sintese_ia_nunca_repete_o_mesmo_ticker_na_mesma_rodada():
    assert job._deve_usar_sintese_ia(
        "PETR4", ia_ativa=True, limite=20, sinteses_usadas=1, tickers_com_sintese_ia={"PETR4"},
    ) is False


def test_deve_usar_sintese_ia_respeita_o_teto_por_rodada():
    assert job._deve_usar_sintese_ia(
        "PETR4", ia_ativa=True, limite=2, sinteses_usadas=2, tickers_com_sintese_ia=set(),
    ) is False


def test_deve_usar_sintese_ia_true_quando_ativa_sem_repeticao_e_sob_o_teto():
    assert job._deve_usar_sintese_ia(
        "PETR4", ia_ativa=True, limite=2, sinteses_usadas=1, tickers_com_sintese_ia={"VALE3"},
    ) is True


def test_executar_nunca_passa_sintese_ia_quando_config_esta_desligada():
    """config.sintese_ia_comite_ativa() é o default real (False) - nenhum
    chamador precisa mockar nada pra este teste valer; mockado aqui só
    pra deixar explícito o que está sendo validado."""
    cliente = _Cliente()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "uniao_watchlists_todos_usuarios", return_value={"PETR4", "VALE3"}), \
         patch.object(job, "listar_carteiras", return_value=[]), \
         patch.object(job, "_tickers_com_analise_recente", return_value=set()), \
         patch.object(job.config, "sintese_ia_comite_ativa", return_value=False), \
         patch.object(job, "analisar_ticker", return_value={"status_execucao": "CONCLUIDA"}) as analisar:
        assert job.executar() == 0
    assert [c.kwargs.get("sintese_ia") for c in analisar.call_args_list] == [False, False]
    assert "sinteses_ia=0" in cliente.linhas[1]["resumo"]


def test_executar_com_ia_ativa_respeita_limite_por_noite_e_nao_repete_ticker():
    cliente = _Cliente()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "uniao_watchlists_todos_usuarios", return_value={"PETR4", "VALE3", "ITUB4"}), \
         patch.object(job, "listar_carteiras", return_value=[]), \
         patch.object(job, "_tickers_com_analise_recente", return_value=set()), \
         patch.object(job.config, "sintese_ia_comite_ativa", return_value=True), \
         patch.object(job.config, "limite_sinteses_ia_comite_por_noite", return_value=2), \
         patch.object(job, "analisar_ticker", return_value={"status_execucao": "CONCLUIDA"}) as analisar:
        assert job.executar() == 0
    tickers_chamados = [c.args[0] for c in analisar.call_args_list]
    sintese_passada = [c.kwargs.get("sintese_ia") for c in analisar.call_args_list]
    assert tickers_chamados == ["ITUB4", "PETR4", "VALE3"]
    # Só os 2 primeiros (teto configurado=2) pedem IA; o 3º é analisado
    # normalmente (deterministico), nunca pulado.
    assert sintese_passada == [True, True, False]
    assert "sinteses_ia=2" in cliente.linhas[1]["resumo"]
