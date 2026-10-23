# -*- coding: utf-8 -*-
"""Testes de data/radar.py (camada de agregação do RADAR) - mocka toda
fonte de dado (Supabase/yfinance/CVM/calendário), nunca faz chamada de
rede real. Mesmo padrão de tests/test_coletores_status.py (funções
test_N_descricao, roda com pytest OU direto).

Uso: python tests/test_radar.py (python do .venv do projeto)."""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

import data.mercado as mercado_mod
import data.radar as radar_mod
from data.eventos import STATUS_ESTIMADO, STATUS_PRAZO_CVM

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


def _limpar_caches():
    radar_mod.mudancas_tese.clear()
    radar_mod.linha_valuation.clear()
    radar_mod.comparaveis_setor.clear()
    radar_mod.evidencias_recentes.clear()


def _hoje():
    return datetime.now(radar_mod._TZ_SP).date()


# ============================================================
# parsing/normalizacao de data
# ============================================================

def test_1_parse_data_variantes():
    _checar("1a date-only ISO", radar_mod._parse_data("2026-10-01") == date(2026, 10, 1))
    _checar("1b datetime completo com Z", radar_mod._parse_data("2026-10-01T13:30:00Z") is not None)
    _checar("1c objeto date direto", radar_mod._parse_data(date(2026, 1, 5)) == date(2026, 1, 5))
    _checar("1d None -> None", radar_mod._parse_data(None) is None)
    _checar("1e string invalida -> None", radar_mod._parse_data("nao-e-data") is None)


def test_2_parse_datetime_variantes():
    dt = radar_mod._parse_datetime("2026-10-01T13:30:00+00:00")
    _checar("2a timezone-aware convertido pra BRT", dt is not None and dt.tzinfo is not None)
    _checar("2b sem timezone assume utc e nao quebra", radar_mod._parse_datetime("2026-10-01T13:30:00") is not None)
    _checar("2c None -> None", radar_mod._parse_datetime(None) is None)
    _checar("2d invalido -> None", radar_mod._parse_datetime("xxx") is None)


# ============================================================
# A. Mudancas de tese: descricao/dedup/janela/FATO vs CALCULO
# ============================================================

def test_3_descricao_mudanca_recomendacao():
    _checar("3a mudou de verdade", radar_mod._descricao_mudanca_recomendacao({"recomendacao": "NEUTRO"}, {"recomendacao": "COMPRA"}) == "Recomendação mudou de NEUTRO para COMPRA")
    _checar("3b iniciada (sem anterior)", radar_mod._descricao_mudanca_recomendacao({"recomendacao": None}, {"recomendacao": "COMPRA"}) == "Recomendação iniciada em COMPRA")
    _checar("3c sem mudanca -> None", radar_mod._descricao_mudanca_recomendacao({"recomendacao": "COMPRA"}, {"recomendacao": "COMPRA"}) is None)
    _checar("3d nova tambem None -> None", radar_mod._descricao_mudanca_recomendacao({"recomendacao": "COMPRA"}, {"recomendacao": None}) is None)


def test_4_descricao_mudanca_preco_alvo():
    subiu = radar_mod._descricao_mudanca_preco_alvo({"preco_alvo": 10.0}, {"preco_alvo": 15.0})
    caiu = radar_mod._descricao_mudanca_preco_alvo({"preco_alvo": 20.0}, {"preco_alvo": 12.5})
    _checar("4a subiu", subiu is not None and "subiu" in subiu)
    _checar("4b caiu", caiu is not None and "caiu" in caiu)
    _checar("4c iniciado", "iniciado" in radar_mod._descricao_mudanca_preco_alvo({"preco_alvo": None}, {"preco_alvo": 10.0}))
    _checar("4d igual -> None", radar_mod._descricao_mudanca_preco_alvo({"preco_alvo": 10.0}, {"preco_alvo": 10.0}) is None)
    _checar("4e novo None -> None", radar_mod._descricao_mudanca_preco_alvo({"preco_alvo": 10.0}, {"preco_alvo": None}) is None)


