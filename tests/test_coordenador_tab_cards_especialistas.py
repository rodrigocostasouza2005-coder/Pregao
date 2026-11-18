# -*- coding: utf-8 -*-
"""Reformulação da apresentação por especialista do Comitê (cards claros,
ui/coordenador_tab.py:_render_parecer_analista/_render_achados_revisao,
2026-11-18) - cobre o achado real confirmado nesta sessão lendo
data/coordenador_central/pareceres.py:montar_pareceres: os 5
especialistas reais (market_researcher/earnings_reviewer/
valuation_comparables/model_builder/valuation_reviewer) têm schemas
ligeiramente diferentes - nem todos têm "pros"/"contras", e os que têm
"achados"/"limitacoes" (valuation_reviewer) teriam esse dado duplicado
e menos estruturado se só reusasse "pros"/"contras" (que lá dentro já
são apenas o mesmo achado reformatado em texto corrido).

Este teste NÃO toca o painel "Divergência entre especialistas do
Comitê" (PR #330, _render_divergencia_comite) - cobre só o card
individual de cada especialista, ao lado dele.

Mesmo padrão de captura de tests/test_coordenador_tab_divergencia_comite.py
(patch.object(tab.st, ...)) - nenhuma função de pareceres.py é tocada
aqui; os dicts de entrada já vêm no formato real que montar_pareceres()
devolve (confirmado lendo o código, não um resumo)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.coordenador_tab as tab


class _FakeCol:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _capturar(fn, *args, **kwargs):
    textos = []

    def _guardar(*a, **k):
        if a:
            textos.append(str(a[0]))

    with patch.object(tab.st, "markdown", side_effect=_guardar), \
         patch.object(tab.st, "caption", side_effect=_guardar), \
         patch.object(tab.st, "warning", side_effect=_guardar), \
         patch.object(tab.st, "info", side_effect=_guardar), \
         patch.object(tab.st, "columns", return_value=(_FakeCol(), _FakeCol())) as mock_columns:
        fn(*args, **kwargs)
    return " ".join(textos), mock_columns


# ============================================================
# Fixtures - schema real de cada 1 dos 5 especialistas, no formato que
# data/coordenador_central/pareceres.py:montar_pareceres realmente
# devolve (confirmado lendo o módulo inteiro nesta sessão).
# ============================================================

def _market_researcher():
    return {
        "id": "market_researcher", "nome": "Market Researcher — Analista de Empresas",
        "recomendacao": "COMPRA", "especialidade": "Fundamentos, qualidade do negócio, crescimento e riscos",
        "metodo": "Síntese heurística dos sinais observáveis.",
        "vies": "POSITIVO", "tese": "Leitura construtiva: ROE positivo de 18,0%.",
        "pros": ["ROE positivo de 18,0%."], "contras": [],
        "preco_alvo": None, "preco_atual": 36.90,
        "indicadores": {"moeda": "R$", "roe_pct": 18.0},
        "fontes": ["Market Researcher", "Valuation Radar", "Earnings Reviewer/CVM"],
    }


def _earnings_reviewer_disponivel():
    return {
        "id": "earnings_reviewer", "nome": "Analista de Resultados",
        "recomendacao": "NEUTRO", "especialidade": "DRE, balanço, fluxo de caixa e evolução trimestral",
        "metodo": "Compara variações YoY.", "vies": "MISTO",
        "tese": "Resultado 3T26 — leitura equilibrada.",
        "pros": ["Receita líquida avançou 4,0% YoY."], "contras": ["Margem bruta contraiu 1,0 p.p."],
        "preco_alvo": None, "periodo": "3T26",
        "fontes": ["CVM — ITR 3T26"],
        "limitacoes": ["Margem bruta sem comparável do mesmo trimestre do ano anterior."],
    }


def _earnings_reviewer_indisponivel():
    # Mesmo schema do ramo "not nota.get('disponivel')" de
    # pareceres.py:_parecer_earnings - pros/contras são [] REAL (o
    # especialista existe e foi acionado, só não achou nada), nunca
    # ausência do campo (diferente de model_builder).
    return {
        "id": "earnings_reviewer", "nome": "Earnings Reviewer — Analista de Resultados",
        "especialidade": "DRE, balanço, fluxo de caixa e evolução trimestral",
        "vies": "SEM BASE SUFICIENTE", "tese": "Nota de resultados indisponível.",
        "pros": [], "contras": [], "preco_alvo": None, "periodo": None,
    }


def _valuation_comparables():
    # Sem "fontes" no dict - campo não existe pra este especialista
    # (ver pareceres.py:_parecer_valuation, nenhum "fontes" é montado).
    return {
        "id": "valuation_comparables", "nome": "Valuation por Múltiplos e Research",
        "recomendacao": "NEUTRO", "especialidade": "DCF, múltiplos, comparáveis e preço-alvo",
        "moeda": "R$", "metodo": "Preço atual × P/L mediano setorial ÷ P/L atual.",
        "vies": "PRÓXIMO À MEDIANA SETORIAL", "tese": "P/L de 9,0x versus mediana setorial 9,5x.",
        "pros": [], "contras": [], "preco_alvo": 39.0, "upside_pct": 6.0, "preco_atual": 36.90,
        "dcf": {"disponivel": False},
    }


def _model_builder():
    # Schema real: NUNCA teve "pros"/"contras" no dict (chave ausente,
    # não lista vazia) - ver pareceres.py:montar_pareceres, bloco
    # analistas.append({"id": "model_builder", ...}).
    return {
        "id": "model_builder", "nome": "Model Builder",
        "especialidade": "Projeção financeira e DCF em três cenários",
        "recomendacao": "MODELADO", "vies": "MODELO DISPONÍVEL",
        "tese": "DCF de 5 anos + Gordon Growth.",
        "preco_alvo": 42.5, "cenarios": {}, "premissas": {},
        "sensibilidade": {"disponivel": False, "motivo": "não calculada."},
        "moeda": "R$", "data_base": "2025-12-31",
        "campos_faltantes": [], "fontes": ["Relatório anual 2025"],
    }


def _valuation_reviewer(achados=None, limitacoes=None, dcf_disponivel=True):
    dcf = {"disponivel": dcf_disponivel}
    return {
        "id": "valuation_reviewer", "nome": "Valuation Reviewer",
        "especialidade": "Revisão independente de cenários, premissas e sensibilidade",
        "recomendacao": "APROVADO" if not achados else "COM RESSALVAS",
        "vies": "APROVADO" if not achados else "REVISÃO COM RESSALVAS",
        "tese": "Revisão concluída.",
        "pros": ["Nenhuma inconsistência encontrada na revisão independente."] if not achados else [],
        "contras": [f"{a['tipo']}: {a['descricao']}" for a in (achados or [])],
        "preco_alvo": 42.5, "upside_pct": 15.2, "preco_atual": 36.90, "moeda": "R$",
        "achados": achados or [], "limitacoes": limitacoes or [],
        "dcf": dcf,
    }


# ============================================================
# 1 teste por especialista real - cada 1 renderiza com os campos que
# de fato tem, nunca quebra, nunca mostra placeholder enganoso.
# ============================================================

def test_market_researcher_mostra_pros_contras_fontes_e_indicadores_reais():
    with patch.object(tab, "_render_indicadores_financeiros") as mock_indicadores:
        textos, mock_columns = _capturar(tab._render_parecer_analista, _market_researcher())
    assert "COMPRA" in textos
    assert "viés: POSITIVO" in textos
    assert "ROE positivo de 18,0%." in textos
    assert "Fontes: Market Researcher, Valuation Radar, Earnings Reviewer/CVM" in textos
    assert "Pontos favoráveis" in textos
    assert "Pontos contrários" in textos
    assert "Sem evidência contrária estruturada." in textos
    mock_indicadores.assert_called_once()
    assert mock_columns.called


def test_earnings_reviewer_disponivel_mostra_pros_contras_fontes_e_limitacoes():
    textos, _ = _capturar(tab._render_parecer_analista, _earnings_reviewer_disponivel())
    assert "Receita líquida avançou 4,0% YoY." in textos
    assert "Margem bruta contraiu 1,0 p.p." in textos
    assert "Fontes: CVM — ITR 3T26" in textos
    assert "Limitações declaradas" in textos
    assert "Margem bruta sem comparável" in textos


def test_earnings_reviewer_indisponivel_mostra_vazio_real_sem_quebrar():
    """pros/contras == [] aqui é um resultado REAL (especialista
    acionado, sem achado) - diferente do model_builder, cujo dict nunca
    tem essas chaves. Os dois casos devem continuar distinguíveis."""
    textos, mock_columns = _capturar(tab._render_parecer_analista, _earnings_reviewer_indisponivel())
    assert "Sem evidência favorável estruturada." in textos
    assert "Sem evidência contrária estruturada." in textos
    assert mock_columns.called


def test_valuation_comparables_sem_fontes_nao_inventa_linha_vazia():
    """valuation_comparables não tem campo "fontes" (confirmado lendo
    pareceres.py:_parecer_valuation) - a linha "Fontes: ..." deve ser
    omitida por completo, nunca aparecer com valor vazio/placeholder."""
    textos, _ = _capturar(tab._render_parecer_analista, _valuation_comparables())
    assert "Fontes:" not in textos
    assert "P/L de 9,0x" in textos


def test_model_builder_sem_pros_contras_nao_mostra_placeholder_enganoso():
    """Achado real: model_builder nunca teve "pros"/"contras" no seu
    dict (ver pareceres.py:montar_pareceres) - antes desta mudança, a
    função genérica ainda assim desenhava as 2 colunas e mostrava "Sem
    evidência favorável/contrária estruturada", sugerindo um campo
    ausente que nunca existiu pra este especialista. Agora o bloco nem
    é desenhado."""
    with patch.object(tab, "_render_parecer_model_builder") as mock_model_builder:
        textos, mock_columns = _capturar(tab._render_parecer_analista, _model_builder())
    assert "Pontos favoráveis" not in textos
    assert "Pontos contrários" not in textos
    assert "Sem evidência favorável estruturada." not in textos
    assert "Sem evidência contrária estruturada." not in textos
    assert not mock_columns.called
    mock_model_builder.assert_called_once()


def test_valuation_reviewer_com_achados_mostra_estrutura_real_sem_pros_contras_genericos():
    achados = [{"tipo": "RASTREABILIDADE", "descricao": "Data-base do modelo não identificada."}]
    with patch.object(tab, "_render_parecer_valuation_reviewer") as mock_reviewer:
        textos, mock_columns = _capturar(
            tab._render_parecer_analista, _valuation_reviewer(achados=achados, limitacoes=["Sensibilidade não calculada."]),
        )
    assert "Achados da revisão independente" in textos
    assert "RASTREABILIDADE" in textos
    assert "Data-base do modelo não identificada." in textos
    assert "Limitações declaradas" in textos
    assert "Sensibilidade não calculada." in textos
    # Nunca os rótulos genéricos (achados/limitações substituem, não convivem).
    assert "Pontos favoráveis" not in textos
    assert "Pontos contrários" not in textos
    assert not mock_columns.called
    mock_reviewer.assert_called_once()


def test_valuation_reviewer_sem_achados_e_revisao_disponivel_mostra_resultado_real():
    """achados == [] com revisão disponível é "revisão concluída, nada
    encontrado" - um resultado real, não ausência de dado."""
    with patch.object(tab, "_render_parecer_valuation_reviewer"):
        textos, _ = _capturar(
            tab._render_parecer_analista, _valuation_reviewer(achados=[], dcf_disponivel=True),
        )
    assert "nenhuma inconsistência encontrada" in textos.lower()
    assert "indisponível" not in textos.lower()


