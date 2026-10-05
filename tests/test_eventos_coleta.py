# -*- coding: utf-8 -*-
"""Testes da fase COLETOR DE DATAS DE RESULTADOS (2026-10-02):
data/eventos_coleta.py - pipeline RI->NEWS->PRAZO_CVM e persistencia
(priorizacao/deduplicacao). Mocka toda chamada de rede (RI/NEWS) e o
cliente Supabase - nao faz requisicao real nem precisa de
.streamlit/secrets.toml.

Uso: python tests/test_eventos_coleta.py (python do .venv do projeto)."""
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.eventos_coleta as coleta_mod
from data.eventos import STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


# ============================================================
# extrair_data_do_periodo: nucleo deterministico (regex periodo+data)
# ============================================================

def test_extrai_data_quando_periodo_e_data_explicitos():
    texto = "A Comercial ABC comunica que os resultados do 3T26 serão divulgados em 20/10/2026 após o fechamento."
    data = coleta_mod.extrair_data_do_periodo(texto, 2026, 3)
    _checar("extrai data numerica quando periodo e data (com ano) estao proximos", data == date(2026, 10, 20), f"(data={data})")


def test_extrai_data_por_extenso():
    texto = "Resultados do 3T26 confirmados para o dia 20 de outubro de 2026."
    data = coleta_mod.extrair_data_do_periodo(texto, 2026, 3)
    _checar("extrai data por extenso (DD de MES de AAAA)", data == date(2026, 10, 20), f"(data={data})")


def test_7_data_de_periodo_errado_nao_e_associada():
    """Pedido explicito: 'data de período errado não ser associada ao
    evento'. Texto so' menciona 2T26 (periodo ERRADO pro que estamos
    procurando, 3T26) - nunca deve achar a data, mesmo ela existindo no
    texto perto de 2T26."""
    texto = "Os resultados do 2T26 foram divulgados em 15/08/2026. Aguardamos o calendario do proximo trimestre."
    data = coleta_mod.extrair_data_do_periodo(texto, 2026, 3)
    _checar("7 texto so' com periodo ERRADO (2T26) nunca retorna data pro periodo pedido (3T26)", data is None)


def test_data_sem_ano_explicito_nunca_e_aceita():
    texto = "O resultado do 3T26 sai dia 20 de outubro, fiquem atentos."
    data = coleta_mod.extrair_data_do_periodo(texto, 2026, 3)
    _checar("data sem ANO explicito nunca e' aceita (regra: nunca inferir ano)", data is None)


def test_data_fora_da_janela_de_sanidade_e_descartada():
    # 3T26 vai de jul-set/2026, prazo CVM (ITR) = 30/09+45d = 14/11/2026.
    # Uma data de 2020 "por perto" no texto e' claramente erro de pagina,
    # nunca deveria ser aceita mesmo com o periodo certo mencionado.
    texto = "Resultados do 3T26. Nota: em 10/03/2020 a empresa mudou de nome."
    data = coleta_mod.extrair_data_do_periodo(texto, 2026, 3)
    _checar("data fora da janela de sanidade do periodo (ex: ano 2020) e' descartada", data is None)


def test_periodo_nao_mencionado_retorna_none():
    texto = "A empresa divulgou um comunicado qualquer em 20/10/2026 sobre outro assunto."
    data = coleta_mod.extrair_data_do_periodo(texto, 2026, 3)
    _checar("periodo nao mencionado em lugar nenhum do texto -> None", data is None)


# ============================================================
# tentar_ri / tentar_news (RI->NEWS, com rede mockada)
# ============================================================

def test_1_ri_confirmado_quando_pagina_tem_data_clara():
    html = "<html><body>Resultados do 3T26 confirmados para 20/10/2026.</body></html>"
    resp_fake = MagicMock(text=html)
    resp_fake.raise_for_status.return_value = None
    with patch.object(coleta_mod, "obter_url_ri", return_value="https://ri.example.com"), \
         patch.object(coleta_mod.cffi_requests, "get", return_value=resp_fake):
        evento = coleta_mod.tentar_ri("PETR4", "Petrobras", 2026, 3)
    _checar("1a RI com data clara vira CONFIRMADO", evento is not None and evento["status"] == STATUS_CONFIRMADO)
    _checar("1b data extraida corretamente", evento["data"] == date(2026, 10, 20))
    _checar("1c origem_url e' a URL oficial de RI (nunca inventada)", evento["origem_url"] == "https://ri.example.com")
    _checar("1d fonte menciona a empresa + RI", "RI" in evento["fonte"])


