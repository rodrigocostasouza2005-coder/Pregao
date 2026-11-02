# -*- coding: utf-8 -*-
"""Agente Comparador de Casas de Research (Fase D, 2026-10-30) -
data/research/comparador.py:comparar_ticker/montar_relatorio_comparativo.
Le so' a biblioteca PERMANENTE (research_premissas, ver
data/research/store.py:listar_premissas) - zero rede/Supabase real,
tudo mockado. Zero chamada de IA (confirmado por teste dedicado no
final do arquivo)."""
import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.comparador as comp_mod


def _pub(casa, link, data_publicacao=None, extraido_em=None, recomendacao=None,
          preco_alvo=None, premissas=None, projecoes=None, tipo_documento=None, titulo="relatorio",
          riscos=None):
    return {
        "link": link, "casa": casa, "titulo": titulo, "tickers": ["WEGE3"],
        "data_publicacao": data_publicacao, "extraido_em": extraido_em,
        "tipo_documento": tipo_documento, "premissas": premissas or [],
        "projecoes": projecoes or {}, "recomendacao": recomendacao,
        "preco_alvo": preco_alvo, "modelo_extracao": "modelo-teste",
        "riscos": riscos or [],
    }


@pytest.fixture(autouse=True)
def _mock_linha_valuation_padrao():
    """Autouse: NENHUM teste deste arquivo pode bater yfinance/rede real
    via data/research/comparador.py:_indicadores_fundamentalistas (usa
    data.radar.linha_valuation). Default "sem dado" - testes que querem
    verificar o caminho com ROE/riscos_mercado reais sobrescrevem com seu
    proprio `with patch.object(comp_mod, "linha_valuation", ...)` dentro
    do corpo do teste (mock aninhado, vale só ali)."""
    with patch.object(comp_mod, "linha_valuation", return_value={
        "roe": None, "alerta_qualidade": [], "consultado_em": None,
    }):
        yield


def _mock_historico_vazio():
    return patch.multiple(
        comp_mod.historico,
        historico_ticker=MagicMock(return_value=[]),
        mudancas_hoje=MagicMock(return_value=[]),
    )


def _mock_cobertura_vazia():
    return patch.object(comp_mod, "cobertura_cruzada_casas", return_value={
        "ticker": "WEGE3", "janela_dias": 30, "cobertura": [], "sem_cobertura": [], "divergencia": None,
    })


# ============================================================
# 1. Normalizacao de recomendacao
# ============================================================

def test_normaliza_termos_conhecidos_de_cada_categoria():
    assert comp_mod._normalizar_recomendacao("COMPRA") == comp_mod.CATEGORIA_OTIMISTA
    assert comp_mod._normalizar_recomendacao("outperform") == comp_mod.CATEGORIA_OTIMISTA
    assert comp_mod._normalizar_recomendacao("Overweight") == comp_mod.CATEGORIA_OTIMISTA
    assert comp_mod._normalizar_recomendacao("MANTER") == comp_mod.CATEGORIA_NEUTRO
    assert comp_mod._normalizar_recomendacao("Hold") == comp_mod.CATEGORIA_NEUTRO
    assert comp_mod._normalizar_recomendacao("VENDA") == comp_mod.CATEGORIA_CAUTELOSO
    assert comp_mod._normalizar_recomendacao("underperform") == comp_mod.CATEGORIA_CAUTELOSO


def test_termo_desconhecido_vira_nao_classificado_nunca_chuta():
    assert comp_mod._normalizar_recomendacao("ANALISANDO") == comp_mod.CATEGORIA_NAO_CLASSIFICADO
    assert comp_mod._normalizar_recomendacao("xyz123") == comp_mod.CATEGORIA_NAO_CLASSIFICADO


def test_ausencia_de_recomendacao_e_none_nao_nao_classificado():
    assert comp_mod._normalizar_recomendacao(None) is None
    assert comp_mod._normalizar_recomendacao("") is None
    assert comp_mod._normalizar_recomendacao("   ") is None


# ============================================================
# 2. Regra de comparabilidade (item 7)
# ============================================================

