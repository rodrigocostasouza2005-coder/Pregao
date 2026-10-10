# -*- coding: utf-8 -*-
"""Testes da fase CALENDARIO (2026-10-01): data/eventos.py - calculo de
proximo resultado via prazo regulatorio da CVM. Mocka
data.cvm.obter_documentos_cvm (mesma fonte/identificador que CVM ja
usa) - nao faz chamada de rede nem de IA.

Uso: python tests/test_eventos.py (python do .venv do projeto) OU
pytest tests/test_eventos.py (suite completa do projeto)."""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.eventos as eventos_mod
from data.eventos import (
    STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM,
    aplicar_cache_resiliente, calcular_calendario, calcular_calendario_cacheado, calcular_proximo_resultado,
    mesclar_eventos,
)

_FALHAS = []

# CNPJ fake usado como default em TODO o arquivo (ver fixture abaixo e
# __main__ no fim) - a maioria dos testes representa um ticker
# CVM-regulado de verdade (PETR4/VALE3/etc), onde obter_cnpj() sempre
# acha algo; so' o teste 7b sobrescreve isso localmente pra cobrir o
# caso real "ticker sem CNPJ mapeado" (bug corrigido em 2026-10-08, ver
# data/eventos.py:periodo_pendente).
_CNPJ_FAKE = "11.222.333/0001-44"


@pytest.fixture(autouse=True)
def _cnpj_mapeado_por_padrao():
    """Sob pytest, o bloco `if __name__ == "__main__"` no fim do arquivo
    nunca roda - sem isso, todo teste chamava o obter_cnpj REAL (sem
    rede/dados locais neste runner), periodo_pendente devolvia None
    sempre e calcular_proximo_resultado devolvia None pra TODO ticker,
    quebrando 10 testes com 'NoneType is not subscriptable' (achado
    real, 2026-10-08: a suite via `python tests/test_eventos.py`
    sempre passou por isso, mascarando a quebra sob pytest). Mock
    padrao aqui replica o mesmo default do runner `__main__`; o teste
    7b sobrescreve localmente pra cobrir o caso sem CNPJ, e o `with`
    interno dele prevalece enquanto ativo (patch mais interno vence)."""
    with patch.object(eventos_mod, "obter_cnpj", return_value=_CNPJ_FAKE):
        yield


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


def _doc_resultado(data_referencia):
    return {"ticker": "PETR4", "tipo": "RESULTADOS", "data_referencia": data_referencia}


# --- 3: PRAZO CVM (caso real/principal desta v1) -------------------------
def test_3_prazo_cvm_quando_nao_ha_resultado_ainda_entregue():
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "_nome_empresa", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("3a evento calculado (nao None)", evento is not None)
    _checar("3b status e' PRAZO_CVM (unica fonte real disponivel nesta v1)", evento["status"] == STATUS_PRAZO_CVM)
    _checar("3c periodo e' 3T26 (hoje=01/10/2026 esta no 3º trimestre)", evento["periodo"] == "3T26", f"(periodo={evento['periodo']})")
    _checar("3d prazo = 30/09 + 45 dias = 14/11/2026 (Instrucao CVM 480/2009)",
             evento["data"] == date(2026, 11, 14), f"(data={evento['data']})")
    _checar("3e fonte explicita a regra CVM (nunca afirma ser data oficial da empresa)",
             "CVM" in evento["fonte"] and "prazo" in evento["fonte"].lower())
    _checar("3f empresa vem de _nome_empresa (cascata barata antes do fallback de rede)", evento["empresa"] == "PETROBRAS")


def test_resultado_ja_entregue_pula_pro_proximo_trimestre():
    # 3T26 (jul-set) ja' foi entregue -> deve pular pro 4T26 (DFP)
    docs = [_doc_resultado("2026-09-30")]
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=docs), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("resultado ja' entregue (data_referencia dentro do trimestre) pula pro proximo",
             evento["periodo"] == "4T26 (DFP)", f"(periodo={evento['periodo']})")
    _checar("prazo do 4T26/DFP = 31/03/2027 (~3 meses apos o fim do exercicio)",
             evento["data"] == date(2027, 3, 31), f"(data={evento['data']})")


