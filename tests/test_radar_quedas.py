# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.radar_quedas import calcular_queda, deve_alertar, avaliar_ticker


def test_calculo_queda():
    assert round(calcular_queda(95.99, 100), 2) == -4.01
    assert calcular_queda(96, 100) == -4.0
    assert calcular_queda(0, 100) is None
    assert calcular_queda(95, None) is None


def test_limite_estrito():
    assert not deve_alertar(-3.5)
    assert not deve_alertar(-4.0)
    assert deve_alertar(-4.01)
    assert deve_alertar(-5.2)
    assert not deve_alertar(None)


def test_alerta_consolida_carteiras():
    recs = [
        {"ticker": "PETR4", "casa": "Casa A", "carteira": "Dividendos", "fonte_url": "https://a"},
        {"ticker": "PETR4", "casa": "Casa B", "carteira": "Top 10", "fonte_url": "https://b"},
    ]
    cot = {"preco": 95.9, "fechamento_anterior": 100, "variacao_pct": -4.1, "cotacao_em": "2026-10-14T12:00:00-03:00"}
    from datetime import datetime
    from zoneinfo import ZoneInfo
    alerta = avaliar_ticker("PETR4", cot, recs, datetime(2026, 10, 14, 12, tzinfo=ZoneInfo("America/Sao_Paulo")))
    assert alerta and len(alerta["casas"]) == 2 and len(alerta["carteiras"]) == 2



def test_monitoramento_nao_usa_carteiras_antigas_quando_fonte_falha():
    from unittest.mock import patch
    import data.radar_quedas as radar
    with patch.object(radar, "coletar_carteiras_genial", return_value=None), \
         patch.object(radar, "listar_carteiras", return_value=[{"ticker": "PETR4"}]), \
         patch.object(radar, "obter_cotacao") as cotacao:
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is False
    assert resultado["alertas_novos"] == []
    cotacao.assert_not_called()


def test_monitoramento_para_se_nao_persistir_coleta():
    from unittest.mock import patch
    import data.radar_quedas as radar
    with patch.object(radar, "coletar_carteiras_genial", return_value=[{"ticker": "PETR4", "carteira": "Top 10"}]), \
         patch.object(radar, "salvar_carteiras", return_value=False), \
         patch.object(radar, "listar_carteiras") as listar, \
         patch.object(radar, "obter_cotacao") as cotacao:
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is False
    listar.assert_not_called()
    cotacao.assert_not_called()

def test_monitoramento_rejeita_snapshot_vazio_e_preserva_carteiras():
    from unittest.mock import patch
    import data.radar_quedas as radar
    with patch.object(radar, "coletar_carteiras_genial", return_value=[]), \
         patch.object(radar, "salvar_carteiras") as salvar, \
         patch.object(radar, "listar_carteiras") as listar, \
         patch.object(radar, "obter_cotacao") as cotacao:
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is False
    assert resultado["alertas_novos"] == []
    assert "zero recomendações" in resultado["erro"]
    salvar.assert_not_called()
    listar.assert_not_called()
    cotacao.assert_not_called()


def test_avaliar_ticker_cotacao_com_erro_nao_gera_alerta_falso():
    """Ausência/erro de cotação nunca equivale a variação zero nem a
    queda - não há como calcular a variação, então não há alerta."""
    recs = [{"ticker": "PETR4", "casa": "Genial Analisa", "carteira": "X", "fonte_url": "https://x"}]
    cot = {"erro": "symbol não encontrado"}
    assert avaliar_ticker("PETR4", cot, recs) is None


def test_avaliar_ticker_sem_fechamento_anterior_nao_gera_alerta_falso():
    """Cotação atrasada/sem referência de fechamento anterior - sem
    referência válida, não há como calcular a variação diária real."""
    recs = [{"ticker": "PETR4", "casa": "Genial Analisa", "carteira": "X", "fonte_url": "https://x"}]
    cot = {"preco": 90.0, "fechamento_anterior": None}
    assert avaliar_ticker("PETR4", cot, recs) is None


def test_avaliar_ticker_queda_exata_5_por_cento_dispara():
    recs = [{"ticker": "PETR4", "casa": "Genial Analisa", "carteira": "X", "fonte_url": "https://x"}]
    cot = {"preco": 95.0, "fechamento_anterior": 100.0, "_coletado_em": "2026-10-16T14:00:00+00:00"}
    alerta = avaliar_ticker("PETR4", cot, recs)
    assert alerta is not None
    assert round(alerta["variacao_pct"], 2) == -5.0


class _FakeQuery:
    """Dublê mínimo de uma query do cliente Supabase pra testar
    registrar_alerta sem rede: encadeia select/eq/limit/insert/execute
    como o client real, mas devolve dados controlados pelo teste."""

    def __init__(self, select_rows=None, insert_raises=None, insert_rows=None):
        self.select_rows = select_rows if select_rows is not None else []
        self.insert_raises = insert_raises
        self.insert_rows = insert_rows if insert_rows is not None else []
        self.inserted_payload = None
        self._modo = None

    def select(self, *_a):
        self._modo = "select"
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    def insert(self, payload):
        self._modo = "insert"
        self.inserted_payload = payload
        return self

    def execute(self):
        if self._modo == "insert":
            if self.insert_raises is not None:
                raise self.insert_raises
            return type("R", (), {"data": self.insert_rows})()
        return type("R", (), {"data": self.select_rows})()


class _FakeCliente:
    def __init__(self, query):
        self._query = query

    def table(self, _nome):
        return self._query


def test_registrar_alerta_idempotente_quando_ja_existe(monkeypatch):
    """Duas execuções idênticas (mesmo ticker + mesmo pregão) nunca
    duplicam o alerta - registrar_alerta confere antes de inserir."""
    import data.radar_quedas as radar
    query = _FakeQuery(select_rows=[{"id": 42}])
    monkeypatch.setattr(radar, "obter_cliente", lambda: _FakeCliente(query))

    ok, alerta_id = radar.registrar_alerta({"ticker": "PETR4", "pregao": "2026-10-16"})

    assert ok is True
    assert alerta_id is None  # já existia - não é um novo id gerado agora
    assert query._modo == "select"  # nunca chegou a tentar inserir de novo


def test_registrar_alerta_falha_de_persistencia_retorna_false(monkeypatch):
    """Falha ao gravar (ex: RLS/conexão) é reportada como falha, nunca
    como sucesso silencioso - quem chama conta isso como alerta não
    persistido."""
    import data.radar_quedas as radar
    query = _FakeQuery(select_rows=[], insert_raises=Exception("conexão perdida"))
    monkeypatch.setattr(radar, "obter_cliente", lambda: _FakeCliente(query))

    ok, alerta_id = radar.registrar_alerta({"ticker": "VALE3", "pregao": "2026-10-16"})

    assert ok is False
    assert alerta_id is None