def test_comparavel_mesmo_campo_e_true():
    assert comp_mod._comparavel(comp_mod.CAMPO_PRECO_ALVO, comp_mod.CAMPO_PRECO_ALVO) is True
    assert comp_mod._comparavel(comp_mod.CAMPO_PROJECAO_RECEITA, comp_mod.CAMPO_PROJECAO_RECEITA) is True


def test_comparavel_campos_de_natureza_diferente_e_false():
    assert comp_mod._comparavel(comp_mod.CAMPO_PRECO_ALVO, comp_mod.CAMPO_PROJECAO_RECEITA) is False
    assert comp_mod._comparavel(comp_mod.CAMPO_DATA_PUBLICACAO, comp_mod.CAMPO_PROJECAO_RECEITA) is False
    assert comp_mod._comparavel(comp_mod.CAMPO_PROJECAO_RECEITA, comp_mod.CAMPO_PROJECAO_EBITDA_MARGEM) is False


def test_comparavel_campo_desconhecido_e_false():
    assert comp_mod._comparavel("campo_inventado", "campo_inventado") is False


def test_data_publicacao_nunca_e_comparavel_com_texto_de_projecao():
    """data_publicacao (metadado de quando a casa publicou) nunca e'
    confundida com periodo projetado mencionado DENTRO do texto livre
    de projecoes."""
    assert comp_mod._comparavel(comp_mod.CAMPO_DATA_PUBLICACAO, comp_mod.CAMPO_PROJECAO_RECEITA) is False
    assert comp_mod._comparavel(comp_mod.CAMPO_DATA_PUBLICACAO, comp_mod.CAMPO_PROJECAO_EBITDA_MARGEM) is False
    assert comp_mod._comparavel(comp_mod.CAMPO_DATA_PUBLICACAO, comp_mod.CAMPO_PROJECAO_LUCRO) is False


# ============================================================
# 3. Ausencia de dados / banco indisponivel / sem publicacoes
# ============================================================

def test_banco_indisponivel_nunca_lanca_excecao():
    with patch.object(comp_mod, "listar_premissas", return_value=None):
        resultado = comp_mod.comparar_ticker("WEGE3")
    assert resultado == {"disponivel": False, "motivo": "banco indisponivel"}


def test_ticker_sem_nenhuma_publicacao():
    with patch.object(comp_mod, "listar_premissas", return_value=[]):
        resultado = comp_mod.comparar_ticker("WEGE3")
    assert resultado["disponivel"] is True
    assert resultado["casas"] == []
    assert "sem publicacoes estruturadas" in resultado["motivo"]


def test_relatorio_banco_indisponivel_propaga_estado_honesto():
    with patch.object(comp_mod, "listar_premissas", return_value=None):
        relatorio = comp_mod.montar_relatorio_comparativo("WEGE3")
    assert relatorio["disponivel"] is False
    assert relatorio["motivo"] == "banco indisponivel"


def test_relatorio_sem_publicacoes_tem_todas_as_9_secoes_com_estado_honesto():
    with patch.object(comp_mod, "listar_premissas", return_value=[]):
        relatorio = comp_mod.montar_relatorio_comparativo("WEGE3")
    assert relatorio["disponivel"] is True
    assert relatorio["tabela_comparativa"] == []
    assert relatorio["fontes_evidencias"] == []
    assert relatorio["dispersao_precos_alvo"]["amostra_insuficiente"] is True
    assert relatorio["divergencias_premissas"]["recomendacao"]["casa_mais_otimista"] is None
    assert relatorio["riscos"]["disponivel"] is False
    assert relatorio["riscos"]["n_casas_total"] == 0
    assert relatorio["indicadores_adicionais"]["disponivel"] is True  # consulta funcionou, so' nao tinha ROE no mock padrao
    assert relatorio["indicadores_adicionais"]["roic_disponivel"] is False


# ============================================================
# 4. Riscos por casa / ROE-ROIC: nunca inventado, fontes rastreaveis
# ============================================================

def test_riscos_por_casa_ausente_quando_nenhuma_publicacao_tem_risco_extraido():
    publicacoes = [_pub("Genial Analisa", "l1", data_publicacao="2026-10-01", recomendacao="COMPRA", preco_alvo=50.0)]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        resultado = comp_mod.comparar_ticker("WEGE3")
    assert resultado["riscos"]["disponivel"] is False
    assert resultado["riscos"]["n_casas_total"] == 1
    assert resultado["riscos"]["n_casas_com_riscos_extraidos"] == 0
    assert resultado["riscos"]["por_casa"] == {}
    assert "nunca inventado" in resultado["riscos"]["motivo"]


