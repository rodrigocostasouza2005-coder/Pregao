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
        "RISCOS: alta de insumos pode comprimir margem | dependencia de licenca regulatoria pendente\n"
    )
    with patch.object(resumir_mod, "_chamar_groq", return_value=(resposta, None)):
        tipo_documento, premissas, projecoes, riscos = resumir_mod._extrair_premissas_projecoes(
            "texto qualquer", "WEGE3 - Iniciacao de cobertura", "chave", "modelo"
        )
    assert tipo_documento == "INICIACAO_COBERTURA"
    assert premissas == ["expansao de capacidade conclui em 2027", "ganho de market share em motores industriais"]
    assert projecoes == {"receita": "crescimento de 12% a.a. nos proximos 3 anos", "ebitda_margem": "margem EBITDA de 22% em 2027"}
    assert "lucro" not in projecoes
    assert riscos == ["alta de insumos pode comprimir margem", "dependencia de licenca regulatoria pendente"]


def test_tudo_nao_identificado_retorna_vazio_nunca_inventa():
    resposta = (
        "TIPO_DOCUMENTO: NAO_IDENTIFICADO\n"
        "PREMISSAS: NAO_IDENTIFICADO\n"
        "PROJECAO_RECEITA: NAO_IDENTIFICADO\n"
        "PROJECAO_EBITDA_MARGEM: NAO_IDENTIFICADO\n"
        "PROJECAO_LUCRO: NAO_IDENTIFICADO\n"
        "RISCOS: NAO_IDENTIFICADO\n"
    )
    with patch.object(resumir_mod, "_chamar_groq", return_value=(resposta, None)):
        tipo_documento, premissas, projecoes, riscos = resumir_mod._extrair_premissas_projecoes(
            "texto sem sinal", "titulo", "chave", "modelo"
        )
    assert tipo_documento is None
    assert premissas == []
    assert projecoes == {}
    assert riscos == []


def test_riscos_ausente_na_resposta_nunca_quebra_o_parsing():
    """Resposta sem a linha RISCOS (ex: modelo antigo/formato parcial) -
    _campo() ja' trata isso como None, mas confirma explicitamente que o
    resto da extracao continua funcionando."""
    resposta = (
        "TIPO_DOCUMENTO: VALUATION\n"
        "PREMISSAS: NAO_IDENTIFICADO\n"
        "PROJECAO_RECEITA: NAO_IDENTIFICADO\n"
        "PROJECAO_EBITDA_MARGEM: NAO_IDENTIFICADO\n"
        "PROJECAO_LUCRO: NAO_IDENTIFICADO\n"
    )
    with patch.object(resumir_mod, "_chamar_groq", return_value=(resposta, None)):
        tipo_documento, _, _, riscos = resumir_mod._extrair_premissas_projecoes(
            "texto", "titulo", "chave", "modelo"
        )
    assert tipo_documento == "VALUATION"
    assert riscos == []


def test_falha_na_chamada_groq_retorna_vazio_sem_excecao():
    with patch.object(resumir_mod, "_chamar_groq", return_value=(None, "indisponivel")):
        tipo_documento, premissas, projecoes, riscos = resumir_mod._extrair_premissas_projecoes(
            "texto", "titulo", "chave", "modelo"
        )
    assert (tipo_documento, premissas, projecoes, riscos) == (None, [], {}, [])


def test_tipo_documento_fora_da_lista_fechada_e_descartado():
    """Lista FECHADA (_TIPOS_DOCUMENTO_VALIDOS) - um rotulo livre que o
    modelo inventar (ex: fora do vocabulario esperado) nunca e' confiado."""
    resposta = "TIPO_DOCUMENTO: ANALISE_TECNICA_GRAFICA\nPREMISSAS: NAO_IDENTIFICADO\nPROJECAO_RECEITA: NAO_IDENTIFICADO\nPROJECAO_EBITDA_MARGEM: NAO_IDENTIFICADO\nPROJECAO_LUCRO: NAO_IDENTIFICADO\nRISCOS: NAO_IDENTIFICADO\n"
    with patch.object(resumir_mod, "_chamar_groq", return_value=(resposta, None)):
        tipo_documento, _, _, _ = resumir_mod._extrair_premissas_projecoes("texto", "titulo", "chave", "modelo")
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
    # riscos=None (default, nao informado) - chave nem vai no payload.
    assert "riscos" not in payload


def test_salvar_premissas_inclui_riscos_no_payload_quando_informado():
    cliente = MagicMock()
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_premissas(
            "https://casa.com/relatorio/2", casa="Genial Analisa", titulo="WEGE3 - Atualizacao",
            tickers=["WEGE3"], data_publicacao="2026-10-30",
            tipo_documento="ATUALIZACAO_COBERTURA", premissas=[], projecoes={},
            recomendacao=None, preco_alvo=None, modelo="openai/gpt-oss-20b",
            riscos=["alta de insumos pode comprimir margem"],
        )
    assert ok is True
    payload = cliente.table.return_value.upsert.call_args.args[0]
    assert payload["riscos"] == ["alta de insumos pode comprimir margem"]


def test_salvar_premissas_retry_sem_riscos_quando_coluna_nao_existe_no_banco():
    """Supabase do usuario ainda sem rodar sql/research_premissas_riscos.sql
    (coluna 'riscos' nao existe) - 1a tentativa (com riscos) falha, retry
    SEM a coluna deve funcionar - premissas/projecoes/recomendacao nunca
    ficam bloqueadas so' por causa da coluna nova."""
    cliente = MagicMock()
    efeitos = [Exception("column research_premissas.riscos does not exist"), MagicMock()]
    cliente.table.return_value.upsert.return_value.execute.side_effect = efeitos
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_premissas(
            "link", casa="X", titulo="Y", tickers=[], data_publicacao=None,
            tipo_documento=None, premissas=["p1"], projecoes={}, recomendacao=None,
            preco_alvo=None, modelo=None, riscos=["r1"],
        )
    assert ok is True
    assert cliente.table.return_value.upsert.call_count == 2
    payload_retry = cliente.table.return_value.upsert.call_args_list[1].args[0]
    assert "riscos" not in payload_retry
    assert payload_retry["premissas"] == ["p1"]


