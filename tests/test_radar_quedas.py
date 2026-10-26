# -*- coding: utf-8 -*-
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.radar_quedas import (
    calcular_queda, deve_alertar, avaliar_ticker, registrar_alerta,
    resumo_fontes_vigentes, salvar_carteiras,
)


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
         patch.object(radar, "salvar_carteiras", return_value=(True, None)) as salvar, \
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
        if casa == "Safra Corretora":
            return True, None
        return False, "erro simulado"

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


# ---- salvar_carteiras: regressão P0 (SAÚDE DOS DADOS 2026-10-26) -------
# Achado real: Safra obteve 10 recomendações, gravação reportada como
# falha, zero registros novos no Radar. Causa: upsert + "desativa tudo
# da casa" + N updates sequenciais de reativação (1 por ticker/carteira)
# - qualquer exceção no loop de reativação (rede, timeout) deixava os 10
# itens PERSISTIDOS pelo upsert, mas com vigente=False (invisíveis em
# listar_carteiras), e reportava "falha ao persistir" genérico, sem a
# exceção real. Ver docstring de salvar_carteiras em data/radar_quedas.py.

def test_salvar_carteiras_sem_cliente_retorna_erro_sem_excecao():
    import data.radar_quedas as radar
    with patch.object(radar, "obter_cliente", return_value=None):
        ok, erro = salvar_carteiras("Safra Corretora", [{"ticker": "PETR4", "carteira": "Top 10"}])
    assert ok is False
    assert erro and "supabase" in erro.lower()


def test_salvar_carteiras_itens_vazios_nao_chama_banco():
    import data.radar_quedas as radar
    cliente = MagicMock()
    with patch.object(radar, "obter_cliente", return_value=cliente):
        ok, erro = salvar_carteiras("Safra Corretora", [])
    assert (ok, erro) == (True, None)
    cliente.table.assert_not_called()


def test_salvar_carteiras_um_unico_upsert_grava_vigente_e_verificado_em():
    """Dez itens (mesmo volume do incidente real) persistidos num ÚNICO
    upsert, já com vigente=True/verificado_em preenchidos - sem o loop de
    N updates sequenciais que causava o bug."""
    import data.radar_quedas as radar
    itens = [{"ticker": f"T{i}", "carteira": "Top 10 Ações", "casa": "Safra Corretora",
              "fonte_url": "https://safra/x"} for i in range(10)]
    cliente = MagicMock()
    with patch.object(radar, "obter_cliente", return_value=cliente):
        ok, erro = salvar_carteiras("Safra Corretora", itens)
    assert (ok, erro) == (True, None)
    cliente.table.return_value.upsert.assert_called_once()
    payload = cliente.table.return_value.upsert.call_args[0][0]
    assert len(payload) == 10
    assert all(item["vigente"] is True and item["verificado_em"] for item in payload)
    assert cliente.table.return_value.upsert.call_args[1]["on_conflict"] == "casa,ticker,carteira"


def test_salvar_carteiras_dedup_por_chave_evita_conflito_de_lote():
    """Mesma composição (ticker, carteira) aparecendo 2x na fonte (ex:
    tabela repetida em 2 páginas do PDF) não pode ir duplicada no mesmo
    upsert - o Postgres rejeita o lote inteiro com 'ON CONFLICT DO UPDATE
    command cannot affect row a second time'."""
    import data.radar_quedas as radar
    itens = [
        {"ticker": "PETR4", "carteira": "Top 10 Ações", "casa": "Safra Corretora", "preco_alvo": None},
        {"ticker": "PETR4", "carteira": "Top 10 Ações", "casa": "Safra Corretora", "preco_alvo": None},
        {"ticker": "VALE3", "carteira": "Top 10 Ações", "casa": "Safra Corretora", "preco_alvo": None},
    ]
    cliente = MagicMock()
    with patch.object(radar, "obter_cliente", return_value=cliente):
        ok, erro = salvar_carteiras("Safra Corretora", itens)
    assert (ok, erro) == (True, None)
    payload = cliente.table.return_value.upsert.call_args[0][0]
    chaves = [(i["ticker"], i["carteira"]) for i in payload]
    assert len(chaves) == len(set(chaves)) == 2


