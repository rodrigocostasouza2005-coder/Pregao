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