def test_riscos_por_casa_presente_com_fonte_rastreavel():
    publicacoes = [
        _pub("Genial Analisa", "l1", data_publicacao="2026-10-01", recomendacao="COMPRA", preco_alvo=50.0,
             riscos=["alta de insumos pode comprimir margem", "atraso regulatorio na licenca"]),
        _pub("XP Investimentos", "l2", data_publicacao="2026-10-02", recomendacao="MANTER"),
    ]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        resultado = comp_mod.comparar_ticker("WEGE3")
    riscos = resultado["riscos"]
    assert riscos["disponivel"] is True
    assert riscos["n_casas_total"] == 2
    assert riscos["n_casas_com_riscos_extraidos"] == 1
    assert riscos["por_casa"]["Genial Analisa"]["riscos"] == [
        "alta de insumos pode comprimir margem", "atraso regulatorio na licenca",
    ]
    assert riscos["por_casa"]["Genial Analisa"]["link"] == "l1"
    assert riscos["por_casa"]["Genial Analisa"]["data_publicacao"] == "2026-10-01"
    assert "XP Investimentos" not in riscos["por_casa"]  # nao tinha risco extraido - nunca inventado


def test_riscos_por_casa_evolucao_historica_preserva_riscos_de_publicacoes_antigas():
    publicacoes = [
        _pub("Genial Analisa", "l1", data_publicacao="2026-10-01", recomendacao="COMPRA",
             riscos=["risco antigo identificado"]),
        _pub("Genial Analisa", "l2", data_publicacao="2026-10-15", recomendacao="COMPRA",
             riscos=["risco novo identificado"]),
    ]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        resultado = comp_mod.comparar_ticker("WEGE3")
    evolucao = resultado["evolucao_historica"]["Genial Analisa"]
    # estado atual = publicacao mais recente (l2)
    assert resultado["riscos"]["por_casa"]["Genial Analisa"]["riscos"] == ["risco novo identificado"]
    # historico preserva o risco da publicacao MAIS ANTIGA (l1), nunca confundido com o atual
    assert evolucao["publicacoes_historicas"][0]["link"] == "l1"
    assert evolucao["publicacoes_historicas"][0]["riscos"] == ["risco antigo identificado"]


def test_roe_real_flui_do_yfinance_via_linha_valuation():
    """roe vem de linha_valuation ja em PONTOS PERCENTUAIS (ex: 18.3 =
    18,3%, ver data/prices.py:_pct_ou_none) - nunca fracao 0-1."""
    publicacoes = [_pub("Genial Analisa", "l1", data_publicacao="2026-10-01", recomendacao="COMPRA", preco_alvo=50.0)]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         patch.object(comp_mod, "linha_valuation", return_value={
             "roe": 18.3, "alerta_qualidade": ["P/L negativo nos ultimos 12 meses"], "consultado_em": "2026-11-01T10:00:00",
         }), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        resultado = comp_mod.comparar_ticker("WEGE3")
    ind = resultado["indicadores_adicionais"]
    assert ind["disponivel"] is True
    assert ind["roe"] == 18.3
    assert ind["riscos_mercado"] == ["P/L negativo nos ultimos 12 meses"]
    assert ind["consultado_em"] == "2026-11-01T10:00:00"


def test_roic_sempre_indisponivel_com_motivo_mesmo_com_roe_real():
    publicacoes = [_pub("Genial Analisa", "l1", data_publicacao="2026-10-01", recomendacao="COMPRA")]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         patch.object(comp_mod, "linha_valuation", return_value={"roe": 20.0, "alerta_qualidade": [], "consultado_em": None}), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        resultado = comp_mod.comparar_ticker("WEGE3")
    ind = resultado["indicadores_adicionais"]
    assert ind["roic"] is None
    assert ind["roic_disponivel"] is False
    assert "yfinance" in ind["roic_motivo"]
    assert "balanco" in ind["roic_motivo"].lower() or "balanço" in ind["roic_motivo"].lower()


