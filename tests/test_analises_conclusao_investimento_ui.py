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


# ---------------------------------------------------------------------
# VAZAMENTO DE TEXTO TÉCNICO CORRIGIDO (Fase 1, 2026-11-02) -
# barra_contexto_empresa nunca pode mencionar nome de arquivo .py pro
# usuário final quando o ticker não tem setor classificado.
# ---------------------------------------------------------------------

def test_barra_contexto_empresa_setor_nao_classificado_nunca_menciona_py():
    capturado = []
    col_mock = MagicMock()
    with patch.object(at_mod, "setores_do_ticker", return_value=[]), \
         patch.object(at_mod.st, "columns", return_value=[col_mock, col_mock, col_mock, col_mock]), \
         patch.object(at_mod.st, "button"), \
         patch.object(at_mod.st, "container"), \
         patch.object(at_mod.st, "caption", side_effect=lambda t, **k: capturado.append(str(t))):
        at_mod.barra_contexto_empresa("XPTO3", {"watchlist": []})
    texto = "\n".join(capturado)
    assert "Setor não classificado" in texto
    assert ".py" not in texto


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


# ---------------------------------------------------------------------
# METODOLOGIA v2 DE CONFIANÇA DA ANÁLISE (Fase 1, 2026-11-02) - correção
# de causa raiz, não cosmética. Bug real diagnosticado (caso BEEF3/
# Minerva S.A.): a v1 fazia média aritmética SIMPLES (peso igual pras
# 11 seções) - um ticker com a DRE oficial 100% indisponível podia
# chegar a 70-80/100 (ALTA) porque "Crescimento e rentabilidade" tem
# fallback de ROE (yfinance) que não depende da DRE/CVM, mascarando a
# ausência da fonte crítica. v2 pondera por criticidade da seção E
# trava um piso explícito (nunca ALTA com DRE indisponível) que não é
# compensável por outras seções fortes - ver _calcular_confianca em
# ui/analises_tab.py pra tabela de pesos e justificativa completa.
# ---------------------------------------------------------------------

_FUNDAMENTOS_SAUDAVEL = {
    "preco": 40.0, "pl": 12.0, "pvp": 1.8, "dividend_yield": 6.0,
    "roe": 18.0, "margem_liquida": 12.0, "divida_liquida_ebitda": 1.2,
    "valor_mercado": 80_000_000_000, "ebitda": 20_000_000_000, "ev_ebitda": 5.5,
    "fluxo_caixa_livre": 8_000_000_000, "desatualizado": False, "alerta_qualidade": [],
}

_CATALISADOR_SAUDAVEL = {
    "categoria": "Resultado trimestral", "data": _HOJE + timedelta(days=12),
    "status_label": "CONFIRMADO", "confirmado": True, "fonte_label": "RI", "fonte_url": "https://ri.exemplo.com.br",
}

_COBERTURA_SAUDAVEL = {
    "janela_dias": 30,
    "cobertura": [{"casa": "Genial Analisa", "data": "2026-10-20", "titulo": "mantemos COMPRA",
                   "link": "https://x", "recomendacao": "COMPRA", "preco_alvo": 48.0}],
    "sem_cobertura": [], "divergencia": None,
}

_HISTORICO_SAUDAVEL = {
    "disponivel": True, "periodos": ["1T26", "2T26", "3T26"],
    "receita_liquida": {"yoy_pct_serie": [2.0, 6.0, 10.0], "tendencia": "RECUPERACAO"},
    "ebit": {"yoy_pct_serie": [1.0, 4.0, 7.0], "tendencia": "RECUPERACAO"},
    "lucro_liquido_consolidado": {"yoy_pct_serie": [1.0, 2.0, 2.5], "tendencia": "ESTABILIDADE"},
    "margem_bruta_pct": {"serie": [30.0, 30.5, 31.0], "tendencia": "ESTABILIDADE"},
    "ultima_nota": {"periodo_label": "3T26", "fontes": [{"nome": "CVM - dados.cvm.gov.br (ITR)"}]},
}


def _analise_saudavel(ticker: str) -> dict:
    """Cenário de dados COMPLETOS (DRE disponível, fundamentos sãos,
    cobertura/catalisador/risco presentes) - usado pelos testes
    PETR4/VALE3/ITUB4 abaixo pra confirmar que a nova metodologia NÃO
    penaliza indevidamente um ticker com dado bom."""
    return {
        "ticker": ticker, "gerado_em": None, "fundamentos": dict(_FUNDAMENTOS_SAUDAVEL, ticker=ticker),
        "catalisadores": [dict(_CATALISADOR_SAUDAVEL, ticker=ticker)], "mudancas_tese": [],
        "riscos_indicadores": ["Exposição a preços de commodity/câmbio relevante pro resultado"],
        "cobertura_research": dict(_COBERTURA_SAUDAVEL, ticker=ticker),
        "fundamentos_historicos": _HISTORICO_SAUDAVEL,
        "comparativo_setorial": _SETORIAL_DISPONIVEL, "fontes_indisponiveis": [],
    }


