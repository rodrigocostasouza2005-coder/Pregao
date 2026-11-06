# -*- coding: utf-8 -*-
"""Persistência do Coordenador Central (data/coordenador_central/
persistencia.py) - Supabase indisponível nunca lança (None/False
distintos de vazio), histórico grava início E fim, métricas de
especialistas calculadas em Python sobre dados mockados. Nenhuma
chamada de rede real - cliente Supabase 100% fake."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.coordenador_central import persistencia


class _Resposta:
    def __init__(self, data):
        self.data = data


class _TabelaFake:
    def __init__(self, cliente, nome):
        self.cliente = cliente
        self.nome = nome
        self._op = None
        self._payload = None
        self._filtros = []
        self._order = None
        self._limit = None

    def insert(self, payload):
        self._op, self._payload = "insert", dict(payload)
        return self

    def update(self, payload):
        self._op, self._payload = "update", dict(payload)
        return self

    def select(self, *_args, **_kwargs):
        self._op = self._op or "select"
        return self

    def eq(self, campo, valor):
        self._filtros.append((campo, valor))
        return self

    def order(self, campo, desc=False):
        self._order = (campo, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        linhas = self.cliente.tabelas.setdefault(self.nome, {})
        if self._op == "insert":
            novo_id = self._payload.get("id") or (max([l.get("_seq", 0) for l in linhas.values()], default=0) + 1)
            linha = {**self._payload, "id": self._payload.get("id", novo_id), "_seq": len(linhas) + 1}
            linhas[linha["id"]] = linha
            return _Resposta([linha])
        if self._op == "update":
            atualizadas = []
            for linha in linhas.values():
                if all(linha.get(c) == v for c, v in self._filtros):
                    linha.update(self._payload)
                    atualizadas.append(linha)
            return _Resposta(atualizadas)
        if self._op == "select":
            resultado = [l for l in linhas.values() if all(l.get(c) == v for c, v in self._filtros)]
            if self._order:
                campo, desc = self._order
                resultado = sorted(resultado, key=lambda l: l.get(campo) or "", reverse=desc)
            if self._limit is not None:
                resultado = resultado[: self._limit]
            return _Resposta(resultado)
        return _Resposta([])


class _ClienteFake:
    def __init__(self):
        self.tabelas = {}

    def table(self, nome):
        return _TabelaFake(self, nome)


def _patched(cliente):
    return patch.object(persistencia, "obter_cliente", return_value=cliente)


# ============================================================
# Cliente fake com UPDATE que pode falhar de propósito (retry/fallback
# de concluir_analise, incidente real 2026-11-05 - ver persistencia.py)
# ============================================================

class _TabelaComFalha(_TabelaFake):
    def execute(self):
        if self._op == "update":
            self.cliente.chamadas_update.append(dict(self._payload))
            if self.cliente.falhar(self._payload):
                raise RuntimeError("falha simulada de rede/Supabase no UPDATE")
        return super().execute()


class _ClienteComFalha(_ClienteFake):
    """`falhar(payload)` decide, por chamada de UPDATE, se ela deve
    lançar - nunca toca rede real, só injeta a falha no fake local."""

    def __init__(self, falhar):
        super().__init__()
        self.chamadas_update = []
        self._falhar = falhar

    def table(self, nome):
        return _TabelaComFalha(self, nome)

    def falhar(self, payload):
        return self._falhar(payload)


# ============================================================
# Supabase indisponível - nunca lança, None/False distinto de vazio
# ============================================================

def test_supabase_indisponivel_iniciar_analise_ainda_devolve_id():
    with _patched(None):
        analise_id = persistencia.iniciar_analise("Analisar X", "analise_ticker", "X")
    assert isinstance(analise_id, str) and analise_id


def test_supabase_indisponivel_concluir_analise_devolve_false():
    with _patched(None):
        assert persistencia.concluir_analise("id-x", "CONCLUIDA", {}) is False


def test_supabase_indisponivel_registrar_execucao_devolve_false():
    with _patched(None):
        assert persistencia.registrar_execucao_especialista("id-x", "comparador", {"disponivel": True}) is False


def test_supabase_indisponivel_listar_analises_devolve_none():
    with _patched(None):
        assert persistencia.listar_analises_recentes() is None


def test_supabase_indisponivel_obter_analise_devolve_none():
    with _patched(None):
        assert persistencia.obter_analise("id-x") is None


def test_supabase_indisponivel_metricas_devolve_dict_vazio():
    with _patched(None):
        assert persistencia.metricas_especialistas() == {}


# ============================================================
# Histórico: grava início E fim (mesmo se o meio falhar)
# ============================================================

def test_iniciar_e_concluir_analise_grava_as_duas_pontas():
    cliente = _ClienteFake()
    with _patched(cliente):
        analise_id = persistencia.iniciar_analise("Analisar PETR4", "analise_ticker", "PETR4")
        linha = cliente.tabelas["coordenador_analises"][analise_id]
        assert linha["status"] == "EM_ANDAMENTO"
        assert linha.get("concluido_em") is None

        persistencia.concluir_analise(analise_id, "CONCLUIDA", {"resumo_executivo": "ok"})
        linha = cliente.tabelas["coordenador_analises"][analise_id]
        assert linha["status"] == "CONCLUIDA"
        assert linha["resultado"] == {"resumo_executivo": "ok"}


def test_rastro_de_inicio_sobrevive_mesmo_se_nunca_concluir():
    """Se o processo cair no meio (nunca chama concluir_analise), a
    linha EM_ANDAMENTO ainda existe - rastro de que a análise começou."""
    cliente = _ClienteFake()
    with _patched(cliente):
        analise_id = persistencia.iniciar_analise("Analisar X", "analise_ticker", "X")
    assert cliente.tabelas["coordenador_analises"][analise_id]["status"] == "EM_ANDAMENTO"


def test_listar_analises_recentes_ordena_por_iniciado_em_desc():
    cliente = _ClienteFake()
    with _patched(cliente):
        persistencia.iniciar_analise("Primeira", "analise_ticker", "A")
        cliente.tabelas["coordenador_analises"][list(cliente.tabelas["coordenador_analises"].keys())[0]]["iniciado_em"] = "2026-10-01T00:00:00Z"
        persistencia.iniciar_analise("Segunda", "analise_ticker", "B")
        lista = persistencia.listar_analises_recentes()
    assert lista[0]["solicitacao"] == "Segunda"


# ============================================================
# listar_analises_por_ticker: filtra por `ticker` usando o índice
# idx_coordenador_analises_ticker (sql/coordenador_central.sql) - antes
# desta revisão nenhuma função acionava esse índice.
# ============================================================

def test_supabase_indisponivel_listar_por_ticker_devolve_none():
    with _patched(None):
        assert persistencia.listar_analises_por_ticker("PETR4") is None


def test_listar_por_ticker_devolve_so_analises_daquele_ticker_ordenadas_por_data_desc():
    cliente = _ClienteFake()
    with _patched(cliente):
        id_antiga = persistencia.iniciar_analise("Primeira PETR4", "analise_ticker", "PETR4")
        cliente.tabelas["coordenador_analises"][id_antiga]["iniciado_em"] = "2026-10-01T00:00:00Z"
        persistencia.iniciar_analise("Outro ticker", "analise_ticker", "VALE3")
        id_recente = persistencia.iniciar_analise("Segunda PETR4", "analise_ticker", "PETR4")
        cliente.tabelas["coordenador_analises"][id_recente]["iniciado_em"] = "2026-11-01T00:00:00Z"

        lista = persistencia.listar_analises_por_ticker("PETR4")

    assert len(lista) == 2
    assert all(linha["ticker"] == "PETR4" for linha in lista)
    assert lista[0]["solicitacao"] == "Segunda PETR4"
    assert lista[1]["solicitacao"] == "Primeira PETR4"


def test_listar_por_ticker_sem_nenhuma_analise_devolve_lista_vazia():
    cliente = _ClienteFake()
    with _patched(cliente):
        persistencia.iniciar_analise("Analisar VALE3", "analise_ticker", "VALE3")
        lista = persistencia.listar_analises_por_ticker("PETR4")
    assert lista == []


def test_obter_analise_encontra_por_id():
    cliente = _ClienteFake()
    with _patched(cliente):
        analise_id = persistencia.iniciar_analise("Analisar X", "analise_ticker", "X")
        encontrada = persistencia.obter_analise(analise_id)
    assert encontrada["id"] == analise_id


# ============================================================
# Métricas de especialistas
# ============================================================

def test_metricas_especialistas_calcula_taxa_de_sucesso_e_tempo_medio():
    cliente = _ClienteFake()
    with _patched(cliente):
        for disponivel, duracao in [(True, 100), (True, 200), (False, None)]:
            persistencia.registrar_execucao_especialista("analise-1", "comparador", {
                "disponivel": disponivel, "duracao_ms": duracao, "erro_tecnico": None,
            })
        metricas = persistencia.metricas_especialistas()
    assert metricas["comparador"]["total_execucoes"] == 3
    assert metricas["comparador"]["sucessos"] == 2
    assert metricas["comparador"]["tempo_medio_ms"] == 150.0


def test_metricas_especialistas_taxa_recente_distinta_da_taxa_historica():
    """Falha antiga isolada seguida de sucessos recentes: taxa histórica
    cai, mas taxa_sucesso_recente_pct reflete só as últimas execuções."""
    cliente = _ClienteFake()
    with _patched(cliente):
        datas = ["2026-10-20T00:00:00Z", "2026-10-21T00:00:00Z", "2026-10-22T00:00:00Z", "2026-10-23T00:00:00Z"]
        disponibilidades = [False, True, True, True]
        for data_iso, disponivel in zip(datas, disponibilidades):
            cliente.table("coordenador_especialistas_execucoes").insert({
                "analise_id": "a", "especialista_id": "noticias", "disponivel": disponivel,
                "duracao_ms": 50, "erro": None, "executado_em": data_iso,
            }).execute()
        metricas = persistencia.metricas_especialistas()
    assert metricas["noticias"]["taxa_sucesso_pct"] == 75.0
    assert metricas["noticias"]["taxa_sucesso_recente_pct"] == 75.0  # só 4 execuções, todas contam na janela de N=10


def test_metricas_especialistas_expoe_erro_tecnico_da_ultima_execucao():
    """Bug 3 (auditoria 2026-11-05): a coluna `erro` de cada execução era
    lida por metricas_especialistas() mas descartada na agregação -
    nenhuma tela mostrava o erro técnico de uma execução específica."""
    cliente = _ClienteFake()
    with _patched(cliente):
        persistencia.registrar_execucao_especialista("a", "comparador", {
            "disponivel": True, "duracao_ms": 100, "erro_tecnico": None,
        })
        persistencia.registrar_execucao_especialista("b", "comparador", {
            "disponivel": False, "duracao_ms": None, "erro_tecnico": "TimeoutError: x",
        })
        linhas = list(cliente.tabelas["coordenador_especialistas_execucoes"].values())
        linhas[0]["executado_em"] = "2026-11-01T00:00:00Z"
        linhas[1]["executado_em"] = "2026-11-02T00:00:00Z"  # mais recente = a que falhou
        metricas = persistencia.metricas_especialistas()
    assert metricas["comparador"]["ultimo_erro_tecnico"] == "TimeoutError: x"


def test_metricas_especialistas_ultimo_erro_e_none_quando_ultima_execucao_teve_sucesso():
    cliente = _ClienteFake()
    with _patched(cliente):
        persistencia.registrar_execucao_especialista("a", "noticias", {
            "disponivel": False, "duracao_ms": None, "erro_tecnico": "ConnectionError: y",
        })
        persistencia.registrar_execucao_especialista("b", "noticias", {
            "disponivel": True, "duracao_ms": 50, "erro_tecnico": None,
        })
        linhas = list(cliente.tabelas["coordenador_especialistas_execucoes"].values())
        linhas[0]["executado_em"] = "2026-11-01T00:00:00Z"  # falha antiga
        linhas[1]["executado_em"] = "2026-11-02T00:00:00Z"  # sucesso mais recente
        metricas = persistencia.metricas_especialistas()
    assert metricas["noticias"]["ultimo_erro_tecnico"] is None


def test_metricas_especialistas_erro_tecnico_nunca_persistido_como_credencial():
    """registrar_execucao_especialista só persiste erro_tecnico (texto
    de diagnóstico), nunca o valor de nenhuma credencial - aqui só
    confirmamos que a coluna 'erro' reflete exatamente o que veio em
    erro_tecnico, nada mais."""
    cliente = _ClienteFake()
    with _patched(cliente):
        persistencia.registrar_execucao_especialista("a", "memoria_research", {
            "disponivel": False, "duracao_ms": 30, "erro_tecnico": "TimeoutError: x",
        })
    linha = next(iter(cliente.tabelas["coordenador_especialistas_execucoes"].values()))
    assert linha["erro"] == "TimeoutError: x"


# ============================================================
# Bug 1 (auditoria 2026-11-05, rodada real de jobs/comite_noturno.py):
# as 20 linhas da rodada ficaram EM_ANDAMENTO pra sempre porque o UPDATE
# final (concluir_analise) falhou e nada tentava de novo nem registrava
# o motivo no banco. concluir_analise agora faz retry simples e, se o
# UPDATE completo (com o jsonb `resultado`) continuar falhando, tenta um
# fallback mínimo (sem `resultado`) pra nunca deixar a linha travada de
# forma não rastreável.
# ============================================================

def test_concluir_analise_retry_recupera_de_falha_transitoria_de_rede():
    """1a tentativa do UPDATE completo falha (ex: blip de rede); o retry
    (2a tentativa) funciona - resultado completo É salvo, sem precisar
    do fallback mínimo."""
    chamadas = {"n": 0}

    def falhar(_payload):
        chamadas["n"] += 1
        return chamadas["n"] == 1  # só a 1a chamada de UPDATE falha

    cliente = _ClienteComFalha(falhar)
    with _patched(cliente):
        analise_id = persistencia.iniciar_analise("Analisar PETR4", "analise_ticker", "PETR4")
        ok = persistencia.concluir_analise(analise_id, "CONCLUIDA", {"resumo_executivo": "ok"})

    assert ok is True
    linha = cliente.tabelas["coordenador_analises"][analise_id]
    assert linha["status"] == "CONCLUIDA"
    assert linha["resultado"] == {"resumo_executivo": "ok"}
    assert len(cliente.chamadas_update) == 2  # 1 falhou, 1 (retry) funcionou


def test_concluir_analise_usa_fallback_minimo_quando_update_completo_sempre_falha():
    """UPDATE completo (com `resultado`, o payload grande) falha mesmo
    após retry - fallback mínimo (sem `resultado`) grava status PARCIAL +
    erro rastreável na coluna `erro` já existente (nenhum enum/coluna
    novo), tirando a linha de EM_ANDAMENTO. concluir_analise ainda
    devolve False: o resultado consolidado pedido não foi persistido."""
    def falhar(payload):
        return "resultado" in payload  # só o UPDATE completo tem essa chave

    cliente = _ClienteComFalha(falhar)
    with _patched(cliente):
        analise_id = persistencia.iniciar_analise("Analisar VALE3", "analise_ticker", "VALE3")
        ok = persistencia.concluir_analise(analise_id, "CONCLUIDA", {"resumo_executivo": "ok"})

    assert ok is False
    linha = cliente.tabelas["coordenador_analises"][analise_id]
    assert linha["status"] == "PARCIAL"  # nunca fica travada em EM_ANDAMENTO
    assert "FALHA_PERSISTENCIA" in linha["erro"]
    assert linha.get("resultado") is None  # resultado consolidado nunca foi salvo
    # 2 tentativas do completo (ambas falham) + 1 do fallback (sucesso de primeira).
    assert len(cliente.chamadas_update) == 3


def test_concluir_analise_fallback_preserva_status_erro_sem_rebaixar():
    """Quando o fluxo original já era ERRO (fluxos.py:_concluir_com_erro),
    o fallback mínimo nunca rebaixa pra PARCIAL - só anexa o aviso de
    falha de persistência ao erro original, na mesma coluna `erro`."""
    def falhar(payload):
        return "resultado" in payload

    cliente = _ClienteComFalha(falhar)
    with _patched(cliente):
        analise_id = persistencia.iniciar_analise("Analisar X", "analise_ticker", "X")
        ok = persistencia.concluir_analise(analise_id, "ERRO", None, erro="ValueError: algo quebrou")

    assert ok is False
    linha = cliente.tabelas["coordenador_analises"][analise_id]
    assert linha["status"] == "ERRO"
    assert "ValueError: algo quebrou" in linha["erro"]
    assert "FALHA_PERSISTENCIA" in linha["erro"]


def test_concluir_analise_serializa_date_puro_dentro_do_resultado():
    """Bug real encontrado na validação operacional com dados reais
    (2026-11-05, Parte 6/comite-validacao-3-empresas): especialistas
    como `catalisadores` (data/radar.py) devolvem datetime.date puro no
    campo "data" sempre que há evento na janela - isso chegava inteiro
    dentro de `resultado["visao_especialistas"]` e o UPDATE completo
    falhava 100% das vezes (TypeError: Object of type date is not JSON
    serializable), rebaixando CONCLUIDA pra PARCIAL mesmo com todos os
    especialistas disponíveis. _serializar_jsonb converte date/datetime
    pra string ISO antes do UPDATE; aqui confirmamos que o valor
    persistido já é string e que json.dumps do payload nunca falha."""
    import datetime as _dt
    import json

    cliente = _ClienteFake()
    resultado_com_date = {
        "visao_especialistas": {
            "catalisadores": {
                "dados": [{"ticker": "PETR4", "data": _dt.date(2026, 11, 10)}],
            },
        },
        "momento_consolidado_em": _dt.datetime(2026, 11, 5, 10, 0, tzinfo=_dt.timezone.utc),
    }
    with _patched(cliente):
        analise_id = persistencia.iniciar_analise("Analisar PETR4", "analise_ticker", "PETR4")
        ok = persistencia.concluir_analise(analise_id, "CONCLUIDA", resultado_com_date)

    assert ok is True
    linha = cliente.tabelas["coordenador_analises"][analise_id]
    assert linha["status"] == "CONCLUIDA"
    data_persistida = linha["resultado"]["visao_especialistas"]["catalisadores"]["dados"][0]["data"]
    assert data_persistida == "2026-11-10"
    assert isinstance(data_persistida, str)
    json.dumps(linha["resultado"])  # nunca lança - é o que o cliente HTTP real faria


def test_concluir_analise_quando_tudo_falha_linha_fica_em_andamento_mas_tentativas_sao_registradas():
    """Se até o fallback mínimo falhar (indisponibilidade real do
    Supabase), a linha fica EM_ANDAMENTO (nenhum UPDATE de fato foi
    aplicado) - mas a função ainda tentou retry + fallback antes de
    desistir (nunca lança, sempre devolve False)."""
    cliente = _ClienteComFalha(lambda _payload: True)  # todo UPDATE falha
    with _patched(cliente):
        analise_id = persistencia.iniciar_analise("Analisar Y", "analise_ticker", "Y")
        ok = persistencia.concluir_analise(analise_id, "CONCLUIDA", {"x": 1})

    assert ok is False
    linha = cliente.tabelas["coordenador_analises"][analise_id]
    assert linha["status"] == "EM_ANDAMENTO"
    assert len(cliente.chamadas_update) == 4  # 2 (completo) + 2 (fallback), todas falharam
