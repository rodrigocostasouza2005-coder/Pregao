import pytest

from jobs import radar_quedas


@pytest.fixture(autouse=True)
def _sem_aquecimento_cenario_global_real(monkeypatch):
    """executar() aquece "MACRO (Cenário Global)" incondicionalmente
    (achado real, auditoria SAÚDE DOS DADOS 2026-10-26: sem isto, essa
    fonte só é chamada por quem abre a aba MACRO/Visão Geral, nunca por
    este job - ver jobs/radar_quedas.py) - nenhum teste deste módulo deve
    bater rede real do yfinance por causa disso."""
    monkeypatch.setattr(radar_quedas, "obter_cenario_global", lambda: [])


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

    assert radar_quedas._enviar_alerta(cliente, alerta, ["assinante@exemplo.com"]) == "ENVIADO"
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

    assert radar_quedas._enviar_alerta(cliente, alerta, ["assinante@exemplo.com"]) == "FALHA_ENVIO"
    assert cliente.query.update_payload["status"] == "FALHA_ENVIO"
    assert cliente.query.update_payload["erro_envio"] == "SMTP indisponível"
    assert cliente.query.update_payload["email_enviado_em"] is None


def test_sem_destinatario_autorizado_nao_envia_nem_atualiza_status(monkeypatch):
    """Caso normal "ninguém autorizou ainda" (missão "Radar/Morning
    Call: consentimento") - nunca é tratado como falha nem reenvia pra
    um EMAIL_TO fixo."""
    cliente = _Cliente()
    chamadas_envio = []
    monkeypatch.setattr(
        radar_quedas, "enviar_email",
        lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None},
    )
    alerta = {"id": 9, "ticker": "ITUB4", "variacao_pct": -4.2, "preco_atual": 30.0, "fechamento_anterior": 31.3}

    assert radar_quedas._enviar_alerta(cliente, alerta, []) == "SEM_DESTINATARIO"
    assert chamadas_envio == []
    assert cliente.query.update_payload is None


def test_sem_destinatario_autorizado_none_tambem_nao_envia():
    """destinatarios=None (Supabase indisponível pra consultar opt-in)
    tem o mesmo efeito prático de [] em _enviar_alerta: nunca envia sem
    saber quem autorizou - a distinção None/[] importa só pra
    executar() decidir o código de saída (ver testes de executar())."""
    cliente = _Cliente()
    alerta = {"id": 10, "ticker": "BBDC4", "variacao_pct": -4.8, "preco_atual": 20.0, "fechamento_anterior": 21.0}

    assert radar_quedas._enviar_alerta(cliente, alerta, None) == "SEM_DESTINATARIO"
    assert cliente.query.update_payload is None


def test_multiplos_destinatarios_recebem_e_falha_parcial_nao_e_falha_total(monkeypatch):
    """2 assinantes, 1 falha: status final é ENVIADO (quem já recebeu
    não pode ser reenviado - duplicaria), e os 2 e-mails são
    efetivamente disparados (1 por destinatário)."""
    cliente = _Cliente()
    chamadas = []

    def _fake_enviar(_assunto, _texto, destinatario=None, **_k):
        chamadas.append(destinatario)
        if destinatario == "falha@exemplo.com":
            return {"ok": False, "erro": "SMTP indisponível"}
        return {"ok": True, "erro": None}

    monkeypatch.setattr(radar_quedas, "enviar_email", _fake_enviar)
    alerta = {"id": 11, "ticker": "WEGE3", "variacao_pct": -4.1, "preco_atual": 40.0, "fechamento_anterior": 41.7}

    desfecho = radar_quedas._enviar_alerta(cliente, alerta, ["ok@exemplo.com", "falha@exemplo.com"])

    assert desfecho == "ENVIADO"
    assert sorted(chamadas) == ["falha@exemplo.com", "ok@exemplo.com"]
    assert cliente.query.update_payload["status"] == "ENVIADO"
    assert "1/2" in cliente.query.update_payload["erro_envio"]


