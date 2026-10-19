# -*- coding: utf-8 -*-
"""Testes de data/user_prefs.py: oferta de inscrição no Morning Call
(deve_oferecer_morning_call) e registro de acesso pro painel admin
(registrar_acesso) - ver missão "onboarding de e-mail + painel de
usuários" (2026-10-18).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import data.user_prefs as user_prefs


def _resp(linhas):
    resp = MagicMock()
    resp.data = linhas
    return resp


# ---------------------------------------------------------------------
# deve_oferecer_morning_call
# ---------------------------------------------------------------------

def test_usuario_sem_resposta_recebe_a_oferta():
    assert user_prefs.deve_oferecer_morning_call({}) is True
    assert user_prefs.deve_oferecer_morning_call(
        {"morning_call_email_ativo": False, "morning_call_email_perguntado": False},
    ) is True


def test_usuario_inscrito_nao_recebe_a_oferta_de_novo():
    assert user_prefs.deve_oferecer_morning_call({"morning_call_email_ativo": True}) is False


def test_usuario_que_recusou_nao_recebe_a_oferta_de_novo():
    assert user_prefs.deve_oferecer_morning_call(
        {"morning_call_email_ativo": False, "morning_call_email_perguntado": True},
    ) is False


# ---------------------------------------------------------------------
# registrar_acesso
# ---------------------------------------------------------------------

def _cliente_select_vazio():
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = _resp([])
    return cliente


def test_registrar_acesso_sem_cliente_nao_lanca_excecao(monkeypatch):
    monkeypatch.setattr(user_prefs, "obter_cliente", lambda: None)
    user_prefs.registrar_acesso("sub-1", "user@exemplo.com")  # nao deve lancar


def test_registrar_acesso_usuario_novo_insere_linha_com_created_e_last_seen():
    cliente = _cliente_select_vazio()
    user_prefs.registrar_acesso("sub-novo", "Novo@Exemplo.com", cliente=cliente)

    cliente.table.return_value.insert.assert_called_once()
    registro = cliente.table.return_value.insert.call_args[0][0]
    assert registro["sub"] == "sub-novo"
    assert registro["email"] == "novo@exemplo.com"
    assert registro["created_at"]
    assert registro["last_seen_at"]
    # nao usa upsert pra usuario novo (ver docstring: evita sobrescrever
    # preferencias de uma linha criada por uma corrida entre o select e
    # o insert)
    cliente.table.return_value.upsert.assert_not_called()


def test_registrar_acesso_corrida_na_criacao_cai_para_update_sem_sobrescrever_prefs():
    cliente = _cliente_select_vazio()
    cliente.table.return_value.insert.return_value.execute.side_effect = RuntimeError("duplicate key sub")

    user_prefs.registrar_acesso("sub-corrida", "user@exemplo.com", cliente=cliente)

    cliente.table.return_value.update.assert_called_once()
    assert "last_seen_at" in cliente.table.return_value.update.call_args[0][0]
    assert "preferencias" not in cliente.table.return_value.update.call_args[0][0]


def test_registrar_acesso_usuario_existente_sem_last_seen_atualiza():
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = _resp(
        [{"last_seen_at": None}],
    )
    user_prefs.registrar_acesso("sub-existente", "user@exemplo.com", cliente=cliente)
    cliente.table.return_value.update.assert_called_once()
    cliente.table.return_value.insert.assert_not_called()


def test_registrar_acesso_recente_nao_escreve_de_novo():
    """Rate-limite: acesso ha' 5min nao deve gerar outro UPDATE - e'
    exatamente o que evita escrever a cada rerun/fragment do Streamlit."""
    agora = datetime.now(timezone.utc)
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = _resp(
        [{"last_seen_at": (agora - timedelta(minutes=5)).isoformat()}],
    )
    user_prefs.registrar_acesso("sub-recente", "user@exemplo.com", cliente=cliente)
    cliente.table.return_value.update.assert_not_called()
    cliente.table.return_value.insert.assert_not_called()


def test_registrar_acesso_antigo_escreve_de_novo():
    agora = datetime.now(timezone.utc)
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = _resp(
        [{"last_seen_at": (agora - timedelta(hours=2)).isoformat()}],
    )
    user_prefs.registrar_acesso("sub-antigo", "user@exemplo.com", cliente=cliente)
    cliente.table.return_value.update.assert_called_once()


def test_registrar_acesso_falha_na_consulta_nao_lanca_excecao():
    cliente = MagicMock()
    cliente.table.side_effect = RuntimeError("Supabase fora do ar")
    user_prefs.registrar_acesso("sub-x", "user@exemplo.com", cliente=cliente)  # nao deve lancar


# ---------------------------------------------------------------------
# round-trip: perguntado persiste entre "sessoes" (obter_prefs/salvar_prefs)
# ---------------------------------------------------------------------

def test_perguntado_persiste_no_round_trip(monkeypatch):
    armazenamento = {}
    cliente = MagicMock()

    def _fake_upsert(registro):
        armazenamento[registro["sub"]] = registro
        execucao = MagicMock()
        execucao.execute.return_value = MagicMock()
        return execucao

    cliente.table.return_value.upsert.side_effect = _fake_upsert

    def _select(*_a, **_k):
        tabela_select = MagicMock()

        def _eq(_campo, valor):
            limit_mock = MagicMock()
            limit_mock.limit.return_value.execute.return_value = _resp(
                [{"preferencias": armazenamento[valor]["preferencias"]}] if valor in armazenamento else [],
            )
            return limit_mock

        tabela_select.eq.side_effect = _eq
        return tabela_select

    cliente.table.return_value.select.side_effect = _select
    monkeypatch.setattr(user_prefs, "obter_cliente", lambda: cliente)

    ok = user_prefs.salvar_prefs(
        "sub-999", "user@exemplo.com",
        {"morning_call_email_ativo": False, "morning_call_email_perguntado": True},
    )
    assert ok is True

    prefs_lidas, banco_ok = user_prefs.obter_prefs("sub-999")
    assert banco_ok is True
    assert prefs_lidas["morning_call_email_perguntado"] is True
    assert user_prefs.deve_oferecer_morning_call(prefs_lidas) is False


def test_falha_de_persistencia_retorna_false_sem_falsa_confirmacao(monkeypatch):
    cliente = MagicMock()
    cliente.table.return_value.upsert.return_value.execute.side_effect = RuntimeError("fora do ar")
    monkeypatch.setattr(user_prefs, "obter_cliente", lambda: cliente)

    ok = user_prefs.salvar_prefs("sub-falha", "user@exemplo.com", {"morning_call_email_ativo": True})
    assert ok is False
