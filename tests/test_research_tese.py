# -*- coding: utf-8 -*-
"""Testes do thesis tracker (data/research/tese.py, tabela
research_teses) - adaptacao do skill "thesis-tracker" do Market
Researcher oficial pro Supabase do projeto. Mocka o cliente Supabase com
um fake simples em memoria (insert/select/eq/order/limit) - nunca faz
chamada de rede real, mesmo padrao de tests/test_ia_cache.py e
tests/test_research_fase3.py.

Uso: pytest tests/test_research_tese.py"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.tese as tese_mod


class _TabelaFake:
    """Simula a tabela research_teses em memoria: insert() grava com
    registrado_em crescente (mais recente = inserido por ultimo);
    select().eq(...).eq(...).order(...).limit(n).execute() filtra por
    usuario_sub+ticker, ordena por registrado_em desc, corta em n -
    comportamento equivalente ao que o PostgREST real daria."""

    def __init__(self):
        self.linhas = []
        self._proximo_id = 1
        self._filtros = {}
        self._limite = None

    def insert(self, payload):
        linha = dict(payload)
        linha["id"] = self._proximo_id
        self._proximo_id += 1
        linha.setdefault("registrado_em", datetime.now(timezone.utc).isoformat())
        self.linhas.append(linha)
        self._ultimo_insert = [linha]
        return self

    def select(self, *_a, **_k):
        self._filtros = {}
        self._limite = None
        return self

    def eq(self, campo, valor):
        self._filtros[campo] = valor
        return self

    def order(self, *_a, **_k):
        self._ordenar = True
        return self

    def limit(self, n):
        self._limite = n
        return self

    def execute(self):
        resp = MagicMock()
        if hasattr(self, "_ultimo_insert") and not self._filtros:
            resp.data = self._ultimo_insert
            del self._ultimo_insert
            return resp
        filtradas = [
            l for l in self.linhas
            if all(l.get(k) == v for k, v in self._filtros.items())
        ]
        filtradas = sorted(filtradas, key=lambda l: l["registrado_em"], reverse=True)
        if self._limite is not None:
            filtradas = filtradas[: self._limite]
        resp.data = filtradas
        return resp


def _cliente_fake():
    cliente = MagicMock()
    tabela = _TabelaFake()
    cliente.table.return_value = tabela
    return cliente, tabela


def _registrar(cliente, **kwargs):
    with patch.object(tese_mod, "obter_cliente", return_value=cliente):
        return tese_mod.registrar_versao(**kwargs)


def test_registrar_versao_grava_e_retorna_a_linha():
    cliente, _ = _cliente_fake()
    linha = _registrar(
        cliente, usuario_sub="user-1", ticker="PETR4", tese="Long PETR4 - dividendos",
        premissas=["Dividend yield alto"], riscos=["Preço do petróleo"],
        catalisadores=["Resultado trimestral"], conviccao="ALTA",
    )
    assert linha is not None
    assert linha["ticker"] == "PETR4"
    assert linha["conviccao"] == "ALTA"


def test_registrar_versao_tese_vazia_levanta_valueerror():
    cliente, _ = _cliente_fake()
    with pytest.raises(ValueError):
        _registrar(cliente, usuario_sub="user-1", ticker="PETR4", tese="   ")


def test_registrar_versao_conviccao_invalida_levanta_valueerror():
    cliente, _ = _cliente_fake()
    with pytest.raises(ValueError):
        _registrar(cliente, usuario_sub="user-1", ticker="PETR4", tese="Long", conviccao="SUPER_ALTA")


def test_registrar_versao_banco_fora_do_ar_retorna_none_sem_excecao():
    with patch.object(tese_mod, "obter_cliente", return_value=None):
        resultado = tese_mod.registrar_versao(usuario_sub="user-1", ticker="PETR4", tese="Long")
    assert resultado is None


def test_historico_e_append_only_nunca_sobrescreve():
    cliente, tabela = _cliente_fake()
    _registrar(cliente, usuario_sub="user-1", ticker="PETR4", tese="Versão 1", conviccao="BAIXA")
    tabela.linhas[-1]["registrado_em"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    _registrar(cliente, usuario_sub="user-1", ticker="PETR4", tese="Versão 2", conviccao="ALTA")

    with patch.object(tese_mod, "obter_cliente", return_value=cliente):
        historico = tese_mod.historico_tese("user-1", "PETR4")

    assert len(historico) == 2
    assert historico[0]["tese"] == "Versão 2"  # mais recente primeiro
    assert historico[1]["tese"] == "Versão 1"


def test_historico_isola_por_usuario():
    cliente, _ = _cliente_fake()
    _registrar(cliente, usuario_sub="user-1", ticker="PETR4", tese="Tese do user-1")
    _registrar(cliente, usuario_sub="user-2", ticker="PETR4", tese="Tese do user-2")

    with patch.object(tese_mod, "obter_cliente", return_value=cliente):
        historico_1 = tese_mod.historico_tese("user-1", "PETR4")
        historico_2 = tese_mod.historico_tese("user-2", "PETR4")

    assert len(historico_1) == 1 and historico_1[0]["tese"] == "Tese do user-1"
    assert len(historico_2) == 1 and historico_2[0]["tese"] == "Tese do user-2"


def test_tese_atual_e_a_versao_mais_recente():
    cliente, tabela = _cliente_fake()
    _registrar(cliente, usuario_sub="user-1", ticker="VALE3", tese="Versão antiga")
    tabela.linhas[-1]["registrado_em"] = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    _registrar(cliente, usuario_sub="user-1", ticker="VALE3", tese="Versão nova")

    with patch.object(tese_mod, "obter_cliente", return_value=cliente):
        atual = tese_mod.tese_atual("user-1", "VALE3")

    assert atual["tese"] == "Versão nova"


def test_tese_atual_none_quando_nunca_registrada():
    cliente, _ = _cliente_fake()
    with patch.object(tese_mod, "obter_cliente", return_value=cliente):
        assert tese_mod.tese_atual("user-1", "TICKER_SEM_TESE") is None


def test_scorecard_agrega_contagem_e_datas():
    cliente, tabela = _cliente_fake()
    _registrar(
        cliente, usuario_sub="user-1", ticker="ITUB4", tese="V1",
        premissas=["Premissa A"], riscos=["Risco A"], catalisadores=["Cat A"], conviccao="MEDIA",
    )
    tabela.linhas[-1]["registrado_em"] = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    _registrar(
        cliente, usuario_sub="user-1", ticker="ITUB4", tese="V2",
        premissas=["Premissa A", "Premissa B"], riscos=["Risco A"], catalisadores=["Cat A"], conviccao="ALTA",
    )

    with patch.object(tese_mod, "obter_cliente", return_value=cliente):
        sc = tese_mod.scorecard("user-1", "ITUB4")

    assert sc["n_versoes"] == 2
    assert sc["tese_atual"] == "V2"
    assert sc["conviccao"] == "ALTA"
    assert sc["premissas"] == ["Premissa A", "Premissa B"]


def test_scorecard_none_quando_nunca_registrada():
    cliente, _ = _cliente_fake()
    with patch.object(tese_mod, "obter_cliente", return_value=cliente):
        assert tese_mod.scorecard("user-1", "TICKER_SEM_TESE") is None


def test_posicao_watchlist_e_aceita():
    cliente, _ = _cliente_fake()
    linha = _registrar(cliente, usuario_sub="user-1", ticker="PETR4", tese="Observando", posicao="WATCHLIST")
    assert linha["posicao"] == "WATCHLIST"


def test_envio_duplicado_do_mesmo_conteudo_dentro_da_janela_nao_cria_versao_nova():
    """Duplo clique/reenvio de rede do MESMO formulario, sem nenhuma
    mudanca de conteudo, em seguida - nao deve virar uma 2a linha."""
    cliente, tabela = _cliente_fake()
    _registrar(
        cliente, usuario_sub="user-1", ticker="PETR4", tese="Long PETR4",
        premissas=["A"], riscos=["B"], catalisadores=["C"], conviccao="ALTA", posicao="LONG",
    )
    _registrar(
        cliente, usuario_sub="user-1", ticker="PETR4", tese="Long PETR4",
        premissas=["A"], riscos=["B"], catalisadores=["C"], conviccao="ALTA", posicao="LONG",
    )
    with patch.object(tese_mod, "obter_cliente", return_value=cliente):
        historico = tese_mod.historico_tese("user-1", "PETR4")
    assert len(historico) == 1


def test_reafirmacao_do_mesmo_conteudo_apos_a_janela_cria_versao_nova():
    """Mesmo conteudo, mas fora da janela de duplicata (ex: o usuario
    reabriu a tese dias depois e confirmou que nada mudou) - isso E' uma
    versao nova de verdade, nao uma duplicata de clique."""
    cliente, tabela = _cliente_fake()
    _registrar(
        cliente, usuario_sub="user-1", ticker="PETR4", tese="Long PETR4",
        premissas=["A"], riscos=["B"], catalisadores=["C"], conviccao="ALTA", posicao="LONG",
    )
    tabela.linhas[-1]["registrado_em"] = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    _registrar(
        cliente, usuario_sub="user-1", ticker="PETR4", tese="Long PETR4",
        premissas=["A"], riscos=["B"], catalisadores=["C"], conviccao="ALTA", posicao="LONG",
    )
    with patch.object(tese_mod, "obter_cliente", return_value=cliente):
        historico = tese_mod.historico_tese("user-1", "PETR4")
    assert len(historico) == 2


def test_ticker_sem_cadastro_conhecido_funciona_normalmente():
    """Tese e' dado pessoal do usuario, nao research editorial vinculado
    a uma fonte - nao existe (nem deveria existir) validacao contra um
    universo de tickers "reais" (mesmo principio que historico.py/
    research_itens ja seguem: casa/ticker sao strings livres)."""
    cliente, _ = _cliente_fake()
    linha = _registrar(cliente, usuario_sub="user-1", ticker="XXXX99", tese="Observando um ticker fora do radar")
    assert linha is not None
    assert linha["ticker"] == "XXXX99"


def test_todos_campos_opcionais_vazios_ou_none():
    cliente, _ = _cliente_fake()
    linha = _registrar(
        cliente, usuario_sub="user-1", ticker="PETR4", tese="Só a tese, sem mais nada",
        premissas=None, riscos=None, catalisadores=None, conviccao=None, posicao=None, preco_alvo_tese=None,
    )
    assert linha is not None
    assert linha["premissas"] == []
    assert linha["riscos"] == []
    assert linha["catalisadores"] == []
    assert linha["conviccao"] is None
    assert linha["posicao"] is None
    assert linha["preco_alvo_tese"] is None


def test_registro_aparece_no_historico_imediatamente_apos_salvar():
    """'Confirmar que o registro apareceu no histórico depois de salvo' -
    leitura logo em seguida ao INSERT (mesma chamada sincrona que a UI
    faz apos o rerun) precisa achar a versao nova."""
    cliente, _ = _cliente_fake()
    salvo = _registrar(cliente, usuario_sub="user-1", ticker="PETR4", tese="Tese registrada agora")
    with patch.object(tese_mod, "obter_cliente", return_value=cliente):
        atual = tese_mod.tese_atual("user-1", "PETR4")
        historico = tese_mod.historico_tese("user-1", "PETR4")
    assert atual is not None and atual["tese"] == "Tese registrada agora"
    assert len(historico) == 1 and historico[0]["id"] == salvo["id"]


def test_envio_duplicado_com_conteudo_diferente_nao_e_bloqueado():
    """So' bloqueia duplicata de CONTEUDO IDENTICO - uma edicao real,
    mesmo que enviada rapido em seguida, sempre gera versao nova."""
    cliente, _ = _cliente_fake()
    _registrar(cliente, usuario_sub="user-1", ticker="PETR4", tese="Long PETR4", conviccao="BAIXA")
    _registrar(cliente, usuario_sub="user-1", ticker="PETR4", tese="Long PETR4 - revisado", conviccao="ALTA")
    with patch.object(tese_mod, "obter_cliente", return_value=cliente):
        historico = tese_mod.historico_tese("user-1", "PETR4")
    assert len(historico) == 2
