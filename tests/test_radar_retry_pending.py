from jobs import radar_quedas


class _Resposta:
    def __init__(self, data=None):
        self.data = data or []


class _Query:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.update_payload = None
        self.filters = []

    def select(self, *_args):
        return self

    def in_(self, coluna, valores):
        self.filters.append((coluna, valores))
        return self

    def gte(self, coluna, valor):
        self.filters.append((coluna, ">=", valor))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args):
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def eq(self, coluna, valor):
        self.filters.append((coluna, valor))
        return self

    def execute(self):
        if self.update_payload is not None:
            return _Resposta([{"id": 7}])
        return _Resposta(self.rows)


class _Cliente:
    def __init__(self, rows=None):
        self.query = _Query(rows)

    def table(self, _nome):
        return self.query


def test_recupera_alertas_pendentes_e_falhos():
    linhas = [{"id": 7, "ticker": "PETR4", "status": "FALHA_ENVIO"}]
    cliente = _Cliente(linhas)

    resultado = radar_quedas._alertas_pendentes(cliente)

    assert resultado == linhas
    assert ("status", ["PENDENTE_ENVIO", "FALHA_ENVIO"]) in cliente.query.filters


def test_alerta_com_envio_bem_sucedido_atualiza_status(monkeypatch):
    cliente = _Cliente()
    monkeypatch.setattr(
        radar_quedas,
        "enviar_email",
        lambda *_args, **_kwargs: {"ok": True, "erro": None},
    )
    alerta = {
        "id": 7,
        "ticker": "PETR4",
        "variacao_pct": -4.5,
        "preco_atual": 10.0,
        "fechamento_anterior": 10.5,
        "cotacao_em": "2026-10-14T15:00:00+00:00",
        "tipo_cotacao": "atrasada",
        "casas": ["Genial Analisa"],
        "carteiras": ["Ações"],
        "fontes": ["https://example.com"],
    }

    assert radar_quedas._enviar_alerta(cliente, alerta) is True
    assert cliente.query.update_payload["status"] == "ENVIADO"
    assert cliente.query.update_payload["email_enviado_em"]
    assert cliente.query.update_payload["erro_envio"] is None


def test_falha_de_email_permanece_reprocessavel(monkeypatch):
    cliente = _Cliente()
    monkeypatch.setattr(
        radar_quedas,
        "enviar_email",
        lambda *_args, **_kwargs: {"ok": False, "erro": "SMTP indisponível"},
    )
    alerta = {
        "id": 8,
        "ticker": "VALE3",
        "variacao_pct": -5.1,
        "preco_atual": 60.0,
        "fechamento_anterior": 63.0,
        "casas": [],
        "carteiras": [],
        "fontes": [],
    }

    assert radar_quedas._enviar_alerta(cliente, alerta) is False
    assert cliente.query.update_payload["status"] == "FALHA_ENVIO"
    assert cliente.query.update_payload["erro_envio"] == "SMTP indisponível"
    assert cliente.query.update_payload["email_enviado_em"] is None


def test_executar_registra_tentativa_no_painel_saude(monkeypatch):
    """Regressao 2026-10-15: igual ao Morning Call - radar_alertas_queda
    so' registra ALERTAS, nao a tentativa de execucao; uma rodada sem
    nenhuma queda >4% (sucesso legitimo) nao deixava rastro nenhum no
    painel SAUDE DOS DADOS."""
    chamadas = []
    monkeypatch.setattr(
        radar_quedas,
        "processar_monitoramento",
        lambda: {"coleta_ok": True, "alertas_novos": [], "erro": ""},
    )
    monkeypatch.setattr(radar_quedas, "obter_cliente", lambda: _Cliente([]))
    monkeypatch.setattr(radar_quedas, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    codigo = radar_quedas.executar()

    assert codigo == 0
    assert len(chamadas) == 1
    args, kwargs = chamadas[0]
    assert args[0] == "RADAR DE QUEDAS"
    assert kwargs["execucao_ok"] is True
    assert kwargs["registros_novos"] == 0


def test_executar_registra_falha_quando_coleta_falha(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        radar_quedas,
        "processar_monitoramento",
        lambda: {"coleta_ok": False, "alertas_novos": [], "erro": "zero recomendações coletadas"},
    )
    monkeypatch.setattr(radar_quedas, "obter_cliente", lambda: _Cliente([]))
    monkeypatch.setattr(radar_quedas, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    codigo = radar_quedas.executar()

    assert codigo == 1
    assert chamadas[0][1]["execucao_ok"] is False
    assert chamadas[0][1]["erro"] == "zero recomendações coletadas"


def test_executar_chama_self_test_de_persistencia_antes_de_tudo(monkeypatch):
    """Regressao 2026-10-15 (auditoria do secret errado em producao):
    executar() precisa rodar o self-test de escrita+leitura ANTES de
    tentar processar_monitoramento/recuperar pendentes - sem isso, uma
    credencial sem privilegio so' aparecia como N excecoes "42501"
    espalhadas, 1 por tabela, sem 1 diagnostico unico na raiz."""
    chamadas_diagnostico = []
    monkeypatch.setattr(
        radar_quedas, "diagnosticar_persistencia",
        lambda: chamadas_diagnostico.append(1) or {"ok": False, "etapa": "ESCRITA", "detalhe": "x"},
    )
    monkeypatch.setattr(radar_quedas, "processar_monitoramento", lambda: {"coleta_ok": False, "alertas_novos": [], "erro": "x"})
    monkeypatch.setattr(radar_quedas, "obter_cliente", lambda: None)

    radar_quedas.executar()

    assert len(chamadas_diagnostico) == 1


def test_so_reenvia_pendentes_de_pregao_recente():
    """Regressão: sem janela, alerta antigo nunca enviado (EMAIL_TO vazio em
    21/10/2026) seria reenviado dias depois como se a queda fosse de hoje, e
    200+ pendentes antigos impediam os novos de entrar no lote."""
    from datetime import date

    cliente = _Cliente([])
    radar_quedas._alertas_pendentes(cliente, hoje=date(2026, 10, 22))
    assert ("pregao", ">=", "2026-10-19") in cliente.query.filters


def test_assunto_do_alerta_traz_a_data_do_pregao(monkeypatch):
    enviados = []
    monkeypatch.setattr(radar_quedas, "enviar_email",
                        lambda assunto, texto: enviados.append(assunto) or {"ok": True, "erro": None})
    alerta = {"id": 7, "ticker": "WEGE3", "pregao": "2026-10-21", "variacao_pct": -4.3, "preco_atual": 40.0,
              "fechamento_anterior": 41.8}
    radar_quedas._enviar_alerta(_Cliente(), alerta)
    assert enviados == ["[PREGÃO] Queda >4% — WEGE3 (pregão 21/10)"]


def test_corpo_do_alerta_traz_a_data_do_pregao_e_aviso_nao_recomendacao():
    texto = radar_quedas._texto_alerta({"ticker": "WEGE3", "pregao": "2026-10-21", "variacao_pct": -4.3,
                                        "preco_atual": 40.0, "fechamento_anterior": 41.8})
    assert "Pregão: 21/10/2026" in texto
    assert "não constitui recomendação" in texto