def test_indicadores_fundamentalistas_falha_de_consulta_nunca_propaga():
    publicacoes = [_pub("Genial Analisa", "l1", data_publicacao="2026-10-01", recomendacao="COMPRA")]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         patch.object(comp_mod, "linha_valuation", side_effect=RuntimeError("yfinance fora do ar")), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        resultado = comp_mod.comparar_ticker("WEGE3")  # nunca lanca excecao
    ind = resultado["indicadores_adicionais"]
    assert ind["disponivel"] is False
    assert ind["roe"] is None
    assert ind["roic_disponivel"] is False


# ============================================================
# 5. Dispersao de precos-alvo - 2+/1/0 casas, NUNCA trata None como 0
# ============================================================

def _estado(casas_precos):
    """{casa: preco_alvo|None} -> estado_atual_por_casa no formato
    esperado por _dispersao_precos_alvo."""
    return {
        casa: {"atual": {comp_mod.CAMPO_PRECO_ALVO: preco}, "categoria": None}
        for casa, preco in casas_precos.items()
    }


def test_dispersao_com_2_mais_casas_calcula_estatisticas():
    estado = _estado({"Genial Analisa": 50.0, "XP Investimentos": 60.0, "BTG Pactual Research": 55.0})
    dispersao = comp_mod._dispersao_precos_alvo(estado)
    assert dispersao["amostra_insuficiente"] is False
    assert dispersao["n_casas_com_preco_alvo"] == 3
    assert dispersao["minimo"] == 50.0
    assert dispersao["maximo"] == 60.0
    assert dispersao["media"] == 55.0
    assert dispersao["mediana"] == 55.0


def test_dispersao_com_1_casa_e_amostra_insuficiente():
    estado = _estado({"Genial Analisa": 50.0})
    dispersao = comp_mod._dispersao_precos_alvo(estado)
    assert dispersao["amostra_insuficiente"] is True
    assert dispersao["n_casas_com_preco_alvo"] == 1
    assert dispersao["minimo"] == dispersao["maximo"] == 50.0
    assert "1 dado so" in dispersao["resumo"]


def test_dispersao_com_0_casas_tudo_none():
    estado = _estado({"Genial Analisa": None, "XP Investimentos": None})
    dispersao = comp_mod._dispersao_precos_alvo(estado)
    assert dispersao["amostra_insuficiente"] is True
    assert dispersao["n_casas_com_preco_alvo"] == 0
    assert dispersao["minimo"] is None
    assert dispersao["maximo"] is None
    assert dispersao["media"] is None


def test_dispersao_nunca_trata_ausencia_como_zero():
    """Criterio de aceite explicito do Rodrigo: 3 casas, 1 com
    preco_alvo=None e 2 com valores reais - a media/min/max tem que
    considerar SO' as 2 reais (nunca contar a ausente como 0, o que
    distorceria a media pra baixo), e o resultado precisa deixar
    explicito que foi calculado com 2 de 3 casas."""
    estado = _estado({"Genial Analisa": None, "XP Investimentos": 40.0, "BTG Pactual Research": 60.0})
    dispersao = comp_mod._dispersao_precos_alvo(estado)
    assert dispersao["n_casas_total"] == 3
    assert dispersao["n_casas_com_preco_alvo"] == 2
    assert dispersao["amostra_insuficiente"] is False
    # media correta seria (40+60)/2=50, NUNCA (0+40+60)/3=33.33 (que
    # trataria a ausencia como zero)
    assert dispersao["media"] == 50.0
    assert dispersao["minimo"] == 40.0
    assert dispersao["maximo"] == 60.0
    assert "2 de 3" in dispersao["resumo"]
    assert "Genial Analisa" not in dispersao["precos_por_casa"]


def test_dispersao_premissa_de_moeda_brl_explicita():
    estado = _estado({"Genial Analisa": 50.0, "XP Investimentos": 60.0})
    dispersao = comp_mod._dispersao_precos_alvo(estado)
    assert dispersao["moeda"] == "BRL"


# ============================================================
# 6. Comparacao de projecoes - nunca compara campos de natureza
#    diferente (ja cobre a regra _comparavel acima); aqui testa que a
#    tabela comparativa preserva cada projecao isolada, sem misturar.
# ============================================================

