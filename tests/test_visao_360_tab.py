# -*- coding: utf-8 -*-
"""ANÁLISES > Visão 360 (ui/visao_360_tab.py:render_visao_360) - missão
visao-360-empresa-20261124. Esta tela é pura COMPOSIÇÃO de 4 peças já
testadas isoladamente em outros arquivos (render_perfil_empresa_tab em
tests/test_coordenador_tab_perfil_empresa.py, controle_dcf_inline em
tests/test_analises_conclusao_investimento_ui.py, render_consolidado em
tests/test_coordenador_tab_consolidado_reorganizado.py e afins) - este
arquivo cobre a ORQUESTRAÇÃO (as 4 seções aparecem, cada uma degrada com
motivo explícito quando a fonte dela falha, nunca derruba as outras) via
streamlit.testing.v1.AppTest real, mesmo padrão de
tests/test_smoke_todas_abas.py: script mínimo que importa e chama DIRETO
render_visao_360 (nunca app.py, que exige login Google real), com as
dependências de rede/Supabase mockadas no atributo do módulo que a tela
realmente chama (ui.visao_360_tab para obter_cotacao/linha_valuation/
listar_analises_por_ticker/obter_analise - importados direto lá; ui.
coordenador_tab para obter_perfil_empresa - importado direto lá, nunca em
ui/visao_360_tab.py).

Achado de desenho que esta suíte prova (pedido explícito do Rodrigo):
listar_analises_por_ticker devolvendo [] ("nunca analisado") e None
("Supabase indisponível, não dá pra saber") são avisos DIFERENTES - a UI
nunca pode tratar os dois como a mesma coisa."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit.testing.v1 import AppTest

_RAIZ = str(Path(__file__).parent.parent)


def _roda(script: str):
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception, f"AppTest lançou exceção: {at.exception}"
    return at


def _textos(at) -> str:
    partes = [m.value for m in at.markdown] + [c.value for c in at.caption]
    for bloco in (at.info, at.warning, at.error, at.success):
        partes += [b.value for b in bloco]
    return " ".join(partes)


def _tem_rotulo(at, trecho: str) -> bool:
    """Um botão de navegação (ui/navegacao.py:link) vira st.button() de
    verdade OU, se o Streamlit recusar por engano um contexto de form que
    não existe de fato aqui, um link HTML puro (ver docstring de link) -
    os dois são formas válidas do CTA aparecer pro usuário; checa as duas,
    nunca assume qual delas o Streamlit escolheu neste processo."""
    if any(trecho in b.label for b in at.button):
        return True
    return trecho in _textos(at)


_COT_OK = {
    "ticker": "PETR4", "preco": 38.5, "fechamento_anterior": 37.9,
    "cotacao_em": "2026-11-24T18:00:00+00:00",
    "tipo_cotacao": "ATRASADA (Yahoo Finance; atraso pode variar)",
    "variacao": 0.6, "variacao_pct": 1.58, "maxima_dia": 38.9, "minima_dia": 37.8,
    "volume": 1_000_000, "maxima_52s": 42.0, "minima_52s": 30.0, "erro": None,
}

_LINHA_OK = {
    "ticker": "PETR4", "setor": "Energy", "moeda": "R$", "moeda_fonte": "yfinance",
    "preco": 38.5, "preco_erro": None, "consultado_em": "2026-11-24T18:00:00+00:00",
    "pl": 6.2, "pvp": 1.1, "dividend_yield": 12.4, "roe": 24.3, "margem_liquida": 18.0,
    "divida_liquida_ebitda": 1.2, "valor_mercado": 500_000_000_000.0, "ebitda": 150_000_000_000.0,
    "ev_ebitda": 4.5, "divida_liquida": 180_000_000_000.0, "fluxo_caixa_livre": 70_000_000_000.0,
    "desatualizado": False, "alerta_qualidade": [],
}

_PERFIL_OK = {
    "identificacao": {
        "setor": "Energy", "industria": "Oil & Gas", "pais": "Brazil",
        "resumo_negocio": "A Petrobras produz e refina petróleo e gás no Brasil.",
        "disponivel": True,
    },
    "noticias_recentes": [], "noticias_disponivel": False,
    "perguntas": {
        "o_que_a_empresa_faz": {
            "dado": "A Petrobras produz e refina petróleo e gás no Brasil.",
            "disponivel": True, "motivo_indisponivel": None,
        },
        "perspectivas": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "pressoes_de_margem": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "riscos": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "o_que_quebraria_a_tese": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "posicao_competitiva": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "vantagens_competitivas": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "concorrentes": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
    },
}

_CONSOLIDADO_OK = {
    "ticker": "PETR4",
    "sinal_comite": {"sinal": "COMPRA", "justificativa": "ROE e margem fortes, dívida controlada."},
    "confianca": {"categoria": "ALTA", "justificativa": "Convergência entre especialistas."},
    "resumo_executivo": "Comitê recomenda COMPRA para PETR4.",
    "pareceres_analistas": {"analistas": [], "casas_research": [], "preco_alvo_consenso": {}},
    "divergencias": {"cross_comparador_memoria": None},
    "pontos_atencao": [], "conclusao": [], "evidencias": [], "visao_especialistas": {},
}


def _script(*, cot=None, linha=None, perfil=None, analises="_SENTINEL_", analise=None) -> str:
    """Monta o script do AppTest - cada mock vira repr() literal injetado
    no corpo (mesmo mecanismo de tests/test_coordenador_tab_sensibilidade_dcf.py).
    `analises="_SENTINEL_"` (string, nunca um valor real de teste) é só
    pra distinguir "não testar este mock" de "testar com None" (None é
    justamente um dos 2 cenários de degradação do Comitê, não pode virar
    o default silenciosamente)."""
    cot = _COT_OK if cot is None else cot
    linha = _LINHA_OK if linha is None else linha
    perfil = _PERFIL_OK if perfil is None else perfil
    analises_repr = repr([{"id": "analise-abc123"}]) if analises == "_SENTINEL_" else repr(analises)
    analise = _CONSOLIDADO_OK if analise is None else analise
    analise_repr = repr({"id": "analise-abc123", "status": "CONCLUIDA", "resultado": analise})
    return f'''
import sys
sys.path.insert(0, r"{_RAIZ}")
from unittest.mock import patch
import ui.visao_360_tab as v360
import ui.coordenador_tab as coord

with patch.object(v360, "obter_cotacao", return_value={cot!r}), \\
     patch.object(v360, "linha_valuation", return_value={linha!r}), \\
     patch.object(v360, "listar_analises_por_ticker", return_value={analises_repr}), \\
     patch.object(v360, "obter_analise", return_value={analise_repr}), \\
     patch.object(coord, "obter_perfil_empresa", return_value={perfil!r}):
    v360.render_visao_360("PETR4", {{"formato_numerico": "BR"}})
'''


# ============================================================
# 1. Dado completo - as 4 seções aparecem, inclusive recomendação do Comitê.
# ============================================================

def test_dado_completo_mostra_as_4_secoes_e_recomendacao_do_comite():
    at = _roda(_script())
    textos = _textos(at)
    assert "PETR4" in textos
    assert "R$" in textos and "38,50" in textos  # preço presente, formatado BR (config.formatar_numero)
    assert "PERFIL DA EMPRESA" in textos
    assert "A Petrobras produz e refina petróleo e gás" in textos
    assert "VALUATION" in textos
    assert "O QUE O COMITÊ ACHA" in textos
    assert "COMPRA" in textos
    assert "Executar Comitê" not in textos  # análise já existe - CTA de executar não aparece
    assert _tem_rotulo(at, "Ver histórico completo")


# ============================================================
# 2. Sem análise do Comitê (lista vazia) - CTA de executar, nunca inventa recomendação.
# ============================================================

def test_sem_analise_do_comite_mostra_cta_e_nunca_inventa_recomendacao():
    at = _roda(_script(analises=[]))
    textos = _textos(at)
    assert "ainda não analisou" in textos
    assert "COMPRA" not in textos
    assert "VENDA" not in textos
    assert _tem_rotulo(at, "Executar Comitê")


# ============================================================
# 3. listar_analises_por_ticker devolve None (Supabase indisponível) -
#    mensagem DISTINTA do caso "nunca analisado".
# ============================================================

def test_comite_indisponivel_mostra_mensagem_distinta_de_nunca_analisado():
    at = _roda(_script(analises=None))
    textos = _textos(at)
    assert "Não foi possível verificar" in textos
    assert "Supabase indisponível" in textos
    assert "diferente de" in textos
    assert "ainda não analisou" not in textos
    assert "COMPRA" not in textos
    assert _tem_rotulo(at, "Executar Comitê")


# ============================================================
# 4. Perfil/research indisponível - motivo explícito, nunca seção vazia em silêncio.
# ============================================================

def test_perfil_indisponivel_mostra_motivo_e_nao_quebra_as_outras_secoes():
    at = _roda(_script_perfil_indisponivel())
    textos = _textos(at)
    assert "indisponível" in textos.lower()
    assert "timeout ao consultar yfinance" in textos
    # as outras 3 seções continuam presentes, mesmo com o perfil falhando
    assert "VALUATION" in textos
    assert "O QUE O COMITÊ ACHA" in textos
    assert "COMPRA" in textos


def _script_perfil_indisponivel() -> str:
    analise_repr = repr({"id": "analise-abc123", "status": "CONCLUIDA", "resultado": _CONSOLIDADO_OK})
    return f'''
import sys
sys.path.insert(0, r"{_RAIZ}")
from unittest.mock import patch
import ui.visao_360_tab as v360
import ui.coordenador_tab as coord

with patch.object(v360, "obter_cotacao", return_value={_COT_OK!r}), \\
     patch.object(v360, "linha_valuation", return_value={_LINHA_OK!r}), \\
     patch.object(v360, "listar_analises_por_ticker", return_value=[{{"id": "analise-abc123"}}]), \\
     patch.object(v360, "obter_analise", return_value={analise_repr}), \\
     patch.object(coord, "obter_perfil_empresa", side_effect=Exception("timeout ao consultar yfinance")):
    v360.render_visao_360("PETR4", {{"formato_numerico": "BR"}})
'''


# ============================================================
# 5. Cotação indisponível - preço mostra "—", resto da página renderiza normal.
# ============================================================

def test_cotacao_indisponivel_mostra_traco_e_resto_da_pagina_renderiza():
    cot_erro = {"ticker": "PETR4", "erro": "timeout ao consultar fast_info"}
    at = _roda(_script(cot=cot_erro))
    textos = _textos(at)
    assert "—" in textos
    assert "Preço atual indisponível agora" in textos
    assert "timeout ao consultar fast_info" in textos
    # resto da página não quebra nem fica em branco
    assert "PERFIL DA EMPRESA" in textos
    assert "VALUATION" in textos
    assert "O QUE O COMITÊ ACHA" in textos
    assert "COMPRA" in textos


# ============================================================
# Sem ticker - aviso explícito, nunca uma página em branco.
# ============================================================

def test_sem_ticker_mostra_aviso():
    script = f'''
import sys
sys.path.insert(0, r"{_RAIZ}")
import ui.visao_360_tab as v360

v360.render_visao_360("", {{"formato_numerico": "BR"}})
'''
    at = _roda(script)
    textos = _textos(at)
    assert "Selecione um ticker" in textos
