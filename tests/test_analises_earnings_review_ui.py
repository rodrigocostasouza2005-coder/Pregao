# -*- coding: utf-8 -*-
"""ANÁLISES › Empresas - integração do Earnings Reviewer
(ui/analises_tab.py:render_revisao_resultados, consome data/earnings/
reviewer.py). Bare mode (sem ScriptRunContext), mesmo padrão de
tests/test_analises_equity_research_ui.py.

Cobre: separação visual FATO vs [INTERPRETAÇÃO], histórico de versões
(comparar_com_versao_anterior) sem sobrescrever a nota anterior, dados
ausentes tratados explicitamente (nunca 0/estimado), e isolamento de
falha de uma empresa não afetando a revisão de outra."""
from unittest.mock import MagicMock, patch

import pytest

import ui.analises_tab as analises_mod

_PREFS = {"formato_numerico": "BR"}


def _nota_vale_disponivel():
    return {
        "ticker": "VALE3", "empresa": "VALE S.A.", "pais": "BR", "disponivel": True,
        "periodo_label": "2T2026", "dt_referencia": "2026-06-30", "moeda": "REAL", "escala_moeda": "MIL",
        "metricas": {
            "receita_liquida": {"atual": 53012000.0, "yoy_anterior": 49807000.0,
                                 "yoy_variacao_pct": 6.43, "qoq_anterior": 48680000.0, "qoq_variacao_pct": 8.9},
            # resultado_bruto AUSENTE DE PROPÓSITO (fonte não reportou o
            # trimestre isolado desta conta) - tem que aparecer como
            # "indisponível" explícito, nunca 0 nem omitido da tabela.
            "resultado_bruto": {"atual": None, "yoy_anterior": None, "yoy_variacao_pct": None,
                                 "qoq_anterior": None, "qoq_variacao_pct": None},
            # ebit com variação pequena - FATO "estável", nao "ausente".
            "ebit": {"atual": 10000000.0, "yoy_anterior": 9970000.0, "yoy_variacao_pct": 0.3,
                     "qoq_anterior": 9990000.0, "qoq_variacao_pct": 0.1},
            "resultado_antes_tributos": {"atual": 9000000.0, "yoy_anterior": 8000000.0,
                                          "yoy_variacao_pct": 12.5, "qoq_anterior": 8500000.0, "qoq_variacao_pct": 5.9},
            "lucro_liquido_consolidado": {"atual": 7000000.0, "yoy_anterior": 6000000.0,
                                           "yoy_variacao_pct": 16.7, "qoq_anterior": 6500000.0, "qoq_variacao_pct": 7.7},
            "lucro_liquido_controladora": {"atual": 6900000.0, "yoy_anterior": 5900000.0,
                                            "yoy_variacao_pct": 16.9, "qoq_anterior": 6400000.0, "qoq_variacao_pct": 7.8},
        },
        "margem_bruta_pct": 16.0, "margem_bruta_yoy_anterior_pct": 14.0,
        "interpretacoes": ["[INTERPRETAÇÃO] margem bruta variou +2.0 p.p. na comparação anual "
                           "(melhora de rentabilidade bruta); não distingue aqui se a causa é preço, "
                           "volume ou custo - ver fatores na fonte original."],
        "limitacoes": ["Sem acesso a consenso de mercado, guidance ou research pago nesta integração."],
        "fontes": [{"nome": "CVM - dados.cvm.gov.br (ITR, DRE consolidada)",
                    "url": "https://dados.cvm.gov.br/x.zip", "coletado_em": "2026-10-26T12:00:00+00:00"}],
        "gerado_em": "2026-10-26T12:00:00+00:00",
    }


