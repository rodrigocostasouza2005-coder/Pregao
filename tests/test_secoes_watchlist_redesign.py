# -*- coding: utf-8 -*-
"""Testes da reformulação visual de MAIS > Watchlist (ui/secoes.py:
render_watchlist, 2026-11-06) - terminal denso de comparação lado a lado
(cotação+variação+volume+valuation básico+recomendação de research numa
só tabela, notícias da watchlist abaixo), no lugar do widget compacto
emprestado da VISÃO GERAL. ZERO dado novo: só mocka as mesmas fontes já
usadas em outras abas (data/mercado.py:obter_cotacoes_lote, data/
prices.py:obter_indicadores, data/news.py:obter_noticias_watchlist,
ui.visao_geral._teses_research_watchlist) - nunca inventa número/
recomendação.

Chamar render_watchlist direto em "bare mode" (fora de ScriptRunContext
real) é seguro: st.container/st.columns/st.markdown/st.button não lançam
exceção fora de uma sessão (mesmo padrão já usado em
tests/test_mercado_ranking_ui.py/test_calendario_ui.py)."""
from unittest.mock import patch

import ui.secoes as secoes

_PREFS = {"formato_numerico": "BR", "watchlist": ["PETR4", "VALE3"], "tema": "AMBAR"}


def _cotacoes_ok():
    return {
        "PETR4": {"preco": 36.52, "variacao_pct": 3.14, "volume_financeiro": 1_250_000_000.0, "erro": None},
        "VALE3": {"preco": 71.80, "variacao_pct": -1.02, "volume_financeiro": 980_000_000.0, "erro": None},
    }


def _indicadores(ticker):
    dados = {
        "PETR4": {"pl": 5.2, "pvp": 1.1, "dividend_yield": 12.4},
        "VALE3": {"pl": None, "pvp": 0.9, "dividend_yield": 8.1},
    }
    return dados[ticker]


def _teses():
    return [("PETR4", {"casa": "XP", "recomendacao": "COMPRA", "preco_alvo": 42.0})]


def _noticias_ok(tickers):
    return (
        [
            {"ticker": "PETR4", "titulo": "Petrobras anuncia novo plano de investimentos",
             "link": "https://exemplo.com/petr4", "data": "2026-11-06T10:00:00-03:00",
             "selo": "CONFIRMADA", "score": 9, "regras": ["veículo confiável"]},
        ],
        [],
    )


def _renderizar(prefs, cotacoes=None, indicadores=None, teses=None, noticias=None, links=None):
    """Chama render_watchlist de verdade, mockando as fontes de dado e
    capturando todo HTML passado a st.markdown + toda chamada a
    navegacao.link (os botões de atalho ticker->EQUITY/Fundamentos/
    Research)."""
    htmls = []
    chamadas_link = []

    def _espiao_link(rotulo, area_id, sub_id=None, *, chave, **kwargs):
        chamadas_link.append((rotulo, area_id, sub_id))
        return False

    with patch.object(secoes, "obter_cotacoes_lote", return_value=cotacoes if cotacoes is not None else _cotacoes_ok()), \
         patch.object(secoes, "obter_indicadores", side_effect=indicadores or _indicadores), \
         patch.object(secoes, "_teses_research_watchlist", return_value=teses if teses is not None else _teses()), \
         patch.object(secoes, "obter_noticias_watchlist", side_effect=noticias or _noticias_ok), \
         patch.object(secoes.navegacao, "link", side_effect=_espiao_link), \
         patch.object(secoes.st, "markdown", side_effect=lambda h, **k: htmls.append(h)):
        secoes.render_watchlist(prefs)
    return htmls, chamadas_link


# ============================================================
# 1. Watchlist vazia: mensagem de orientação, sem tabela/sem notícias,
#    sem chamar nenhuma fonte de dado (nada pra buscar)
# ============================================================

def test_1_watchlist_vazia_mostra_mensagem_e_nao_consulta_nenhuma_fonte():
    prefs = {**_PREFS, "watchlist": []}
    with patch.object(secoes, "obter_cotacoes_lote") as mock_cot, \
         patch.object(secoes, "obter_indicadores") as mock_ind, \
         patch.object(secoes, "obter_noticias_watchlist") as mock_news, \
         patch.object(secoes.st, "markdown", side_effect=lambda h, **k: None):
        secoes.render_watchlist(prefs)
    mock_cot.assert_not_called()
    mock_ind.assert_not_called()
    mock_news.assert_not_called()


# ============================================================
# 2. Watchlist populada: tabela comparativa tem ticker, preço formatado
#    BR, variação com sinal, P/L, P/VP, DY e a recomendação da casa
# ============================================================

