# -*- coding: utf-8 -*-
"""Testes da camada analítica nova de CARTEIRA RECOMENDADA
(ui/carteira_recomendada_tab.py:_leitura_carteira, missão "camada
analítica" 2026-11-18): auditoria desta missão encontrou CARTEIRA
RECOMENDADA como PARCIAL - o resumo já mostrava números crus
(diversificacao_setorial, concentracao_maxima_pct) e cada item já tinha
confianca_comite/riscos (ver data/carteira_recomendada.py), mas nenhuma
leitura qualitativa conectava isso a "existe concentração/risco
excessivo?" ou "qual posição merece atenção?" (pedido explícito do
Rodrigo).

_leitura_carteira reaproveita SÓ esse dado já computado por
montar_carteira_recomendada() - zero cálculo novo, zero IA. O limiar de
concentração setorial (25%) é o MESMO já estabelecido em data/radar.py
(_LIMIAR_CONCENTRACAO_PCT, usado no RISCO DA CARTEIRA do RADAR pra
carteira real do usuário), não um número novo inventado aqui. "Merece
atenção" usa só confianca_comite == "BAIXA" (categoria já atribuída pelo
Comitê) - nunca a mera presença de 'riscos' (quase toda posição tem ao
menos 1 ponto contrário listado; usar isso como gatilho deixaria a nota
sempre populada).

Mesmo padrão de captura de tests/test_carteira_recomendada_tab_ui.py:
patch.object(tab.st, "markdown", ...)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.carteira_recomendada_tab as tab

PREFS = {"formato_numerico": "BR"}


def _capturar(fn, *args, **kwargs):
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
          preco_alvo=44.10, retorno_base=20.8, setor="Petróleo e Gás", riscos=None):
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
        "tese": "Tese resumida.", "riscos": riscos if riscos is not None else ["Risco A"],
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


def test_carteira_default_sem_concentracao_nem_baixa_confianca_nao_mostra_leitura():
    """Regressão: a carteira-padrão de teste (1 ativo a 15%, confiança
    ALTA) não tem nenhum sinal real de concentração/atenção - a seção
    LEITURA DA CARTEIRA nunca aparece pra não inflar o painel com ruído."""
    html, _, _ = _capturar(tab.render_visao_geral, _carteira(), PREFS)
    assert "LEITURA DA CARTEIRA" not in html


def test_concentracao_setorial_acima_do_limiar_mostra_fato():
    itens = [
        _item(ticker="PETR4", peso=15.0, setor="Petróleo e Gás"),
        _item(ticker="PRIO3", peso=14.0, setor="Petróleo e Gás"),
        _item(ticker="VALE3", peso=10.0, setor="Mineração"),
    ]
    html, _, _ = _capturar(tab.render_visao_geral, _carteira(itens=itens), PREFS)
    assert "LEITURA DA CARTEIRA" in html
    assert "[FATO]" in html
    assert "Concentração setorial acima de 25%" in html
    assert "Petróleo e Gás (29,0%)" in html
    assert "Mineração" not in html.split("Concentração setorial")[1].split("</div>")[0]


def test_posicao_confianca_baixa_aparece_como_merece_atencao():
    itens = [
        _item(ticker="PETR4", peso=15.0, confianca="ALTA"),
        _item(ticker="MGLU3", peso=10.0, setor="Varejo", confianca="BAIXA", riscos=["Risco X", "Risco Y"]),
    ]
    html, _, _ = _capturar(tab.render_visao_geral, _carteira(itens=itens), PREFS)
    assert "LEITURA DA CARTEIRA" in html
    assert "Posições que merecem atenção" in html
    assert "MGLU3 (confiança BAIXA, 2 risco(s) listado(s) pelo Comitê)" in html
    assert "PETR4 (" not in html.split("Posições que merecem atenção")[1]


def test_riscos_sozinhos_sem_confianca_baixa_nunca_disparam_atencao():
    """A mera presença de 'riscos' (quase toda posição tem ao menos 1)
    NUNCA é suficiente - só confianca_comite == 'BAIXA' é um gatilho
    real, senão a nota ficaria sempre populada."""
    itens = [_item(ticker="PETR4", confianca="ALTA", riscos=["Risco A", "Risco B", "Risco C"])]
    html, _, _ = _capturar(tab.render_visao_geral, _carteira(itens=itens), PREFS)
    assert "LEITURA DA CARTEIRA" not in html
    assert "merecem atenção" not in html


def test_setor_unico_ativo_abaixo_do_limiar_nao_mostra_concentracao():
    html, _, _ = _capturar(tab.render_visao_geral, _carteira(itens=[_item(peso=15.0)]), PREFS)
    assert "Concentração setorial" not in html


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