def test_salvar_premissas_falha_persistente_mesmo_sem_riscos_retorna_false():
    cliente = MagicMock()
    cliente.table.return_value.upsert.return_value.execute.side_effect = Exception("Supabase fora do ar")
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_premissas(
            "link", casa="X", titulo="Y", tickers=[], data_publicacao=None,
            tipo_documento=None, premissas=[], projecoes={}, recomendacao=None,
            preco_alvo=None, modelo=None, riscos=["r1"],
        )
    assert ok is False


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
# 2b. listar_premissas - filtro multi-casa (2026-11-01, pedido do Rodrigo)
# ============================================================

def test_listar_premissas_casa_string_unica_usa_eq_retrocompativel():
    """Comportamento ORIGINAL preservado: casa=str continua usando .eq()
    (filtro exato), nunca muda pra quem ja chamava assim."""
    cliente = MagicMock()
    consulta = cliente.table.return_value.select.return_value
    consulta.eq.return_value = consulta
    consulta.order.return_value = consulta
    consulta.execute.return_value = MagicMock(data=[])
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        store_mod.listar_premissas(casa="Genial Analisa")
    consulta.eq.assert_called_once_with("casa", "Genial Analisa")
    consulta.in_.assert_not_called()


def test_listar_premissas_casa_lista_usa_in_com_todas_as_casas():
    cliente = MagicMock()
    consulta = cliente.table.return_value.select.return_value
    consulta.in_.return_value = consulta
    consulta.order.return_value = consulta
    consulta.execute.return_value = MagicMock(data=[
        {"link": "a", "casa": "Genial Analisa"}, {"link": "b", "casa": "XP Investimentos"},
    ])
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        resultado = store_mod.listar_premissas(casa=["Genial Analisa", "XP Investimentos"])
    consulta.in_.assert_called_once_with("casa", ["Genial Analisa", "XP Investimentos"])
    consulta.eq.assert_not_called()
    assert {r["casa"] for r in resultado} == {"Genial Analisa", "XP Investimentos"}


def test_listar_premissas_casa_lista_vazia_nao_filtra_nenhum_campo():
    """Lista vazia ([]) e' tratada como 'nenhum filtro de casa' (mesma
    semantica de falsy ja usada pra tickers/casa=None) - nunca filtra
    por uma lista IN vazia (que devolveria sempre zero linhas no Postgres,
    resultado enganoso de 'nenhuma casa pedida' != 'nenhuma casa cobre')."""
    cliente = MagicMock()
    consulta = cliente.table.return_value.select.return_value
    consulta.order.return_value = consulta
    consulta.execute.return_value = MagicMock(data=[{"link": "a"}])
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        store_mod.listar_premissas(casa=[])
    consulta.in_.assert_not_called()
    consulta.eq.assert_not_called()


def test_listar_premissas_casa_none_nao_filtra_nenhum_campo():
    cliente = MagicMock()
    consulta = cliente.table.return_value.select.return_value
    consulta.order.return_value = consulta
    consulta.execute.return_value = MagicMock(data=[{"link": "a"}, {"link": "b"}])
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        resultado = store_mod.listar_premissas(casa=None)
    consulta.in_.assert_not_called()
    consulta.eq.assert_not_called()
    assert len(resultado) == 2


# ============================================================
# 3. Integracao em _gerar_resumo - so' persiste quando ha sinal real,
#    nunca derruba o resumo narrativo se a persistencia falhar
# ============================================================

def test_gerar_resumo_persiste_premissas_quando_tipo_acoes_tem_sinal():
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=("texto do relatorio", None)), \
         patch.object(resumir_mod, "resumir_com_groq", return_value=(
             "resumo narrativo qualquer", None,
             {"modelo": "openai/gpt-oss-20b", "preco_alvo": 55.0, "recomendacao": "COMPRA",
              "tipo_documento": "INICIACAO_COBERTURA", "premissas": ["ganho de market share"],
              "projecoes": {"receita": "12% a.a."}, "riscos": ["alta de insumos"]},
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
    assert kwargs["riscos"] == ["alta de insumos"]


def test_gerar_resumo_persiste_quando_so_riscos_foi_identificado():
    """Sinal real pode ser SO' riscos (sem premissas/projecoes/preco-alvo/
    recomendacao) - ainda vale persistir, nao e' uma linha vazia."""
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=("texto do relatorio", None)), \
         patch.object(resumir_mod, "resumir_com_groq", return_value=(
             "resumo narrativo qualquer", None,
             {"modelo": "m", "preco_alvo": None, "recomendacao": None,
              "tipo_documento": None, "premissas": [], "projecoes": {},
              "riscos": ["dependencia de licenca regulatoria pendente"]},
         )), \
         patch.object(resumir_mod.qualidade, "validar_fidelidade", return_value=None), \
         patch.object(resumir_mod.store, "salvar_resumo", return_value=True), \
         patch.object(resumir_mod.store, "salvar_premissas", return_value=True) as mock_premissas:
        resumir_mod._gerar_resumo(
            "https://casa.com/4", "titulo", None, "Genial Analisa", "ACOES",
        )
    mock_premissas.assert_called_once()
    assert mock_premissas.call_args.kwargs["riscos"] == ["dependencia de licenca regulatoria pendente"]


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