def test_salvar_carteiras_falha_no_upsert_retorna_a_excecao_real():
    """O painel SAÚDE DOS DADOS precisa da causa real (tabela, permissão,
    conflito de chave), não um rótulo genérico - ver data/saude_dados.py
    e jobs/radar_quedas.py:_registrar_tentativas_por_casa."""
    import data.radar_quedas as radar
    cliente = MagicMock()
    cliente.table.return_value.upsert.return_value.execute.side_effect = RuntimeError("42501: permission denied")
    with patch.object(radar, "obter_cliente", return_value=cliente):
        ok, erro = salvar_carteiras("Safra Corretora", [{"ticker": "PETR4", "carteira": "Top 10 Ações"}])
    assert ok is False
    assert "42501" in erro and "permission denied" in erro


def test_salvar_carteiras_falha_so_na_desativacao_nao_perde_dados_confirmados():
    """Os itens confirmados nesta coleta já foram persistidos (upsert com
    sucesso) - uma falha isolada ao desativar recomendações antigas dessa
    casa não pode fazer a coleta inteira ser reportada como perdida."""
    import data.radar_quedas as radar
    cliente = MagicMock()
    cliente.table.return_value.update.return_value.eq.return_value.lt.return_value.execute.side_effect = (
        RuntimeError("timeout")
    )
    with patch.object(radar, "obter_cliente", return_value=cliente):
        ok, erro = salvar_carteiras("Safra Corretora", [{"ticker": "PETR4", "carteira": "Top 10 Ações"}])
    assert (ok, erro) == (True, None)
    cliente.table.return_value.upsert.assert_called_once()


def test_salvar_carteiras_chamado_2x_com_mesmos_itens_e_idempotente():
    """Reexecutar com a MESMA coleta não deve duplicar nem lançar excecao
    (mesma garantia de on_conflict usada no upsert)."""
    import data.radar_quedas as radar
    itens = [{"ticker": "PETR4", "carteira": "Top 10 Ações", "casa": "Safra Corretora"}]
    cliente = MagicMock()
    with patch.object(radar, "obter_cliente", return_value=cliente):
        primeira = salvar_carteiras("Safra Corretora", itens)
        segunda = salvar_carteiras("Safra Corretora", itens)
    assert primeira == (True, None)
    assert segunda == (True, None)
    assert cliente.table.return_value.upsert.call_count == 2


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


def test_registrar_alerta_nao_duplica_quando_cotacao_repete_em_feriado():
    """Feriado em dia util: cron roda (schedule e' so' por dia da semana,
    nao exclui feriado - ver .github/workflows/radar-morning-call.yml),
    yfinance devolve a MESMA cotacao do ultimo pregao real (sem negocio
    novo), mas 'pregao' (data de hoje) e' uma chave NOVA - sem a checagem
    de cotacao repetida, isso reenviaria o alerta do mesmo evento."""
    cliente = MagicMock()
    alerta = {
        "ticker": "PETR4", "pregao": "2026-11-02",  # feriado (Finados), dia util
        "preco_atual": 95.9, "fechamento_anterior": 100.0,
    }
    resposta_vazia = MagicMock(data=[])
    resposta_ultimo_igual = MagicMock(data=[{"preco_atual": 95.9, "fechamento_anterior": 100.0}])
    cliente.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = resposta_vazia
    cliente.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = resposta_ultimo_igual

    with patch("data.radar_quedas.obter_cliente", return_value=cliente):
        ok, alerta_id = registrar_alerta(alerta)
    assert ok is True and alerta_id is None
    cliente.table.return_value.insert.assert_not_called()


