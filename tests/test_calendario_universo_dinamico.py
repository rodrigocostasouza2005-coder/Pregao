# -*- coding: utf-8 -*-
"""Fase 1 da reforma estrutural do CALENDARIO (universo dinamico) - ver
plano aprovado em C:\\Users\\Dell\\.claude\\plans\\eventual-hatching-pancake.md.
Testa:

- data/cvm.py:tickers_com_cnpj_cvm() - filtro de formato (rejeita linha
  malformada do FCA, ex. "NÃO HÁ").
- data/user_prefs.py:uniao_watchlists_todos_usuarios() - uniao de TODAS
  as watchlists, paginacao, None (Supabase indisponivel) vs set() vazio.
- data/eventos.py:universo_calendario()/universo_calendario_priorizado() -
  uniao das 3 fontes, dedupe, BDR fora dos aliases curados mas presente
  numa watchlist, fallback quando uma fonte falha, watchlist sempre
  primeiro na ordem priorizada.
- data/eventos.py:calcular_calendario_cacheado - nunca paga rede por
  nome em lote grande (protege a UI de bloquear com o universo TODOS).
"""
from datetime import date
from unittest.mock import MagicMock, patch

import config
import data.cvm as cvm_mod
import data.eventos as eventos_mod
import data.user_prefs as user_prefs_mod
from data.cvm import tickers_com_cnpj_cvm
from data.eventos import (
    STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM,
    calcular_calendario_cacheado, universo_calendario, universo_calendario_priorizado,
)
from data.user_prefs import uniao_watchlists_todos_usuarios


# ============================================================
# tickers_com_cnpj_cvm - filtro de formato
# ============================================================

def test_tickers_com_cnpj_cvm_rejeita_linha_malformada_do_fca():
    """Achado real do diagnostico: o FCA tem pelo menos 1 linha com
    "NÃO HÁ" no lugar do codigo de negociacao."""
    with patch.object(cvm_mod, "_mapa_ticker_cnpj",
                       return_value={"PETR4": "123", "VALE3": "456", "NÃO HÁ": "789", "": "000"}):
        tickers = tickers_com_cnpj_cvm()
    assert tickers == {"PETR4", "VALE3"}


def test_tickers_com_cnpj_cvm_aceita_unit_e_bdr_classe_11_32_34():
    with patch.object(cvm_mod, "_mapa_ticker_cnpj",
                       return_value={"KLBN11": "1", "ABCD33": "2", "WXYZ34": "3", "LIXO": "4"}):
        tickers = tickers_com_cnpj_cvm()
    assert tickers == {"KLBN11", "ABCD33", "WXYZ34"}


def test_tickers_com_cnpj_cvm_vazio_quando_cvm_indisponivel():
    """CVM fora do ar -> _mapa_ticker_cnpj() ja degrada pro ultimo valor
    valido ou {} (comportamento existente, nao alterado aqui) -
    tickers_com_cnpj_cvm so' filtra o que vier, nunca fabrica ticker."""
    with patch.object(cvm_mod, "_mapa_ticker_cnpj", return_value={}):
        assert tickers_com_cnpj_cvm() == set()


# ============================================================
# uniao_watchlists_todos_usuarios
# ============================================================

def _resp(linhas):
    resp = MagicMock()
    resp.data = linhas
    return resp


def _cliente_paginas(*paginas):
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.range.return_value.execute.side_effect = [
        _resp(p) for p in paginas
    ]
    return cliente


def test_uniao_watchlists_inclui_todas_as_watchlists_de_todos_os_usuarios():
    cliente = _cliente_paginas([
        {"preferencias": {"watchlist": ["PETR4", "VALE3"]}},
        {"preferencias": {"watchlist": ["ITUB4"]}},
    ])
    assert uniao_watchlists_todos_usuarios(cliente) == {"PETR4", "VALE3", "ITUB4"}


def test_uniao_watchlists_dedupe_entre_usuarios_diferentes():
    cliente = _cliente_paginas([
        {"preferencias": {"watchlist": ["PETR4"]}},
        {"preferencias": {"watchlist": ["petr4", "PETR4"]}},
    ])
    assert uniao_watchlists_todos_usuarios(cliente) == {"PETR4"}


def test_uniao_watchlists_usuario_sem_watchlist_nao_quebra():
    cliente = _cliente_paginas([
        {"preferencias": {}},
        {"preferencias": {"watchlist": ["VALE3"]}},
    ])
    assert uniao_watchlists_todos_usuarios(cliente) == {"VALE3"}


