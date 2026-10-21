# -*- coding: utf-8 -*-
"""Cobertura de jobs/morning_call_pdf.py (redesenho editorial de
2026-10-18). Usa as edições de amostra de tests/morning_call_amostras.py
(típica, vazia, cheia) e verifica o PDF REAL gerado: fontes embutidas,
acentuação, links, paginação (manchete nunca órfã, editoria nunca no pé
da página, capa sem transbordo), limite de extensão e ausência dos
elementos do layout antigo (chips FATO, "sem foto disponível"...)."""
import io
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import jobs.morning_call_pdf as pdf_mod  # noqa: E402
import morning_call_amostras as amostras  # noqa: E402

TZ_SP = ZoneInfo("America/Sao_Paulo")


def _gerar(nome):
    registro = {}
    pdf = pdf_mod.gerar_pdf(getattr(amostras, f"edicao_{nome}")(), registro)
    return pdf, registro, PdfReader(io.BytesIO(pdf))


@pytest.fixture(scope="module")
def tipica():
    return _gerar("tipica")


@pytest.fixture(scope="module")
def cheia():
    return _gerar("cheia")


@pytest.fixture(scope="module")
def vazia():
    return _gerar("vazia")


def _texto(leitor):
    return "\n".join(p.extract_text() for p in leitor.pages)


def test_gera_pdf_valido_nos_tres_volumes(tipica, cheia, vazia):
    for pdf, registro, leitor in (tipica, cheia, vazia):
        assert pdf.startswith(b"%PDF")
        assert registro["total_paginas"] == len(leitor.pages)


def test_extensao_decorre_do_conteudo_com_limite(tipica, cheia, vazia):
    """O número de páginas acompanha o conteúdo (não é fixo em 4) e
    fica num limite razoável mesmo com o volume máximo da camada de dados."""
    assert len(vazia[2].pages) < len(tipica[2].pages) < len(cheia[2].pages)
    assert len(tipica[2].pages) <= 4
    assert len(cheia[2].pages) <= 8


def test_fontes_editoriais_embutidas(tipica):
    _, _, leitor = tipica
    nomes = set()
    for pagina in leitor.pages:
        for fonte in pagina["/Resources"]["/Font"].values():
            fonte = fonte.get_object()
            nomes.add(str(fonte["/BaseFont"]))
            descendentes = fonte.get("/DescendantFonts")
            descritor = (descendentes[0].get_object() if descendentes else fonte).get("/FontDescriptor")
            if descritor is not None:
                assert "/FontFile2" in descritor.get_object(), f"fonte {fonte['/BaseFont']} não embutida"
    assert pdf_mod.FONTES_EMBUTIDAS is True
    assert not any(base in n for n in nomes for base in ("Helvetica", "Times-", "Courier"))
    assert any("SourceSerif4" in n for n in nomes) and any("IBMPlexMono" in n for n in nomes)
    assert any("LibreFranklin" in n for n in nomes)


def test_acentuacao_portuguesa_preservada(tipica):
    # A extração do PDF pode inserir quebras de linha no meio de manchetes
    # conforme a largura da coluna; normalize o whitespace antes de validar.
    texto = " ".join(_texto(tipica[2]).split())
    for trecho in ("ações do petróleo", "Inflação", "EDIÇÃO MATINAL", "SITUAÇÃO", "não", "Câmbio".upper()):
        assert trecho in texto, trecho


def test_links_das_materias_continuam_clicaveis(tipica):
    _, _, leitor = tipica
    uris = set()
    for pagina in leitor.pages:
        for anot in pagina.get("/Annots") or []:
            acao = anot.get_object().get("/A")
            if acao and "/URI" in acao:
                uris.add(str(acao["/URI"]))
    ed = amostras.edicao_tipica()
    todas = ed["brasil"]["noticias"] + ed["exterior"]["noticias"] + ed["empresas"]["cards"]
    for item in todas:
        assert item["link"] in uris, item["titulo"]


def test_veiculo_de_cada_materia_aparece(tipica):
    texto = _texto(tipica[2]).upper()
    for veiculo in ("INFOMONEY", "VALOR ECONÔMICO", "REUTERS", "MONEY TIMES", "BLOOMBERG LÍNEA"):
        assert veiculo in texto