def test_6_ri_sem_url_oficial_ou_fonte_bloqueada_retorna_none():
    with patch.object(coleta_mod, "obter_url_ri", return_value=None):
        evento = coleta_mod.tentar_ri("XXXX4", "Empresa X", 2026, 3)
    _checar("6a sem URL oficial de RI -> None (nunca inventa)", evento is None)

    with patch.object(coleta_mod, "obter_url_ri", return_value="https://ri.example.com"), \
         patch.object(coleta_mod.cffi_requests, "get", side_effect=Exception("timeout/bloqueado")):
        evento2 = coleta_mod.tentar_ri("PETR4", "Petrobras", 2026, 3)
    _checar("6b fonte RI bloqueada/indisponivel -> None (segue pra proxima fonte, nunca quebra)", evento2 is None)


def test_2_news_estimado_quando_noticia_confiavel_tem_data_clara():
    entry = {
        "title": "Empresa X anuncia resultado do 3T26 - Reuters",
        "summary": "A divulgação será em 25/10/2026, segundo comunicado.",
        "link": "https://reuters.example.com/n1",
        "source": {"title": "Reuters"},
    }
    with patch.object(coleta_mod, "_buscar_feed", return_value=[entry]), \
         patch.object(coleta_mod, "eh_fonte_confiavel", return_value=True):
        evento = coleta_mod.tentar_news("XPTO4", "Empresa X", 2026, 3)
    _checar("2a noticia de fonte confiavel com data clara vira ESTIMADO", evento is not None and evento["status"] == STATUS_ESTIMADO)
    _checar("2b data extraida da noticia corretamente", evento["data"] == date(2026, 10, 25))
    _checar("2c origem_url e' o link da noticia", evento["origem_url"] == "https://reuters.example.com/n1")


def test_news_fonte_nao_confiavel_e_ignorada():
    entry = {
        "title": "Resultado do 3T26 sai em 25/10/2026 - Blog Qualquer",
        "summary": "", "link": "https://blog.example.com/n1", "source": {"title": "Blog Qualquer"},
    }
    with patch.object(coleta_mod, "_buscar_feed", return_value=[entry]), \
         patch.object(coleta_mod, "eh_fonte_confiavel", return_value=False):
        evento = coleta_mod.tentar_news("XPTO4", "Empresa X", 2026, 3)
    _checar("fonte NAO confiavel nunca vira ESTIMADO, mesmo com data clara no titulo", evento is None)


def test_news_sem_resultado_nenhum_retorna_none():
    with patch.object(coleta_mod, "_buscar_feed", return_value=None):
        evento = coleta_mod.tentar_news("XPTO4", "Empresa X", 2026, 3)
    _checar("busca de noticia sem resultado (None) -> None, nunca quebra", evento is None)


# ============================================================
# coletar_evento: pipeline completo RI->NEWS->PRAZO_CVM
# ============================================================

def test_3_nenhuma_fonte_mantem_prazo_cvm():
    prazo_evento = {
        "ticker": "PETR4", "empresa": "Petrobras", "periodo": "3T26", "data": date(2026, 11, 14),
        "horario": None, "status": STATUS_PRAZO_CVM, "fonte": "CVM — prazo regulatório",
        "origem_url": None, "tipo_evento": "RESULTADO", "coletado_em": datetime.now(timezone.utc),
    }
    with patch.object(coleta_mod, "periodo_pendente", return_value=(2026, 3)), \
         patch.object(coleta_mod, "obter_nome_yf", return_value="Petrobras"), \
         patch.object(coleta_mod, "tentar_ri", return_value=None), \
         patch.object(coleta_mod, "tentar_news", return_value=None), \
         patch.object(coleta_mod, "_calcular_proximo_resultado", return_value=prazo_evento):
        evento = coleta_mod.coletar_evento("PETR4")
    _checar("3 RI e NEWS falham -> mantem PRAZO_CVM (fallback final)", evento["status"] == STATUS_PRAZO_CVM)


