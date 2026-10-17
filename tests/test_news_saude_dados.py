# -*- coding: utf-8 -*-
"""Testes de instrumentacao de SAUDE DOS DADOS em
data/news.py:obter_noticias_watchlist - achado real (auditoria missao
coletores, 2026-10-13): a linha "NEWS" do painel (data/saude_dados.py)
so' refletia obter_top_mercado_tudo (pool BRASIL+INTERNACIONAL); a
busca POR TICKER (o que a aba NOTICIAS de verdade usa pra watchlist)
nunca chamava registrar_tentativa - se quebrasse isolada, o painel
continuava mostrando "NEWS: Coleta OK" com a aba principal vazia.
Corrigido com uma linha separada ("NEWS (watchlist)", mesma categoria
Noticias) - ver REGISTRO_COLETORES em data/saude_dados.py.

test_9 em diante: instrumentacao de data/news.py:obter_noticias(ticker)
em si (BACKLOG.md "NEWS - obter_noticias fora da watchlist agregada sem
instrumentacao de SAUDE DOS DADOS") - ui/research_tab.py, ui/
calendario_tab.py e a visao de ticker unico de ui/news_tab.py chamam
obter_noticias(ticker) DIRETO (sem passar por obter_noticias_watchlist);
nome separado ("NEWS (ticker único)") pro mesmo motivo de "NEWS
(watchlist)" acima.

Mocka obter_noticias/registrar_tentativa - nunca faz chamada de rede.

Uso: python tests/test_news_saude_dados.py (venv)."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.news as news_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


def test_1_todos_os_tickers_ok_registra_sucesso_nao_parcial():
    def _fake_obter_noticias(ticker):
        return [{"ticker": ticker, "titulo": f"noticia de {ticker}", "data": "2026-10-13T10:00:00-03:00",
                  "titulos": [f"noticia de {ticker}"], "link": "https://x", "fontes": [], "veiculos": [],
                  "fontes_count": 0, "score": 50, "selo": "", "regras": [], "cvm_confirmacao": None, "tickers": []}]

    with patch.object(news_mod, "obter_noticias", side_effect=_fake_obter_noticias), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        todas, falhas = news_mod.obter_noticias_watchlist(["PETR4", "VALE3"])

    _checar("1a nenhuma falha reportada", falhas == [], f"(falhas={falhas})")
    _checar("1b registra NEWS (watchlist) execucao_ok=True",
            mock_reg.call_args.args[0] == "NEWS (watchlist)" and mock_reg.call_args.kwargs.get("execucao_ok") is True,
            f"(call={mock_reg.call_args})")
    _checar("1c nao marca parcial (nenhum ticker falhou)",
            mock_reg.call_args.kwargs.get("parcial") is False, f"(call={mock_reg.call_args})")


def test_2_alguns_tickers_falham_registra_sucesso_parcial():
    def _fake_obter_noticias(ticker):
        return None if ticker == "VALE3" else []

    with patch.object(news_mod, "obter_noticias", side_effect=_fake_obter_noticias), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        todas, falhas = news_mod.obter_noticias_watchlist(["PETR4", "VALE3"])

    _checar("2a so VALE3 em falhas", falhas == ["VALE3"], f"(falhas={falhas})")
    _checar("2b registra execucao_ok=True (PETR4 respondeu) E parcial=True",
            mock_reg.call_args.kwargs.get("execucao_ok") is True and mock_reg.call_args.kwargs.get("parcial") is True,
            f"(call={mock_reg.call_args})")


def test_3_todos_os_tickers_falham_registra_falha_real():
    """Bug que esta correcao previne: antes, isso nunca aparecia em
    SAUDE DOS DADOS - o painel continuava mostrando a linha "NEWS"
    (TOP MERCADO) como OK mesmo com a busca por ticker 100% quebrada."""
    with patch.object(news_mod, "obter_noticias", return_value=None), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        todas, falhas = news_mod.obter_noticias_watchlist(["PETR4", "VALE3"])

    _checar("3a todos os tickers em falhas", sorted(falhas) == ["PETR4", "VALE3"], f"(falhas={falhas})")
    _checar("3b registra NEWS (watchlist) execucao_ok=False",
            mock_reg.call_args.kwargs.get("execucao_ok") is False, f"(call={mock_reg.call_args})")


def test_4_watchlist_vazia_nao_registra_nada():
    """Watchlist vazia nao e' "falha" (nada pra buscar) - nao deve virar
    um FALHOU/NAO_COMPROVADO artificial no painel."""
    with patch.object(news_mod, "obter_noticias") as mock_obter, \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        todas, falhas = news_mod.obter_noticias_watchlist([])

    _checar("4a obter_noticias nunca chamado", mock_obter.call_count == 0)
    _checar("4b registrar_tentativa nunca chamado", mock_reg.call_count == 0)
    _checar("4c resultado vazio, sem falha", todas == [] and falhas == [])


def test_5_top_mercado_br_pool_falho_registra_falha_em_news():
    # bug real corrigido (auditoria missao coletores 2026-10-13,
    # continuacao): obter_top_mercado (BR) e
    # obter_top_mercado_internacional, chamados direto quando o usuario
    # filtra TOP MERCADO por regiao (ui/top_mercado_tab.py), nunca
    # chamavam registrar_tentativa - so' obter_top_mercado_tudo
    # chamava. Se o pool BR falhasse isolado enquanto o usuario olhava
    # so' o filtro BRASIL, SAUDE DOS DADOS continuava "NEWS: Coleta OK"
    # com base na ultima execucao bem-sucedida de "TUDO".
    news_mod.obter_top_mercado.clear()
    with patch.object(news_mod, "_coletar_pool_brasil", return_value=({}, False)), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        resultado = news_mod.obter_top_mercado()
    _checar("5a pool BR falho -> None (nunca inventa noticia)", resultado is None)
    _checar("5b registra NEWS execucao_ok=False (nao fica invisivel pro painel)",
            mock_reg.call_args.args[0] == "NEWS (Brasil)" and mock_reg.call_args.kwargs.get("execucao_ok") is False,
            f"(call={mock_reg.call_args})")


def test_6_top_mercado_br_sucesso_registra_ok_em_news():
    news_mod.obter_top_mercado.clear()
    with patch.object(news_mod, "_coletar_pool_brasil", return_value=({"https://x": {}}, True)), \
         patch.object(news_mod, "_processar_pool", return_value=[{"importancia": 1, "titulo": "A"}]), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        resultado = news_mod.obter_top_mercado()
    _checar("6a resultado real retornado", resultado == [{"importancia": 1, "titulo": "A"}], f"(resultado={resultado})")
    _checar("6b registra NEWS execucao_ok=True com registros_novos real",
            mock_reg.call_args.args[0] == "NEWS (Brasil)" and mock_reg.call_args.kwargs.get("execucao_ok") is True
            and mock_reg.call_args.kwargs.get("registros_novos") == 1, f"(call={mock_reg.call_args})")


def test_7_top_mercado_internacional_pool_falho_registra_falha_em_news():
    news_mod.obter_top_mercado_internacional.clear()
    with patch.object(news_mod, "_coletar_pool_internacional", return_value=({}, False)), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        resultado = news_mod.obter_top_mercado_internacional()
    _checar("7a pool INTL falho -> None (nunca inventa noticia)", resultado is None)
    _checar("7b registra NEWS execucao_ok=False (mesmo mecanismo do pool BR)",
            mock_reg.call_args.args[0] == "NEWS (Internacional)" and mock_reg.call_args.kwargs.get("execucao_ok") is False,
            f"(call={mock_reg.call_args})")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass  # ja' registrado em _FALHAS por _checar

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE SAUDE DOS DADOS (NEWS WATCHLIST) PASSARAM")


def test_8_excecao_em_um_ticker_nao_aborta_watchlist():
    news_mod.obter_noticias.clear()
    with (
        patch.object(news_mod, "obter_noticias", side_effect=[RuntimeError("falha isolada"), [{"titulo": "Noticia", "data": "2026-10-13T10:00:00-03:00", "ticker": "PETR4", "titulos": ["Noticia"], "fontes": [], "veiculos": [], "fontes_count": 0}]]),
        patch.object(news_mod, "registrar_tentativa") as mock_reg,
        patch.object(news_mod, "logging") as mock_logging,
    ):
        todas, falhas = news_mod.obter_noticias_watchlist(["BAD1", "PETR4"])
    _checar("8a continua coleta do segundo ticker", len(todas) == 1)
    _checar("8b marca apenas ticker que falhou", falhas == ["BAD1"])
    _checar("8c registra falha inesperada no log", mock_logging.exception.called)
    _checar("8d registra coleta parcial no painel", mock_reg.call_args.kwargs.get("parcial") is True)


def test_google_news_feed_repete_timeout_transitorio():
    from unittest.mock import Mock
    from requests import Timeout
    resposta = Mock()
    resposta.status_code = 200
    resposta.raise_for_status.return_value = None
    resposta.content = b'<rss version="2.0"><channel><title>Teste</title><item><title>Resultado</title></item></channel></rss>'
    with patch.object(news_mod.requests, "get", side_effect=[Timeout("lento"), resposta]) as get, patch.object(news_mod.time, "sleep"):
        resultado = news_mod._buscar_feed_de_url("https://example.com/feed")
    _checar("Google News recupera apos timeout", resultado is not None)
    _checar("Google News repete uma vez", get.call_count == 2)


def test_9_obter_noticias_busca_falha_registra_falha_sem_propagar():
    """_buscar_feed so' devolve None numa falha real de requisicao (ver
    docstring de _buscar_feed_de_url) - nunca lanca excecao pro caller;
    obter_noticias precisa manter esse contrato (retornar None) E
    registrar a falha em "NEWS (ticker único)", sem o caller (ui/
    research_tab.py etc.) precisar de try/except."""
    news_mod.obter_noticias.clear()
    with patch.object(news_mod, "_buscar_feed", return_value=None), \
         patch.object(news_mod, "obter_nome_yf", return_value="Petrobras"), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        resultado = news_mod.obter_noticias("PETR4")
    _checar("9a busca falhou -> None (nunca inventa noticia, nunca propaga excecao)", resultado is None)
    _checar("9b registra NEWS (ticker único) execucao_ok=False",
            mock_reg.call_args.args[0] == "NEWS (ticker único)" and mock_reg.call_args.kwargs.get("execucao_ok") is False,
            f"(call={mock_reg.call_args})")


def test_10_obter_noticias_sem_item_relevante_registra_sucesso_zero():
    """Fonte respondeu mas sem noticia nenhuma pro papel (lista vazia,
    nao None - ver docstring de obter_noticias): ainda e' sucesso de
    execucao, so' sem novidade - registros_novos deve bater com 0."""
    news_mod.obter_noticias.clear()
    with patch.object(news_mod, "_buscar_feed", return_value=[]), \
         patch.object(news_mod, "obter_nome_yf", return_value="Petrobras"), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        resultado = news_mod.obter_noticias("PETR4")
    _checar("10a fonte respondeu sem noticia -> lista vazia (nao None)", resultado == [])
    _checar("10b registra NEWS (ticker único) execucao_ok=True com registros_novos=0",
            mock_reg.call_args.args[0] == "NEWS (ticker único)" and mock_reg.call_args.kwargs.get("execucao_ok") is True
            and mock_reg.call_args.kwargs.get("registros_novos") == 0, f"(call={mock_reg.call_args})")


