# -*- coding: utf-8 -*-
"""Testes de data/user_prefs.py - mocka Supabase, nunca faz chamada real.

Cobre especificamente listar_assinantes_morning_call() (opt-in/opt-out
individual do Morning Call, 2026-10-16): consentimento explícito, nunca
um destinatário fixo (EMAIL_TO)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.user_prefs as user_prefs_mod


def _cliente_com_linhas(linhas):
    resp = MagicMock(data=linhas)
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.execute.return_value = resp
    return cliente


def test_listar_assinantes_so_inclui_quem_optou_explicitamente():
    linhas = [
        {"sub": "s1", "email": "assinante@exemplo.com", "preferencias": {"morning_call_email": True}},
        {"sub": "s2", "email": "nao-assinante@exemplo.com", "preferencias": {"morning_call_email": False}},
        {"sub": "s3", "email": "nunca-mexeu@exemplo.com", "preferencias": {}},
    ]
    with patch.object(user_prefs_mod, "obter_cliente", return_value=_cliente_com_linhas(linhas)):
        assinantes = user_prefs_mod.listar_assinantes_morning_call()
    assert assinantes == [{"sub": "s1", "email": "assinante@exemplo.com"}]


def test_listar_assinantes_usuario_pode_cancelar_descadastro():
    """Desmarcar o opt-in (morning_call_email=False) remove o usuário da
    lista - mesmo registro, mesmo controle que ativa."""
    linhas = [{"sub": "s1", "email": "voltou-atras@exemplo.com", "preferencias": {"morning_call_email": False, "tema": "AMBAR"}}]
    with patch.object(user_prefs_mod, "obter_cliente", return_value=_cliente_com_linhas(linhas)):
        assinantes = user_prefs_mod.listar_assinantes_morning_call()
    assert assinantes == []


def test_listar_assinantes_ignora_opt_in_sem_email_valido():
    """email é NOT NULL em user_prefs (sql/schema.sql) - defesa extra
    ainda assim, nunca envia pra string vazia."""
    linhas = [{"sub": "s1", "email": "", "preferencias": {"morning_call_email": True}}]
    with patch.object(user_prefs_mod, "obter_cliente", return_value=_cliente_com_linhas(linhas)):
        assinantes = user_prefs_mod.listar_assinantes_morning_call()
    assert assinantes == []


def test_listar_assinantes_multiplos_usuarios():
    linhas = [
        {"sub": "s1", "email": "a@exemplo.com", "preferencias": {"morning_call_email": True}},
        {"sub": "s2", "email": "b@exemplo.com", "preferencias": {"morning_call_email": True}},
        {"sub": "s3", "email": "c@exemplo.com", "preferencias": {"morning_call_email": True}},
    ]
    with patch.object(user_prefs_mod, "obter_cliente", return_value=_cliente_com_linhas(linhas)):
        assinantes = user_prefs_mod.listar_assinantes_morning_call()
    assert {a["email"] for a in assinantes} == {"a@exemplo.com", "b@exemplo.com", "c@exemplo.com"}


def test_listar_assinantes_nenhum_opt_in_retorna_lista_vazia_nao_none():
    linhas = [{"sub": "s1", "email": "a@exemplo.com", "preferencias": {"morning_call_email": False}}]
    with patch.object(user_prefs_mod, "obter_cliente", return_value=_cliente_com_linhas(linhas)):
        assinantes = user_prefs_mod.listar_assinantes_morning_call()
    assert assinantes == []  # nunca None - None significa "não deu pra saber", não "ninguém assinou"


def test_listar_assinantes_banco_indisponivel_retorna_none_nao_lista_vazia():
    """None (banco fora do ar) precisa ser DISTINGUÍVEL de [] (ninguém
    assinou) - quem chama (jobs/morning_call.py) nunca pode tratar
    'não consegui checar' como 'zero assinantes' (enviaria pra zero
    pessoas silenciosamente num dia em que na verdade havia assinantes)."""
    with patch.object(user_prefs_mod, "obter_cliente", return_value=None):
        assert user_prefs_mod.listar_assinantes_morning_call() is None


def test_listar_assinantes_excecao_na_consulta_retorna_none():
    cliente = MagicMock()
    cliente.table.side_effect = RuntimeError("Supabase fora do ar")
    with patch.object(user_prefs_mod, "obter_cliente", return_value=cliente):
        assert user_prefs_mod.listar_assinantes_morning_call() is None
