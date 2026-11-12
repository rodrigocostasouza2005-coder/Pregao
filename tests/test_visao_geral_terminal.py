# -*- coding: utf-8 -*-
"""Redesign terminal de VISÃO GERAL (2026-10-27, inspirado em Bloomberg,
aprovado via prévia visual): cockpit fixo (sem workspace modular nesta
aba), indicadores densos, leitura do pregão condensada, gráfico+"para
investigar", grade de exploração (altas/baixas com barra de magnitude,
notícias, mapa setorial com flag de dispersão), desempenho+agenda/teses
de research. Cobre: REGISTRO_PAINEIS vazio (sem drag), cada painel
renderiza sem exceção (dados reais e vazios), teses de research só
aparecem com recomendação real salva, e render_visao_geral completo roda
sem exceção com tudo mockado."""
from unittest.mock import patch

import ui.graficos as graficos_mod
import ui.visao_geral as vg

_PREFS = {"formato_numerico": "BR", "watchlist": [], "tema": "AMBAR"}

_ALTAS = [
    {"ticker": "PETR4", "preco": 36.5, "variacao_pct": 3.1, "setor": "Petróleo e Gás"},
    {"ticker": "PRIO3", "preco": 40.0, "variacao_pct": 1.2, "setor": "Petróleo e Gás"},
]
_BAIXAS = [{"ticker": "MGLU3", "preco": 2.1, "variacao_pct": -4.2, "setor": "Consumo"}]
_SETORES = [
    {"setor": "Petróleo e Gás", "variacao_media_pct": 2.1, "n_papeis": 5},
    {"setor": "Varejo", "variacao_media_pct": -4.3, "n_papeis": 2},
]
_NEGOCIADOS = [
    {"ticker": "PETR4", "preco": 36.5, "variacao_pct": 3.1, "setor": "Petróleo e Gás", "volume_financeiro": 4.2e9},
]
_COTACAO_OK = {"preco": 136000.0, "variacao_pct": 0.8, "erro": False}


def _ids():
    return [pid for pid, _, _ in vg.REGISTRO_PAINEIS]


def test_registro_paineis_vazio_sem_drag():
    # redesign terminal: todo o conteudo virou secao fixa - sem workspace
    # modular nesta aba (MERCADO > PAINEL continua com drag, intocado).
    assert _ids() == []


def test_altas_baixas_resumo_renderiza_sem_excecao():
    with patch.object(vg, "obter_altas_baixas", return_value=(_ALTAS, _BAIXAS)):
        vg._painel_altas_baixas_resumo(_PREFS)


def test_mapa_setorial_compacto_renderiza_flag_dispersao_sem_excecao():
    with patch.object(vg, "obter_desempenho_setorial", return_value=_SETORES):
        vg._painel_mapa_setorial_compacto(_PREFS)


def test_desempenho_tabela_renderiza_sem_excecao():
    with patch.object(vg, "obter_mais_negociados", return_value=_NEGOCIADOS):
        vg._painel_desempenho_tabela(_PREFS)


def test_indicadores_renderiza_sem_excecao():
    with patch.object(vg, "obter_composicao_oficial", return_value={"PETR4": {}}), \
         patch.object(vg, "obter_mercados_globais", return_value=[]), \
         patch.object(vg, "obter_cdi", return_value=None), \
         patch.object(vg, "obter_cotacao_indice", return_value=_COTACAO_OK), \
         patch.object(vg, "obter_cotacao", return_value=_COTACAO_OK):
        vg._painel_indicadores(_PREFS)


def test_paineis_vazios_nao_quebram():
    with patch.object(vg, "obter_altas_baixas", return_value=([], [])):
        vg._painel_altas_baixas_resumo(_PREFS)
    with patch.object(vg, "obter_desempenho_setorial", return_value=[]):
        vg._painel_mapa_setorial_compacto(_PREFS)
    with patch.object(vg, "obter_mais_negociados", return_value=[]):
        vg._painel_desempenho_tabela(_PREFS)


def test_teses_research_watchlist_sem_watchlist_retorna_vazio():
    assert vg._teses_research_watchlist({"watchlist": []}) == []


def test_teses_research_watchlist_so_inclui_item_com_recomendacao_real():
    relatorios = [
        {"casa": "Genial Analisa", "tickers": ["PETR4"], "recomendacao": "COMPRA", "preco_alvo": 44.0},
        {"casa": "XP", "tickers": ["VALE3"], "recomendacao": None, "preco_alvo": None},
    ]
    with patch.object(vg, "_casas_ativas", return_value=["genial"]), \
         patch.object(vg, "preparar_leitura", return_value=(relatorios, [], [], [])):
        itens = vg._teses_research_watchlist({"watchlist": ["PETR4", "VALE3"]})
    assert len(itens) == 1
    assert itens[0][0] == "PETR4"
    assert itens[0][1]["recomendacao"] == "COMPRA"


