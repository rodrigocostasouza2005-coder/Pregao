# -*- coding: utf-8 -*-
"""Testes da fase CALENDARIO V3 (2026-10-02): ui/calendario_tab.py -
separacao visual entre PROXIMOS RESULTADOS (CONFIRMADO/ESTIMADO) e
PRAZOS CVM (PRAZO_CVM) - regra explicita: PRAZO CVM != data de
divulgacao. Mocka data.eventos.calcular_calendario (mesma funcao que a
UI real usa) - nao faz chamada de rede nem de IA.

Uso: python tests/test_calendario_ui.py (python do .venv do projeto)."""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.calendario_tab as calendario_tab_mod
from data.eventos import STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


def _evento(ticker="PETR4", periodo="3T26", status=STATUS_PRAZO_CVM, data_evento=None, fonte="fonte teste"):
    return {
        "ticker": ticker, "empresa": "EMPRESA TESTE", "periodo": periodo,
        "data": data_evento or date(2026, 11, 14), "horario": None,
        "status": status, "fonte": fonte, "origem_url": None, "tipo_evento": "RESULTADO",
        "coletado_em": None,
    }


def _capturar_markdown(fn, *args, **kwargs):
    capturado = []
    with patch.object(calendario_tab_mod.st, "markdown", side_effect=lambda html, **k: capturado.append(html)):
        fn(*args, **kwargs)
    return capturado


def test_1_somente_prazo_cvm_mostra_mensagem_de_nenhum_resultado_confirmado():
    prefs = {"watchlist": ["PETR4"]}
    with patch.object(calendario_tab_mod, "calcular_calendario", return_value=[_evento(status=STATUS_PRAZO_CVM)]):
        capturado = _capturar_markdown(calendario_tab_mod._painel_proximos_watchlist, prefs)
    texto = " ".join(capturado)
    _checar("1a mensagem 'Nenhuma data de divulgação confirmada.' aparece quando so' ha PRAZO_CVM",
             "Nenhuma data de divulgação confirmada." in texto)
    _checar("1b subheader PRAZOS CVM aparece listando o evento", "PRAZOS CVM" in texto and "PETR4" in texto)
    _checar("1c PRAZO CVM nunca aparece sob o rotulo PRÓXIMOS RESULTADOS",
             texto.index("PRÓXIMOS RESULTADOS") < texto.index("PRAZOS CVM"))


def test_2_confirmado_aparece_em_proximos_resultados_nao_em_prazos_cvm():
    prefs = {"watchlist": ["PETR4"]}
    eventos = [_evento(status=STATUS_CONFIRMADO, fonte="Petrobras RI", data_evento=date(2026, 10, 20))]
    with patch.object(calendario_tab_mod, "calcular_calendario", return_value=eventos):
        capturado = _capturar_markdown(calendario_tab_mod._painel_proximos_watchlist, prefs)
    texto = " ".join(capturado)
    _checar("2a CONFIRMADO aparece na lista (nao esconde o evento)", "PETR4" in texto and "CONFIRMADO" in texto)
    _checar("2b mensagem de 'nenhuma data confirmada' NAO aparece quando ha' CONFIRMADO", "Nenhuma data de divulgação confirmada." not in texto)
    _checar("2c subheader PRAZOS CVM NAO aparece (nenhum evento PRAZO_CVM nesta lista)", "PRAZOS CVM" not in texto)


def test_3_estimado_tambem_vai_pra_proximos_resultados():
    prefs = {"watchlist": ["VALE3"]}
    eventos = [_evento(ticker="VALE3", status=STATUS_ESTIMADO, fonte="Consenso de mercado")]
    with patch.object(calendario_tab_mod, "calcular_calendario", return_value=eventos):
        capturado = _capturar_markdown(calendario_tab_mod._painel_proximos_watchlist, prefs)
    texto = " ".join(capturado)
    _checar("3 ESTIMADO aparece em PRÓXIMOS RESULTADOS (nao em PRAZOS CVM)",
             "VALE3" in texto and "PRAZOS CVM" not in texto)


def test_4_mix_confirmado_e_prazo_cvm_fica_em_secoes_diferentes():
    prefs = {"watchlist": ["PETR4", "VALE3"]}
    eventos = [
        _evento(ticker="PETR4", status=STATUS_CONFIRMADO, fonte="Petrobras RI", data_evento=date(2026, 10, 20)),
        _evento(ticker="VALE3", status=STATUS_PRAZO_CVM, data_evento=date(2026, 11, 14)),
    ]
    with patch.object(calendario_tab_mod, "calcular_calendario", return_value=eventos):
        capturado = _capturar_markdown(calendario_tab_mod._painel_proximos_watchlist, prefs)
    texto = " ".join(capturado)
    idx_resultados = texto.index("PRÓXIMOS RESULTADOS")
    idx_prazos = texto.index("PRAZOS CVM")
    idx_petr4 = texto.index("PETR4")
    idx_vale3 = texto.index("VALE3")
    _checar("4 PETR4 (CONFIRMADO) aparece ANTES do subheader PRAZOS CVM",
             idx_resultados < idx_petr4 < idx_prazos)
    _checar("4b VALE3 (PRAZO_CVM) aparece DEPOIS do subheader PRAZOS CVM",
             idx_prazos < idx_vale3)


