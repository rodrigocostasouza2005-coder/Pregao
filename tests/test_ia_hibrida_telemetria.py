# -*- coding: utf-8 -*-
"""data/ia_hibrida_telemetria.py - auditoria das chamadas de IA da
camada híbrida (missão "PREGÃO 2.1", 2026-11-13). Cobre: degrade sem
Supabase (nunca lança excecao), hash determinístico da entrada, e que
um erro de gravação (ex: tabela ainda não migrada) nunca propaga."""
from unittest.mock import MagicMock, patch

from data import ia_hibrida_telemetria as iht


def test_hash_entrada_e_deterministico_e_sensivel_ao_conteudo():
    payload_a = {"ticker": "WEGE3", "casas": {"Genial Analisa": {"recomendacao": "COMPRA"}}}
    payload_b = {"casas": {"Genial Analisa": {"recomendacao": "COMPRA"}}, "ticker": "WEGE3"}  # ordem diferente
    payload_c = {"ticker": "WEGE3", "casas": {"Genial Analisa": {"recomendacao": "VENDA"}}}
    assert iht.hash_entrada(payload_a) == iht.hash_entrada(payload_b)  # chaves ordenadas - ordem não importa
    assert iht.hash_entrada(payload_a) != iht.hash_entrada(payload_c)  # conteúdo diferente -> hash diferente


def test_registrar_execucao_sem_supabase_nunca_lanca():
    with patch.object(iht, "obter_cliente", return_value=None):
        ok = iht.registrar_execucao(
            origem="teste", provedor="groq", modelo="modelo-x", entrada_hash="abc123",
            sucesso=True, ticker="WEGE3",
        )
    assert ok is False


def test_registrar_execucao_com_falha_de_escrita_nunca_lanca():
    cliente_fake = MagicMock()
    cliente_fake.table.return_value.insert.return_value.execute.side_effect = RuntimeError("tabela não existe")
    with patch.object(iht, "obter_cliente", return_value=cliente_fake):
        ok = iht.registrar_execucao(
            origem="teste", provedor="groq", modelo="modelo-x", entrada_hash="abc123", sucesso=False,
            motivo_falha="falha de teste",
        )
    assert ok is False


def test_registrar_execucao_com_sucesso_grava_payload_completo():
    cliente_fake = MagicMock()
    with patch.object(iht, "obter_cliente", return_value=cliente_fake):
        ok = iht.registrar_execucao(
            origem="teste", provedor="groq", modelo="modelo-x", entrada_hash="abc123", sucesso=True,
            ticker="WEGE3", entrada_resumo="2 casas", fontes=[{"casa": "Genial Analisa"}],
            duracao_ms=1234, resultado_resumo="texto gerado",
        )
    assert ok is True
    payload_gravado = cliente_fake.table.return_value.insert.call_args[0][0]
    assert payload_gravado["origem"] == "teste"
    assert payload_gravado["ticker"] == "WEGE3"
    assert payload_gravado["sucesso"] is True
    assert payload_gravado["duracao_ms"] == 1234
    assert payload_gravado["fontes"] == [{"casa": "Genial Analisa"}]


def test_truncar_resumos_longos_sem_quebrar():
    texto_longo = "x" * 10000
    assert len(iht._truncar(texto_longo)) <= iht._TAMANHO_MAX_RESUMO + 1
    assert iht._truncar(None) is None
    assert iht._truncar("") is None


def test_listar_execucoes_recentes_sem_supabase_devolve_none():
    with patch.object(iht, "obter_cliente", return_value=None):
        assert iht.listar_execucoes_recentes() is None
