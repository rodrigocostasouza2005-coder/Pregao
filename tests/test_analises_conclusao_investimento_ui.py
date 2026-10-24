# -*- coding: utf-8 -*-
"""CONCLUSÃO DE INVESTIMENTO (ui/analises_tab.py:render_conclusao_investimento)
- complemento de render_equity_research_executivo (tests/
test_analises_equity_research_ui.py): aquele painel já mostra momento/
catalisadores/mudanças/research das casas; este fecha a análise de
ANÁLISES > Empresas sintetizando as 7 perguntas de equity research
(qualidade do negócio, momento, tese a favor/contra, avaliação, o que
monitorar, o que invalidaria), reaproveitando o MESMO dict de
analise_ticker (via _analise_ticker_cacheada, zero consulta nova) e a
Tese própria do usuário quando existir.

1. `_montar_conclusao` isolada (função pura, sem Streamlit) - garante
   que cada resposta cita evidência real ou declara "dado insuficiente"
   explícito, e que nunca aparece uma recomendação de compra/venda.
2. `render_conclusao_investimento` em bare mode - mesmo padrão de
   tests/test_analises_equity_research_ui.py (patch de st.markdown/
   caption/warning/container, sem ScriptRunContext real)."""
from datetime import date, timedelta
from unittest.mock import patch

import ui.analises_tab as at_mod

_HOJE = date.today()

_FUNDAMENTOS = {
    "ticker": "WEGE3", "preco": 40.0, "pl": 28.5, "pvp": 9.1, "dividend_yield": 1.2,
    "roe": 32.0, "margem_liquida": 14.0, "divida_liquida_ebitda": 0.3,
    "valor_mercado": 150_000_000_000, "alerta_qualidade": [],
}

_CATALISADOR = {
    "ticker": "WEGE3", "categoria": "Resultado do 3T26", "data": _HOJE + timedelta(days=10),
    "status_label": "CONFIRMADO", "confirmado": True, "fonte_label": "RI WEG", "fonte_url": "https://ri.weg.net",
}

_MUDANCA = {
    "ticker": "WEGE3", "categoria": "Mudança de recomendação", "descricao": "Genial elevou WEGE3 para COMPRA",
    "relevancia": "alta", "data_evento": _HOJE - timedelta(days=2), "tipo_evidencia": "FATO",
    "fonte_label": "Genial Analisa", "fonte_url": "https://genialanalisa.com.br/x",
}

_COBERTURA_COM_DADO = {
    "ticker": "WEGE3", "janela_dias": 30,
    "cobertura": [{"casa": "Genial Analisa", "data": "2026-10-20", "titulo": "WEGE3: elevamos para COMPRA",
                   "link": "https://genialanalisa.com.br/x", "recomendacao": "COMPRA", "preco_alvo": 45.0}],
    "sem_cobertura": ["BTG Pactual Research"], "divergencia": None,
}

_ANALISE_COMPLETA = {
    "ticker": "WEGE3", "fundamentos": _FUNDAMENTOS, "catalisadores": [_CATALISADOR],
    "mudancas_tese": [_MUDANCA], "riscos_indicadores": [],
    "cobertura_research": _COBERTURA_COM_DADO, "fontes_indisponiveis": [],
}

_ANALISE_VAZIA = {
    "ticker": "XPTO3", "fundamentos": None, "catalisadores": None, "mudancas_tese": None,
    "riscos_indicadores": None, "cobertura_research": None,
    "fontes_indisponiveis": ["fundamentos", "contexto_mercado", "cobertura_research"],
}


# --- _montar_conclusao (pura, sem Streamlit) --------------------------------

def test_conclusao_sem_evidencia_declara_dado_insuficiente_em_tudo():
    blocos = at_mod._montar_conclusao(_ANALISE_VAZIA, tese=None)
    assert len(blocos) == 8  # 7 perguntas do pedido + confiança/lacunas
    for b in blocos:
        assert b["resposta"]  # nunca string vazia
    qualidade = next(b for b in blocos if b["pergunta"] == "Qualidade do negócio")
    assert "Dado insuficiente" in qualidade["resposta"]
    assert qualidade["tipo_evidencia"] == at_mod.TIPO_INSUFICIENTE


