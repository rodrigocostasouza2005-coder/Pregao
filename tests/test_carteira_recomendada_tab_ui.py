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
