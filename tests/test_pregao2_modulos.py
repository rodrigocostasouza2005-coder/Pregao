# -*- coding: utf-8 -*-
"""Modulos novos/reorganizados do PREGAO 2.0: historico do Morning Call
(so' leitura, sem destinatario), tela do Morning Call (nunca envia),
vinculos empresa/noticia -> setor (so' listas curadas), subabas do RADAR
(sem coleta de rede) e AppTest das telas que nao dependem de rede."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.morning_call_historico as hist
import data.radar_quedas as radar_quedas_mod
import ui.morning_call_tab as mc_tab
import ui.radar_tab as radar_tab_mod
from ui.setores_tab import setores_do_ticker


# --- historico do Morning Call -----------------------------------------------

def test_agrupa_uma_edicao_por_dia_no_fuso_de_brasilia():
    linhas = [
        # 01h UTC de 15/10 = 22h de 14/10 em Brasilia
        {"executado_em": "2026-10-15T01:00:00+00:00", "status": "ENVIADO", "conteudo": "edicao 14"},
        {"executado_em": "2026-10-15T11:05:00+00:00", "status": "ENVIADO", "conteudo": "edicao 15"},
        {"executado_em": "2026-10-15T11:06:00+00:00", "status": "FALHA_ENVIO", "conteudo": "edicao 15"},
    ]
    edicoes = hist.agrupar_por_dia(linhas)
    assert [e["data"].isoformat() for e in edicoes] == ["2026-10-15", "2026-10-14"]
    assert edicoes[0]["status"] == "ENVIADA"  # 1 envio ok basta; falha de outro assinante nao rebaixa
    assert edicoes[0]["conteudo"] == "edicao 15"


def test_falha_nunca_vira_sucesso_e_texto_mais_recente_vence():
    linhas = [
        {"executado_em": "2026-10-16T11:00:00Z", "status": "FALHA_ENVIO", "conteudo": "versao antiga"},
        {"executado_em": "2026-10-16T12:00:00Z", "status": "FALHA_ENVIO", "conteudo": None},
        {"executado_em": "2026-10-16T11:30:00Z", "status": "FALHA_ENVIO", "conteudo": "versao nova"},
        {"executado_em": None, "status": "ENVIADO"},
        {"executado_em": "lixo", "status": "ENVIADO"},
    ]
    (ed,) = hist.agrupar_por_dia(linhas)
    assert ed["status"] == "FALHA_ENVIO"
    assert ed["conteudo"] == "versao nova"


def test_listar_edicoes_nao_seleciona_destinatario_e_trata_banco_fora():
    hist.listar_edicoes.clear()
    with patch.object(hist, "obter_cliente", return_value=None):
        assert hist.listar_edicoes() is None
    hist.listar_edicoes.clear()
    cliente = MagicMock()
    tabela = cliente.table.return_value
    tabela.select.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    with patch.object(hist, "obter_cliente", return_value=cliente):
        assert hist.listar_edicoes() == []
    colunas = tabela.select.call_args[0][0]
    assert "destinatario" not in colunas
    # somente leitura
    assert not tabela.insert.called and not tabela.update.called and not tabela.delete.called
    hist.listar_edicoes.clear()


# --- tela do Morning Call ---------------------------------------------------------

def test_texto_para_html_escapa_antes_de_linkificar():
    saida = mc_tab.texto_para_html("<script>x</script> fonte: https://exemplo.com/a?b=1&c=2")
    assert "<script>" not in saida
    assert "&lt;script&gt;" in saida
    assert "<a href='https://exemplo.com/a?b=1&amp;c=2'" in saida


def test_tela_do_morning_call_nunca_importa_envio_de_email():
    fonte = Path(mc_tab.__file__).read_text(encoding="utf-8")
    assert "enviar_email" not in fonte.replace("sem enviar_email", "")
    assert "executar(" not in fonte and "enviar_teste" not in fonte


# --- vinculos -------------------------------------------------------------------

def test_setor_do_ticker_so_por_lista_curada():
    assert "PETRÓLEO & GÁS" in setores_do_ticker("PETR4")
    assert "BANCOS" in setores_do_ticker("ITUB4")
    assert setores_do_ticker("XPTO3") == []


# --- subabas do RADAR: mesma garantia de nunca coletar so' pra desenhar ------------

def _render_sem_coleta(fn, prefs):
    blocos = []

    def _proibido(*_a, **_k):
        raise AssertionError("coletor de rede chamado só para exibir o Radar")

    with patch.object(radar_quedas_mod, "resumo_fontes_vigentes", return_value={}), \
         patch.object(radar_quedas_mod, "painel_monitorados", return_value=[]), \
         patch.object(radar_quedas_mod, "alertas_periodo", return_value=[]), \
         patch.object(radar_quedas_mod, "coletar_carteiras_genial", side_effect=_proibido), \
         patch.object(radar_quedas_mod, "coletar_carteiras_safra", side_effect=_proibido), \
         patch.object(radar_tab_mod.st, "markdown", side_effect=lambda t, **_k: blocos.append(t)):
        fn.__wrapped__(prefs)
    return "\n".join(blocos)


def test_subabas_do_radar_renderizam_sem_coletar():
    prefs = {"formato_numerico": "BR", "watchlist": []}
    alertas = _render_sem_coleta(radar_tab_mod.render_radar_alertas, prefs)
    assert "RADAR DE QUEDAS" in alertas and "não constitui" in alertas
    carteiras = _render_sem_coleta(radar_tab_mod.render_radar_carteiras, prefs)
    assert "COBERTURA" in carteiras
    acompanhamento = _render_sem_coleta(radar_tab_mod.render_radar_acompanhamento, prefs)
    assert "Nenhum alerta de queda registrado" in acompanhamento


def test_alertas_com_banco_fora_mostram_indisponivel():
    blocos = []
    with patch.object(radar_quedas_mod, "resumo_fontes_vigentes", return_value=None), \
         patch.object(radar_tab_mod.st, "markdown", side_effect=lambda t, **_k: blocos.append(t)):
        radar_tab_mod.render_radar_alertas.__wrapped__({"formato_numerico": "BR", "watchlist": []})
    assert any("Banco indisponível" in b for b in blocos)


# --- telas sem rede: AppTest real ------------------------------------------------

def test_appteste_morning_call_historico_e_preferencias():
    from streamlit.testing.v1 import AppTest

    script = '''
import streamlit as st
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
import ui.morning_call_tab as mc
ed = {"data": datetime(2026, 10, 16).date(), "executado_em": datetime(2026, 10, 16, 8, 1, tzinfo=ZoneInfo("America/Sao_Paulo")),
      "conteudo": "1. RESUMO EXECUTIVO\\nfonte https://exemplo.com", "status": "ENVIADA"}
prefs = st.session_state.setdefault("prefs", {"morning_call_email_ativo": False})
st.session_state.setdefault("salvos", 0)
def persistir():
    st.session_state.salvos += 1
    return True
with patch.object(mc, "listar_edicoes", return_value=[ed]):
    mc.render_edicao_atual(prefs)
    mc.render_historico(prefs)
mc.render_preferencias(prefs, {"email": "teste@exemplo.com"}, persistir)
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "16/10/2026" in textos and "NÃO é a edição de hoje" in textos
    assert "<a href='https://exemplo.com'" in textos
    at.toggle(key="toggle_morning_call_email").set_value(True).run()
    assert at.session_state["prefs"]["morning_call_email_ativo"] is True
    assert at.session_state["salvos"] == 1
