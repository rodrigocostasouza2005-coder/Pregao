# -*- coding: utf-8 -*-
"""ANÁLISES > Empresas deixa de mostrar só cotação/indicadores: ganha
SÍNTESE EXECUTIVA (topo) e RESEARCH DAS CASAS/RISCOS/CONCLUSÃO (fim do
bloco), compondo o que data/market_researcher.py:analise_ticker() já
agrega (linha_valuation + contexto_ticker + cobertura_cruzada_casas,
PR #152) - zero coletor novo, zero consulta nova. Este arquivo cobre:

1. `_montar_conclusao` isolada (função pura, sem Streamlit) - garante
   que cada resposta cita evidência real ou declara "dado insuficiente"
   explícito, e que nunca aparece uma recomendação de compra/venda.
2. `render_sintese_executiva`/`render_pesquisa_e_conclusao` via AppTest
   real (ScriptRunContext de verdade - mesmo padrão de
   tests/test_pregao2_modulos.py:test_appteste_fundamentos_...), com
   analise_ticker() mockado - confirma zero exceção e que os dados
   compostos aparecem na tela."""
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.analises_tab as at_mod

_PREFS = {"formato_numerico": "BR", "watchlist": ["WEGE3"]}

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
    "interpretacao_movimento": {"texto": "Mudança de recomendação: Genial elevou WEGE3 para COMPRA (2 dias atrás).",
                                 "tipo_evidencia": "FATO", "fonte_label": "Genial Analisa", "fonte_url": "https://x"},
    "cobertura_research": _COBERTURA_COM_DADO, "fontes_indisponiveis": [],
}

_ANALISE_VAZIA = {
    "ticker": "XPTO3", "fundamentos": None, "catalisadores": None, "mudancas_tese": None,
    "riscos_indicadores": None, "interpretacao_movimento": None,
    "cobertura_research": None, "fontes_indisponiveis": ["fundamentos", "contexto_mercado", "cobertura_research"],
}


# --- _montar_conclusao (pura, sem Streamlit) --------------------------------

def test_conclusao_sem_evidencia_declara_dado_insuficiente_em_tudo():
    blocos = at_mod._montar_conclusao(_ANALISE_VAZIA, tese=None)
    assert len(blocos) == 8  # 7 perguntas do pedido + confiança/lacunas
    for b in blocos:
        assert b["resposta"]  # nunca string vazia
    # qualidade do negocio e sempre insuficiente hoje (sem serie historica integrada)
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


# --- AppTest real (ScriptRunContext de verdade) -----------------------------

def test_appteste_sintese_executiva_sem_excecao_com_dado_real():
    from streamlit.testing.v1 import AppTest

    script = '''
from unittest.mock import patch
from datetime import date, timedelta
import ui.analises_tab as at_mod

hoje = date.today()
analise = {
    "ticker": "WEGE3", "fundamentos": None,
    "catalisadores": [{"ticker": "WEGE3", "categoria": "Resultado do 3T26", "data": hoje + timedelta(days=10),
                        "status_label": "CONFIRMADO", "confirmado": True, "fonte_label": "RI WEG", "fonte_url": "https://ri.weg.net"}],
    "mudancas_tese": [{"ticker": "WEGE3", "categoria": "Mudança de recomendação",
                        "descricao": "Genial elevou WEGE3 para COMPRA", "relevancia": "alta",
                        "data_evento": hoje - timedelta(days=2), "tipo_evidencia": "FATO",
                        "fonte_label": "Genial Analisa", "fonte_url": "https://genialanalisa.com.br/x"}],
    "riscos_indicadores": [], "interpretacao_movimento": None,
    "cobertura_research": None, "fontes_indisponiveis": [],
}
with patch.object(at_mod.market_researcher, "analise_ticker", return_value=analise):
    at_mod.render_sintese_executiva("WEGE3", {"formato_numerico": "BR", "watchlist": ["WEGE3"]})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "SÍNTESE EXECUTIVA" in textos
    assert "Genial elevou WEGE3 para COMPRA" in textos
    assert "Resultado do 3T26" in textos


def test_appteste_pesquisa_e_conclusao_sem_excecao_com_cobertura_e_sem_cobertura():
    from streamlit.testing.v1 import AppTest

    script = '''
from unittest.mock import patch
from datetime import date, timedelta
import ui.analises_tab as at_mod

hoje = date.today()
analise = {
    "ticker": "WEGE3",
    "fundamentos": {"ticker": "WEGE3", "preco": 40.0, "pl": 28.5, "pvp": 9.1, "dividend_yield": 1.2,
                     "roe": 32.0, "margem_liquida": 14.0, "divida_liquida_ebitda": 0.3,
                     "valor_mercado": 150000000000, "alerta_qualidade": []},
    "catalisadores": [{"ticker": "WEGE3", "categoria": "Resultado do 3T26", "data": hoje + timedelta(days=10),
                        "status_label": "CONFIRMADO", "confirmado": True, "fonte_label": "RI WEG", "fonte_url": "https://ri.weg.net"}],
    "mudancas_tese": [], "riscos_indicadores": [],
    "interpretacao_movimento": None,
    "cobertura_research": {"ticker": "WEGE3", "janela_dias": 30,
                            "cobertura": [{"casa": "Genial Analisa", "data": "2026-10-20",
                                           "titulo": "WEGE3: elevamos para COMPRA",
                                           "link": "https://genialanalisa.com.br/x",
                                           "recomendacao": "COMPRA", "preco_alvo": 45.0}],
                            "sem_cobertura": ["BTG Pactual Research"], "divergencia": None},
    "fontes_indisponiveis": [],
}
with patch.object(at_mod.market_researcher, "analise_ticker", return_value=analise), \\
     patch.object(at_mod, "historico_ticker", return_value=[]), \\
     patch.object(at_mod, "obter_cotacao", return_value={"preco": 40.0, "erro": None}), \\
     patch.object(at_mod, "scorecard", return_value=None):
    at_mod.render_pesquisa_e_conclusao("WEGE3", {"formato_numerico": "BR", "watchlist": ["WEGE3"]},
                                        {"sub": "sub-teste", "email": "teste@exemplo.com"})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "RESEARCH DAS CASAS" in textos
    assert "Genial Analisa" in textos and "COMPRA" in textos
    assert "Sem cobertura recente: BTG Pactual Research" in " ".join(c.value for c in at.caption)
    assert "CONCLUSÃO" in textos
    assert "Qualidade do negócio" in textos
    assert "Você ainda não registrou uma Tese própria" in " ".join(c.value for c in at.caption)