def test_hash_destinatario_nunca_expoe_o_email_e_e_estavel():
    h1 = radar_quedas._hash_destinatario("Assinante@Exemplo.com")
    h2 = radar_quedas._hash_destinatario("assinante@exemplo.com")
    assert h1 == h2
    assert "assinante" not in h1
    assert len(h1) == 10


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
    monkeypatch.setattr(radar_quedas, "listar_assinantes_radar_quedas", lambda cliente: [])
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
    monkeypatch.setattr(radar_quedas, "listar_assinantes_radar_quedas", lambda cliente: [])
    monkeypatch.setattr(radar_quedas, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    codigo = radar_quedas.executar()

    assert codigo == 1
    assert chamadas[0][1]["execucao_ok"] is False
    assert chamadas[0][1]["erro"] == "zero recomendações coletadas"


def test_executar_com_destinatarios_indisponiveis_registra_falha_sem_enviar(monkeypatch):
    """destinatarios=None (Supabase indisponível pra consultar opt-in) é
    uma falha de execução visível (mesmo espírito de
    jobs/morning_call.py), mesmo com coleta_ok=True - nunca mascara a
    falha de infra como sucesso silencioso."""
    chamadas = []
    chamadas_envio = []
    monkeypatch.setattr(
        radar_quedas, "processar_monitoramento",
        lambda: {"coleta_ok": True, "alertas_novos": [{"id": 99, "ticker": "ABCD3"}], "erro": ""},
    )
    monkeypatch.setattr(radar_quedas, "obter_cliente", lambda: _Cliente([]))
    monkeypatch.setattr(radar_quedas, "listar_assinantes_radar_quedas", lambda cliente: None)
    monkeypatch.setattr(radar_quedas, "_alertas_pendentes", lambda cliente, hoje=None: [{"id": 99, "ticker": "ABCD3"}])
    monkeypatch.setattr(radar_quedas, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)))
    monkeypatch.setattr(radar_quedas, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    codigo = radar_quedas.executar()

    assert codigo == 1
    assert chamadas_envio == []  # nunca tenta enviar sem saber quem autorizou, mesmo com pendente real
    assert chamadas[0][1]["execucao_ok"] is False
    assert "destinatários opt-in" in chamadas[0][1]["erro"]


def test_executar_sem_destinatarios_autorizados_finaliza_sem_falha(monkeypatch):
    """Caso normal "ninguém autorizou ainda" (destinatarios=[]) - nunca
    deve contar como falha mesmo havendo alertas pendentes de verdade."""
    chamadas = []
    chamadas_envio = []
    monkeypatch.setattr(
        radar_quedas, "processar_monitoramento",
        lambda: {"coleta_ok": True, "alertas_novos": [{"id": 99, "ticker": "ABCD3"}], "erro": ""},
    )
    monkeypatch.setattr(radar_quedas, "obter_cliente", lambda: _Cliente([]))
    monkeypatch.setattr(radar_quedas, "listar_assinantes_radar_quedas", lambda cliente: [])
    monkeypatch.setattr(radar_quedas, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)))
    monkeypatch.setattr(radar_quedas, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))
    monkeypatch.setattr(radar_quedas, "_alertas_pendentes", lambda cliente, hoje=None: [{"id": 99, "ticker": "ABCD3"}])

    codigo = radar_quedas.executar()

    assert codigo == 0
    assert chamadas_envio == []
    assert chamadas[0][1]["execucao_ok"] is True
    assert chamadas[0][1]["erro"] is None


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
    monkeypatch.setattr(
        radar_quedas, "enviar_email",
        lambda assunto, texto, destinatario=None, **_k: enviados.append(assunto) or {"ok": True, "erro": None},
    )
    alerta = {"id": 7, "ticker": "WEGE3", "pregao": "2026-10-21", "variacao_pct": -4.3, "preco_atual": 40.0,
              "fechamento_anterior": 41.8}
    radar_quedas._enviar_alerta(_Cliente(), alerta, ["assinante@exemplo.com"])
    assert enviados == ["[PREGÃO] Queda >4% — WEGE3 (pregão 21/10)"]


def test_corpo_do_alerta_traz_a_data_do_pregao_e_aviso_nao_recomendacao():
    texto = radar_quedas._texto_alerta({"ticker": "WEGE3", "pregao": "2026-10-21", "variacao_pct": -4.3,
                                        "preco_atual": 40.0, "fechamento_anterior": 41.8})
    assert "Pregão: 21/10/2026" in texto
    assert "não constitui recomendação" in texto


# ---------------------------------------------------------------------
# GRANULARIDADE POR CASA (auditoria 2026-10-22): resultado["fontes"] de
# processar_monitoramento() já tinha o status de CADA casa separado, mas
# só o agregado "RADAR DE QUEDAS" chegava ao painel SAUDE DOS DADOS - uma
# falha isolada de 1 casa ficava indistinguível de "tudo OK".
# ---------------------------------------------------------------------