def test_prazo_ja_vencido_pula_pro_proximo_trimestre():
    # hoje ja' passou do prazo do 2T26 (14/08) sem nenhum documento - pula pro 3T26
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 9, 1))
    _checar("prazo do trimestre atual (2T26) ja' vencido -> mostra o PROXIMO (3T26), nao um vencido",
             evento["periodo"] == "3T26", f"(periodo={evento['periodo']})")


# --- 4: evento sem horario (sempre None nesta v1 - CVM nao informa) ------
def test_4_evento_sem_horario():
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("4 horario e' None (CVM nao informa isso - nunca inventado)", evento["horario"] is None)


# --- 7: ausencia de eventos (ticker com CNPJ, mas sem documento ainda) ----
def test_7_ausencia_de_documento_mas_cnpj_mapeado_ainda_calcula_prazo():
    # obter_documentos_cvm retorna [] quando a fonte respondeu mas nao ha
    # documento algum pro periodo - pra um ticker DE FATO regulado pela
    # CVM (tem CNPJ mapeado), isso ainda e' prazo calculavel (independe
    # de documento existir, e' uma regra legal generica).
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="EMPRESA TESTE"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = calcular_proximo_resultado("ZZZZ4", hoje=date(2026, 10, 1))
    _checar("7 CNPJ mapeado + sem nenhum documento CVM -> prazo regulatorio ainda e' calculavel", evento is not None)


# --- 7b: bug real corrigido (2026-10-08) - ticker SEM CNPJ mapeado nunca
# pode ter um prazo fabricado (ex: BDR estrangeiro que nunca protocola
# ITR/DFP na CVM nesse regime) -------------------------------------------
def test_7b_ticker_sem_cnpj_mapeado_nao_fabrica_prazo_cvm():
    with patch.object(eventos_mod, "obter_cnpj", return_value=None), \
         patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="BDR ESTRANGEIRO"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = calcular_proximo_resultado("MELI34", hoje=date(2026, 10, 1))
    _checar("7b ticker sem CNPJ mapeado (ex: BDR) -> None, nunca fabrica um PRAZO_CVM", evento is None)


# --- 8: data invalida/ausente (data_referencia malformada) ----------------
def test_8_data_referencia_invalida_nao_quebra_nem_conta_como_entregue():
    docs = [{"ticker": "PETR4", "tipo": "RESULTADOS", "data_referencia": "data-invalida-xyz"},
            {"ticker": "PETR4", "tipo": "RESULTADOS", "data_referencia": None}]
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=docs), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("8 data_referencia invalida/ausente nao quebra o calculo", evento is not None)
    _checar("8b documento com data ilegivel NAO conta como 'ja entregue' (continua no 3T26)",
             evento["periodo"] == "3T26", f"(periodo={evento['periodo']})")


# --- 9: duplicidade do mesmo evento (ticker repetido na lista) ------------
def test_9_duplicidade_mesmo_ticker_gera_1_evento_so():
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        eventos = calcular_calendario(["PETR4", "PETR4", "PETR4"], hoje=date(2026, 10, 1))
    _checar("9 ticker duplicado na lista de entrada gera so' 1 evento", len(eventos) == 1, f"(qtd={len(eventos)})")