def test_registrar_alerta_cotacao_diferente_do_ultimo_insere_normalmente():
    """Pregão novo com cotação REALMENTE diferente do último alerta (uma
    nova queda de verdade, não o mesmo evento repetido) continua inserindo."""
    cliente = MagicMock()
    alerta = {
        "ticker": "PETR4", "pregao": "2026-10-20",
        "preco_atual": 88.0, "fechamento_anterior": 93.0,
    }
    resposta_vazia = MagicMock(data=[])
    resposta_ultimo_diferente = MagicMock(data=[{"preco_atual": 95.9, "fechamento_anterior": 100.0}])
    resposta_com_insercao = MagicMock(data=[{"id": 99}])
    cliente.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = resposta_vazia
    cliente.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = resposta_ultimo_diferente
    cliente.table.return_value.insert.return_value.execute.return_value = resposta_com_insercao

    with patch("data.radar_quedas.obter_cliente", return_value=cliente):
        ok, alerta_id = registrar_alerta(alerta)
    assert ok is True and alerta_id == 99
    cliente.table.return_value.insert.assert_called_once()


def test_registrar_alerta_fechamento_anterior_diferente_nao_e_tratado_como_mesmo_evento():
    """_mesma_cotacao exige preco_atual E fechamento_anterior iguais - um
    preco_atual que bate por coincidencia com o ultimo alerta, mas com
    fechamento_anterior diferente (ex: ajuste de proventos/split entre
    pregões), não pode ser tratado como o mesmo evento de queda."""
    cliente = MagicMock()
    alerta = {"ticker": "PETR4", "pregao": "2026-10-20", "preco_atual": 95.9, "fechamento_anterior": 90.0}
    resposta_vazia = MagicMock(data=[])
    resposta_ultimo = MagicMock(data=[{"preco_atual": 95.9, "fechamento_anterior": 100.0}])  # só fechamento difere
    resposta_insercao = MagicMock(data=[{"id": 7}])
    cliente.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = resposta_vazia
    cliente.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = resposta_ultimo
    cliente.table.return_value.insert.return_value.execute.return_value = resposta_insercao

    with patch("data.radar_quedas.obter_cliente", return_value=cliente):
        ok, alerta_id = registrar_alerta(alerta)
    assert ok is True and alerta_id == 7
    cliente.table.return_value.insert.assert_called_once()


def test_registrar_alerta_sem_pregao_falha_de_forma_segura_sem_inserir():
    """Alerta malformado (sem a chave 'pregao') nunca pode lançar exceção
    pro chamador nem inserir - falha segura (ok=False), mesmo
    comportamento de qualquer outra falha de persistência (nunca envia
    e-mail de um alerta que não foi confirmado como persistido)."""
    cliente = MagicMock()
    with patch("data.radar_quedas.obter_cliente", return_value=cliente):
        ok, alerta_id = registrar_alerta({"ticker": "PETR4", "preco_atual": 90.0, "fechamento_anterior": 95.0})
    assert ok is False and alerta_id is None
    cliente.table.return_value.insert.assert_not_called()


class _TabelaAlertasFake:
    """Fake MINIMO da tabela radar_alertas_queda que persiste de verdade
    entre chamadas (em memoria) - ao contrario dos outros testes deste
    arquivo (que so' mockam o retorno de cada chamada isolada), este
    fake deixa o comportamento de dedupe de registrar_alerta rodar POR
    INTEIRO contra um estado real que cresce entre pregões simulados."""

    def __init__(self):
        self.linhas = []
        self._next_id = 1
        self._filtros = {}
        self._limit = None
        self._order_desc = False
        self._pendente_insert = None

    def select(self, *_a):
        self._filtros = {}
        self._limit = None
        self._order_desc = False
        return self

    def eq(self, campo, valor):
        self._filtros[campo] = valor
        return self

    def order(self, _campo, desc=False):
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def insert(self, payload):
        self._pendente_insert = dict(payload)
        return self

    def execute(self):
        if self._pendente_insert is not None:
            linha = self._pendente_insert
            linha["id"] = self._next_id
            self._next_id += 1
            self.linhas.append(linha)
            self._pendente_insert = None
            return MagicMock(data=[linha])
        resultado = [l for l in self.linhas if all(l.get(k) == v for k, v in self._filtros.items())]
        resultado.sort(key=lambda l: l.get("pregao", ""), reverse=self._order_desc)
        if self._limit:
            resultado = resultado[: self._limit]
        return MagicMock(data=resultado)


