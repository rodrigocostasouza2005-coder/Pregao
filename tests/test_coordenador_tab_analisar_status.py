# -*- coding: utf-8 -*-
"""Bug 2 + Bug 3 (2 auditorias independentes, 2026-11-05) em
ui/coordenador_tab.py:

Bug 2 - render_analisar sempre mostrava st.success incondicionalmente,
mesmo quando a análise ficou PARCIAL (especialista indisponível OU
falha ao persistir o resultado completo, ver
data/coordenador_central/persistencia.py:concluir_analise). Usuário via
"sucesso" verde quando a análise não tinha terminado bem.

Bug 3 - coordenador_especialistas_execucoes.erro (erro técnico por
execução) era gravado mas descartado por metricas_especialistas() -
nenhuma tela mostrava o erro técnico de uma execução específica.
render_especialistas agora expõe o erro técnico da ÚLTIMA execução de
cada especialista (persistencia.metricas_especialistas()["X"]
["ultimo_erro_tecnico"]).

AppTest real (nunca AppTest.from_string tocando rede: fluxos/persistência
100% mockados - nada é escrito em nenhum log de produção por este
teste)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _rodar_analisar(consolidado_fake: dict):
    from streamlit.testing.v1 import AppTest

    script = f'''
import ui.coordenador_tab as coord

def _fluxo_fake(ticker, premissas_dcf=None):
    return {consolidado_fake!r}

coord._FLUXOS["analise_ticker"] = ("Análise de ticker", _fluxo_fake)
coord.render_analisar({{}})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    at.text_input(key="coord_analisar_ticker").set_value("PETR4").run()
    at.button(key="coord_analisar_botao").click().run()
    return at


def _consolidado_base(status_execucao: str) -> dict:
    return {
        "resumo_executivo": "Análise consolidada para PETR4.",
        "visao_especialistas": {}, "evidencias": [],
        "divergencias": {"cross_comparador_memoria": None},
        "pontos_atencao": [], "conclusao": [], "confianca": {"categoria": "MEDIA", "justificativa": "x"},
        "pareceres_analistas": {}, "sinal_comite": {},
        "status_execucao": status_execucao,
        "_duracao_ms": 1234, "_analise_id": "abc123",
    }


# ============================================================
# Bug 2 - render_analisar precisa refletir status_execucao de verdade
# ============================================================

def test_render_analisar_mostra_sucesso_quando_status_e_concluida():
    at = _rodar_analisar(_consolidado_base("CONCLUIDA"))
    assert not at.exception
    sucessos = " ".join(s.value for s in at.success)
    assert "Análise concluída em 1.2s." in sucessos
    assert not list(at.warning)
    assert not list(at.error)


def test_render_analisar_mostra_warning_quando_status_e_parcial():
    """Antes do fix: st.success aparecia aqui do mesmo jeito - o usuário
    via "sucesso" verde numa análise que não terminou bem (especialista
    indisponível ou falha ao persistir o resultado completo)."""
    at = _rodar_analisar(_consolidado_base("PARCIAL"))
    assert not at.exception
    assert not list(at.success)
    avisos = " ".join(w.value for w in at.warning)
    assert "PARCIAL" in avisos
    assert not list(at.error)


def test_render_analisar_mostra_erro_quando_status_e_inesperado():
    """status_execucao ausente/desconhecido nunca deve parecer sucesso."""
    at = _rodar_analisar(_consolidado_base(None))
    assert not at.exception
    assert not list(at.success)
    assert not list(at.warning)
    erros = " ".join(e.value for e in at.error)
    assert "status inesperado" in erros


# ============================================================
# Bug 3 - erro técnico por especialista exposto em render_especialistas
# ============================================================

def test_render_especialistas_mostra_ultimo_erro_tecnico():
    from streamlit.testing.v1 import AppTest
    from data.coordenador_central.registro import Especialista

    especialistas_fake = [
        Especialista(
            id="comparador", nome="Comparador de Casas", descricao="desc",
            capacidades=(), pre_requisitos=(), entradas_aceitas={},
            funcao=lambda **_k: {}, extrator_saida=lambda x: x,
        ),
    ]
    metricas_fake = {
        "comparador": {
            "total_execucoes": 5, "sucessos": 4, "taxa_sucesso_pct": 80.0,
            "taxa_sucesso_recente_pct": 80.0, "n_execucoes_recentes_consideradas": 5,
            "tempo_medio_ms": 120.0, "ultima_execucao_em": "2026-11-05T00:00:00Z",
            "ultimo_erro_tecnico": "TimeoutError: especialista não respondeu em 30s",
        },
    }

    script = f'''
from unittest.mock import patch
import ui.coordenador_tab as coord
from data.coordenador_central import persistencia
from data.coordenador_central.registro import Especialista

especialistas_fake = [
    Especialista(
        id="comparador", nome="Comparador de Casas", descricao="desc",
        capacidades=(), pre_requisitos=(), entradas_aceitas={{}},
        funcao=lambda **_k: {{}}, extrator_saida=lambda x: x,
    ),
]
metricas_fake = {metricas_fake!r}

with patch.object(coord, "listar_especialistas", return_value=especialistas_fake), \\
     patch.object(persistencia, "metricas_especialistas", return_value=metricas_fake):
    coord.render_especialistas({{}})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "TimeoutError" in textos


def test_render_especialistas_mostra_travessao_quando_sem_erro():
    from streamlit.testing.v1 import AppTest

    metricas_fake = {
        "comparador": {
            "total_execucoes": 3, "sucessos": 3, "taxa_sucesso_pct": 100.0,
            "taxa_sucesso_recente_pct": 100.0, "n_execucoes_recentes_consideradas": 3,
            "tempo_medio_ms": 90.0, "ultima_execucao_em": "2026-11-05T00:00:00Z",
            "ultimo_erro_tecnico": None,
        },
    }
    script = f'''
from unittest.mock import patch
import ui.coordenador_tab as coord
from data.coordenador_central import persistencia
from data.coordenador_central.registro import Especialista

especialistas_fake = [
    Especialista(
        id="comparador", nome="Comparador de Casas", descricao="desc",
        capacidades=(), pre_requisitos=(), entradas_aceitas={{}},
        funcao=lambda **_k: {{}}, extrator_saida=lambda x: x,
    ),
]
metricas_fake = {metricas_fake!r}

with patch.object(coord, "listar_especialistas", return_value=especialistas_fake), \\
     patch.object(persistencia, "metricas_especialistas", return_value=metricas_fake):
    coord.render_especialistas({{}})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    assert "Último erro técnico" in " ".join(m.value for m in at.markdown)
