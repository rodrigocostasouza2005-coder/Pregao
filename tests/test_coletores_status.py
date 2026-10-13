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
        # 2026-10-10: faz a checagem REALMENTE falhar sob pytest (antes so'
        # imprimia e guardava em _FALHAS, lido so' pelo runner `__main__` -
        # sob pytest toda funcao test_* passava mesmo com condicao=False,
        # a menos que outra linha lancasse excecao por acidente; ver
        # investigacao registrada no relatorio da auditoria 2026-10-10)
        raise AssertionError(f"{nome} {detalhe}".strip())


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


def _cliente_cuja_consulta_falha(excecao: Exception) -> "_ClienteFake":
    cliente = _ClienteFake()
    cliente.table_original = cliente.table

    def _table_que_falha(nome):
        tabela = cliente.table_original(nome)
        tabela.execute = lambda: (_ for _ in ()).throw(excecao)
        return tabela

    cliente.table = _table_que_falha
    return cliente


def test_9_tabela_disponivel_quando_consulta_trivial_funciona():
    # sucesso real: consulta funciona e devolve historico vazio (lista
    # vazia, sem excecao nenhuma) - distinto de qualquer um dos 3
    # estados de falha abaixo, e distinto de obter_status/obter_todos_status
    # tambem nao lancarem excecao pro mesmo cliente (ver tests 5/7).
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        disponivel = cs_mod.tabela_disponivel()
        vazio = cs_mod.obter_todos_status()
    _checar("9 tabela responde a consulta trivial -> True", disponivel is True)
    _checar("9z historico vazio (sem tentativa registrada) nao e' erro -> {}", vazio == {})


def test_9b_tabela_ausente_classificada_distinto_de_credencial():
    # erro real do postgrest-py (APIError==2.32.0): .code='PGRST205',
    # .message contem "Could not find the table ... in the schema cache"
    # - mesma assinatura ja' confirmada em producao pra eventos_resultados
    # (commit 4c17876).
    erro = Exception("PGRST205: Could not find the table 'public.coletores_status' in the schema cache")
    cliente = _cliente_cuja_consulta_falha(erro)
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        disponivel = cs_mod.tabela_disponivel()
    _checar(
        "9b tabela ausente/erro de schema -> TABELA_AUSENTE (nunca o mesmo sinal de credencial/conexao)",
        disponivel == cs_mod.TABELA_AUSENTE,
    )


def test_9c_supabase_fora_do_ar_retorna_none_nao_false():
    with patch.object(cs_mod, "obter_cliente", return_value=None):
        disponivel = cs_mod.tabela_disponivel()
    _checar("9c Supabase em si fora do ar (sem credencial configurada) -> None (distinto de 'tabela ausente')", disponivel is None)


def test_9d_erro_de_credencial_invalida_classificado_distinto_de_tabela_ausente():
    # achado real (missao 2026-10-13, continuacao): ANTES desta correcao,
    # esta excecao caia no MESMO sinal de "tabela ausente" (False), fazendo
    # o painel sugerir rodar sql/coletores_status.sql quando a tabela ja'
    # existe e o problema real e' a API key/secret_key errada.
    erro = Exception('{"message":"Invalid API key","hint":"Double check your Supabase `anon` or `service_role` API key."}')
    cliente = _cliente_cuja_consulta_falha(erro)
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        disponivel = cs_mod.tabela_disponivel()
    _checar(
        "9d erro de credencial invalida -> CREDENCIAL_OU_CONEXAO (nunca TABELA_AUSENTE)",
        disponivel == cs_mod.TABELA_CREDENCIAL_OU_CONEXAO,
    )


def test_9e_erro_de_conexao_tambem_classificado_como_credencial_ou_conexao():
    # erro tipico de rede (httpx.ConnectTimeout/ConnectError na vida real,
    # aqui so' uma Exception generica com o mesmo texto) - mesmo vocabulario
    # de data/saude_dados.py:_TERMOS_INDISPONIBILIDADE.
    erro = Exception("httpx.ConnectTimeout: timed out while connecting to Supabase")
    cliente = _cliente_cuja_consulta_falha(erro)
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        disponivel = cs_mod.tabela_disponivel()
    _checar(
        "9e timeout de conexao -> CREDENCIAL_OU_CONEXAO (agrupado com credencial, nunca TABELA_AUSENTE)",
        disponivel == cs_mod.TABELA_CREDENCIAL_OU_CONEXAO,
    )


def test_9f_erro_sem_nenhum_sinal_conhecido_fica_erro_desconhecido():
    # nem "tabela ausente" nem "credencial/conexao" - ainda assim nunca
    # finge sucesso (True) nem reusa um dos outros 2 sinais sem evidencia.
    erro = Exception("ValueError inesperado dentro do parser da resposta")
    cliente = _cliente_cuja_consulta_falha(erro)
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        disponivel = cs_mod.tabela_disponivel()
    _checar(
        "9f erro sem sinal conhecido -> ERRO_DESCONHECIDO (nunca True, nunca os outros 2 sinais)",
        disponivel == cs_mod.TABELA_ERRO_DESCONHECIDO,
    )


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass  # ja' registrado em _FALHAS por _checar

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE REGISTRO DE SAUDE DOS COLETORES PASSARAM")
