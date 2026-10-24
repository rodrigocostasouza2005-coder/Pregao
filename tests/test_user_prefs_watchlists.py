# -*- coding: utf-8 -*-
"""Testes de data/user_prefs.py:uniao_watchlists_todos_usuarios - reforma
estrutural do CALENDARIO (2026-10-24): universo do coletor de datas de
resultado deixa de ser fixo (config.IBOVESPA_SETORES) e passa a incluir a
UNIAO real de todas as watchlists de todos os usuarios, lida direto do
Supabase (mesma paginacao/distincao None-vs-vazio de
listar_assinantes_morning_call, ver test_user_prefs_assinantes.py)."""
from unittest.mock import MagicMock, patch

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


def test_uniao_de_watchlists_de_usuarios_diferentes_inclui_ticker_fora_do_ibovespa():
    cliente = _cliente_paginas([
        {"preferencias": {"watchlist": ["PETR4", "VALE3"]}},
        {"preferencias": {"watchlist": ["MELI34", "AAPL34"]}},  # BDRs, fora do Ibovespa
    ])
    uniao = user_prefs.uniao_watchlists_todos_usuarios(cliente)
    assert uniao == {"PETR4", "VALE3", "MELI34", "AAPL34"}


def test_dedupe_ticker_repetido_entre_watchlists_minusculo_maiusculo():
    cliente = _cliente_paginas([
        {"preferencias": {"watchlist": ["petr4", "VALE3"]}},
        {"preferencias": {"watchlist": ["PETR4", "vale3", "WEGE3"]}},
    ])
    uniao = user_prefs.uniao_watchlists_todos_usuarios(cliente)
    assert uniao == {"PETR4", "VALE3", "WEGE3"}


def test_watchlist_ausente_ou_vazia_nao_quebra():
    cliente = _cliente_paginas([
        {"preferencias": {}},
        {"preferencias": {"watchlist": []}},
        {"preferencias": None},
    ])
    assert user_prefs.uniao_watchlists_todos_usuarios(cliente) == set()


def test_nenhum_usuario_cadastrado_retorna_set_vazio_nao_none():
    """set() vazio = 'ninguem tem watchlist ainda', estado real e
    legitimo - distinto de None ('nao deu pra saber', Supabase fora do
    ar)."""
    cliente = _cliente_paginas([])
    assert user_prefs.uniao_watchlists_todos_usuarios(cliente) == set()


def test_paginacao_percorre_todas_as_paginas_acima_de_500_registros():
    tamanho_pagina = user_prefs._TAMANHO_PAGINA_ASSINANTES
    pagina_cheia = [{"preferencias": {"watchlist": [f"T{i}3"]}} for i in range(tamanho_pagina)]
    pagina_final = [{"preferencias": {"watchlist": ["ULTM3"]}}]
    cliente = _cliente_paginas(pagina_cheia, pagina_final)

    uniao = user_prefs.uniao_watchlists_todos_usuarios(cliente)

    assert len(uniao) == tamanho_pagina + 1
    assert "ULTM3" in uniao
    assert cliente.table.return_value.select.return_value.range.return_value.execute.call_count == 2


def test_supabase_indisponivel_retorna_none_nunca_confundido_com_vazio():
    """None (nao set()) quando obter_cliente() nao acha credenciais -
    mesma distincao de listar_assinantes_morning_call: quem chama
    (universo_calendario) NUNCA deve tratar isso como 'ninguem tem
    watchlist', senao o universo do calendario fica incompleto sem
    avisar."""
    with patch.object(user_prefs, "obter_cliente", return_value=None):
        assert user_prefs.uniao_watchlists_todos_usuarios() is None
        assert user_prefs.uniao_watchlists_todos_usuarios(None) is None


def test_falha_na_consulta_retorna_none_sem_lancar_excecao():
    cliente = MagicMock()
    cliente.table.side_effect = RuntimeError("Supabase fora do ar")
    assert user_prefs.uniao_watchlists_todos_usuarios(cliente) is None