def _capturar_render(ticker="VALE3", pais="Brasil", nota=None, levanta_montar=None,
                      anterior=None, mudancas=None, salvar_mock=None):
    blocos = []
    dataframes = []
    col_mock = MagicMock()
    expander_mock = MagicMock()
    expander_mock.__enter__ = lambda self=None: expander_mock
    expander_mock.__exit__ = lambda *a: False

    montar_nota_br = MagicMock(side_effect=levanta_montar) if levanta_montar else MagicMock(return_value=nota)

    with patch.object(analises_mod.config, "info_ativo", return_value={"pais": pais}), \
         patch.object(analises_mod.earnings_reviewer, "montar_nota_br", montar_nota_br), \
         patch.object(analises_mod.earnings_reviewer, "salvar_versao", salvar_mock or MagicMock(return_value=True)), \
         patch.object(analises_mod.earnings_reviewer, "obter_ultima_versao", return_value=anterior), \
         patch.object(analises_mod.earnings_reviewer, "comparar_com_versao_anterior",
                       return_value=mudancas if mudancas is not None else []), \
         patch.object(analises_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(str(texto))), \
         patch.object(analises_mod.st, "caption", side_effect=lambda texto, **_k: blocos.append(str(texto))), \
         patch.object(analises_mod.st, "warning", side_effect=lambda texto, **_k: blocos.append(str(texto))), \
         patch.object(analises_mod.st, "info", side_effect=lambda texto, **_k: blocos.append(str(texto))), \
         patch.object(analises_mod.st, "dataframe", side_effect=lambda linhas, **_k: dataframes.append(linhas)), \
         patch.object(analises_mod.st, "selectbox", return_value="3T2026"), \
         patch.object(analises_mod.st, "columns", return_value=[col_mock, col_mock]), \
         patch.object(analises_mod.st, "expander", return_value=expander_mock), \
         patch.object(analises_mod.st, "container") as container_mock:
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        analises_mod.render_revisao_resultados(ticker, _PREFS)
    return "\n".join(blocos), dataframes


# ---------------------------------------------------------------------
# FATO vs [INTERPRETAÇÃO] - nunca misturados sem rótulo/estilo distinto
# ---------------------------------------------------------------------

def test_interpretacao_aparece_em_bloco_visualmente_separado():
    html_render, _ = _capturar_render(nota=_nota_vale_disponivel())
    assert "[INTERPRETAÇÃO]" in html_render
    assert "border-left" in html_render  # bloco destacado, nunca texto corrido igual ao fato


def test_sem_interpretacao_diz_isso_explicitamente_sem_inventar():
    nota = _nota_vale_disponivel()
    nota["interpretacoes"] = []
    html_render, _ = _capturar_render(nota=nota)
    assert "Nenhuma [INTERPRETAÇÃO] gerada" in html_render


# ---------------------------------------------------------------------
# DADOS AUSENTES vs VARIAÇÃO PEQUENA/NEUTRA - nunca a mesma mensagem
# ---------------------------------------------------------------------

def test_metrica_ausente_mostra_indisponivel_nunca_zero():
    _, dataframes = _capturar_render(nota=_nota_vale_disponivel())
    linhas = dataframes[0]
    linha_resultado_bruto = next(l for l in linhas if l["Conta"] == "Resultado bruto")
    assert linha_resultado_bruto["Valor atual"] == "indisponível"
    assert linha_resultado_bruto["Variação YoY"] == "indisponível"
    assert "0" not in linha_resultado_bruto["Valor atual"].replace("indisponível", "")


def test_variacao_pequena_e_fato_estavel_nao_indisponivel():
    _, dataframes = _capturar_render(nota=_nota_vale_disponivel())
    linhas = dataframes[0]
    linha_ebit = next(l for l in linhas if l["Conta"] == "EBIT")
    assert "estável" in linha_ebit["Variação YoY"]
    assert "indisponível" not in linha_ebit["Variação YoY"]


def test_metrica_com_numero_real_mostra_valor_formatado():
    _, dataframes = _capturar_render(nota=_nota_vale_disponivel())
    linhas = dataframes[0]
    linha_receita = next(l for l in linhas if l["Conta"] == "Receita líquida")
    assert "R$" in linha_receita["Valor atual"]
    assert "alta" in linha_receita["Variação YoY"]


def test_lucro_controladora_so_aparece_para_empresa_br():
    _, dataframes = _capturar_render(nota=_nota_vale_disponivel(), pais="Brasil")
    nomes = [l["Conta"] for l in dataframes[0]]
    assert "Lucro líquido - controladora" in nomes


