# -*- coding: utf-8 -*-
"""Painel novo "Divergência entre especialistas do Comitê"
(ui/coordenador_tab.py:_render_divergencia_comite) - expõe na tela um
cálculo que já existia em data/coordenador_central/consolidacao.py
(_divergencia_entre_analistas_comite, chave
`divergencias.entre_analistas_comite` do dict devolvido por
consolidar()) mas nunca tinha tela (achado de auditoria).

Conceito DIFERENTE do painel já existente "Divergência: comparador ×
memória de research" (cross_comparador_memoria - fonte externa vs.
memória de research interna, mesmo tipo de dado) - este aqui compara
os PRÓPRIOS especialistas do Comitê (market_researcher/
earnings_reviewer/valuation_comparables) entre si, na escala COMPRA/
VENDA/NEUTRO.

Mesmo padrão de captura de tests/test_calendario_ui.py e
tests/test_carteira_recomendada_tab_ui.py: patch.object(tab.st,
"markdown", ...) pra inspecionar o HTML gerado sem precisar de uma
sessão Streamlit de verdade - nenhuma função de consolidação é tocada
aqui (o dict de entrada já vem no formato que consolidar() devolve)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.coordenador_tab as tab


def _capturar(fn, *args, **kwargs):
    markdown_html = []
    with patch.object(tab.st, "markdown", side_effect=lambda html, **k: markdown_html.append(html)), \
         patch.object(tab.st, "expander") as mock_expander:
        mock_expander.return_value.__enter__ = lambda self: self
        mock_expander.return_value.__exit__ = lambda self, *a: False
        fn(*args, **kwargs)
        rotulos_expander = [c.args[0] for c in mock_expander.call_args_list]
    return "".join(markdown_html), rotulos_expander


def test_divergente_mostra_badge_divergente_contagem_e_resumo_real():
    divergencia = {
        "n_analistas_comparados": 2,
        "categorias": {"market_researcher": "COMPRA", "valuation_comparables": "VENDA"},
        "divergente": True,
        "resumo": "2 especialista(s) com recomendação comparável DIVERGEM entre si (market_researcher=COMPRA; valuation_comparables=VENDA).",
    }
    html, rotulos_expander = _capturar(tab._render_divergencia_comite, divergencia)
    assert "Divergência entre especialistas do Comitê" in rotulos_expander
    assert "DIVERGENTE" in html
    assert "CONVERGENTE" not in html
    assert "2 especialista(s)" in html
    # O resumo é exibido literalmente - nunca uma frase nova/recomposta.
    assert divergencia["resumo"] in html


def test_convergente_mostra_badge_convergente_e_resumo_real():
    divergencia = {
        "n_analistas_comparados": 3,
        "categorias": {"market_researcher": "COMPRA", "earnings_reviewer": "COMPRA", "valuation_comparables": "COMPRA"},
        "divergente": False,
        "resumo": "3 especialista(s) com recomendação comparável concordam em COMPRA (earnings_reviewer=COMPRA; market_researcher=COMPRA; valuation_comparables=COMPRA).",
    }
    html, rotulos_expander = _capturar(tab._render_divergencia_comite, divergencia)
    assert "Divergência entre especialistas do Comitê" in rotulos_expander
    assert "CONVERGENTE" in html
    assert "DIVERGENTE" not in html
    assert "3 especialista(s)" in html
    assert divergencia["resumo"] in html


def test_nunca_fabrica_texto_alem_do_que_consolidar_ja_calculou():
    """O painel só pode exibir os 4 campos que
    _divergencia_entre_analistas_comite() de fato devolve
    (n_analistas_comparados/categorias/divergente/resumo) - nunca um
    "veredito" de quem está certo (o Coordenador não tem esse
    mecanismo). Confere que nenhuma palavra de decisão/vencedor aparece
    e que o único texto de síntese é exatamente o `resumo` fornecido."""
    divergencia = {
        "n_analistas_comparados": 2,
        "categorias": {"market_researcher": "COMPRA", "valuation_comparables": "VENDA"},
        "divergente": True,
        "resumo": "2 especialista(s) com recomendação comparável DIVERGEM entre si (market_researcher=COMPRA; valuation_comparables=VENDA).",
    }
    html, _ = _capturar(tab._render_divergencia_comite, divergencia)
    for termo_proibido in ("veredito", "vencedor", "está certo", "correto", "melhor análise"):
        assert termo_proibido not in html.lower()


def test_sem_divergencia_comite_nao_renderiza_nada():
    """None (menos de 2 analistas comparáveis, ver consolidacao.py) não
    deve produzir painel vazio nem texto nenhum - degradação explícita,
    nunca um placeholder inventado."""
    html, rotulos_expander = _capturar(tab._render_divergencia_comite, None)
    assert html == ""
    assert rotulos_expander == []


def test_painel_cross_comparador_memoria_tem_rotulo_distinto_do_painel_do_comite():
    """Os dois painéis de divergência (cross_comparador_memoria x
    entre_analistas_comite) nunca podem compartilhar rótulo - são
    conceitos diferentes (fonte externa vs. memória de research interna,
    versus especialistas do Comitê entre si)."""
    consolidado = {
        "conclusao": [],
        "pontos_atencao": [],
        "evidencias": [],
        "visao_especialistas": {},
        "divergencias": {
            "cross_comparador_memoria": {
                "n_casas_comparadas": 1,
                "divergencias": [
                    {"casa": "BTG Pactual", "tipo": "qualitativa", "campo": "recomendacao", "comparador": "COMPRA", "memoria_research": "NEUTRO"},
                ],
            },
            "entre_analistas_comite": {
                "n_analistas_comparados": 2,
                "categorias": {"market_researcher": "COMPRA", "valuation_comparables": "VENDA"},
                "divergente": True,
                "resumo": "2 especialista(s) com recomendação comparável DIVERGEM entre si (market_researcher=COMPRA; valuation_comparables=VENDA).",
            },
        },
    }
    with patch.object(tab, "subtitulo") as mock_subtitulo:
        _, rotulos_expander = _capturar(tab._render_sintese_final, consolidado)
    assert "Divergência: comparador × memória de research (1)" in rotulos_expander
    assert "Divergência entre especialistas do Comitê" in rotulos_expander
    assert rotulos_expander.count("Divergência entre especialistas do Comitê") == 1


def test_divergencia_cross_comparador_memoria_com_valor_none_mostra_traco():
    """Regressão: consolidacao.py devolve `comparador`/`memoria_research`
    como None quando uma das 2 fontes não tem preço-alvo/recomendação
    para aquela casa (caso legítimo). O painel tem que mostrar "—",
    nunca a string literal "None"."""
    consolidado = {
        "conclusao": [], "pontos_atencao": [], "evidencias": [], "visao_especialistas": {},
        "divergencias": {
            "cross_comparador_memoria": {
                "n_casas_comparadas": 1,
                "divergencias": [
                    {"casa": "XP", "tipo": "qualitativa", "campo": "recomendacao",
                     "comparador": None, "memoria_research": None},
                ],
            },
        },
    }
    with patch.object(tab, "subtitulo"):
        html, _ = _capturar(tab._render_sintese_final, consolidado)
    assert "None" not in html
    assert "—" in html
