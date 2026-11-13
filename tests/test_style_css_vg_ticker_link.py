# -*- coding: utf-8 -*-
"""Regressao do bug real de CSS confirmado por Playwright (2026-11-12,
evidencia completa em docs/evidencias/css-links-vg-ticker-link-20261112/):
todo link com classe .vg-ticker-link (ui/secoes.py, ui/setores_tab.py,
ui/visao_geral.py) renderizava AZUL e SUBLINHADO - estilo padrao de link
de navegador - em vez da cor do tema.

Causa raiz exata (capturada via getComputedStyle + varredura real de
document.styleSheets, nao suposta): o proprio Streamlit injeta uma regra
".st-emotion-cache-XXXXXX a" (hash de classe que MUDA a cada build/versao
- confirmado o valor atual ser "st-emotion-cache-1cnr85b", mas isso nao e'
garantia nenhuma pro futuro) com especificidade (0,1,1 - 1 classe + 1
elemento) MAIOR que a regra original do projeto pra .vg-ticker-link
(0,1,0 - so' 1 classe), vencendo a cascata mesmo vindo DEPOIS no arquivo
(especificidade bate ordem de declaracao). Fix: !important (nao e' so'
preferencia - a alternativa seria depender do hash do Streamlit, que e'
justamente o que nao pode ser feito, ver comentario em style.css).

Este teste NAO substitui a validacao real de browser (ja feita e
documentada com evidencia em docs/evidencias/css-links-vg-ticker-link-
20261112/: antes_fix_resultado.json, depois_fix_resultado.json,
screenshots desktop+iPad) - serve como rede de seguranca rapida (sem
precisar de Chromium/Streamlit rodando) pra pegar regressao se alguem
editar style.css e remover o !important ou trocar as cores, sem precisar
refazer a investigacao de browser inteira pra notar.
"""
import re
from pathlib import Path

import pytest

STYLE_CSS = Path(__file__).resolve().parents[1] / "style.css"


@pytest.fixture(scope="module")
def css_texto():
    return STYLE_CSS.read_text(encoding="utf-8")


def _bloco_regra(css_texto: str, seletor: str) -> str:
    """Extrai o corpo (dentro de { }) da PRIMEIRA regra cujo seletor e'
    exatamente `seletor` (ignora regras de outro seletor que so' CONTENHA
    o texto, ex: '.vg-ticker-link:hover' nao deve casar a busca por
    '.vg-ticker-link')."""
    padrao = re.compile(re.escape(seletor) + r"\s*\{([^}]*)\}")
    m = padrao.search(css_texto)
    assert m, f"regra '{seletor}' nao encontrada em style.css"
    return m.group(1)


def test_vg_ticker_link_normal_sem_azul_e_sem_sublinhado(css_texto):
    corpo = _bloco_regra(css_texto, ".vg-ticker-link")
    assert "!important" in corpo, (
        ".vg-ticker-link precisa de !important pra vencer a regra interna "
        "do Streamlit (.st-emotion-cache-* a, especificidade 0,1,1 > 0,1,0 "
        "da classe sozinha) - ver causa raiz no docstring deste arquivo."
    )
    assert re.search(r"text-decoration\s*:\s*none\s*!important", corpo), (
        "estado normal precisa remover o sublinhado padrao do navegador "
        "(requisito 2 do fix: text-decoration:none no estado normal)"
    )
    assert "var(--neutro)" in corpo, (
        "estado normal precisa usar a cor de texto clara do design system "
        "(--neutro), nao a cor azul do navegador nem uma cor inventada"
    )
    # nao pode sobrar a cor azul literal do bug nem --destaque fixo no
    # estado normal (requisito do fix: normal = --neutro, hover = --destaque)
    assert "rgb(61" not in corpo and "61,157,243" not in corpo.replace(" ", "")


def test_vg_ticker_link_hover_ambar(css_texto):
    corpo = _bloco_regra(css_texto, ".vg-ticker-link:hover")
    assert "!important" in corpo, (
        ".vg-ticker-link:hover tambem precisa de !important - o mesmo "
        "seletor interno do Streamlit tambem aplica no estado hover"
    )
    assert "var(--destaque)" in corpo, (
        "hover precisa usar a cor ambar do design system (--destaque, "
        "#FFA028) - requisito 4 do fix"
    )


def test_vg_ticker_link_nao_e_regra_generica_demais(css_texto):
    """Requisito 6 do fix: a correcao tem que ficar escopada a
    .vg-ticker-link, nunca virar um `a { ... }` generico que afetaria
    links externos (ex: GitHub na tela de apresentacao) ou outras
    classes de link do projeto (.rq-ticker, en ui/radar_tab.py)."""
    # nenhuma regra "a {" solta (elemento puro, sem classe/atributo) deve
    # existir sobrescrevendo color/text-decoration no arquivo inteiro
    for m in re.finditer(r"(?<![.\w-])a\s*\{([^}]*)\}", css_texto):
        corpo = m.group(1)
        assert "color" not in corpo and "text-decoration" not in corpo, (
            "achada uma regra 'a { ... }' generica tocando color/"
            "text-decoration - isso afetaria TODO link do app, inclusive "
            "externos, violando o escopo exigido (so' .vg-ticker-link)"
        )


def test_focus_visible_continua_com_indicador_visivel(css_texto):
    """Requisito 5 do fix: :focus-visible nao pode virar outline:none sem
    substituto - precisa continuar com indicador visivel (a regra global
    de :focus-visible, usada por todo o app, ja cobre isso)."""
    assert re.search(r":focus-visible\s*\{[^}]*outline\s*:\s*(?!none)", css_texto), (
        ":focus-visible precisa ter outline visivel (nao 'none' sem "
        "substituto) em algum lugar do style.css"
    )
    # nenhuma regra cancela o outline do foco sem por outro indicador no
    # lugar (ex.: 'a.vg-ticker-link:focus-visible { outline: none; }' sem
    # mais nada seria uma regressao de acessibilidade)
    for m in re.finditer(r"([^{};]+)\{([^}]*)\}", css_texto):
        seletor, corpo = m.group(1), m.group(2)
        if "focus-visible" in seletor or ":focus" in seletor:
            if re.search(r"outline\s*:\s*none", corpo):
                raise AssertionError(
                    f"regra de foco '{seletor.strip()}' zera o outline sem "
                    "substituto visivel - regressao de acessibilidade"
                )
