# -*- coding: utf-8 -*-
"""Teste de UI (sem sessao Streamlit real) do modulo novo
ui/carteira_recomendada_tab.py - correcao de inconsistencia visual
(2026-11-13): antes, app.py tinha um render MINIMO direto (st.title/
st.write/st.expander puro) sem nenhum traco do design system - a unica
area de conteudo do app sem classe_sinal/numero_financeiro_html/
painel-titulo (ver docstring do modulo). Mesmo padrao de captura de
tests/test_calendario_ui.py: patch.object(st, "markdown", ...) pra
inspecionar o HTML gerado sem precisar de uma sessao Streamlit de
verdade. Shape do dado (`carteira`) e' o mesmo documentado em
data/carteira_recomendada.py - nenhuma funcao de calculo tocada aqui."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.carteira_recomendada_tab as tab

PREFS = {"formato_numerico": "BR"}


def _capturar(fn, *args, **kwargs):
    """Intercepta st.markdown (conteudo HTML) e st.warning/st.info
    (avisos) na mesma chamada - cobre as 3 formas que o modulo usa pra
    exibir coisa na tela."""
    markdown_html = []
    avisos = []
    infos = []
    with patch.object(tab.st, "markdown", side_effect=lambda html, **k: markdown_html.append(html)), \
         patch.object(tab.st, "warning", side_effect=lambda t, **k: avisos.append(t)), \
         patch.object(tab.st, "info", side_effect=lambda t, **k: infos.append(t)), \
         patch.object(tab.st, "expander") as mock_expander:
        mock_expander.return_value.__enter__ = lambda self: self
        mock_expander.return_value.__exit__ = lambda self, *a: False
        fn(*args, **kwargs)
    return "".join(markdown_html), avisos, infos


def _item(ticker="PETR4", sinal="COMPRA", confianca="ALTA", peso=15.0, preco_ref=36.52,
          preco_alvo=44.10, retorno_base=20.8, setor="Petróleo e Gás"):
    return {
        "ticker": ticker, "setor": setor, "peso_pct": peso,
        "justificativa": "Sinal do Comitê.", "preco_referencia": preco_ref,
        "preco_referencia_em": None, "preco_alvo": preco_alvo,
        "metodo_preco_alvo": "consenso dos especialistas do Comitê",
        "cenarios": ({
            "conservador": {"preco": preco_ref, "retorno_pct": 0.0},
            "base": {"preco": preco_alvo, "retorno_pct": retorno_base},
            "otimista": {"preco": preco_alvo, "retorno_pct": retorno_base},
            "aviso": "aviso de cenário condicional",
        } if preco_alvo is not None else None),
        "tese": "Tese resumida.", "riscos": ["Risco A"],
        "criterio_saida": "Critério de saída.", "data_revisao": "2026-12-13",
        "liquidez": {"volume": 1_000_000, "consultado_em": None},
        "confianca_comite": confianca, "sinal_comite": sinal, "score_comite": 8,
        "origem_analise_id": "abc", "origem_analise_em": None, "historico_alteracao": [],
    }


def _carteira(itens=None, avisos=None):
    itens = itens if itens is not None else [_item()]
    diversificacao = {}
    for item in itens:
        if item.get("setor"):
            diversificacao[item["setor"]] = diversificacao.get(item["setor"], 0.0) + item["peso_pct"]
    resumo = {
        "n_ativos": len(itens), "peso_total_pct": sum(i["peso_pct"] for i in itens),
        "diversificacao_setorial": diversificacao, "setores_cobertos": len(diversificacao),
        "concentracao_maxima_pct": 15.0, "horizonte": "médio/longo prazo", "correlacao": None,
        "cenario_macro": {},
    }
    return {
        "gerado_em": "2026-11-13T09:00:00-03:00", "criterios": {}, "itens": itens,
        "resumo": resumo if itens else None,
        "avisos": avisos if avisos is not None else ["Carteira informativa - não garante rentabilidade."],
        "fonte_universo": "Comitê de Investimentos.", "universo_consultado": 10, "universo_elegivel": len(itens),
    }


def test_visao_geral_mostra_tabela_densa_com_sinal_e_preco_sem_json_cru():
    html, avisos, infos = _capturar(tab.render_visao_geral, _carteira(), PREFS)
    assert "PETR4" in html
    assert "COMPRA" in html
    assert "cart-badge-alta" in html, "sinal COMPRA precisa usar a classe de cor 'alta' do design system"
    assert "R$ 36,52" in html and "R$ 44,10" in html
    assert "+20,8%" in html
    assert avisos, "avisos do shape de dado precisam virar st.warning (nunca somem)"


def test_visao_geral_sinal_venda_usa_cor_de_baixa():
    html, _, _ = _capturar(tab.render_visao_geral, _carteira(itens=[_item(ticker="MGLU3", sinal="VENDA")]), PREFS)
    assert "cart-badge-baixa" in html


def test_visao_geral_sem_itens_mostra_info_e_nao_quebra():
    html, _, infos = _capturar(tab.render_visao_geral, _carteira(itens=[]), PREFS)
    assert infos, "carteira vazia precisa de st.info explícito (nunca tela em branco)"
    assert "PETR4" not in html


def test_visao_geral_preco_alvo_ausente_mostra_traco_sem_quebrar():
    item_sem_alvo = _item(preco_alvo=None, retorno_base=None)
    html, _, _ = _capturar(tab.render_visao_geral, _carteira(itens=[item_sem_alvo]), PREFS)
    assert "—" in html


def test_visao_geral_cenario_macro_mostra_indicadores_do_shape_atual():
    """Regressão (2026-11-14): `_resumo` lia `cenario_macro` como se fosse
    o shape ANTIGO (DataFrame indexado por coluna, pré-PR #313, chaves
    'selic_meta'/'cdi'/'focus_ipca') - desde que data/carteira_recomendada.py
    passou a usar _contexto_macro() (PR #313), o shape real é
    {nome_indicador: {"valor","unidade","referencia","detalhe","erro"}}
    com chaves como 'Selic meta'/'CDI'/'Focus IPCA 2026'. A seção CENÁRIO
    MACRO nunca aparecia na tela, sem nenhum erro visível - nenhuma
    fixture anterior populava `cenario_macro` de verdade (ver `_carteira()`,
    que usa `{}`), por isso nenhum teste pegava."""
    carteira = _carteira()
    carteira["resumo"]["cenario_macro"] = {
        "Selic meta": {"valor": 13.75, "unidade": "% a.a.", "referencia": "18ª reunião do Copom",
                        "detalhe": None, "erro": None},
        "CDI": {"valor": 13.65, "unidade": "% a.a.", "referencia": "16/11/2026",
                 "detalhe": None, "erro": None},
        "Focus IPCA 2026": {"valor": None, "unidade": "%", "referencia": None,
                              "detalhe": None, "erro": "Boletim Focus sem dado nesta execução"},
    }
    html, _, _ = _capturar(tab.render_visao_geral, carteira, PREFS)
    assert "CENÁRIO MACRO" in html
    assert "SELIC META" in html and "13,75" in html
    assert "CDI" in html and "13,65" in html
    # indicador com valor=None (erro de coleta) é omitido, nunca quebra o resto
    assert "Boletim Focus" not in html


def test_visao_geral_cenario_macro_vazio_nao_mostra_secao():
    html, _, _ = _capturar(tab.render_visao_geral, _carteira(), PREFS)
    assert "CENÁRIO MACRO" not in html


def test_historico_none_mostra_mensagem_de_persistencia_nao_aplicada():
    _, _, infos = _capturar(tab.render_historico, None)
    assert infos and "sql/carteira_recomendada.sql" in infos[0]


def test_historico_vazio_mostra_mensagem_de_nenhuma_alteracao():
    _, _, infos = _capturar(tab.render_historico, [])
    assert infos and "Nenhuma alteração" in infos[0]


def test_historico_com_linhas_monta_tabela_sem_dict_cru_json():
    linha = {"ticker": "PETR4", "campo": "peso_pct", "valor_anterior": "12.0", "valor_novo": "15.0",
              "motivo": "Score subiu.", "registrado_em": "2026-11-12T16:15:16+00:00"}
    html, _, _ = _capturar(tab.render_historico, [linha])
    assert "<table" in html
    assert "PETR4" in html and "peso_pct" in html and "Score subiu." in html


# ---------------------------------------------------------------------
# ESTADO DA TESE (missão "Radar inteligente e acompanhamento de teses",
# 2026-11-23) - seção dentro do DETALHE POR ATIVO, sobre
# data/carteira_recomendada.py:estado_tese() (mockado aqui - teste de UI
# não cobre a lógica de classificação, só a apresentação).
# ---------------------------------------------------------------------

def _estado_tese_fake(classificacao="PRESERVADA", motivo="Nenhuma mudança registrada.",
                       retorno_acumulado_pct=12.5, benchmark_retorno=6.0, retorno_relativo=6.5,
                       eventos=None, avisos=None, tese_original="Tese original.", tese_atual="Tese original."):
    return {
        "ticker": "PETR4", "em_carteira": True, "motivo_entrada": "Sinal COMPRA do Comitê.",
        "data_entrada": "2026-11-13T10:00:00+00:00", "preco_entrada": 36.0,
        "tese_original": tese_original, "tese_atual": tese_atual,
        "preco_alvo_atual": 44.0, "riscos_atuais": ["Câmbio"], "criterio_saida_atual": "Rebaixamento do sinal.",
        "sinal_atual": "COMPRA", "confianca_atual": "ALTA", "score_atual": 7,
        "eventos": eventos if eventos is not None else [],
        "preco_atual": 40.0, "retorno_acumulado_pct": retorno_acumulado_pct,
        "benchmark": {"indice": "IBOVESPA", "retorno_pct": benchmark_retorno, "preco_entrada": 130000.0,
                      "preco_atual": 137800.0} if benchmark_retorno is not None else None,
        "retorno_relativo_pct": retorno_relativo,
        "estado": {"classificacao": classificacao, "motivo": motivo, "baseado_em": []},
        "avisos": avisos if avisos is not None else [],
    }


def test_estado_tese_none_mostra_mensagem_sem_dado_suficiente():
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=[]), \
         patch("data.carteira_recomendada.estado_tese", return_value=None):
        html, _, _ = _capturar(tab.render_visao_geral, _carteira(), PREFS)
    assert "sem dado suficiente" in html.lower()


def test_estado_tese_preservada_mostra_badge_e_retorno_relativo():
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=[]), \
         patch("data.carteira_recomendada.estado_tese", return_value=_estado_tese_fake()):
        html, _, _ = _capturar(tab.render_visao_geral, _carteira(), PREFS)
    assert "cart-tese-preservada" in html
    assert "TESE PRESERVADA" in html
    assert "+12,5%" in html  # retorno acumulado
    assert "+6,5%" in html  # retorno relativo


def test_estado_tese_invalidada_usa_classe_propria():
    info = _estado_tese_fake(classificacao="INVALIDADA", motivo="Comitê rebaixou o sinal para VENDA.")
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=[]), \
         patch("data.carteira_recomendada.estado_tese", return_value=info):
        html, _, _ = _capturar(tab.render_visao_geral, _carteira(), PREFS)
    assert "cart-tese-invalidada" in html
    assert "Comitê rebaixou o sinal para VENDA." in html


def test_estado_tese_mostra_diferenca_entre_tese_original_e_atual():
    info = _estado_tese_fake(tese_original="Tese original.", tese_atual="Tese revista pelo Comitê.")
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=[]), \
         patch("data.carteira_recomendada.estado_tese", return_value=info):
        html, _, _ = _capturar(tab.render_visao_geral, _carteira(), PREFS)
    assert "Tese original." in html and "Tese revista pelo Comitê." in html


def test_estado_tese_avisos_aparecem_no_html():
    info = _estado_tese_fake(avisos=["Benchmark (Ibovespa) indisponível para o período desde a entrada."])
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=[]), \
         patch("data.carteira_recomendada.estado_tese", return_value=info):
        html, _, _ = _capturar(tab.render_visao_geral, _carteira(), PREFS)
    assert "Benchmark (Ibovespa) indisponível" in html


def test_estado_tese_busca_itens_atuais_uma_unica_vez_para_varios_ativos():
    """Achado de performance: render_visao_geral busca
    obter_ultima_carteira_persistida() 1x fora do loop e repassa pra cada
    chamada de estado_tese - nunca 1x por ativo."""
    itens = [_item(ticker="PETR4"), _item(ticker="VALE3"), _item(ticker="ITUB4")]
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=[]) as obter_itens, \
         patch("data.carteira_recomendada.estado_tese", return_value=None) as estado_mock:
        _capturar(tab.render_visao_geral, _carteira(itens=itens), PREFS)
    obter_itens.assert_called_once()
    assert estado_mock.call_count == 3
    for chamada in estado_mock.call_args_list:
        assert chamada.kwargs.get("itens_atuais") == []
