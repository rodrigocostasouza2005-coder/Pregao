# -*- coding: utf-8 -*-
"""Testes de data/eventos.py:universo_calendario - reforma estrutural do
CALENDARIO (2026-10-24): universo do coletor de datas de resultado deixa
de ser fixo (config.IBOVESPA_SETORES, 84 tickers) e passa a ser a UNIAO
de (1) todo ticker com CNPJ no cadastro FCA da CVM (data.cvm.
tickers_com_cnpj_cvm), (2) BDRs curados (config.TICKER_ALIASES) e (3) a
uniao de todas as watchlists reais (data.user_prefs.
uniao_watchlists_todos_usuarios). Mocka as 3 fontes diretamente - nunca
faz rede/Supabase real."""
from datetime import date
from unittest.mock import patch

import data.eventos as eventos_mod


def _limpar_cache_universo():
    eventos_mod.universo_calendario.clear()


def test_uniao_das_3_fontes_inclui_watchlist_fora_do_ibovespa_e_cvm():
    _limpar_cache_universo()
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"PETR4", "VALE3"}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value={"MELI34", "VALE3"}), \
         patch.object(eventos_mod.config, "TICKER_ALIASES", {"AAPL34": ["AAPL"]}):
        universo = set(eventos_mod.universo_calendario())
    assert universo == {"PETR4", "VALE3", "MELI34", "AAPL34"}


def test_dedupe_ticker_presente_em_mais_de_1_fonte_aparece_1x():
    _limpar_cache_universo()
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"WEGE3"}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value={"WEGE3", "wege3"}), \
         patch.object(eventos_mod.config, "TICKER_ALIASES", {}):
        universo = eventos_mod.universo_calendario()
    assert universo.count("WEGE3") == 1
    assert len(universo) == len(set(universo))  # nenhuma duplicata na lista final


def test_watchlists_indisponivel_nao_reduz_universo_a_vazio_nem_bloqueia_cvm():
    """Supabase fora do ar (uniao_watchlists_todos_usuarios=None) nao
    pode: (a) lancar excecao, (b) esvaziar o universo, (c) impedir que
    CVM/aliases (fontes que respoderam) sejam usadas."""
    _limpar_cache_universo()
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"PETR4", "VALE3"}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value=None), \
         patch.object(eventos_mod.config, "TICKER_ALIASES", {"AAPL34": ["AAPL"]}):
        universo = set(eventos_mod.universo_calendario())
    assert universo == {"PETR4", "VALE3", "AAPL34"}


def test_cvm_falha_nao_reduz_universo_a_vazio_nem_bloqueia_watchlists():
    """tickers_com_cnpj_cvm ja' e' resiliente por construcao (herda o
    fallback de _mapa_ticker_cnpj) - mesmo que ela degrade pra set()
    vazio numa falha total nunca-teve-sucesso, watchlists/aliases
    continuam compondo o universo."""
    _limpar_cache_universo()
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value=set()), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value={"PETR4"}), \
         patch.object(eventos_mod.config, "TICKER_ALIASES", {"AAPL34": ["AAPL"]}):
        universo = set(eventos_mod.universo_calendario())
    assert universo == {"PETR4", "AAPL34"}


def test_cada_fonte_e_consultada_exatamente_1x_por_chamada_sem_custo_por_ticker():
    """universo_calendario() precisa ser 1 composicao, nao 1 chamada por
    ticker - sem isso, escalar de 84 pra 500+ tickers multiplicaria
    consultas ao Supabase/CVM por ticker em vez de 1x no total."""
    _limpar_cache_universo()
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={f"T{i}3" for i in range(50)}) as m_cvm, \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value=set()) as m_wl:
        eventos_mod.universo_calendario()
    assert m_cvm.call_count == 1
    assert m_wl.call_count == 1


def test_bdr_de_watchlist_sem_cnpj_mapeado_nunca_fabrica_prazo_cvm():
    """Integracao com o fallback ja existente (data/eventos.py:
    calcular_proximo_resultado/periodo_pendente): um BDR que so' entrou
    no universo porque algum usuario tem na watchlist (nao esta em
    tickers_com_cnpj_cvm nem em TICKER_ALIASES) nunca tem CNPJ na CVM -
    continua retornando None (nunca um PRAZO_CVM inventado), mesma
    garantia do test_7b_ticker_sem_cnpj_mapeado_nao_fabrica_prazo_cvm
    (tests/test_eventos.py), agora alimentada pelo universo novo."""
    _limpar_cache_universo()
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"PETR4"}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value={"ROXO34"}), \
         patch.object(eventos_mod.config, "TICKER_ALIASES", {}):
        universo = eventos_mod.universo_calendario()
    assert "ROXO34" in universo

    with patch.object(eventos_mod, "obter_cnpj", return_value=None), \
         patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="BDR ESTRANGEIRO (ROXO34)"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = eventos_mod.calcular_proximo_resultado("ROXO34", hoje=date(2026, 10, 1))
    assert evento is None


