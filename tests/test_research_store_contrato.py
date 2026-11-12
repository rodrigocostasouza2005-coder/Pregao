# -*- coding: utf-8 -*-
"""Testes das adicoes de arquitetura em data/research/store.py (auditoria
Agente A, 2026-11-12): contagem de duplicidade (metrica pura),
persistencia das colunas ADITIVAS do contrato ampliado (mesmo padrao
defensivo ja usado pra 'publicado_em', ver tests/test_research_fase3.py)
e o versionamento best-effort pra research_itens_historico (tabela
PROPOSTA, nunca aplicada por este agente - ver sql/research_itens_
historico.sql). Tudo mockado (Supabase fake em memoria), nunca faz
chamada de rede/banco real.

Uso: python -m pytest tests/test_research_store_contrato.py"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.store as store_mod


# ============================================================
# contar_duplicados (metrica pura)
# ============================================================

def test_contar_duplicados_vazio():
    assert store_mod.contar_duplicados([]) == 0


def test_contar_duplicados_sem_nenhum_repetido():
    itens = [{"link": "https://x/1"}, {"link": "https://x/2"}]
    assert store_mod.contar_duplicados(itens) == 0


def test_contar_duplicados_conta_links_repetidos():
    itens = [
        {"link": "https://x/1"}, {"link": "https://x/2"}, {"link": "https://x/1"},
    ]
    assert store_mod.contar_duplicados(itens) == 1


def test_contar_duplicados_ignora_item_sem_link():
    itens = [{"link": "https://x/1"}, {"titulo": "sem link"}, {}]
    assert store_mod.contar_duplicados(itens) == 0


# ============================================================
# Fake de cliente Supabase com select() e upsert() independentes -
# generaliza _cliente_upsert de tests/test_research_fase3.py (que so'
# cobria upsert) pra tambem cobrir o SELECT que _versionar_antes_do_upsert
# faz antes do upsert principal.
# ============================================================

class _ClienteFakeCompleto:
    def __init__(self, linhas_existentes: dict = None, efeitos_upsert: list = None, falhar_insert_historico: bool = False):
        self._linhas = dict(linhas_existentes or {})  # link -> linha (simula research_itens)
        self._efeitos_upsert = list(efeitos_upsert or [None])  # 1 por chamada de upsert().execute()
        self._falhar_insert_historico = falhar_insert_historico
        self.upsert_payloads = []
        self.historico_inserts = []
        self._tabela = None

    def table(self, nome):
        self._tabela = nome
        return self

    def select(self, *_a, **_k):
        self._op = "select"
        return self

    def in_(self, campo, valores):
        self._in_campo, self._in_valores = campo, valores
        return self

    def eq(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def upsert(self, payload, **_k):
        self._op = "upsert"
        self._payload = payload
        return self

    def insert(self, payload, **_k):
        self._op = "insert"
        self._payload = payload
        return self

    def execute(self):
        if self._tabela == "research_itens" and self._op == "select":
            linhas = [self._linhas[link] for link in self._in_valores if link in self._linhas]
            return _Resposta(linhas)
        if self._tabela == "research_itens" and self._op == "upsert":
            self.upsert_payloads.append(self._payload)
            efeito = self._efeitos_upsert.pop(0) if self._efeitos_upsert else None
            if efeito is not None:
                raise efeito
            for linha in self._payload:
                self._linhas[linha["link"]] = linha
            return _Resposta(self._payload)
        if self._tabela == "research_itens_historico" and self._op == "insert":
            if self._falhar_insert_historico:
                raise Exception("relation \"research_itens_historico\" does not exist")
            self.historico_inserts.append(self._payload)
            return _Resposta(self._payload)
        return _Resposta([])


class _Resposta:
    def __init__(self, data):
        self.data = data


# ============================================================
# Colunas ADITIVAS do contrato ampliado (empresa/setor/preco_referencia/
# horizonte/texto_integral_disponivel) - mesmo padrao defensivo ja
# comprovado pra 'publicado_em'.
# ============================================================

def test_salvar_itens_inclui_colunas_novas_quando_presentes():
    cliente = _ClienteFakeCompleto()
    itens = [{
        "link": "https://x/1", "casa": "J.P. Morgan Global Research", "titulo": "Nota",
        "data": "2026-11-10", "autor": "", "tipo": "MACRO", "tickers": [],
        "setor": "Global Research", "empresa": None, "preco_referencia": None,
        "horizonte": None, "texto_integral_disponivel": False,
    }]
    import unittest.mock as mock
    with mock.patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_itens(itens)
    assert ok is True
    payload = cliente.upsert_payloads[0]
    assert payload[0]["setor"] == "Global Research"
    # texto_integral_disponivel=False e' um valor REAL (nao "ausente") -
    # tem que ir no payload mesmo sendo falsy.
    assert "texto_integral_disponivel" in payload[0]
    assert payload[0]["texto_integral_disponivel"] is False


def test_salvar_itens_sem_nenhum_item_com_campo_novo_nunca_manda_a_coluna():
    cliente = _ClienteFakeCompleto()
    itens = [{
        "link": "https://x/2", "casa": "Nord Research", "titulo": "Resultado",
        "data": "2026-11-10", "autor": "Fabiano Vaz", "tipo": "ACOES", "tickers": ["PETR4"],
    }]
    import unittest.mock as mock
    with mock.patch.object(store_mod, "obter_cliente", return_value=cliente):
        store_mod.salvar_itens(itens)
    payload = cliente.upsert_payloads[0]
    assert "setor" not in payload[0]
    assert "empresa" not in payload[0]
    assert "preco_referencia" not in payload[0]
    assert "horizonte" not in payload[0]
    assert "texto_integral_disponivel" not in payload[0]


def test_salvar_itens_coluna_nova_ausente_no_banco_cai_pro_retry_sem_ela():
    cliente = _ClienteFakeCompleto(
        efeitos_upsert=[Exception("column research_itens.setor does not exist"), None],
    )
    itens = [{
        "link": "https://x/3", "casa": "Citi Global Insights", "titulo": "Nota",
        "data": "2026-11-10", "autor": "", "tipo": "MACRO", "tickers": [], "setor": "Equities",
    }]
    import unittest.mock as mock
    with mock.patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_itens(itens)
    assert ok is True
    assert len(cliente.upsert_payloads) == 2
    assert "setor" not in cliente.upsert_payloads[1][0]


# ============================================================
# Versionamento best-effort (research_itens_historico)
# ============================================================

def test_versionamento_arquiva_quando_titulo_muda_pro_mesmo_link():
    cliente = _ClienteFakeCompleto(linhas_existentes={
        "https://x/4": {
            "link": "https://x/4", "casa": "BTG Pactual Research", "titulo": "Versão antiga",
            "data": "2026-11-10", "autor": "", "tipo": "ACOES", "tickers": ["PETR4"],
            "resumo": "resumo salvo antes", "modelo_resumo": "modelo-x",
            "preco_alvo": 40.0, "recomendacao": "COMPRA", "coletado_em": "2026-11-10T09:00:00+00:00",
        },
    })
    itens = [{
        "link": "https://x/4", "casa": "BTG Pactual Research", "titulo": "Versão corrigida",
        "data": "2026-11-10", "autor": "", "tipo": "ACOES", "tickers": ["PETR4"],
    }]
    import unittest.mock as mock
    with mock.patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_itens(itens)
    assert ok is True
    assert len(cliente.historico_inserts) == 1
    arquivada = cliente.historico_inserts[0][0]
    assert arquivada["titulo"] == "Versão antiga"
    assert arquivada["resumo"] == "resumo salvo antes"
    assert arquivada["preco_alvo"] == 40.0
    assert arquivada["link"] == "https://x/4"


def test_versionamento_nao_arquiva_quando_titulo_e_data_sao_identicos():
    """Recoleta de rotina (fonte continua listando o mesmo relatorio, sem
    mudar titulo/data) NUNCA gera linha de historico - so' mudanca real
    conta como 'nova versao' (ver _CAMPOS_VERSAO)."""
    cliente = _ClienteFakeCompleto(linhas_existentes={
        "https://x/5": {
            "link": "https://x/5", "casa": "Monte Bravo", "titulo": "Mesmo título",
            "data": "2026-11-10", "autor": "", "tipo": "ACOES", "tickers": ["WEGE3"],
            "coletado_em": "2026-11-10T09:00:00+00:00",
        },
    })
    itens = [{
        "link": "https://x/5", "casa": "Monte Bravo", "titulo": "Mesmo título",
        "data": "2026-11-10", "autor": "", "tipo": "ACOES", "tickers": ["WEGE3"],
    }]
    import unittest.mock as mock
    with mock.patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_itens(itens)
    assert ok is True
    assert cliente.historico_inserts == []


def test_versionamento_sem_linha_anterior_nunca_arquiva_nada():
    """Link novo (1a coleta) - nao ha' versao anterior nenhuma pra
    arquivar."""
    cliente = _ClienteFakeCompleto()
    itens = [{
        "link": "https://x/6", "casa": "Morgan Stanley Insights", "titulo": "Nota nova",
        "data": "2026-11-10", "autor": "", "tipo": "MACRO", "tickers": [],
    }]
    import unittest.mock as mock
    with mock.patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_itens(itens)
    assert ok is True
    assert cliente.historico_inserts == []


def test_versionamento_tabela_historico_ausente_nunca_bloqueia_o_upsert_principal():
    """Melhor esforco: se research_itens_historico ainda nao existir
    (migracao proposta nao aplicada), salvar_itens continua funcionando
    normalmente - so' nao arquiva nada."""
    cliente = _ClienteFakeCompleto(
        linhas_existentes={
            "https://x/7": {
                "link": "https://x/7", "casa": "BofA Institute", "titulo": "Versão antiga",
                "data": "2026-11-10", "autor": "", "tipo": "MACRO", "tickers": [],
                "coletado_em": "2026-11-10T09:00:00+00:00",
            },
        },
        falhar_insert_historico=True,
    )
    itens = [{
        "link": "https://x/7", "casa": "BofA Institute", "titulo": "Versão nova",
        "data": "2026-11-10", "autor": "", "tipo": "MACRO", "tickers": [],
    }]
    import unittest.mock as mock
    with mock.patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_itens(itens)
    assert ok is True  # upsert principal segue funcionando mesmo com o historico indisponivel
    assert len(cliente.upsert_payloads) == 1
    assert cliente.upsert_payloads[0][0]["titulo"] == "Versão nova"


def test_versionar_antes_do_upsert_leitura_falha_nunca_propaga():
    """Mesmo melhor-esforco do lado da LEITURA (nao so' da escrita) - se
    o SELECT falhar por qualquer motivo, salvar_itens segue pro upsert
    principal sem versionar nada."""
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.in_.return_value.execute.side_effect = Exception("timeout")
    itens = [{
        "link": "https://x/8", "casa": "X", "titulo": "Y", "data": "2026-11-10",
        "autor": "", "tipo": "MACRO", "tickers": [],
    }]
    # chamada direta (nao via salvar_itens) - isola a funcao, sem depender
    # do upsert() tambem estar mockado corretamente no MagicMock generico.
    store_mod._versionar_antes_do_upsert(cliente, itens)  # nao deve lancar


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
