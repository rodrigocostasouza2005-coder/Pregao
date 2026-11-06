# -*- coding: utf-8 -*-
"""HISTÓRICO, EVOLUÇÃO E PERSPECTIVAS - "Company 360" sob demanda
(ui/analises_tab.py:_dialog_historico_evolucao_empresa, 2026-11-06),
aberto pelo botão "Histórico, evolução e perspectivas (3 anos) ↗" em
render_equity_research_executivo (ver tests/test_analises_equity_research_ui.py
pro teste do botão em si).

Reaproveita, sem nenhum cálculo novo: earnings_reviewer.serie_historica_br
(mesma fonte de data/market_researcher.py:historico_fundamentos, só com
n_trimestres=12 em vez de 4) e as funções analíticas puras já existentes
(_secao_qualidade_negocio, _secao_crescimento_rentabilidade,
_secao_estrutura_capital, _secao_geracao_caixa, _montar_cenarios,
_secao_riscos_invalidacao, _secao_catalisadores) - cobertas a fundo em
tests/test_analises_conclusao_investimento_ui.py; aqui o foco é só a
integração nova (janela de 3 anos, tabela, múltiplos atuais e a
cross-referência de premissas do Comitê), bare mode (sem ScriptRunContext
real), mesmo padrão dos demais testes deste módulo."""
from unittest.mock import MagicMock, patch

import ui.analises_tab as at_mod

_PREFS = {"formato_numerico": "BR"}

_HISTORICO_3ANOS_COMPLETO = {
    "disponivel": True,
    "periodos": ["4T23", "1T24", "2T24", "3T24", "4T24", "1T25", "2T25", "3T25", "4T25", "1T26", "2T26", "3T26"],
    "receita_liquida": {"yoy_pct_serie": [2.0, 3.0, 9.0], "tendencia": "RECUPERACAO"},
    "ebit": {"yoy_pct_serie": [1.0, 2.0, 6.0], "tendencia": "RECUPERACAO"},
    "lucro_liquido_consolidado": {"yoy_pct_serie": [0.5, 0.6, 0.5], "tendencia": "ESTABILIDADE"},
    "margem_bruta_pct": {"serie": [37.0, 38.0, 39.0], "tendencia": "RECUPERACAO"},
    "roic_pct": {"serie": [8.0, 9.0, 10.0], "tendencia": "RECUPERACAO"},
    "divida_liquida": {"serie": [1_000.0, 900.0, 800.0], "yoy_pct_serie": [-5.0, -8.0, -10.0], "tendencia": "RECUPERACAO"},
    "ebitda_ytd": {"yoy_pct_serie": [4.0, 5.0], "tendencia": "RECUPERACAO"},
    "fco_ytd": {"yoy_pct_serie": [3.0], "tendencia": None},
    "fcf_ytd": {"yoy_pct_serie": [], "tendencia": None},
    "capex_ytd": {"yoy_pct_serie": [10.0, -2.0], "tendencia": "DETERIORACAO"},
    "dividendos_pagos_ytd": {"yoy_pct_serie": [1.0, 1.0], "tendencia": "ESTABILIDADE"},
    "ultima_nota": {"periodo_label": "3T26", "fontes": [{"nome": "CVM - dados.cvm.gov.br (ITR)"}]},
}

_FUNDAMENTOS = {
    "pl": 28.5, "pvp": 9.1, "dividend_yield": 1.2, "roe": 32.0,
    "divida_liquida_ebitda": 0.3, "ev_ebitda": 25.1,
}

_ANALISE = {
    "ticker": "WEGE3", "fundamentos": _FUNDAMENTOS, "catalisadores": [], "riscos_indicadores": [],
    "cobertura_research": None, "fundamentos_historicos": _HISTORICO_3ANOS_COMPLETO,
}


# ============================================================
# _historico_3anos_cacheado - janela de 3 anos (12 trimestres), mesma
# fonte de historico_fundamentos, só BR.
# ============================================================

def test_historico_3anos_internacional_nao_inventa_serie():
    with patch.object(at_mod.config, "info_ativo", return_value={"pais": "Estados Unidos"}):
        resultado = at_mod._historico_3anos_cacheado.__wrapped__("AAPL34")
    assert resultado["disponivel"] is False
    assert "brasileiras" in resultado["motivo"]


def test_historico_3anos_br_pede_12_trimestres_da_mesma_fonte():
    with patch.object(at_mod.config, "info_ativo", return_value={"pais": "Brasil"}), \
         patch.object(at_mod.earnings_reviewer, "serie_historica_br", return_value=_HISTORICO_3ANOS_COMPLETO) as mock_serie:
        resultado = at_mod._historico_3anos_cacheado.__wrapped__("WEGE3")
    mock_serie.assert_called_once_with("WEGE3", n_trimestres=12)
    assert resultado is _HISTORICO_3ANOS_COMPLETO


