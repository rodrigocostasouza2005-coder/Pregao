# -*- coding: utf-8 -*-
"""Testes da classificacao de SAUDE DOS DADOS (data/saude_dados.py) -
os estados diferenciados pedidos na FASE 2 (sucesso com/sem novidade,
parcial, falha de execucao, falha de persistencia, desatualizado,
fonte indisponivel, nao comprovado/nunca executado). `classificar_estado`
e' funcao pura (sem rede/banco) - testada so' com dicts de entrada.
`obter_painel_saude` e' testado mockando `coletores_status.obter_status`
e os leitores somente-leitura.

Uso: python tests/test_saude_dados.py (python do .venv do projeto)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.saude_dados as saude_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


def _ha(horas):
    return (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()


def test_1_sem_status_e_nunca_executado():
    codigo, _ = saude_mod.classificar_estado(None)
    _checar("1 status None -> NUNCA_EXECUTADO", codigo == "NUNCA_EXECUTADO")


def test_2_execucao_ok_sem_sucesso_nunca_e_nao_comprovado():
    status = {"execucao_ok": False, "persistencia_ok": True, "ultimo_erro": "x", "ultimo_sucesso_em": None}
    codigo, rotulo = saude_mod.classificar_estado(status)
    _checar("2 nunca teve sucesso -> NAO_COMPROVADO", codigo == "NAO_COMPROVADO")
    _checar("2b rotulo menciona o erro mais recente", "x" in rotulo)


def test_3_sucesso_com_novidade():
    status = {"execucao_ok": True, "persistencia_ok": True, "registros_novos": 5, "ultimo_sucesso_em": _ha(0.1)}
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("3 execucao+persistencia OK e registros_novos>0 -> SUCESSO_COM_NOVIDADE", codigo == "SUCESSO_COM_NOVIDADE")


def test_4_sucesso_sem_novidade():
    status = {"execucao_ok": True, "persistencia_ok": True, "registros_novos": 0, "ultimo_sucesso_em": _ha(0.1)}
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("4 registros_novos==0 -> SUCESSO_SEM_NOVIDADE", codigo == "SUCESSO_SEM_NOVIDADE")


def test_5_parcial():
    status = {"execucao_ok": True, "persistencia_ok": True, "registros_novos": 0, "parcial": True, "ultimo_sucesso_em": _ha(0.1)}
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("5 parcial=True -> PARCIAL", codigo == "PARCIAL")


def test_6_falha_execucao_generica():
    status = {"execucao_ok": False, "persistencia_ok": True, "ultimo_erro": "KeyError inesperado", "ultimo_sucesso_em": _ha(1)}
    codigo, rotulo = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("6 erro sem termo de indisponibilidade -> FALHA_EXECUCAO", codigo == "FALHA_EXECUCAO")
    _checar("6b rotulo cita o erro real", "KeyError" in rotulo)


def test_7_fonte_indisponivel():
    status = {"execucao_ok": False, "persistencia_ok": True, "ultimo_erro": "timeout ao conectar", "ultimo_sucesso_em": _ha(1)}
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("7 erro com 'timeout' -> FONTE_INDISPONIVEL", codigo == "FONTE_INDISPONIVEL")


def test_8_falha_persistencia():
    status = {"execucao_ok": True, "persistencia_ok": False, "ultimo_sucesso_em": _ha(1)}
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("8 execucao OK mas persistencia_ok=False -> FALHA_PERSISTENCIA", codigo == "FALHA_PERSISTENCIA")


def test_9_dados_desatualizados():
    status = {"execucao_ok": True, "persistencia_ok": True, "registros_novos": 0, "ultimo_sucesso_em": _ha(48)}
    codigo, rotulo = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("9 ultimo sucesso ha 48h com limite 6h -> DADOS_DESATUALIZADOS", codigo == "DADOS_DESATUALIZADOS")
    _checar("9b rotulo cita a idade aproximada", "48" in rotulo)


def test_10_sem_limite_de_idade_nao_marca_desatualizado():
    status = {"execucao_ok": True, "persistencia_ok": True, "registros_novos": 0, "ultimo_sucesso_em": _ha(1000)}
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=None)
    _checar("10 idade_maxima_horas=None nunca marca desatualizado", codigo == "SUCESSO_SEM_NOVIDADE")


def test_11_falha_execucao_tem_prioridade_sobre_desatualizado():
    status = {"execucao_ok": False, "persistencia_ok": True, "ultimo_erro": "erro generico", "ultimo_sucesso_em": _ha(100)}
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("11 tentativa mais recente falhou -> reporta a falha, nao so' 'desatualizado'", codigo == "FALHA_EXECUCAO")


def test_12_status_somente_leitura_sem_dado_e_none():
    _checar("12 _status_somente_leitura(None) -> None", saude_mod._status_somente_leitura(None) is None)


def test_13_status_somente_leitura_aceita_datetime_e_string():
    agora = datetime.now(timezone.utc)
    s1 = saude_mod._status_somente_leitura(agora)
    s2 = saude_mod._status_somente_leitura(agora.isoformat())
    _checar("13a datetime normalizado pra iso", s1["ultimo_sucesso_em"] == agora.isoformat())
    _checar("13b string aceita direto", s2["ultimo_sucesso_em"] == agora.isoformat())
    _checar("13c execucao_ok=None (desconhecido, nunca inventado)", s1["execucao_ok"] is None)


def test_14_painel_completo_cobre_todos_os_coletores_registrados():
    with patch.object(saude_mod.coletores_status, "obter_status", return_value=None):
        with patch.object(saude_mod, "REGISTRO_COLETORES", [
            {**c, "leitor": (lambda: None)} if not c["instrumentado"] else c
            for c in saude_mod.REGISTRO_COLETORES
        ]):
            painel = saude_mod.obter_painel_saude()
    nomes_painel = {item["nome"] for item in painel}
    nomes_registro = {c["nome"] for c in saude_mod.REGISTRO_COLETORES}
    _checar("14a painel tem 1 entrada por coletor registrado", nomes_painel == nomes_registro)
    _checar("14b sem nenhum dado disponivel, tudo cai em NUNCA_EXECUTADO", all(item["codigo_estado"] == "NUNCA_EXECUTADO" for item in painel))
    _checar("14c todos marcados como 'desconhecido' (nao falso-verde)", all(item["desconhecido"] for item in painel))


def test_15_painel_excecao_num_leitor_nao_derruba_o_painel():
    def _leitor_que_falha():
        raise RuntimeError("Supabase fora do ar")

    registro_modificado = [dict(c) for c in saude_mod.REGISTRO_COLETORES]
    for c in registro_modificado:
        if not c["instrumentado"]:
            c["leitor"] = _leitor_que_falha

    with patch.object(saude_mod.coletores_status, "obter_status", side_effect=RuntimeError("banco fora do ar")):
        with patch.object(saude_mod, "REGISTRO_COLETORES", registro_modificado):
            painel = saude_mod.obter_painel_saude()
    _checar("15 painel completo mesmo com todo leitor/obter_status lancando excecao", len(painel) == len(registro_modificado))
    _checar("15b todas as entradas ficam NUNCA_EXECUTADO (nao quebra, nao finge sucesso)", all(item["codigo_estado"] == "NUNCA_EXECUTADO" for item in painel))


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE SAUDE DOS DADOS PASSARAM")
