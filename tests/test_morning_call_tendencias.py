# -*- coding: utf-8 -*-
"""Seção 6 do Morning Call (jobs/morning_call.py:_secao_tendencias) derivada
dos dados da edição - antes eram 3 frases fixas iguais todo dia - e erros de
coleta que não vazam exceção pro e-mail do assinante."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import jobs.morning_call as mc

AGORA = datetime(2026, 10, 22, 8, 3, tzinfo=ZoneInfo("America/Sao_Paulo"))


def _cot(var, **extra):
    return {"preco": 100.0, "variacao_pct": var, "erro": None, **extra}


def test_so_movimentos_de_1_por_cento_ou_mais_viram_item():
    linhas = mc._secao_tendencias(
        [("Dólar (USD/BRL)", _cot(0.4)), ("Petróleo Brent", _cot(-2.31)), ("Ouro", _cot(1.0))], [])
    texto = "\n".join(linhas)
    assert "Petróleo Brent em queda de 2,31%" in texto and "Petrobras" in texto
    assert "Ouro em alta de 1,00%" in texto
    assert "Dólar" not in texto
    assert all(l.startswith("- [INTERPRETAÇÃO]") for l in linhas[2:])


def test_valor_de_cache_ou_erro_nao_vira_gatilho():
    antigo = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    linhas = mc._secao_tendencias(
        [("Petróleo Brent", _cot(-3.0, _fallback_cache=True, _coletado_em=antigo)),
         ("Ouro", {"erro": "sem dado"})], [])
    assert "sem gatilho específico" in linhas[-1]


def test_resultados_de_hoje_entram_com_os_tickers():
    eventos = [{"ticker": t, "data": date(2026, 10, 22)} for t in
               ("PETR4", "VALE3", "ITUB4", "BBDC4", "WEGE3", "ABEV3", "RENT3")]
    texto = "\n".join(mc._secao_tendencias([], eventos))
    assert "PETR4, VALE3, ITUB4, BBDC4, WEGE3, ABEV3 e mais 1" in texto


def test_sem_gatilho_diz_isso_em_vez_de_texto_generico():
    linhas = mc._secao_tendencias([("Dólar (USD/BRL)", _cot(0.2))], [])
    assert linhas[1] == "6. TENDÊNCIAS E RISCOS A ACOMPANHAR"
    assert len(linhas) == 3 and "sem gatilho específico" in linhas[2]
    assert "acompanhe a direção dos futuros" not in "\n".join(linhas)


def test_agenda_indisponivel_e_vazia_sao_diferentes():
    assert "indisponível" in mc._secao_agenda(AGORA, None)[-1]
    assert "Nenhum evento" in mc._secao_agenda(AGORA, [])[-1]
    with patch.object(mc, "calcular_calendario_cacheado", side_effect=RuntimeError("cvm fora")):
        assert mc._eventos_hoje(AGORA) is None


def test_email_completo_nao_expoe_excecao_de_noticias_e_mantem_secoes():
    def _quebra():
        raise RuntimeError("HTTPSConnectionPool(host='news.google.com')")

    cot = _cot(1.5, _barra_em="2026-10-21T00:00:00-03:00")
    with patch.object(mc, "obter_cotacao_indice", return_value=cot), \
         patch.object(mc, "_noticias_por_regiao", _quebra), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_selic_meta_copom", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None):
        texto = mc.montar_morning_call(AGORA)
    assert "HTTPSConnectionPool" not in texto and "RuntimeError" not in texto
    assert "Notícias indisponíveis nesta execução (a coleta do Google News falhou)." in texto
    assert all(secao in texto for secao in mc.SECOES_OBRIGATORIAS)
    assert "[INTERPRETAÇÃO] Dólar (USD/BRL) em alta de 1,50%" in texto


# --- tradução das manchetes internacionais no e-mail -------------------------

def test_email_traduz_manchete_e_preserva_o_original():
    itens = [{"titulo": "UK inflation jumps to 3.5% as prices rise", "link": "https://cnbc/1"}]
    linhas = mc._linhas_noticias(itens, 8, {"https://cnbc/1": "Inflação do Reino Unido sobe para 3,5%"})
    assert linhas == ["- Inflação do Reino Unido sobe para 3,5% (original: UK inflation jumps to 3.5% as prices rise)"
                      " — https://cnbc/1"]


def test_email_sinaliza_ingles_sem_traducao_e_nao_mexe_no_portugues():
    itens = [{"titulo": "Stocks are heading for a showdown as earnings collide with rates", "link": "https://mw/1"},
             {"titulo": "Ibovespa sobe 0,54% com apoio do petróleo", "link": "https://valor/1"}]
    linhas = mc._linhas_noticias(itens, 8, {})
    assert "[em inglês - tradução indisponível nesta edição]" in linhas[0]
    assert linhas[1] == "- Ibovespa sobe 0,54% com apoio do petróleo — https://valor/1"


def test_heuristica_de_idioma_e_a_mesma_do_pdf():
    from data.news import parece_ingles

    assert parece_ingles("Fed signals interest rate cuts as inflation cools")
    assert not parece_ingles("Copom mantém Selic em 15% e sinaliza cautela")
