# -*- coding: utf-8 -*-
"""Regressao do bug real confirmado por Playwright (2026-11-13, evidencia
em docs/evidencias/revisao-interface-bloomberg-20261113/,
calendario_390_antes_bug_grade_mobile.png): a grade semanal do CALENDÁRIO
(ui/calendario_tab.py, MERCADO > Agenda - `st.columns(7)` por semana,
dentro de `st.container(key="cal_grade_area")`) caia na regra GENERICA de
mobile (style.css, `@media (max-width:640px)` perto do topo do arquivo,
empilha QUALQUER st.columns em 100% de largura) - a tela 390px virava uma
lista vertical de ~35 celulas cheias, perdendo o sentido de calendario
(dia da semana deixava de corresponder a posicao). Mesmo padrao do bug ja
corrigido antes pra `.st-key-mercado_ranking_lista` (ver comentario em
style.css, linha ~1222) - faltava a mesma excecao pra `cal_grade_area`.

Este teste NAO substitui a validacao real de browser (ja feita e
documentada com screenshot antes/depois em
docs/evidencias/revisao-interface-bloomberg-20261113/) - serve como rede
de seguranca rapida (sem precisar de Chromium/Streamlit rodando) pra
pegar regressao se alguem editar style.css e remover a excecao."""
import re
from pathlib import Path

STYLE_CSS = Path(__file__).resolve().parents[1] / "style.css"


def _css_texto() -> str:
    return STYLE_CSS.read_text(encoding="utf-8")


def test_cal_grade_area_mantem_colunas_lado_a_lado_no_mobile():
    css = _css_texto()
    padrao = re.compile(
        r"@media\s*\(max-width:\s*640px\)\s*\{[^@]*?"
        r"\.st-key-cal_grade_area\s+div\[data-testid=\"stHorizontalBlock\"\]\s*\{([^}]*)\}",
        re.DOTALL,
    )
    m = padrao.search(css)
    assert m, (
        "nao encontrei, dentro de um @media (max-width:640px), a regra "
        "'.st-key-cal_grade_area div[data-testid=\"stHorizontalBlock\"]' - "
        "sem ela a grade semanal do calendario empilha em 1 coluna no "
        "celular (ver docstring deste arquivo)."
    )
    corpo = m.group(1)
    assert re.search(r"flex-wrap\s*:\s*nowrap\s*!important", corpo), (
        "a regra precisa de 'flex-wrap: nowrap !important' pra vencer a "
        "regra generica de mobile (style.css, topo do arquivo) que "
        "empilha qualquer st.columns - mesma tecnica ja usada pro "
        "ranking (.st-key-mercado_ranking_lista)."
    )


def test_cal_grade_area_colunas_encolhem_sem_estourar_largura():
    css = _css_texto()
    padrao = re.compile(
        r"\.st-key-cal_grade_area\s+div\[data-testid=\"stHorizontalBlock\"\]\s*>\s*"
        r"div\[data-testid=\"stColumn\"\]\s*\{([^}]*)\}",
        re.DOTALL,
    )
    m = padrao.search(css)
    assert m, (
        "nao encontrei a regra das colunas-filhas de "
        "'.st-key-cal_grade_area div[data-testid=\"stHorizontalBlock\"]' - "
        "sem 'min-width:0', as 7 colunas recusam encolher abaixo do "
        "conteudo e estouram a largura da tela no celular."
    )
    corpo = m.group(1)
    assert re.search(r"min-width\s*:\s*0\s*!important", corpo)