def test_valuation_reviewer_sem_achados_e_revisao_indisponivel_nao_finge_resultado():
    """Revisão que nunca rodou (dcf.disponivel=False) não pode mostrar
    a mesma frase de "nenhuma inconsistência encontrada" - seria fingir
    um resultado que não existe."""
    with patch.object(tab, "_render_parecer_valuation_reviewer"):
        textos, _ = _capturar(
            tab._render_parecer_analista, _valuation_reviewer(achados=[], dcf_disponivel=False),
        )
    assert "nenhuma inconsistência encontrada" not in textos.lower()
    assert "ainda não disponível" in textos.lower()


# ============================================================
# Nenhum campo inventado (achado de auditoria anterior confirmado:
# "confiança por especialista" e "o que faria mudar de opinião" não
# existem hoje em nenhum dos 5 especialistas) - varre os 5 schemas
# reais de uma vez.
# ============================================================

def test_nenhum_campo_inventado_aparece_em_nenhum_dos_5_especialistas():
    termos_proibidos = (
        "confiança do especialista", "confiança por especialista",
        "o que faria mudar de opinião", "mudaria de opinião", "muda de opinião",
    )
    fixtures = [
        _market_researcher(), _earnings_reviewer_disponivel(), _valuation_comparables(),
        _model_builder(), _valuation_reviewer(achados=[{"tipo": "X", "descricao": "Y"}]),
    ]
    with patch.object(tab, "_render_indicadores_financeiros"), \
         patch.object(tab, "_render_parecer_model_builder"), \
         patch.object(tab, "_render_parecer_valuation_reviewer"):
        for analista in fixtures:
            textos, _ = _capturar(tab._render_parecer_analista, analista)
            textos_lower = textos.lower()
            for termo in termos_proibidos:
                assert termo not in textos_lower, f"{analista['id']}: termo inventado '{termo}' apareceu"
            # Nenhum "N/A" solto como se o campo devesse existir.
            assert "n/a" not in textos_lower