def test_uniao_watchlists_paginacao_acima_de_500():
    tamanho_pagina = user_prefs_mod._TAMANHO_PAGINA_ASSINANTES  # 500
    pagina_cheia = [{"preferencias": {"watchlist": [f"T{i}3"]}} for i in range(tamanho_pagina)]
    pagina_final = [{"preferencias": {"watchlist": ["ULTIMO3"]}}]
    cliente = _cliente_paginas(pagina_cheia, pagina_final)

    tickers = uniao_watchlists_todos_usuarios(cliente)

    assert len(tickers) == tamanho_pagina + 1
    assert "ULTIMO3" in tickers
    assert cliente.table.return_value.select.return_value.range.return_value.execute.call_count == 2


def test_uniao_watchlists_supabase_indisponivel_e_none_nao_set_vazio():
    """None (Supabase fora do ar) e' DIFERENTE de set() (ninguem tem
    watchlist) - quem chama (universo_calendario) nao pode confundir os
    dois, senao o universo encolhe silenciosamente."""
    with patch.object(user_prefs_mod, "obter_cliente", return_value=None):
        assert uniao_watchlists_todos_usuarios() is None


def test_uniao_watchlists_ninguem_cadastrou_e_set_vazio_nao_none():
    cliente = _cliente_paginas([])
    assert uniao_watchlists_todos_usuarios(cliente) == set()


def test_uniao_watchlists_erro_de_rede_degrada_pra_none_nunca_lanca():
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.range.return_value.execute.side_effect = RuntimeError("timeout")
    assert uniao_watchlists_todos_usuarios(cliente) is None


# ============================================================
# universo_calendario / universo_calendario_priorizado
# ============================================================

def test_universo_calendario_uniao_das_3_fontes_sem_duplicar():
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"PETR4", "VALE3"}), \
         patch.object(config, "TICKER_ALIASES", {"AAPL34": "x"}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value={"PETR4", "ITUB4"}):
        universo = universo_calendario()
    assert set(universo) == {"PETR4", "VALE3", "AAPL34", "ITUB4"}
    assert len(universo) == len(set(universo))  # sem duplicata


def test_universo_calendario_bdr_fora_dos_aliases_mas_na_watchlist_entra():
    """100% das watchlists: um BDR que o usuario cadastrou mas que nao
    esta' na lista curada de config.TICKER_ALIASES ainda entra no
    universo - achado real do diagnostico (ROXO34/MELI34/etc)."""
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value=set()), \
         patch.object(config, "TICKER_ALIASES", {}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value={"ROXO34"}):
        universo = universo_calendario()
    assert "ROXO34" in universo


def test_universo_calendario_watchlists_indisponivel_nao_encolhe_silenciosamente():
    """Supabase fora do ar (uniao_watchlists_todos_usuarios=None) cai
    so' pros 2 conjuntos estaticos (CVM+BDRs) - continua bem maior que
    o universo fixo antigo, nunca um universo vazio por 1 fonte falhar."""
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"PETR4", "VALE3"}), \
         patch.object(config, "TICKER_ALIASES", {"AAPL34": "x"}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value=None):
        universo = universo_calendario()
    assert set(universo) == {"PETR4", "VALE3", "AAPL34"}


def test_universo_calendario_cvm_indisponivel_fallback_seguro():
    """CVM fora do ar (tickers_com_cnpj_cvm=set(), ja' o comportamento
    existente de _mapa_ticker_cnpj numa falha total) - sobra BDRs e
    watchlists, nunca um universo vazio por 1 fonte so'."""
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value=set()), \
         patch.object(config, "TICKER_ALIASES", {"AAPL34": "x"}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value={"PETR4"}):
        universo = universo_calendario()
    assert set(universo) == {"AAPL34", "PETR4"}


def test_universo_calendario_priorizado_watchlist_sempre_primeiro():
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"ZZZZ3", "AAAA3"}), \
         patch.object(config, "TICKER_ALIASES", {}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value={"PETR4", "VALE3"}):
        watchlist, resto = universo_calendario_priorizado()
        universo = universo_calendario()
    assert watchlist == ["PETR4", "VALE3"]
    assert resto == ["AAAA3", "ZZZZ3"]
    assert universo == ["PETR4", "VALE3", "AAAA3", "ZZZZ3"]  # watchlist antes do resto, sempre
    assert "PETR4" not in resto and "VALE3" not in resto  # sem sobreposicao


# ============================================================
# calcular_calendario_cacheado - protecao de desempenho (nome_via_rede)
# ============================================================