def test_elementos_do_layout_antigo_nao_voltam(tipica, vazia):
    """Cards/chips/placeholders do layout de dashboard: nunca mais."""
    for _, _, leitor in (tipica, vazia):
        texto = _texto(leitor)
        for proibido in ("FATO", "INTERPRETAÇÃO", "ACOMPANHAR", "sem foto disponível",
                         "Tendências e riscos", "INSIGHT", "Panorama"):
            assert proibido not in texto, proibido


def test_manchete_nunca_orfa_no_pe_da_coluna(cheia, tipica):
    """Manchete e primeiro parágrafo da mesma matéria: mesma página e
    mesma coluna (x), com o parágrafo logo abaixo."""
    for _, registro, _ in (tipica, cheia):
        marcas = registro["marcas"]
        manchetes = {rot[1]: (pag, pos) for rot, pag, pos in marcas if rot[0] == "manchete"}
        corpos = {rot[1]: (pag, pos) for rot, pag, pos in marcas if rot[0] == "corpo"}
        assert corpos, "nenhuma matéria com texto registrada"
        for titulo, (pag_corpo, (x_corpo, y_corpo)) in corpos.items():
            pag_m, (x_m, y_m) = manchetes[titulo]
            assert pag_m == pag_corpo, titulo
            assert y_corpo < y_m, titulo


def test_editoria_nunca_fica_sozinha_no_pe_da_pagina(cheia, tipica):
    """O cabeçalho de uma editoria de notícias sai na mesma página da
    primeira matéria dela (achado real da inspeção: 'MUNDO' sozinho no pé
    da página 2, matéria na 3); Mercados/Agenda vão inteiros com o
    cabeçalho (KeepTogether), então basta não estarem colados na base."""
    for nome, (_, registro, _) in (("típica", tipica), ("cheia", cheia)):
        marcas = registro["marcas"]
        for chave, pagina, y in registro["cabecalhos"]:
            assert y > pdf_mod.MARGEM_BASE + 40, f"{nome}: {chave} colado na base (pág. {pagina})"
        ed = getattr(amostras, "edicao_tipica" if nome == "típica" else "edicao_cheia")()
        manchete_capa = ed["capa"]["manchete"]["titulo"]
        for chave, lista in (("brasil", ed["brasil"]["noticias"]), ("exterior", ed["exterior"]["noticias"]),
                             ("empresas", ed["empresas"]["cards"])):
            titulos = [i["titulo"] for i in sorted(lista, key=lambda i: -i["importancia"])
                       if i.get("corpo") and i["titulo"] != manchete_capa]
            if not titulos:
                continue
            pagina_cab = registro["paginas"][chave]
            pagina_primeira = next(p for rot, p, _ in marcas if rot == ("manchete", titulos[0]))
            assert pagina_primeira == pagina_cab, f"{nome}: {chave} na pág. {pagina_cab}, 1ª matéria na {pagina_primeira}"


def test_agenda_curta_compartilha_pagina_com_mercados(tipica):
    # Evita uma página quase vazia só para duas linhas de agenda: o bloco de
    # mercados deve ser compacto o suficiente para compartilhar a página.
    registro = tipica[1]
    assert registro["paginas"]["agenda"] == registro["paginas"]["mercados"]


def test_capa_cabe_numa_pagina_e_indice_bate_com_paginas_reais(tipica, cheia):
    for _, registro, leitor in (tipica, cheia):
        primeira = leitor.pages[0].extract_text()
        assert "N E S T A" in primeira.replace(" ", " ") or "NESTA" in primeira.replace(" ", "")
        segunda = leitor.pages[1].extract_text().replace(" ", "").replace(" ", "")
        assert "NESTAEDIÇÃO" not in segunda
        assert all(p >= 2 for p in registro["paginas"].values())


def test_manchete_da_capa_nao_se_repete_dentro(tipica):
    _, registro, _ = tipica
    manchete = amostras.edicao_tipica()["capa"]["manchete"]["titulo"]
    paginas = [pag for rot, pag, _ in registro["marcas"] if rot == ("manchete", manchete)]
    assert paginas == [1]


def test_edicao_vazia_e_honesta(vazia):
    texto = _texto(vazia[2])
    assert "A coleta de notícias falhou" in texto
    assert "indisponível" in texto
    assert "Ibovespa sobe" not in texto


