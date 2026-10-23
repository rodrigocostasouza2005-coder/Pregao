# -*- coding: utf-8 -*-
"""MARKET RESEARCHER (data/market_researcher.py): camada de avaliação de
qualidade dos coletores (reaproveita data/saude_dados.py) + comparação
de cobertura entre casas de research (reaproveita data/research/store.py)
- sem coletor novo, sem tabela nova, sem chamada de IA nova. Testes
cobrem: priorização por severidade/criticidade, degradação quando uma
fonte falha, e que "divergência" só é apontada com campo estruturado
real (nunca inferida de título/sentimento)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from data import market_researcher as mr


def _coletor(nome, categoria, codigo_estado, alerta=True, desconhecido=False, erro=None):
    return {
        "nome": nome, "categoria": categoria, "codigo_estado": codigo_estado,
        "rotulo_estado": codigo_estado, "alerta": alerta, "desconhecido": desconhecido,
        "status_bruto": {"ultimo_sucesso_em": None, "ultima_tentativa_em": "2026-10-23T10:00:00Z", "ultimo_erro": erro},
    }


def test_achados_ignora_coletores_saudaveis():
    painel = [_coletor("NEWS (Brasil)", "Noticias", "SUCESSO_COM_NOVIDADE", alerta=False, desconhecido=False)]
    with patch.object(mr.saude_dados, "obter_painel_saude", return_value=painel):
        achados = mr.achados_qualidade_coletores()
    assert achados == []


def test_achados_prioriza_critico_sobre_secundario_mesmo_codigo_igual():
    painel = [
        _coletor("Genial Analisa", "Research", "FALHA_EXECUCAO", erro="bloqueio WAF"),
        _coletor("NEWS (Brasil)", "Noticias", "FALHA_EXECUCAO", erro="timeout"),
    ]
    with patch.object(mr.saude_dados, "obter_painel_saude", return_value=painel):
        achados = mr.achados_qualidade_coletores()
    assert [a["coletor"] for a in achados] == ["NEWS (Brasil)", "Genial Analisa"]
    assert achados[0]["critico"] is True
    assert achados[1]["critico"] is False


def test_achados_prioriza_falha_persistencia_antes_de_fonte_indisponivel():
    painel = [
        _coletor("CVM (watchlist)", "CVM", "FONTE_INDISPONIVEL"),
        _coletor("MERCADO", "Cotacoes", "FALHA_PERSISTENCIA"),
    ]
    with patch.object(mr.saude_dados, "obter_painel_saude", return_value=painel):
        achados = mr.achados_qualidade_coletores()
    assert achados[0]["coletor"] == "MERCADO"


def test_achados_degrada_sem_excecao_quando_painel_falha():
    with patch.object(mr.saude_dados, "obter_painel_saude", side_effect=RuntimeError("Supabase fora do ar")):
        assert mr.achados_qualidade_coletores() == []


def _item(casa, data_iso, titulo="Relatório", recomendacao=None, preco_alvo=None, tickers=("WEGE3",)):
    return {"casa": casa, "data": data_iso, "titulo": titulo, "link": f"https://{casa}/x",
            "recomendacao": recomendacao, "preco_alvo": preco_alvo, "tickers": list(tickers)}


def test_cobertura_cruzada_lista_quem_cobriu_e_quem_nao_cobriu():
    hoje = datetime.now(timezone.utc)
    itens = [_item("Genial Analisa", hoje.isoformat()), _item("XP Investimentos", (hoje - timedelta(days=40)).isoformat())]
    with patch.object(mr, "listar_itens", return_value=itens), \
         patch.object(mr, "_casas_ativas_nomes", return_value=["Genial Analisa", "XP Investimentos", "BTG Research"]):
        resultado = mr.cobertura_cruzada_casas("WEGE3")
    nomes_cobertura = {c["casa"] for c in resultado["cobertura"]}
    assert nomes_cobertura == {"Genial Analisa"}  # XP está fora da janela de 30 dias
    assert resultado["sem_cobertura"] == ["BTG Research", "XP Investimentos"]
    assert resultado["divergencia"] is None


def test_cobertura_cruzada_banco_indisponivel_e_distinto_de_sem_cobertura():
    with patch.object(mr, "listar_itens", return_value=None):
        resultado = mr.cobertura_cruzada_casas("WEGE3")
    assert resultado["cobertura"] is None
    assert resultado["sem_cobertura"] == []


def test_cobertura_cruzada_so_aponta_divergencia_com_campo_estruturado_real():
    hoje = datetime.now(timezone.utc).isoformat()
    itens = [
        _item("Genial Analisa", hoje, recomendacao="COMPRA"),
        _item("XP Investimentos", hoje, recomendacao="VENDA"),
    ]
    with patch.object(mr, "listar_itens", return_value=itens), \
         patch.object(mr, "_casas_ativas_nomes", return_value=["Genial Analisa", "XP Investimentos"]):
        resultado = mr.cobertura_cruzada_casas("WEGE3")
    assert resultado["divergencia"]["por_casa"] == {"Genial Analisa": "COMPRA", "XP Investimentos": "VENDA"}


def test_cobertura_cruzada_nunca_infere_divergencia_so_de_titulo():
    hoje = datetime.now(timezone.utc).isoformat()
    itens = [
        _item("Genial Analisa", hoje, titulo="WEGE3: hora de vender?", recomendacao=None),
        _item("XP Investimentos", hoje, titulo="WEGE3 é uma boa compra", recomendacao=None),
    ]
    with patch.object(mr, "listar_itens", return_value=itens), \
         patch.object(mr, "_casas_ativas_nomes", return_value=["Genial Analisa", "XP Investimentos"]):
        resultado = mr.cobertura_cruzada_casas("WEGE3")
    assert resultado["divergencia"] is None  # sem campo estruturado, nunca infere do título
