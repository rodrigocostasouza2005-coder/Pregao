# -*- coding: utf-8 -*-
"""Teste de que data/research/__init__.py:coletar_casa passa as metricas
reais (tempo_s/publicacoes_encontradas/documentos_extraidos/duplicidades,
auditoria de arquitetura Agente A 2026-11-12) pra registrar_tentativa -
complementa tests/test_research_instrumentacao.py (que cobre
execucao_ok/persistencia_ok/registros_novos, intocado aqui). Mocka
obter_relatorios/store.salvar_itens/registrar_tentativa, nunca faz
chamada de rede nem toca Supabase de verdade.

Uso: python -m pytest tests/test_research_coletar_casa_metricas.py"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research as research_mod


def _casa_fake(nome="Casa Fake", fonte="fonte-fake.com", itens=None, falha=False):
    return {
        "id": "fake", "nome": nome, "fonte": fonte,
        "obter_relatorios": lambda: (None if falha else (itens or [])),
    }


def test_sucesso_passa_tempo_s_e_publicacoes_encontradas():
    itens = [{"link": "https://x/1"}, {"link": "https://x/2"}]
    casa = _casa_fake(itens=itens)
    with patch.object(research_mod, "registrar_tentativa") as mock_reg, \
         patch.object(research_mod.store, "salvar_itens", return_value=True):
        research_mod.coletar_casa(casa)
    _, kwargs = mock_reg.call_args
    assert kwargs.get("tempo_s") is not None and kwargs["tempo_s"] >= 0
    assert kwargs.get("publicacoes_encontradas") == 2


def test_sucesso_com_persistencia_ok_conta_documentos_extraidos():
    itens = [{"link": "https://x/1"}]
    casa = _casa_fake(itens=itens)
    with patch.object(research_mod, "registrar_tentativa") as mock_reg, \
         patch.object(research_mod.store, "salvar_itens", return_value=True):
        research_mod.coletar_casa(casa)
    _, kwargs = mock_reg.call_args
    assert kwargs.get("documentos_extraidos") == 1


def test_persistencia_falha_documentos_extraidos_e_zero():
    """So' conta como 'extraido' o que foi IDENTIFICADO + persistido de
    verdade - achar a publicacao mas falhar ao salvar nunca conta como
    documento extraido (nivel de completude real, nao so' 'a fonte
    respondeu')."""
    itens = [{"link": "https://x/1"}, {"link": "https://x/2"}]
    casa = _casa_fake(itens=itens)
    with patch.object(research_mod, "registrar_tentativa") as mock_reg, \
         patch.object(research_mod.store, "salvar_itens", return_value=False):
        research_mod.coletar_casa(casa)
    _, kwargs = mock_reg.call_args
    assert kwargs.get("publicacoes_encontradas") == 2
    assert kwargs.get("documentos_extraidos") == 0


def test_duplicidade_dentro_do_lote_e_contada_e_reportada():
    itens = [
        {"link": "https://x/dup"}, {"link": "https://x/unico"}, {"link": "https://x/dup"},
    ]
    casa = _casa_fake(itens=itens)
    with patch.object(research_mod, "registrar_tentativa") as mock_reg, \
         patch.object(research_mod.store, "salvar_itens", return_value=True):
        research_mod.coletar_casa(casa)
    _, kwargs = mock_reg.call_args
    assert kwargs.get("duplicidades") == 1


def test_falha_na_fonte_passa_zeros_nas_metricas_de_volume():
    casa = _casa_fake(falha=True)
    with patch.object(research_mod, "registrar_tentativa") as mock_reg, \
         patch.object(research_mod.store, "salvar_itens") as mock_salvar:
        research_mod.coletar_casa(casa)
    mock_salvar.assert_not_called()
    _, kwargs = mock_reg.call_args
    assert kwargs.get("publicacoes_encontradas") == 0
    assert kwargs.get("documentos_extraidos") == 0
    assert kwargs.get("duplicidades") == 0
    assert kwargs.get("tempo_s") is not None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