def test_tabela_comparativa_preserva_projecoes_isoladas_sem_misturar_campos():
    publicacoes = [_pub(
        "Genial Analisa", "l1", data_publicacao="2026-10-01", recomendacao="COMPRA", preco_alvo=55.0,
        projecoes={"receita": "crescimento de 12% a.a.", "ebitda_margem": "margem de 22%"},
    )]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        comparacao = comp_mod.comparar_ticker("WEGE3")
    tabela = comp_mod._tabela_comparativa(comparacao["estado_atual_por_casa"])
    linha = tabela[0]
    assert linha["projecao_receita"] == "crescimento de 12% a.a."
    assert linha["projecao_ebitda_margem"] == "margem de 22%"
    assert linha["projecao_lucro"] is None  # nao informado - None explicito, nunca omitido
    assert linha["preco_alvo"] == 55.0
    # preco_alvo nunca e' igual/confundido com o texto de projecao
    assert linha["preco_alvo"] != linha["projecao_receita"]


# ============================================================
# 7. Identificacao de divergencias - numerica vs qualitativa, 0/1/2+
# ============================================================

def _estado_full(casas: dict) -> dict:
    """casas: {nome: {"preco_alvo": ..., "recomendacao": ...}}"""
    estado = {}
    for casa, dados in casas.items():
        estado[casa] = {
            "atual": {comp_mod.CAMPO_PRECO_ALVO: dados.get("preco_alvo"),
                      comp_mod.CAMPO_RECOMENDACAO: dados.get("recomendacao"),
                      "premissas": dados.get("premissas") or []},
            "categoria": comp_mod._normalizar_recomendacao(dados.get("recomendacao")),
        }
    return estado


def test_divergencia_numerica_e_qualitativa_juntas_com_2_mais_casas():
    estado = _estado_full({
        "Genial Analisa": {"preco_alvo": 50.0, "recomendacao": "COMPRA"},
        "XP Investimentos": {"preco_alvo": 30.0, "recomendacao": "VENDA"},
    })
    dispersao = comp_mod._dispersao_precos_alvo(estado)
    divergencia = comp_mod._divergencia_recomendacao(estado, dispersao)
    assert divergencia["numerica"] is True
    assert divergencia["qualitativa"] is True
    assert divergencia["casa_mais_otimista"] == "Genial Analisa"
    assert divergencia["casa_mais_cautelosa"] == "XP Investimentos"
    assert "preco_alvo" in divergencia["criterio_otimismo"]


def test_sem_divergencia_quando_precos_e_categorias_iguais():
    estado = _estado_full({
        "Genial Analisa": {"preco_alvo": 50.0, "recomendacao": "COMPRA"},
        "XP Investimentos": {"preco_alvo": 50.0, "recomendacao": "COMPRA"},
    })
    dispersao = comp_mod._dispersao_precos_alvo(estado)
    divergencia = comp_mod._divergencia_recomendacao(estado, dispersao)
    assert divergencia["numerica"] is False
    assert divergencia["qualitativa"] is False


def test_divergencia_com_1_casa_e_amostra_insuficiente_nunca_afirma_divergencia():
    estado = _estado_full({"Genial Analisa": {"preco_alvo": 50.0, "recomendacao": "COMPRA"}})
    dispersao = comp_mod._dispersao_precos_alvo(estado)
    divergencia = comp_mod._divergencia_recomendacao(estado, dispersao)
    assert divergencia["numerica"] is False
    assert divergencia["qualitativa"] is False
    assert divergencia["amostra_insuficiente_qualitativa"] is True
    assert divergencia["casa_mais_otimista"] is None  # 1 casa so' - nao ha "mais otimista que quem"


def test_divergencia_com_0_casas_classificaveis():
    estado = _estado_full({
        "Genial Analisa": {"preco_alvo": None, "recomendacao": None},
        "XP Investimentos": {"preco_alvo": None, "recomendacao": None},
    })
    dispersao = comp_mod._dispersao_precos_alvo(estado)
    divergencia = comp_mod._divergencia_recomendacao(estado, dispersao)
    assert divergencia["numerica"] is False
    assert divergencia["qualitativa"] is False
    assert divergencia["casa_mais_otimista"] is None
    assert divergencia["casa_mais_cautelosa"] is None