def test_petr4_dados_completos_nao_e_penalizado_indevidamente():
    blocos = at_mod._montar_conclusao(_analise_saudavel("PETR4"), tese=None)
    confianca = next(b for b in blocos if b["pergunta"] == "Confiança da análise")
    assert "ALTA" in confianca["resposta"]


def test_vale3_dados_completos_nao_e_penalizado_indevidamente():
    blocos = at_mod._montar_conclusao(_analise_saudavel("VALE3"), tese=None)
    confianca = next(b for b in blocos if b["pergunta"] == "Confiança da análise")
    assert "ALTA" in confianca["resposta"]


def test_itub4_dados_completos_nao_e_penalizado_indevidamente():
    blocos = at_mod._montar_conclusao(_analise_saudavel("ITUB4"), tese=None)
    confianca = next(b for b in blocos if b["pergunta"] == "Confiança da análise")
    assert "ALTA" in confianca["resposta"]


# --- BEEF3/Minerva (DRE indisponível) - teste CENTRAL do bug ---------------

_FUNDAMENTOS_BEEF3_SIMULADO = {
    "preco": 8.0, "pl": 12.0, "pvp": 1.1, "dividend_yield": 3.0,
    "roe": 15.0, "margem_liquida": 2.0, "divida_liquida_ebitda": 3.5,
    "valor_mercado": 4_000_000_000, "ebitda": 1_500_000_000, "ev_ebitda": 6.2,
    "fluxo_caixa_livre": 300_000_000, "desatualizado": False, "alerta_qualidade": [],
}

_CATALISADOR_BEEF3 = {
    "categoria": "Resultado do 3T26", "data": _HOJE + timedelta(days=15),
    "status_label": "CONFIRMADO", "confirmado": True, "fonte_label": "RI Minerva",
    "fonte_url": "https://ri.minervafoods.com",
}

_COBERTURA_BEEF3 = {
    "janela_dias": 30,
    "cobertura": [{"casa": "Genial Analisa", "data": "2026-10-15", "titulo": "mantemos COMPRA",
                   "link": "https://x", "recomendacao": "COMPRA", "preco_alvo": 10.0}],
    "sem_cobertura": [], "divergencia": None,
}

# DRE oficial (CVM) indisponível - mesma forma que
# data/earnings/reviewer.py:serie_historica_br devolve quando nenhum
# trimestre teve DRE publicada na CVM pra este ticker (qualquer uma das
# 3 causas específicas de data/earnings/cvm_dre.py resulta nisso aqui).
_HISTORICO_INDISPONIVEL_BEEF3 = {
    "disponivel": False,
    "motivo": "nenhum trimestre com DRE disponível na CVM para este ticker nos períodos civis "
              "verificados (empresa pode não ter CNPJ mapeado, ou a fonte CVM não tem registro "
              "desse período).",
    "periodos": [],
}

_ANALISE_BEEF3_SIMULADA = {
    "ticker": "BEEF3", "gerado_em": None, "fundamentos": _FUNDAMENTOS_BEEF3_SIMULADO,
    "catalisadores": [_CATALISADOR_BEEF3], "mudancas_tese": [],
    "riscos_indicadores": ["Exposição cambial relevante em dívida denominada em dólar"],
    "cobertura_research": _COBERTURA_BEEF3, "fundamentos_historicos": _HISTORICO_INDISPONIVEL_BEEF3,
    "comparativo_setorial": None, "fontes_indisponiveis": [],
}


def test_historico_ausente_nao_aplica_piso_cvm_a_ativos_sem_serie_br():\n    """Historico=None e ausencia normal da serie internacional nesta versao;\n    nao pode ser confundido com DRE/CVM explicitamente indisponivel para\n    uma empresa brasileira."""\n    secoes = [\n        {"pergunta": nome, "tipo_evidencia": at_mod.TIPO_FATO}\n        for nome in at_mod._PESO_CONFIANCA_POR_SECAO\n    ]\n    confianca = at_mod._calcular_confianca(\n        secoes, historico=None, fundamentos={"desatualizado": False},\n    )\n    assert confianca["dre_indisponivel"] is False\n    assert confianca["nivel"] == "ALTA"\n\n\ndef test_beef3_minerva_dre_indisponivel_nunca_classifica_confianca_como_alta():
    """Regressão do bug real diagnosticado (caso BEEF3/Minerva S.A.
    citado na investigação original). Com a metodologia ANTIGA (média
    aritmética simples, 11 seções com peso igual), este cenário
    classificava ALTA (70-80/100) - o ROE do yfinance (fallback de
    "Crescimento e rentabilidade") mascarava a ausência total da DRE
    oficial da CVM, e nenhuma outra seção "sabia" que a fonte crítica
    estava faltando. Este teste TERIA FALHADO com o código antigo
    (confianca['nivel'] teria sido "ALTA") e tem que passar agora: o
    score PONDERADO bruto ainda fecha >=70 (prova de que o peso por
    criticidade, sozinho, não bastaria - ver comentário em
    ui/analises_tab.py), mas o piso explícito trava o nível em MÉDIA."""
    secoes = [b for b in at_mod._montar_conclusao(_ANALISE_BEEF3_SIMULADA, tese=None)
              if b["pergunta"] not in ("Resumo executivo", "Confiança da análise", "Lacunas de informação")]
    confianca = at_mod._calcular_confianca(
        secoes, historico=_HISTORICO_INDISPONIVEL_BEEF3, fundamentos=_FUNDAMENTOS_BEEF3_SIMULADO,
    )
    assert confianca["dre_indisponivel"] is True
    assert confianca["score"] >= 70  # prova que a regra antiga (score>=70 -> ALTA) teria classificado ALTA
    assert confianca["nivel"] == "MÉDIA"  # piso explícito: nunca ALTA com DRE indisponível
    assert any("DRE/CVM" in p or "demonstração financeira oficial" in p
               for p in confianca["penalidades_aplicadas"])

    blocos = at_mod._montar_conclusao(_ANALISE_BEEF3_SIMULADA, tese=None)
    bloco_confianca = next(b for b in blocos if b["pergunta"] == "Confiança da análise")
    assert "MÉDIA" in bloco_confianca["resposta"]
    assert "risco da tese" in bloco_confianca["resposta"]  # distingue os 2 conceitos explicitamente


