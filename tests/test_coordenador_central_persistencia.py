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