def test_criterio_otimismo_cai_para_categoria_quando_menos_de_2_precos():
    estado = _estado_full({
        "Genial Analisa": {"preco_alvo": 50.0, "recomendacao": "COMPRA"},
        "XP Investimentos": {"preco_alvo": None, "recomendacao": "VENDA"},
    })
    _, _, criterio = comp_mod._casa_mais_otimista_cautelosa(estado)
    assert "categoria_recomendacao" in criterio


def test_divergencia_premissas_aparece_so_quando_ausente_em_alguma_casa():
    estado = _estado_full({
        "Genial Analisa": {"premissas": ["expansao de capacidade", "ganho de market share"]},
        "XP Investimentos": {"premissas": ["expansao de capacidade"]},
    })
    resultado = comp_mod._divergencia_premissas(estado)
    assert resultado["amostra_insuficiente"] is False
    divergentes = resultado["premissas_divergentes"]
    assert len(divergentes) == 1
    assert divergentes[0]["premissa"] == "ganho de market share"
    assert divergentes[0]["casas_que_mencionam"] == ["Genial Analisa"]
    assert divergentes[0]["casas_que_nao_mencionam"] == ["XP Investimentos"]


def test_divergencia_premissas_amostra_insuficiente_com_menos_de_2_casas_com_premissas():
    estado = _estado_full({
        "Genial Analisa": {"premissas": ["expansao de capacidade"]},
        "XP Investimentos": {"premissas": []},
    })
    resultado = comp_mod._divergencia_premissas(estado)
    assert resultado["amostra_insuficiente"] is True
    assert resultado["n_casas_com_premissas_extraidas"] == 1


# ============================================================
# 8. Consenso - amostra insuficiente / empate / maioria clara
# ============================================================

def test_consenso_maioria_clara():
    estado = _estado_full({
        "Genial Analisa": {"recomendacao": "COMPRA"},
        "XP Investimentos": {"recomendacao": "COMPRA"},
        "BTG Pactual Research": {"recomendacao": "MANTER"},
    })
    consenso = comp_mod._consenso(estado)
    assert consenso["categoria_mais_comum"] == comp_mod.CATEGORIA_OTIMISTA
    assert consenso["contagem_por_categoria"][comp_mod.CATEGORIA_OTIMISTA] == 2
    assert consenso["amostra_insuficiente"] is False
    assert consenso["empate"] is False


def test_consenso_empate_nunca_escolhe_arbitrariamente():
    estado = _estado_full({
        "Genial Analisa": {"recomendacao": "COMPRA"},
        "XP Investimentos": {"recomendacao": "VENDA"},
    })
    consenso = comp_mod._consenso(estado)
    assert consenso["categoria_mais_comum"] is None
    assert consenso["empate"] is True


def test_consenso_amostra_insuficiente_com_menos_de_2_classificadas():
    estado = _estado_full({
        "Genial Analisa": {"recomendacao": "COMPRA"},
        "XP Investimentos": {"recomendacao": None},
    })
    consenso = comp_mod._consenso(estado)
    assert consenso["n_casas_com_recomendacao_classificada"] == 1
    assert consenso["amostra_insuficiente"] is True


# ============================================================
# 9. Evolucao historica - usa data/research/historico.py, nunca
#    confunde ATUAL com HISTORICO
# ============================================================

def test_evolucao_historica_usa_historico_py_e_separa_atual_de_historico():
    publicacoes = [
        _pub("Genial Analisa", "l1", data_publicacao="2026-10-20", recomendacao="COMPRA", preco_alvo=60.0),
        _pub("Genial Analisa", "l0", data_publicacao="2026-09-01", recomendacao="MANTER", preco_alvo=45.0),
    ]
    snapshots = [
        {"recomendacao": "COMPRA", "preco_alvo": 60.0, "capturado_em": "2026-10-20T10:00:00+00:00"},
        {"recomendacao": "MANTER", "preco_alvo": 45.0, "capturado_em": "2026-09-01T10:00:00+00:00"},
    ]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         patch.object(comp_mod.historico, "historico_ticker", return_value=snapshots), \
         patch.object(comp_mod.historico, "mudancas_hoje", return_value=[{"ticker": "WEGE3"}]), \
         _mock_cobertura_vazia():
        comparacao = comp_mod.comparar_ticker("WEGE3")
    evolucao = comparacao["evolucao_historica"]["Genial Analisa"]
    assert evolucao["preco_alvo_atual"] == 60.0
    assert evolucao["recomendacao_atual"] == "COMPRA"
    # historico (publicacao anterior) nunca aparece como atual
    assert len(evolucao["publicacoes_historicas"]) == 1
    assert evolucao["publicacoes_historicas"][0]["preco_alvo"] == 45.0
    assert evolucao["historico_estruturado_disponivel"] is True
    assert len(evolucao["historico_estruturado"]) == 2
    assert evolucao["mudou_recomendacao_ou_alvo_hoje"] is True