def test_painel_agenda_e_teses_renderiza_sem_excecao():
    with patch.object(vg, "_painel_proximos_watchlist", return_value=None), \
         patch.object(vg, "_teses_research_watchlist", return_value=[
             ("PETR4", {"casa": "Genial Analisa", "recomendacao": "COMPRA", "preco_alvo": 44.0}),
         ]):
        vg._painel_agenda_e_teses(_PREFS)


def test_painel_leitura_pregao_chips_ficam_dentro_de_bloco_html():
    """Regressão de um bug real achado via Playwright (auditoria
    independente de HOME/MERCADO, 2026-11-06): os chips (_chip_html)
    começam com <span>, tag INLINE - o CommonMark só reconhece "HTML
    block" (conteúdo cru, sem nenhum parsing inline por cima) quando a
    string passada a st.markdown começa com uma tag de BLOCO (div/table/
    p/...), nunca com <span>/<em>/<a>. Sem isso, o markdown-it do
    Streamlit processa a string como parágrafo normal, e QUALQUER "$"
    solto (ex: "R$" no chip de maior negociado + um "US$" dentro de um
    texto de síntese por IA, os dois reais e sem relação um com o outro)
    é interpretado como abre/fecha de matemática LaTeX - tudo entre os
    dois "$" virava um bloco "language-math" quebrado em vez do HTML
    pretendido (confirmado via Playwright contra um harness real:
    reproduzido e corrigido, screenshot antes/depois). Envolver a string
    final num <div> faz o CommonMark reconhecer HTML block de verdade e
    pular o parsing inline - mesmo efeito visual, zero dado alterado."""
    negociado_com_cifrao = [
        {"ticker": "PETR4", "preco": 36.5, "variacao_pct": 3.1, "setor": "Petróleo e Gás", "volume_financeiro": 4.2e9},
    ]
    sintese_com_cifrao_extra = {
        "ok": True, "gerado_em": None, "atual": True,
        "dados": {
            "resumo_executivo": {"texto": "Ibov sobe."},
            # "US$" aqui e' o 2o "$" da rodada - junto com o "R$" do chip
            # de maior volume financeiro (sempre presente), e' exatamente
            # a combinacao real que disparava o bug.
            "movimentos": [{"evento": "Brent sobe acima de US$ 86", "fonte": "Valor Econômico"}],
            "oportunidades_riscos": [], "cenarios": [],
        },
    }
    htmls = []
    with patch.object(vg, "obter_altas_baixas", return_value=([], [])), \
         patch.object(vg, "obter_mais_negociados", return_value=negociado_com_cifrao), \
         patch.object(vg, "_proximo_evento_watchlist", return_value=None), \
         patch.object(vg, "obter_sintese_mercado", return_value=sintese_com_cifrao_extra), \
         patch.object(vg.st, "markdown", side_effect=lambda html, **k: htmls.append(html)):
        vg._painel_leitura_pregao(_PREFS)

    chamada_chips = next(h for h in htmls if "DADO" in h and "<span" in h)
    assert chamada_chips.lstrip().startswith("<div>"), (
        f"chips precisam estar envolvidos por uma tag de BLOCO (<div>), nunca "
        f"começar direto com <span> (tag inline, vulnerável ao parsing de "
        f"matemática do Streamlit quando há 2+ '$' na mesma chamada): {chamada_chips[:80]!r}"
    )
    # ambos os "$" (R$ do chip de volume, US$ do texto de sintese) continuam
    # no HTML gerado, intactos - a string em si nao e' alterada, so' passa a
    # vir envolvida por <div> (o parsing errado de "$...$" como matematica
    # acontece no browser, do lado do markdown-it do Streamlit - nao da pra
    # reproduzir aqui sem um browser real, ja validado via Playwright).
    assert "R$" in chamada_chips and "US$ 86" in chamada_chips


