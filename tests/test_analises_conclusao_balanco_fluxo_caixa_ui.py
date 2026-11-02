# -*- coding: utf-8 -*-
"""Complemento de test_analises_conclusao_investimento_ui.py: cobre o
uso do bloco `balanco_fluxo_caixa` (ROIC, dívida líquida histórica,
EBITDA/FCO/FCF/CAPEX/dividendos acumulados no ano, da CVM - Fase 2,
2026-11-01) nas seções 3 (Crescimento e rentabilidade), 4 (Estrutura de
capital), 5 (Geração de caixa) e Valuation/DCF da Conclusão de
Investimento. Funções puras, sem Streamlit - mesmo padrão do arquivo
que complementa."""

import ui.analises_tab as at_mod

_FUNDAMENTOS_SEM_FCF = {
    "ticker": "WEGE3", "preco": 40.0, "pl": 28.5, "pvp": 9.1, "dividend_yield": 1.2,
    "roe": 32.0, "margem_liquida": 14.0, "divida_liquida_ebitda": 0.3,
    "valor_mercado": 150_000_000_000, "ebitda": None, "ev_ebitda": None,
    "fluxo_caixa_livre": None, "desatualizado": False, "alerta_qualidade": [],
}

_BFC_COMPLETO = {
    "roic_pct": 10.4, "aliquota_efetiva_pct": 16.2,
    "divida_liquida_atual": 1_500_000_000.0,
    "fco_ytd": 4_000_000_000.0, "capex_ytd": 2_000_000_000.0,
    "fcf_ytd": 2_000_000_000.0, "dividendos_pagos_ytd": 1_700_000_000.0,
}

_HISTORICO_COM_BFC = {
    "disponivel": True, "periodos": ["1T26", "2T26", "3T26"],
    "receita_liquida": {"yoy_pct_serie": [2.0, 5.0, 9.0], "tendencia": "RECUPERACAO"},
    "ebit": {"yoy_pct_serie": [1.0, 3.0, 6.0], "tendencia": "RECUPERACAO"},
    "lucro_liquido_consolidado": {"yoy_pct_serie": [0.5, 1.0, 1.2], "tendencia": "ESTABILIDADE"},
    "margem_bruta_pct": {"serie": [38.0, 38.5, 39.0], "tendencia": "ESTABILIDADE"},
    "roic_pct": {"serie": [9.0, 9.8, 10.4], "tendencia": "RECUPERACAO"},
    "divida_liquida": {"serie": [1.6e9, 1.55e9, 1.5e9], "yoy_pct_serie": [-2.0, -4.0], "tendencia": "RECUPERACAO"},
    "fco_ytd": {"yoy_pct_serie": [5.0], "tendencia": "RECUPERACAO"},
    "fcf_ytd": {"yoy_pct_serie": [8.0], "tendencia": "RECUPERACAO"},
    "capex_ytd": {"yoy_pct_serie": [3.0], "tendencia": "RECUPERACAO"},
    "dividendos_pagos_ytd": {"yoy_pct_serie": [-10.0], "tendencia": "DETERIORACAO"},
    "ultima_nota": {
        "periodo_label": "3T26", "fontes": [{"nome": "CVM - dados.cvm.gov.br (ITR)"}],
        "balanco_fluxo_caixa": _BFC_COMPLETO,
    },
}

_HISTORICO_SEM_BFC = {  # formato "antigo" (Fase 1), sem balanco_fluxo_caixa
    "disponivel": True, "periodos": ["1T26"],
    "receita_liquida": {"yoy_pct_serie": [2.0], "tendencia": "RECUPERACAO"},
    "ebit": {"yoy_pct_serie": [1.0], "tendencia": "RECUPERACAO"},
    "lucro_liquido_consolidado": {"yoy_pct_serie": [0.5], "tendencia": "ESTABILIDADE"},
    "margem_bruta_pct": {"serie": [38.0], "tendencia": "ESTABILIDADE"},
    "ultima_nota": {"periodo_label": "1T26", "fontes": [{"nome": "CVM"}]},
}


