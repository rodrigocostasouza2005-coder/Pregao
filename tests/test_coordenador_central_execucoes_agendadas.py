# -*- coding: utf-8 -*-
"""Leitura de coordenador_execucoes (data/coordenador_central/
execucoes_agendadas.py) - log do SCHEDULER puro via cron
(jobs/coordenador.py). Supabase indisponível nunca lança (None
distinto de []), reduz corretamente pra "1 linha por tipo, a mais
recente", e nunca propaga exceção de rede. Cliente Supabase 100% fake
- nenhuma chamada real, nenhuma escrita em log de produção."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.coordenador_central import execucoes_agendadas


class _Resposta:
    def __init__(self, data):
        self.data = data


class _TabelaFake:
    """Só leitura (select/order/limit/execute) - este módulo nunca
    escreve em coordenador_execucoes, só jobs/coordenador.py escreve."""

    def __init__(self, linhas):
        self._linhas = linhas
        self._order = None
        self._limit = None

    def select(self, *_args, **_kwargs):
        return self

    def order(self, campo, desc=False):
        self._order = (campo, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        linhas = list(self._linhas)
        if self._order:
            campo, desc = self._order
            linhas = sorted(linhas, key=lambda l: l.get(campo) or "", reverse=desc)
        if self._limit is not None:
            linhas = linhas[: self._limit]
        return _Resposta(linhas)


class _ClienteFake:
    def __init__(self, linhas):
        self._linhas = linhas

    def table(self, _nome):
        return _TabelaFake(self._linhas)


class _ClienteQuebrado:
    """Simula uma falha de rede/credencial no meio da consulta."""

    def table(self, _nome):
        raise RuntimeError("conexão com o Supabase falhou")


def _patched(cliente):
    return patch.object(execucoes_agendadas, "obter_cliente", return_value=cliente)


def test_supabase_indisponivel_devolve_none():
    with _patched(None):
        assert execucoes_agendadas.listar_ultimas_execucoes() is None


def test_tabela_sem_nenhuma_linha_devolve_lista_vazia_nao_none():
    with _patched(_ClienteFake([])):
        resultado = execucoes_agendadas.listar_ultimas_execucoes()
    assert resultado == []
    assert resultado is not None


def test_falha_na_consulta_devolve_none_sem_lancar():
    with _patched(_ClienteQuebrado()):
        assert execucoes_agendadas.listar_ultimas_execucoes() is None


def test_pega_so_a_execucao_mais_recente_de_cada_tipo():
    linhas = [
        {"id": 1, "tipo": "backoffice", "status": "ERRO", "iniciado_em": "2026-11-01T00:00:00Z",
         "erro": "falha antiga"},
        {"id": 2, "tipo": "backoffice", "status": "OK", "iniciado_em": "2026-11-03T00:00:00Z",
         "resumo": "7 achado(s) atual(is)"},
        {"id": 3, "tipo": "sintese", "status": "PARCIAL", "iniciado_em": "2026-11-02T00:00:00Z"},
    ]
    with _patched(_ClienteFake(linhas)):
        resultado = execucoes_agendadas.listar_ultimas_execucoes()
    por_tipo = {r["tipo"]: r for r in resultado}
    assert len(resultado) == 2
    # id=2 é a rodada mais recente de "backoffice" - nunca a mais antiga.
    assert por_tipo["backoffice"]["id"] == 2
    assert por_tipo["backoffice"]["status"] == "OK"
    assert por_tipo["sintese"]["status"] == "PARCIAL"


def test_tipo_sem_valor_e_ignorado_sem_lancar():
    linhas = [
        {"id": 1, "tipo": None, "status": "OK", "iniciado_em": "2026-11-01T00:00:00Z"},
        {"id": 2, "tipo": "radar_x", "status": "OK", "iniciado_em": "2026-11-01T00:00:00Z"},
    ]
    with _patched(_ClienteFake(linhas)):
        resultado = execucoes_agendadas.listar_ultimas_execucoes()
    assert [r["tipo"] for r in resultado] == ["radar_x"]


def test_rotulos_tipo_cobrem_exatamente_os_tipos_do_schema():
    # sql/coordenador.sql documenta estes 5 tipos na coluna `tipo`.
    assert set(execucoes_agendadas.ROTULOS_TIPO.keys()) == {
        "backoffice", "sintese", "radar_x", "embeddings", "comite_noturno",
    }