# --- 10: fonte CVM indisponivel --------------------------------------------
def test_10_fonte_cvm_indisponivel_nao_inventa_evento():
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=None), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("10 fonte CVM fora do ar (None) -> evento None, nunca inventa um prazo",
             evento is None)

    with patch.object(eventos_mod, "obter_documentos_cvm", side_effect=lambda t: None if t == "PETR4" else []), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="VALE"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
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
         patch.object(eventos_mod, "obter_nome_yf", return_value="X"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
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


# ============================================================
# FASE CALENDARIO V2 (2026-10-01): prioridade/deduplicacao/cache
# resiliente. Investigacao real (ver docstring de data/eventos.py)
# confirmou que NAO existe hoje fonte automatica segura de CONFIRMADO/
# ESTIMADO (dados estruturados da CVM pra "Calendario de Eventos
# Corporativos" nao tem a data do evento, so' data de protocolo) - os
# testes abaixo usam eventos SINTETICOS (dict construido a mao,
# representando o que uma fonte confiavel RETORNARIA se existisse) pra
# provar que a camada de prioridade/deduplicacao/resiliencia funciona
# corretamente, pronta pra quando uma fonte assim for integrada.
# ============================================================

def _evento_sintetico(ticker="PETR4", periodo="3T26", data_evento=None, status=STATUS_PRAZO_CVM, fonte="fonte teste", url=None):
    return {
        "ticker": ticker, "empresa": "EMPRESA TESTE", "periodo": periodo,
        "data": data_evento or date(2026, 11, 14), "horario": None,
        "status": status, "fonte": fonte, "origem_url": url, "tipo_evento": "RESULTADO",
        "coletado_em": None,
    }


def test_v2_1_data_oficial_vira_confirmado():
    evento = _evento_sintetico(status=STATUS_CONFIRMADO, data_evento=date(2026, 10, 20),
                                fonte="Petrobras RI", url="https://ri.petrobras.com.br/calendario")
    _checar("v2.1 evento com status CONFIRMADO preserva fonte e URL",
             evento["status"] == STATUS_CONFIRMADO and evento["fonte"] == "Petrobras RI" and evento["origem_url"])


def test_v2_2_fonte_externa_confiavel_vira_estimado():
    evento = _evento_sintetico(status=STATUS_ESTIMADO, fonte="Consenso de mercado (fonte externa)")
    _checar("v2.2 evento com status ESTIMADO preserva a fonte (nunca escondida)",
             evento["status"] == STATUS_ESTIMADO and "fonte externa" in evento["fonte"])


def test_v2_3_somente_prazo_cvm_quando_sem_fonte_melhor():
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        eventos = calcular_calendario(["PETR4"], hoje=date(2026, 10, 1))
    _checar("v2.3 pipeline real (sem fonte oficial integrada) so' produz PRAZO_CVM, nunca inventa CONFIRMADO/ESTIMADO",
             len(eventos) == 1 and eventos[0]["status"] == STATUS_PRAZO_CVM)


def test_v2_4_confirmado_substitui_estimado_na_mesma_rodada():
    prazo = _evento_sintetico(status=STATUS_PRAZO_CVM, data_evento=date(2026, 11, 14))
    estimado = _evento_sintetico(status=STATUS_ESTIMADO, data_evento=date(2026, 10, 25), fonte="Consenso")
    confirmado = _evento_sintetico(status=STATUS_CONFIRMADO, data_evento=date(2026, 10, 20), fonte="Petrobras RI")
    mesclado = mesclar_eventos([prazo], [estimado], [confirmado])
    _checar("v2.4 CONFIRMADO vence ESTIMADO e PRAZO_CVM pro mesmo (ticker,periodo) - so' 1 evento no resultado",
             len(mesclado) == 1 and mesclado[0]["status"] == STATUS_CONFIRMADO, f"(qtd={len(mesclado)})")
    _checar("v2.4b fonte perdedora (ESTIMADO) continua visivel em _fontes_alternativas - nunca escondida",
             any(f["status"] == STATUS_ESTIMADO for f in mesclado[0].get("_fontes_alternativas", [])))


def test_v2_5_confirmado_substitui_prazo_cvm():
    prazo = _evento_sintetico(status=STATUS_PRAZO_CVM)
    confirmado = _evento_sintetico(status=STATUS_CONFIRMADO, data_evento=date(2026, 10, 20), fonte="Petrobras RI")
    mesclado = mesclar_eventos([prazo], [confirmado])
    _checar("v2.5 CONFIRMADO substitui PRAZO_CVM (nunca os dois como eventos separados)",
             len(mesclado) == 1 and mesclado[0]["status"] == STATUS_CONFIRMADO)
    _checar("v2.5b PRAZO_CVM perdedor preservado em _fontes_alternativas (origem nunca escondida)",
             any(f["status"] == STATUS_PRAZO_CVM for f in mesclado[0].get("_fontes_alternativas", [])))


def test_v2_6_ausencia_de_fonte_nao_inventa():
    # ja' coberto por test_10 (fonte CVM indisponivel -> None) - reforco
    # aqui especificamente pro caso "nenhuma fonte confiavel identificada"
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=None):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("v2.6 sem nenhuma fonte disponivel, NUNCA inventa um evento (None, nao um PRAZO_CVM de brincadeira)",
             evento is None)


