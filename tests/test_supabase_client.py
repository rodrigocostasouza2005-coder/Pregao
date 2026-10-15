# -*- coding: utf-8 -*-
"""Testes de data/supabase_client.py - nunca faz chamada de rede real,
nunca usa uma credencial de verdade.

Regressao 2026-10-15 (auditoria do secret SUPABASE_SECRET_KEY errado em
producao): antes, qualquer valor nao-vazio criava um cliente Supabase,
mesmo quando era claramente a chave PUBLICA (publishable/anon) - toda
escrita subsequente falhava com "new row violates row-level security
policy", 1x por tabela/coletor, sem 1 diagnostico claro na origem.
"""
import base64
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.supabase_client as sc_mod


def _jwt_fake(papel: str) -> str:
    """JWT sintatico minimo (header.payload.signature) com o claim
    'role' pedido - assinatura fake, nunca validada aqui (so' o PAYLOAD
    e' lido, sem checar assinatura, igual o codigo real faz)."""
    def _b64(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    return f"{_b64({'alg': 'HS256'})}.{_b64({'role': papel})}.assinatura-fake"


def test_formato_sb_secret_e_privilegiada():
    assert sc_mod._classificar_formato_chave("sb_secret_abc123") == "PRIVILEGIADA"


def test_formato_sb_publishable_e_publica():
    assert sc_mod._classificar_formato_chave("sb_publishable_abc123") == "PUBLICA"


def test_formato_jwt_service_role_e_privilegiada():
    assert sc_mod._classificar_formato_chave(_jwt_fake("service_role")) == "PRIVILEGIADA"


def test_formato_jwt_anon_e_publica():
    assert sc_mod._classificar_formato_chave(_jwt_fake("anon")) == "PUBLICA"


def test_formato_jwt_authenticated_e_publica():
    assert sc_mod._classificar_formato_chave(_jwt_fake("authenticated")) == "PUBLICA"


def test_formato_vazio_e_desconhecido():
    assert sc_mod._classificar_formato_chave("") == "DESCONHECIDO"


def test_formato_desconhecido_nao_e_bloqueado_por_engano():
    """Formato nunca visto (ex: um esquema de chave futuro) fica
    DESCONHECIDO - nunca PUBLICA por engano, pra nao bloquear uma
    credencial legitima so' porque o formato ainda nao e' reconhecido."""
    assert sc_mod._classificar_formato_chave("algum-formato-novo-nao-mapeado") == "DESCONHECIDO"
    assert sc_mod._classificar_formato_chave("eyJsixo.nao-e-json-valido.assinatura") == "DESCONHECIDO"


def test_obter_cliente_retorna_none_com_chave_publica_sb_publishable(monkeypatch):
    sc_mod.obter_cliente.clear()
    monkeypatch.setenv("SUPABASE_URL", "https://projeto-teste.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_publishable_naoescreve123")
    with patch.object(sc_mod, "create_client") as mock_create:
        cliente = sc_mod.obter_cliente()
    assert cliente is None
    assert not mock_create.called, "nunca deve tentar criar cliente com chave claramente publica"
    sc_mod.obter_cliente.clear()


def test_obter_cliente_retorna_none_com_jwt_anon(monkeypatch):
    sc_mod.obter_cliente.clear()
    monkeypatch.setenv("SUPABASE_URL", "https://projeto-teste.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", _jwt_fake("anon"))
    with patch.object(sc_mod, "create_client") as mock_create:
        cliente = sc_mod.obter_cliente()
    assert cliente is None
    assert not mock_create.called
    sc_mod.obter_cliente.clear()


def test_obter_cliente_cria_cliente_com_chave_sb_secret(monkeypatch):
    sc_mod.obter_cliente.clear()
    monkeypatch.setenv("SUPABASE_URL", "https://projeto-teste.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_privilegiada123")
    with patch.object(sc_mod, "create_client", return_value="cliente-fake") as mock_create:
        cliente = sc_mod.obter_cliente()
    assert cliente == "cliente-fake"
    assert mock_create.called
    sc_mod.obter_cliente.clear()


def test_obter_cliente_formato_desconhecido_ainda_tenta_criar(monkeypatch):
    """Formato nao reconhecido nunca bloqueia preventivamente - so' os
    2 casos INEQUIVOCOS (sb_publishable_/JWT anon-authenticated) bloqueiam."""
    sc_mod.obter_cliente.clear()
    monkeypatch.setenv("SUPABASE_URL", "https://projeto-teste.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "formato-futuro-desconhecido")
    with patch.object(sc_mod, "create_client", return_value="cliente-fake") as mock_create:
        cliente = sc_mod.obter_cliente()
    assert cliente == "cliente-fake"
    assert mock_create.called
    sc_mod.obter_cliente.clear()


def test_obter_cliente_sem_credencial_retorna_none(monkeypatch):
    sc_mod.obter_cliente.clear()
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    with patch.object(sc_mod.st, "secrets", {}):
        cliente = sc_mod.obter_cliente()
    assert cliente is None
    sc_mod.obter_cliente.clear()
