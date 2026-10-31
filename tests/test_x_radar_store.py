# -*- coding: utf-8 -*-
"""Persistencia (data/x_radar/store.py) - cliente Supabase fake em
memoria (nenhuma chamada de rede real). Cobre: upsert por post_id
(dedup), post com classificacao falha NUNCA persistido como
'sem_relevancia', reprocessamento com versao nova historiza a linha
anterior, listar_sinais filtra corretamente, None quando banco fora
do ar (distinto de [] = sem sinal no filtro)."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent / "fixtures"))

import data.x_radar.store as store_mod
from x_radar_posts import SINAL_ANALISE_FUNDAMENTADA, SINAL_RUMOR


class _QueryFake:
    def __init__(self, tabela):
        self.tabela = tabela
        self._filtros = []
        self._limite = None
        self._selecionar_count = False

    def select(self, _campos, count=None):
        self._selecionar_count = count == "exact"
        return self

    def eq(self, campo, valor):
        self._filtros.append(("eq", campo, valor))
        return self

    def in_(self, campo, valores):
        self._filtros.append(("in", campo, valores))
        return self

    def gte(self, campo, valor):
        self._filtros.append(("gte", campo, valor))
        return self

    def order(self, campo, desc=False):
        self._filtros.append(("order", campo, desc))
        return self

    def limit(self, n):
        self._limite = n
        return self

    def _aplicar_filtros(self, linhas):
        for tipo, campo, valor in self._filtros:
            if tipo == "eq":
                linhas = [l for l in linhas if l.get(campo) == valor]
            elif tipo == "in":
                linhas = [l for l in linhas if l.get(campo) in valor]
            elif tipo == "gte":
                linhas = [l for l in linhas if (l.get(campo) or "") >= valor]
            elif tipo == "order":
                linhas = sorted(linhas, key=lambda l: l.get(campo) or "", reverse=valor)
        return linhas

    def execute(self):
        linhas = self._aplicar_filtros(list(self.tabela.linhas.values()))
        if self._limite:
            linhas = linhas[: self._limite]
        resp = _RespostaFake(linhas)
        if self._selecionar_count:
            resp.count = len(linhas)
        return resp

    def upsert(self, linha, on_conflict=None):
        self.tabela.linhas[linha[on_conflict]] = linha
        return _ExecutavelDireto(linha)

    def insert(self, linha):
        chave = f"hist-{len(self.tabela.linhas) + 1}"
        self.tabela.linhas[chave] = linha
        return _ExecutavelDireto(linha)


class _ExecutavelDireto:
    def __init__(self, linha):
        self._linha = linha

    def execute(self):
        return _RespostaFake([self._linha])


class _RespostaFake:
    def __init__(self, data):
        self.data = data
        self.count = None


class _TabelaFake:
    def __init__(self):
        self.linhas = {}


class _ClienteFake:
    def __init__(self):
        self.tabelas = {}

    def table(self, nome):
        return _QueryFake(self.tabelas.setdefault(nome, _TabelaFake()))


def _classificacao_ok(**overrides):
    base = {
        "ok": True, "categoria": "opiniao_analista", "ticker": "PETR4",
        "relevancia": 40, "relevancia_motivo": "teste", "credibilidade": None,
        "credibilidade_motivo": None, "versao_classificador": "v1",
        "classificado_em": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


def _cruzamento_padrao():
    return {"nivel_evidencia": "nivel_1_sinal_social", "estado": "detectado",
            "chave_acontecimento": "PETR4|teste|2026-10-30", "mesma_origem": False,
            "evidencias_confirmacao": [], "fontes_cruzadas": []}


def test_persistir_lote_novo_post_conta_como_novo():
    cliente = _ClienteFake()
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        novos = store_mod.persistir_lote([
            {"sinal": SINAL_ANALISE_FUNDAMENTADA, "classificacao": _classificacao_ok(), "cruzamento": _cruzamento_padrao()},
        ])
    assert novos == 1
    assert SINAL_ANALISE_FUNDAMENTADA.post_id in cliente.tabelas["x_sinais"].linhas


def test_persistir_lote_post_ja_existente_nao_conta_como_novo():
    cliente = _ClienteFake()
    cliente.tabelas.setdefault("x_sinais", _TabelaFake()).linhas[SINAL_ANALISE_FUNDAMENTADA.post_id] = {"post_id": SINAL_ANALISE_FUNDAMENTADA.post_id, "versao_classificador": "v1"}
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        novos = store_mod.persistir_lote([
            {"sinal": SINAL_ANALISE_FUNDAMENTADA, "classificacao": _classificacao_ok(), "cruzamento": _cruzamento_padrao()},
        ])
    assert novos == 0


def test_classificacao_falha_nunca_e_persistida_como_sem_relevancia():
    cliente = _ClienteFake()
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        novos = store_mod.persistir_lote([
            {"sinal": SINAL_RUMOR, "classificacao": {"ok": False, "motivo_falha": "cota"}, "cruzamento": _cruzamento_padrao()},
        ])
    assert novos == 0
    assert SINAL_RUMOR.post_id not in cliente.tabelas.get("x_sinais", _TabelaFake()).linhas


def test_reprocessamento_com_versao_nova_historiza_classificacao_anterior():
    cliente = _ClienteFake()
    cliente.tabelas.setdefault("x_sinais", _TabelaFake()).linhas[SINAL_ANALISE_FUNDAMENTADA.post_id] = {
        "post_id": SINAL_ANALISE_FUNDAMENTADA.post_id, "categoria": "opiniao_analista",
        "relevancia": 10, "relevancia_motivo": "antigo", "credibilidade": None,
        "credibilidade_motivo": None, "nivel_evidencia": "nivel_1_sinal_social",
        "estado": "detectado", "versao_classificador": "v1", "classificado_em": "2026-10-01T00:00:00Z",
    }
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        store_mod.persistir_lote([
            {"sinal": SINAL_ANALISE_FUNDAMENTADA, "classificacao": _classificacao_ok(versao_classificador="v2"), "cruzamento": _cruzamento_padrao()},
        ])
    historico = cliente.tabelas["x_sinais_historico"].linhas
    assert len(historico) == 1
    linha_historico = list(historico.values())[0]
    assert linha_historico["versao_classificador"] == "v1"


def test_sem_cliente_retorna_zero_sem_lancar():
    with patch.object(store_mod, "obter_cliente", return_value=None):
        assert store_mod.persistir_lote([{"sinal": SINAL_RUMOR, "classificacao": _classificacao_ok(), "cruzamento": _cruzamento_padrao()}]) == 0
        assert store_mod.listar_sinais() is None
        assert store_mod.historico_autor("@x") is None


def test_listar_sinais_filtra_por_ticker():
    cliente = _ClienteFake()
    agora_iso = datetime.now(timezone.utc).isoformat()
    cliente.tabelas.setdefault("x_sinais", _TabelaFake()).linhas.update({
        "1": {"post_id": "1", "ticker": "PETR4", "horario_captura": agora_iso},
        "2": {"post_id": "2", "ticker": "VALE3", "horario_captura": agora_iso},
    })
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        resultado = store_mod.listar_sinais(ticker="petr4")
    assert len(resultado) == 1
    assert resultado[0]["ticker"] == "PETR4"
