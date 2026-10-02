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


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE UI DO CALENDARIO (V3) PASSARAM")
