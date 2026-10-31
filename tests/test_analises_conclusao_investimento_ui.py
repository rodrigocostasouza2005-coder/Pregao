# -*- coding: utf-8 -*-
"""CONCLUSÃO DE INVESTIMENTO (ui/analises_tab.py:render_conclusao_investimento)
- complemento de render_equity_research_executivo (tests/
test_analises_equity_research_ui.py): aquele painel já mostra momento/
catalisadores/mudanças/research das casas; este fecha a análise de
ANÁLISES > Empresas com uma conclusão fundamentalista completa em 14
seções (resumo executivo, qualidade do negócio, crescimento e
rentabilidade, estrutura de capital, geração de caixa, tese positiva,
tese negativa, valuation, catalisadores, riscos e invalidação da tese,
consenso de research, cenários, confiança da análise, lacunas de
informação), reaproveitando o MESMO dict de analise_ticker (via
_analise_ticker_cacheada, zero consulta nova) e a Tese própria do
usuário quando existir.

1. `_montar_conclusao` isolada (função pura, sem Streamlit) - garante
   que cada resposta cita evidência real ou declara "dado insuficiente"
   explícito, que lacunas estruturais nunca são repetidas por extenso em
   mais de uma seção (só citadas por nome, texto completo só em "Lacunas
   de informação"), e que nunca aparece uma recomendação de compra/venda.
2. `_dcf_calculo`, `_calcular_confianca`, `_montar_cenarios` isoladas -
   cálculos puros usados pela conclusão.
3. `render_conclusao_investimento` em bare mode - mesmo padrão de
   tests/test_analises_equity_research_ui.py (patch de st.markdown/
   caption/warning/container, sem ScriptRunContext real)."""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import ui.analises_tab as at_mod

_HOJE = date.today()

_FUNDAMENTOS = {
    "ticker": "WEGE3", "preco": 40.0, "pl": 28.5, "pvp": 9.1, "dividend_yield": 1.2,
    "roe": 32.0, "margem_liquida": 14.0, "divida_liquida_ebitda": 0.3,
    "valor_mercado": 150_000_000_000, "ebitda": 6_000_000_000, "ev_ebitda": 25.1,
    "fluxo_caixa_livre": 3_000_000_000, "desatualizado": False, "alerta_qualidade": [],
}

_CATALISADOR = {
    "ticker": "WEGE3", "categoria": "Resultado do 3T26", "data": _HOJE + timedelta(days=10),
    "status_label": "CONFIRMADO", "confirmado": True, "fonte_label": "RI WEG", "fonte_url": "https://ri.weg.net",
}

_COBERTURA_COM_DADO = {
    "ticker": "WEGE3", "janela_dias": 30,
    "cobertura": [{"casa": "Genial Analisa", "data": "2026-10-20", "titulo": "WEGE3: elevamos para COMPRA",
                   "link": "https://genialanalisa.com.br/x", "recomendacao": "COMPRA", "preco_alvo": 45.0}],
    "sem_cobertura": ["BTG Pactual Research"], "divergencia": None,
}

_HISTORICO_DISPONIVEL = {
    "disponivel": True, "periodos": ["1T26", "2T26", "3T26"],
    "receita_liquida": {"yoy_pct_serie": [2.0, 5.0, 9.0], "tendencia": "RECUPERACAO"},
    "ebit": {"yoy_pct_serie": [1.0, 3.0, 6.0], "tendencia": "RECUPERACAO"},
    "lucro_liquido_consolidado": {"yoy_pct_serie": [0.5, 1.0, 1.2], "tendencia": "ESTABILIDADE"},
    "margem_bruta_pct": {"serie": [38.0, 38.5, 39.0], "tendencia": "ESTABILIDADE"},
    "ultima_nota": {"periodo_label": "3T26", "fontes": [{"nome": "CVM - dados.cvm.gov.br (ITR)"}]},
}

_SETORIAL_DISPONIVEL = {
    "setor": "Bens de Capital e Industrial", "pares_considerados": 6, "insuficiente": False,
    "pl_mediana": 18.0, "pl_mediana_n": 5, "pvp_mediana": 4.0, "pvp_mediana_n": 5,
    "dy_mediana": 2.5, "dy_mediana_n": 4,
}

