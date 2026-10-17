# -*- coding: utf-8 -*-
"""Testes de data/user_prefs.py: filtro/dedupe de assinantes do Morning
Call (opt-in explícito) e persistência da preferência (round-trip no
Supabase) - ver missão "Morning Call: consentimento e destinatários".
"""
from unittest.mock import MagicMock

import data.user_prefs as user_prefs


def _resp(linhas):
    resp = MagicMock()
    resp.data = linhas
    return resp


def _cliente_paginas(*paginas):
    """Fake cliente Supabase: cada chamada .range(...).execute() devolve
    a próxima página da sequência `paginas` (lista de listas de linhas)."""
    cliente = MagicMock()
    respostas = [_resp(p) for p in paginas]
    cliente.table.return_value.select.return_value.range.return_value.execute.side_effect = respostas
    return cliente


# ---------------------------------------------------------------------
# email_valido
# ---------------------------------------------------------------------

def test_email_valido_aceita_formato_basico():
    assert user_prefs.email_valido("usuario@exemplo.com") is True


def test_email_valido_rejeita_vazio_none_e_sem_arroba():
    assert user_prefs.email_valido("") is False
    assert user_prefs.email_valido(None) is False
    assert user_prefs.email_valido("nao-e-email") is False


# ---------------------------------------------------------------------
# listar_assinantes_morning_call
# ---------------------------------------------------------------------

def test_usuario_sem_preferencia_ativada_nao_entra_na_lista():
    cliente = _cliente_paginas([
        {"email": "semopt-in@exemplo.com", "preferencias": {}},
    ])
    assert user_prefs.listar_assinantes_morning_call(cliente) == []


def test_usuario_com_preferencia_ativada_e_email_valido_entra_na_lista():
    cliente = _cliente_paginas([
        {"email": "Assinante@Exemplo.com", "preferencias": {"morning_call_email_ativo": True}},
    ])
    assert user_prefs.listar_assinantes_morning_call(cliente) == ["assinante@exemplo.com"]


def test_preferencia_ativada_mas_email_invalido_nao_entra_na_lista():
    cliente = _cliente_paginas([
        {"email": "nao-e-email", "preferencias": {"morning_call_email_ativo": True}},
    ])
    assert user_prefs.listar_assinantes_morning_call(cliente) == []


def test_preferencia_ativada_mas_email_ausente_nao_entra_na_lista():
    cliente = _cliente_paginas([
        {"email": None, "preferencias": {"morning_call_email_ativo": True}},
        {"email": "", "preferencias": {"morning_call_email_ativo": True}},
    ])
    assert user_prefs.listar_assinantes_morning_call(cliente) == []


def test_dedupe_de_email_repetido_entre_usuarios_diferentes():
    """Dois "sub" (contas Google) diferentes podem ter cadastrado o
    mesmo e-mail (ex: trocou de provedor OAuth) - o Resend nunca deve
    receber o mesmo endereço 2x na mesma execução."""
    cliente = _cliente_paginas([
        {"email": "duplicado@exemplo.com", "preferencias": {"morning_call_email_ativo": True}},
        {"email": "DUPLICADO@exemplo.com", "preferencias": {"morning_call_email_ativo": True}},
    ])
    assinantes = user_prefs.listar_assinantes_morning_call(cliente)
    assert assinantes == ["duplicado@exemplo.com"]


def test_paginacao_percorre_todas_as_paginas_ate_a_ultima_incompleta():
    tamanho_pagina = user_prefs._TAMANHO_PAGINA_ASSINANTES
    pagina_cheia = [
        {"email": f"user{i}@exemplo.com", "preferencias": {"morning_call_email_ativo": True}}
        for i in range(tamanho_pagina)
    ]
    pagina_final = [
        {"email": "ultimo@exemplo.com", "preferencias": {"morning_call_email_ativo": True}},
    ]
    cliente = _cliente_paginas(pagina_cheia, pagina_final)

    assinantes = user_prefs.listar_assinantes_morning_call(cliente)

    assert len(assinantes) == tamanho_pagina + 1
    assert "ultimo@exemplo.com" in assinantes
    assert cliente.table.return_value.select.return_value.range.return_value.execute.call_count == 2


def test_cliente_none_retorna_none_sem_lancar_excecao():
    """None (nao []) - Supabase indisponivel e' um estado DIFERENTE de
    "ninguem assinou ainda": quem chama (jobs/morning_call.py:executar)
    precisa poder distinguir os 2 pra nao reportar uma falha de infra
    como sucesso silencioso (ver tests/test_morning_call.py:
    test_executar_com_supabase_indisponivel_nao_mascara_falha_como_sucesso)."""
    assert user_prefs.listar_assinantes_morning_call(None) is None


def test_falha_na_consulta_retorna_none_sem_lancar_excecao():
    cliente = MagicMock()
    cliente.table.side_effect = RuntimeError("Supabase fora do ar")
    assert user_prefs.listar_assinantes_morning_call(cliente) is None


# ---------------------------------------------------------------------
# Persistência da preferência (toggle) - round-trip salvar/obter.
# ---------------------------------------------------------------------

def test_toggle_persiste_e_e_lido_de_volta_no_round_trip(monkeypatch):
    """Simula o par salvar_prefs()/obter_prefs() que app.py usa pro
    toggle inline de CONFIG: depois de salvar com
    morning_call_email_ativo=True, uma NOVA leitura (nova "sessão")
    precisa devolver True - persistência real, não só o retorno HTTP
    do upsert."""
    armazenamento = {}

    cliente = MagicMock()

    def _fake_upsert(registro):
        armazenamento[registro["sub"]] = registro
        execucao = MagicMock()
        execucao.execute.return_value = MagicMock()
        return execucao

    def _fake_select_chain(sub_buscado):
        linha = armazenamento.get(sub_buscado)
        resp = _resp([{"preferencias": linha["preferencias"]}] if linha else [])
        execucao = MagicMock()
        execucao.execute.return_value = resp
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

    ok = user_prefs.salvar_prefs("sub-123", "user@exemplo.com", {"morning_call_email_ativo": True})
    assert ok is True

    prefs_lidas, banco_ok = user_prefs.obter_prefs("sub-123")
    assert banco_ok is True
    assert prefs_lidas["morning_call_email_ativo"] is True


def test_toggle_default_e_desligado_para_usuario_novo_sem_registro():
    """Default global (config.PREFS_PADRAO) precisa ser False - sem
    opt-in explícito, usuário novo (ou sem Supabase) nunca é tratado
    como assinante."""
    from config import PREFS_PADRAO
    assert PREFS_PADRAO["morning_call_email_ativo"] is False