class _ClienteAlertasFake:
    def __init__(self):
        self.tabela = _TabelaAlertasFake()

    def table(self, nome):
        assert nome == "radar_alertas_queda"
        return self.tabela


def test_fluxo_completo_feriado_nao_duplica_email_mas_evento_novo_alerta_em_outro_pregao():
    """Reproduz 3 pregões em sequência pro mesmo ticker contra um client
    FAKE que persiste de verdade (não só mocka retorno isolado): pregão 1
    insere normalmente (candidato real a e-mail); pregão 2 é feriado com
    a MESMA cotação do pregão 1 (não insere, não é candidato a e-mail -
    reproduz data.radar_quedas.processar_monitoramento, que só acrescenta
    a 'novos'/candidatos de e-mail quando ok and alerta_id is not None);
    pregão 3 é um pregão real com queda NOVA (insere de novo, volta a ser
    candidato a e-mail)."""
    cliente = _ClienteAlertasFake()
    candidatos_email = []

    def _processar(alerta):
        with patch("data.radar_quedas.obter_cliente", return_value=cliente):
            ok, alerta_id = registrar_alerta(alerta)
        if ok and alerta_id is not None:  # mesma condição de processar_monitoramento
            candidatos_email.append(alerta["pregao"])
        return ok, alerta_id

    pregao_1 = {"ticker": "PETR4", "pregao": "2026-10-30", "preco_atual": 95.9, "fechamento_anterior": 100.0}
    pregao_2_feriado = {"ticker": "PETR4", "pregao": "2026-11-02", "preco_atual": 95.9, "fechamento_anterior": 100.0}
    pregao_3_evento_novo = {"ticker": "PETR4", "pregao": "2026-11-03", "preco_atual": 85.0, "fechamento_anterior": 95.9}

    assert _processar(pregao_1) == (True, 1)
    assert _processar(pregao_2_feriado) == (True, None)  # mesmo evento - não duplica, não vira e-mail
    assert _processar(pregao_3_evento_novo) == (True, 2)  # evento novo, pregão novo - insere e vira e-mail

    assert candidatos_email == ["2026-10-30", "2026-11-03"]  # feriado nunca gerou candidato a e-mail
    assert len(cliente.tabela.linhas) == 2  # só 2 linhas persistidas (pregão do feriado nunca foi inserido)


def test_registrar_alerta_falha_de_persistencia_nunca_lanca_excecao():
    cliente = MagicMock()
    cliente.table.side_effect = Exception("Supabase fora do ar")
    with patch("data.radar_quedas.obter_cliente", return_value=cliente):
        ok, alerta_id = registrar_alerta({"ticker": "PETR4", "pregao": "2026-10-16"})
    assert ok is False and alerta_id is None


def test_resumo_fontes_vigentes_agrupa_por_casa_e_conta_ativos_unicos():
    """UI precisa saber 'quais fontes estao atualizadas agora' (secao 7
    do pedido) sem nenhuma chamada de rede nova - so' agrega o que
    listar_carteiras() (ja filtrado por vigente e nao-expirado) devolve.
    PETR4 repetido (2 carteiras da mesma casa) conta 1 ativo so'."""
    import data.radar_quedas as radar
    agora = datetime.now(timezone.utc)
    recente = (agora - timedelta(hours=1)).isoformat()
    linhas = [
        {"casa": "Safra Corretora", "ticker": "PETR4", "verificado_em": recente},
        {"casa": "Safra Corretora", "ticker": "VALE3", "verificado_em": recente},
        {"casa": "Safra Corretora", "ticker": "PETR4", "verificado_em": (agora - timedelta(hours=25)).isoformat()},
    ]
    with patch.object(radar, "listar_carteiras", return_value=linhas):
        resumo = resumo_fontes_vigentes()
    assert resumo == {
        "Safra Corretora": {"ativos": 2, "verificado_em": recente, "desatualizada": False,
                            "carteiras": [], "data_publicacao": None},
    }
    assert "Genial Analisa" not in resumo  # sem linha vigente -> casa ausente (UI rotula "indisponível")


