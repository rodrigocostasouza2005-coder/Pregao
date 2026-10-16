# -*- coding: utf-8 -*-
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.radar_quedas import calcular_queda, deve_alertar, avaliar_ticker, registrar_alerta


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
    # Regressão: avaliar_ticker lia a chave errada ("_coletado_em", que
    # obter_cotacao() nunca produz) - o horário real da cotação nunca
    # chegava no alerta, sempre caía no fallback (agora). A chave real é
    # "cotacao_em" (ver data/prices.py:obter_cotacao).
    assert alerta["cotacao_em"] == "2026-10-14T12:00:00-03:00"



def test_monitoramento_nao_usa_carteiras_antigas_quando_todas_fontes_falham():
    from unittest.mock import patch
    import data.radar_quedas as radar
    with patch.object(radar, "coletar_carteiras_genial", return_value=None), \
         patch.object(radar, "coletar_carteiras_safra", return_value=None), \
         patch.object(radar, "listar_carteiras", return_value=[{"ticker": "PETR4"}]), \
         patch.object(radar, "obter_cotacao") as cotacao:
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is False
    assert resultado["alertas_novos"] == []
    cotacao.assert_not_called()


def test_monitoramento_continua_quando_so_uma_fonte_falha():
    """Requisito do Radar multi-fonte: Genial bloqueada não pode impedir
    a avaliação das recomendações que a Safra entregou normalmente."""
    from unittest.mock import patch
    import data.radar_quedas as radar
    item_safra = {"ticker": "PETR4", "empresa": "Petrobras", "casa": "Safra Corretora",
                  "carteira": "Top 10 Ações", "fonte_url": "https://safra/x"}
    with patch.object(radar, "coletar_carteiras_genial", return_value=None), \
         patch.object(radar, "coletar_carteiras_safra", return_value=[item_safra]), \
         patch.object(radar, "salvar_carteiras", return_value=True) as salvar, \
         patch.object(radar, "listar_carteiras", return_value=[item_safra]), \
         patch.object(radar, "obter_cotacao", return_value={"erro": "indisponível"}) as cotacao:
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is True
    assert resultado["fontes"]["Genial Analisa"] == "fonte indisponível"
    assert resultado["fontes"]["Safra Corretora"].startswith("ok")
    salvar.assert_called_once_with("Safra Corretora", [item_safra])
    cotacao.assert_called_once_with("PETR4")


def test_monitoramento_para_persistir_uma_fonte_nao_bloqueia_a_outra():
    from unittest.mock import patch
    import data.radar_quedas as radar
    item_genial = {"ticker": "VALE3", "carteira": "Top 10"}
    item_safra = {"ticker": "PETR4", "carteira": "Top 10 Ações"}

    def _salvar(casa, itens):
        return casa == "Safra Corretora"

    with patch.object(radar, "coletar_carteiras_genial", return_value=[item_genial]), \
         patch.object(radar, "coletar_carteiras_safra", return_value=[item_safra]), \
         patch.object(radar, "salvar_carteiras", side_effect=_salvar), \
         patch.object(radar, "listar_carteiras", return_value=[item_safra]), \
         patch.object(radar, "obter_cotacao", return_value={"erro": "indisponível"}):
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is True
    assert "falha ao persistir" in resultado["fontes"]["Genial Analisa"]
    assert resultado["fontes"]["Safra Corretora"].startswith("ok")


def test_monitoramento_rejeita_snapshot_vazio_e_preserva_carteiras_dessa_casa():
    from unittest.mock import patch
    import data.radar_quedas as radar
    with patch.object(radar, "coletar_carteiras_genial", return_value=[]), \
         patch.object(radar, "coletar_carteiras_safra", return_value=None), \
         patch.object(radar, "salvar_carteiras") as salvar, \
         patch.object(radar, "listar_carteiras") as listar, \
         patch.object(radar, "obter_cotacao") as cotacao:
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is False
    assert resultado["alertas_novos"] == []
    assert "snapshot vazio" in resultado["fontes"]["Genial Analisa"]
    salvar.assert_not_called()
    listar.assert_not_called()
    cotacao.assert_not_called()


def test_variacao_positiva_nao_alerta():
    recs = [{"ticker": "PETR4", "casa": "Casa A", "carteira": "X"}]
    cot = {"preco": 105.0, "fechamento_anterior": 100.0, "cotacao_em": "2026-10-16T10:00:00-03:00"}
    assert avaliar_ticker("PETR4", cot, recs) is None


def test_cotacao_com_erro_nao_gera_alerta_falso():
    recs = [{"ticker": "PETR4", "casa": "Casa A", "carteira": "X"}]
    cot = {"erro": "symbol not found"}
    assert avaliar_ticker("PETR4", cot, recs) is None


