# -*- coding: utf-8 -*-
"""Cobertura de jobs/morning_call_pdf.py - camada de apresentação
(ReportLab). Consome um dict no MESMO formato de
data/morning_call_editorial.py:montar_edicao, construído manualmente
aqui (sem rede) pra exercitar os caminhos de degradação (seção vazia/
erro/None) sem depender de nenhum provedor real."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from reportlab.pdfbase.pdfmetrics import getAscent

import jobs.morning_call_pdf as pdf_mod

TZ_SP = ZoneInfo("America/Sao_Paulo")


class _CanvasRecorder:
    """Fake mínimo do Canvas do ReportLab - só grava (x, y, texto) de cada
    drawString, sem desenhar nada de verdade. Usado pra testar POSIÇÃO
    sem precisar rasterizar um PDF de verdade (ver
    test_card_indicador_nunca_desenha_variacao_e_barra_na_mesma_linha)."""

    def __init__(self):
        self.textos = []

    def setFillColor(self, *_a, **_k):
        pass

    def setStrokeColor(self, *_a, **_k):
        pass

    def setFont(self, *_a, **_k):
        pass

    def roundRect(self, *_a, **_k):
        pass

    def drawString(self, x, y, texto):
        self.textos.append((x, y, texto))


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


# ---------------------------------------------------------------------
# REGRESSÃO - 3 bugs reais achados por inspeção visual (render de
# verdade via Playwright/PyMuPDF, 2026-10-17), nenhum pego por teste
# automatizado até aqui. Cada um ganha um teste geométrico/determinístico
# que não depende de rasterizar o PDF.
# ---------------------------------------------------------------------

def test_data_extenso_pt_br_nao_depende_de_locale_do_so():
    """Bug real: agora.strftime('%A, %d de %B de %Y') lê o locale do
    processo - sem pt_BR instalado (caso comum de runner Linux do GitHub
    Actions), saía 'Monday, 19 de october de 2026'. _data_extenso_pt_br
    usa um mapa PT-BR fixo, nunca o locale do SO."""
    segunda = datetime(2026, 10, 19, 8, 0, tzinfo=TZ_SP)
    assert pdf_mod._data_extenso_pt_br(segunda) == "Segunda-feira, 19 de outubro de 2026"
    sabado = datetime(2026, 10, 24, 8, 0, tzinfo=TZ_SP)
    assert pdf_mod._data_extenso_pt_br(sabado) == "Sábado, 24 de outubro de 2026"


def test_titulo_pagina_interna_fica_abaixo_do_cabecalho():
    """Bug real: o título de página (BRASIL/EXTERIOR/EMPRESAS E SETORES,
    serifado 18pt) era desenhado perto demais do rodapé do cabeçalho
    navy - o topo dos glifos entrava na faixa navy e ficava invisível
    (texto navy-sobre-navy). Teste geométrico: calcula o topo real do
    texto (baseline + ascensão da fonte) e confere que fica abaixo do
    rodapé do cabeçalho, com folga mínima - nunca precisa rasterizar."""
    fonte, tamanho = pdf_mod.FONTE_TITULO_PAGINA_INTERNA
    ascensao = getAscent(fonte) / 1000 * tamanho
    topo_titulo = pdf_mod.Y_TITULO_PAGINA_INTERNA + ascensao
    base_cabecalho = pdf_mod.PAGINA_ALTURA - pdf_mod.ALTURA_CABECALHO - pdf_mod.ALTURA_FAIXA_AMBAR_CABECALHO
    folga_minima = 4
    assert topo_titulo <= base_cabecalho - folga_minima, (
        f"título entra {topo_titulo - (base_cabecalho - folga_minima):.1f}pt no cabeçalho navy"
    )


def test_card_indicador_nunca_desenha_variacao_e_barra_na_mesma_linha():
    """Bug real: variação% (esquerda) e barra_fmt/timestamp (direita)
    eram desenhados na MESMA linha (y) - colidiam quando o card era
    estreito (layout de 4 colunas da página EXTERIOR). Hoje são sempre
    empilhados; este teste trava essa garantia independente da largura
    do card, sem precisar rasterizar um PDF."""
    rec = _CanvasRecorder()
    pdf_mod._card_indicador(
        rec, _indicador("Petróleo Brent", preco=78.34, variacao_pct=0.64),
        x=0, y=0, largura=120, altura=pdf_mod.ALTURA_CARD_INDICADOR,
    )
    y_variacao = next(y for (_x, y, t) in rec.textos if "0,64%" in t)
    y_barra = next(y for (_x, y, t) in rec.textos if "horário de Brasília" in t)
    assert y_variacao != y_barra
