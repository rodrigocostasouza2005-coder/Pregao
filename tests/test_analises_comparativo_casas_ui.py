# -*- coding: utf-8 -*-
"""ANÁLISES › Empresas - Comparativo de Casas de Análise
(ui/analises_tab.py:render_comparativo_casas/_render_riscos_e_indicadores,
integra data/research/comparador.py:montar_relatorio_comparativo). Bare
mode (sem ScriptRunContext), mesmo padrão de
tests/test_analises_equity_research_ui.py.

Usa a função REAL montar_relatorio_comparativo (com listar_premissas/
linha_valuation/historico/cobertura_cruzada_casas mockados, mesmo padrão
de tests/test_research_comparador.py) pra garantir que o dict passado
pra UI tem sempre a forma real - nunca um fixture construído à mão que
pode divergir do formato de verdade. Cobre o fechamento do gap de
riscos/ROE/ROIC (2026-11-01): renderiza o DADO REAL quando disponível,
nunca esconde ROE só porque não há cobertura de research."""
from unittest.mock import MagicMock, patch

import data.research.comparador as comp_mod
import ui.analises_tab as analises_mod

_PREFS = {"formato_numerico": "BR"}


def _pub(casa, link, data_publicacao=None, recomendacao=None, preco_alvo=None, riscos=None):
    return {
        "link": link, "casa": casa, "titulo": "relatorio", "tickers": ["WEGE3"],
        "data_publicacao": data_publicacao, "extraido_em": None,
        "tipo_documento": None, "premissas": [], "projecoes": {},
        "recomendacao": recomendacao, "preco_alvo": preco_alvo,
        "modelo_extracao": "modelo-teste", "riscos": riscos or [],
    }


def _gerar_relatorio_real(publicacoes, linha_valuation_retorno=None):
    """Monta um relatorio de verdade via montar_relatorio_comparativo,
    só mockando as fontes externas (Supabase/yfinance/historico)."""
    with patch.object(comp_mod, "listar_premissas", return_value=publicacoes), \
         patch.object(comp_mod, "linha_valuation",
                       return_value=linha_valuation_retorno or {"roe": None, "alerta_qualidade": [], "consultado_em": None}), \
         patch.multiple(comp_mod.historico, historico_ticker=MagicMock(return_value=[]), mudancas_hoje=MagicMock(return_value=[])), \
         patch.object(comp_mod, "cobertura_cruzada_casas", return_value={
             "ticker": "WEGE3", "janela_dias": 30, "cobertura": [], "sem_cobertura": [], "divergencia": None,
         }):
        return comp_mod.montar_relatorio_comparativo("WEGE3")


def _capturar_render(relatorio):
    blocos = []

    def _coletar(texto, *_a, **_k):
        blocos.append(str(texto))

    col_mock = MagicMock()

    with patch.object(analises_mod, "_comparativo_casas_cacheado", return_value=relatorio), \
         patch.object(analises_mod.st, "markdown", side_effect=_coletar), \
         patch.object(analises_mod.st, "caption", side_effect=_coletar), \
         patch.object(analises_mod.st, "warning", side_effect=_coletar), \
         patch.object(analises_mod.st, "dataframe"), \
         patch.object(analises_mod.st, "columns", return_value=[col_mock, col_mock]), \
         patch.object(analises_mod.st, "expander") as expander_mock, \
         patch.object(analises_mod.st, "container") as container_mock:
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        expander_mock.return_value.__enter__ = lambda self: self
        expander_mock.return_value.__exit__ = lambda *a: False
        analises_mod.render_comparativo_casas("WEGE3", _PREFS)
    return "\n".join(blocos)


def test_banco_indisponivel_avisa_sem_lancar_excecao():
    relatorio = {"disponivel": False, "ticker": "WEGE3", "motivo": "banco indisponivel"}
    html_render = _capturar_render(relatorio)
    assert "indisponível" in html_render


def test_sem_cobertura_de_casas_ainda_assim_mostra_indicadores_adicionais():
    """Achado real (validação visual, 2026-11-01): ROE ficava escondido
    por um early-return quando nenhuma casa cobria o ticker, mesmo com
    indicadores_adicionais.disponivel=True - corrigido, nunca mais
    omitido só por falta de cobertura de research."""
    relatorio = _gerar_relatorio_real([], linha_valuation_retorno={"roe": 18.3, "alerta_qualidade": [], "consultado_em": None})
    assert relatorio["tabela_comparativa"] == []
    assert relatorio["indicadores_adicionais"]["disponivel"] is True

    html_render = _capturar_render(relatorio)
    assert "Nenhuma casa monitorada" in html_render
    assert "18,3" in html_render  # ROE real renderizado mesmo sem cobertura


def test_riscos_disponivel_lista_por_casa_com_fonte_e_data():
    publicacoes = [
        _pub("Genial Analisa", "https://x/1", data_publicacao="2026-10-20", recomendacao="COMPRA", preco_alvo=50.0,
             riscos=["alta de insumos pode comprimir margem"]),
        _pub("XP Investimentos", "https://x/2", data_publicacao="2026-10-18", recomendacao="MANTER"),
    ]
    relatorio = _gerar_relatorio_real(publicacoes)
    assert relatorio["riscos"]["disponivel"] is True

    html_render = _capturar_render(relatorio)
    assert "1 de 2 casa(s)" in html_render
    assert "alta de insumos pode comprimir margem" in html_render
    assert "Genial Analisa" in html_render


def test_riscos_indisponivel_mostra_motivo_honesto_nunca_inventa():
    publicacoes = [_pub("Genial Analisa", "https://x/1", data_publicacao="2026-10-20", recomendacao="COMPRA")]
    relatorio = _gerar_relatorio_real(publicacoes)
    assert relatorio["riscos"]["disponivel"] is False

    html_render = _capturar_render(relatorio)
    assert "nunca inventado" in html_render


def test_roic_sempre_mostrado_como_indisponivel_mesmo_com_roe_real():
    publicacoes = [_pub("Genial Analisa", "https://x/1", data_publicacao="2026-10-20", recomendacao="COMPRA")]
    relatorio = _gerar_relatorio_real(publicacoes, linha_valuation_retorno={"roe": 20.1, "alerta_qualidade": [], "consultado_em": None})

    html_render = _capturar_render(relatorio)
    assert "ROIC" in html_render and "não disponível" in html_render
    assert "20,1" in html_render


def test_riscos_mercado_deterministicos_aparecem_junto_do_roe():
    publicacoes = [_pub("Genial Analisa", "https://x/1", data_publicacao="2026-10-20", recomendacao="COMPRA")]
    relatorio = _gerar_relatorio_real(publicacoes, linha_valuation_retorno={
        "roe": 10.0, "alerta_qualidade": ["P/L negativo nos últimos 12 meses"], "consultado_em": None,
    })

    html_render = _capturar_render(relatorio)
    assert "P/L negativo nos últimos 12 meses" in html_render