def test_v2_7_deduplicacao_mesmo_ticker_periodo_nunca_vira_2_linhas():
    a = _evento_sintetico(status=STATUS_PRAZO_CVM, data_evento=date(2026, 11, 14))
    b = _evento_sintetico(status=STATUS_PRAZO_CVM, data_evento=date(2026, 11, 14), fonte="fonte teste 2")
    mesclado = mesclar_eventos([a], [b])
    _checar("v2.7 2 eventos do MESMO (ticker,periodo) e MESMA prioridade -> deduplica pra 1 so'",
             len(mesclado) == 1, f"(qtd={len(mesclado)})")
    # tickers/periodos DIFERENTES nunca se fundem entre si
    c = _evento_sintetico(ticker="VALE3", status=STATUS_PRAZO_CVM, data_evento=date(2026, 11, 10))
    mesclado2 = mesclar_eventos([a], [c])
    _checar("v2.7b tickers diferentes NUNCA se fundem (continuam 2 eventos)", len(mesclado2) == 2)


def test_v2_8_fonte_indisponivel_preserva_ultimo_dado_valido():
    eventos_mod._cache_eventos().clear()
    confirmado_antigo = _evento_sintetico(status=STATUS_CONFIRMADO, data_evento=date(2026, 10, 20), fonte="Petrobras RI")
    # 1a rodada: fonte respondeu com CONFIRMADO -> vai pro cache
    aplicar_cache_resiliente([confirmado_antigo])
    # 2a rodada: a MESMA fonte oficial falhou dessa vez, so' sobrou o
    # calculo de PRAZO_CVM (pipeline sempre disponivel) pro mesmo periodo
    prazo_novo = _evento_sintetico(status=STATUS_PRAZO_CVM, data_evento=date(2026, 11, 14))
    resultado = aplicar_cache_resiliente([prazo_novo])
    _checar("v2.8 fonte melhor indisponivel -> NUNCA regride pra PRAZO_CVM, mantem o CONFIRMADO anterior",
             resultado[0]["status"] == STATUS_CONFIRMADO, f"(status={resultado[0]['status']})")
    _checar("v2.8b evento resgatado do cache vem marcado como possivelmente desatualizado (nunca escondido)",
             resultado[0].get("_pode_estar_desatualizado") is True)
    eventos_mod._cache_eventos().clear()


def test_v2_9_cache_evita_recalculo_sem_necessidade():
    eventos_mod._cache_eventos().clear()
    evento = _evento_sintetico(status=STATUS_PRAZO_CVM)
    aplicar_cache_resiliente([evento])
    chave = (evento["ticker"], evento["periodo"])
    _checar("v2.9 cache de ultimo-dado-valido grava a chave (ticker,periodo) depois da 1a chamada",
             chave in eventos_mod._cache_eventos())
    eventos_mod._cache_eventos().clear()


def test_v2_10_evento_antigo_confirmado_nao_vira_prazo_de_novo():
    # mesmo cenario do v2.8, nomeado conforme pedido explicito da fase
    eventos_mod._cache_eventos().clear()
    confirmado = _evento_sintetico(status=STATUS_CONFIRMADO, data_evento=date(2026, 10, 20), fonte="Petrobras RI")
    aplicar_cache_resiliente([confirmado])
    prazo = _evento_sintetico(status=STATUS_PRAZO_CVM, data_evento=date(2026, 11, 14))
    resultado = aplicar_cache_resiliente([prazo])
    _checar("v2.10 evento ja' CONFIRMADO anteriormente nao regride pra PRAZO_CVM numa consulta seguinte",
             resultado[0]["status"] == STATUS_CONFIRMADO)
    eventos_mod._cache_eventos().clear()


def test_v2_11_watchlist_prioriza_confiabilidade():
    import ui.calendario_tab as calendario_tab_mod
    eventos = [
        _evento_sintetico(ticker="ABCD4", status=STATUS_PRAZO_CVM, data_evento=date(2026, 10, 5)),
        _evento_sintetico(ticker="PETR4", status=STATUS_CONFIRMADO, data_evento=date(2026, 10, 20)),
        _evento_sintetico(ticker="VALE3", status=STATUS_ESTIMADO, data_evento=date(2026, 10, 10)),
    ]
    ordenado = sorted(eventos, key=lambda e: (-calendario_tab_mod.PRIORIDADE_STATUS[e["status"]], e["data"]))
    _checar("v2.11 ordenacao da watchlist prioriza CONFIRMADO > ESTIMADO > PRAZO_CVM (nao so' data)",
             [e["status"] for e in ordenado] == [STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM],
             f"(ordem={[e['status'] for e in ordenado]})")