_ANALISE_COMPLETA = {
    "ticker": "WEGE3", "gerado_em": None, "fundamentos": _FUNDAMENTOS, "catalisadores": [_CATALISADOR],
    "mudancas_tese": [], "riscos_indicadores": [],
    "cobertura_research": _COBERTURA_COM_DADO, "fundamentos_historicos": _HISTORICO_DISPONIVEL,
    "comparativo_setorial": _SETORIAL_DISPONIVEL, "fontes_indisponiveis": [],
}

_ANALISE_VAZIA = {
    "ticker": "XPTO3", "gerado_em": None, "fundamentos": None, "catalisadores": None, "mudancas_tese": None,
    "riscos_indicadores": None, "cobertura_research": None, "fundamentos_historicos": None,
    "comparativo_setorial": None,
    "fontes_indisponiveis": ["fundamentos", "contexto_mercado", "cobertura_research",
                             "historico_fundamentos", "comparativo_setorial"],
}

_PERGUNTAS_ESPERADAS = (
    "Resumo executivo", "Qualidade do negócio", "Crescimento e rentabilidade", "Estrutura de capital",
    "Geração de caixa", "Tese positiva", "Tese negativa", "Valuation", "Catalisadores",
    "Riscos e invalidação da tese", "Consenso de Research", "Cenários (otimista, base e pessimista)",
    "Confiança da análise", "Lacunas de informação",
)


# --- _montar_conclusao (pura, sem Streamlit) --------------------------------

def test_conclusao_tem_as_14_secoes_na_ordem_certa():
    blocos = at_mod._montar_conclusao(_ANALISE_COMPLETA, tese=None)
    assert [b["pergunta"] for b in blocos] == list(_PERGUNTAS_ESPERADAS)
    for b in blocos:
        assert b["resposta"]  # nunca string vazia


def test_conclusao_sem_evidencia_declara_dado_insuficiente():
    blocos = at_mod._montar_conclusao(_ANALISE_VAZIA, tese=None)
    por_pergunta = {b["pergunta"]: b for b in blocos}
    for pergunta in ("Qualidade do negócio", "Crescimento e rentabilidade", "Estrutura de capital",
                      "Geração de caixa", "Tese positiva", "Valuation", "Catalisadores",
                      "Riscos e invalidação da tese", "Consenso de Research"):
        assert "Dado insuficiente" in por_pergunta[pergunta]["resposta"], pergunta
        assert por_pergunta[pergunta]["tipo_evidencia"] == at_mod.TIPO_INSUFICIENTE, pergunta


def test_conclusao_cita_evidencia_real_quando_existe():
    blocos = at_mod._montar_conclusao(_ANALISE_COMPLETA, tese=None)
    por_pergunta = {b["pergunta"]: b for b in blocos}

    qualidade = por_pergunta["Qualidade do negócio"]
    assert "recuperação" in qualidade["resposta"]
    assert qualidade["tipo_evidencia"] == at_mod.TIPO_CALCULO

    positiva = por_pergunta["Tese positiva"]
    assert "Genial Analisa: COMPRA" in positiva["resposta"]

    catalisadores = por_pergunta["Catalisadores"]
    assert "Resultado do 3T26" in catalisadores["resposta"]
    assert "confirmado" in catalisadores["resposta"]

    valuation = por_pergunta["Valuation"]
    assert "P/L 28.5x" in valuation["resposta"] or "P/L 28,5x" in valuation["resposta"]
    assert "EV/EBITDA" in valuation["resposta"]
    assert "Mediana do setor" in valuation["resposta"]

    consenso = por_pergunta["Consenso de Research"]
    assert "Genial Analisa" in consenso["resposta"]
    assert "sem cobertura" in consenso["resposta"].lower() or "sem cobertura" in consenso["resposta"]


