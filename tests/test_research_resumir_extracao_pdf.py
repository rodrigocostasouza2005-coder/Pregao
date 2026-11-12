# -*- coding: utf-8 -*-
"""Extracao de texto de PDF em data/research/resumir.py (Agente C,
2026-11-12, item 1 do pedido de processamento): cadeia pypdf -> pdfplumber
-> OCR. Os 2 primeiros sao exercitados com PDF REAL (gerado via
reportlab, ja' dependencia do projeto) - nao mock. O caminho de OCR e'
exercitado so' com mock (ver limitacao honesta documentada em
_ocr_disponivel: este ambiente nao tem o binario Tesseract instalado).

Uso: pytest tests/test_research_resumir_extracao_pdf.py"""
import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.resumir as resumir_mod


def _pdf_com_texto_real(texto: str) -> bytes:
    """PDF de verdade (nao mock) com `texto` desenhado numa pagina -
    reportlab ja' e' dependencia do projeto (jobs/morning_call_pdf.py)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 700, texto)
    c.save()
    return buf.getvalue()


def _pdf_sem_texto() -> bytes:
    """PDF de verdade, mas SEM nenhum conteudo de texto (pagina em
    branco) - simula o caso 'PDF so' de imagem escaneada' sem precisar
    rasterizar nada: nenhum extrator de texto acha nada, como aconteceria
    com um PDF de imagem."""
    import pypdf
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------
# Extracao real (PDF de verdade, sem mock) - cobertura real, nao fingida
# ---------------------------------------------------------------------

def test_pypdf_extrai_texto_real_de_pdf_real():
    pdf = _pdf_com_texto_real("Texto de teste PETR4 relatorio real.")
    texto = resumir_mod._extrair_texto_pdf_pypdf(pdf)
    assert texto is not None
    assert "PETR4" in texto


def test_pdfplumber_extrai_texto_real_de_pdf_real():
    pdf = _pdf_com_texto_real("Texto de teste VALE3 relatorio real.")
    texto = resumir_mod._extrair_texto_pdf_pdfplumber(pdf)
    assert texto is not None
    assert "VALE3" in texto


def test_pypdf_retorna_none_pra_pdf_sem_texto():
    assert resumir_mod._extrair_texto_pdf_pypdf(_pdf_sem_texto()) is None


def test_pdfplumber_retorna_none_pra_pdf_sem_texto():
    assert resumir_mod._extrair_texto_pdf_pdfplumber(_pdf_sem_texto()) is None


def test_extratores_nunca_lancam_excecao_em_conteudo_invalido():
    lixo = b"isto nao e' um pdf de verdade"
    assert resumir_mod._extrair_texto_pdf_pypdf(lixo) is None
    assert resumir_mod._extrair_texto_pdf_pdfplumber(lixo) is None


# ---------------------------------------------------------------------
# Cadeia completa _extrair_texto_pdf: pypdf -> pdfplumber -> OCR
# ---------------------------------------------------------------------

def test_cadeia_usa_pypdf_quando_funciona_sem_tentar_os_outros():
    pdf = _pdf_com_texto_real("Nota real ITUB4.")
    with patch.object(resumir_mod, "_extrair_texto_pdf_pdfplumber") as plumber_mock, \
         patch.object(resumir_mod, "_ocr_disponivel") as ocr_disp_mock:
        texto, motivo = resumir_mod._extrair_texto_pdf(pdf)
    assert texto is not None
    assert "ITUB4" in texto
    assert motivo is None
    plumber_mock.assert_not_called()
    ocr_disp_mock.assert_not_called()


def test_cadeia_cai_pro_pdfplumber_quando_pypdf_nao_acha_nada():
    with patch.object(resumir_mod, "_extrair_texto_pdf_pypdf", return_value=None), \
         patch.object(resumir_mod, "_extrair_texto_pdf_pdfplumber", return_value="texto via pdfplumber") as plumber_mock:
        texto, motivo = resumir_mod._extrair_texto_pdf(b"qualquer-coisa")
    assert texto == "texto via pdfplumber"
    assert motivo is None
    plumber_mock.assert_called_once()


def test_cadeia_sem_ocr_disponivel_reporta_motivo_especifico():
    """Nenhum dos 2 extratores reais acha texto, OCR nao esta disponivel
    neste ambiente (caso real deste repositorio, ver _ocr_disponivel) -
    motivo precisa dizer explicitamente que OCR estava indisponivel, nao
    so' 'nao foi possivel ler'."""
    with patch.object(resumir_mod, "_extrair_texto_pdf_pypdf", return_value=None), \
         patch.object(resumir_mod, "_extrair_texto_pdf_pdfplumber", return_value=None), \
         patch.object(resumir_mod, "_ocr_disponivel", return_value=False):
        texto, motivo = resumir_mod._extrair_texto_pdf(b"pdf-escaneado-fake")
    assert texto is None
    assert "OCR indisponivel" in motivo