def test_5_potencial_calculado_casos_limite():
    with patch.object(radar_mod, "obter_cotacao", return_value={"preco": 20.0, "erro": None}):
        pot, motivo = radar_mod._potencial_calculado("PETR4", 24.0)
        _checar("5a potencial calculado corretamente", pot is not None and abs(pot - 20.0) < 0.01, f"pot={pot}")
    _checar("5b sem preco-alvo -> None + motivo", radar_mod._potencial_calculado("PETR4", None) == (None, "sem preço-alvo pra calcular potencial"))
    with patch.object(radar_mod, "obter_cotacao", return_value={"erro": "sem dado"}):
        pot, motivo = radar_mod._potencial_calculado("PETR4", 24.0)
        _checar("5c cotacao com erro -> None + motivo", pot is None and motivo != "")


def test_6_mudancas_research_dedup_e_janela():
    _limpar_caches()
    hoje = _hoje()
    recente = (hoje - timedelta(days=2)).isoformat() + "T10:00:00+00:00"
    antigo = (hoje - timedelta(days=40)).isoformat() + "T10:00:00+00:00"
    # historico_ticker retorna mais recente primeiro (ver docstring real)
    historico_fake = [
        {"recomendacao": "COMPRA", "preco_alvo": 30.0, "potencial_pct": 10.0, "capturado_em": recente},
        {"recomendacao": "NEUTRO", "preco_alvo": 25.0, "potencial_pct": None, "capturado_em": antigo},
    ]
    with patch.object(radar_mod, "historico_ticker", return_value=historico_fake), \
         patch.object(radar_mod, "obter_cotacao", return_value={"preco": 28.0, "erro": None}):
        alertas = radar_mod._mudancas_research(("PETR4",), hoje - timedelta(days=7))
    _checar("6a 1 mudanca dentro da janela de 7 dias", len(alertas) == 1, f"len={len(alertas)}")
    _checar("6b tipo_evidencia FATO", alertas[0]["tipo_evidencia"] == radar_mod.TIPO_FATO)
    _checar("6c potencial_pct_fonte preservado (nao sobrescrito)", alertas[0]["potencial_pct_fonte"] == 10.0)
    _checar("6d potencial_pct_calculado tambem presente, rotulado como calculo interno", alertas[0]["potencial_pct_calculado"] is not None)

    with patch.object(radar_mod, "historico_ticker", return_value=historico_fake), \
         patch.object(radar_mod, "obter_cotacao", return_value={"preco": 28.0, "erro": None}):
        alertas_30d_antes_do_corte = radar_mod._mudancas_research(("PETR4",), hoje - timedelta(days=50))
    _checar("6e janela maior inclui a mudanca antiga tambem (2 linhas = 1 transicao antiga + 1 recente)", len(alertas_30d_antes_do_corte) == 1)


def test_7_mudancas_cvm_filtra_fato_relevante_e_janela():
    _limpar_caches()
    hoje = _hoje()
    documentos = [
        {"ticker": "VALE3", "tipo": "FATO_RELEVANTE", "tipo_label": "Fato Relevante", "assunto": "Fusão anunciada", "data": hoje.isoformat(), "link": "https://cvm.gov.br/doc1"},
        {"ticker": "VALE3", "tipo": "COMUNICADO", "tipo_label": "Comunicado", "assunto": "Comunicado rotineiro", "data": hoje.isoformat(), "link": "https://cvm.gov.br/doc2"},
        {"ticker": "VALE3", "tipo": "FATO_RELEVANTE", "tipo_label": "Fato Relevante", "assunto": "Fato antigo", "data": (hoje - timedelta(days=100)).isoformat(), "link": "https://cvm.gov.br/doc3"},
    ]
    with patch.object(radar_mod, "obter_documentos_watchlist", return_value=(documentos, [])):
        alertas = radar_mod._mudancas_cvm(("VALE3",), hoje - timedelta(days=7))
    _checar("7a so' FATO_RELEVANTE dentro da janela entra (nao COMUNICADO, nao o antigo)", len(alertas) == 1, f"len={len(alertas)}")
    _checar("7b fonte_url e' o link real do documento", alertas[0]["fonte_url"] == "https://cvm.gov.br/doc1")
    _checar("7c tipo_evidencia FATO", alertas[0]["tipo_evidencia"] == radar_mod.TIPO_FATO)