def test_resumo_fontes_vigentes_marca_desatualizada_apos_idade_fresca_horas():
    """Distingue 'atualizada' (confirmação recente) de 'desatualizada'
    (ainda vigente/não-expirada, mas sem confirmação há mais de
    IDADE_FRESCA_HORAS) - sem essa distinção, uma carteira confirmada há
    quase 40 dias (IDADE_MAXIMA_CARTEIRA_DIAS, ainda listada) apareceria
    como 'atualizada' igual a uma confirmada há 1 hora."""
    import data.radar_quedas as radar
    agora = datetime.now(timezone.utc)
    fresca = (agora - timedelta(hours=1)).isoformat()
    velha = (agora - timedelta(hours=radar.IDADE_FRESCA_HORAS + 1)).isoformat()
    linhas = [
        {"casa": "Safra Corretora", "ticker": "PETR4", "verificado_em": fresca},
        {"casa": "Genial Analisa", "ticker": "ITUB4", "verificado_em": velha},
    ]
    with patch.object(radar, "listar_carteiras", return_value=linhas):
        resumo = resumo_fontes_vigentes()
    assert resumo["Safra Corretora"]["desatualizada"] is False
    assert resumo["Genial Analisa"]["desatualizada"] is True


def test_resumo_fontes_vigentes_none_quando_supabase_indisponivel():
    import data.radar_quedas as radar
    with patch.object(radar, "listar_carteiras", return_value=None):
        assert resumo_fontes_vigentes() is None


def test_monitoramento_sem_queda_elegivel_e_execucao_valida():
    """Nenhuma ação cruzou o limiar de -4% - execução continua válida
    (coleta_ok=True), só sem alertas novos."""
    import data.radar_quedas as radar
    item = {"ticker": "PETR4", "casa": "Safra Corretora", "carteira": "Top 10 Ações"}
    cotacao_sem_queda = {"preco": 99.0, "fechamento_anterior": 100.0, "cotacao_em": "2026-10-16T10:00:00-03:00"}
    with patch.object(radar, "coletar_carteiras_genial", return_value=None), \
         patch.object(radar, "coletar_carteiras_safra", return_value=[item]), \
         patch.object(radar, "salvar_carteiras", return_value=(True, None)), \
         patch.object(radar, "listar_carteiras", return_value=[item]), \
         patch.object(radar, "obter_cotacao", return_value=cotacao_sem_queda), \
         patch.object(radar, "registrar_alerta") as registrar:
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is True
    assert resultado["alertas_novos"] == []
    assert resultado["total_tickers"] == 1
    registrar.assert_not_called()


def test_monitoramento_todas_cotacoes_falham_fica_visivel_no_erro():
    """Achado real (2026-10-19): quando o provedor de cotacao (yfinance)
    falha pra TODOS os tickers monitorados - por exemplo um bloqueio só
    no IP do runner que roda o job, diferente do IP onde o app serve a
    UI -, a execucao antes reportava coleta_ok=True e erro=None, igual a
    um dia real sem nenhuma queda >4%. As duas situacoes agora precisam
    ficar distinguiveis em `resultado` (ver jobs/radar_quedas.py e
    data/saude_dados.py, que propagam isto pro painel SAUDE DOS DADOS)."""
    import data.radar_quedas as radar
    item = {"ticker": "PETR4", "casa": "Safra Corretora", "carteira": "Top 10 Ações"}
    with patch.object(radar, "coletar_carteiras_genial", return_value=None), \
         patch.object(radar, "coletar_carteiras_safra", return_value=[item]), \
         patch.object(radar, "salvar_carteiras", return_value=(True, None)), \
         patch.object(radar, "listar_carteiras", return_value=[item]), \
         patch.object(radar, "obter_cotacao", return_value={"erro": "indisponível"}):
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is True
    assert resultado["cotacoes_falhas"] == 1
    assert resultado["total_tickers"] == 1
    assert resultado["erro"] and "cotação indisponível" in resultado["erro"].lower()
    assert "1/1" in resultado["erro"]


