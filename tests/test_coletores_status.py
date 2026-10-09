# -*- coding: utf-8 -*-
"""Testes do registro de tentativas de coleta (data/coletores_status.py,
tabela coletores_status) - mocka o cliente Supabase (fake em memoria,
mesmo padrao de tests/test_ia_cache.py), nunca faz chamada de rede.

Uso: python tests/test_coletores_status.py (python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.coletores_status as cs_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


class _TabelaFake:
    def __init__(self, cliente):
        self.cliente = cliente
        self._filtro_nome = None
        self._op = None
        self._payload = None

    def select(self, *_a, **_k):
        self._op = "select"
        return self

    def upsert(self, payload):
        self._op = "upsert"
        self._payload = payload
        return self

    def eq(self, campo, valor):
        if campo == "nome":
            self._filtro_nome = valor
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        if self._op == "upsert":
            self.cliente.linhas[self._payload["nome"]] = dict(self._payload)
            return _Resposta([self._payload])
        if self._op == "select":
            if self._filtro_nome is not None:
                linha = self.cliente.linhas.get(self._filtro_nome)
                return _Resposta([linha] if linha else [])
            return _Resposta(list(self.cliente.linhas.values()))
        return _Resposta([])


class _Resposta:
    def __init__(self, data):
        self.data = data


class _ClienteFake:
    def __init__(self):
        self.linhas = {}

    def table(self, _nome):
        return _TabelaFake(self)


def test_1_registrar_sucesso_com_banco_fora_do_ar_retorna_false():
    with patch.object(cs_mod, "obter_cliente", return_value=None):
        ok = cs_mod.registrar_tentativa("NEWS", "Google News", execucao_ok=True, registros_novos=3)
    _checar("1 banco fora do ar -> registrar_tentativa retorna False, nunca lanca excecao", ok is False)


def test_2_registrar_sucesso_grava_ultimo_sucesso_em():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        ok = cs_mod.registrar_tentativa("NEWS", "Google News", execucao_ok=True, persistencia_ok=True, registros_novos=4, categoria="Noticias")
    linha = cliente.linhas["NEWS"]
    _checar("2a registrar_tentativa retorna True", ok is True)
    _checar("2b ultimo_sucesso_em preenchido", linha["ultimo_sucesso_em"] is not None)
    _checar("2c registros_novos gravado", linha["registros_novos"] == 4)
    _checar("2d ultimo_erro None em sucesso", linha["ultimo_erro"] is None)


def test_3_falha_depois_de_sucesso_preserva_ultimo_sucesso_em():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        cs_mod.registrar_tentativa("MACRO", "BCB", execucao_ok=True, registros_novos=1)
        sucesso_registrado = cliente.linhas["MACRO"]["ultimo_sucesso_em"]
        cs_mod.registrar_tentativa("MACRO", "BCB", execucao_ok=False, erro="timeout")
    linha = cliente.linhas["MACRO"]
    _checar("3a tentativa seguinte falhou -> execucao_ok False", linha["execucao_ok"] is False)
    _checar("3b ultimo_sucesso_em da tentativa boa anterior preservado", linha["ultimo_sucesso_em"] == sucesso_registrado)
    _checar("3c erro da tentativa falha registrado", linha["ultimo_erro"] == "timeout")
    _checar("3d registros_novos zera numa tentativa falha", linha["registros_novos"] == 0)


def test_4_falha_sem_sucesso_anterior_ultimo_sucesso_em_fica_none():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        cs_mod.registrar_tentativa("CVM", "dados.cvm.gov.br", execucao_ok=False, erro="403 bloqueado")
    linha = cliente.linhas["CVM"]
    _checar("4 nunca teve sucesso -> ultimo_sucesso_em None", linha["ultimo_sucesso_em"] is None)


def test_5_obter_status_inexistente_retorna_none():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        status = cs_mod.obter_status("NAO_EXISTE")
    _checar("5 coletor nunca registrado -> obter_status None", status is None)


def test_6_obter_status_banco_fora_do_ar_retorna_none():
    with patch.object(cs_mod, "obter_cliente", return_value=None):
        status = cs_mod.obter_status("NEWS")
    _checar("6 banco fora do ar -> obter_status None (nunca excecao)", status is None)


def test_7_obter_todos_status_indexado_por_nome():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        cs_mod.registrar_tentativa("NEWS", "Google News", execucao_ok=True, registros_novos=1)
        cs_mod.registrar_tentativa("MERCADO", "yfinance", execucao_ok=True, registros_novos=0)
        todos = cs_mod.obter_todos_status()
    _checar("7a retorna um dict com as 2 chaves", set(todos.keys()) == {"NEWS", "MERCADO"})
    _checar("7b cada valor e' a linha completa", todos["NEWS"]["fonte"] == "Google News")


def test_8_execucao_excecao_no_execute_nunca_propaga():
    cliente = _ClienteFake()
    cliente.table_original = cliente.table

    def _table_que_falha(nome):
        tabela = cliente.table_original(nome)
        tabela.execute = lambda: (_ for _ in ()).throw(Exception("PGRST205"))
        return tabela

    cliente.table = _table_que_falha
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        ok = cs_mod.registrar_tentativa("NEWS", "Google News", execucao_ok=True)
        status = cs_mod.obter_status("NEWS")
    _checar("8a registrar_tentativa com erro no execute -> False, sem excecao", ok is False)
    _checar("8b obter_status com erro no execute -> None, sem excecao", status is None)


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE REGISTRO DE SAUDE DOS COLETORES PASSARAM")