def test_cacheado_lote_pequeno_nao_coberto_mantem_nome_via_rede():
    """Watchlist/setor reais (ate' _LIMITE_NOME_VIA_REDE_UI) continuam
    com o comportamento de sempre - nome bonito via rede quando
    necessario, intocado pela reforma do universo."""
    chamadas = []

    def _fake(tickers, hoje=None, nome_via_rede=True):
        chamadas.append(nome_via_rede)
        return []

    with patch.object(eventos_mod, "obter_snapshot_calendario", return_value={"eventos": []}), \
         patch.object(eventos_mod, "calcular_calendario", side_effect=_fake):
        calcular_calendario_cacheado(["PETR4", "VALE3"])
    assert chamadas == [True]


def test_cacheado_lote_grande_nao_coberto_desativa_nome_via_rede():
    """So' um lote GRANDE (ex: filtro TODOS com ~500 tickers, maioria
    ainda fora do snapshot) desativa a busca de nome via rede - protege
    a UI de bloquear por minutos. Testa o limite real do codigo."""
    limite = eventos_mod._LIMITE_NOME_VIA_REDE_UI
    tickers_grande = [f"T{i}3" for i in range(limite + 1)]
    chamadas = []

    def _fake(tickers, hoje=None, nome_via_rede=True):
        chamadas.append(nome_via_rede)
        return []

    with patch.object(eventos_mod, "obter_snapshot_calendario", return_value={"eventos": []}), \
         patch.object(eventos_mod, "calcular_calendario", side_effect=_fake):
        calcular_calendario_cacheado(tickers_grande)
    assert chamadas == [False]


def test_cacheado_sem_snapshot_nenhum_e_lote_grande_tambem_desativa_rede():
    limite = eventos_mod._LIMITE_NOME_VIA_REDE_UI
    tickers_grande = [f"T{i}3" for i in range(limite + 1)]
    chamadas = []

    def _fake(tickers, hoje=None, nome_via_rede=True):
        chamadas.append(nome_via_rede)
        return []

    with patch.object(eventos_mod, "obter_snapshot_calendario", return_value=None), \
         patch.object(eventos_mod, "calcular_calendario", side_effect=_fake):
        calcular_calendario_cacheado(tickers_grande)
    assert chamadas == [False]


def test_nome_via_rede_false_nunca_chama_yfinance_e_usa_o_proprio_codigo():
    """_nome_empresa(nome_via_rede=False) pra um ticker sem nome curado
    nunca chama obter_nome_yf - mostra o proprio codigo, nunca inventa
    um nome nem paga rede."""
    with patch.object(eventos_mod, "obter_nome_yf", side_effect=AssertionError("nao deveria chamar rede")):
        nome = eventos_mod._nome_empresa("ZZZZ99", nome_via_rede=False)
    assert nome == "ZZZZ99"


# ============================================================
# Hierarquia de confiabilidade preservada (CONFIRMADO > ESTIMADO > PRAZO_CVM)
# ============================================================

def test_hierarquia_confirmado_preservada_com_nome_via_rede_false():
    """O novo parametro nome_via_rede so' afeta o NOME de exibicao -
    status/data/fonte do evento (CONFIRMADO/ESTIMADO/PRAZO_CVM) nunca
    mudam, com ou sem busca de nome via rede."""
    persistido = {
        "data_evento": "2026-12-15", "status": STATUS_CONFIRMADO,
        "fonte": "RI da empresa", "url_fonte": "https://ri.exemplo.com",
    }
    with patch.object(eventos_mod, "periodo_pendente", return_value=(2026, 4)), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=persistido), \
         patch.object(eventos_mod, "obter_nome_yf", side_effect=AssertionError("nao deveria chamar rede")):
        evento = eventos_mod.calcular_proximo_resultado("ZZZZ99", hoje=date(2026, 10, 1), nome_via_rede=False)
    assert evento["status"] == STATUS_CONFIRMADO
    assert evento["data"] == date(2026, 12, 15)
    assert evento["empresa"] == "ZZZZ99"  # sem nome curado, nunca inventado


def test_nenhuma_data_fabricada_para_ticker_sem_cnpj_mesmo_com_universo_novo():
    """Mesmo caso real ja' testado em test_7b (sem CNPJ -> sem evento),
    confirmado tambem com nome_via_rede=False (caminho do universo
    grande) - nunca fabrica PRAZO_CVM pra ticker sem evidencia
    cadastral valida."""
    with patch.object(eventos_mod, "obter_cnpj", return_value=None), \
         patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", side_effect=AssertionError("nao deveria chamar rede")), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = eventos_mod.calcular_proximo_resultado("SEMCNPJ9", hoje=date(2026, 10, 1), nome_via_rede=False)
    assert evento is None
