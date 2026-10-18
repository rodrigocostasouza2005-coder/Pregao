# -*- coding: utf-8 -*-
"""Cobertura de jobs/morning_call_pdf.py - camada de apresentação
(ReportLab). Consome um dict no MESMO formato de
data/morning_call_editorial.py:montar_edicao, construído manualmente
aqui (sem rede) pra exercitar os caminhos de degradação (seção vazia/
erro/None) sem depender de nenhum provedor real."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import jobs.morning_call_pdf as pdf_mod

TZ_SP = ZoneInfo("America/Sao_Paulo")


def _indicador(nome, preco=100.0, variacao_pct=1.0, erro=None):
    return {"nome": nome, "preco": preco, "variacao_pct": variacao_pct, "barra_fmt": "14/10 10:00 (horário de Brasília)", "erro": erro}


def _edicao_minima(agora):
    """Edição com TODAS as seções degradadas (sem notícia, sem gráfico,
    sem agenda, sem card) - o caso mais adverso que gerar_pdf() precisa
    sobreviver sem lançar exceção."""
    return {
        "agora": agora,
        "capa": {"indicadores": [_indicador("Ibovespa"), _indicador("Dólar (USD/BRL)")], "destaques": []},
        "brasil": {
            "indicadores": [_indicador("Ibovespa"), _indicador("Dólar (USD/BRL)")],
            "historico_ibov": [],
            "destaque": None,
            "noticias": None,
            "noticias_erro": None,
        },
        "exterior": {
            "indicadores": [_indicador("S&P 500 futuro"), _indicador("Nasdaq futuro")],
            "historico_petroleo": [],
            "destaque": None,
            "noticias": None,
            "noticias_erro": "RuntimeError: Google News fora do ar",
            "interpretacoes": [{"texto": "Risco global: acompanhe os futuros.", "tag": "INTERPRETAÇÃO"}],
        },
        "empresas": {"cards": [], "agenda": None, "noticias_erro": None},
        "limitacoes": ("Conteúdo informativo, não constitui recomendação de investimento.",),
        "fontes": ("Cotações: Yahoo Finance (yfinance).",),
    }


def _edicao_completa(agora):
    """Edição com dado em TODAS as seções - inclusive um card de notícia
    SEM imagem cacheada (deve cair no placeholder tipográfico, nunca
    tentar rede: _baixar_imagem_card(None) devolve None sem chamar
    requests)."""
    edicao = _edicao_minima(agora)
    noticia_fato = {"titulo": "Petrobras anuncia dividendo extraordinário", "link": "https://exemplo.com/petr4", "veiculo": "InfoMoney", "tag": "FATO"}
    edicao["brasil"]["noticias"] = [noticia_fato]
    edicao["brasil"]["destaque"] = noticia_fato
    edicao["exterior"]["noticias"] = [{"titulo": "Fed sinaliza postura", "link": "https://exemplo.com/fed", "veiculo": "Reuters", "tag": "FATO"}]
    edicao["exterior"]["noticias_erro"] = None
    edicao["empresas"]["cards"] = [{
        "titulo": "Petrobras anuncia dividendo extraordinário", "link": "https://exemplo.com/petr4",
        "veiculo": "InfoMoney", "tag": "FATO", "resumo": "Resumo curto da notícia.",
        "imagem": None, "link_original": "https://exemplo.com/petr4",
    }]
    edicao["empresas"]["agenda"] = [{
        "empresa": "Petrobras", "ticker": "PETR4", "tipo_evento": "RESULTADO", "periodo": "3T26",
        "horario": "08:00", "status_rotulo": "CONFIRMADO", "status_nota": "data confirmada.", "tag": "ACOMPANHAR",
    }]
    return edicao


def test_gerar_pdf_com_tudo_degradado_produz_bytes_validos():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    pdf_bytes = pdf_mod.gerar_pdf(_edicao_minima(agora))
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_gerar_pdf_com_edicao_completa_produz_bytes_validos():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    pdf_bytes = pdf_mod.gerar_pdf(_edicao_completa(agora))
    assert pdf_bytes.startswith(b"%PDF")


def test_gerar_pdf_do_momento_usa_montar_edicao(monkeypatch):
    chamadas = []
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    monkeypatch.setattr(
        "data.morning_call_editorial.montar_edicao",
        lambda a=None: chamadas.append(a) or _edicao_minima(agora),
    )
    pdf_bytes = pdf_mod.gerar_pdf_do_momento(agora)
    assert pdf_bytes.startswith(b"%PDF")
    assert chamadas == [agora]


def test_grafico_linha_png_none_com_serie_vazia_ou_curta():
    assert pdf_mod._grafico_linha_png([]) is None
    assert pdf_mod._grafico_linha_png([(1, 10.0)]) is None


def test_grafico_linha_png_gera_imagem_com_serie_valida():
    serie = [(i, 100.0 + i) for i in range(10)]
    buffer = pdf_mod._grafico_linha_png(serie)
    assert buffer is not None
    assert buffer.read(4) == b"\x89PNG"


def test_baixar_imagem_card_sem_url_devolve_none_sem_chamar_rede(monkeypatch):
    chamado = []
    monkeypatch.setattr(pdf_mod, "requests", type("R", (), {"get": staticmethod(lambda *a, **k: chamado.append(1))})())
    assert pdf_mod._baixar_imagem_card(None) is None
    assert chamado == []


def test_baixar_imagem_card_content_type_invalido_devolve_none(monkeypatch):
    class _Resp:
        status_code = 200
        headers = {"Content-Type": "text/html"}

    monkeypatch.setattr(pdf_mod, "requests", type("R", (), {"get": staticmethod(lambda *a, **k: _Resp())})())
    assert pdf_mod._baixar_imagem_card("https://exemplo.com/img.png") is None


def test_baixar_imagem_card_http_erro_devolve_none(monkeypatch):
    class _Resp:
        status_code = 404
        headers = {}

    monkeypatch.setattr(pdf_mod, "requests", type("R", (), {"get": staticmethod(lambda *a, **k: _Resp())})())
    assert pdf_mod._baixar_imagem_card("https://exemplo.com/img.png") is None


def test_texto_variacao_e_cor_variacao_cobrem_alta_queda_estavel_e_indisponivel():
    assert pdf_mod._texto_variacao(1.5) == "+1,50%"
    assert pdf_mod._texto_variacao(-1.5) == "-1,50%"
    assert pdf_mod._texto_variacao(None) == "indisponível"
    assert pdf_mod._cor_variacao(1.5) == pdf_mod.VERDE_ALTA
    assert pdf_mod._cor_variacao(-1.5) == pdf_mod.VERMELHO_QUEDA
    assert pdf_mod._cor_variacao(None) == pdf_mod.CINZA_EDITORIAL


def test_quebrar_linhas_nunca_devolve_lista_vazia():
    assert pdf_mod._quebrar_linhas("", pdf_mod.SANS, 9, 100) == [""]