def test_executar_registra_tentativa_por_casa_quando_uma_falha_e_outra_ok(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        radar_quedas, "processar_monitoramento",
        lambda: {
            "coleta_ok": True, "alertas_novos": [], "erro": "Execução parcial: x",
            "fontes": {"Genial Analisa": "fonte indisponível", "Safra Corretora": "ok (12 recomendações)"},
        },
    )
    monkeypatch.setattr(radar_quedas, "obter_cliente", lambda: _Cliente([]))
    monkeypatch.setattr(radar_quedas, "listar_assinantes_radar_quedas", lambda cliente: [])
    monkeypatch.setattr(radar_quedas, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    radar_quedas.executar()

    por_nome = {args[0]: kwargs for args, kwargs in chamadas}
    assert "RADAR DE QUEDAS" in por_nome  # agregado continua existindo
    assert por_nome["Genial Analisa (carteiras)"]["execucao_ok"] is False
    assert por_nome["Genial Analisa (carteiras)"]["erro"] == "fonte indisponível"
    assert por_nome["Safra Corretora (carteiras)"]["execucao_ok"] is True
    assert por_nome["Safra Corretora (carteiras)"]["registros_novos"] == 12
    # nunca usa o nome da casa de RESEARCH (colidiria no upsert por nome)
    assert "Genial Analisa" not in por_nome
    assert "Safra Corretora" not in por_nome


def test_executar_registra_snapshot_vazio_como_parcial_nao_falha_nem_sucesso_pleno(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        radar_quedas, "processar_monitoramento",
        lambda: {
            "coleta_ok": True, "alertas_novos": [], "erro": None,
            "fontes": {"Genial Analisa": "snapshot vazio, rejeitado (carteira anterior preservada)",
                       "Safra Corretora": "ok (10 recomendações)"},
        },
    )
    monkeypatch.setattr(radar_quedas, "obter_cliente", lambda: _Cliente([]))
    monkeypatch.setattr(radar_quedas, "listar_assinantes_radar_quedas", lambda cliente: [])
    monkeypatch.setattr(radar_quedas, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    radar_quedas.executar()

    por_nome = {args[0]: kwargs for args, kwargs in chamadas}
    genial = por_nome["Genial Analisa (carteiras)"]
    assert genial["execucao_ok"] is True  # a fonte respondeu, só o conteúdo foi rejeitado
    assert genial["parcial"] is True
    assert genial["registros_novos"] == 0


def test_executar_registra_falha_de_persistencia_por_casa(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        radar_quedas, "processar_monitoramento",
        lambda: {
            "coleta_ok": True, "alertas_novos": [], "erro": None,
            "fontes": {"Safra Corretora": "falha ao persistir (carteira anterior preservada)"},
        },
    )
    monkeypatch.setattr(radar_quedas, "obter_cliente", lambda: _Cliente([]))
    monkeypatch.setattr(radar_quedas, "listar_assinantes_radar_quedas", lambda cliente: [])
    monkeypatch.setattr(radar_quedas, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    radar_quedas.executar()

    por_nome = {args[0]: kwargs for args, kwargs in chamadas}
    safra = por_nome["Safra Corretora (carteiras)"]
    assert safra["execucao_ok"] is True
    assert safra["persistencia_ok"] is False


def test_executar_aquece_cenario_global_mesmo_quando_coleta_falha(monkeypatch):
    """Regressão (auditoria SAÚDE DOS DADOS 2026-10-26): idade_maxima_horas=2
    pra "MACRO (Cenário Global)" só é sustentável se algo roda com frequência
    - este job já roda a cada 15min em dia de pregão (ver .github/workflows/
    radar-morning-call.yml), então precisa aquecer essa fonte SEMPRE, mesmo
    quando o resto da execução falha."""
    chamadas = []
    monkeypatch.setattr(radar_quedas, "obter_cenario_global", lambda: chamadas.append(1) or [])
    monkeypatch.setattr(
        radar_quedas, "processar_monitoramento",
        lambda: {"coleta_ok": False, "alertas_novos": [], "erro": "zero recomendações coletadas"},
    )
    monkeypatch.setattr(radar_quedas, "obter_cliente", lambda: _Cliente([]))
    monkeypatch.setattr(radar_quedas, "registrar_tentativa", lambda *a, **k: None)

    radar_quedas.executar()

    assert len(chamadas) == 1


def test_executar_sem_fontes_no_resultado_nunca_quebra_e_nao_gera_chamada_extra(monkeypatch):
    """Compat com o retorno antigo (sem "fontes") - não pode lançar
    excecao nem criar chamadas extras além do agregado."""
    chamadas = []
    monkeypatch.setattr(
        radar_quedas, "processar_monitoramento",
        lambda: {"coleta_ok": True, "alertas_novos": [], "erro": ""},
    )
    monkeypatch.setattr(radar_quedas, "obter_cliente", lambda: _Cliente([]))
    monkeypatch.setattr(radar_quedas, "listar_assinantes_radar_quedas", lambda cliente: [])
    monkeypatch.setattr(radar_quedas, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    radar_quedas.executar()

    assert len(chamadas) == 1
    assert chamadas[0][0][0] == "RADAR DE QUEDAS"
