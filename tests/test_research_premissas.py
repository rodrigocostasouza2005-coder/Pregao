# -*- coding: utf-8 -*-
"""Testes da biblioteca PERMANENTE de premissas/projecoes (Equity Research
Library, 2026-10-30, pedido do Rodrigo) - sql/research_premissas.sql,
data/research/store.py:salvar_premissas/listar_premissas e
data/research/resumir.py:_extrair_premissas_projecoes. Cobre ingestao
(extracao), recuperacao (listar_premissas), deduplicacao (upsert por
link) e rastreabilidade (link/casa/titulo preservados). Sem rede/Supabase
real - tudo mockado."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.resumir as resumir_mod
import data.research.store as store_mod


# ============================================================
# 1. Ingestao/extracao - _extrair_premissas_projecoes nunca inventa
# ============================================================

def test_extrai_tipo_documento_premissas_e_projecoes_do_formato_esperado():
    resposta = (
        "TIPO_DOCUMENTO: INICIACAO_COBERTURA\n"
        "PREMISSAS: expansao de capacidade conclui em 2027 | ganho de market share em motores industriais\n"
        "PROJECAO_RECEITA: crescimento de 12% a.a. nos proximos 3 anos\n"
        "PROJECAO_EBITDA_MARGEM: margem EBITDA de 22% em 2027\n"
        "PROJECAO_LUCRO: NAO_IDENTIFICADO\n"
    )
    with patch.object(resumir_mod, "_chamar_groq", return_value=(resposta, None)):
        tipo_documento, premissas, projecoes = resumir_mod._extrair_premissas_projecoes(
            "texto qualquer", "WEGE3 - Iniciacao de cobertura", "chave", "modelo"
        )
    assert tipo_documento == "INICIACAO_COBERTURA"
    assert premissas == ["expansao de capacidade conclui em 2027", "ganho de market share em motores industriais"]
    assert projecoes == {"receita": "crescimento de 12% a.a. nos proximos 3 anos", "ebitda_margem": "margem EBITDA de 22% em 2027"}
    assert "lucro" not in projecoes


def test_tudo_nao_identificado_retorna_vazio_nunca_inventa():
    resposta = (
        "TIPO_DOCUMENTO: NAO_IDENTIFICADO\n"
        "PREMISSAS: NAO_IDENTIFICADO\n"
        "PROJECAO_RECEITA: NAO_IDENTIFICADO\n"
        "PROJECAO_EBITDA_MARGEM: NAO_IDENTIFICADO\n"
        "PROJECAO_LUCRO: NAO_IDENTIFICADO\n"
    )
    with patch.object(resumir_mod, "_chamar_groq", return_value=(resposta, None)):
        tipo_documento, premissas, projecoes = resumir_mod._extrair_premissas_projecoes(
            "texto sem sinal", "titulo", "chave", "modelo"
        )
    assert tipo_documento is None
    assert premissas == []
    assert projecoes == {}


def test_falha_na_chamada_groq_retorna_vazio_sem_excecao():
    with patch.object(resumir_mod, "_chamar_groq", return_value=(None, "indisponivel")):
        tipo_documento, premissas, projecoes = resumir_mod._extrair_premissas_projecoes(
            "texto", "titulo", "chave", "modelo"
        )
    assert (tipo_documento, premissas, projecoes) == (None, [], {})


def test_tipo_documento_fora_da_lista_fechada_e_descartado():
    """Lista FECHADA (_TIPOS_DOCUMENTO_VALIDOS) - um rotulo livre que o
    modelo inventar (ex: fora do vocabulario esperado) nunca e' confiado."""
    resposta = "TIPO_DOCUMENTO: ANALISE_TECNICA_GRAFICA\nPREMISSAS: NAO_IDENTIFICADO\nPROJECAO_RECEITA: NAO_IDENTIFICADO\nPROJECAO_EBITDA_MARGEM: NAO_IDENTIFICADO\nPROJECAO_LUCRO: NAO_IDENTIFICADO\n"
    with patch.object(resumir_mod, "_chamar_groq", return_value=(resposta, None)):
        tipo_documento, _, _ = resumir_mod._extrair_premissas_projecoes("texto", "titulo", "chave", "modelo")
    assert tipo_documento is None


# ============================================================
# 2. store.py - persistencia permanente (upsert/dedup) e recuperacao
# ============================================================

def test_salvar_premissas_faz_upsert_por_link_sem_texto_completo():
    cliente = MagicMock()
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_premissas(
            "https://casa.com/relatorio/1", casa="Genial Analisa", titulo="WEGE3 - Iniciacao",
            tickers=["WEGE3"], data_publicacao="2026-10-30",
            tipo_documento="INICIACAO_COBERTURA", premissas=["ganho de market share"],
            projecoes={"receita": "crescimento de 12% a.a."},
            recomendacao="COMPRA", preco_alvo=55.0, modelo="openai/gpt-oss-20b",
        )
    assert ok is True
    chamada = cliente.table.return_value.upsert.call_args
    payload = chamada.args[0]
    assert chamada.kwargs["on_conflict"] == "link"
    assert payload["link"] == "https://casa.com/relatorio/1"
    assert payload["tickers"] == ["WEGE3"]
    assert payload["tipo_documento"] == "INICIACAO_COBERTURA"
    assert payload["premissas"] == ["ganho de market share"]
    assert payload["projecoes"] == {"receita": "crescimento de 12% a.a."}
    # nunca o texto completo do relatorio original - so' estrutura.
    assert "texto" not in payload and "conteudo" not in payload


