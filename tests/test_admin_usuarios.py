# -*- coding: utf-8 -*-
"""Testes de data/admin_usuarios.py: a camada de dados do painel
USUÁRIOS (ver ui/usuarios_tab.py) - autorização aplicada NA CONSULTA
(não só na renderização/navegação do app.py), normalização do status
de inscrição e paginação, seguindo o mesmo padrão de
tests/test_user_prefs_assinantes.py (None = indisponível/não-autorizado,
[] = banco disponível e vazio de verdade).
"""
from unittest.mock import MagicMock, patch

import data.admin_usuarios as admin_usuarios


def _resp(linhas):
    resp = MagicMock()
    resp.data = linhas
    return resp


def _cliente_paginas(*paginas):
    cliente = MagicMock()
    respostas = [_resp(p) for p in paginas]
    cliente.table.return_value.select.return_value.range.return_value.execute.side_effect = respostas
    return cliente


_ADMIN = "admin@exemplo.com"
_NAO_ADMIN = "intruso@exemplo.com"


# ---------------------------------------------------------------------
# Autorização - a parte inegociável: protege a CONSULTA, não só a tela.
# ---------------------------------------------------------------------

def test_email_nao_admin_recebe_none_sem_nenhuma_query(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    cliente = MagicMock()

    resultado = admin_usuarios.obter_usuarios_admin(_NAO_ADMIN, cliente=cliente)

    assert resultado is None
    cliente.table.assert_not_called()  # nunca chega a consultar o banco


def test_email_admin_autorizado_consulta_normalmente(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    cliente = _cliente_paginas([
        {"sub": "s1", "email": "a@exemplo.com", "preferencias": {}, "created_at": None, "last_seen_at": None},
    ])
    resultado = admin_usuarios.obter_usuarios_admin(_ADMIN, cliente=cliente)
    assert resultado is not None
    assert len(resultado) == 1


def test_comparacao_de_admin_ignora_caixa(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: ["Admin@Exemplo.com"])
    cliente = _cliente_paginas([])
    resultado = admin_usuarios.obter_usuarios_admin("admin@exemplo.com", cliente=cliente)
    assert resultado == []


def test_email_vazio_nunca_e_admin(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    cliente = MagicMock()
    assert admin_usuarios.obter_usuarios_admin("", cliente=cliente) is None
    assert admin_usuarios.obter_usuarios_admin(None, cliente=cliente) is None
    cliente.table.assert_not_called()


# ---------------------------------------------------------------------
# Status de inscrição normalizado a partir de `preferencias`
# ---------------------------------------------------------------------

def test_status_inscricao_inscrito_recusou_nao_respondeu(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    cliente = _cliente_paginas([
        {"sub": "s1", "email": "inscrito@exemplo.com", "preferencias": {"morning_call_email_ativo": True}, "created_at": None, "last_seen_at": None},
        {"sub": "s2", "email": "recusou@exemplo.com", "preferencias": {"morning_call_email_ativo": False, "morning_call_email_perguntado": True}, "created_at": None, "last_seen_at": None},
        {"sub": "s3", "email": "ninguem@exemplo.com", "preferencias": {}, "created_at": None, "last_seen_at": None},
    ])
    resultado = admin_usuarios.obter_usuarios_admin(_ADMIN, cliente=cliente)
    status_por_email = {u["email"]: u["status_inscricao"] for u in resultado}
    assert status_por_email["inscrito@exemplo.com"] == "inscrito"
    assert status_por_email["recusou@exemplo.com"] == "recusou"
    assert status_por_email["ninguem@exemplo.com"] == "nao_respondeu"


# ---------------------------------------------------------------------
# Indisponibilidade / falha - nunca inventa dado, nunca derruba o app
# ---------------------------------------------------------------------

def test_sem_cliente_supabase_retorna_none(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    with patch.object(admin_usuarios, "obter_cliente", return_value=None):
        assert admin_usuarios.obter_usuarios_admin(_ADMIN) is None


def test_falha_na_consulta_retorna_none_sem_lancar_excecao(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    cliente = MagicMock()
    cliente.table.side_effect = RuntimeError("Supabase fora do ar")
    assert admin_usuarios.obter_usuarios_admin(_ADMIN, cliente=cliente) is None


def test_tabela_vazia_retorna_lista_vazia_nao_none(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    cliente = _cliente_paginas([])
    assert admin_usuarios.obter_usuarios_admin(_ADMIN, cliente=cliente) == []


# ---------------------------------------------------------------------
# Paginação (mesmo mecanismo de listar_assinantes_morning_call)
# ---------------------------------------------------------------------

def test_paginacao_percorre_todas_as_paginas(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    tamanho_pagina = admin_usuarios._TAMANHO_PAGINA_USUARIOS
    pagina_cheia = [
        {"sub": f"s{i}", "email": f"user{i}@exemplo.com", "preferencias": {}, "created_at": None, "last_seen_at": None}
        for i in range(tamanho_pagina)
    ]
    pagina_final = [
        {"sub": "s-ultimo", "email": "ultimo@exemplo.com", "preferencias": {}, "created_at": None, "last_seen_at": None},
    ]
    cliente = _cliente_paginas(pagina_cheia, pagina_final)

    resultado = admin_usuarios.obter_usuarios_admin(_ADMIN, cliente=cliente)

    assert len(resultado) == tamanho_pagina + 1
    assert cliente.table.return_value.select.return_value.range.return_value.execute.call_count == 2


# ---------------------------------------------------------------------
# diagnosticar_usuarios_admin - causa REAL de obter_usuarios_admin==None
# (achado real 2026-10-19: a UI mostrava "Supabase indisponível" pra
# qualquer falha, inclusive erro de schema/coluna ausente - ver
# docstring de diagnosticar_usuarios_admin).
# ---------------------------------------------------------------------

def test_diagnostico_nao_admin_nao_consulta_banco(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    cliente = MagicMock()

    diagnostico = admin_usuarios.diagnosticar_usuarios_admin(_NAO_ADMIN, cliente=cliente)

    assert diagnostico == {"ok": False, "etapa": "NAO_ADMIN", "detalhe": "e-mail fora da lista de administradores"}
    cliente.table.assert_not_called()


def test_diagnostico_sem_cliente_identifica_credencial_ausente(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    with patch.object(admin_usuarios, "obter_cliente", return_value=None):
        diagnostico = admin_usuarios.diagnosticar_usuarios_admin(_ADMIN)
    assert diagnostico["ok"] is False
    assert diagnostico["etapa"] == "SEM_CREDENCIAL"


def test_diagnostico_expoe_o_erro_real_do_postgres_nao_so_generico(monkeypatch):
    """O caso real que motivou isto: coluna ausente por migração de
    sql/schema.sql nunca aplicada em produção - erro real do Postgres,
    não 'Supabase caiu'. O admin precisa ver ESSE texto, não um genérico."""
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    cliente = MagicMock()
    erro_real = Exception('column user_prefs.last_seen_at does not exist')
    cliente.table.return_value.select.return_value.limit.return_value.execute.side_effect = erro_real

    diagnostico = admin_usuarios.diagnosticar_usuarios_admin(_ADMIN, cliente=cliente)

    assert diagnostico["ok"] is False
    assert diagnostico["etapa"] == "CONSULTA"
    assert "last_seen_at" in diagnostico["detalhe"]


def test_diagnostico_ok_quando_consulta_minima_funciona(monkeypatch):
    monkeypatch.setattr(admin_usuarios.config, "obter_emails_admin", lambda: [_ADMIN])
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.limit.return_value.execute.return_value = _resp([])

    diagnostico = admin_usuarios.diagnosticar_usuarios_admin(_ADMIN, cliente=cliente)

    assert diagnostico == {"ok": True, "etapa": "", "detalhe": ""}