def test_evolucao_historica_casa_sem_historico_estruturado_nao_e_erro():
    publicacoes = [_pub("Monte Bravo", "l1", data_publicacao="2026-10-20", recomendacao="COMPRA", preco_alvo=60.0)]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        comparacao = comp_mod.comparar_ticker("WEGE3")
    evolucao = comparacao["evolucao_historica"]["Monte Bravo"]
    assert evolucao["historico_estruturado_disponivel"] is False
    assert evolucao["historico_estruturado"] == []
    assert evolucao["mudou_recomendacao_ou_alvo_hoje"] is False


def test_evolucao_historica_falha_no_modulo_historico_nunca_propaga():
    publicacoes = [_pub("Genial Analisa", "l1", data_publicacao="2026-10-20", recomendacao="COMPRA", preco_alvo=60.0)]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         patch.object(comp_mod.historico, "historico_ticker", side_effect=RuntimeError("Supabase fora do ar")), \
         patch.object(comp_mod.historico, "mudancas_hoje", side_effect=RuntimeError("Supabase fora do ar")), \
         _mock_cobertura_vazia():
        comparacao = comp_mod.comparar_ticker("WEGE3")  # nunca lanca excecao
    assert comparacao["evolucao_historica"]["Genial Analisa"]["historico_estruturado_disponivel"] is False


# ============================================================
# 10. Fontes e rastreabilidade - toda conclusao remonta a uma fonte
# ============================================================

def test_fontes_evidencias_cobre_toda_publicacao_usada_deduplicada_por_link():
    publicacoes = [
        _pub("Genial Analisa", "l1", data_publicacao="2026-10-20", recomendacao="COMPRA", preco_alvo=60.0),
        _pub("Genial Analisa", "l0", data_publicacao="2026-09-01", recomendacao="MANTER", preco_alvo=45.0),
        _pub("XP Investimentos", "l2", data_publicacao="2026-10-15", recomendacao="VENDA", preco_alvo=30.0),
    ]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        relatorio = comp_mod.montar_relatorio_comparativo("WEGE3")
    links = {f["link"] for f in relatorio["fontes_evidencias"]}
    assert links == {"l0", "l1", "l2"}
    # cada linha da tabela comparativa (conclusao) tem fonte correspondente
    for linha in relatorio["tabela_comparativa"]:
        assert linha["link"] in links


def test_toda_casa_na_tabela_comparativa_tem_fonte_rastreavel():
    publicacoes = [
        _pub("Genial Analisa", "l1", data_publicacao="2026-10-20", recomendacao="COMPRA", preco_alvo=60.0),
        _pub("XP Investimentos", "l2", data_publicacao="2026-10-15", recomendacao="VENDA", preco_alvo=30.0),
    ]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        relatorio = comp_mod.montar_relatorio_comparativo("WEGE3")
    casas_na_tabela = {linha["casa"] for linha in relatorio["tabela_comparativa"]}
    casas_nas_fontes = {f["casa"] for f in relatorio["fontes_evidencias"]}
    assert casas_na_tabela <= casas_nas_fontes


# ============================================================
# 11. Fallback de data (data_publicacao ausente -> extraido_em)
# ============================================================

def test_fallback_extraido_em_quando_data_publicacao_ausente():
    publicacoes = [
        _pub("Genial Analisa", "antigo", data_publicacao="2026-09-01", recomendacao="MANTER", preco_alvo=40.0),
        _pub("Genial Analisa", "recente_sem_data", data_publicacao=None,
             extraido_em="2026-10-25T08:00:00+00:00", recomendacao="COMPRA", preco_alvo=70.0),
    ]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        comparacao = comp_mod.comparar_ticker("WEGE3")
    atual = comparacao["estado_atual_por_casa"]["Genial Analisa"]["atual"]
    assert atual["link"] == "recente_sem_data"  # extraido_em mais recente venceu, mesmo sem data_publicacao


