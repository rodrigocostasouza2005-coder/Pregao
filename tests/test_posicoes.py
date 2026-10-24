# -*- coding: utf-8 -*-
"""Testes de data/posicoes.py (cadastro de posicoes reais - quantidade +
preco medio por ativo, tabela posicoes_carteira). Mocka o cliente Supabase
(fake simples que simula a tabela em memoria), nunca faz chamada de rede.

Uso: python tests/test_posicoes.py (python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.posicoes as posicoes_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


# ============================================================
# Fake de cliente Supabase - simula posicoes_carteira em memoria,
# chave (sub, ticker).
# ============================================================

class _TabelaFake:
    def __init__(self, cliente):
        self.cliente = cliente
        self._op = None
        self._payload = None
        self._filtros = {}

    def select(self, *_a, **_k):
        self._op = "select"
        return self

    def upsert(self, payload, on_conflict=None):
        self._op = "upsert"
        self._payload = payload
        self._on_conflict = on_conflict
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, campo, valor):
        self._filtros[campo] = valor
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, _n):
        return self

    def execute(self):
        c = self.cliente
        if self._op == "select":
            linhas = [
                l for l in c.linhas.values()
                if all(l.get(k) == v for k, v in self._filtros.items())
            ]
            linhas = sorted(linhas, key=lambda l: l.get("ticker", ""))
            resp = MagicMock()
            resp.data = linhas
            return resp
        if self._op == "upsert":
            if c.falhar_proxima_escrita:
                raise Exception("conexao indisponivel")
            chave = (self._payload["sub"], self._payload["ticker"])
            c.linhas[chave] = dict(self._payload)
            c.upserts.append(dict(self._payload))
            resp = MagicMock()
            resp.data = [dict(self._payload)]
            return resp
        if self._op == "delete":
            if c.falhar_proxima_escrita:
                raise Exception("conexao indisponivel")
            chave = (self._filtros.get("sub"), self._filtros.get("ticker"))
            c.linhas.pop(chave, None)
            c.deletes.append(chave)
            resp = MagicMock()
            resp.data = []
            return resp
        raise AssertionError(f"operacao nao mockada: {self._op}")


class _ClienteFake:
    def __init__(self):
        self.linhas = {}
        self.upserts = []
        self.deletes = []
        self.falhar_proxima_escrita = False

    def table(self, nome):
        assert nome == "posicoes_carteira"
        return _TabelaFake(self)


# ============================================================
# posicao_valida
# ============================================================

def test_1_posicao_valida_rejeita_nao_positivo_e_nao_numerico():
    _checar("1a quantidade e preco positivos -> valida", posicoes_mod.posicao_valida(100, 32.5) is True)
    _checar("1b quantidade zero -> invalida", posicoes_mod.posicao_valida(0, 32.5) is False)
    _checar("1c preco negativo -> invalida", posicoes_mod.posicao_valida(100, -1) is False)
    _checar("1d nao numerico -> invalida, sem excecao", posicoes_mod.posicao_valida("abc", 10) is False)


# ============================================================
# obter_posicoes: None (banco indisponivel) vs [] (vazio de verdade)
# ============================================================

def test_2_obter_posicoes_none_sem_cliente():
    with patch.object(posicoes_mod, "obter_cliente", return_value=None):
        _checar("2a sem cliente -> None (nunca [])", posicoes_mod.obter_posicoes("sub1") is None)


def test_3_obter_posicoes_vazio_de_verdade():
    cliente = _ClienteFake()
    with patch.object(posicoes_mod, "obter_cliente", return_value=cliente):
        _checar("3a ninguem cadastrou -> [] (lista vazia real)", posicoes_mod.obter_posicoes("sub1") == [])


def test_4_obter_posicoes_filtra_por_sub_e_ordena():
    cliente = _ClienteFake()
    cliente.linhas[("sub1", "VALE3")] = {"sub": "sub1", "ticker": "VALE3", "quantidade": 10, "preco_medio": 60}
    cliente.linhas[("sub1", "PETR4")] = {"sub": "sub1", "ticker": "PETR4", "quantidade": 20, "preco_medio": 30}
    cliente.linhas[("sub2", "ITUB4")] = {"sub": "sub2", "ticker": "ITUB4", "quantidade": 5, "preco_medio": 25}
    with patch.object(posicoes_mod, "obter_cliente", return_value=cliente):
        resultado = posicoes_mod.obter_posicoes("sub1")
    _checar("4a so' as posicoes de sub1", len(resultado) == 2)
    _checar("4b ordenado por ticker", [p["ticker"] for p in resultado] == ["PETR4", "VALE3"])


# ============================================================
# salvar_posicao: cadastro novo e edicao (upsert por sub+ticker)
# ============================================================

def test_5_salvar_posicao_cadastro_novo():
    cliente = _ClienteFake()
    with patch.object(posicoes_mod, "obter_cliente", return_value=cliente):
        ok = posicoes_mod.salvar_posicao("sub1", "petr4", 100, 32.5)
    _checar("5a retorna True", ok is True)
    linha = cliente.linhas[("sub1", "PETR4")]
    _checar("5b ticker normalizado em maiuscula", linha["ticker"] == "PETR4")
    _checar("5c quantidade/preco gravados", linha["quantidade"] == 100.0 and linha["preco_medio"] == 32.5)
    _checar("5d data_referencia default = hoje (string ISO presente)", bool(linha.get("data_referencia")))


def test_6_salvar_posicao_edicao_substitui_sem_duplicar():
    cliente = _ClienteFake()
    with patch.object(posicoes_mod, "obter_cliente", return_value=cliente):
        posicoes_mod.salvar_posicao("sub1", "PETR4", 100, 30.0)
        posicoes_mod.salvar_posicao("sub1", "PETR4", 150, 31.0)
    _checar("6a so' 1 linha pra (sub1, PETR4)", len(cliente.linhas) == 1)
    linha = cliente.linhas[("sub1", "PETR4")]
    _checar("6b quantidade/preco atualizados pro ultimo valor", linha["quantidade"] == 150.0 and linha["preco_medio"] == 31.0)


def test_7_salvar_posicao_sem_cliente_retorna_false():
    with patch.object(posicoes_mod, "obter_cliente", return_value=None):
        _checar("7a sem cliente -> False", posicoes_mod.salvar_posicao("sub1", "PETR4", 1, 1) is False)


def test_8_salvar_posicao_falha_supabase_retorna_false_sem_excecao():
    cliente = _ClienteFake()
    cliente.falhar_proxima_escrita = True
    with patch.object(posicoes_mod, "obter_cliente", return_value=cliente):
        _checar("8a falha na escrita -> False, nunca lanca", posicoes_mod.salvar_posicao("sub1", "PETR4", 1, 1) is False)


# ============================================================
# remover_posicao
# ============================================================

def test_9_remover_posicao_existente():
    cliente = _ClienteFake()
    cliente.linhas[("sub1", "PETR4")] = {"sub": "sub1", "ticker": "PETR4", "quantidade": 10, "preco_medio": 30}
    with patch.object(posicoes_mod, "obter_cliente", return_value=cliente):
        ok = posicoes_mod.remover_posicao("sub1", "petr4")
    _checar("9a retorna True", ok is True)
    _checar("9b linha removida", ("sub1", "PETR4") not in cliente.linhas)


def test_10_remover_posicao_inexistente_e_idempotente():
    cliente = _ClienteFake()
    with patch.object(posicoes_mod, "obter_cliente", return_value=cliente):
        ok = posicoes_mod.remover_posicao("sub1", "NAOEXISTE")
    _checar("10a remover algo que nao existe -> True (idempotente)", ok is True)


def test_11_remover_posicao_sem_cliente_retorna_false():
    with patch.object(posicoes_mod, "obter_cliente", return_value=None):
        _checar("11a sem cliente -> False", posicoes_mod.remover_posicao("sub1", "PETR4") is False)


# ============================================================
# tabela_disponivel - diagnostico
# ============================================================

def test_12_tabela_disponivel_sem_cliente_none():
    with patch.object(posicoes_mod, "obter_cliente", return_value=None):
        _checar("12a sem cliente -> None", posicoes_mod.tabela_disponivel() is None)


def test_13_tabela_disponivel_classifica_tabela_ausente():
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.limit.return_value.execute.side_effect = Exception(
        "Could not find the table 'public.posicoes_carteira' in the schema cache"
    )
    with patch.object(posicoes_mod, "obter_cliente", return_value=cliente):
        _checar("13a erro de schema cache -> TABELA_AUSENTE",
                 posicoes_mod.tabela_disponivel() == posicoes_mod.TABELA_AUSENTE)


def test_14_tabela_disponivel_ok():
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    with patch.object(posicoes_mod, "obter_cliente", return_value=cliente):
        _checar("14a sem erro -> True", posicoes_mod.tabela_disponivel() is True)


if __name__ == "__main__":
    nomes = [n for n in dir() if n.startswith("test_")]
    for nome in sorted(nomes, key=lambda n: int(n.split("_")[1])):
        globals()[nome]()
    if _FALHAS:
        print(f"\n{len(_FALHAS)} teste(s) falharam: {_FALHAS}")
        sys.exit(1)
    print(f"\nTodos os {len(nomes)} testes passaram.")