def test_resultado_e_lista_cacheada_mesma_chamada_2x_nao_bate_fontes_de_novo():
    """coletor_local.py chama universo_calendario() 2x por execucao
    (coleta de eventos + snapshot) - @st.cache_data(ttl=300) evita 2
    leituras completas de user_prefs/CVM por rodada."""
    _limpar_cache_universo()
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"PETR4"}) as m_cvm, \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value=set()):
        eventos_mod.universo_calendario()
        eventos_mod.universo_calendario()
    assert m_cvm.call_count == 1


# ============================================================
# universo_calendario_priorizado - priorizacao watchlist-primeiro
# (2026-10-25): watchlist nunca rotaciona junto com o resto do
# universo em coletor_local.py (ver _universo_rotativo la').
# ============================================================

def _limpar_cache_priorizado():
    eventos_mod.universo_calendario_priorizado.clear()


def test_priorizado_divide_watchlist_e_resto_sem_sobreposicao():
    _limpar_cache_priorizado()
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"PETR4", "VALE3", "ITUB4"}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value={"VALE3", "ROXO34"}), \
         patch.object(eventos_mod.config, "TICKER_ALIASES", {}):
        watchlist, resto = eventos_mod.universo_calendario_priorizado()
    assert set(watchlist) == {"VALE3", "ROXO34"}
    assert set(resto) == {"PETR4", "ITUB4"}  # VALE3 so' na watchlist, nunca duplicado no resto
    assert not (set(watchlist) & set(resto))


def test_priorizado_e_universo_calendario_descrevem_o_mesmo_conjunto():
    _limpar_cache_universo()
    _limpar_cache_priorizado()
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"PETR4", "VALE3"}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value={"ROXO34"}), \
         patch.object(eventos_mod.config, "TICKER_ALIASES", {"AAPL34": ["AAPL"]}):
        watchlist, resto = eventos_mod.universo_calendario_priorizado()
        universo = eventos_mod.universo_calendario()
    assert set(watchlist) | set(resto) == set(universo)


def test_priorizado_watchlists_indisponivel_degrada_pro_resto_sem_esvaziar():
    _limpar_cache_priorizado()
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"PETR4", "VALE3"}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value=None), \
         patch.object(eventos_mod.config, "TICKER_ALIASES", {}):
        watchlist, resto = eventos_mod.universo_calendario_priorizado()
    assert watchlist == []
    assert set(resto) == {"PETR4", "VALE3"}  # nunca vazio por 1 fonte indisponivel


def test_priorizado_dedupe_ticker_em_watchlist_e_cvm_fica_so_na_watchlist():
    _limpar_cache_priorizado()
    with patch.object(eventos_mod, "tickers_com_cnpj_cvm", return_value={"WEGE3", "wege3"}), \
         patch.object(eventos_mod, "uniao_watchlists_todos_usuarios", return_value={"WEGE3"}), \
         patch.object(eventos_mod.config, "TICKER_ALIASES", {}):
        watchlist, resto = eventos_mod.universo_calendario_priorizado()
    assert watchlist == ["WEGE3"]
    assert "WEGE3" not in resto  # sem duplicata entre as 2 listas


# ============================================================
# nome_via_rede - protecao de desempenho do filtro TODOS
# (achado real durante a revisao da reforma: calcular_calendario_
# cacheado pagava yfinance por ticker nao-coberto pelo snapshot, sem
# limite - com o universo de ~500 tickers, isso bloquearia a UI).
# ============================================================

def test_cacheado_lote_pequeno_nao_coberto_mantem_nome_via_rede():
    """Watchlist/setor reais (ate' _LIMITE_NOME_VIA_REDE_UI) continuam
    com o comportamento de sempre - nome bonito via rede quando
    necessario."""
    chamadas = []

    def _fake(tickers, hoje=None, nome_via_rede=True):
        chamadas.append(nome_via_rede)
        return []

    with patch.object(eventos_mod, "obter_snapshot_calendario", return_value={"eventos": []}), \
         patch.object(eventos_mod, "calcular_calendario", side_effect=_fake):
        eventos_mod.calcular_calendario_cacheado(["PETR4", "VALE3"])
    assert chamadas == [True]


def test_cacheado_lote_grande_nao_coberto_desativa_nome_via_rede():
    """So' um lote GRANDE (filtro TODOS, maioria fora do snapshot
    ainda) desativa a busca de nome via rede - protege a UI de
    bloquear por minutos."""
    limite = eventos_mod._LIMITE_NOME_VIA_REDE_UI
    tickers_grande = [f"T{i}3" for i in range(limite + 1)]
    chamadas = []

    def _fake(tickers, hoje=None, nome_via_rede=True):
        chamadas.append(nome_via_rede)
        return []

    with patch.object(eventos_mod, "obter_snapshot_calendario", return_value={"eventos": []}), \
         patch.object(eventos_mod, "calcular_calendario", side_effect=_fake):
        eventos_mod.calcular_calendario_cacheado(tickers_grande)
    assert chamadas == [False]


def test_nome_via_rede_false_nunca_chama_yfinance():
    with patch.object(eventos_mod, "obter_nome_yf", side_effect=AssertionError("nao deveria chamar rede")):
        nome = eventos_mod._nome_empresa("ZZZZ99", nome_via_rede=False)
    assert nome == "ZZZZ99"  # proprio codigo, nunca inventado