def test_monitoramento_cotacao_falha_parcial_nao_conta_ticker_ok():
    """2 tickers monitorados, só 1 com falha de cotação - cotacoes_falhas
    reflete exatamente 1, nao os 2."""
    import data.radar_quedas as radar
    itens = [
        {"ticker": "PETR4", "casa": "Safra Corretora", "carteira": "Top 10 Ações"},
        {"ticker": "VALE3", "casa": "Safra Corretora", "carteira": "Top 10 Ações"},
    ]
    respostas = {
        "PETR4": {"erro": "indisponível"},
        "VALE3": {"preco": 99.0, "fechamento_anterior": 100.0, "cotacao_em": "2026-10-19T10:00:00-03:00"},
    }
    with patch.object(radar, "coletar_carteiras_genial", return_value=None), \
         patch.object(radar, "coletar_carteiras_safra", return_value=itens), \
         patch.object(radar, "salvar_carteiras", return_value=(True, None)), \
         patch.object(radar, "listar_carteiras", return_value=itens), \
         patch.object(radar, "obter_cotacao", side_effect=lambda t: respostas[t]):
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is True
    assert resultado["cotacoes_falhas"] == 1
    assert resultado["total_tickers"] == 2
    assert "1/2" in resultado["erro"]


def test_monitoramento_sem_falha_de_cotacao_nao_gera_erro_espurio():
    """Execucao totalmente saudavel (todas as fontes OK, todas as
    cotacoes OK) continua sem `erro` - a mensagem nova nao aparece por
    acaso quando nada deu errado."""
    import data.radar_quedas as radar
    item = {"ticker": "PETR4", "casa": "Safra Corretora", "carteira": "Top 10 Ações"}
    cotacao_ok = {"preco": 99.0, "fechamento_anterior": 100.0, "cotacao_em": "2026-10-19T10:00:00-03:00"}
    with patch.object(radar, "coletar_carteiras_genial", return_value=[item]), \
         patch.object(radar, "coletar_carteiras_safra", return_value=[item]), \
         patch.object(radar, "salvar_carteiras", return_value=(True, None)), \
         patch.object(radar, "listar_carteiras", return_value=[item]), \
         patch.object(radar, "obter_cotacao", return_value=cotacao_ok):
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is True
    assert resultado["cotacoes_falhas"] == 0
    assert resultado["erro"] is None


# ---- revisao 2026-10-18 -------------------------------------------------

def test_pregao_do_alerta_vem_da_cotacao_nao_do_relogio():
    """Num feriado em dia util o Yahoo devolve a cotacao do ultimo pregao
    real - o alerta precisa carregar ESSA data (chave de idempotencia
    ticker+pregao), nao a data de hoje."""
    from datetime import date
    agora = datetime(2026, 11, 20, 14, 0, tzinfo=timezone.utc)  # feriado (Consciencia Negra)
    recs = [{"ticker": "PETR4", "casa": "Safra Corretora", "carteira": "Top 10", "empresa": "Petrobras"}]
    cot = {"preco": 36.0, "fechamento_anterior": 38.0, "erro": None, "pregao": date(2026, 11, 19)}
    alerta = avaliar_ticker("PETR4", cot, recs, agora=agora)
    assert alerta["pregao"] == "2026-11-19"


def test_pregao_cai_pro_relogio_quando_provedor_nao_informa():
    agora = datetime(2026, 10, 16, 14, 0, tzinfo=timezone.utc)
    recs = [{"ticker": "PETR4", "casa": "Safra Corretora", "carteira": "Top 10"}]
    alerta = avaliar_ticker("PETR4", {"preco": 36.0, "fechamento_anterior": 38.0, "erro": None}, recs, agora=agora)
    assert alerta["pregao"] == "2026-10-16"