def test_8_mudancas_tese_combina_ordena_e_vazio_honesto():
    _limpar_caches()
    with patch.object(radar_mod, "historico_ticker", return_value=[]), \
         patch.object(radar_mod, "obter_documentos_watchlist", return_value=([], [])):
        vazio = radar_mod.mudancas_tese(("PETR4",), "7 DIAS")
    _checar("8a sem nenhuma fonte com dado -> lista vazia (nunca inventa)", vazio == [])

    _limpar_caches()
    hoje = _hoje()
    documentos = [{"ticker": "PETR4", "tipo": "FATO_RELEVANTE", "tipo_label": "Fato Relevante", "assunto": "X", "data": hoje.isoformat(), "link": "https://x"}]
    historico_fake = [
        {"recomendacao": "COMPRA", "preco_alvo": 30.0, "potencial_pct": None, "capturado_em": (hoje - timedelta(days=1)).isoformat() + "T10:00:00+00:00"},
        {"recomendacao": "NEUTRO", "preco_alvo": 25.0, "potencial_pct": None, "capturado_em": (hoje - timedelta(days=3)).isoformat() + "T10:00:00+00:00"},
    ]
    with patch.object(radar_mod, "historico_ticker", return_value=historico_fake), \
         patch.object(radar_mod, "obter_documentos_watchlist", return_value=(documentos, [])), \
         patch.object(radar_mod, "obter_cotacao", return_value={"preco": 28.0, "erro": None}):
        alertas = radar_mod.mudancas_tese(("PETR4",), "7 DIAS")
    _checar("8b combina research + CVM", len(alertas) == 2, f"len={len(alertas)}")
    _checar("8c ordenado por data desc (mais recente primeiro)", alertas[0]["data_evento"] >= alertas[1]["data_evento"])


# ============================================================
# B. Valuation Radar - alertas de qualidade/staleness/casos-limite
# ============================================================

def test_9_alertas_qualidade_casos_limite():
    _checar("9a P/L negativo gera alerta", any("negativo" in a for a in radar_mod._alertas_qualidade({"pl": -5.0})))
    _checar("9b margem negativa gera alerta", any("margem" in a for a in radar_mod._alertas_qualidade({"margem_liquida": -1.0})))
    _checar("9c divida/ebitda alta gera alerta", any("dívida" in a for a in radar_mod._alertas_qualidade({"divida_liquida_ebitda": 6.2})))
    _checar("9d indicadores normais -> sem alerta", radar_mod._alertas_qualidade({"pl": 12.0, "margem_liquida": 8.0, "divida_liquida_ebitda": 1.5}) == [])
    _checar("9e todos None -> sem alerta (nao inventa problema por falta de dado)", radar_mod._alertas_qualidade({}) == [])


def test_10_indicadores_desatualizados():
    agora = datetime.now(timezone.utc)
    recente = {"_coletado_em": agora.isoformat()}
    antigo = {"_coletado_em": (agora - timedelta(hours=30)).isoformat()}
    sem_timestamp = {}
    _checar("10a recente -> nao desatualizado", radar_mod._indicadores_desatualizados(recente) is False)
    _checar("10b >24h -> desatualizado", radar_mod._indicadores_desatualizados(antigo) is True)
    _checar("10c sem timestamp (coleta de agora) -> nao desatualizado", radar_mod._indicadores_desatualizados(sem_timestamp) is False)


def test_11_linha_valuation_nao_chama_peers():
    """valuation_radar/linha_valuation NUNCA deve iterar o universo de
    pares do setor (isso e' comparaveis_setor, sob demanda/dialog) -
    carregamento sob demanda real, nao so' documentado."""
    _limpar_caches()
    chamadas = {"n": 0}

    def _fake_indicadores(ticker):
        chamadas["n"] += 1
        return {"pl": 10.0, "pvp": 1.5, "dividend_yield": 5.0, "roe": 15.0, "margem_liquida": 10.0, "divida_liquida_ebitda": 1.0, "valor_mercado": 1e9}

    with patch.object(radar_mod, "obter_cotacao", return_value={"preco": 30.0, "erro": None}), \
         patch.object(radar_mod, "obter_indicadores", side_effect=_fake_indicadores):
        linhas = radar_mod.valuation_radar(("PETR4", "VALE3"))
    _checar("11a 1 chamada de indicadores por ticker (sem N+1 de peers)", chamadas["n"] == 2, f"n={chamadas['n']}")
    _checar("11b retorna 1 linha por ticker", len(linhas) == 2)
    _checar("11c preco presente", linhas[0]["preco"] == 30.0)