# ============================================================
# _execucao_comite_cacheada - cross-referência só de LEITURA com o
# Coordenador Central (nunca inventa quando não houver análise/fonte fora).
# ============================================================

def test_execucao_comite_supabase_fora_do_ar_tem_motivo_distinto_de_nao_encontrada():
    with patch.object(at_mod.coordenador_persistencia, "listar_analises_recentes", return_value=None):
        resultado = at_mod._execucao_comite_cacheada.__wrapped__("WEGE3")
    assert resultado["disponivel"] is False
    assert "Supabase" in resultado["motivo"]


def test_execucao_comite_excecao_nunca_propaga():
    with patch.object(at_mod.coordenador_persistencia, "listar_analises_recentes",
                       side_effect=RuntimeError("Supabase fora do ar")):
        resultado = at_mod._execucao_comite_cacheada.__wrapped__("WEGE3")
    assert resultado["disponivel"] is False


def test_execucao_comite_sem_analise_para_o_ticker_nao_inventa():
    with patch.object(at_mod.coordenador_persistencia, "listar_analises_recentes",
                       return_value=[{"ticker": "PETR4", "status": "CONCLUIDA", "resultado": {}}]):
        resultado = at_mod._execucao_comite_cacheada.__wrapped__("WEGE3")
    assert resultado == {"disponivel": True, "encontrada": False}


def test_execucao_comite_encontra_modelagem_do_model_builder():
    analises = [{
        "ticker": "WEGE3", "status": "CONCLUIDA", "iniciado_em": "2026-10-15T10:00:00+00:00",
        "resultado": {"pareceres_analistas": {"analistas": [
            {"id": "market_researcher", "recomendacao": "COMPRA"},
            {"id": "model_builder", "recomendacao": "MODELADO",
             "premissas": {"wacc": 0.12, "crescimento_fcf_base": 0.05, "divida_liquida": 900.0,
                           "origem_divida_liquida": "CVM — balanço patrimonial consolidado"}},
        ]}},
    }]
    with patch.object(at_mod.coordenador_persistencia, "listar_analises_recentes", return_value=analises):
        resultado = at_mod._execucao_comite_cacheada.__wrapped__("WEGE3")
    assert resultado["disponivel"] is True
    assert resultado["encontrada"] is True
    assert resultado["modelo_disponivel"] is True
    assert resultado["premissas"]["wacc"] == 0.12
    assert resultado["origem_divida_liquida"] == "CVM — balanço patrimonial consolidado"


def test_execucao_comite_ignora_analise_de_outro_ticker_e_erro():
    analises = [
        {"ticker": "PETR4", "status": "CONCLUIDA", "resultado": {"pareceres_analistas": {"analistas": []}}},
        {"ticker": "WEGE3", "status": "ERRO", "resultado": {"pareceres_analistas": {"analistas": []}}},
    ]
    with patch.object(at_mod.coordenador_persistencia, "listar_analises_recentes", return_value=analises):
        resultado = at_mod._execucao_comite_cacheada.__wrapped__("WEGE3")
    assert resultado == {"disponivel": True, "encontrada": False}


def test_execucao_comite_model_builder_sem_premissas_suficientes():
    analises = [{
        "ticker": "WEGE3", "status": "CONCLUIDA", "iniciado_em": "2026-10-15T10:00:00+00:00",
        "resultado": {"pareceres_analistas": {"analistas": [
            {"id": "model_builder", "recomendacao": "INSUFICIENTE", "premissas": {}},
        ]}},
    }]
    with patch.object(at_mod.coordenador_persistencia, "listar_analises_recentes", return_value=analises):
        resultado = at_mod._execucao_comite_cacheada.__wrapped__("WEGE3")
    assert resultado["encontrada"] is True
    assert resultado["modelo_disponivel"] is False


# ============================================================
# Badge de tendência / linha e tabela do histórico de 3 anos
# ============================================================

def test_badge_tendencia_sem_pontos_suficientes_e_honesto():
    assert "sem tendência" in at_mod._badge_tendencia_html(None)


def test_badge_tendencia_recuperacao_usa_cor_de_alta():
    html_badge = at_mod._badge_tendencia_html("RECUPERACAO")
    assert "RECUPERAÇÃO" in html_badge
    assert "var(--alta)" in html_badge