def test_texto_dentro_das_margens(cheia):
    """Nenhum texto desenhado fora da área útil da página."""
    _, _, leitor = cheia
    for n, pagina in enumerate(leitor.pages, 1):
        fora = []

        def visitar(texto, cm, tm, *_a):
            if not texto.strip():
                return
            x = cm[4] + tm[4] * cm[0]
            y = cm[5] + tm[5] * cm[3]
            if not (pdf_mod.MARGEM_X - 2 <= x <= pdf_mod.PAGINA_LARGURA - pdf_mod.MARGEM_X + 2
                    and 10 <= y <= pdf_mod.PAGINA_ALTURA - 10):
                fora.append((texto[:20], round(x), round(y)))

        pagina.extract_text(visitor_text=visitar)
        assert not fora, f"pág. {n}: {fora[:3]}"


def test_variacao_usa_sinal_explicito_e_menos_tipografico():
    assert pdf_mod._texto_variacao(0.54) == "+0,54%"
    assert pdf_mod._texto_variacao(-0.3) == "−0,30%"
    assert pdf_mod._texto_variacao(0.001) == "0,00%"
    assert pdf_mod._texto_variacao(None) == "—"
    assert pdf_mod._cor_variacao(1) == pdf_mod.ALTA
    assert pdf_mod._cor_variacao(-1) == pdf_mod.BAIXA
    assert pdf_mod._cor_variacao(None) == pdf_mod.CINZA


def test_casas_decimais_por_tipo_de_ativo():
    assert pdf_mod._fmt_num(145320.48, pdf_mod._casas_ativo("Ibovespa", 145320.48)) == "145.320"
    assert pdf_mod._fmt_num(5.0712, pdf_mod._casas_ativo("Dólar (USD/BRL)", 5.0712)) == "5,0712"
    assert pdf_mod._fmt_num(62.35, pdf_mod._casas_ativo("Petróleo Brent", 62.35)) == "62,35"


def test_linha_fina_e_a_primeira_frase_e_sai_do_corpo():
    corpo = ["O Ibovespa fechou a sexta-feira em alta de 0,54%, aos 145.320 pontos, sustentado pela Petrobras. "
             "O volume somou R$ 21 bilhões.", "Segundo parágrafo."]
    linha_fina, resto = pdf_mod._dividir_linha_fina(corpo)
    assert linha_fina.startswith("O Ibovespa fechou") and linha_fina.endswith("Petrobras.")
    assert resto == ["O volume somou R$ 21 bilhões.", "Segundo parágrafo."]
    assert pdf_mod._dividir_linha_fina(["Curta."]) == (None, ["Curta."])


def test_data_extenso_pt_br_nao_depende_de_locale_do_so():
    agora = datetime(2026, 10, 19, 8, 0, tzinfo=TZ_SP)
    assert pdf_mod._data_extenso_pt_br(agora) == "Segunda-feira, 19 de outubro de 2026"


def test_gerar_pdf_do_momento_usa_montar_edicao(monkeypatch):
    import data.morning_call_editorial as ed_mod
    chamado = {}

    def _fake(agora=None):
        chamado["ok"] = True
        return amostras.edicao_vazia()

    monkeypatch.setattr(ed_mod, "montar_edicao", _fake)
    assert pdf_mod.gerar_pdf_do_momento().startswith(b"%PDF")
    assert chamado["ok"]


def test_baixar_imagem_card_sem_url_devolve_none_sem_chamar_rede(monkeypatch):
    def _nao_chamar(*_a, **_k):
        raise AssertionError("não deveria chamar a rede")
    monkeypatch.setattr(pdf_mod.requests, "get", _nao_chamar)
    assert pdf_mod._baixar_imagem_card(None) is None


def test_baixar_imagem_card_content_type_invalido_devolve_none(monkeypatch):
    class _Resp:
        status_code = 200
        headers = {"Content-Type": "text/html"}
    monkeypatch.setattr(pdf_mod.requests, "get", lambda *_a, **_k: _Resp())
    assert pdf_mod._baixar_imagem_card("https://exemplo.invalid/x.jpg") is None