def test_conclusao_divergencia_so_aparece_quando_estruturada():
    analise = dict(_ANALISE_COMPLETA)
    analise["cobertura_research"] = {
        **_COBERTURA_COM_DADO,
        "divergencia": {"descricao": "Recomendação estruturada diverge entre casas pra WEGE3.",
                         "por_casa": {"Genial Analisa": "COMPRA", "Monte Bravo": "VENDA"}},
    }
    blocos = at_mod._montar_conclusao(analise, tese=None)
    por_pergunta = {b["pergunta"]: b for b in blocos}
    assert "diverge entre casas" in por_pergunta["Tese negativa"]["resposta"]
    assert "diverge entre casas" in por_pergunta["Consenso de Research"]["resposta"]


def test_conclusao_usa_riscos_da_tese_propria_quando_existe():
    tese = {"ticker": "WEGE3", "riscos": ["Câmbio desfavorável pode comprimir margem de exportação"],
            "registrado_em": "2026-10-01", "n_versoes": 2}
    blocos = at_mod._montar_conclusao(_ANALISE_COMPLETA, tese=tese)
    por_pergunta = {b["pergunta"]: b for b in blocos}
    invalida = por_pergunta["Riscos e invalidação da tese"]
    assert "Câmbio desfavorável" in invalida["resposta"]
    assert "Tese própria" in invalida["resposta"]


def test_conclusao_nunca_recomenda_compra_ou_venda():
    for analise, tese in ((_ANALISE_COMPLETA, None), (_ANALISE_VAZIA, None)):
        blocos = at_mod._montar_conclusao(analise, tese)
        texto = " ".join(b["resposta"].lower() for b in blocos)
        for palavra_proibida in ("recomendo comprar", "recomendo vender", "deve comprar", "deve vender"):
            assert palavra_proibida not in texto


def test_conclusao_nunca_trata_catalisador_futuro_como_positivo_automatico():
    # catalisador sem confirmação (estimado/prazo regulatório) não é tratado
    # como FATO positivo - vira ESTIMATIVA_TERCEIRO, nunca uma leitura bullish.
    catalisador_estimado = dict(_CATALISADOR, confirmado=False, status_label="ESTIMADO")
    analise = dict(_ANALISE_COMPLETA, catalisadores=[catalisador_estimado])
    blocos = at_mod._montar_conclusao(analise, tese=None)
    catalisadores = next(b for b in blocos if b["pergunta"] == "Catalisadores")
    assert catalisadores["tipo_evidencia"] == at_mod.TIPO_ESTIMATIVA_TERCEIRO


def test_lacuna_estrutural_nunca_repetida_por_extenso_em_mais_de_uma_secao():
    blocos = at_mod._montar_conclusao(_ANALISE_COMPLETA, tese=None)
    texto_lacunas = next(b for b in blocos if b["pergunta"] == "Lacunas de informação")["resposta"]
    assert "ROIC" in texto_lacunas
    # o texto completo da lacuna de ROIC só aparece na seção de Lacunas -
    # nas demais seções que a mencionam, só "(ver Lacunas)" curto.
    outras_secoes = [b["resposta"] for b in blocos if b["pergunta"] != "Lacunas de informação"]
    for resposta in outras_secoes:
        assert "calcular à mão viraria estimativa" not in resposta


def test_confianca_alta_quando_maioria_fato_ou_calculo():
    blocos = at_mod._montar_conclusao(_ANALISE_COMPLETA, tese=None)
    confianca = next(b for b in blocos if b["pergunta"] == "Confiança da análise")
    assert "ALTA" in confianca["resposta"] or "MÉDIA" in confianca["resposta"]
    assert "/100" in confianca["resposta"]


def test_confianca_baixa_quando_tudo_insuficiente():
    blocos = at_mod._montar_conclusao(_ANALISE_VAZIA, tese=None)
    confianca = next(b for b in blocos if b["pergunta"] == "Confiança da análise")
    assert "BAIXA" in confianca["resposta"]


def test_cenarios_hipotese_do_analista_quando_ha_insumo():
    blocos = at_mod._montar_conclusao(_ANALISE_COMPLETA, tese=None)
    cenarios = next(b for b in blocos if b["pergunta"] == "Cenários (otimista, base e pessimista)")
    assert cenarios["tipo_evidencia"] == at_mod.TIPO_HIPOTESE
    assert "OTIMISTA" in cenarios["resposta"] and "BASE" in cenarios["resposta"] and "PESSIMISTA" in cenarios["resposta"]