def test_cotacao_sem_fechamento_anterior_nao_gera_alerta_falso():
    """O provedor pode devolver preço sem o fechamento anterior (campo
    ausente) - sem uma referência real pra calcular a queda, nunca
    estima/inventa um fechamento, só recusa o alerta."""
    recs = [{"ticker": "PETR4", "casa": "Casa A", "carteira": "X"}]
    cot = {"preco": 90.0, "fechamento_anterior": None}
    assert avaliar_ticker("PETR4", cot, recs) is None


def test_cotacao_nao_e_dict_nao_gera_alerta_falso():
    recs = [{"ticker": "PETR4", "casa": "Casa A", "carteira": "X"}]
    assert avaliar_ticker("PETR4", None, recs) is None


def test_listar_carteiras_exclui_carteira_expirada():
    """Carteira mensal cuja última confirmação real passou de
    IDADE_MAXIMA_CARTEIRA_DIAS não é apresentada como atual, mesmo com
    vigente=True ainda gravado no banco (a fonte parou de confirmar, não
    necessariamente removeu a linha)."""
    import data.radar_quedas as radar
    agora = datetime.now(timezone.utc)
    linha_fresca = {"ticker": "PETR4", "casa": "Safra Corretora",
                     "verificado_em": agora.isoformat()}
    linha_expirada = {"ticker": "VALE3", "casa": "Genial Analisa",
                       "verificado_em": (agora - timedelta(days=radar.IDADE_MAXIMA_CARTEIRA_DIAS + 1)).isoformat()}
    cliente = MagicMock()
    resposta = MagicMock()
    resposta.data = [linha_fresca, linha_expirada]
    cliente.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = resposta
    with patch.object(radar, "obter_cliente", return_value=cliente):
        resultado = radar.listar_carteiras()
    assert resultado == [linha_fresca]


def test_listar_carteiras_sem_verificado_em_nao_quebra():
    import data.radar_quedas as radar
    linha_sem_campo = {"ticker": "PETR4", "casa": "Safra Corretora"}
    cliente = MagicMock()
    resposta = MagicMock()
    resposta.data = [linha_sem_campo]
    cliente.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = resposta
    with patch.object(radar, "obter_cliente", return_value=cliente):
        resultado = radar.listar_carteiras()
    assert resultado == [linha_sem_campo]


def test_registrar_alerta_e_idempotente_mesmo_ticker_mesmo_pregao():
    """Duas execuções no mesmo pregão não podem duplicar o alerta."""
    cliente = MagicMock()
    alerta = {"ticker": "PETR4", "pregao": "2026-10-16"}

    resposta_vazia = MagicMock(data=[])
    resposta_com_insercao = MagicMock(data=[{"id": 42}])
    cliente.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = resposta_vazia
    cliente.table.return_value.insert.return_value.execute.return_value = resposta_com_insercao

    with patch("data.radar_quedas.obter_cliente", return_value=cliente):
        ok1, id1 = registrar_alerta(alerta)
    assert ok1 is True and id1 == 42
    assert cliente.table.return_value.insert.call_count == 1

    # Segunda chamada: já existe um registro pro mesmo ticker+pregão -
    # não insere de novo.
    resposta_ja_existe = MagicMock(data=[{"id": 42}])
    cliente.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = resposta_ja_existe
    with patch("data.radar_quedas.obter_cliente", return_value=cliente):
        ok2, id2 = registrar_alerta(alerta)
    assert ok2 is True and id2 is None  # já existia; não duplica
    assert cliente.table.return_value.insert.call_count == 1  # continua em 1, não subiu pra 2


def test_registrar_alerta_falha_de_persistencia_nunca_lanca_excecao():
    cliente = MagicMock()
    cliente.table.side_effect = Exception("Supabase fora do ar")
    with patch("data.radar_quedas.obter_cliente", return_value=cliente):
        ok, alerta_id = registrar_alerta({"ticker": "PETR4", "pregao": "2026-10-16"})
    assert ok is False and alerta_id is None


def test_monitoramento_sem_queda_elegivel_e_execucao_valida():
    """Nenhuma ação cruzou o limiar de -4% - execução continua válida
    (coleta_ok=True), só sem alertas novos."""
    import data.radar_quedas as radar
    item = {"ticker": "PETR4", "casa": "Safra Corretora", "carteira": "Top 10 Ações"}
    cotacao_sem_queda = {"preco": 99.0, "fechamento_anterior": 100.0, "cotacao_em": "2026-10-16T10:00:00-03:00"}
    with patch.object(radar, "coletar_carteiras_genial", return_value=None), \
         patch.object(radar, "coletar_carteiras_safra", return_value=[item]), \
         patch.object(radar, "salvar_carteiras", return_value=True), \
         patch.object(radar, "listar_carteiras", return_value=[item]), \
         patch.object(radar, "obter_cotacao", return_value=cotacao_sem_queda), \
         patch.object(radar, "registrar_alerta") as registrar:
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is True
    assert resultado["alertas_novos"] == []
    assert resultado["total_tickers"] == 1
    registrar.assert_not_called()