def test_salvar_premissas_banco_fora_do_ar_retorna_false_sem_excecao():
    with patch.object(store_mod, "obter_cliente", return_value=None):
        ok = store_mod.salvar_premissas(
            "link", casa="X", titulo="Y", tickers=[], data_publicacao=None,
            tipo_documento=None, premissas=[], projecoes={}, recomendacao=None,
            preco_alvo=None, modelo=None,
        )
    assert ok is False


def test_salvar_premissas_erro_de_escrita_retorna_false_sem_propagar():
    cliente = MagicMock()
    cliente.table.return_value.upsert.return_value.execute.side_effect = Exception("Supabase fora do ar")
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_premissas(
            "link", casa="X", titulo="Y", tickers=[], data_publicacao=None,
            tipo_documento=None, premissas=[], projecoes={}, recomendacao=None,
            preco_alvo=None, modelo=None,
        )
    assert ok is False


def test_listar_premissas_filtra_por_ticker_via_overlaps():
    cliente = MagicMock()
    consulta = cliente.table.return_value.select.return_value
    consulta.overlaps.return_value = consulta
    consulta.eq.return_value = consulta
    consulta.order.return_value = consulta
    consulta.execute.return_value = MagicMock(data=[{"link": "a", "casa": "Genial Analisa", "tickers": ["WEGE3"]}])
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        resultado = store_mod.listar_premissas(tickers=["WEGE3"])
    consulta.overlaps.assert_called_once_with("tickers", ["WEGE3"])
    assert resultado == [{"link": "a", "casa": "Genial Analisa", "tickers": ["WEGE3"]}]


def test_listar_premissas_banco_fora_do_ar_retorna_none_distinto_de_vazio():
    with patch.object(store_mod, "obter_cliente", return_value=None):
        resultado = store_mod.listar_premissas()
    assert resultado is None


# ============================================================
# 3. Integracao em _gerar_resumo - so' persiste quando ha sinal real,
#    nunca derruba o resumo narrativo se a persistencia falhar
# ============================================================

def test_gerar_resumo_persiste_premissas_quando_tipo_acoes_tem_sinal():
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=("texto do relatorio", None)), \
         patch.object(resumir_mod, "resumir_com_groq", return_value=(
             "resumo narrativo qualquer", None,
             {"modelo": "openai/gpt-oss-20b", "preco_alvo": 55.0, "recomendacao": "COMPRA",
              "tipo_documento": "INICIACAO_COBERTURA", "premissas": ["ganho de market share"], "projecoes": {"receita": "12% a.a."}},
         )), \
         patch.object(resumir_mod.qualidade, "validar_fidelidade", return_value=None), \
         patch.object(resumir_mod.store, "salvar_resumo", return_value=True), \
         patch.object(resumir_mod.store, "salvar_premissas", return_value=True) as mock_premissas:
        resultado = resumir_mod._gerar_resumo(
            "https://casa.com/1", "WEGE3 - Iniciacao", None, "Genial Analisa", "ACOES",
            tickers=["WEGE3"], data_publicacao="2026-10-30",
        )
    assert resultado["resumo"] == "resumo narrativo qualquer"
    mock_premissas.assert_called_once()
    kwargs = mock_premissas.call_args.kwargs
    assert kwargs["tipo_documento"] == "INICIACAO_COBERTURA"
    assert kwargs["premissas"] == ["ganho de market share"]
    assert kwargs["data_publicacao"] == "2026-10-30"


def test_gerar_resumo_nao_persiste_quando_nenhum_campo_foi_identificado():
    """Sem NENHUM sinal real (nem preco-alvo, nem recomendacao, nem
    premissas/tipo/projecoes), nao cria linha vazia na biblioteca
    permanente - so' registra o que tem conteudo real."""
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=("texto do relatorio", None)), \
         patch.object(resumir_mod, "resumir_com_groq", return_value=(
             "resumo narrativo qualquer", None,
             {"modelo": "openai/gpt-oss-20b", "preco_alvo": None, "recomendacao": None,
              "tipo_documento": None, "premissas": [], "projecoes": {}},
         )), \
         patch.object(resumir_mod.qualidade, "validar_fidelidade", return_value=None), \
         patch.object(resumir_mod.store, "salvar_resumo", return_value=True), \
         patch.object(resumir_mod.store, "salvar_premissas", return_value=True) as mock_premissas:
        resumir_mod._gerar_resumo(
            "https://casa.com/2", "Macro - Boletim semanal", None, "Genial Analisa", "MACRO",
        )
    mock_premissas.assert_not_called()


def test_gerar_resumo_nao_persiste_quando_gate_de_qualidade_reprova():
    """Resumo reprovado pelo gate de fidelidade nunca persiste nada - nem
    em research_itens (ja testado em outro arquivo), nem na biblioteca
    permanente."""
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=("texto do relatorio", None)), \
         patch.object(resumir_mod, "resumir_com_groq", return_value=(
             "resumo com numero inventado", None,
             {"modelo": "m", "preco_alvo": 999.0, "recomendacao": "COMPRA",
              "tipo_documento": "VALUATION", "premissas": ["premissa qualquer"], "projecoes": {}},
         )), \
         patch.object(resumir_mod.qualidade, "validar_fidelidade", return_value="numero sem base no original"), \
         patch.object(resumir_mod, "_log_erro_ia"), \
         patch.object(resumir_mod.store, "salvar_premissas") as mock_premissas:
        resultado = resumir_mod._gerar_resumo(
            "https://casa.com/3", "titulo", None, "Genial Analisa", "ACOES",
        )
    assert resultado["resumo"] is None
    mock_premissas.assert_not_called()