def test_12_comparaveis_setor_insuficiente_e_mediana():
    _limpar_caches()

    def _poucos_pares(ticker):
        return {"pl": 10.0, "pvp": None, "dividend_yield": None}

    with patch.object(radar_mod.config, "IBOVESPA_SETORES", {"PETR4": "Petróleo e Gás", "PETR3": "Petróleo e Gás"}), \
         patch.object(radar_mod, "obter_indicadores", side_effect=_poucos_pares):
        comp = radar_mod.comparaveis_setor("PETR4")
    _checar("12a poucos pares -> insuficiente", comp["insuficiente"] is True, str(comp))

    _limpar_caches()
    setores_fake = {"AAA4": "Teste", "BBB4": "Teste", "CCC4": "Teste", "DDD4": "Teste", "ALVO4": "Teste"}

    def _varios_pares(ticker):
        valores = {"AAA4": 10.0, "BBB4": 12.0, "CCC4": 14.0, "DDD4": 20.0}
        return {"pl": valores.get(ticker), "pvp": 1.0, "dividend_yield": 5.0}

    with patch.object(radar_mod.config, "IBOVESPA_SETORES", setores_fake), \
         patch.object(radar_mod, "obter_indicadores", side_effect=_varios_pares):
        comp2 = radar_mod.comparaveis_setor("ALVO4")
    _checar("12b com >=3 pares validos, calcula mediana real", comp2["pl_mediana"] == 13.0, str(comp2))
    _checar("12c pares_considerados exclui o proprio ticker", comp2["pares_considerados"] == 4)


# ============================================================
# C. Catalisadores - combina calendario + proventos, sem duplicar
# ============================================================

def test_13_catalisadores_combina_e_respeita_janela():
    _limpar_caches()
    hoje = _hoje()
    eventos_calendario = [
        {"ticker": "PETR4", "empresa": "Petrobras", "data": hoje + timedelta(days=10), "status": STATUS_ESTIMADO, "fonte": "NEWS", "origem_url": "https://x1"},
        {"ticker": "PETR4", "empresa": "Petrobras", "data": hoje + timedelta(days=200), "status": STATUS_PRAZO_CVM, "fonte": "CVM", "origem_url": None},
    ]
    documentos = [
        {"ticker": "PETR4", "tipo": "PROVENTOS", "data": (hoje + timedelta(days=5)).isoformat(), "link": "https://cvm/prov"},
        {"ticker": "PETR4", "tipo": "COMUNICADO", "data": (hoje + timedelta(days=5)).isoformat(), "link": "https://cvm/com"},
    ]
    with patch.object(radar_mod, "calcular_calendario_cacheado", return_value=eventos_calendario), \
         patch.object(radar_mod, "obter_documentos_watchlist", return_value=(documentos, [])):
        cats = radar_mod.catalisadores(("PETR4",), dias_passado=7, dias_futuro=60)
    _checar("13a evento fora da janela (200 dias) excluido", all(c["categoria"] != "Resultado corporativo" or c["data"] <= hoje + timedelta(days=60) for c in cats))
    _checar("13b PROVENTOS entra como catalisador confirmado", any(c["categoria"] == "Proventos (dividendo/JCP)" and c["confirmado"] for c in cats))
    _checar("13c COMUNICADO (nao PROVENTOS) nao entra como catalisador", not any(c.get("fonte_url") == "https://cvm/com" for c in cats))
    _checar("13d resultado estimado dentro da janela entra", any(c["categoria"] == "Resultado corporativo" for c in cats))


# ============================================================
# D. Risco da carteira - stub honesto (sem posicao) e calculo real
# (com posicao cadastrada, tabela posicoes_carteira/data/posicoes.py)
# ============================================================

