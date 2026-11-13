# -*- coding: utf-8 -*-
"""Testes de data/empresa_perfil.py (missao noturna 2026-11-12/13,
frente PERFIL DE EMPRESA) - camada de consolidacao (funcao pura, zero
IA/rede nova) sobre data/research/comparador.py:comparar_ticker,
data/prices.py:obter_indicadores/obter_perfil_institucional e
data/news.py:obter_noticias. Mocka os 4 pontos de entrada - nunca faz
chamada de rede/IA real nem precisa de credencial.

Uso: pytest tests/test_empresa_perfil.py (venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.empresa_perfil as perfil_mod
from data.empresa_perfil import obter_perfil_empresa

_PERFIL_INST_COMPLETO = {
    "disponivel": True,
    "resumo_negocio": "A Empresa Teste atua na producao e distribuicao de commodities agricolas no Brasil.",
    "setor": "Basic Materials", "industria": "Agricultural Inputs", "pais": "Brazil",
    "website": "https://exemplo.com", "funcionarios": 5000,
    "fonte": "yfinance (tk.info)", "consultado_em": "2026-11-12T10:00:00+00:00",
}

_INDICADORES_COMPLETOS = {
    "valor_mercado": 1_000_000_000.0, "pl": 12.0, "pvp": 1.8, "dividend_yield": 4.5, "beta": 0.95,
    "roe": 18.0, "margem_liquida": 10.0, "margem_operacional": 14.0, "margem_ebitda": 22.0,
    "divida_liquida": 500_000_000.0, "divida_liquida_ebitda": 1.5, "ebitda": 300_000_000.0,
    "fluxo_caixa_livre": 200_000_000.0,
}


def _estado_atual_por_casa():
    return {
        "BTG": {
            "atual": {
                "casa": "BTG", "titulo": "Relatorio BTG", "link": "https://btg.com/r1",
                "data_publicacao": "2026-11-01",
                "premissas": ["A empresa e lider de mercado no segmento de fertilizantes",
                              "Crescimento de receita apoiado em expansao de volume"],
                "riscos": ["Alta dependencia de preco de commodities no custo de insumo"],
                "projecoes": {"receita": "crescimento de 10% no ano", "ebitda_margem": "estavel em 22%"},
                "recomendacao": "COMPRA", "preco_alvo": 50.0,
            },
            "categoria": "OTIMISTA",
        },
        "Nord": {
            "atual": {
                "casa": "Nord", "titulo": "Relatorio Nord", "link": "https://nord.com/r1",
                "data_publicacao": "2026-10-20",
                "premissas": ["Vantagem competitiva vem da escala logistica no escoamento da safra"],
                "riscos": ["Risco cambial afeta receita de exportacao"],
                "projecoes": {"lucro": "alta de 8% no proximo trimestre"},
                "recomendacao": "MANTER", "preco_alvo": 45.0,
            },
            "categoria": "NEUTRO",
        },
    }


def _comparacao_completa():
    return {
        "disponivel": True, "ticker": "TEST3", "casas": ["BTG", "Nord"],
        "estado_atual_por_casa": _estado_atual_por_casa(),
        "dispersao_precos_alvo": {"media": 47.5, "min": 45.0, "max": 50.0},
        "divergencia_recomendacao": {"existe": True},
        "divergencia_premissas": {
            "n_casas_total": 2, "n_casas_com_premissas_extraidas": 2, "amostra_insuficiente": False,
            "premissas_divergentes": [
                {"premissa": "A empresa e lider de mercado no segmento de fertilizantes",
                 "casas_que_mencionam": ["BTG"], "casas_que_nao_mencionam": ["Nord"]},
            ],
        },
        "evolucao_historica": {"BTG": {}, "Nord": {}},
        "cobertura_cruzada": None,
        "riscos": {
            "disponivel": True, "n_casas_total": 2, "n_casas_com_riscos_extraidos": 2,
            "por_casa": {
                "BTG": {"riscos": ["Alta dependencia de preco de commodities no custo de insumo"],
                       "data_publicacao": "2026-11-01", "link": "https://btg.com/r1"},
                "Nord": {"riscos": ["Risco cambial afeta receita de exportacao"],
                        "data_publicacao": "2026-10-20", "link": "https://nord.com/r1"},
            },
            "motivo": None,
        },
        "indicadores_adicionais": {"disponivel": True, "roe": 18.0, "roic": 15.0, "roic_disponivel": True,
                                   "riscos_mercado": []},
    }


_NOTICIAS_EXEMPLO = [
    {"ticker": "TEST3", "titulo": "Empresa Teste anuncia expansao", "data": "2026-11-10",
     "link": "https://noticia.com/1", "veiculos": ["Valor"], "selo": "ALTA"},
]


def _mock_tudo(comparacao=None, indicadores=None, perfil_inst=None, noticias=None):
    return (
        patch.object(perfil_mod, "comparar_ticker",
                     return_value=comparacao if comparacao is not None else _comparacao_completa()),
        patch.object(perfil_mod, "obter_indicadores",
                     return_value=indicadores if indicadores is not None else dict(_INDICADORES_COMPLETOS)),
        patch.object(perfil_mod, "obter_perfil_institucional",
                     return_value=perfil_inst if perfil_inst is not None else dict(_PERFIL_INST_COMPLETO)),
        patch.object(perfil_mod, "obter_noticias",
                     return_value=noticias if noticias is not None else list(_NOTICIAS_EXEMPLO)),
    )


# ============================================================
# Shape geral / normalizacao
# ============================================================

def test_ticker_e_normalizado_para_maiuscula():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("test3")
    assert perfil["ticker"] == "TEST3"


def test_shape_de_retorno_tem_todas_as_chaves_documentadas():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    for chave in ("ticker", "gerado_em", "identificacao", "indicadores_fundamentalistas",
                  "research", "noticias_recentes", "noticias_disponivel", "perguntas"):
        assert chave in perfil, f"chave ausente: {chave}"
    assert len(perfil["perguntas"]) == 18, f"esperava 18 perguntas, veio {len(perfil['perguntas'])}"


def test_todas_as_perguntas_tem_os_campos_obrigatorios():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    for chave, resp in perfil["perguntas"].items():
        for campo in ("pergunta", "fonte_primaria", "dado", "evidencias", "disponivel", "motivo_indisponivel"):
            assert campo in resp, f"pergunta {chave} sem campo {campo}"
        assert isinstance(resp["disponivel"], bool), f"pergunta {chave}: disponivel nao e bool"


# ============================================================
# Perguntas institucionais (1-4): yfinance
# ============================================================

def test_perguntas_institucionais_usam_resumo_de_negocio_real():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    for chave in ("o_que_a_empresa_faz", "como_ganha_dinheiro", "produtos", "clientes", "segmentos"):
        p = perfil["perguntas"][chave]
        assert p["disponivel"] is True
        assert p["dado"] == _PERFIL_INST_COMPLETO["resumo_negocio"]
    onde_atua = perfil["perguntas"]["onde_atua"]
    assert onde_atua["dado"]["pais_sede"] == "Brazil"


def test_perguntas_institucionais_indisponiveis_quando_yfinance_falha():
    perfil_vazio = {"disponivel": False, "resumo_negocio": None, "setor": None, "industria": None,
                    "pais": None, "website": None, "funcionarios": None, "fonte": None, "consultado_em": None}
    m1, m2, m3, m4 = _mock_tudo(perfil_inst=perfil_vazio)
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    for chave in ("o_que_a_empresa_faz", "como_ganha_dinheiro", "produtos", "clientes", "segmentos", "onde_atua"):
        p = perfil["perguntas"][chave]
        assert p["disponivel"] is False
        assert p["motivo_indisponivel"] is not None


# ============================================================
# Perguntas qualitativas via palavra-chave (5-7, 10): research
# ============================================================

def test_concorrentes_e_posicao_competitiva_e_vantagem_competitiva_encontrados_no_research():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    posicao = perfil["perguntas"]["posicao_competitiva"]
    assert posicao["disponivel"] is True
    assert any("lider de mercado" in t for t in posicao["dado"])
    assert posicao["evidencias"][0]["casa"] == "BTG"
    assert posicao["evidencias"][0]["link"] == "https://btg.com/r1"

    vantagem = perfil["perguntas"]["vantagens_competitivas"]
    assert vantagem["disponivel"] is True
    assert any("escala logistica" in t for t in vantagem["dado"])


def test_concorrentes_sem_mencao_no_research_fica_indisponivel_com_motivo():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    concorrentes = perfil["perguntas"]["concorrentes"]
    # nenhuma premissa/risco do fixture usa palavra-chave de concorrencia
    assert concorrentes["disponivel"] is False
    assert concorrentes["motivo_indisponivel"] is not None
    assert concorrentes["dado"] == []


def test_estrutura_de_custo_encontrada_via_palavra_chave_insumo():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    custo = perfil["perguntas"]["estrutura_de_custo"]
    assert custo["disponivel"] is True
    assert any("insumo" in t for t in custo["dado"])


def test_palavra_chave_ignora_acento_e_caixa():
    assert perfil_mod._bate_palavra_chave("A EMPRESA É LÍDER DE MERCADO", perfil_mod._PALAVRAS_POSICAO_COMPETITIVA)
    assert perfil_mod._bate_palavra_chave("lideranca consolidada no setor", perfil_mod._PALAVRAS_POSICAO_COMPETITIVA)
    assert not perfil_mod._bate_palavra_chave("texto sem nenhuma palavra relevante", perfil_mod._PALAVRAS_POSICAO_COMPETITIVA)


# ============================================================
# Drivers de receita / pressoes de margem (8-9): projecoes por casa
# ============================================================

def test_drivers_de_receita_usa_projecao_dedicada_por_casa():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    receita = perfil["perguntas"]["drivers_de_receita"]
    assert receita["disponivel"] is True
    textos = [e["texto"] for e in receita["evidencias"]]
    assert "crescimento de 10% no ano" in textos
    assert any(e["casa"] == "BTG" for e in receita["evidencias"])


def test_pressoes_de_margem_combina_margens_atuais_e_projecao_por_casa():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    margem = perfil["perguntas"]["pressoes_de_margem"]
    assert margem["disponivel"] is True
    assert margem["dado"]["margens_atuais"]["margem_ebitda_pct"] == 22.0
    assert "estavel em 22%" in margem["dado"]["evidencias_research"]


# ============================================================
# Divida / geracao de caixa (11-12): FATO numerico direto (yfinance)
# ============================================================

def test_divida_e_geracao_de_caixa_vem_direto_dos_indicadores():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    divida = perfil["perguntas"]["divida"]
    assert divida["disponivel"] is True
    assert divida["dado"]["divida_liquida"] == 500_000_000.0
    assert divida["dado"]["divida_liquida_ebitda"] == 1.5

    caixa = perfil["perguntas"]["geracao_de_caixa"]
    assert caixa["disponivel"] is True
    assert caixa["dado"] == 200_000_000.0


def test_divida_indisponivel_quando_yfinance_nao_reporta():
    m1, m2, m3, m4 = _mock_tudo(indicadores={})
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    divida = perfil["perguntas"]["divida"]
    assert divida["disponivel"] is False
    assert divida["motivo_indisponivel"] is not None
    caixa = perfil["perguntas"]["geracao_de_caixa"]
    assert caixa["disponivel"] is False


# ============================================================
# Riscos (14) / o que quebraria a tese (16): campo dedicado
# ============================================================

def test_riscos_repassa_campo_dedicado_com_atribuicao_por_casa():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    riscos = perfil["perguntas"]["riscos"]
    assert riscos["disponivel"] is True
    assert len(riscos["evidencias"]) == 2
    casas = {e["casa"] for e in riscos["evidencias"]}
    assert casas == {"BTG", "Nord"}


def test_riscos_indisponivel_quando_nenhuma_casa_extraiu_risco():
    comparacao = _comparacao_completa()
    comparacao["riscos"] = {"disponivel": False, "n_casas_total": 2, "n_casas_com_riscos_extraidos": 0,
                             "por_casa": {}, "motivo": "nenhuma publicacao com risco extraido"}
    m1, m2, m3, m4 = _mock_tudo(comparacao=comparacao)
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    riscos = perfil["perguntas"]["riscos"]
    assert riscos["disponivel"] is False
    assert riscos["motivo_indisponivel"] == "nenhuma publicacao com risco extraido"


def test_o_que_quebraria_a_tese_inclui_riscos_e_divergencia_entre_casas():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    quebra_tese = perfil["perguntas"]["o_que_quebraria_a_tese"]
    assert quebra_tese["disponivel"] is True
    assert len(quebra_tese["dado"]["riscos"]) == 2
    assert quebra_tese["dado"]["divergencia_entre_casas"][0]["premissa"] == (
        "A empresa e lider de mercado no segmento de fertilizantes"
    )


# ============================================================
# Research totalmente indisponivel (banco fora do ar)
# ============================================================

def test_research_indisponivel_nao_quebra_perfil_so_marca_perguntas_dependentes():
    m1, m2, m3, m4 = _mock_tudo(comparacao={"disponivel": False, "motivo": "banco indisponivel"})
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    assert perfil["research"]["disponivel"] is False
    assert perfil["research"]["motivo"] == "banco indisponivel"
    # perguntas que dependem SO' de research ficam indisponiveis...
    for chave in ("concorrentes", "riscos", "drivers_de_receita"):
        assert perfil["perguntas"][chave]["disponivel"] is False
    # ...mas as que vem de yfinance continuam disponiveis normalmente
    assert perfil["perguntas"]["o_que_a_empresa_faz"]["disponivel"] is True
    assert perfil["perguntas"]["divida"]["disponivel"] is True


# ============================================================
# Noticias: metadado, nunca resumo de IA
# ============================================================

def test_noticias_recentes_sao_metadado_sem_campo_de_resumo():
    m1, m2, m3, m4 = _mock_tudo()
    with m1, m2, m3, m4:
        perfil = obter_perfil_empresa("TEST3")
    assert perfil["noticias_disponivel"] is True
    assert perfil["noticias_recentes"] == _NOTICIAS_EXEMPLO
    for noticia in perfil["noticias_recentes"]:
        assert "resumo" not in noticia


def test_noticias_indisponivel_vira_lista_vazia_com_flag_propria():
    m1, m2, m3, _ = _mock_tudo()
    with m1, m2, m3, patch.object(perfil_mod, "obter_noticias", return_value=None):
        perfil = obter_perfil_empresa("TEST3")
    assert perfil["noticias_disponivel"] is False
    assert perfil["noticias_recentes"] == []


# ============================================================
# Resiliencia: nenhuma excecao de dependencia propaga
# ============================================================

def test_excecao_em_qualquer_fonte_nunca_propaga():
    with patch.object(perfil_mod, "comparar_ticker", side_effect=RuntimeError("falha")), \
         patch.object(perfil_mod, "obter_indicadores", side_effect=RuntimeError("falha")), \
         patch.object(perfil_mod, "obter_perfil_institucional", side_effect=RuntimeError("falha")), \
         patch.object(perfil_mod, "obter_noticias", side_effect=RuntimeError("falha")):
        perfil = obter_perfil_empresa("TEST3")  # nao deve lancar
    assert perfil["ticker"] == "TEST3"
    assert perfil["research"]["disponivel"] is False
    assert perfil["noticias_disponivel"] is False
    assert len(perfil["perguntas"]) == 18