def test_ri_tem_prioridade_sobre_news():
    evento_ri = {"ticker": "PETR4", "status": STATUS_CONFIRMADO, "periodo": "3T26", "data": date(2026, 10, 20),
                 "empresa": "Petrobras", "horario": None, "fonte": "Petrobras RI", "origem_url": "https://ri.example.com",
                 "tipo_evento": "RESULTADO", "coletado_em": datetime.now(timezone.utc)}
    chamou_news = []
    with patch.object(coleta_mod, "periodo_pendente", return_value=(2026, 3)), \
         patch.object(coleta_mod, "obter_nome_yf", return_value="Petrobras"), \
         patch.object(coleta_mod, "tentar_ri", return_value=evento_ri), \
         patch.object(coleta_mod, "tentar_news", side_effect=lambda *a: chamou_news.append(1)):
        evento = coleta_mod.coletar_evento("PETR4")
    _checar("RI com sucesso -> NUNCA tenta NEWS (RI tem prioridade)", chamou_news == [])
    _checar("retorna o evento CONFIRMADO do RI", evento["status"] == STATUS_CONFIRMADO)


def test_periodo_pendente_none_retorna_none_sem_tentar_nada():
    with patch.object(coleta_mod, "periodo_pendente", return_value=None):
        evento = coleta_mod.coletar_evento("PETR4")
    _checar("sem periodo pendente calculavel (fonte CVM fora do ar) -> None, nunca inventa", evento is None)


# ============================================================
# persistencia: priorizacao/deduplicacao (Supabase mockado)
# ============================================================

def _cliente_mock(evento_salvo):
    cliente = MagicMock()
    resp = MagicMock()
    resp.data = [evento_salvo] if evento_salvo else []
    cliente.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = resp
    upserts = []
    cliente.table.return_value.upsert.side_effect = lambda payload, **k: (upserts.append(payload), MagicMock(execute=lambda: None))[1]
    return cliente, upserts


def _evento(status, data_evento=date(2026, 10, 20), fonte="fonte teste", ticker="PETR4", periodo="3T26", url=None):
    return {
        "ticker": ticker, "empresa": "Petrobras", "periodo": periodo, "data": data_evento,
        "horario": None, "status": status, "fonte": fonte, "origem_url": url,
        "tipo_evento": "RESULTADO", "coletado_em": datetime.now(timezone.utc),
    }


def test_4_confirmado_substitui_estimado():
    anterior = {"ticker": "PETR4", "periodo": "3T26", "status": STATUS_ESTIMADO, "data_evento": "2026-10-25"}
    cliente, upserts = _cliente_mock(anterior)
    novo = _evento(STATUS_CONFIRMADO, data_evento=date(2026, 10, 20), fonte="Petrobras RI")
    with patch.object(coleta_mod, "obter_cliente", return_value=cliente):
        gravou = coleta_mod.salvar_evento_se_mais_confiavel(novo)
    _checar("4 CONFIRMADO substitui ESTIMADO anterior (grava)", gravou is True)
    _checar("4b upsert gravado com status CONFIRMADO", len(upserts) == 1 and upserts[0]["status"] == STATUS_CONFIRMADO)


def test_estimado_nunca_substitui_confirmado_existente():
    anterior = {"ticker": "PETR4", "periodo": "3T26", "status": STATUS_CONFIRMADO, "data_evento": "2026-10-20"}
    cliente, upserts = _cliente_mock(anterior)
    novo = _evento(STATUS_ESTIMADO, data_evento=date(2026, 10, 25), fonte="Reuters")
    with patch.object(coleta_mod, "obter_cliente", return_value=cliente):
        gravou = coleta_mod.salvar_evento_se_mais_confiavel(novo)
    _checar("ESTIMADO NUNCA regride um CONFIRMADO ja' salvo (nao grava)", gravou is False)
    _checar("nenhum upsert e' chamado quando a mudanca regrediria confiabilidade", upserts == [])