# ============================================================
# FECHAMENTO DO CICLO (2026-10-05): calcular_proximo_resultado agora le
# o que o coletor (data/eventos_coleta.py) ja persistiu em
# eventos_resultados (sql/eventos.sql) antes de cair pro PRAZO_CVM -
# fecha o ciclo coleta->consumo que ate aqui so' tinha o lado da escrita
# testado (ver tests/test_eventos_coleta.py). Mocka
# _buscar_evento_persistido diretamente (mesmo nivel dos demais testes
# deste arquivo) - sem chamada de rede/Supabase real.
# ============================================================

def _linha_persistida(status, data_evento, fonte, url=None):
    return {"ticker": "PETR4", "periodo": "3T26", "data_evento": data_evento,
            "status": status, "fonte": fonte, "url_fonte": url,
            "coletado_em": "2026-10-03T12:00:00+00:00"}


def test_leitura_1_confirmado_persistido_e_usado_em_vez_do_prazo_cvm():
    linha = _linha_persistida(STATUS_CONFIRMADO, "2026-10-20", "Petrobras RI", "https://ri.petrobras.com.br")
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=linha):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("leitura1a CONFIRMADO persistido pelo coletor e' usado (nao PRAZO_CVM)",
             evento["status"] == STATUS_CONFIRMADO, f"(status={evento['status']})")
    _checar("leitura1b data vem da linha persistida (20/10), nao do prazo CVM (14/11)",
             evento["data"] == date(2026, 10, 20), f"(data={evento['data']})")
    _checar("leitura1c fonte/origem_url vem da linha persistida (nunca escondida)",
             evento["fonte"] == "Petrobras RI" and evento["origem_url"] == "https://ri.petrobras.com.br")


def test_leitura_2_estimado_persistido_e_usado_em_vez_do_prazo_cvm():
    linha = _linha_persistida(STATUS_ESTIMADO, "2026-10-25", "Reuters", "https://reuters.example.com/n1")
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=linha):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("leitura2 ESTIMADO persistido pelo coletor e' usado (nao PRAZO_CVM)",
             evento["status"] == STATUS_ESTIMADO and evento["data"] == date(2026, 10, 25))


def test_leitura_3_nada_persistido_cai_pro_prazo_cvm():
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("leitura3 nada persistido ainda -> cai pro PRAZO_CVM (comportamento original preservado)",
             evento["status"] == STATUS_PRAZO_CVM)


def test_leitura_4_linha_persistida_malformada_nao_quebra_cai_pro_prazo_cvm():
    linha_sem_status = {"ticker": "PETR4", "periodo": "3T26", "data_evento": "2026-10-20", "fonte": "x"}  # falta 'status'
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=linha_sem_status):
        evento = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("leitura4a linha persistida malformada (campo ausente) nao quebra", evento is not None)
    _checar("leitura4b cai pro PRAZO_CVM com seguranca (nunca mostra um status invalido)",
             evento["status"] == STATUS_PRAZO_CVM)

    linha_data_invalida = _linha_persistida(STATUS_CONFIRMADO, "nao-e-uma-data", "Petrobras RI")
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="PETROBRAS"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=linha_data_invalida):
        evento2 = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    _checar("leitura4c data_evento invalida na linha persistida tambem cai pro PRAZO_CVM, nunca quebra",
             evento2["status"] == STATUS_PRAZO_CVM)


def test_leitura_5_supabase_fora_do_ar_na_leitura_cai_pro_prazo_cvm_sem_quebrar():
    with patch.object(eventos_mod, "obter_cliente", return_value=None):
        resultado = eventos_mod._buscar_evento_persistido("TESTE-CACHE-5", "3T26")
    _checar("leitura5 obter_cliente() None -> _buscar_evento_persistido retorna None sem excecao",
             resultado is None)


def test_leitura_6_erro_na_consulta_supabase_nao_quebra():
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.side_effect = Exception("fora do ar")
    with patch.object(eventos_mod, "obter_cliente", return_value=cliente):
        resultado = eventos_mod._buscar_evento_persistido("TESTE-CACHE-6", "3T26")
    _checar("leitura6 excecao na consulta (banco indisponivel/erro de rede) -> None, nunca propaga", resultado is None)


