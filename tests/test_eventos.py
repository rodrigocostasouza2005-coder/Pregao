# -*- coding: utf-8 -*-
"""Testes da fase CALENDARIO (2026-10-01): data/eventos.py - calculo de
proximo resultado via prazo regulatorio da CVM. Mocka
data.cvm.obter_documentos_cvm (mesma fonte/identificador que CVM ja
usa) - nao faz chamada de rede nem de IA.

Uso: python tests/test_eventos.py (python do .venv do projeto)."""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.eventos as eventos_mod
from data.eventos import STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM, calcular_calendario, calcular_proximo_resultado

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


def _doc_resultado(data_referencia):
    return {"ticker": "PETR4", "tipo": "RESULTADOS", "data_referencia": data_referencia}


# --- 3: PRAZO CVM (caso real/principal desta v1) -------------------------
def test_3_prazo_cvm_quando_nao_ha_resultado_ainda_entregue():
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("3a evento calculado (nao None)", evento is not None)
    _checar("3b status e' PRAZO_CVM (unica fonte real disponivel nesta v1)", evento["status"] == STATUS_PRAZO_CVM)
    _checar("3c periodo e' 3T26 (hoje=01/10/2026 esta no 3º trimestre)", evento["periodo"] == "3T26", f"(periodo={evento['periodo']})")
    _checar("3d prazo = 30/09 + 45 dias = 14/11/2026 (Instrucao CVM 480/2009)",
             evento["data"] == date(2026, 11, 14), f"(data={evento['data']})")
    _checar("3e fonte explicita a regra CVM (nunca afirma ser data oficial da empresa)",
             "CVM" in evento["fonte"] and "prazo" in evento["fonte"].lower())
    _checar("3f empresa vem de obter_nome_yf (reaproveita identificador existente)", evento["empresa"] == "PETROBRAS")


def test_resultado_ja_entregue_pula_pro_proximo_trimestre():
    # 3T26 (jul-set) ja' foi entregue -> deve pular pro 4T26 (DFP)
    docs = [_doc_resultado("2026-09-30")]
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=docs), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("resultado ja' entregue (data_referencia dentro do trimestre) pula pro proximo",
             evento["periodo"] == "4T26 (DFP)", f"(periodo={evento['periodo']})")
    _checar("prazo do 4T26/DFP = 31/03/2027 (~3 meses apos o fim do exercicio)",
             evento["data"] == date(2027, 3, 31), f"(data={evento['data']})")


def test_prazo_ja_vencido_pula_pro_proximo_trimestre():
    # hoje ja' passou do prazo do 2T26 (14/08) sem nenhum documento - pula pro 3T26
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 9, 1))
    _checar("prazo do trimestre atual (2T26) ja' vencido -> mostra o PROXIMO (3T26), nao um vencido",
             evento["periodo"] == "3T26", f"(periodo={evento['periodo']})")


# --- 4: evento sem horario (sempre None nesta v1 - CVM nao informa) ------
def test_4_evento_sem_horario():
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("4 horario e' None (CVM nao informa isso - nunca inventado)", evento["horario"] is None)


# --- 7: ausencia de eventos (fonte sem CNPJ/documento) --------------------
def test_7_ausencia_de_eventos_fonte_sem_cnpj():
    # obter_documentos_cvm retorna [] quando o ticker nao tem CNPJ mapeado
    # ou nao ha documento algum - ainda assim calculamos o prazo
    # regulatorio (independe de documento existir, e' uma regra legal
    # generica) - o "evento" sempre existe quando a fonte responde (so'
    # fica None se a FONTE falhar de verdade, ver teste 10)
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="EMPRESA TESTE"):
        evento = calcular_proximo_resultado("ZZZZ4", hoje=date(2026, 10, 1))
    _checar("7 mesmo sem nenhum documento CVM, o prazo regulatorio ainda e' calculavel", evento is not None)


# --- 8: data invalida/ausente (data_referencia malformada) ----------------
def test_8_data_referencia_invalida_nao_quebra_nem_conta_como_entregue():
    docs = [{"ticker": "PETR4", "tipo": "RESULTADOS", "data_referencia": "data-invalida-xyz"},
            {"ticker": "PETR4", "tipo": "RESULTADOS", "data_referencia": None}]
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=docs), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("8 data_referencia invalida/ausente nao quebra o calculo", evento is not None)
    _checar("8b documento com data ilegivel NAO conta como 'ja entregue' (continua no 3T26)",
             evento["periodo"] == "3T26", f"(periodo={evento['periodo']})")


# --- 9: duplicidade do mesmo evento (ticker repetido na lista) ------------
def test_9_duplicidade_mesmo_ticker_gera_1_evento_so():
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"):
        eventos = calcular_calendario(["PETR4", "PETR4", "PETR4"], hoje=date(2026, 10, 1))
    _checar("9 ticker duplicado na lista de entrada gera so' 1 evento", len(eventos) == 1, f"(qtd={len(eventos)})")


# --- 10: fonte CVM indisponivel --------------------------------------------
def test_10_fonte_cvm_indisponivel_nao_inventa_evento():
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=None), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("10 fonte CVM fora do ar (None) -> evento None, nunca inventa um prazo",
             evento is None)

    with patch.object(eventos_mod, "obter_documentos_cvm", side_effect=lambda t: None if t == "PETR4" else []), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="VALE"):
        eventos = calcular_calendario(["PETR4", "VALE3"], hoje=date(2026, 10, 1))
    _checar("10b calendario com 1 fonte falhando nao quebra os outros tickers",
             len(eventos) == 1 and eventos[0]["ticker"] == "VALE3", f"(eventos={[e['ticker'] for e in eventos]})")


# --- 5/6: ticker da watchlist vs fora da watchlist (logica de FILTRO fica
# na UI - esse teste confirma que calcular_calendario so' processa os
# tickers que recebe, nunca busca nenhum outro por conta propria) --------
def test_5_6_so_processa_os_tickers_recebidos():
    chamadas = []

    def _fake(ticker):
        chamadas.append(ticker)
        return []

    with patch.object(eventos_mod, "obter_documentos_cvm", side_effect=_fake), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="X"):
        calcular_calendario(["PETR4"], hoje=date(2026, 10, 1))
    _checar("5 ticker da watchlist (unico passado) e' processado", chamadas == ["PETR4"])
    _checar("6 nenhum ticker 'fora da lista' e' buscado por conta propria", len(chamadas) == 1)


# --- 1/2: CONFIRMADO/ESTIMADO - estrutura pronta, sem fonte real nesta v1
# (documentado no modulo) - testa que a CAMADA (status/rotulos) suporta
# os dois mesmo que o calculo de hoje so' produza PRAZO_CVM -------------
def test_1_2_estrutura_suporta_confirmado_e_estimado():
    _checar("1 status CONFIRMADO existe na camada normalizada", STATUS_CONFIRMADO == "CONFIRMADO")
    _checar("2 status ESTIMADO existe na camada normalizada", STATUS_ESTIMADO == "ESTIMADO")
    _checar("1b rotulo de CONFIRMADO esta mapeado", eventos_mod.STATUS_LABEL[STATUS_CONFIRMADO] == "CONFIRMADO")
    _checar("2b rotulo de ESTIMADO esta mapeado", eventos_mod.STATUS_LABEL[STATUS_ESTIMADO] == "ESTIMADO")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE EVENTOS/CALENDARIO PASSARAM")