def test_11_obter_noticias_sucesso_com_noticia_registra_contagem_real():
    """registros_novos registrado precisa bater com a contagem REAL do
    resultado devolvido pro caller - nao um valor fixo/estimado."""
    news_mod.obter_noticias.clear()
    agora = datetime.now(timezone.utc)
    published_parsed = (agora.year, agora.month, agora.day, agora.hour, agora.minute, agora.second, 0, 0, 0)
    entry = {
        "title": "PETR4 anuncia resultado forte do trimestre - InfoMoney",
        "link": "https://infomoney.com.br/noticia-1",
        "published_parsed": published_parsed,
        "source": {"title": "InfoMoney", "href": "https://infomoney.com.br"},
    }
    with patch.object(news_mod, "_buscar_feed", return_value=[entry]), \
         patch.object(news_mod, "obter_nome_yf", return_value="Petrobras"), \
         patch.object(news_mod, "documento_confirmador", return_value=None), \
         patch.object(news_mod, "registrar_tentativa") as mock_reg:
        resultado = news_mod.obter_noticias("PETR4")
    _checar("11a retorna 1 noticia real (grupo relevante)", resultado is not None and len(resultado) == 1, f"(resultado={resultado})")
    _checar("11b registra NEWS (ticker único) execucao_ok=True com contagem real",
            mock_reg.call_args.args[0] == "NEWS (ticker único)" and mock_reg.call_args.kwargs.get("execucao_ok") is True
            and mock_reg.call_args.kwargs.get("registros_novos") == len(resultado),
            f"(call={mock_reg.call_args}, resultado={resultado})")