# ---------------------------------------------------------------------
# HISTÓRICO DE REVISÕES - nunca sobrescreve, só sinaliza mudança real
# ---------------------------------------------------------------------

def test_primeira_revisao_sem_versao_anterior_diz_isso():
    html_render, _ = _capturar_render(nota=_nota_vale_disponivel(), anterior=None, mudancas=[])
    assert "Primeira revisão registrada" in html_render


def test_mudanca_de_direcao_e_mostrada_como_aviso():
    anterior = {"periodo_label": "1T2026", "metricas": {"receita_liquida": {"yoy_variacao_pct": -5.0}}}
    mudancas = [{"metrica": "receita_liquida", "direcao_anterior": "QUEDA", "direcao_atual": "ALTA",
                 "periodo_anterior": "1T2026", "periodo_atual": "2T2026"}]
    html_render, _ = _capturar_render(nota=_nota_vale_disponivel(), anterior=anterior, mudancas=mudancas)
    assert "receita_liquida" in html_render
    assert "QUEDA" in html_render and "ALTA" in html_render


def test_sem_mudanca_de_direcao_diz_isso_sem_alarme_falso():
    anterior = {"periodo_label": "1T2026", "metricas": {}}
    html_render, _ = _capturar_render(nota=_nota_vale_disponivel(), anterior=anterior, mudancas=[])
    assert "Nenhuma métrica mudou de direção" in html_render


def test_nota_disponivel_e_persistida_via_salvar_versao():
    salvar_mock = MagicMock(return_value=True)
    _capturar_render(nota=_nota_vale_disponivel(), salvar_mock=salvar_mock)
    salvar_mock.assert_called_once()


def test_nota_indisponivel_nunca_tenta_persistir():
    salvar_mock = MagicMock(return_value=True)
    nota_indisponivel = {"ticker": "ZZZZ3", "pais": "BR", "disponivel": False, "motivo": "sem CNPJ mapeado"}
    _capturar_render(nota=nota_indisponivel, salvar_mock=salvar_mock)
    salvar_mock.assert_not_called()


def test_nota_indisponivel_mostra_motivo_explicito():
    nota_indisponivel = {"ticker": "ZZZZ3", "pais": "BR", "disponivel": False,
                          "motivo": "DRE indisponível (ticker sem CNPJ mapeado)."}
    html_render, _ = _capturar_render(nota=nota_indisponivel)
    assert "DRE indisponível" in html_render


# ---------------------------------------------------------------------
# ISOLAMENTO DE FALHA - 1 empresa falhando nunca afeta outra
# ---------------------------------------------------------------------

def test_falha_na_fonte_nunca_lanca_excecao_e_avisa_sem_expor_detalhe_tecnico():
    html_render, _ = _capturar_render(
        nota=None, levanta_montar=RuntimeError("CVM fora do ar - traceback interno sensível"),
    )
    assert "indisponível" in html_render.lower()
    # nunca expõe tipo/mensagem bruta da exceção na tela (mesmo padrão
    # cobrado por tests/test_pregao2_modulos.py pra todo ui/analises_tab.py)
    assert "RuntimeError" not in html_render
    assert "traceback interno sensível" not in html_render


def test_gerar_nota_earnings_isola_falha_de_uma_empresa_da_outra():
    """Chamar _gerar_nota_earnings pra 2 tickers em sequência - a falha
    do primeiro (fonte fora do ar) não pode contaminar nem bloquear o
    segundo (que tem que vir com o resultado real, intacto)."""
    chamadas = {"PETR4": RuntimeError("CVM indisponível"), "VALE3": _nota_vale_disponivel()}

    def _fake_montar(ticker, ano, trimestre):
        resultado = chamadas[ticker]
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    with patch.object(analises_mod.earnings_reviewer, "montar_nota_br", side_effect=_fake_montar), \
         patch.object(analises_mod.earnings_reviewer, "salvar_versao", return_value=True):
        resultado_petr4 = analises_mod._gerar_nota_earnings("PETR4", "BR", {"ano": 2026, "trimestre": 2})
        resultado_vale3 = analises_mod._gerar_nota_earnings("VALE3", "BR", {"ano": 2026, "trimestre": 2})

    assert resultado_petr4["disponivel"] is False
    assert resultado_petr4["motivo"]
    assert "RuntimeError" not in resultado_petr4["motivo"]  # nunca expõe detalhe técnico cru
    assert resultado_vale3["disponivel"] is True
    assert resultado_vale3["ticker"] == "VALE3"


