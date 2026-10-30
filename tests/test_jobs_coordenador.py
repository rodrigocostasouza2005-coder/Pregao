# -*- coding: utf-8 -*-
"""jobs/coordenador.py: agenda registrar_achados_atuais() (Backoffice),
obter_sintese_mercado() (síntese executiva) e, desde 2026-10-30,
data.x_radar.executar_ciclo() (RADAR X - INTELIGÊNCIA SOCIAL) - as três
já existiam e já são testadas nos módulos próprios
(tests/test_market_researcher.py, tests/test_sintese_mercado.py,
tests/test_x_radar_*.py); este arquivo testa só a ORQUESTRAÇÃO (3a
rotina independente, registro em coordenador_execucoes, indisponível-
e-documentado não conta como falha do job)."""
from unittest.mock import patch

from jobs import coordenador as job


class _TabelaExecucoesFake:
    def __init__(self, cliente):
        self.cliente = cliente
        self._op = None
        self._payload = None
        self._filtro_id = None

    def insert(self, payload):
        self._op = "insert"
        self._payload = dict(payload)
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = dict(payload)
        return self

    def eq(self, _campo, valor):
        self._filtro_id = valor
        return self

    def execute(self):
        if self._op == "insert":
            linha = {"id": len(self.cliente.linhas) + 1, **self._payload}
            self.cliente.linhas[linha["id"]] = linha
            return _Resposta([linha])
        if self._op == "update":
            linha = self.cliente.linhas.get(self._filtro_id)
            if linha is not None:
                linha.update(self._payload)
                return _Resposta([linha])
        return _Resposta([])


class _Resposta:
    def __init__(self, data):
        self.data = data


class _ClienteFake:
    def __init__(self):
        self.linhas = {}

    def table(self, _nome):
        return _TabelaExecucoesFake(self)


_RADAR_X_SEM_CREDENCIAL = {"ok": False, "motivo": "sem credencial", "estado": "sem_credencial", "sinais_novos": 0}
_RADAR_X_OK = {"ok": True, "sinais_novos": 5, "estado": "ok", "motivo": None}


def test_executar_sem_supabase_retorna_1_sem_lancar():
    with patch.object(job, "obter_cliente", return_value=None):
        assert job.executar() == 1


def test_executar_com_sucesso_nas_tres_rotinas_retorna_0_e_registra_execucoes():
    cliente = _ClienteFake()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "registrar_achados_atuais", return_value={"ok": True, "achados_atuais": 3}), \
         patch.object(job, "obter_sintese_mercado", return_value={"ok": True, "atual": True}), \
         patch.object(job, "executar_ciclo_radar_x", return_value=_RADAR_X_OK):
        assert job.executar() == 0
    tipos = sorted(l["tipo"] for l in cliente.linhas.values())
    assert tipos == ["backoffice", "radar_x", "sintese"]
    assert all(l["status"] == "OK" for l in cliente.linhas.values())
    assert all(l.get("duracao_ms") is not None for l in cliente.linhas.values())


def test_radar_x_sem_credencial_registra_parcial_e_nao_conta_como_falha():
    """Indisponível-e-documentado (sem X_BEARER_TOKEN, caso de hoje) não
    é um erro de execução do job - mesma distinção que a síntese
    reaproveitada do cache já faz."""
    cliente = _ClienteFake()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "registrar_achados_atuais", return_value={"ok": True, "achados_atuais": 0}), \
         patch.object(job, "obter_sintese_mercado", return_value={"ok": True, "atual": True}), \
         patch.object(job, "executar_ciclo_radar_x", return_value=_RADAR_X_SEM_CREDENCIAL):
        assert job.executar() == 0
    por_tipo = {l["tipo"]: l for l in cliente.linhas.values()}
    assert por_tipo["radar_x"]["status"] == "PARCIAL"
    assert "sem_credencial" in por_tipo["radar_x"]["resumo"]


def test_falha_do_backoffice_nao_impede_as_demais_de_rodar():
    """Isolamento de falha (Fase 7 do pedido): um especialista falhar
    nunca pode impedir os demais de rodar."""
    cliente = _ClienteFake()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "registrar_achados_atuais", side_effect=RuntimeError("Supabase fora do ar")), \
         patch.object(job, "obter_sintese_mercado", return_value={"ok": True, "atual": True}), \
         patch.object(job, "executar_ciclo_radar_x", return_value=_RADAR_X_OK):
        assert job.executar() == 1  # geral falho (backoffice falhou), mas...
    por_tipo = {l["tipo"]: l for l in cliente.linhas.values()}
    assert por_tipo["backoffice"]["status"] == "ERRO"
    assert "RuntimeError" in por_tipo["backoffice"]["erro"]
    assert por_tipo["sintese"]["status"] == "OK"  # ...a síntese rodou e foi registrada normalmente
    assert por_tipo["radar_x"]["status"] == "OK"  # ...e o radar_x também


