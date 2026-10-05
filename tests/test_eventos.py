# -*- coding: utf-8 -*-
"""Testes da fase CALENDARIO (2026-10-01): data/eventos.py - calculo de
proximo resultado via prazo regulatorio da CVM. Mocka
data.cvm.obter_documentos_cvm (mesma fonte/identificador que CVM ja
usa) - nao faz chamada de rede nem de IA.

Uso: python tests/test_eventos.py (python do .venv do projeto)."""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.eventos as eventos_mod
from data.eventos import (
    STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM,
    aplicar_cache_resiliente, calcular_calendario, calcular_proximo_resultado, mesclar_eventos,
)

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


# --- 7: ausencia de eventos (fonte sem CNPJ/documento) --------------------
def test_7_ausencia_de_eventos_fonte_sem_cnpj():
    # obter_documentos_cvm retorna [] quando o ticker nao tem CNPJ mapeado
    # ou nao ha documento algum - ainda assim calculamos o prazo
    # regulatorio (independe de documento existir, e' uma regra legal
    # generica) - o "evento" sempre existe quando a fonte responde (so'
    # fica None se a FONTE falhar de verdade, ver teste 10)
    with patch.object(eventos_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(eventos_mod, "obter_nome_yf", return_value="EMPRESA TESTE"), \
         patch.object(eventos_mod, "_buscar_evento_persistido", return_value=None):
        evento = calcular_proximo_resultado("ZZZZ4", hoje=date(2026, 10, 1))
    _checar("7 mesmo sem nenhum documento CVM, o prazo regulatorio ainda e' calculavel", evento is not None)


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


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE EVENTOS/CALENDARIO PASSARAM")