def test_gerar_nota_earnings_falha_de_persistencia_nao_impede_exibicao():
    """Supabase fora do ar na hora de salvar não pode impedir a nota
    JÁ CALCULADA de ser devolvida pra exibição."""
    with patch.object(analises_mod.earnings_reviewer, "montar_nota_br", return_value=_nota_vale_disponivel()), \
         patch.object(analises_mod.earnings_reviewer, "salvar_versao", side_effect=RuntimeError("banco fora do ar")):
        resultado = analises_mod._gerar_nota_earnings("VALE3", "BR", {"ano": 2026, "trimestre": 2})
    assert resultado["disponivel"] is True
    assert resultado["ticker"] == "VALE3"


def test_historico_revisao_isola_falha_de_leitura():
    nota = _nota_vale_disponivel()
    with patch.object(analises_mod.earnings_reviewer, "obter_ultima_versao",
                       side_effect=RuntimeError("Supabase fora do ar")):
        historico = analises_mod._historico_revisao_earnings(nota)
    assert historico == {"anterior": None, "mudancas": []}


def test_historico_revisao_nota_indisponivel_nunca_consulta_nada():
    with patch.object(analises_mod.earnings_reviewer, "obter_ultima_versao") as mock_obter:
        historico = analises_mod._historico_revisao_earnings({"disponivel": False})
    mock_obter.assert_not_called()
    assert historico == {"anterior": None, "mudancas": []}


# ---------------------------------------------------------------------
# FUNÇÕES PURAS DE FORMATAÇÃO / PERÍODO
# ---------------------------------------------------------------------

from datetime import date  # noqa: E402


def test_trimestres_candidatos_br_ordem_decrescente_sem_q4():
    candidatos = analises_mod._trimestres_candidatos_br(date(2026, 10, 26), n=4)
    assert candidatos == [(2026, 3), (2026, 2), (2026, 1), (2025, 3)]
    assert all(tri in (1, 2, 3) for _, tri in candidatos)  # nunca trimestre 4


def test_trimestres_candidatos_br_antes_do_1t_fechar_cai_pro_ano_anterior():
    candidatos = analises_mod._trimestres_candidatos_br(date(2026, 2, 15), n=1)
    assert candidatos == [(2025, 3)]


def test_fmt_moeda_earnings_bi_mi_sinal_negativo_e_indisponivel():
    assert analises_mod._fmt_moeda_earnings(5_000_000.0, "REAL", "MIL") == "R$5,0 bi"
    assert analises_mod._fmt_moeda_earnings(-5_000_000.0, "REAL", "MIL") == "-R$5,0 bi"
    assert analises_mod._fmt_moeda_earnings(None, "REAL", "MIL") == "indisponível"


def test_fmt_variacao_pct_earnings_distingue_ausente_de_estavel():
    assert analises_mod._fmt_variacao_pct_earnings(None) == "indisponível"
    assert "estável" in analises_mod._fmt_variacao_pct_earnings(0.3)
    assert "alta" in analises_mod._fmt_variacao_pct_earnings(5.0)
    assert "queda" in analises_mod._fmt_variacao_pct_earnings(-5.0)


def test_mesmo_dia_ano_anterior_trata_29_de_fevereiro():
    assert analises_mod._mesmo_dia_ano_anterior(date(2024, 2, 29)) == date(2023, 2, 28)
    assert analises_mod._mesmo_dia_ano_anterior(date(2026, 6, 30)) == date(2025, 6, 30)