def test_2_tabela_mostra_cotacao_variacao_volume_e_valuation_basico():
    htmls, _ = _renderizar(_PREFS)
    tabela = "".join(h for h in htmls if "<table" in h)
    assert "PETR4" in tabela and "VALE3" in tabela
    assert "36,52" in tabela  # preco BR (virgula decimal)
    assert "+3,14" in tabela  # variacao com sinal
    assert "-1,02" in tabela
    assert "5,20" in tabela  # P/L PETR4 (formatar_multiplo)
    assert "N.M." not in tabela  # nenhum multiplo <= 0 neste caso
    assert "—" in tabela  # P/L ausente de VALE3 (None) vira travessao, nunca inventado


def test_2b_recomendacao_de_research_aparece_na_linha_do_ticker_com_tese():
    htmls, _ = _renderizar(_PREFS)
    tabela = "".join(h for h in htmls if "<table" in h)
    assert "COMPRA" in tabela
    assert "XP" in tabela
    assert "42" in tabela  # preco-alvo
    # VALE3 nao tem tese nesta amostra -> travessao na celula de recomendacao,
    # nunca uma recomendacao inventada
    assert tabela.count("—") >= 1


def test_2c_recomendacao_nunca_inventada_quando_nao_ha_tese_salva():
    htmls, _ = _renderizar(_PREFS, teses=[])
    tabela = "".join(h for h in htmls if "<table" in h)
    assert "COMPRA" not in tabela and "VENDA" not in tabela


def test_2d_tabela_sinaliza_alta_baixa_com_classe_design_system():
    """Missão HOME/watchlist/cotações (2026-11-11): confirma que a
    sinalização verde/vermelho pedida pro terminal denso (ticker/preço/
    variação%/volume) vem de fato da classe do design system
    (`ds-numero alta`/`ds-numero baixa`, via design_system.variacao_html) -
    PETR4 (+3,14%) sai 'alta', VALE3 (-1,02%) sai 'baixa', nunca as duas
    presas na mesma cor."""
    htmls, _ = _renderizar(_PREFS)
    tabela = "".join(h for h in htmls if "<table" in h)
    linha_petr4 = tabela[tabela.index("PETR4"):tabela.index("VALE3")]
    linha_vale3 = tabela[tabela.index("VALE3"):]
    assert "ds-numero alta" in linha_petr4 and "ds-numero baixa" not in linha_petr4
    assert "ds-numero baixa" in linha_vale3


# ============================================================
# 3. Ticker sem cotação (fonte falhou pra esse papel) nunca derruba a
#    tela nem esconde os demais - mesma regra de _painel_watchlist_compacta
# ============================================================

def test_3_ticker_com_erro_de_cotacao_nao_quebra_e_nao_mostra_numero_falso():
    cotacoes = {
        "PETR4": {"erro": "sem dado"},
        "VALE3": {"preco": 71.80, "variacao_pct": -1.02, "volume_financeiro": 980_000_000.0, "erro": None},
    }
    htmls, _ = _renderizar(_PREFS, cotacoes=cotacoes)
    tabela = "".join(h for h in htmls if "<table" in h)
    assert "indisponível agora" in tabela
    assert "VALE3" in tabela and "71,8" in tabela


# ============================================================
# 4. Notícias da watchlist: feed compacto com ticker em destaque; quando
#    a fonte falha pra todo mundo, avisa sem inventar notícia
# ============================================================

def test_4_feed_de_noticias_mostra_ticker_e_manchete():
    htmls, _ = _renderizar(_PREFS)
    feed = "".join(h for h in htmls if "Petrobras anuncia" in h)
    assert feed
    assert "PETR4" in feed


def test_4b_sem_noticia_nenhuma_mostra_aviso_sem_quebrar():
    htmls, _ = _renderizar(_PREFS, noticias=lambda tickers: ([], []))
    assert any("sem notícias recentes" in h for h in htmls)


def test_4c_falha_na_fonte_de_noticias_avisa_sem_esconder_o_resto_da_tela():
    htmls, _ = _renderizar(_PREFS, noticias=lambda tickers: ([], list(tickers)))
    assert any("indisponível agora" in h for h in htmls)
    # tabela comparativa continua presente mesmo com noticias fora do ar
    assert any("<table" in h for h in htmls)


# ============================================================
# 5. Funcionalidade preservada: link rapido por ticker pra ANALISES >
#    Empresas (mesma rota/ajuda de antes) + atalhos novos pra Fundamentos
#    completos e Research > Casas de Analise
# ============================================================

def test_5_links_de_atalho_preservados_e_atalhos_novos_presentes():
    _, chamadas_link = _renderizar(_PREFS)
    rotas_ticker = {(area, sub) for _, area, sub in chamadas_link if area == "analises" and sub == "empresas"}
    assert ("analises", "empresas") in rotas_ticker
    tickers_linkados = {rotulo for rotulo, area, sub in chamadas_link if (area, sub) == ("analises", "empresas")}
    assert tickers_linkados == {"PETR4", "VALE3"}
    assert ("Fundamentos completos (comparar) ↗", "analises", "fundamentos") in chamadas_link
    assert ("Research · Casas de Análise ↗", "research", "casas") in chamadas_link