def test_linha_tabela_historico_serie_vazia_declara_dado_insuficiente():
    linha = at_mod._linha_tabela_historico_3anos("Receita líquida (YoY)", [], "RECUPERACAO", lambda v: f"{v}")
    assert "dado insuficiente" in linha


def test_linha_tabela_historico_ignora_none_sem_quebrar_alinhamento():
    """Série com None no meio (trimestre sem YoY calculável) - último
    ponto reportado é o último VÁLIDO, nunca um None nem um valor de
    outro índice (ver docstring da função: nunca assume alinhamento
    posicional com a lista de períodos)."""
    linha = at_mod._linha_tabela_historico_3anos("EBIT (YoY)", [5.0, None, 9.0], "RECUPERACAO",
                                                   lambda v: f"{v:+.1f}%")
    assert "+9.0%" in linha  # último ponto VÁLIDO
    assert "+5.0%" in linha  # mínimo
    assert "2/3" in linha  # 2 pontos válidos de 3 na janela


def test_tabela_historico_3anos_html_mostra_janela_real_e_nao_trava():
    tabela, legenda = at_mod._tabela_historico_3anos_html(_HISTORICO_3ANOS_COMPLETO, "BR")
    assert "4T23" in legenda and "3T26" in legenda and "12 trimestre" in legenda
    assert "Receita líquida" in tabela
    assert "Dívida líquida" in tabela
    assert "ROIC" in tabela


# ============================================================
# Múltiplos atuais / evolução operacional / perspectivas e riscos -
# blocos individuais do diálogo (capturando st.markdown/st.caption).
# ============================================================

def _capturar(fn, *args):
    blocos = []
    with patch.object(at_mod.st, "markdown", side_effect=lambda t, **k: blocos.append(str(t))), \
         patch.object(at_mod.st, "caption", side_effect=lambda t, **k: blocos.append(str(t))):
        fn(*args)
    return "\n".join(blocos)


def test_multiplos_atuais_sem_fundamentos_nunca_inventa():
    texto = _capturar(at_mod._render_multiplos_atuais_empresa, None, "BR")
    assert "indisponíveis agora" in texto


def test_multiplos_atuais_com_fundamentos_mostra_ponto_real_e_avisa_sobre_serie():
    texto = _capturar(at_mod._render_multiplos_atuais_empresa, _FUNDAMENTOS, "BR")
    assert "28,50" in texto  # P/L
    assert "não é calculada nesta versão" in texto


def test_evolucao_operacional_reaproveita_secoes_existentes():
    texto = _capturar(at_mod._render_evolucao_operacional_empresa, _FUNDAMENTOS, _HISTORICO_3ANOS_COMPLETO)
    assert "Qualidade do negócio" in texto
    assert "Crescimento e rentabilidade" in texto
    assert "Estrutura de capital" in texto
    assert "Geração de caixa" in texto


def test_evolucao_operacional_sem_historico_declara_insuficiente_sem_inventar():
    texto = _capturar(at_mod._render_evolucao_operacional_empresa, None, {})
    assert "Dado insuficiente" in texto


def test_perspectivas_riscos_reaproveita_montar_cenarios_e_secoes():
    texto = _capturar(at_mod._render_perspectivas_riscos_empresa, _HISTORICO_3ANOS_COMPLETO, [], [], None)
    assert "Perspectivas" in texto or "Catalisadores" in texto  # subtítulos vêm via st.markdown mockado


# ============================================================
# Premissas atualizadas pelo Comitê - nunca inventa quando não houver
# análise/fonte fora do ar.
# ============================================================

def test_premissas_comite_sem_analise_nunca_inventa():
    with patch.object(at_mod, "_execucao_comite_cacheada", return_value={"disponivel": True, "encontrada": False}):
        texto = _capturar(at_mod._render_premissas_comite_empresa, "WEGE3")
    assert "Nenhuma análise do Comitê" in texto


def test_premissas_comite_fonte_fora_do_ar_tem_mensagem_distinta():
    with patch.object(at_mod, "_execucao_comite_cacheada",
                       return_value={"disponivel": False, "motivo": "indisponível agora (Supabase fora do ar)."}):
        texto = _capturar(at_mod._render_premissas_comite_empresa, "WEGE3")
    assert "Supabase fora do ar" in texto
    assert "Nenhuma análise do Comitê" not in texto