# --- _ultimo_bfc ---------------------------------------------------------

def test_ultimo_bfc_extrai_bloco_quando_disponivel():
    assert at_mod._ultimo_bfc(_HISTORICO_COM_BFC) == _BFC_COMPLETO


def test_ultimo_bfc_vazio_quando_historico_indisponivel():
    assert at_mod._ultimo_bfc({"disponivel": False}) == {}
    assert at_mod._ultimo_bfc(None) == {}


def test_ultimo_bfc_vazio_quando_nota_sem_a_chave():
    assert at_mod._ultimo_bfc(_HISTORICO_SEM_BFC) == {}


# --- _secao_crescimento_rentabilidade (ROIC) ----------------------------

def test_crescimento_rentabilidade_cita_roic_real_quando_disponivel():
    lacunas = set()
    bloco = at_mod._secao_crescimento_rentabilidade(
        {"roe": 32.0}, _HISTORICO_COM_BFC, lacunas,
    )
    assert "ROIC" in bloco["resposta"]
    assert "10.4" in bloco["resposta"] or "10,4" in bloco["resposta"]
    assert "roic" not in lacunas  # dado disponível - nunca aparece como lacuna
    assert bloco["tipo_evidencia"] == at_mod.TIPO_CALCULO


def test_crescimento_rentabilidade_sem_roic_vira_lacuna():
    lacunas = set()
    bloco = at_mod._secao_crescimento_rentabilidade({"roe": 32.0}, _HISTORICO_SEM_BFC, lacunas)
    assert "roic" in lacunas
    assert "ROE" in bloco["resposta"]  # ainda cita o que existe (ROE)


def test_crescimento_rentabilidade_so_roe_sem_tendencia_e_fato_puro():
    """Único conteúdo é um valor reportado cru (ROE), sem nenhuma
    tendência/ROIC calculados - aqui sim é FATO puro."""
    historico_sem_tendencia_nem_bfc = {"disponivel": False}
    lacunas = set()
    bloco = at_mod._secao_crescimento_rentabilidade({"roe": 32.0}, historico_sem_tendencia_nem_bfc, lacunas)
    assert bloco["tipo_evidencia"] == at_mod.TIPO_FATO


def test_crescimento_rentabilidade_roe_mais_tendencia_nunca_e_fato_puro():
    """Bug real encontrado em auditoria (2026-11-01): quando a resposta
    mistura ROE bruto (FATO) com tendência de lucro/EBIT (CÁLCULO,
    derivada de variação YoY), NUNCA pode ser rotulada só como FATO -
    isso escondia a natureza calculada da tendência sob um selo errado."""
    lacunas = set()
    bloco = at_mod._secao_crescimento_rentabilidade({"roe": 32.0}, _HISTORICO_SEM_BFC, lacunas)
    assert bloco["tipo_evidencia"] == at_mod.TIPO_CALCULO  # nunca TIPO_FATO aqui


# --- _secao_estrutura_capital (dívida líquida histórica) ----------------

def test_estrutura_capital_cita_divida_liquida_historica_quando_disponivel():
    lacunas = set()
    bloco = at_mod._secao_estrutura_capital(
        {"divida_liquida_ebitda": 1.2}, _HISTORICO_COM_BFC, lacunas,
    )
    assert "dívida líquida" in bloco["resposta"].lower()
    assert "divida_historica" not in lacunas
    assert bloco["tipo_evidencia"] == at_mod.TIPO_CALCULO


def test_estrutura_capital_sem_balanco_vira_lacuna_mas_mantem_ponto_atual():
    lacunas = set()
    bloco = at_mod._secao_estrutura_capital({"divida_liquida_ebitda": 1.2}, _HISTORICO_SEM_BFC, lacunas)
    assert "divida_historica" in lacunas
    assert "Dívida líquida/EBITDA" in bloco["resposta"]  # ponto atual (yfinance) ainda aparece
    assert bloco["tipo_evidencia"] == at_mod.TIPO_FATO