def test_14_risco_carteira_sem_posicao_nunca_finge_ter_carteira():
    with patch.object(radar_mod, "obter_posicoes", return_value=[]):
        info = radar_mod.risco_carteira("sub1", {"watchlist": ["PETR4", "VALE3"]})
    _checar("14a carteira_cadastrada False (ninguem cadastrou posicao)", info["carteira_cadastrada"] is False)
    _checar("14b watchlist_tamanho reflete prefs, nao inventa", info["watchlist_tamanho"] == 2)
    with patch.object(radar_mod, "obter_posicoes", return_value=[]):
        _checar("14c sem watchlist -> 0, sem excecao", radar_mod.risco_carteira("sub1", {})["watchlist_tamanho"] == 0)


def test_14d_risco_carteira_banco_indisponivel_distinto_de_vazio():
    with patch.object(radar_mod, "obter_posicoes", return_value=None):
        info = radar_mod.risco_carteira("sub1", {"watchlist": []})
    _checar("14d.1 carteira_cadastrada None (banco fora do ar, nao 'ninguem cadastrou')", info["carteira_cadastrada"] is None)
    _checar("14d.2 nunca finge que calculou algo", "concentracao_ativo" not in info)


def test_14e_risco_carteira_sem_cotacao_nenhuma_posicao_tem_preco():
    posicoes = [{"ticker": "PETR4", "quantidade": 100, "preco_medio": 30.0}]
    with patch.object(radar_mod, "obter_posicoes", return_value=posicoes), \
         patch.object(mercado_mod, "obter_cotacoes_lote", return_value={"PETR4": {"erro": "sem dado"}}):
        info = radar_mod.risco_carteira("sub1", {})
    _checar("14e.1 carteira_cadastrada True (existe posicao)", info["carteira_cadastrada"] is True)
    _checar("14e.2 sem_cotacao True, nunca inventa valor", info.get("sem_cotacao") is True)
    _checar("14e.3 ticker sem cotacao listado", info["tickers_sem_preco"] == ["PETR4"])


def _historico_fake(precos: list, inicio: date = date(2026, 1, 1)) -> pd.DataFrame:
    datas = [inicio + timedelta(days=i) for i in range(len(precos))]
    return pd.DataFrame({"Data": pd.to_datetime(datas), "Close": precos})


def test_14f_risco_carteira_calculo_real_concentracao_correlacao_vol_drawdown_cenario():
    posicoes = [
        {"ticker": "PETR4", "quantidade": 100, "preco_medio": 30.0},
        {"ticker": "VALE3", "quantidade": 50, "preco_medio": 60.0},
    ]
    cotacoes = {"PETR4": {"preco": 36.0, "erro": None}, "VALE3": {"preco": 66.0, "erro": None}}
    # PETR4: valor 3600 (peso ~52%), VALE3: valor 3300 (peso ~48%). Serie
    # sobe quase todo dia (pra isolar o drawdown de verdade: 1 unico
    # tombo expressivo no final, nos dois ativos ao mesmo tempo).
    precos_petr4 = [30, 31, 32, 33, 34, 35, 34, 35.5, 36.5, 37, 33]
    precos_vale3 = [60, 61, 62, 63, 64, 65, 64, 66, 67, 68, 60]
    historicos = {"PETR4": _historico_fake(precos_petr4), "VALE3": _historico_fake(precos_vale3)}

    with patch.object(radar_mod, "obter_posicoes", return_value=posicoes), \
         patch.object(mercado_mod, "obter_cotacoes_lote", return_value=cotacoes), \
         patch.object(radar_mod, "obter_historico", side_effect=lambda t, periodo: historicos[t]), \
         patch.object(radar_mod, "_calcular_beta", side_effect=lambda t: {"PETR4": 1.2, "VALE3": 0.8}[t]):
        info = radar_mod.risco_carteira("sub1", {"watchlist": []})

    _checar("14f.1 carteira_cadastrada True", info["carteira_cadastrada"] is True)
    _checar("14f.2 valor_total = soma dos valores atuais (sem inventar)", info["valor_total"] == 3600 + 3300)
    pesos = {p["nome"]: p["peso_pct"] for p in info["concentracao_ativo"]}
    _checar("14f.3 pesos por ativo somam 100%", abs(sum(pesos.values()) - 100) < 0.01)
    _checar("14f.4 ordenado por peso desc", info["concentracao_ativo"][0]["peso_pct"] >= info["concentracao_ativo"][1]["peso_pct"])
    setores = {s["nome"] for s in info["concentracao_setor"]}
    _checar("14f.5 setor via config.IBOVESPA_SETORES (nunca inventa classificacao)",
             setores == {"Petróleo e Gás", "Mineração e Siderurgia"})
    _checar("14f.6 sem ticker sem preco/historico nesse caso", info["tickers_sem_preco"] == [] and info["tickers_sem_historico"] == [])
    _checar("14f.7 correlacao calculada (2 ativos com historico)", info["correlacao"] is not None and "PETR4" in info["correlacao"])
    _checar("14f.8 volatilidade anualizada calculada (numero finito > 0)", info["volatilidade_anual_pct"] is not None and info["volatilidade_anual_pct"] > 0)
    _checar("14f.9 drawdown calculado e <= 0 (queda, nunca positivo)", info["drawdown_pct"] is not None and info["drawdown_pct"] <= 0)
    _checar("14f.10 maior queda diaria <= 0", info["maior_queda_diaria_pct"] <= 0)
    cenario = info["cenario_beta"]
    beta_esperado = 1.2 * (3600 / 6900) + 0.8 * (3300 / 6900)
    _checar("14f.11 beta da carteira ponderado pelo valor de cada posicao",
             cenario is not None and abs(cenario["beta_carteira"] - beta_esperado) < 1e-6)
    _checar("14f.12 impacto estimado (-10% Ibov) = beta_carteira * -10",
             abs(cenario["impacto_pct"][-10] - beta_esperado * -10) < 1e-6)