def test_5_mensagem_de_periodo_vazio_na_agenda():
    prefs = {"watchlist": ["PETR4"]}
    with patch.object(calendario_tab_mod, "calcular_calendario", return_value=[]), \
         patch.object(calendario_tab_mod.st, "columns", return_value=(_FakeCol(), _FakeCol())), \
         patch.object(calendario_tab_mod.st, "pills", return_value=None), \
         patch.object(calendario_tab_mod.st, "spinner", return_value=_FakeCtx()):
        capturado = _capturar_markdown(calendario_tab_mod._painel_agenda, prefs)
    texto = " ".join(capturado)
    _checar("5 mensagem exata 'Nenhum evento no período.' (sem 'selecionado')",
             "Nenhum evento no período." in texto)


class _FakeCol:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_6_detalhe_prazo_cvm_mostra_aviso_explicito():
    evento = _evento(status=STATUS_PRAZO_CVM)
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[]):
        capturado = _capturar_markdown(calendario_tab_mod._detalhe_evento, evento)
    texto = " ".join(capturado)
    _checar("6 detalhe de PRAZO_CVM mostra o aviso obrigatório",
             "Não representa necessariamente a data de divulgação do resultado" in texto)


def test_7_detalhe_confirmado_nao_mostra_aviso_de_prazo():
    evento = _evento(status=STATUS_CONFIRMADO, fonte="Petrobras RI")
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[]):
        capturado = _capturar_markdown(calendario_tab_mod._detalhe_evento, evento)
    texto = " ".join(capturado)
    _checar("7 detalhe de CONFIRMADO NAO mostra o aviso de prazo regulatório",
             "Não representa necessariamente a data de divulgação do resultado" not in texto)


# ============================================================
# FASE "HUB DO EVENTO" (2026-10-02): RESEARCH/NEWS/CVM/HISTORICO no
# detalhe de um evento - reaproveita obter_documentos_cvm/obter_noticias/
# listar_itens (mesmas funcoes cacheadas que EQUITY/CVM/NEWS/RESEARCH ja
# usam), zero chamada de IA, zero fonte nova.
# ============================================================

_DOC_CVM_GENERICO = {
    "ticker": "PETR4", "tipo": "COMUNICADO", "tipo_label": "COMUNICADO",
    "categoria_original": "Comunicado ao Mercado", "assunto": "Aviso de fato relevante",
    "data": "2026-09-28", "data_referencia": None, "link": "https://cvm.example/doc1", "destaque": False,
}
_DOC_CVM_RESULTADO_ANTIGO = {
    "ticker": "PETR4", "tipo": "RESULTADOS", "tipo_label": "RESULTADOS",
    "categoria_original": "Dados Econômico-Financeiros", "assunto": "Press-release",
    "data": "2026-07-10", "data_referencia": "2026-06-30", "link": "https://cvm.example/doc2", "destaque": False,
}
_NOTICIA = {"ticker": "PETR4", "titulo": "Petrobras anuncia investimento", "data": "2026-09-29",
            "link": "https://news.example/n1", "selo": "MENÇÃO", "score": 1, "veiculos": ["Veículo Teste"], "tickers": ["PETR4"]}
_RELATORIO = {"casa": "Genial Analisa", "titulo": "PETR4: tese de investimento", "data": "2026-09-27",
              "autor": "", "tipo": "ACOES", "tickers": ["PETR4"], "link": "https://research.example/r1",
              "resumo": None, "modelo_resumo": None, "preco_alvo": None, "recomendacao": None}


def test_8_evento_com_todas_as_fontes_mostra_as_4_secoes():
    evento = _evento()
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[_DOC_CVM_GENERICO, _DOC_CVM_RESULTADO_ANTIGO]) as mock_cvm, \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[_NOTICIA]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[_RELATORIO]):
        capturado = _capturar_markdown(calendario_tab_mod._detalhe_evento, evento)
    texto = " ".join(capturado)
    _checar("8a seção RESEARCH aparece", "RESEARCH" in texto and "tese de investimento" in texto)
    _checar("8b seção NEWS aparece", "NEWS" in texto and "Petrobras anuncia investimento" in texto)
    _checar("8c seção CVM (documentos genéricos) aparece", "CVM" in texto and "Aviso de fato relevante" in texto)
    _checar("8d seção HISTÓRICO (resultado antigo) aparece", "HISTÓRICO" in texto and "ref. 2026-06-30" in texto)
    # usa "CVM ·" (com o separador do rotulo da secao), nao so' "CVM" -
    # o badge de status do evento PRAZO_CVM ja' contem a substring "CVM"
    # bem antes de qualquer secao (achado real ao rodar este teste)
    _checar("8e ordem das seções é RESEARCH, NEWS, CVM, HISTÓRICO (pedido explícito)",
             texto.index("RESEARCH ·") < texto.index("NEWS ·") < texto.index("CVM ·") < texto.index("HISTÓRICO ·"))
    _checar("8f obter_documentos_cvm chamado so' 1 VEZ (CVM + HISTÓRICO reaproveitam a mesma busca, sem N+1)",
             mock_cvm.call_count == 1, f"(call_count={mock_cvm.call_count})")