def test_beef3_render_conclusao_investimento_nunca_lanca_excecao():
    """Garante que a UI inteira (não só a função pura) nunca lança
    excecao com DRE indisponível + demais dados completos."""
    html_render = _capturar_render(_ANALISE_BEEF3_SIMULADA, tese=None)
    assert "CONCLUSÃO DE INVESTIMENTO" in html_render
    assert "MÉDIA" in html_render


# --- múltiplas lacunas (nível mais baixo, mesmo sem envolver a DRE) --------

def test_confianca_multiplas_lacunas_fica_baixa_mesmo_com_dre_disponivel():
    """Lacunas estruturais (não só a DRE) também têm que arrastar o
    score pra baixo - prova que o piso explícito não é a ÚNICA defesa
    da metodologia, os pesos por criticidade também respondem a dado
    ausente em seções centrais (Estrutura de capital/Geração de caixa/
    Valuation)."""
    analise = dict(_analise_saudavel("XPTO3"))
    fundamentos_pobres = {"preco": None, "desatualizado": False, "alerta_qualidade": []}
    analise["fundamentos"] = fundamentos_pobres
    analise["catalisadores"] = None
    analise["riscos_indicadores"] = []
    analise["cobertura_research"] = {"cobertura": [], "sem_cobertura": [], "divergencia": None}
    analise["comparativo_setorial"] = None
    blocos = at_mod._montar_conclusao(analise, tese=None)
    confianca = next(b for b in blocos if b["pergunta"] == "Confiança da análise")
    assert "BAIXA" in confianca["resposta"]


# --- dados desatualizados (fallback/cache) - penalidade visível ------------

def test_confianca_dados_desatualizados_aplica_penalidade_visivel():
    analise_atual = _analise_saudavel("PETR4")
    analise_desatualizada = dict(analise_atual, fundamentos=dict(analise_atual["fundamentos"], desatualizado=True))

    secoes_atual = [b for b in at_mod._montar_conclusao(analise_atual, tese=None)
                    if b["pergunta"] not in ("Resumo executivo", "Confiança da análise", "Lacunas de informação")]
    secoes_desatualizada = [b for b in at_mod._montar_conclusao(analise_desatualizada, tese=None)
                            if b["pergunta"] not in ("Resumo executivo", "Confiança da análise", "Lacunas de informação")]

    confianca_atual = at_mod._calcular_confianca(
        secoes_atual, historico=_HISTORICO_SAUDAVEL, fundamentos=analise_atual["fundamentos"])
    confianca_desatualizada = at_mod._calcular_confianca(
        secoes_desatualizada, historico=_HISTORICO_SAUDAVEL, fundamentos=analise_desatualizada["fundamentos"])

    assert confianca_desatualizada["score"] < confianca_atual["score"]
    assert confianca_desatualizada["penalidades_aplicadas"]
    assert "fallback/cache" in confianca_desatualizada["motivo"]

    blocos = at_mod._montar_conclusao(analise_desatualizada, tese=None)
    bloco_confianca = next(b for b in blocos if b["pergunta"] == "Confiança da análise")
    assert "fallback/cache" in bloco_confianca["resposta"]


def test_confianca_dados_desatualizados_render_nunca_lanca_excecao():
    analise_atual = _analise_saudavel("VALE3")
    analise_desatualizada = dict(analise_atual, fundamentos=dict(analise_atual["fundamentos"], desatualizado=True))
    html_render = _capturar_render(analise_desatualizada, tese=None)
    assert "CONCLUSÃO DE INVESTIMENTO" in html_render


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
