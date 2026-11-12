# -*- coding: utf-8 -*-
"""data/research/classificacao.py - identificacao de ticker(s) no CORPO
do texto de um relatorio (nao so' no metadado da fonte) + classificacao
por setor (reusa config.IBOVESPA_SETORES). Zero IA, zero rede, zero
Supabase - tudo funcao pura, testada so' com texto/listas em memoria.

Uso: pytest tests/test_research_classificacao.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.classificacao as classif_mod
from data.research.classificacao import (
    classificar_documento,
    classificar_setor,
    classificar_setores,
    identificar_tickers_no_texto,
)


# ---------------------------------------------------------------------
# identificar_tickers_no_texto
# ---------------------------------------------------------------------

def test_identifica_ticker_conhecido_mencionado_no_corpo():
    texto = "A Petrobras (PETR4) anunciou novo investimento no pre-sal."
    assert identificar_tickers_no_texto(texto) == ["PETR4"]


def test_identifica_varios_tickers_sem_duplicar():
    texto = "VALE3 caiu apos noticia envolvendo CSNA3 e GGBR4; CSNA3 reagiu no pregao."
    assert identificar_tickers_no_texto(texto) == ["CSNA3", "GGBR4", "VALE3"]


def test_ticker_com_sufixo_de_2_digitos_e_reconhecido():
    texto = "SANB11 e BPAC11 fecharam estaveis."
    assert identificar_tickers_no_texto(texto) == ["BPAC11", "SANB11"]


def test_nao_inventa_ticker_fora_do_universo_conhecido():
    """4 letras + numero que BATE o formato de ticker B3 mas nao esta
    cadastrado em nenhum dict de config.py (IBOVESPA_SETORES/
    TICKER_ALIASES/ATIVOS_CADASTRO_US) nunca e' aceito como ticker real -
    evita falso positivo (ex: uma sigla+numero de nota de rodape)."""
    texto = "Ver nota ZZZZ9 no apendice do relatorio."
    assert identificar_tickers_no_texto(texto) == []


def test_texto_vazio_ou_none_nao_quebra():
    assert identificar_tickers_no_texto("") == []
    assert identificar_tickers_no_texto(None) == []


def test_case_insensitive():
    texto = "petr4 subiu 2% no pregao de hoje."
    assert identificar_tickers_no_texto(texto) == ["PETR4"]


def test_bdr_cadastrado_em_ticker_aliases_e_reconhecido():
    texto = "A acao do Nubank, ROXO34, operou em alta na B3."
    assert identificar_tickers_no_texto(texto) == ["ROXO34"]


# ---------------------------------------------------------------------
# classificar_setor / classificar_setores
# ---------------------------------------------------------------------

def test_classificar_setor_ticker_conhecido():
    assert classificar_setor("PETR4") == "Petróleo e Gás"
    assert classificar_setor("itub4") == "Bancos"  # normaliza case


def test_classificar_setor_ticker_desconhecido_retorna_none_nunca_outros():
    assert classificar_setor("XXXX9") is None


def test_classificar_setor_vazio_retorna_none():
    assert classificar_setor("") is None
    assert classificar_setor(None) is None


def test_classificar_setores_lista():
    resultado = classificar_setores(["PETR4", "VALE3", "XXXX9"])
    assert resultado == {
        "PETR4": "Petróleo e Gás",
        "VALE3": "Mineração e Siderurgia",
        "XXXX9": None,
    }


def test_classificar_setores_lista_vazia():
    assert classificar_setores([]) == {}
    assert classificar_setores(None) == {}


# ---------------------------------------------------------------------
# classificar_documento (visao combinada)
# ---------------------------------------------------------------------

def test_classificar_documento_sem_texto_so_usa_metadado():
    resultado = classificar_documento(["vale3"], texto=None)
    assert resultado["tickers_metadado"] == ["VALE3"]
    assert resultado["tickers_no_corpo"] == []  # nao tentou procurar (texto None)
    assert resultado["tickers_novos_no_corpo"] == []
    assert resultado["tickers_todos"] == ["VALE3"]
    assert resultado["setor_por_ticker"] == {"VALE3": "Mineração e Siderurgia"}
    assert resultado["setores_identificados"] == ["Mineração e Siderurgia"]


def test_classificar_documento_encontra_mencao_cruzada_no_corpo():
    """Caso real do pedido (item 2): relatorio categorizado so' sob
    VALE3 na fonte, mas o corpo tambem menciona CSNA3 de passagem -
    tickers_novos_no_corpo precisa capturar isso explicitamente."""
    texto = "A Vale (VALE3) comentou sinergias com a siderurgia, citando a CSNA3 como referencia."
    resultado = classificar_documento(["VALE3"], texto=texto)
    assert resultado["tickers_metadado"] == ["VALE3"]
    assert resultado["tickers_no_corpo"] == ["CSNA3", "VALE3"]
    assert resultado["tickers_novos_no_corpo"] == ["CSNA3"]
    assert resultado["tickers_todos"] == ["CSNA3", "VALE3"]
    assert resultado["setor_por_ticker"] == {
        "CSNA3": "Mineração e Siderurgia", "VALE3": "Mineração e Siderurgia",
    }


def test_classificar_documento_texto_vazio_string_tambem_tenta_procurar():
    """Diferente de texto=None (nao tenta) - string vazia "" tenta e
    simplesmente nao acha nada, mesmo resultado final mas caminho
    diferente (documentado no docstring do modulo)."""
    resultado = classificar_documento(["PETR4"], texto="")
    assert resultado["tickers_no_corpo"] == []
    assert resultado["tickers_todos"] == ["PETR4"]


def test_classificar_documento_sem_nenhum_ticker():
    resultado = classificar_documento(None, texto=None)
    assert resultado == {
        "tickers_metadado": [], "tickers_no_corpo": [], "tickers_novos_no_corpo": [],
        "tickers_todos": [], "setor_por_ticker": {}, "setores_identificados": [],
    }


def test_universo_conhecido_nao_depende_de_rede():
    """Confirma que o universo de validacao e' puramente estatico (nao
    importa data/ibovespa.py, que bate rede/Streamlit cache, nem
    streamlit) - garante que identificar_tickers_no_texto pode rodar
    dentro de resumir.py:_gerar_resumo sem custo/dependencia extra."""
    assert not hasattr(classif_mod, "st")
    assert not hasattr(classif_mod, "obter_composicao_oficial")
    assert isinstance(classif_mod._UNIVERSO_CONHECIDO, frozenset)
