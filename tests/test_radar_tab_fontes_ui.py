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


def _capturar_render(resumo_fontes, alertas=None, monitorados=None):
    """Chama render_radar de verdade com os dados ja' persistidos mockados
    (resumo_fontes_vigentes/painel_monitorados/alertas_periodo, sem rede)
    e os coletores reais substituidos por algo que FALHA o teste se for
    chamado - prova que desenhar a tela nao dispara coleta nova. Retorna
    todo o HTML passado a st.markdown, concatenado."""
    blocos = []

    def _coletor_nao_deveria_ser_chamado(*_a, **_k):
        raise AssertionError("coletor de rede chamado só para exibir o Radar")

    with patch.object(radar_quedas_mod, "resumo_fontes_vigentes", return_value=resumo_fontes), \
         patch.object(radar_quedas_mod, "painel_monitorados", return_value=monitorados if monitorados is not None else []), \
         patch.object(radar_quedas_mod, "alertas_periodo", return_value=alertas if alertas is not None else []), \
         patch.object(radar_quedas_mod, "coletar_carteiras_genial", side_effect=_coletor_nao_deveria_ser_chamado), \
         patch.object(radar_quedas_mod, "coletar_carteiras_safra", side_effect=_coletor_nao_deveria_ser_chamado), \
         patch.object(radar_tab_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)):
        # render_radar e' decorado com @st.fragment, que em bare mode (sem
        # ScriptRunContext real) NUNCA executa o corpo da funcao - chamar
        # render_radar(...) direto aqui silenciosamente nao faria nada e o
        # teste passaria "por acidente" sem checar coisa alguma.
        # .__wrapped__ e' a funcao original (sem o decorador).
        radar_tab_mod.render_radar.__wrapped__(_PREFS_SEM_WATCHLIST)

    return "\n".join(b for b in blocos if not b.lstrip().startswith("<style>"))


def _linha_da_casa(html_render, casa):
    inicio = html_render.index(f"<td class='rq-esq'>{casa}</td>")
    return html_render[inicio:html_render.index("</tr>", inicio)]


def test_fonte_atualizada_e_fonte_indisponivel_sao_distinguidas():
    resumo = {
        "Safra Corretora": {"ativos": 10, "verificado_em": "2026-10-17T10:00:00+00:00", "desatualizada": False,
                            "carteiras": ["Top 10 Ações"], "data_publicacao": "2026-10-01"},
        # Genial Analisa ausente do resumo -> UI trata como indisponível
    }
    html_render = _capturar_render(resumo)
    assert "rq-estado-ATUALIZADA" in _linha_da_casa(html_render, "Safra Corretora")
    assert "rq-estado-INDISPONIVEL" in _linha_da_casa(html_render, "Genial Analisa")
    assert "1 de 2 casas com carteira vigente" in html_render
    assert "rq-estado-DESATUALIZADA" not in html_render


def test_fonte_desatualizada_e_distinguida_de_atualizada_e_de_indisponivel():
    resumo = {
        "Safra Corretora": {"ativos": 10, "verificado_em": "2026-09-01T10:00:00+00:00", "desatualizada": True,
                            "carteiras": ["Top 10 Ações"], "data_publicacao": "2026-09-01"},
        "Genial Analisa": {"ativos": 42, "verificado_em": "2026-10-17T10:00:00+00:00", "desatualizada": False,
                           "carteiras": ["Carteira Ações"], "data_publicacao": "2026-10-05"},
    }
    html_render = _capturar_render(resumo)
    assert "rq-estado-DESATUALIZADA" in _linha_da_casa(html_render, "Safra Corretora")
    assert "rq-estado-ATUALIZADA" in _linha_da_casa(html_render, "Genial Analisa")
    assert "rq-estado-INDISPONIVEL" not in html_render
    assert "2 de 2 casas com carteira vigente" in html_render


def test_supabase_indisponivel_avisa_e_nao_quebra():
    """resumo_fontes_vigentes() devolve None quando o Supabase está fora do
    ar - a UI avisa, não desenha tabela nenhuma e nunca lança exceção."""
    html_render = _capturar_render(resumo_fontes=None)
    assert "Banco indisponível" in html_render
    assert "rq-tabela" not in html_render


def test_alertas_e_monitorados_renderizados_com_numero_brasileiro_e_estado_do_email():
    import data.radar_quedas as rq
    resumo = {"Safra Corretora": {"ativos": 2, "verificado_em": "2026-10-17T10:00:00+00:00", "desatualizada": False,
                                  "carteiras": ["Top 10 Ações"], "data_publicacao": "2026-10-01"}}
    monitorados = rq.linhas_monitorados(
        [{"casa": "Safra Corretora", "carteira": "Top 10 Ações", "ticker": "PETR4", "empresa": "Petrobras"},
         {"casa": "Safra Corretora", "carteira": "Top 10 Ações", "ticker": "VALE3", "empresa": "Vale"}],
        {"PETR4": {"preco": 36.10, "fechamento_anterior": 37.92, "erro": None}, "VALE3": {"erro": "timeout"}},
    )
    alertas = [{"ticker": "PETR4", "empresa": "Petrobras", "pregao": "2026-10-16", "variacao_pct": -4.7996,
                "preco_atual": 36.10, "fechamento_anterior": 37.92, "casas": ["Safra Corretora"],
                "carteiras": ["Top 10 Ações"], "fontes": ["https://www.safra.com.br/x"],
                "alertado_em": "2026-10-16T15:31:05+00:00", "status": "FALHA_ENVIO"}]
    html_render = _capturar_render(resumo, alertas=alertas, monitorados=monitorados)
    assert "-4,80%" in html_render and "37,92" in html_render  # formato BR, nunca 37.92
    assert "rq-estado-ALERTA" in html_render
    assert "rq-estado-SEM_COTACAO" in html_render  # VALE3 sem cotação não vira "0,00%"
    assert "rq-estado-FALHOU" in html_render and "FALHA_ENVIO" not in html_render
    assert "16/10 12:31" in html_render  # horário de Brasília, não ISO UTC


def test_ticker_monitorado_e_alertado_e_link_real_para_analises():
    """Achado da auditoria 2026-10-18 (P1, documentado mas nao
    corrigido la': ".rq-ticker sem destino", mesma cor/peso do padrao
    "isto e' clicavel" do resto do app, sem nenhum jeito de ir ate
    EQUITY/ANALISES). Corrigido nesta missao de redesign 2026-10-19
    com link real (<a>), mantendo a tabela densa (sem converter pra
    st.button por linha)."""
    monitorados = [{
        "ticker": "PETR4", "empresa": "Petrobras", "casas": ["Safra Corretora"],
        "estado": "NORMAL", "preco": 36.10, "fechamento_anterior": 37.92,
        "variacao_pct": -4.8, "distancia_gatilho_pp": 3.5,
    }]
    alertas = [{
        "ticker": "VALE3", "empresa": "Vale", "pregao": "2026-10-16", "variacao_pct": -5.1,
        "preco_atual": 60.0, "fechamento_anterior": 63.2, "casas": ["Safra Corretora"],
        "carteiras": ["Top 10 Ações"], "fontes": [], "alertado_em": "2026-10-16T15:31:05+00:00",
        "status": "ENVIADO",
    }]
    html_render = _capturar_render({}, alertas=alertas, monitorados=monitorados)
    assert "<a class='rq-ticker' href='?aba=analises&sub=empresas&ticker=PETR4' target='_self'>PETR4</a>" in html_render
    assert "<a class='rq-ticker' href='?aba=analises&sub=empresas&ticker=VALE3' target='_self'>VALE3</a>" in html_render
