# -*- coding: utf-8 -*-
"""Redesign visual da subaba RADAR > ACOMPANHAMENTO (2026-10-23): só
formatação (alinhamento das posições cadastradas, rótulos compactos dos
indicadores de risco, hierarquia consistente entre "MINHAS POSIÇÕES" e
"ANÁLISE DE RISCO" - antes essa última usava a mesma classe de separador
de PÁGINA usada por "INTELIGÊNCIA DA WATCHLIST", peso visual maior que os
blocos irmãos no mesmo expander). Este arquivo prova que a reformatação
não perdeu nenhum dado (ticker, quantidade, preço médio, variação,
indicadores de risco continuam todos presentes) - zero mudança de
cálculo/regra de negócio, só HTML/CSS.

Bare mode (sem ScriptRunContext real), mesmo padrão de
tests/test_radar_tab_fontes_ui.py: col_info/col_remover são fakes
controlados aqui, já que st.columns(...) em bare mode não devolve nada
que capturemos de fora da função chamada."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.radar_tab as radar_tab_mod

_PREFS = {"formato_numerico": "BR", "watchlist": ["PETR4"]}


class _ColFake:
    def __init__(self):
        self.markdown_calls = []
        self.metric_calls = []

    def markdown(self, texto, **_k):
        self.markdown_calls.append(texto)

    def metric(self, label, value, **_k):
        self.metric_calls.append((label, value))

    def button(self, *_a, **_k):
        return False


def test_linha_posicao_alinha_ticker_quantidade_preco_e_lucro_em_colunas_fixas():
    """A linha de uma posição cadastrada precisa continuar trazendo TUDO
    que trazia antes (ticker, quantidade, preço médio, variação) - só a
    estrutura HTML virou colunas alinhadas (.acomp-posicao) em vez de uma
    frase corrida."""
    posicao = {"ticker": "PETR4", "quantidade": 100, "preco_medio": 30.0}
    valores_atuais = {"PETR4": {"lucro_pct": 12.5}}
    col_info, col_remover = _ColFake(), _ColFake()
    with patch.object(radar_tab_mod.st, "columns", return_value=(col_info, col_remover)):
        radar_tab_mod._linha_posicao_gerenciar("sub-teste", posicao, valores_atuais, _PREFS)

    html_linha = col_info.markdown_calls[0]
    assert "acomp-posicao" in html_linha
    assert "PETR4" in html_linha
    assert "100" in html_linha
    assert "30,00" in html_linha  # preco medio, formato BR
    assert "+12,50%" in html_linha
    assert "rq-alta" in html_linha  # lucro positivo destacado como alta, mesma convencao de VAR. DIA


def test_linha_posicao_sem_cotacao_nao_inventa_variacao():
    posicao = {"ticker": "VALE3", "quantidade": 10, "preco_medio": 60.0}
    col_info, col_remover = _ColFake(), _ColFake()
    with patch.object(radar_tab_mod.st, "columns", return_value=(col_info, col_remover)):
        radar_tab_mod._linha_posicao_gerenciar("sub-teste", posicao, {}, _PREFS)

    html_linha = col_info.markdown_calls[0]
    assert "variação indisponível" in html_linha
    assert "rq-alta" not in html_linha and "rq-baixa" not in html_linha


def test_secao_risco_calculado_usa_rotulos_compactos_e_janela_unica():
    """Antes cada metric() repetia "(periodo)" no proprio rotulo (so' em 2
    dos 3 indicadores, inconsistente) - agora o periodo aparece 1 vez so'
    no cabecalho da secao, e os rotulos ficam curtos/maiusculos, no mesmo
    padrao das colunas de tabela do resto do RADAR (ex: "VAR. DIA")."""
    info = {
        "concentracao_ativo": [{"nome": "PETR4", "peso_pct": 60.0}],
        "concentracao_setor": [{"nome": "Petróleo e Gás", "peso_pct": 60.0}],
        "limiar_concentracao_pct": 40.0,
        "periodo_historico": "6 meses",
        "volatilidade_anual_pct": 22.3,
        "drawdown_pct": -8.1,
        "maior_queda_diaria_pct": -3.4,
        "correlacao": None,
        "cenario_beta": None,
        "tickers_sem_preco": [],
        "tickers_sem_historico": [],
    }
    blocos = []
    colunas_metric = [_ColFake(), _ColFake(), _ColFake()]
    with patch.object(radar_tab_mod.st, "markdown", side_effect=lambda t, **_k: blocos.append(t)), \
         patch.object(radar_tab_mod.st, "columns", return_value=tuple(colunas_metric)):
        radar_tab_mod._secao_risco_calculado(info, _PREFS)

    texto = "\n".join(blocos)
    assert "janela de 6 meses" in texto  # periodo aparece 1 vez, no cabecalho
    assert "(6 meses)" not in texto  # nao mais repetido dentro de cada rotulo de metrica

    rotulos = [label for label, _valor in colunas_metric[0].metric_calls + colunas_metric[1].metric_calls + colunas_metric[2].metric_calls]
    assert rotulos == ["VOLATILIDADE ANUALIZADA", "DRAWDOWN MÁXIMO", "MAIOR QUEDA DIÁRIA"]


def test_appteste_acompanhamento_renderiza_posicao_e_risco_sem_excecao():
    """AppTest real (ScriptRunContext de verdade, @st.fragment executa o
    corpo normalmente - diferente do bare mode usado nos testes acima):
    prova que a tela inteira, com 1 posição cadastrada e risco calculável,
    roda ponta a ponta sem excecao e que os dados continuam todos
    presentes depois do redesign (ticker, preço médio, indicadores de
    risco, tabela de concentração)."""
    from streamlit.testing.v1 import AppTest

    script = '''
from unittest.mock import patch
import data.posicoes as posicoes_mod
import data.radar as radar_mod
import data.radar_quedas as radar_quedas_mod
import ui.radar_tab as radar_tab_mod

prefs = {"formato_numerico": "BR", "watchlist": ["PETR4"]}
usuario = {"sub": "sub-teste", "email": "teste@exemplo.com"}
posicoes = [{"ticker": "PETR4", "quantidade": 100, "preco_medio": 30.0}]
info_risco = {
    "carteira_cadastrada": True,
    "posicoes": [{"ticker": "PETR4", "lucro_pct": 20.0}],
    "concentracao_ativo": [{"nome": "PETR4", "peso_pct": 100.0}],
    "concentracao_setor": [{"nome": "Petróleo e Gás", "peso_pct": 100.0}],
    "limiar_concentracao_pct": 40.0,
    "periodo_historico": "6 meses",
    "volatilidade_anual_pct": 22.3,
    "drawdown_pct": -8.1,
    "maior_queda_diaria_pct": -3.4,
    "correlacao": None,
    "cenario_beta": None,
    "tickers_sem_preco": [],
    "tickers_sem_historico": [],
}
with patch.object(radar_quedas_mod, "alertas_periodo", return_value=[]), \\
     patch.object(posicoes_mod, "obter_posicoes", return_value=posicoes), \\
     patch.object(radar_mod, "risco_carteira", return_value=info_risco):
    radar_tab_mod.render_radar_acompanhamento(prefs, usuario)
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception

    textos = " ".join(m.value for m in at.markdown)
    assert "acomp-posicao" in textos and "PETR4" in textos and "30,00" in textos and "+20,00%" in textos
    assert "CONCENTRAÇÃO POR ATIVO" in textos

    rotulos = [m.label for m in at.metric]
    assert rotulos == ["VOLATILIDADE ANUALIZADA", "DRAWDOWN MÁXIMO", "MAIOR QUEDA DIÁRIA"]
    valores = [m.value for m in at.metric]
    assert valores == ["22,3%", "-8,1%", "-3,4%"]


def test_analise_de_risco_usa_mesmo_peso_visual_dos_blocos_irmaos():
    """"ANÁLISE DE RISCO" e "MINHAS POSIÇÕES" sao headings irmaos dentro
    do MESMO expander - antes um usava .rq-bloco e o outro .radar-separador
    (classe de divisor de PAGINA, usada em "INTELIGENCIA DA WATCHLIST").
    Agora os dois usam .rq-bloco."""
    blocos = []
    with patch.object(radar_tab_mod.st, "markdown", side_effect=lambda t, **_k: blocos.append(t)), \
         patch.object(radar_tab_mod, "_formulario_posicao"), \
         patch.object(radar_tab_mod.posicoes_mod, "obter_posicoes", return_value=[]), \
         patch.object(radar_tab_mod.radar, "risco_carteira", return_value={
             "carteira_cadastrada": False, "motivo": "sem posicao", "watchlist_tamanho": 1,
         }):
        radar_tab_mod._secao_risco(_PREFS, "sub-teste")

    texto = "\n".join(blocos)
    assert "<div class='rq-bloco'><span>MINHAS POSIÇÕES</span></div>" in texto
    assert "rq-bloco' style='margin-top:1.3rem;'><span>ANÁLISE DE RISCO</span>" in texto
    assert "radar-separador" not in texto
