# -*- coding: utf-8 -*-
"""Teste do gap real corrigido na auditoria de arquitetura (Agente A,
2026-11-12): Monte Bravo, Nord Research e os 4 bancos globais (J.P.
Morgan/BofA/Morgan Stanley/Citi) sao casas ATIVAS de research
(data/research/__init__.py:CASAS) mas nao estavam cadastradas em
data/diagnostico.py (painel DIAGNOSTICO DE FONTES, aba CONFIG) -
nenhuma delas era testada por ali, mesmo tendo seu proprio
testar_conexao(). Este teste trava que as 6 continuam presentes (nunca
regride em silencio se alguem remover de novo sem querer).

Uso: python -m pytest tests/test_diagnostico_research_casas.py"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.diagnostico as diag_mod

_CASAS_ATIVAS_RESEARCH = (
    "Monte Bravo", "Nord Research", "J.P. Morgan Global Research",
    "BofA Institute", "Morgan Stanley Insights", "Citi Global Insights",
)


def test_todas_as_casas_ativas_de_research_tem_teste_especifico_cadastrado():
    faltantes = [nome for nome in _CASAS_ATIVAS_RESEARCH if nome not in diag_mod._TESTES_ESPECIFICOS]
    assert faltantes == [], f"casas sem teste especifico cadastrado: {faltantes}"


def test_todas_as_casas_ativas_de_research_tem_entrada_em_fontes():
    nomes_em_fontes = {f["nome"] for f in diag_mod.FONTES}
    faltantes = [nome for nome in _CASAS_ATIVAS_RESEARCH if nome not in nomes_em_fontes]
    assert faltantes == [], f"casas sem entrada em FONTES: {faltantes}"


def test_teste_especifico_de_cada_casa_e_o_proprio_testar_conexao_do_modulo():
    """O diagnostico tem que chamar a MESMA logica de verdade que o
    coletor real usa (nao um GET generico) - ver docstring de
    data.diagnostico.testar_fonte."""
    from data.research import bankofamerica, citi, jpmorgan, montebravo, morgan_stanley, nord

    mapeamento = {
        "Monte Bravo": montebravo.testar_conexao,
        "Nord Research": nord.testar_conexao,
        "J.P. Morgan Global Research": jpmorgan.testar_conexao,
        "BofA Institute": bankofamerica.testar_conexao,
        "Morgan Stanley Insights": morgan_stanley.testar_conexao,
        "Citi Global Insights": citi.testar_conexao,
    }
    for nome, funcao_esperada in mapeamento.items():
        assert diag_mod._TESTES_ESPECIFICOS[nome] is funcao_esperada


# ============================================================
# Bug de desempacotamento (auditoria 2026-11-26): _testar_gnews_decode
# desempacotava 3 valores de news._extrair_texto_artigo, que devolve 4
# (texto, imagem, link_real, motivo_falha) desde a fase 3 de NEWS. Como
# testar_fonte captura qualquer excecao, o painel DIAGNOSTICO DE FONTES
# reportava "erro: too many values to unpack (expected 3)" - acusando
# bloqueio da fonte quando o problema era local, sem nunca avaliar o
# pipeline real. Nada de rede aqui: _buscar_feed e _extrair_texto_artigo
# sao mockados.
# ============================================================

_FONTE_GNEWS = {
    "nome": "Google News (decode+extração)",
    "url": "https://news.google.com/rss/search?q=Ibovespa",
}


def _com_news_mockado(retorno_extracao):
    """Mocka data.news._buscar_feed/_extrair_texto_artigo - importados
    DENTRO de _testar_gnews_decode, entao o patch e' no modulo data.news."""
    from unittest.mock import patch

    import data.news as news_mod
    return (
        patch.object(news_mod, "_buscar_feed", return_value=[{"link": "https://news.google.com/rss/articles/x"}]),
        patch.object(news_mod, "_extrair_texto_artigo", return_value=retorno_extracao),
    )


def test_gnews_decode_com_extracao_bem_sucedida_nunca_levanta_valueerror():
    patch_feed, patch_extrair = _com_news_mockado(
        ("texto do artigo com conteudo real", "https://img/x.jpg", "https://infomoney.com.br/materia", None)
    )
    with patch_feed, patch_extrair:
        resultado = diag_mod.testar_fonte(_FONTE_GNEWS)

    assert resultado["ok"] is True
    assert "unpack" not in resultado["status"]
    assert "OK (" in resultado["status"]
    assert "infomoney.com.br" in resultado["status"]  # link_real, nao a imagem


def test_gnews_decode_com_extracao_falhando_reporta_o_motivo_real_nao_erro_de_unpack():
    patch_feed, patch_extrair = _com_news_mockado((None, None, None, "bloqueado por paywall"))
    with patch_feed, patch_extrair:
        resultado = diag_mod.testar_fonte(_FONTE_GNEWS)

    assert resultado["ok"] is False
    assert resultado["status"] == "falhou: bloqueado por paywall"
    assert "unpack" not in resultado["status"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
