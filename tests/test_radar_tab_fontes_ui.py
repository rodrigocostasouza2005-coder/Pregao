# -*- coding: utf-8 -*-
"""Revisão do PR de auditoria do Radar de Carteiras Recomendadas: a aba
RADAR agora mostra, dentro do expander "RADAR DE QUEDAS", o estado por
casa (Genial Analisa/Safra Corretora) usando
data.radar_quedas.resumo_fontes_vigentes() - este arquivo confirma que
a UI:

1. distingue corretamente os 3 estados (atualizada/desatualizada/
   indisponível), e não só um binário "tem dado ou não tem";
2. nunca chama os coletores de rede (coletar_carteiras_genial/
   coletar_carteiras_safra) só para desenhar essa linha de status -
   resumo_fontes_vigentes() só lê o que já está persistido
   (listar_carteiras(), sem rede nova).

Bare mode (sem ScriptRunContext real) - mesmo padrão de
tests/test_mercado_ranking_ui.py/test_calendario_ui.py deste projeto:
st.columns/st.pills/st.caption/st.markdown funcionam fora de uma sessão
Streamlit real, só avisam no log.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.radar_quedas as radar_quedas_mod
import ui.radar_tab as radar_tab_mod

_PREFS_SEM_WATCHLIST = {"formato_numerico": "BR", "watchlist": []}


def _capturar_render(resumo_fontes, alertas=None):
    """Chama render_radar de verdade com resumo_fontes_vigentes/
    alertas_recentes mockados (dado já persistido, sem rede) e os
    coletores reais substituídos por algo que FALHA o teste se for
    chamado - prova que exibir o status não dispara coleta nova.
    Retorna a lista de textos passados a st.caption."""
    captions = []

    def _coletor_nao_deveria_ser_chamado(*_a, **_k):
        raise AssertionError("coletor de rede chamado só para exibir o status de fontes")

    with patch.object(radar_quedas_mod, "resumo_fontes_vigentes", return_value=resumo_fontes), \
         patch.object(radar_quedas_mod, "alertas_recentes", return_value=alertas if alertas is not None else []), \
         patch.object(radar_quedas_mod, "coletar_carteiras_genial", side_effect=_coletor_nao_deveria_ser_chamado), \
         patch.object(radar_quedas_mod, "coletar_carteiras_safra", side_effect=_coletor_nao_deveria_ser_chamado), \
         patch.object(radar_tab_mod.st, "caption", side_effect=lambda texto, **_k: captions.append(texto)):
        # render_radar e' decorado com @st.fragment, que em bare mode (sem
        # ScriptRunContext real) NUNCA executa o corpo da funcao - chamar
        # render_radar(...) direto aqui silenciosamente nao faria nada e o
        # teste passaria "por acidente" sem checar coisa alguma.
        # .__wrapped__ e' a funcao original (sem o decorador), que executa
        # de verdade - confirmado em teste manual antes de escrever isto.
        radar_tab_mod.render_radar.__wrapped__(_PREFS_SEM_WATCHLIST)

    return captions


def test_fonte_atualizada_e_fonte_indisponivel_sao_distinguidas():
    resumo = {
        "Safra Corretora": {"ativos": 10, "verificado_em": "2026-10-17T10:00:00+00:00", "desatualizada": False},
        # Genial Analisa ausente do resumo -> UI trata como indisponível
    }
    captions = _capturar_render(resumo)
    assert captions, "a linha de status de fontes não foi renderizada"
    texto = captions[0]
    assert "🟢 Safra Corretora: atualizada (10 ativos)" in texto
    assert "🔴 Genial Analisa: indisponível" in texto
    assert "🟡" not in texto  # nenhuma das duas está no estado "desatualizada" aqui


def test_fonte_desatualizada_e_distinguida_de_atualizada_e_de_indisponivel():
    resumo = {
        "Safra Corretora": {"ativos": 10, "verificado_em": "2026-09-01T10:00:00+00:00", "desatualizada": True},
        "Genial Analisa": {"ativos": 42, "verificado_em": "2026-10-17T10:00:00+00:00", "desatualizada": False},
    }
    captions = _capturar_render(resumo)
    texto = captions[0]
    assert "🟡 Safra Corretora: desatualizada" in texto
    assert "🟢 Genial Analisa: atualizada (42 ativos)" in texto
    assert "🔴" not in texto  # nenhuma das duas está "indisponível" aqui


def test_supabase_indisponivel_nao_renderiza_linha_de_status_mas_nao_quebra():
    """resumo_fontes_vigentes() devolve None (mesmo contrato de
    listar_carteiras) quando o Supabase está fora do ar pra leitura - a
    UI deve simplesmente omitir a linha, nunca lançar exceção."""
    captions = _capturar_render(resumo_fontes=None)
    assert captions == []