def test_14g_risco_carteira_ativo_sem_historico_nao_quebra_calculo_dos_outros():
    posicoes = [
        {"ticker": "PETR4", "quantidade": 100, "preco_medio": 30.0},
        {"ticker": "NOVO3", "quantidade": 10, "preco_medio": 10.0},
    ]
    cotacoes = {"PETR4": {"preco": 36.0, "erro": None}, "NOVO3": {"preco": 11.0, "erro": None}}
    precos_petr4 = [30, 31, 30.5, 32, 31.5, 33, 32.5, 34, 33.5, 35, 36]

    with patch.object(radar_mod, "obter_posicoes", return_value=posicoes), \
         patch.object(mercado_mod, "obter_cotacoes_lote", return_value=cotacoes), \
         patch.object(radar_mod, "obter_historico",
                      side_effect=lambda t, periodo: _historico_fake(precos_petr4) if t == "PETR4" else None), \
         patch.object(radar_mod, "_calcular_beta", return_value=None):
        info = radar_mod.risco_carteira("sub1", {})

    _checar("14g.1 NOVO3 (sem historico) listado, nao quebra o calculo", info["tickers_sem_historico"] == ["NOVO3"])
    _checar("14g.2 correlacao None com so' 1 ativo com historico", info["correlacao"] is None)
    _checar("14g.3 volatilidade ainda calculada so' com PETR4", info["volatilidade_anual_pct"] is not None)
    _checar("14g.4 sem beta disponivel -> cenario_beta None", info["cenario_beta"] is None)


# ============================================================
# E. Research com evidencias - feed combinado, ordenado, limitado
# ============================================================

def test_15_evidencias_recentes_ordena_filtra_e_limita():
    _limpar_caches()
    noticias = [{"data": "2026-10-01T10:00:00", "titulo": "N1", "link": "https://n1"}]
    documentos = [
        {"data": "2026-10-05", "tipo": "FATO_RELEVANTE", "assunto": "D1", "ticker": "PETR4", "link": "https://d1"},
        {"data": "2026-10-03", "tipo": "PROVENTOS", "assunto": "D2 (nao deveria entrar)", "ticker": "PETR4", "link": "https://d2"},
    ]
    with patch.object(radar_mod, "obter_noticias_watchlist", return_value=(noticias, [])), \
         patch.object(radar_mod, "obter_documentos_watchlist", return_value=(documentos, [])):
        itens = radar_mod.evidencias_recentes(("PETR4",), limite=10)
    _checar("15a PROVENTOS fora do feed editorial (so' fato/comunicado/resultados)", not any(i["_payload"].get("assunto") == "D2 (nao deveria entrar)" for i in itens))
    _checar("15b ordenado por data desc", itens[0]["_data_ord"] >= itens[-1]["_data_ord"])
    _checar("15c 2 itens (1 noticia + 1 documento valido)", len(itens) == 2, f"len={len(itens)}")

    _limpar_caches()
    muitos_docs = [{"data": f"2026-10-{i:02d}", "tipo": "RESULTADOS", "assunto": f"D{i}", "ticker": "PETR4", "link": f"https://d{i}"} for i in range(1, 10)]
    with patch.object(radar_mod, "obter_noticias_watchlist", return_value=([], [])), \
         patch.object(radar_mod, "obter_documentos_watchlist", return_value=(muitos_docs, [])):
        limitado = radar_mod.evidencias_recentes(("PETR4",), limite=3)
    _checar("15d respeita o limite", len(limitado) == 3)