def test_falha_da_sintese_nao_impede_o_backoffice_nem_o_radar_x():
    cliente = _ClienteFake()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "registrar_achados_atuais", return_value={"ok": True, "achados_atuais": 0}), \
         patch.object(job, "obter_sintese_mercado", side_effect=RuntimeError("Groq indisponível")), \
         patch.object(job, "executar_ciclo_radar_x", return_value=_RADAR_X_OK):
        assert job.executar() == 1
    por_tipo = {l["tipo"]: l for l in cliente.linhas.values()}
    assert por_tipo["backoffice"]["status"] == "OK"
    assert por_tipo["sintese"]["status"] == "ERRO"
    assert por_tipo["radar_x"]["status"] == "OK"


def test_falha_do_radar_x_nao_impede_backoffice_nem_sintese():
    cliente = _ClienteFake()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "registrar_achados_atuais", return_value={"ok": True, "achados_atuais": 0}), \
         patch.object(job, "obter_sintese_mercado", return_value={"ok": True, "atual": True}), \
         patch.object(job, "executar_ciclo_radar_x", side_effect=RuntimeError("erro inesperado")):
        assert job.executar() == 1
    por_tipo = {l["tipo"]: l for l in cliente.linhas.values()}
    assert por_tipo["backoffice"]["status"] == "OK"
    assert por_tipo["sintese"]["status"] == "OK"
    assert por_tipo["radar_x"]["status"] == "ERRO"
    assert "RuntimeError" in por_tipo["radar_x"]["erro"]


def test_sintese_reaproveitada_do_cache_registra_parcial_nao_erro():
    """obter_sintese_mercado() pode devolver ok=True, atual=False
    (síntese ANTERIOR reaproveitada, Groq indisponível agora) - isso não
    é um erro de execução do job, é um resultado degradado válido
    (mesma distinção que data/sintese_mercado.py já faz)."""
    cliente = _ClienteFake()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "registrar_achados_atuais", return_value={"ok": True, "achados_atuais": 0}), \
         patch.object(job, "obter_sintese_mercado", return_value={"ok": True, "atual": False, "motivo_atual_indisponivel": "GROQ_API_KEY não configurada"}), \
         patch.object(job, "executar_ciclo_radar_x", return_value=_RADAR_X_OK):
        assert job.executar() == 0
    por_tipo = {l["tipo"]: l for l in cliente.linhas.values()}
    assert por_tipo["sintese"]["status"] == "PARCIAL"


def test_execucao_anterior_travada_em_andamento_nao_bloqueia_nova_rodada():
    """Retomada segura (Fase 7 do pedido): se uma execução anterior ficou
    EM_ANDAMENTO pra sempre (processo morto no meio, ex. runner do GitHub
    Actions cancelado), a próxima rodada agendada tem que rodar normalmente
    - nunca esperar/bloquear por uma linha travada, mesmo espírito de
    data/ia_cache.py:_linha_abandonada."""
    cliente = _ClienteFake()
    cliente.linhas[1] = {"id": 1, "tipo": "backoffice", "status": "EM_ANDAMENTO", "iniciado_em": "2026-10-28T10:00:00Z"}
    cliente.linhas[2] = {"id": 2, "tipo": "sintese", "status": "EM_ANDAMENTO", "iniciado_em": "2026-10-28T10:00:00Z"}
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "registrar_achados_atuais", return_value={"ok": True, "achados_atuais": 1}), \
         patch.object(job, "obter_sintese_mercado", return_value={"ok": True, "atual": True}), \
         patch.object(job, "executar_ciclo_radar_x", return_value=_RADAR_X_OK):
        assert job.executar() == 0
    # a rodada travada antiga continua intocada (auditoria, não apagamos
    # histórico) - a rodada NOVA criou outras 3 linhas (backoffice/sintese/radar_x)
    assert len(cliente.linhas) == 5
    novas = [l for l in cliente.linhas.values() if l["id"] > 2]
    assert all(l["status"] == "OK" for l in novas)


def test_motivo_de_falha_do_backoffice_sem_excecao_vira_erro_registrado():
    cliente = _ClienteFake()
    with patch.object(job, "obter_cliente", return_value=cliente), \
         patch.object(job, "registrar_achados_atuais", return_value={"ok": False, "motivo": "Supabase indisponível"}), \
         patch.object(job, "obter_sintese_mercado", return_value={"ok": False, "motivo": "síntese indisponível"}), \
         patch.object(job, "executar_ciclo_radar_x", return_value=_RADAR_X_OK):
        assert job.executar() == 1
    por_tipo = {l["tipo"]: l for l in cliente.linhas.values()}
    assert por_tipo["backoffice"]["erro"] == "Supabase indisponível"
    assert por_tipo["sintese"]["erro"] == "síntese indisponível"