def test_conclusao_cita_evidencia_real_quando_existe():
    blocos = at_mod._montar_conclusao(_ANALISE_COMPLETA, tese=None)
    momento = next(b for b in blocos if b["pergunta"] == "Momento atual")
    assert "Genial elevou WEGE3 para COMPRA" in momento["resposta"]
    assert momento["tipo_evidencia"] == "FATO"

    positiva = next(b for b in blocos if b["pergunta"] == "O que sustenta uma leitura positiva")
    assert "Genial Analisa: COMPRA" in positiva["resposta"]
    assert "Resultado do 3T26" in positiva["resposta"]

    avaliacao = next(b for b in blocos if b["pergunta"] == "Avaliação (caro ou barato)")
    assert "P/L 28.5x" in avaliacao["resposta"] or "P/L 28,5x" in avaliacao["resposta"]


def test_conclusao_divergencia_so_aparece_quando_estruturada():
    analise = dict(_ANALISE_COMPLETA)
    analise["cobertura_research"] = {
        **_COBERTURA_COM_DADO,
        "divergencia": {"descricao": "Recomendação estruturada diverge entre casas pra WEGE3.",
                         "por_casa": {"Genial Analisa": "COMPRA", "Monte Bravo": "VENDA"}},
    }
    blocos = at_mod._montar_conclusao(analise, tese=None)
    contrarios = next(b for b in blocos if b["pergunta"] == "Principais argumentos contrários / lacunas de cobertura")
    assert "diverge entre casas" in contrarios["resposta"]


def test_conclusao_usa_riscos_da_tese_propria_quando_existe():
    tese = {"ticker": "WEGE3", "riscos": ["Câmbio desfavorável pode comprimir margem de exportação"],
            "registrado_em": "2026-10-01", "n_versoes": 2}
    blocos = at_mod._montar_conclusao(_ANALISE_COMPLETA, tese=tese)
    invalida = next(b for b in blocos if b["pergunta"] == "O que invalidaria a tese")
    assert "Câmbio desfavorável" in invalida["resposta"]
    assert "Tese própria" in invalida["resposta"]


def test_conclusao_nunca_recomenda_compra_ou_venda():
    for analise, tese in ((_ANALISE_COMPLETA, None), (_ANALISE_VAZIA, None)):
        blocos = at_mod._montar_conclusao(analise, tese)
        texto = " ".join(b["resposta"].lower() for b in blocos)
        for palavra_proibida in ("recomendo comprar", "recomendo vender", "deve comprar", "deve vender"):
            assert palavra_proibida not in texto


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
         patch.object(at_mod.st, "container") as container_mock:
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        at_mod.render_conclusao_investimento("WEGE3", {"formato_numerico": "BR"}, {"sub": "sub-teste"})
    return "\n".join(blocos)


def test_render_fonte_indisponivel_avisa_e_nunca_lanca_excecao():
    html_render = _capturar_render(levanta=lambda t: (_ for _ in ()).throw(RuntimeError("Supabase fora do ar")))
    assert "indisponível agora" in html_render


def test_render_mostra_todas_as_perguntas_e_tese_propria():
    tese = {"ticker": "WEGE3", "riscos": [], "registrado_em": "2026-10-01T10:00:00", "n_versoes": 1}
    html_render = _capturar_render(_ANALISE_COMPLETA, tese=tese)
    assert "CONCLUSÃO DE INVESTIMENTO" in html_render
    for pergunta in ("Qualidade do negócio", "Momento atual", "O que sustenta uma leitura positiva",
                      "Principais argumentos contrários", "Avaliação (caro ou barato)",
                      "O que monitorar a seguir", "O que invalidaria a tese", "Confiança e lacunas"):
        assert pergunta in html_render
    assert "Você já registrou uma Tese própria para WEGE3" in html_render


def test_render_sem_tese_propria_sugere_registrar():
    html_render = _capturar_render(_ANALISE_VAZIA, tese=None)
    assert "Você ainda não registrou uma Tese própria" in html_render