def test_9_evento_sem_algumas_fontes_oculta_so_as_vazias():
    evento = _evento()
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[_DOC_CVM_GENERICO]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[]):
        capturado = _capturar_markdown(calendario_tab_mod._detalhe_evento, evento)
    texto = " ".join(capturado)
    _checar("9a RESEARCH oculto quando vazio (sem relatório relacionado)", "RESEARCH" not in texto)
    _checar("9b NEWS oculto quando vazio (sem notícia relacionada)", "NEWS" not in texto)
    _checar("9c CVM aparece (tem documento genérico)", "CVM" in texto)
    _checar("9d HISTÓRICO oculto (documento genérico não é tipo RESULTADOS)", "HISTÓRICO" not in texto)


def test_10_ticker_sem_dado_nenhum_oculta_todas_as_4_secoes():
    evento = _evento()
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[]):
        capturado = _capturar_markdown(calendario_tab_mod._detalhe_evento, evento)
    texto = " ".join(capturado)
    for secao in ("RESEARCH", "NEWS", "CVM ·", "HISTÓRICO"):
        _checar(f"10 seção '{secao}' oculta quando ticker nao tem dado nenhum", secao not in texto)

    # fonte CVM indisponivel (None, nao []) tambem precisa ocultar CVM/HISTORICO
    # sem quebrar (achado real: obter_documentos_cvm pode retornar None)
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=None), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[]):
        try:
            capturado2 = _capturar_markdown(calendario_tab_mod._detalhe_evento, evento)
            ok = True
        except Exception as e:
            ok = False
            print("      excecao:", e)
    _checar("10b fonte CVM indisponível (None) não quebra o detalhe do evento", ok)
    if ok:
        texto2 = " ".join(capturado2)
        _checar("10c fonte CVM indisponível (None) também oculta CVM/HISTÓRICO (nunca mostra seção vazia)",
                 "CVM ·" not in texto2 and "HISTÓRICO" not in texto2)


def test_11_links_sao_clicaveis_apontando_para_a_fonte_original():
    evento = _evento()
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[_DOC_CVM_GENERICO, _DOC_CVM_RESULTADO_ANTIGO]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[_NOTICIA]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[_RELATORIO]):
        capturado = _capturar_markdown(calendario_tab_mod._detalhe_evento, evento)
    texto = " ".join(capturado)
    _checar("11a link do RESEARCH aponta pra URL original", "href='https://research.example/r1'" in texto)
    _checar("11b link do NEWS aponta pra URL original", "href='https://news.example/n1'" in texto)
    _checar("11c link do CVM aponta pra URL original", "href='https://cvm.example/doc1'" in texto)
    _checar("11d link do HISTÓRICO aponta pra URL original", "href='https://cvm.example/doc2'" in texto)
    _checar("11e todos os links abrem em nova aba (target='_blank', nunca navega pra fora do Pregão)",
             texto.count("target='_blank'") >= 4)


def test_12_ausencia_de_chamadas_de_ia():
    evento = _evento()
    chamadas_ia = []
    # research_tab.obter_resumo e resumir_com_groq sao os unicos pontos de
    # IA do projeto relacionados a ticker/research - garantir que o hub do
    # calendario nunca os importa/chama, mesmo com RESEARCH relacionado
    import data.research.resumir as resumir_mod
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[_DOC_CVM_GENERICO]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[_NOTICIA]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[_RELATORIO]), \
         patch.object(resumir_mod, "resumir_com_groq", side_effect=lambda *a, **k: chamadas_ia.append(1)), \
         patch.object(resumir_mod, "obter_resumo", side_effect=lambda *a, **k: chamadas_ia.append(1)):
        _capturar_markdown(calendario_tab_mod._detalhe_evento, evento)
    _checar("12 nenhuma chamada de IA (resumir_com_groq/obter_resumo) acontece ao montar o hub do evento",
             chamadas_ia == [], f"(chamadas_ia={chamadas_ia})")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE UI DO CALENDARIO (V3) PASSARAM")
