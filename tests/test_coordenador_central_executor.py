# -*- coding: utf-8 -*-
"""Executor do Coordenador Central (data/coordenador_central/executor.py)
- isolamento (erro de 1 especialista nunca propaga), timeout real (nunca
trava o chamador) e paralelismo real (N especialistas rodam ao mesmo
tempo, não em sequência). Especialistas FAKE registrados temporariamente
em registro.REGISTRO (restaurados no fim de cada teste) - zero chamada
real a qualquer função de negócio."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.coordenador_central import executor
from data.coordenador_central.registro import Especialista, REGISTRO


def _extrator_identidade(bruto):
    return bruto


@pytest.fixture
def registro_limpo():
    """Remove, no fim do teste, qualquer especialista fake inserido."""
    chaves_antes = set(REGISTRO.keys())
    yield
    for chave in set(REGISTRO.keys()) - chaves_antes:
        del REGISTRO[chave]


def _registrar_fake(especialista_id: str, funcao):
    REGISTRO[especialista_id] = Especialista(
        id=especialista_id, nome=especialista_id, descricao="fake de teste",
        capacidades=(), pre_requisitos=(), entradas_aceitas={},
        funcao=funcao, extrator_saida=_extrator_identidade,
    )


def test_executar_especialista_sucesso_simples(registro_limpo):
    _registrar_fake("fake_ok", lambda **kw: {
        "disponivel": True, "resumo": "ok", "evidencias": [], "motivo_indisponivel": None, "dados": kw,
    })
    resultado = executor.executar_especialista("fake_ok", ticker="PETR4")
    assert resultado["id"] == "fake_ok"
    assert resultado["disponivel"] is True
    assert resultado["resumo"] == "ok"
    assert resultado["erro_tecnico"] is None
    assert resultado["duracao_ms"] >= 0
    assert resultado["dados"] == {"ticker": "PETR4"}


def test_executar_especialista_nao_registrado_nunca_lanca():
    resultado = executor.executar_especialista("nao-existe", ticker="X")
    assert resultado["disponivel"] is False
    assert "não está registrado" in resultado["motivo_indisponivel"]


def test_executar_especialista_isola_excecao_da_funcao_real(registro_limpo):
    def _quebra(**kw):
        raise RuntimeError("falha interna do especialista")
    _registrar_fake("fake_quebra", _quebra)
    resultado = executor.executar_especialista("fake_quebra", ticker="X")
    assert resultado["disponivel"] is False
    assert resultado["motivo_indisponivel"] == "falha técnica ao executar especialista"
    assert "RuntimeError" in resultado["erro_tecnico"]


def test_executar_especialista_timeout_nunca_trava_o_chamador(registro_limpo):
    def _nunca_retorna(**kw):
        time.sleep(5)
        return {"disponivel": True, "resumo": "nunca deveria chegar aqui", "evidencias": [], "motivo_indisponivel": None}
    _registrar_fake("fake_lento", _nunca_retorna)

    inicio = time.monotonic()
    resultado = executor.executar_especialista("fake_lento", timeout_seg=1, ticker="X")
    duracao_real = time.monotonic() - inicio

    assert duracao_real < 3  # bem menor que os 5s do sleep interno
    assert resultado["disponivel"] is False
    assert resultado["motivo_indisponivel"] == "timeout"
    assert "TimeoutError" in resultado["erro_tecnico"]


def test_executar_varios_roda_em_paralelo_de_verdade(registro_limpo):
    """3 especialistas de 0.5s cada: em paralelo o lote inteiro termina
    em ~0.5s, NUNCA ~1.5s (que seria o caso sequencial)."""
    def _lento(**kw):
        time.sleep(0.5)
        return {"disponivel": True, "resumo": "ok", "evidencias": [], "motivo_indisponivel": None}

    for especialista_id in ("fake_a", "fake_b", "fake_c"):
        _registrar_fake(especialista_id, _lento)

    inicio = time.monotonic()
    resultados = executor.executar_varios(["fake_a", "fake_b", "fake_c"], ticker="X")
    duracao_total = time.monotonic() - inicio

    assert duracao_total < 1.2  # bem abaixo de 1.5s (soma sequencial)
    assert all(r["disponivel"] for r in resultados.values())
    assert set(resultados.keys()) == {"fake_a", "fake_b", "fake_c"}


def test_executar_varios_falha_parcial_nao_impede_os_demais(registro_limpo):
    def _ok(**kw):
        return {"disponivel": True, "resumo": "ok", "evidencias": [], "motivo_indisponivel": None}

    def _falha(**kw):
        raise ValueError("erro de verdade")

    _registrar_fake("fake_ok1", _ok)
    _registrar_fake("fake_falha", _falha)
    _registrar_fake("fake_ok2", _ok)

    resultados = executor.executar_varios(["fake_ok1", "fake_falha", "fake_ok2"], ticker="X")
    assert resultados["fake_ok1"]["disponivel"] is True
    assert resultados["fake_ok2"]["disponivel"] is True
    assert resultados["fake_falha"]["disponivel"] is False
    assert "ValueError" in resultados["fake_falha"]["erro_tecnico"]


def test_executar_varios_lista_vazia_devolve_dict_vazio():
    assert executor.executar_varios([]) == {}


def test_execucao_id_e_unico_por_chamada(registro_limpo):
    _registrar_fake("fake_ok", lambda **kw: {"disponivel": True, "resumo": "ok", "evidencias": [], "motivo_indisponivel": None})
    r1 = executor.executar_especialista("fake_ok")
    r2 = executor.executar_especialista("fake_ok")
    assert r1["execucao_id"] != r2["execucao_id"]
