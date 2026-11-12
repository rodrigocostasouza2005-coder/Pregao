# -*- coding: utf-8 -*-
"""Smoke test de regressão: 1 subaba representativa de cada ÁREA principal
da navegação (ui/navegacao.py:AREAS), via streamlit.testing.v1.AppTest real.

Baseline ANTES de 4 PRs paralelas que vão alterar arquitetura de
coletores/UI/processamento (missão "Agente E — QA/auditoria",
2026-11-12) - objetivo único: nenhuma das telas abaixo lança exceção ao
renderizar. Não é teste funcional profundo (isso já existe, espalhado em
tests/test_*_tab_*.py e tests/test_coordenador_tab_*.py - ver também
tests/test_pregao2_modulos.py) - é cobertura de "a tela ainda monta".

app.py inteiro exige login Google real (auth.py: st.login/st.user, sem
bypass de teste) - mesma restrição e mesmo padrão já documentado em
tests/test_navegacao.py e tests/test_pregao2_modulos.py: cada AppTest
roda um script mínimo que importa e chama DIRETO a função render_ da
tela (nunca app.py), com as dependências de rede/Supabase mockadas no
mesmo ponto em que os testes já existentes mockam (atributo do módulo
que a tela realmente chama - nunca ui/*.py é editado, só mockado em
tempo de teste)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit.testing.v1 import AppTest


def _roda(script: str):
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception, f"AppTest lançou exceção: {at.exception}"
    return at


# --- MERCADO › Mercados Globais (secoes.py) ---------------------------------

def test_smoke_mercado_globais():
    script = '''
import config
from unittest.mock import patch
import ui.secoes as secoes

prefs = dict(config.PREFS_PADRAO)
with patch.object(secoes, "_painel_globais", lambda p: None), \\
     patch.object(secoes, "_painel_cenario_global", lambda p: None):
    secoes.render_mercados_globais(prefs)
'''
    _roda(script)


# --- NOTÍCIAS › Destaques (news_tab.py, watchlist vazia = sem rede) --------

def test_smoke_noticias_destaques():
    script = '''
import config
import ui.news_tab as news_tab

prefs = dict(config.PREFS_PADRAO)
prefs["watchlist"] = []
news_tab.render_news(prefs)
'''
    at = _roda(script)
    textos = " ".join(m.value for m in at.markdown)
    assert "NOTÍCIAS" in textos


# --- RADAR › Alertas (radar_tab.py, mesmos mocks de test_pregao2_modulos.py)-

def test_smoke_radar_alertas():
    script = '''
import config
from unittest.mock import patch
import ui.radar_tab as radar_tab
from data import radar_quedas as rq

prefs = dict(config.PREFS_PADRAO)
with patch.object(rq, "resumo_fontes_vigentes", return_value={}), \\
     patch.object(rq, "painel_monitorados", return_value=[]), \\
     patch.object(rq, "alertas_periodo", return_value=[]):
    radar_tab.render_radar_alertas(prefs)
'''
    _roda(script)


# --- RESEARCH › Memória de Research (research_tab.py) ----------------------

def test_smoke_research_memoria():
    script = '''
import config
from unittest.mock import patch
import ui.research_tab as research_tab

prefs = dict(config.PREFS_PADRAO)
resultado_vazio = {"confianca": "sem_evidencia", "resultados": [], "aviso": None}
with patch.object(research_tab, "_premissas_para_opcoes_cacheado", return_value=[]), \\
     patch.object(research_tab.embeddings, "buscar", return_value=resultado_vazio):
    research_tab.render_memoria_research(prefs)
'''
    at = _roda(script)
    textos = " ".join(m.value for m in at.markdown)
    assert "MEMÓRIA DE RESEARCH" in textos


# --- ANÁLISES › Fundamentos (analises_tab.py, mesmo mock de test_pregao2_modulos.py)

def test_smoke_analises_fundamentos():
    script = '''
import config
from unittest.mock import patch
import ui.analises_tab as at_mod

def _ind(t):
    return {k: None for k in ("valor_mercado", "pl", "pvp", "dividend_yield", "beta", "roe",
                              "margem_liquida", "margem_operacional", "margem_ebitda",
                              "divida_liquida", "divida_liquida_ebitda")}

prefs = dict(config.PREFS_PADRAO)
prefs["watchlist"] = ["PETR4", "VALE3"]
with patch.object(at_mod, "obter_indicadores", side_effect=_ind):
    at_mod.render_fundamentos(prefs)
'''
    _roda(script)


# --- COORDENADOR › Visão Geral (mesmos mocks de test_coordenador_tab_execucoes_agendadas.py)

def test_smoke_coordenador_visao_geral():
    script = '''
from unittest.mock import patch
import ui.coordenador_tab as coord
from data.coordenador_central import execucoes_agendadas, persistencia

with patch.object(execucoes_agendadas, "listar_ultimas_execucoes", return_value=[]), \\
     patch.object(persistencia, "listar_analises_recentes", return_value=[]), \\
     patch.object(persistencia, "metricas_especialistas", return_value={}):
    coord.render_visao_geral({})
'''
    at = _roda(script)
    textos = " ".join(m.value for m in at.markdown)
    assert "COORDENADOR CENTRAL" in textos


# --- MACRO › Juros (macro_tab.py) -------------------------------------------

def test_smoke_macro_juros():
    script = '''
import config
from unittest.mock import patch
import ui.macro_tab as mt

prefs = dict(config.PREFS_PADRAO)
with patch.object(mt, "_painel_selic_cdi", lambda p: None), \\
     patch.object(mt, "_painel_curva_pre", lambda p: None), \\
     patch.object(mt, "_painel_expectativas", lambda p: None), \\
     patch.object(mt, "setores_sensiveis_a_juros", return_value=[]):
    mt.render_macro_juros(prefs)
'''
    _roda(script)


# --- SETORES › Mapa Setorial (setores_tab.py) -------------------------------

def test_smoke_setores_mapa():
    script = '''
import config
from unittest.mock import patch
import ui.setores_tab as setores_tab

prefs = dict(config.PREFS_PADRAO)
with patch.object(setores_tab, "_painel_setorial", lambda p: None), \\
     patch.object(setores_tab, "_painel_treemap", lambda p: None):
    setores_tab.render_mapa_setorial(prefs)
'''
    _roda(script)


# --- MORNING CALL › Histórico (morning_call_tab.py, mesmo mock de test_pregao2_modulos.py)

def test_smoke_morning_call_historico():
    script = '''
import config
from unittest.mock import patch
import ui.morning_call_tab as mc

prefs = dict(config.PREFS_PADRAO)
with patch.object(mc, "listar_edicoes", return_value=[]):
    mc.render_historico(prefs)
'''
    _roda(script)


# --- MAIS › Watchlist (secoes.py, watchlist vazia = sem rede) ---------------

def test_smoke_mais_watchlist():
    script = '''
import config
import ui.secoes as secoes

prefs = dict(config.PREFS_PADRAO)
prefs["watchlist"] = []
secoes.render_watchlist(prefs)
'''
    at = _roda(script)
    textos = " ".join(m.value for m in at.markdown)
    assert "WATCHLIST" in textos