# ============================================================
# PERFORMANCE (2026-10-05): calcular_calendario fazia 1 consulta
# SEQUENCIAL ao Supabase por ticker (eventos_resultados) e resolvia o
# nome da empresa via yfinance (rede) pra TODO ticker, mesmo os mais
# comuns ja curados em config - com 13 tickers isso levava ~17s.
# Corrigido: 1 UNICA consulta em lote (nao importa quantos tickers) +
# cascata barata de nome antes do fallback de rede. Testes abaixo
# confirmam o N->1 na consulta e o 0-rede pra tickers conhecidos.
# ============================================================

def test_perf_1_calendario_faz_so_1_consulta_ao_supabase_independente_do_numero_de_tickers():
    chamadas_query = []

    class _ClienteContador:
        def table(self, nome):
            chamadas_query.append(nome)
            return self
        def select(self, *_a, **_k):
            return self
        def in_(self, *_a, **_k):
            return self
        def execute(self):
            resp = MagicMock()
            resp.data = []
            return resp

    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "_nome_empresa", return_value="X"), \
         patch.object(eventos_mod, "obter_cliente", return_value=_ClienteContador()):
        calcular_calendario(["PETR4", "VALE3", "ITUB4", "BBAS3", "WEGE3"], hoje=date(2026, 10, 1))
    _checar("perf1 calendario com 5 tickers faz exatamente 1 consulta ao Supabase (nao 5)",
             chamadas_query.count("eventos_resultados") == 1, f"(chamadas={chamadas_query})")


def test_perf_2_nome_empresa_cascata_nao_bate_em_rede_pra_ticker_conhecido():
    chamadas_rede = []
    with patch.object(eventos_mod, "obter_nome_yf", side_effect=lambda t: chamadas_rede.append(t) or "NUNCA DEVERIA CHEGAR AQUI"):
        nome = eventos_mod._nome_empresa("PETR4")
    _checar("perf2a ticker conhecido (config/B3) resolve nome sem chamar obter_nome_yf", chamadas_rede == [])
    _checar("perf2b nome resolvido e' o curado (Petrobras), nao o fallback de rede", nome == "Petrobras", f"(nome={nome!r})")


def test_perf_3_nome_empresa_cai_pro_fallback_de_rede_so_pra_ticker_desconhecido():
    chamadas_rede = []
    with patch.object(eventos_mod, "obter_nome_yf", side_effect=lambda t: chamadas_rede.append(t) or "Empresa Desconhecida Ltda"):
        nome = eventos_mod._nome_empresa("ZZZZ99")
    _checar("perf3a ticker fora de config/B3 cai pro fallback de rede (obter_nome_yf chamado)", chamadas_rede == ["ZZZZ99"])
    _checar("perf3b nome do fallback e' retornado normalmente", nome == "Empresa Desconhecida Ltda")


def test_perf_4_resultado_final_identico_com_ou_sem_prebusca_em_lote():
    """Garante que o CAMINHO RAPIDO (calcular_calendario, com prebusca em
    lote) e o CAMINHO ISOLADO (calcular_proximo_resultado chamado direto,
    sem prebusca - uso de data/eventos_coleta.py) produzem o MESMO
    resultado pro mesmo ticker - a otimizacao nunca muda o dado."""
    linha = {"ticker": "PETR4", "periodo": "3T26", "data_evento": "2026-10-20",
             "status": STATUS_CONFIRMADO, "fonte": "Petrobras RI", "url_fonte": "https://ri.petrobras.com.br"}
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "_nome_empresa", return_value="Petrobras"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        isolado = calcular_proximo_resultado("PETR4", hoje=date(2026, 10, 1))
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "_nome_empresa", return_value="Petrobras"):
        em_lote = calcular_proximo_resultado(
            "PETR4", hoje=date(2026, 10, 1),
            _periodo_prebuscado=(2026, 3), _persistidos_prebuscados={("PETR4", "3T26"): linha},
        )
    _checar("perf4a caminho em lote com persistido encontrado -> CONFIRMADO", em_lote["status"] == STATUS_CONFIRMADO)
    _checar("perf4b data/fonte identicas as da linha persistida (mesma regra do caminho isolado)",
             em_lote["data"] == date(2026, 10, 20) and em_lote["fonte"] == "Petrobras RI")
    _checar("perf4c caminho isolado (sem prebusca) continua funcionando igual (fallback PRAZO_CVM, nada persistido)",
             isolado["status"] == STATUS_PRAZO_CVM)