def test_cenarios_dado_insuficiente_sem_nenhum_insumo():
    analise_sem_insumo = dict(_ANALISE_VAZIA, cobertura_research={"ticker": "XPTO3", "cobertura": [],
                                                                    "sem_cobertura": [], "divergencia": None})
    blocos = at_mod._montar_conclusao(analise_sem_insumo, tese=None)
    cenarios = next(b for b in blocos if b["pergunta"] == "Cenários (otimista, base e pessimista)")
    assert cenarios["tipo_evidencia"] == at_mod.TIPO_INSUFICIENTE


# --- _dcf_calculo (pura) -----------------------------------------------------

def test_dcf_bloqueado_sem_premissa_do_usuario():
    resultado = at_mod._dcf_calculo(fcf_atual=1_000_000, taxa_crescimento_pct=None, taxa_desconto_pct=10)
    assert resultado["calculavel"] is False
    assert "taxa de crescimento" in resultado["motivo"]


def test_dcf_bloqueado_sem_fluxo_de_caixa_livre():
    resultado = at_mod._dcf_calculo(fcf_atual=None, taxa_crescimento_pct=5, taxa_desconto_pct=10)
    assert resultado["calculavel"] is False
    assert "fluxo de caixa livre" in resultado["motivo"]


def test_dcf_rejeita_desconto_menor_ou_igual_crescimento():
    resultado = at_mod._dcf_calculo(fcf_atual=1_000_000, taxa_crescimento_pct=10, taxa_desconto_pct=8)
    assert resultado["calculavel"] is False
    assert "maior que a taxa de crescimento" in resultado["motivo"]


def test_dcf_calcula_com_premissas_completas():
    resultado = at_mod._dcf_calculo(fcf_atual=1_000_000, taxa_crescimento_pct=5, taxa_desconto_pct=12,
                                     valor_mercado=8_000_000)
    assert resultado["calculavel"] is True
    assert resultado["valor_justo_estimado"] > 0
    assert resultado["premissas"]["taxa_crescimento_pct"] == 5
    assert "potencial_pct" in resultado


# --- render_conclusao_investimento (bare mode, mesmo padrão de
#     test_analises_equity_research_ui.py) ------------------------------------

def _capturar_render(analise=None, tese=None, levanta=None):
    blocos = []
    with patch.object(at_mod, "_analise_ticker_cacheada",
                       side_effect=levanta if levanta else lambda t: analise), \
         patch.object(at_mod, "scorecard", return_value=tese), \
         patch.object(at_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(str(texto))), \
         patch.object(at_mod.st, "caption", side_effect=lambda texto, **_k: blocos.append(str(texto))), \
         patch.object(at_mod.st, "warning", side_effect=lambda texto, **_k: blocos.append(str(texto))), \
         patch.object(at_mod.st, "columns",
                      side_effect=lambda n, **_k: [MagicMock(number_input=lambda *a, **k: None) for _ in range(n)]), \
         patch.object(at_mod.st, "container") as container_mock:
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        at_mod.render_conclusao_investimento("WEGE3", {"formato_numerico": "BR"}, {"sub": "sub-teste"})
    return "\n".join(blocos)


def test_render_fonte_indisponivel_avisa_e_nunca_lanca_excecao():
    html_render = _capturar_render(levanta=lambda t: (_ for _ in ()).throw(RuntimeError("Supabase fora do ar")))
    assert "indisponível agora" in html_render


def test_render_mostra_todas_as_secoes_e_tese_propria():
    tese = {"ticker": "WEGE3", "riscos": [], "registrado_em": "2026-10-01T10:00:00", "n_versoes": 1}
    html_render = _capturar_render(_ANALISE_COMPLETA, tese=tese)
    assert "CONCLUSÃO DE INVESTIMENTO" in html_render
    for pergunta in _PERGUNTAS_ESPERADAS:
        assert pergunta in html_render, pergunta
    assert "Você já registrou uma Tese própria para WEGE3" in html_render


def test_render_sem_tese_propria_sugere_registrar():
    html_render = _capturar_render(_ANALISE_VAZIA, tese=None)
    assert "Você ainda não registrou uma Tese própria" in html_render