# ============================================================
# F. Copiloto - respostas citam evidencia real ou declaram insuficiencia
# ============================================================

def test_16_copiloto_o_que_mudou():
    _limpar_caches()
    with patch.object(radar_mod, "historico_ticker", return_value=[]), \
         patch.object(radar_mod, "obter_documentos_watchlist", return_value=([], [])):
        r = radar_mod.responder_copiloto(radar_mod.PERGUNTAS_SUGERIDAS[0], "PETR4")
    _checar("16a sem evidencia -> DADO_INSUFICIENTE, nunca resposta inventada", r["tipo"] == radar_mod.TIPO_INSUFICIENTE)

    _limpar_caches()
    hoje = _hoje()
    historico_fake = [
        {"recomendacao": "COMPRA", "preco_alvo": 30.0, "potencial_pct": 10.0, "capturado_em": (hoje - timedelta(days=1)).isoformat() + "T10:00:00+00:00"},
        {"recomendacao": "NEUTRO", "preco_alvo": 25.0, "potencial_pct": None, "capturado_em": (hoje - timedelta(days=5)).isoformat() + "T10:00:00+00:00"},
    ]
    with patch.object(radar_mod, "historico_ticker", return_value=historico_fake), \
         patch.object(radar_mod, "obter_documentos_watchlist", return_value=([], [])), \
         patch.object(radar_mod, "obter_cotacao", return_value={"preco": 28.0, "erro": None}):
        r2 = radar_mod.responder_copiloto(radar_mod.PERGUNTAS_SUGERIDAS[0], "PETR4")
    _checar("16b com evidencia real -> FATO, cita a mudanca", r2["tipo"] == radar_mod.TIPO_FATO and "COMPRA" in r2["resposta"])


def test_17_copiloto_riscos_e_eventos_e_contradicao():
    _limpar_caches()
    with patch.object(radar_mod, "obter_cotacao", return_value={"preco": 30.0, "erro": None}), \
         patch.object(radar_mod, "obter_indicadores", return_value={"pl": -3.0, "pvp": 1.0, "dividend_yield": None, "roe": None, "margem_liquida": None, "divida_liquida_ebitda": None, "valor_mercado": None}):
        r_risco = radar_mod.responder_copiloto(radar_mod.PERGUNTAS_SUGERIDAS[1], "PETR4")
    _checar("17a risco real (P/L negativo) -> CALCULO_INTERNO, nao insuficiente", r_risco["tipo"] == radar_mod.TIPO_CALCULO)

    _limpar_caches()
    with patch.object(radar_mod, "calcular_calendario_cacheado", return_value=[]), \
         patch.object(radar_mod, "obter_documentos_watchlist", return_value=([], [])):
        r_evt = radar_mod.responder_copiloto(radar_mod.PERGUNTAS_SUGERIDAS[2], "PETR4")
    _checar("17b sem evento -> DADO_INSUFICIENTE", r_evt["tipo"] == radar_mod.TIPO_INSUFICIENTE)

    r_contra = radar_mod.responder_copiloto(radar_mod.PERGUNTAS_SUGERIDAS[3], "PETR4")
    _checar("17c contradicao sempre honesta (sem texto/racional persistido pra comparar)", r_contra["tipo"] == radar_mod.TIPO_INSUFICIENTE)

    r_desconhecida = radar_mod.responder_copiloto("pergunta que nao existe", "PETR4")
    _checar("17d pergunta fora da lista -> nao quebra, declara nao reconhecida", r_desconhecida["tipo"] == radar_mod.TIPO_INSUFICIENTE)


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
    print("TODOS OS TESTES DO RADAR PASSARAM")