def test_5_deduplicacao_mesmo_status_e_data_nao_regrava():
    anterior = {"ticker": "PETR4", "periodo": "3T26", "status": STATUS_CONFIRMADO, "data_evento": "2026-10-20"}
    cliente, upserts = _cliente_mock(anterior)
    novo = _evento(STATUS_CONFIRMADO, data_evento=date(2026, 10, 20), fonte="Petrobras RI")
    with patch.object(coleta_mod, "obter_cliente", return_value=cliente):
        gravou = coleta_mod.salvar_evento_se_mais_confiavel(novo)
    _checar("5 mesmo status+data (idempotente) nao gera upsert duplicado", gravou is False and upserts == [])


def test_prazo_cvm_nunca_e_persistido():
    cliente, upserts = _cliente_mock(None)
    evento_prazo = _evento(STATUS_PRAZO_CVM)
    with patch.object(coleta_mod, "obter_cliente", return_value=cliente):
        gravou = coleta_mod.salvar_evento_se_mais_confiavel(evento_prazo)
    _checar("PRAZO_CVM nunca e' persistido na tabela (so' CONFIRMADO/ESTIMADO)", gravou is False and upserts == [])


def test_8_fonte_indisponivel_na_persistencia_nao_quebra():
    with patch.object(coleta_mod, "obter_cliente", return_value=None):
        gravou = coleta_mod.salvar_evento_se_mais_confiavel(_evento(STATUS_CONFIRMADO))
    _checar("8 Supabase indisponivel (obter_cliente=None) -> retorna False sem excecao", gravou is False)


# ============================================================
# DIAGNOSTICO (2026-10-05): achado real em producao - a tabela
# eventos_resultados nao existia no Supabase (sql/eventos.sql nunca
# tinha sido rodado la), e tanto leitura quanto escrita degradavam em
# silencio pro mesmo caminho de "nada encontrado", escondendo o
# problema por dias. tabela_eventos_disponivel existe so' pra tornar
# esse caso diagnosticavel no log do coletor (coletor_local.py) - nunca
# decide o pipeline RI->NEWS->PRAZO_CVM em si.
# ============================================================

def test_9_tabela_disponivel_quando_consulta_trivial_funciona():
    cliente = MagicMock()
    with patch.object(coleta_mod, "obter_cliente", return_value=cliente):
        disponivel = coleta_mod.tabela_eventos_disponivel()
    _checar("9a tabela responde a consulta trivial -> True", disponivel is True)


def test_9b_tabela_indisponivel_quando_consulta_falha():
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.limit.return_value.execute.side_effect = Exception(
        "PGRST205: Could not find the table 'public.eventos_resultados' in the schema cache"
    )
    with patch.object(coleta_mod, "obter_cliente", return_value=cliente):
        disponivel = coleta_mod.tabela_eventos_disponivel()
    _checar("9b tabela ausente/erro de schema -> False (distinto de 'Supabase fora do ar')", disponivel is False)


def test_9c_supabase_fora_do_ar_retorna_none_nao_false():
    with patch.object(coleta_mod, "obter_cliente", return_value=None):
        disponivel = coleta_mod.tabela_eventos_disponivel()
    _checar("9c Supabase em si fora do ar -> None (distinto de 'tabela ausente')", disponivel is None)


def test_9d_coletar_eventos_universo_reporta_tabela_disponivel_nas_stats():
    with patch.object(coleta_mod, "periodo_pendente", return_value=None), \
         patch.object(coleta_mod, "tabela_eventos_disponivel", return_value=False):
        stats = coleta_mod.coletar_eventos_universo(["PETR4"])
    _checar("9d stats de coletar_eventos_universo incluem tabela_disponivel (diagnostico pro log)",
             stats["tabela_disponivel"] is False)


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DO COLETOR DE EVENTOS PASSARAM")
