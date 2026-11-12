# -*- coding: utf-8 -*-
"""Seção "ÚLTIMAS EXECUÇÕES AGENDADAS" no topo da VISÃO GERAL do
COORDENADOR CENTRAL (ui/coordenador_tab.py) - equivalente em Streamlit
do painel "Status dos especialistas" já existente na versão web
(web/app/(terminal)/inteligencia/page.tsx). AppTest real (nunca
AppTest.from_string tocando rede: tudo mockado - data.coordenador_central.
execucoes_agendadas.listar_ultimas_execucoes e persistencia.* nunca
chamam Supabase real aqui, então nada é escrito em nenhum log de
produção por este teste)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_mostra_status_idade_duracao_e_resumo_por_tipo():
    from streamlit.testing.v1 import AppTest

    iniciado_backoffice = (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
    iniciado_sintese = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()

    script = '''
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import ui.coordenador_tab as coord
from data.coordenador_central import execucoes_agendadas, persistencia

iniciado_backoffice = (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
iniciado_sintese = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()

execucoes = [
    {"id": 1, "tipo": "backoffice", "status": "OK", "iniciado_em": iniciado_backoffice,
     "duracao_ms": 850, "resumo": "7 achado(s) atual(is), 2 novo(s)", "erro": None},
    {"id": 2, "tipo": "sintese", "status": "ERRO", "iniciado_em": iniciado_sintese,
     "duracao_ms": 15230, "resumo": None, "erro": "Groq indisponivel (timeout)"},
    # radar_x/embeddings/comite_noturno de proposito ausentes (sem linha) -> "NUNCA RODOU".
]

with patch.object(execucoes_agendadas, "listar_ultimas_execucoes", return_value=execucoes), \\
     patch.object(persistencia, "listar_analises_recentes", return_value=[]), \\
     patch.object(persistencia, "metricas_especialistas", return_value={}):
    coord.render_visao_geral({})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception

    textos = " ".join(m.value for m in at.markdown)
    # Redesign estrutural (2026-11-12, Agente D): a seção deixou de ser um
    # st.expander (fechável, título no widget) e virou um painel sempre
    # visível lado a lado com "Análises sob demanda recentes" (grade de
    # 2 colunas, ver render_visao_geral) - título agora é um <div
    # class="painel-titulo"> normal, aparece em at.markdown como o resto.
    assert "ÚLTIMAS EXECUÇÕES AGENDADAS" in textos
    # Backoffice: OK, ~12min, 850ms, resumo.
    assert "Backoffice (achados)" in textos
    assert "há 12min" in textos
    assert "850ms" in textos
    assert "7 achado(s) atual(is), 2 novo(s)" in textos
    # Síntese: ERRO, ~3h, 15.2s, mensagem de erro (não o resumo, que é None).
    assert "Síntese (IA)" in textos
    assert "há 3h" in textos
    assert "15.2s" in textos
    assert "Groq indisponivel (timeout)" in textos
    # Tipos sem nenhuma linha aparecem como "nunca rodou".
    assert "NUNCA RODOU" in textos
    assert "Radar X (sinais sociais)" in textos
    assert "Memória de Research (embeddings)" in textos
    assert "Comitê de Investimentos (análise noturna)" in textos


def test_supabase_indisponivel_mostra_aviso_sem_quebrar_o_resto_da_aba():
    from streamlit.testing.v1 import AppTest

    script = '''
from unittest.mock import patch
import ui.coordenador_tab as coord
from data.coordenador_central import execucoes_agendadas, persistencia

with patch.object(execucoes_agendadas, "listar_ultimas_execucoes", return_value=None), \\
     patch.object(persistencia, "listar_analises_recentes", return_value=[]), \\
     patch.object(persistencia, "metricas_especialistas", return_value={}):
    coord.render_visao_geral({})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    avisos = " ".join(w.value for w in at.warning)
    assert "execuções agendadas indisponível" in avisos
    # O resto da VISÃO GERAL (métricas de especialistas) ainda renderiza.
    textos = " ".join(m.value for m in at.markdown)
    assert "COORDENADOR CENTRAL" in textos