# ============================================================
# SNAPSHOT do calendario (2026-10-05): a UI (ui/calendario_tab.py) le
# so' o snapshot persistido pelo coletor (coletor_local.py) - nunca
# recalcula/coleta ao renderizar ou navegar. Testes abaixo mockam
# obter_snapshot_calendario/calcular_calendario/obter_cliente - sem
# chamada de rede.
# ============================================================

def _evento_sint(ticker="PETR4", periodo="3T26", status=STATUS_CONFIRMADO, data_evento=None, fonte="fonte teste"):
    return {
        "ticker": ticker, "empresa": "EMPRESA TESTE", "periodo": periodo,
        "data": data_evento or date(2026, 10, 20), "horario": None,
        "status": status, "fonte": fonte, "origem_url": None, "tipo_evento": "RESULTADO",
        "coletado_em": None,
    }


def test_snap_1_cacheado_le_do_snapshot_sem_recalcular_quando_tudo_coberto():
    linha_a = eventos_mod._evento_para_json(_evento_sint(ticker="PETR4", data_evento=date(2026, 10, 20)))
    linha_b = eventos_mod._evento_para_json(_evento_sint(ticker="VALE3", data_evento=date(2026, 11, 5)))
    chamadas_live = []
    with patch.object(eventos_mod, "obter_snapshot_calendario", return_value={"eventos": [linha_a, linha_b]}), \
         patch.object(eventos_mod, "calcular_calendario", side_effect=lambda *a, **k: chamadas_live.append(a) or []):
        eventos = calcular_calendario_cacheado(["PETR4", "VALE3"])
    _checar("snap1a nenhuma chamada ao calculo em tempo real (os 2 tickers estao no snapshot)", chamadas_live == [])
    _checar("snap1b os 2 eventos do snapshot sao retornados", {e["ticker"] for e in eventos} == {"PETR4", "VALE3"})
    _checar("snap1c datas desserializadas como date (nao string)", all(isinstance(e["data"], date) for e in eventos))


def test_snap_2_ticker_fora_do_snapshot_cai_pro_calculo_isolado_so_pra_ele():
    linha_a = eventos_mod._evento_para_json(_evento_sint(ticker="PETR4"))
    evento_xpto = _evento_sint(ticker="XPTO9", status=STATUS_PRAZO_CVM, data_evento=date(2026, 11, 14))
    chamadas_live = []

    def _calc(tickers, hoje=None):
        chamadas_live.append(list(tickers))
        return [evento_xpto]

    with patch.object(eventos_mod, "obter_snapshot_calendario", return_value={"eventos": [linha_a]}), \
         patch.object(eventos_mod, "calcular_calendario", side_effect=_calc):
        eventos = calcular_calendario_cacheado(["PETR4", "XPTO9"])
    _checar("snap2a calculo em tempo real chamado SO' com o ticker fora do snapshot",
             chamadas_live == [["XPTO9"]], f"(chamadas={chamadas_live})")
    _checar("snap2b resultado inclui os 2 tickers (snapshot + calculado)",
             {e["ticker"] for e in eventos} == {"PETR4", "XPTO9"})


def test_snap_3_sem_snapshot_cai_pro_calculo_completo_de_sempre():
    chamadas_live = []

    def _calc(tickers, hoje=None):
        chamadas_live.append(list(tickers))
        return []

    with patch.object(eventos_mod, "obter_snapshot_calendario", return_value=None), \
         patch.object(eventos_mod, "calcular_calendario", side_effect=_calc):
        calcular_calendario_cacheado(["PETR4", "VALE3", "ITUB4"])
    _checar("snap3 sem snapshot (projeto novo) -> calcula o LOTE INTEIRO em tempo real, comportamento de sempre",
             chamadas_live == [["PETR4", "VALE3", "ITUB4"]])


