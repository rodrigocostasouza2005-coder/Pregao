# -*- coding: utf-8 -*-
"""Testes das metricas cumulativas de data/coletores_status.py (auditoria
Agente A, 2026-11-12): tempo_s/publicacoes_encontradas/documentos_
extraidos/duplicidades passados a registrar_tentativa SOMAM aos
contadores cumulativos (ver sql/coletores_status_metricas.sql, PROPOSTO
mas nunca aplicado), e taxa_sucesso()/tempo_medio_s() leem esses
contadores. Mesmo padrao de fake Supabase em memoria de
tests/test_coletores_status.py (_TabelaFake/_ClienteFake) - reaproveitado
aqui, nunca faz chamada de rede/banco real.

Uso: python -m pytest tests/test_coletores_status_metricas.py"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.coletores_status as cs_mod


class _TabelaFake:
    def __init__(self, cliente):
        self.cliente = cliente
        self._filtro_nome = None
        self._op = None
        self._payload = None

    def select(self, *_a, **_k):
        self._op = "select"
        return self

    def upsert(self, payload):
        self._op = "upsert"
        self._payload = payload
        return self

    def eq(self, campo, valor):
        if campo == "nome":
            self._filtro_nome = valor
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        if self._op == "upsert":
            self.cliente.linhas[self._payload["nome"]] = dict(self._payload)
            return _Resposta([self._payload])
        if self._op == "select":
            if self._filtro_nome is not None:
                linha = self.cliente.linhas.get(self._filtro_nome)
                return _Resposta([linha] if linha else [])
            return _Resposta(list(self.cliente.linhas.values()))
        return _Resposta([])


class _Resposta:
    def __init__(self, data):
        self.data = data


class _ClienteFake:
    def __init__(self):
        self.linhas = {}

    def table(self, _nome):
        return _TabelaFake(self)


def test_primeira_tentativa_inicia_contadores_cumulativos_em_1():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        cs_mod.registrar_tentativa(
            "J.P. Morgan Global Research", "jpmorgan.com", execucao_ok=True,
            registros_novos=2, categoria="Research",
            tempo_s=1.5, publicacoes_encontradas=2, documentos_extraidos=2, duplicidades=0,
        )
    linha = cliente.linhas["J.P. Morgan Global Research"]
    assert linha["total_tentativas"] == 1
    assert linha["total_sucessos"] == 1
    assert linha["total_falhas"] == 0
    assert linha["total_tempo_s"] == 1.5
    assert linha["total_publicacoes_encontradas"] == 2
    assert linha["total_documentos_extraidos"] == 2
    assert linha["total_duplicidades"] == 0
    assert linha["tempo_ultima_execucao_s"] == 1.5


def test_tentativas_sucessivas_somam_aos_contadores_sem_resetar():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        cs_mod.registrar_tentativa(
            "Nord Research", "nordinvestimentos.com.br", execucao_ok=True,
            registros_novos=3, categoria="Research", tempo_s=2.0,
            publicacoes_encontradas=3, documentos_extraidos=3, duplicidades=1,
        )
        cs_mod.registrar_tentativa(
            "Nord Research", "nordinvestimentos.com.br", execucao_ok=True,
            registros_novos=1, categoria="Research", tempo_s=1.0,
            publicacoes_encontradas=1, documentos_extraidos=1, duplicidades=0,
        )
    linha = cliente.linhas["Nord Research"]
    assert linha["total_tentativas"] == 2
    assert linha["total_sucessos"] == 2
    assert linha["total_tempo_s"] == 3.0
    assert linha["total_publicacoes_encontradas"] == 4
    assert linha["total_documentos_extraidos"] == 4
    assert linha["total_duplicidades"] == 1


def test_falha_incrementa_total_falhas_nao_total_sucessos():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        cs_mod.registrar_tentativa(
            "Citi Global Insights", "citigroup.com", execucao_ok=True,
            registros_novos=2, categoria="Research", tempo_s=1.0,
            publicacoes_encontradas=2, documentos_extraidos=2,
        )
        cs_mod.registrar_tentativa(
            "Citi Global Insights", "citigroup.com", execucao_ok=False,
            erro="sitemap indisponível: ConnectionError", categoria="Research",
            tempo_s=0.3, publicacoes_encontradas=0, documentos_extraidos=0, duplicidades=0,
        )
    linha = cliente.linhas["Citi Global Insights"]
    assert linha["total_tentativas"] == 2
    assert linha["total_sucessos"] == 1
    assert linha["total_falhas"] == 1
    assert round(linha["total_tempo_s"], 2) == 1.3


def test_metricas_opcionais_nao_informadas_nao_incrementam_nada():
    """registrar_tentativa continua funcionando sem NENHUMA das metricas
    novas (retrocompatibilidade - coletores que ainda nao foram
    adaptados pra medir isso continuam registrando normalmente)."""
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        cs_mod.registrar_tentativa("NEWS", "Google News", execucao_ok=True, registros_novos=5)
    linha = cliente.linhas["NEWS"]
    assert linha["total_tentativas"] == 1
    assert linha["total_tempo_s"] == 0
    assert linha["total_publicacoes_encontradas"] == 0


def test_upsert_falha_com_colunas_novas_cai_pro_retry_sem_elas():
    cliente = _ClienteFake()
    tabela_original = _TabelaFake

    chamadas_upsert = []

    class _TabelaComFalhaNaPrimeira(tabela_original):
        def execute(self):
            if self._op == "upsert":
                chamadas_upsert.append(self._payload)
                if len(chamadas_upsert) == 1:
                    raise Exception("column coletores_status.total_tentativas does not exist")
            return super().execute()

    cliente.table = lambda _nome: _TabelaComFalhaNaPrimeira(cliente)

    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        ok = cs_mod.registrar_tentativa(
            "Morgan Stanley Insights", "morganstanley.com", execucao_ok=True,
            registros_novos=1, tempo_s=1.0, publicacoes_encontradas=1, documentos_extraidos=1,
        )
    assert ok is True
    assert len(chamadas_upsert) == 2
    assert "total_tentativas" not in chamadas_upsert[1]
    assert "tempo_ultima_execucao_s" not in chamadas_upsert[1]
    # colunas legadas continuam presentes no retry
    assert chamadas_upsert[1]["registros_novos"] == 1


# ============================================================
# taxa_sucesso / tempo_medio_s
# ============================================================

def test_taxa_sucesso_sem_nenhuma_tentativa_retorna_none():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        assert cs_mod.taxa_sucesso("Casa Nunca Rodou") is None


def test_taxa_sucesso_banco_fora_do_ar_retorna_none():
    with patch.object(cs_mod, "obter_cliente", return_value=None):
        assert cs_mod.taxa_sucesso("NEWS") is None


def test_taxa_sucesso_calculada_a_partir_dos_contadores_reais():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        cs_mod.registrar_tentativa("BTG Pactual Research", "btg", execucao_ok=True, registros_novos=1)
        cs_mod.registrar_tentativa("BTG Pactual Research", "btg", execucao_ok=True, registros_novos=1)
        cs_mod.registrar_tentativa("BTG Pactual Research", "btg", execucao_ok=False, erro="x")
        taxa = cs_mod.taxa_sucesso("BTG Pactual Research")
    assert taxa == pytest.approx(2 / 3, rel=1e-3)


def test_tempo_medio_s_calculado_a_partir_do_total_acumulado():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        cs_mod.registrar_tentativa("Monte Bravo", "montebravo.com.br", execucao_ok=True, tempo_s=2.0)
        cs_mod.registrar_tentativa("Monte Bravo", "montebravo.com.br", execucao_ok=True, tempo_s=4.0)
        medio = cs_mod.tempo_medio_s("Monte Bravo")
    assert medio == pytest.approx(3.0)


def test_tempo_medio_s_sem_tentativa_retorna_none():
    cliente = _ClienteFake()
    with patch.object(cs_mod, "obter_cliente", return_value=cliente):
        assert cs_mod.tempo_medio_s("Casa Nunca Rodou") is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
