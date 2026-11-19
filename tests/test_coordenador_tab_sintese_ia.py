# -*- coding: utf-8 -*-
"""Fiação real da síntese de IA do Comitê na UI - missão "PREGÃO 2.3-B",
2026-11-13. A auditoria anterior (docs/auditoria-comite-20261113.md)
confirmou que a camada híbrida (sintese_ia=True em
data/coordenador_central/fluxos.py:analisar_ticker) funciona de verdade,
mas nenhum caminho de produção a exibia - nem o Comitê Noturno passava o
parâmetro, nem ui/coordenador_tab.py tinha onde mostrar o resultado se
alguém passasse manualmente.

Estes testes cobrem 2 coisas, SEM nenhuma chamada real de rede/IA (tudo
mockado):
1. render_historico/_render_consolidado agora mostra a seção "Leitura de
   IA" quando o consolidado trazia as 2 chaves aditivas
   (sintese_divergencia_comite_ia/sintese_qualitativa_research_ia), e
   continua sem mostrar nada quando elas não existem (compatibilidade
   com toda análise já persistida antes desta missão).
2. render_analisar só oferece o checkbox de pedir a síntese de IA quando
   config.sintese_ia_comite_ativa() está ligada - com a config desligada
   (o padrão real em produção, ver config.py), o checkbox nem aparece.

AppTest real (nunca AppTest.from_string tocando rede: fluxos/persistência/
config 100% mockados - nada é escrito em nenhum log de produção por este
teste)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _consolidado_base() -> dict:
    return {
        "resumo_executivo": "Análise consolidada para PETR4.",
        "visao_especialistas": {}, "evidencias": [],
        "divergencias": {"cross_comparador_memoria": None},
        "pontos_atencao": [], "conclusao": [], "confianca": {"categoria": "MEDIA", "justificativa": "x"},
        "pareceres_analistas": {}, "sinal_comite": {},
        "status_execucao": "CONCLUIDA",
        "_duracao_ms": 1234, "_analise_id": "abc123",
    }


def _rodar_render_historico(consolidado: dict):
    from streamlit.testing.v1 import AppTest

    analise_fake = {
        "id": "fedcba987654", "solicitacao": "Analisar PETR4",
        "tipo_fluxo": "analise_ticker", "ticker": "PETR4",
        "iniciado_em": "2026-11-05T10:00:00Z", "status": "CONCLUIDA",
        "duracao_ms": 3456, "resultado": consolidado,
    }
    script = f'''
from unittest.mock import patch
import ui.coordenador_tab as coord
from data.coordenador_central import persistencia

analises_fake = [{analise_fake!r}]
analise_fake = {analise_fake!r}

with patch.object(persistencia, "listar_analises_recentes", return_value=analises_fake), \\
     patch.object(persistencia, "obter_analise", return_value=analise_fake):
    coord.render_historico({{}})
'''
    return AppTest.from_string(script, default_timeout=30).run()


# ============================================================
# 1. _render_sintese_ia (via render_historico/_render_consolidado)
# ============================================================

def test_sem_as_chaves_de_ia_nenhuma_secao_de_ia_aparece():
    """Compatibilidade: toda análise persistida ANTES desta missão não
    tem essas 2 chaves - a UI não deve mostrar nada nem quebrar."""
    at = _rodar_render_historico(_consolidado_base())
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "Leitura de IA" not in textos


def test_sintese_divergencia_comite_ia_disponivel_mostra_leitura_modelo_e_fator_decisivo():
    consolidado = _consolidado_base()
    consolidado["sintese_divergencia_comite_ia"] = {
        "disponivel": True, "modelo": "openai/gpt-oss-20b",
        "leitura": "Os especialistas convergem em COMPRA sustentados por ROE de 32,2% e margem de 24,0%.",
        "fator_decisivo": "P/L abaixo da mediana setorial",
        "especialistas_citados": ["market_researcher", "earnings_reviewer"],
    }
    at = _rodar_render_historico(consolidado)
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "Leitura de IA" in textos
    assert "openai/gpt-oss-20b" in textos
    assert "ROE de 32,2%" in textos
    legendas = " ".join(c.value for c in at.caption)
    assert "P/L abaixo da mediana setorial" in legendas
    assert "market_researcher" in legendas and "earnings_reviewer" in legendas


def test_sintese_divergencia_comite_ia_indisponivel_mostra_motivo_sem_esconder():
    consolidado = _consolidado_base()
    consolidado["sintese_divergencia_comite_ia"] = {
        "disponivel": False, "motivo": "GROQ_API_KEY não configurada",
    }
    at = _rodar_render_historico(consolidado)
    assert not at.exception
    legendas = " ".join(c.value for c in at.caption)
    assert "GROQ_API_KEY não configurada" in legendas


def test_sintese_qualitativa_research_ia_disponivel_mostra_sintese_e_casas():
    consolidado = _consolidado_base()
    consolidado["sintese_qualitativa_research_ia"] = {
        "disponivel": True, "modelo": "openai/gpt-oss-20b",
        "sintese": "As casas monitoradas convergem em recomendação de compra para o ticker.",
        "convergencias": ["Ambas destacam crescimento de receita"],
        "divergencias": [], "pontos_atencao": ["Alavancagem em alta"],
        "casas_citadas": ["Genial Analisa", "XP Investimentos"],
    }
    at = _rodar_render_historico(consolidado)
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "recomendação de compra" in textos
    legendas = " ".join(c.value for c in at.caption)
    assert "Genial Analisa" in legendas and "XP Investimentos" in legendas


def test_sintese_qualitativa_research_ia_indisponivel_mostra_motivo():
    consolidado = _consolidado_base()
    consolidado["sintese_qualitativa_research_ia"] = {
        "disponivel": False, "motivo": "nenhuma casa monitorada cobre este ticker",
    }
    at = _rodar_render_historico(consolidado)
    assert not at.exception
    legendas = " ".join(c.value for c in at.caption)
    assert "nenhuma casa monitorada cobre este ticker" in legendas


# ============================================================
# 2. Checkbox em render_analisar - gated por config.sintese_ia_comite_ativa()
# ============================================================

def _rodar_analisar_para_checkbox(*, config_ativa: bool):
    from streamlit.testing.v1 import AppTest

    script = f'''
from unittest.mock import patch
import ui.coordenador_tab as coord

def _fluxo_fake(ticker, premissas_dcf=None, sintese_ia=False):
    return {{
        "resumo_executivo": "x", "visao_especialistas": {{}}, "evidencias": [],
        "divergencias": {{"cross_comparador_memoria": None}}, "pontos_atencao": [],
        "conclusao": [], "confianca": {{"categoria": "MEDIA", "justificativa": "x"}},
        "pareceres_analistas": {{}}, "sinal_comite": {{}}, "status_execucao": "CONCLUIDA",
        "_duracao_ms": 1234, "_analise_id": "abc123",
        "sintese_ia_recebida": sintese_ia,
    }}

coord._FLUXOS["analise_ticker"] = ("Análise de ticker", _fluxo_fake)
with patch.object(coord.config, "sintese_ia_comite_ativa", return_value={config_ativa!r}):
    coord.render_analisar({{}})
'''
    return AppTest.from_string(script, default_timeout=30).run()


def test_checkbox_de_sintese_ia_nao_aparece_quando_config_esta_desligada():
    """Default real em produção (config.sintese_ia_comite_ativa() == False,
    ver config.py) - o analista não deve nem ver a opção."""
    at = _rodar_analisar_para_checkbox(config_ativa=False)
    assert not at.exception
    assert not any(cb.key == "coord_sintese_ia_ativar" for cb in at.checkbox)
    legendas = " ".join(c.value for c in at.caption)
    assert "desligada por configuração" in legendas


def test_checkbox_de_sintese_ia_aparece_quando_config_esta_ligada():
    at = _rodar_analisar_para_checkbox(config_ativa=True)
    assert not at.exception
    assert len(list(at.checkbox(key="coord_sintese_ia_ativar"))) == 1


def test_marcar_checkbox_propaga_sintese_ia_true_pro_fluxo():
    at = _rodar_analisar_para_checkbox(config_ativa=True)
    at.text_input(key="coord_analisar_ticker").set_value("PETR4").run()
    at.checkbox(key="coord_sintese_ia_ativar").set_value(True).run()
    at.button(key="coord_analisar_botao").click().run()
    assert not at.exception
    assert not list(at.error)


def test_sugestao_clicada_nunca_pede_sintese_ia_mesmo_com_checkbox_marcado():
    """As sugestões ("Analisar PETR4" etc.) disparam direto, sem passar
    pelo fluxo do checkbox - precisam continuar 100% determinísticas
    mesmo que o checkbox tenha ficado marcado de uma interação anterior."""
    at = _rodar_analisar_para_checkbox(config_ativa=True)
    at.checkbox(key="coord_sintese_ia_ativar").set_value(True).run()
    at.button(key="coord_sugestao_analise_ticker").click().run()
    assert not at.exception
    assert not list(at.error)