def test_snap_4_salvar_nao_sobrescreve_quando_calculo_vazio():
    cliente = MagicMock()
    with patch.object(eventos_mod, "calcular_calendario", return_value=[]), \
         patch.object(eventos_mod, "obter_cliente", return_value=cliente):
        gravou = eventos_mod.salvar_snapshot_calendario(["PETR4"])
    _checar("snap4a calculo vazio -> salvar_snapshot_calendario retorna False", gravou is False)
    _checar("snap4b nenhum upsert e' chamado (preserva o snapshot anterior, nunca apaga com um calculo vazio)",
             cliente.table.called is False)


def test_snap_5_salvar_serializa_datas_antes_de_gravar():
    upserts = []
    cliente = MagicMock()
    cliente.table.return_value.upsert.side_effect = lambda payload, **k: (upserts.append(payload), MagicMock(execute=lambda: None))[1]
    evento = _evento_sint(data_evento=date(2026, 10, 20))
    with patch.object(eventos_mod, "calcular_calendario", return_value=[evento]), \
         patch.object(eventos_mod, "obter_cliente", return_value=cliente):
        gravou = eventos_mod.salvar_snapshot_calendario(["PETR4"])
    _checar("snap5a gravou com sucesso", gravou is True)
    _checar("snap5b payload gravado e' JSON-seguro (data serializada como string ISO, nao date object)",
             len(upserts) == 1 and isinstance(upserts[0]["eventos"][0]["data"], str))
    _checar("snap5c string da data e' exatamente 2026-10-20", upserts[0]["eventos"][0]["data"] == "2026-10-20")


def test_snap_6_json_roundtrip_preserva_data_e_fontes_alternativas():
    evento = _evento_sint(data_evento=date(2026, 10, 20))
    evento["_fontes_alternativas"] = [{"status": STATUS_PRAZO_CVM, "data": date(2026, 11, 14), "fonte": "CVM"}]
    serializado = eventos_mod._evento_para_json(evento)
    _checar("snap6a serializado: data e' string", isinstance(serializado["data"], str))
    _checar("snap6b serializado: data dentro de _fontes_alternativas tambem e' string",
             isinstance(serializado["_fontes_alternativas"][0]["data"], str))
    de_volta = eventos_mod._evento_de_json(serializado)
    _checar("snap6c round-trip: data volta a ser date", de_volta["data"] == date(2026, 10, 20))
    _checar("snap6d round-trip: data em _fontes_alternativas tambem volta a ser date",
             de_volta["_fontes_alternativas"][0]["data"] == date(2026, 11, 14))


def test_snap_7_obter_snapshot_supabase_fora_do_ar_retorna_none_sem_quebrar():
    with patch.object(eventos_mod, "obter_cliente", return_value=None):
        resultado = eventos_mod.obter_snapshot_calendario()
    _checar("snap7 Supabase fora do ar -> None, sem excecao", resultado is None)


def test_snap_8_cacheado_ignora_linha_malformada_no_snapshot_sem_quebrar():
    linha_boa = eventos_mod._evento_para_json(_evento_sint(ticker="PETR4"))
    linha_malformada = {"ticker": "VALE3"}  # sem 'data' - KeyError se nao tratado
    chamadas_live = []
    with patch.object(eventos_mod, "obter_snapshot_calendario", return_value={"eventos": [linha_boa, linha_malformada]}), \
         patch.object(eventos_mod, "calcular_calendario", side_effect=lambda tickers, hoje=None: (chamadas_live.append(list(tickers)), [])[1]):
        eventos = calcular_calendario_cacheado(["PETR4", "VALE3"])
    _checar("snap8a linha malformada nao quebra a leitura", True)
    _checar("snap8b PETR4 (linha boa) retornado normalmente", any(e["ticker"] == "PETR4" for e in eventos))
    _checar("snap8c VALE3 (linha malformada, ignorada) cai pro calculo isolado",
             chamadas_live == [["VALE3"]], f"(chamadas={chamadas_live})")


if __name__ == "__main__":
    # default global: CNPJ mapeado (ticker CVM-regulado "comum") - so'
    # test_7b sobrescreve isso localmente pra cobrir o caso sem CNPJ.
    with patch.object(eventos_mod, "obter_cnpj", return_value=_CNPJ_FAKE):
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
    print("TODOS OS TESTES DE EVENTOS/CALENDARIO PASSARAM")