# ============================================================
# 12. Relatorio completo (montar_relatorio_comparativo) - integracao
# ============================================================

def test_relatorio_completo_tem_as_9_secoes_esperadas():
    publicacoes = [
        _pub("Genial Analisa", "l1", data_publicacao="2026-10-20", recomendacao="COMPRA", preco_alvo=60.0,
             premissas=["expansao de capacidade"], tipo_documento="INICIACAO_COBERTURA"),
        _pub("XP Investimentos", "l2", data_publicacao="2026-10-15", recomendacao="MANTER", preco_alvo=50.0,
             premissas=["ganho de market share"]),
    ]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        relatorio = comp_mod.montar_relatorio_comparativo("WEGE3")
    secoes_esperadas = {
        "resumo_executivo", "consenso", "tabela_comparativa", "dispersao_precos_alvo",
        "divergencias_premissas", "revisoes_recentes", "riscos", "pontos_atencao", "fontes_evidencias",
    }
    assert secoes_esperadas <= set(relatorio.keys())
    assert "WEGE3" in relatorio["resumo_executivo"]
    assert len(relatorio["tabela_comparativa"]) == 2


def test_relatorio_pontos_atencao_lista_casa_sem_preco_alvo():
    publicacoes = [
        _pub("Genial Analisa", "l1", data_publicacao="2026-10-20", recomendacao="COMPRA", preco_alvo=60.0),
        _pub("XP Investimentos", "l2", data_publicacao="2026-10-15", recomendacao="VENDA", preco_alvo=None),
    ]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        relatorio = comp_mod.montar_relatorio_comparativo("WEGE3")
    assert any("XP Investimentos" in aviso and "preco-alvo" in aviso for aviso in relatorio["pontos_atencao"])


def test_relatorio_pontos_atencao_lista_casa_nao_classificada():
    publicacoes = [_pub("Monte Bravo", "l1", data_publicacao="2026-10-20", recomendacao="ANALISANDO", preco_alvo=60.0)]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         _mock_historico_vazio(), _mock_cobertura_vazia():
        relatorio = comp_mod.montar_relatorio_comparativo("WEGE3")
    assert any("NAO_CLASSIFICADO" in aviso for aviso in relatorio["pontos_atencao"])
    linha = relatorio["tabela_comparativa"][0]
    assert linha["recomendacao_original"] == "ANALISANDO"
    assert linha["recomendacao_categoria"] == comp_mod.CATEGORIA_NAO_CLASSIFICADO


def test_relatorio_sem_cobertura_de_casas_monitoradas_aparece_em_pontos_atencao():
    publicacoes = [_pub("Genial Analisa", "l1", data_publicacao="2026-10-20", recomendacao="COMPRA", preco_alvo=60.0)]
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), _mock_historico_vazio(), \
         patch.object(comp_mod, "cobertura_cruzada_casas", return_value={
             "ticker": "WEGE3", "janela_dias": 30, "cobertura": [], "sem_cobertura": ["BTG Pactual Research"],
             "divergencia": None,
         }):
        relatorio = comp_mod.montar_relatorio_comparativo("WEGE3")
    assert any("BTG Pactual Research" in aviso for aviso in relatorio["pontos_atencao"])


# ============================================================
# 13. Zero chamada de IA neste modulo (determinístico sobre dado
#    ja estruturado) - confirmado estaticamente via AST, nunca por
#    heuristica de texto.
# ============================================================

def test_modulo_nao_importa_nada_de_ia():
    caminho = Path(comp_mod.__file__)
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    nomes_importados = []
    for node in ast.walk(arvore):
        if isinstance(node, ast.Import):
            nomes_importados += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                nomes_importados.append(node.module)
    proibidos = ("requests", "groq", "google.generativeai", "openai", "anthropic")
    for nome in nomes_importados:
        for proibido in proibidos:
            assert proibido not in nome.lower(), f"import proibido encontrado: {nome}"
