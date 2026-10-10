# -*- coding: utf-8 -*-
"""Testes de ui/news_tab.py:_bloco_contexto_research - integração
NEWS→RESEARCH dentro do dialog de detalhe da notícia (FASE 3,
2026-10-08), sem nenhum teste direto até a auditoria da FASE 8. Cobre:
contexto correto, ausência de contexto, múltiplos tickers/itens,
fallback quando nenhum ticker está na watchlist, e que nunca fabrica
recomendação/preço-alvo (só mostra o que obter_recomendacoes() já
trouxe de verdade).

Mocka data.research.genial.obter_recomendacoes (já importado por nome
em ui.news_tab) e st.markdown - sem rede/IA. Uso:
python tests/test_news_contexto_research.py (venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.news_tab as news_tab_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        # 2026-10-10: faz a checagem REALMENTE falhar sob pytest (antes so'
        # imprimia e guardava em _FALHAS, lido so' pelo runner `__main__` -
        # sob pytest toda funcao test_* passava mesmo com condicao=False,
        # a menos que outra linha lancasse excecao por acidente; ver
        # investigacao registrada no relatorio da auditoria 2026-10-10)
        raise AssertionError(f"{nome} {detalhe}".strip())


def _recomendacao(ticker, recomendacao="COMPRA", preco_alvo=42.0, potencial_pct=5.3):
    return {"ticker": ticker, "recomendacao": recomendacao, "preco_alvo": preco_alvo, "potencial_pct": potencial_pct}


def test_1_contexto_aparece_quando_ha_recomendacao_real_pro_ticker():
    capturado = []
    with patch.object(news_tab_mod, "obter_recomendacoes", return_value=[_recomendacao("PETR4")]), \
         patch.object(news_tab_mod.st, "markdown", side_effect=lambda h, **k: capturado.append(h)):
        news_tab_mod._bloco_contexto_research(["PETR4"], ["PETR4", "VALE3"])
    texto = " ".join(capturado)
    _checar("1a bloco RESEARCH aparece (markdown chamado)", len(capturado) > 0)
    _checar("1b ticker PETR4 aparece no bloco", "PETR4" in texto)
    _checar("1c recomendacao real (COMPRA) aparece, nunca fabricada", "COMPRA" in texto)
    _checar("1d preco-alvo real aparece formatado", "42.00" in texto or "42,00" in texto, f"(texto={texto!r})")


def test_2_sem_recomendacao_nenhuma_nao_mostra_nada():
    capturado = []
    with patch.object(news_tab_mod, "obter_recomendacoes", return_value=[_recomendacao("VALE3")]), \
         patch.object(news_tab_mod.st, "markdown", side_effect=lambda h, **k: capturado.append(h)):
        news_tab_mod._bloco_contexto_research(["PETR4"], ["PETR4"])
    _checar("2 ticker sem recomendacao coletada -> nenhum markdown (secao nem aparece)", capturado == [])


def test_3_fonte_indisponivel_degrada_sem_quebrar():
    with patch.object(news_tab_mod, "obter_recomendacoes", return_value=None):
        try:
            news_tab_mod._bloco_contexto_research(["PETR4"], ["PETR4"])
            ok = True
        except Exception as e:
            ok = False
            print("      excecao:", e)
    _checar("3 fonte Genial indisponivel (None) -> nao quebra, nunca mostra contexto inventado", ok)


def test_4_tickers_vazio_nunca_chama_a_fonte():
    chamadas = []
    with patch.object(news_tab_mod, "obter_recomendacoes", side_effect=lambda: chamadas.append(1) or []):
        news_tab_mod._bloco_contexto_research([], ["PETR4"])
    _checar("4 lista de tickers vazia -> nem chama obter_recomendacoes", chamadas == [])


def test_5_multiplos_tickers_mostra_cada_um_relevante_ate_o_limite():
    recomendacoes = [_recomendacao("PETR4"), _recomendacao("VALE3"), _recomendacao("ITUB4"),
                      _recomendacao("BBAS3")]
    capturado = []
    with patch.object(news_tab_mod, "obter_recomendacoes", return_value=recomendacoes), \
         patch.object(news_tab_mod.st, "markdown", side_effect=lambda h, **k: capturado.append(h)):
        news_tab_mod._bloco_contexto_research(["PETR4", "VALE3", "ITUB4", "BBAS3"], ["PETR4", "VALE3", "ITUB4", "BBAS3"])
    texto = " ".join(capturado)
    tickers_mostrados = [t for t in ("PETR4", "VALE3", "ITUB4", "BBAS3") if t in texto]
    _checar(f"5 respeita o limite de {news_tab_mod._LIMITE_CONTEXTO_RESEARCH} itens (nao mostra os 4)",
            len(tickers_mostrados) == news_tab_mod._LIMITE_CONTEXTO_RESEARCH, f"(mostrados={tickers_mostrados})")


def test_6_fallback_pra_tickers_fora_da_watchlist_quando_nenhum_na_watchlist():
    # tickers_watch = [t for t in tickers if t in watchlist] or tickers -
    # se NENHUM ticker do item esta na watchlist do usuario, cai pro
    # proprio `tickers` (nunca fica sem mostrar so' por causa disso).
    capturado = []
    with patch.object(news_tab_mod, "obter_recomendacoes", return_value=[_recomendacao("MGLU3")]), \
         patch.object(news_tab_mod.st, "markdown", side_effect=lambda h, **k: capturado.append(h)):
        news_tab_mod._bloco_contexto_research(["MGLU3"], ["PETR4", "VALE3"])
    texto = " ".join(capturado)
    _checar("6 ticker do item fora da watchlist do usuario ainda mostra contexto (fallback pro proprio item)",
            "MGLU3" in texto, f"(texto={texto!r})")


def test_7_potencial_e_preco_alvo_ausentes_nao_fabricam_valor():
    capturado = []
    with patch.object(news_tab_mod, "obter_recomendacoes",
                       return_value=[_recomendacao("PETR4", preco_alvo=None, potencial_pct=None)]), \
         patch.object(news_tab_mod.st, "markdown", side_effect=lambda h, **k: capturado.append(h)):
        news_tab_mod._bloco_contexto_research(["PETR4"], ["PETR4"])
    texto = " ".join(capturado)
    _checar("7a sem preco-alvo coletado -> nenhum 'preço-alvo' no texto (nunca inventa)", "preço-alvo" not in texto)
    _checar("7b sem potencial coletado -> nenhum 'potencial' no texto (nunca inventa)", "potencial" not in texto)
    _checar("7c recomendacao real continua aparecendo mesmo sem os outros 2 campos", "COMPRA" in texto)


def test_8_nenhuma_chamada_de_ia_e_feita():
    chamadas_ia = []
    with patch.object(news_tab_mod, "obter_recomendacoes", return_value=[_recomendacao("PETR4")]), \
         patch.object(news_tab_mod.st, "markdown"):
        if hasattr(news_tab_mod, "obter_resumo_grupo"):
            with patch.object(news_tab_mod, "obter_resumo_grupo", side_effect=lambda *a, **k: chamadas_ia.append(1)):
                news_tab_mod._bloco_contexto_research(["PETR4"], ["PETR4"])
        else:
            news_tab_mod._bloco_contexto_research(["PETR4"], ["PETR4"])
    _checar("8 nenhuma chamada de resumo/IA acontece ao montar o contexto de research", chamadas_ia == [])


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass  # ja' registrado em _FALHAS por _checar

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE _bloco_contexto_research (NEWS->RESEARCH) PASSARAM")