def test_painel_watchlist_compacta_sinaliza_alta_baixa_via_design_system():
    """Missão HOME/watchlist/cotações (2026-11-11): "MINHA WATCHLIST" (painel
    compacto da Visão Geral, `_painel_watchlist_compacta`) precisa mostrar
    sinalização verde/vermelho real por ativo - isso já vinha de
    `design_system.variacao_html` (sem CSS paralelo), mas nenhum teste
    conferia que a classe aplicada bate com o SINAL de cada cotação. Regressão:
    garante que uma alta (PETR4, +3,14%) sai com a classe 'alta' e uma baixa
    (VALE3, -1,02%) sai com 'baixa', nunca as duas presas na mesma classe."""
    cotacoes = {
        "PETR4": {"preco": 36.52, "variacao_pct": 3.14, "volume_financeiro": 1_250_000_000.0, "erro": None},
        "VALE3": {"preco": 71.80, "variacao_pct": -1.02, "volume_financeiro": 980_000_000.0, "erro": None},
    }
    prefs = {"formato_numerico": "BR", "watchlist": ["PETR4", "VALE3"], "tema": "AMBAR"}
    htmls = []
    with patch.object(vg, "obter_cotacoes_lote", return_value=cotacoes), \
         patch.object(vg.st, "markdown", side_effect=lambda h, **k: htmls.append(h)):
        vg._painel_watchlist_compacta(prefs)
    tabela = "".join(h for h in htmls if "<table" in h)
    linha_petr4 = tabela[tabela.index("PETR4"):tabela.index("VALE3")]
    linha_vale3 = tabela[tabela.index("VALE3"):]
    assert "ds-numero alta" in linha_petr4
    assert "ds-numero baixa" not in linha_petr4
    assert "ds-numero baixa" in linha_vale3


def test_altas_baixas_resumo_sinaliza_cores_corretas():
    """"PRINCIPAIS ALTAS E BAIXAS": a coluna ALTAS só deve conter variação
    marcada como 'alta' e a coluna BAIXAS só 'baixa' - nenhuma mistura."""
    htmls = []
    with patch.object(vg, "obter_altas_baixas", return_value=(_ALTAS, _BAIXAS)), \
         patch.object(vg.st, "markdown", side_effect=lambda h, **k: htmls.append(h)):
        vg._painel_altas_baixas_resumo(_PREFS)
    bloco_altas = next(h for h in htmls if "PETR4" in h or "PRIO3" in h)
    bloco_baixas = next(h for h in htmls if "MGLU3" in h)
    assert "ds-numero alta" in bloco_altas and "ds-numero baixa" not in bloco_altas
    assert "ds-numero baixa" in bloco_baixas and "ds-numero alta" not in bloco_baixas


def test_desempenho_tabela_sinaliza_cor_da_variacao():
    """"MAIS NEGOCIADOS (VOLUME)": variação positiva sai com classe 'alta'."""
    htmls = []
    with patch.object(vg, "obter_mais_negociados", return_value=_NEGOCIADOS), \
         patch.object(vg.st, "markdown", side_effect=lambda h, **k: htmls.append(h)):
        vg._painel_desempenho_tabela(_PREFS)
    tabela = "".join(h for h in htmls if "<table" in h)
    assert "ds-numero alta" in tabela


def test_render_visao_geral_completo_sem_excecao():
    """render_visao_geral (cockpit fixo de ponta a ponta), tudo mockado -
    garante que a composição inteira (indicadores/leitura do pregão/
    gráfico+investigar/grade de exploração/desempenho+agenda/globais+
    watchlist) roda sem exceção."""
    prefs = {"formato_numerico": "BR", "watchlist": [], "tema": "AMBAR"}
    with patch.object(vg, "obter_composicao_oficial", return_value={"PETR4": {}}), \
         patch.object(vg, "obter_mercados_globais", return_value=[]), \
         patch.object(vg, "obter_cdi", return_value=None), \
         patch.object(vg, "obter_cotacao_indice", return_value=_COTACAO_OK), \
         patch.object(vg, "obter_cotacao", return_value=_COTACAO_OK), \
         patch.object(vg, "obter_altas_baixas", return_value=(_ALTAS, _BAIXAS)), \
         patch.object(vg, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(vg, "obter_desempenho_setorial", return_value=_SETORES), \
         patch.object(vg, "obter_mais_negociados", return_value=_NEGOCIADOS), \
         patch.object(vg, "_painel_proximos_watchlist", return_value=None), \
         patch.object(vg, "_teses_research_watchlist", return_value=[]), \
         patch.object(vg, "_proximo_evento_watchlist", return_value=None), \
         patch.object(vg, "obter_sintese_mercado", return_value={"ok": False, "motivo": "teste"}), \
         patch.object(graficos_mod, "obter_historico", return_value=None), \
         patch.object(graficos_mod, "obter_historico_intraday", return_value=None), \
         patch.object(vg, "_painel_globais", return_value=None), \
         patch.object(vg, "obter_cotacoes_lote", return_value={}):
        vg.render_visao_geral(prefs, persistir_fn=None)