def test_estrutura_capital_sem_nenhum_dado_e_insuficiente():
    lacunas = set()
    bloco = at_mod._secao_estrutura_capital({"divida_liquida_ebitda": None}, _HISTORICO_SEM_BFC, lacunas)
    assert bloco["tipo_evidencia"] == at_mod.TIPO_INSUFICIENTE


# --- _secao_geracao_caixa (FCO/FCF/CAPEX/dividendos YTD) -----------------

def test_geracao_caixa_cita_fco_fcf_capex_dividendos_quando_disponiveis():
    lacunas = set()
    bloco = at_mod._secao_geracao_caixa(_FUNDAMENTOS_SEM_FCF, _HISTORICO_COM_BFC, lacunas)
    resposta = bloco["resposta"]
    assert "FCO" in resposta and "CAPEX" in resposta and "FCF" in resposta and "dividendos" in resposta.lower()
    assert "geracao_caixa" not in lacunas
    assert bloco["tipo_evidencia"] == at_mod.TIPO_CALCULO


def test_geracao_caixa_sem_nenhuma_fonte_e_insuficiente():
    lacunas = set()
    bloco = at_mod._secao_geracao_caixa(_FUNDAMENTOS_SEM_FCF, _HISTORICO_SEM_BFC, lacunas)
    assert bloco["tipo_evidencia"] == at_mod.TIPO_INSUFICIENTE
    assert "geracao_caixa" in lacunas


def test_geracao_caixa_fco_parcial_ainda_vira_lacuna():
    """Mesmo com FCO disponível, se CAPEX/FCF/dividendos faltarem
    parcialmente a lacuna continua sinalizada - não é tudo-ou-nada no
    texto, mas a seção 14 precisa saber que algo falta."""
    historico_parcial = dict(_HISTORICO_COM_BFC)
    historico_parcial["ultima_nota"] = dict(_HISTORICO_COM_BFC["ultima_nota"])
    historico_parcial["ultima_nota"]["balanco_fluxo_caixa"] = {**_BFC_COMPLETO, "capex_ytd": None}
    lacunas = set()
    bloco = at_mod._secao_geracao_caixa(_FUNDAMENTOS_SEM_FCF, historico_parcial, lacunas)
    assert "geracao_caixa" in lacunas
    assert "FCO" in bloco["resposta"]  # o que existe ainda é citado


# --- _fcf_para_dcf (fallback yfinance -> CVM YTD) ------------------------

def test_fcf_para_dcf_prefere_yfinance_quando_disponivel():
    fundamentos = {"fluxo_caixa_livre": 999.0}
    valor, fonte = at_mod._fcf_para_dcf(fundamentos, _HISTORICO_COM_BFC)
    assert valor == 999.0
    assert "TTM" in fonte


def test_fcf_para_dcf_cai_pro_cvm_quando_yfinance_ausente():
    valor, fonte = at_mod._fcf_para_dcf(_FUNDAMENTOS_SEM_FCF, _HISTORICO_COM_BFC)
    assert valor == _BFC_COMPLETO["fcf_ytd"]
    assert "YTD" in fonte


def test_fcf_para_dcf_none_quando_nenhuma_fonte_disponivel():
    valor, fonte = at_mod._fcf_para_dcf(_FUNDAMENTOS_SEM_FCF, _HISTORICO_SEM_BFC)
    assert valor is None
    assert fonte is None


# --- _secao_valuation (DCF habilitado via fallback CVM) ------------------

def test_valuation_dcf_disponivel_via_fallback_cvm():
    lacunas = set()
    bloco = at_mod._secao_valuation(_FUNDAMENTOS_SEM_FCF, _HISTORICO_COM_BFC, None, lacunas)
    assert "dcf" not in lacunas
    assert "DCF" in bloco["resposta"]


def test_valuation_dcf_bloqueado_sem_nenhuma_fonte_de_fcf():
    lacunas = set()
    at_mod._secao_valuation(_FUNDAMENTOS_SEM_FCF, _HISTORICO_SEM_BFC, None, lacunas)
    assert "dcf" in lacunas