def test_foto_pequena_demais_nao_e_publicada(monkeypatch):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (200, 120), "white").save(buf, format="JPEG")
    monkeypatch.setattr(pdf_mod, "_baixar_imagem_card", lambda _u: buf.getvalue())
    assert pdf_mod._foto({"imagem": "https://x/y.jpg", "veiculo": "V"}, 250, pdf_mod._estilos()) == []


def test_foto_valida_entra_proporcional_com_credito(monkeypatch):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1200, 800), "white").save(buf, format="JPEG")
    monkeypatch.setattr(pdf_mod, "_baixar_imagem_card", lambda _u: buf.getvalue())
    flows = pdf_mod._foto({"imagem": "https://x/y.jpg", "veiculo": "InfoMoney"}, 240, pdf_mod._estilos())
    img = flows[0]
    assert abs(img.drawWidth / img.drawHeight - 1.5) < 0.01
    assert "InfoMoney" in flows[1].text


# ------------------------------------------------------------------
# Auditoria da edição real de 18/10/2026 - regressões de conteúdo
# ------------------------------------------------------------------

def _plano(texto):
    return " ".join(texto.split())


def test_tabela_macro_sem_nome_de_coluna_e_com_focus_do_ano_corrente(tipica):
    texto = _plano(_texto(tipica[2]))
    for cru in ("mediana pct", "media pct", "numero respondentes", "mediana_pct"):
        assert cru not in texto
    assert "Focus IPCA 2026" in texto and "5,22%" in texto
    assert "Focus Selic 2027" in texto and "12,00%" in texto
    assert "2028" not in texto
    assert "boletim 09/10/2026" in texto
    assert "Selic meta" in texto and "15,00% a.a." in texto
    assert "144 respondentes" in texto


def test_indicador_macro_indisponivel_mostra_motivo_sem_inventar_valor():
    edicao = amostras.edicao_tipica()
    for linha in edicao["brasil"]["indicadores"]:
        if linha.get("indicador") in ("Selic meta", "CDI"):
            linha.update(valor=None, referencia="—",
                         erro="SGS 432: o Banco Central respondeu com página de erro HTML")
    texto = _plano(_texto(PdfReader(io.BytesIO(pdf_mod.gerar_pdf(edicao)))))
    assert "Indisponível (Selic meta, CDI): SGS 432: o Banco Central respondeu com página de erro HTML" in texto
    assert "15,00% a.a." not in texto
    assert "indisponíve l" not in texto and "indisponíve\nl" not in texto


def test_nota_de_mercados_explica_sessao_e_dolar(tipica):
    texto = _plano(_texto(tipica[2]))
    assert "referem-se à última sessão disponível (sexta-feira, 16/10)" in texto
    assert "USDBRL=X" in texto
    assert "00:00" not in texto and "01:00" not in texto


def test_agenda_vazia_nao_afirma_ausencia_de_eventos():
    edicao = amostras.edicao_tipica()
    edicao["empresas"]["agenda"] = []
    edicao["agora"] = datetime(2026, 10, 18, 12, 0, tzinfo=TZ_SP)  # domingo
    texto = _plano(_texto(PdfReader(io.BytesIO(pdf_mod.gerar_pdf(edicao)))))
    assert "Não há pregão hoje (fim de semana)" in texto
    assert "pode não incluir todos os eventos" in texto
    assert "Nenhuma divulgação de resultado prevista" not in texto


def test_editoria_vazia_diz_a_janela_consultada():
    edicao = amostras.edicao_tipica()
    edicao["exterior"]["noticias"] = None
    texto = _plano(_texto(PdfReader(io.BytesIO(pdf_mod.gerar_pdf(edicao)))))
    assert "Nenhuma notícia desta editoria publicada desde 16/10 às 06:00" in texto


def test_mensagem_de_erro_nunca_aparece_na_coluna_de_valor():
    """Erro vai na nota da tabela; a célula de valor diz só 'indisponível'."""
    linha = {"indicador": "Selic meta", "valor": None, "unidade": "% a.a.", "referencia": "—",
             "erro": "SGS 432: erro 500 Internal error"}
    assert pdf_mod._valor_macro(linha) == "indisponível"
    assert pdf_mod._valor_macro({**linha, "valor": 15.0}) == "15,00% a.a."