def test_premissas_comite_mostra_modelagem_real_do_model_builder():
    info = {
        "disponivel": True, "encontrada": True, "data": "2026-10-15T10:00:00+00:00",
        "modelo_disponivel": True,
        "premissas": {"wacc": 0.12, "crescimento_fcf_base": 0.05, "divida_liquida": 900.0},
        "origem_divida_liquida": "CVM — balanço patrimonial consolidado",
    }
    with patch.object(at_mod, "_execucao_comite_cacheada", return_value=info):
        texto = _capturar(at_mod._render_premissas_comite_empresa, "WEGE3")
    assert "WACC 12.0%" in texto
    assert "CVM — balanço patrimonial consolidado" in texto
    assert "CÁLCULO INTERNO DO COMITÊ" in texto


def test_premissas_comite_encontrada_mas_sem_modelo_concluido():
    info = {"disponivel": True, "encontrada": True, "data": "2026-10-15T10:00:00+00:00",
            "modelo_disponivel": False, "premissas": None}
    with patch.object(at_mod, "_execucao_comite_cacheada", return_value=info):
        texto = _capturar(at_mod._render_premissas_comite_empresa, "WEGE3")
    assert "sem modelagem" in texto


# ============================================================
# Diálogo completo (.__wrapped__, mesmo padrão de
# tests/test_analises_equity_research_ui.py:_capturar_dialog_setor) -
# nunca lança excecao, nunca inventa dado quando as fontes faltarem.
# ============================================================

def _capturar_dialog_historico(historico3=None, levanta_historico=None, info_comite=None):
    blocos = []
    with patch.object(at_mod, "_historico_3anos_cacheado",
                       side_effect=levanta_historico if levanta_historico else lambda t: historico3), \
         patch.object(at_mod, "_execucao_comite_cacheada",
                       return_value=info_comite or {"disponivel": True, "encontrada": False}), \
         patch.object(at_mod.st, "markdown", side_effect=lambda t, **k: blocos.append(str(t))), \
         patch.object(at_mod.st, "caption", side_effect=lambda t, **k: blocos.append(str(t))), \
         patch.object(at_mod.st, "spinner") as mock_spinner:
        mock_spinner.return_value.__enter__ = lambda self: None
        mock_spinner.return_value.__exit__ = lambda self, *a: False
        at_mod._dialog_historico_evolucao_empresa.__wrapped__("WEGE3", _PREFS, _ANALISE)
    return "\n".join(blocos)


def test_dialog_historico_completo_nunca_lanca_excecao_e_mostra_tudo():
    texto = _capturar_dialog_historico(historico3=_HISTORICO_3ANOS_COMPLETO)
    assert "Janela considerada" in texto
    assert "Qualidade do negócio" in texto  # evolução operacional
    assert "nunca uma recomendação de" in texto  # disclaimer final
    assert "Nenhuma análise do Comitê" in texto


def test_dialog_historico_fonte_cvm_fora_do_ar_cai_pro_historico_de_1_ano_sem_inventar():
    """Quando a janela de 3 anos falha, a evolução operacional cai pro
    histórico de 1 ano já calculado em analise_ticker (fundamentos_historicos) -
    nunca inventa um dado novo nem quebra a tela."""
    texto = _capturar_dialog_historico(
        levanta_historico=lambda t: (_ for _ in ()).throw(RuntimeError("CVM fora do ar")),
    )
    assert "indisponível" in texto.lower()
    # fallback usa _HISTORICO_3ANOS_COMPLETO (fundamentos_historicos de _ANALISE) - ainda mostra evolução real
    assert "Qualidade do negócio" in texto


def test_dialog_historico_sem_nenhum_historico_declara_insuficiente_sem_crash():
    analise_vazia = {"ticker": "XPTO3", "fundamentos": None, "catalisadores": None,
                      "riscos_indicadores": None, "cobertura_research": None, "fundamentos_historicos": None}
    blocos = []
    with patch.object(at_mod, "_historico_3anos_cacheado", return_value={"disponivel": False, "motivo": "sem DRE disponível na CVM."}), \
         patch.object(at_mod, "_execucao_comite_cacheada", return_value={"disponivel": True, "encontrada": False}), \
         patch.object(at_mod.st, "markdown", side_effect=lambda t, **k: blocos.append(str(t))), \
         patch.object(at_mod.st, "caption", side_effect=lambda t, **k: blocos.append(str(t))), \
         patch.object(at_mod.st, "spinner") as mock_spinner:
        mock_spinner.return_value.__enter__ = lambda self: None
        mock_spinner.return_value.__exit__ = lambda self, *a: False
        at_mod._dialog_historico_evolucao_empresa.__wrapped__("XPTO3", _PREFS, analise_vazia)
    texto = "\n".join(blocos)
    assert "sem DRE disponível na CVM" in texto
    assert "Dado insuficiente" in texto  # evolução operacional sem nenhuma fonte