def test_processar_monitoramento_usa_data_do_ultimo_pregao_do_provedor():
    from datetime import date
    import data.radar_quedas as radar
    recs = [{"ticker": "PETR4", "casa": "Safra Corretora", "carteira": "Top 10", "empresa": "Petrobras",
             "fonte_url": "https://www.safra.com.br/x"}]
    registrados = []
    with patch.object(radar, "coletar_carteiras_genial", return_value=None), \
         patch.object(radar, "coletar_carteiras_safra", return_value=recs), \
         patch.object(radar, "salvar_carteiras", return_value=(True, None)), \
         patch.object(radar, "listar_carteiras", return_value=recs), \
         patch.object(radar, "obter_cotacao", return_value={"preco": 36.0, "fechamento_anterior": 38.0, "erro": None}), \
         patch.object(radar, "obter_data_ultimo_pregao", return_value=date(2026, 11, 19)), \
         patch.object(radar, "registrar_alerta", side_effect=lambda a: (registrados.append(a), (True, 1))[1]):
        resultado = radar.processar_monitoramento()
    assert resultado["coleta_ok"] is True
    assert registrados and registrados[0]["pregao"] == "2026-11-19"


def test_linhas_monitorados_consolida_ordena_e_classifica():
    import data.radar_quedas as radar
    recs = [
        {"ticker": "PETR4", "casa": "Safra Corretora", "carteira": "Top 10", "empresa": "Petrobras"},
        {"ticker": "PETR4", "casa": "Genial Analisa", "carteira": "Dividendos", "empresa": ""},
        {"ticker": "VALE3", "casa": "Safra Corretora", "carteira": "Top 10", "empresa": "Vale"},
        {"ticker": "BBAS3", "casa": "Safra Corretora", "carteira": "Top 10", "empresa": "BB"},
        {"ticker": "ITUB4", "casa": "Safra Corretora", "carteira": "Top 10", "empresa": "Itau"},
    ]
    cot = {
        "PETR4": {"preco": 36.0, "fechamento_anterior": 38.0, "erro": None},   # -5,26% -> ALERTA
        "VALE3": {"preco": 57.6, "fechamento_anterior": 60.0, "erro": None},   # -4,00% exato -> nao alerta
        "BBAS3": {"preco": 10.5, "fechamento_anterior": 10.0, "erro": None},   # +5% -> NORMAL
        "ITUB4": {"erro": "timeout"},
    }
    linhas = radar.linhas_monitorados(recs, cot)
    assert [l["ticker"] for l in linhas] == ["PETR4", "VALE3", "BBAS3", "ITUB4"]
    petr = linhas[0]
    assert petr["estado"] == "ALERTA" and petr["casas"] == ["Genial Analisa", "Safra Corretora"]
    assert petr["empresa"] == "Petrobras"
    assert linhas[1]["estado"] == "ATENCAO"  # -4,00% exato: atencao, nunca alerta
    assert linhas[2]["estado"] == "NORMAL"
    assert linhas[3]["estado"] == "SEM_COTACAO" and linhas[3]["variacao_pct"] is None


def test_alertas_periodo_filtra_no_banco_pela_data_do_pregao():
    import data.radar_quedas as radar
    cliente = MagicMock()
    consulta = cliente.table.return_value.select.return_value
    consulta.gte.return_value.order.return_value.order.return_value.limit.return_value.execute.return_value.data = [{"id": 1}]
    with patch.object(radar, "obter_cliente", return_value=cliente):
        radar.alertas_periodo.clear()
        resultado = radar.alertas_periodo(7)
    assert resultado == [{"id": 1}]
    campo, valor = consulta.gte.call_args[0]
    assert campo == "pregao"
    esperado = (datetime.now(radar.TZ_SP).date() - timedelta(days=6)).isoformat()
    assert valor == esperado