def test_cadeia_com_ocr_disponivel_mockado_tenta_ocr_e_usa_resultado():
    """OCR real nao e' validavel neste ambiente (sem Tesseract instalado -
    ver limitacao documentada) - este teste mocka _ocr_disponivel=True e
    _extrair_texto_pdf_ocr pra confirmar que a CADEIA (orquestracao) esta
    certa, nao que o OCR de verdade funciona."""
    with patch.object(resumir_mod, "_extrair_texto_pdf_pypdf", return_value=None), \
         patch.object(resumir_mod, "_extrair_texto_pdf_pdfplumber", return_value=None), \
         patch.object(resumir_mod, "_ocr_disponivel", return_value=True), \
         patch.object(resumir_mod, "_extrair_texto_pdf_ocr", return_value="texto via ocr") as ocr_mock:
        texto, motivo = resumir_mod._extrair_texto_pdf(b"pdf-escaneado-fake")
    assert texto == "texto via ocr"
    assert motivo is None
    ocr_mock.assert_called_once()


def test_cadeia_com_ocr_disponivel_mas_sem_resultado_reporta_motivo_final():
    with patch.object(resumir_mod, "_extrair_texto_pdf_pypdf", return_value=None), \
         patch.object(resumir_mod, "_extrair_texto_pdf_pdfplumber", return_value=None), \
         patch.object(resumir_mod, "_ocr_disponivel", return_value=True), \
         patch.object(resumir_mod, "_extrair_texto_pdf_ocr", return_value=None):
        texto, motivo = resumir_mod._extrair_texto_pdf(b"pdf-ilegivel-fake")
    assert texto is None
    assert "OCR" in motivo


# ---------------------------------------------------------------------
# _ocr_disponivel: checagem ativa (nao so' "o import funcionou")
# ---------------------------------------------------------------------

def test_ocr_indisponivel_neste_ambiente_de_verdade():
    """SEM nenhum mock - confirma o estado REAL deste ambiente (nao tem
    pytesseract instalado, nem o binario Tesseract) - documentacao viva
    da limitacao, nunca um mock escondendo a realidade."""
    resumir_mod._ocr_disponivel_cache = None  # reseta cache de 1-checagem-por-processo
    assert resumir_mod._ocr_disponivel() is False


def test_ocr_disponivel_usa_cache_apos_1a_checagem():
    resumir_mod._ocr_disponivel_cache = None
    primeira = resumir_mod._ocr_disponivel()
    resumir_mod._ocr_disponivel_cache = not primeira  # força um valor diferente no "cache"
    assert resumir_mod._ocr_disponivel() == (not primeira)  # confirma que leu do cache, nao re-checou
    resumir_mod._ocr_disponivel_cache = None  # limpa pro proximo teste


def test_ocr_falso_quando_pytesseract_importa_mas_binario_nao_responde():
    """Caso real documentado: pytesseract PODE importar sem erro mesmo
    sem o binario Tesseract instalado - so' falha na hora de chamar
    get_tesseract_version(). Simula esse caso especifico via mock."""
    resumir_mod._ocr_disponivel_cache = None
    pytesseract_falso = type(sys)("pytesseract")
    pytesseract_falso.get_tesseract_version = lambda: (_ for _ in ()).throw(EnvironmentError("tesseract nao encontrado"))
    with patch.dict(sys.modules, {"pytesseract": pytesseract_falso}):
        assert resumir_mod._ocr_disponivel() is False
    resumir_mod._ocr_disponivel_cache = None


def test_extrair_texto_pdf_ocr_retorna_none_sem_ocr_disponivel():
    with patch.object(resumir_mod, "_ocr_disponivel", return_value=False):
        assert resumir_mod._extrair_texto_pdf_ocr(b"qualquer-coisa") is None


# ---------------------------------------------------------------------
# obter_texto_relatorio: integra a cadeia no fluxo de download real
# ---------------------------------------------------------------------

def test_obter_texto_relatorio_pdf_usa_motivo_da_cadeia(monkeypatch):
    """O motivo retornado quando PDF falha precisa vir exatamente da
    cadeia _extrair_texto_pdf (nao mais um texto fixo generico) - garante
    que a mensagem distinta de OCR indisponivel chega até quem chama
    obter_texto_relatorio."""
    class _RespostaFalsa:
        status_code = 200
        headers = {"Content-Type": "application/pdf"}
        content = b"pdf-fake"

        def raise_for_status(self):
            return None

    with patch.object(resumir_mod, "permitido", return_value=True), \
         patch.object(resumir_mod.cffi_requests, "get", return_value=_RespostaFalsa()), \
         patch.object(resumir_mod, "_extrair_texto_pdf", return_value=(None, "motivo customizado de teste")):
        texto, motivo = resumir_mod.obter_texto_relatorio("https://exemplo.com/relatorio.pdf")

    assert texto is None
    assert motivo == "motivo customizado de teste"
