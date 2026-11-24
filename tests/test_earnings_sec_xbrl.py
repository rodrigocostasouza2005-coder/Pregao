# -*- coding: utf-8 -*-
"""Testes de data/earnings/sec_xbrl.py com dados REAIS (fixtures
baixadas de data.sec.gov em 2026-10-22, conceitos XBRL da Apple Inc,
CIK 320193, trimestre fiscal Q3 2026 - ver tests/fixtures/earnings/
sec_aapl_*.json). Nenhum teste faz chamada de rede - _serie_conceito e'
sempre mockado pra devolver a fixture certa por tag."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from data.earnings import sec_xbrl

_DIR = Path(__file__).parent / "fixtures" / "earnings"

_INICIO, _FIM = "2026-03-29", "2026-06-27"           # Q3 fiscal 2026 (real)
_INICIO_ANT, _FIM_ANT = "2025-03-30", "2025-06-28"   # mesmo trimestre fiscal, ano anterior


def _carregar(tag: str) -> list:
    with open(_DIR / f"sec_aapl_{tag}.json", encoding="utf-8") as f:
        return json.load(f)["units"]["USD"]


def _fake_serie_conceito(cik, tag):
    caminho = _DIR / f"sec_aapl_{tag}.json"
    if not caminho.exists():
        return None
    return _carregar(tag)


@pytest.fixture(autouse=True)
def _mock_fonte():
    with patch.object(sec_xbrl, "obter_cik", return_value=320193), \
         patch.object(sec_xbrl, "_serie_conceito", side_effect=_fake_serie_conceito):
        yield


def test_aapl_receita_e_lucro_q3_fiscal_2026_reais():
    """Conferido manualmente contra a API real da SEC (2026-10-22):
    receita Q3 fiscal 2026 = US$109.417bi; mesmo trimestre fiscal 2025
    (YoY) = US$94.036bi. Lucro liquido: US$29.789bi vs US$23.434bi."""
    dados = sec_xbrl.obter_metricas_trimestre("AAPL", _INICIO, _FIM, _INICIO_ANT, _FIM_ANT)
    assert dados is not None
    assert dados["metricas"]["receita_liquida"]["atual"] == pytest.approx(109417000000.0)
    assert dados["metricas"]["receita_liquida"]["ano_anterior"] == pytest.approx(94036000000.0)
    assert dados["metricas"]["receita_liquida"]["tag_usada"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert dados["metricas"]["lucro_liquido_consolidado"]["atual"] == pytest.approx(29789000000.0)
    assert dados["metricas"]["lucro_liquido_consolidado"]["ano_anterior"] == pytest.approx(23434000000.0)


def test_aapl_resultado_bruto_e_custo_reais():
    dados = sec_xbrl.obter_metricas_trimestre("AAPL", _INICIO, _FIM, _INICIO_ANT, _FIM_ANT)
    assert dados["metricas"]["resultado_bruto"]["atual"] == pytest.approx(54770000000.0)
    assert dados["metricas"]["custo_vendas"]["atual"] == pytest.approx(54647000000.0)


def test_aapl_ebit_e_resultado_antes_tributos_reais():
    """Gap de cobertura encontrado em revisao tecnica independente
    (2026-10-22): estas 2 metricas (de 6 em TAGS_POR_METRICA) nunca
    tinham fixture/teste - resolviam sempre None nos testes anteriores
    sem ningum notar, mesmo a tag funcionando de verdade na API real.
    Conferido contra data.sec.gov ao vivo em 2026-10-22."""
    dados = sec_xbrl.obter_metricas_trimestre("AAPL", _INICIO, _FIM, _INICIO_ANT, _FIM_ANT)
    assert dados["metricas"]["ebit"]["atual"] == pytest.approx(35695000000.0)
    assert dados["metricas"]["ebit"]["tag_usada"] == "OperatingIncomeLoss"
    assert dados["metricas"]["resultado_antes_tributos"]["atual"] == pytest.approx(36267000000.0)


def test_ticker_sem_cik_devolve_none():
    with patch.object(sec_xbrl, "obter_cik", return_value=None):
        assert sec_xbrl.obter_metricas_trimestre("ZZZZ", _INICIO, _FIM, _INICIO_ANT, _FIM_ANT) is None


def test_periodo_sem_ponto_exato_fica_none_nunca_interpolado():
    dados = sec_xbrl.obter_metricas_trimestre("AAPL", "2026-01-01", "2026-01-31", "2025-01-01", "2025-01-31")
    for metrica, valores in dados["metricas"].items():
        assert valores["atual"] is None, metrica
        assert valores["ano_anterior"] is None, metrica


def test_conceito_sem_tag_disponivel_fica_none():
    with patch.object(sec_xbrl, "_serie_conceito", return_value=None):
        dados = sec_xbrl.obter_metricas_trimestre("AAPL", _INICIO, _FIM, _INICIO_ANT, _FIM_ANT)
    assert all(v["atual"] is None and v["tag_usada"] is None for v in dados["metricas"].values())


def _limpar_caches_mapa_ticker_cik():
    """Reseta os 3 caches envolvidos no mapa ticker->CIK entre testes
    (ver data/earnings/sec_xbrl.py:_mapa_ticker_cik) - _buscar_mapa_
    ticker_cik_ok (st.cache_data, caminho de sucesso), _ultimo_mapa_
    ticker_cik_valido e _ultima_falha_mapa_ticker_cik (st.cache_resource,
    sem TTL - precisam ser limpos manualmente ou o cooldown/fallback de
    um teste vaza pro próximo, mesmo padrão de tests/test_cvm.py)."""
    sec_xbrl._buscar_mapa_ticker_cik_ok.clear()
    sec_xbrl._ultimo_mapa_ticker_cik_valido().clear()
    falha = sec_xbrl._ultima_falha_mapa_ticker_cik()
    falha["quando"] = None
    falha["erro"] = None


def test_mapa_ticker_cik_fonte_indisponivel_devolve_dict_vazio():
    """Bug real encontrado na investigação Fase 5 (2026-11-23): este teste
    não mockava `registrar_tentativa` - em qualquer ambiente com
    secrets.toml real configurado (ex: pra consultar o Supabase de
    produção, não só em CI sem credencial), a falha simulada aqui
    ("timeout... boom", ticker fake "X") era gravada de verdade na tabela
    `coletores_status` de PRODUÇÃO via o caminho real de
    `registrar_tentativa` -> `data/coletores_status.py` -> Supabase,
    sujando o painel SAÚDE DOS DADOS com dado de teste. Confirmado: antes
    desta correção, rodar esta suíte com credencial real deixava
    `coletores_status."SEC EDGAR (XBRL)".ultimo_erro` = literalmente
    "timeout (>30s) ao buscar X: boom"."""
    _limpar_caches_mapa_ticker_cik()
    with patch.object(sec_xbrl, "_get_json", return_value=(None, "timeout (>30s) ao buscar X: boom")), \
         patch.object(sec_xbrl, "registrar_tentativa"):
        assert sec_xbrl._mapa_ticker_cik() == {}
    _limpar_caches_mapa_ticker_cik()


# ---------------------------------------------------------------------
# Regressão (auditoria SAÚDE DOS DADOS 2026-10-26): "SEC EDGAR (XBRL)"
# aparecia NUNCA_EXECUTADO sem nenhuma evidência real - só _serie_conceito
# chamava registrar_tentativa, e só é alcançada quando obter_cik(ticker)
# já encontrou um CIK; o próprio mapa ticker->CIK (_mapa_ticker_cik, esta
# função) nunca registrava tentativa nenhuma, sucesso ou falha. Mesmo gap
# já corrigido pro mapa ticker->CNPJ da CVM (ver data/cvm.py:
# _mapa_ticker_cnpj, "CVM (FCA)").
# ---------------------------------------------------------------------

def test_mapa_ticker_cik_fonte_indisponivel_registra_tentativa_de_falha():
    _limpar_caches_mapa_ticker_cik()
    chamadas = []
    with patch.object(sec_xbrl, "_get_json", return_value=(None, "HTTP 429 ao buscar X: corpo='rate limited'")), \
         patch.object(sec_xbrl, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k))):
        sec_xbrl._mapa_ticker_cik()
    _limpar_caches_mapa_ticker_cik()
    assert len(chamadas) == 1
    args, kwargs = chamadas[0]
    assert args[0] == "SEC EDGAR (XBRL)"
    assert kwargs["execucao_ok"] is False
    assert kwargs["erro"]


def test_mapa_ticker_cik_sucesso_registra_tentativa_com_registros_novos():
    _limpar_caches_mapa_ticker_cik()
    chamadas = []
    resposta = {"fields": ["cik", "name", "ticker", "exchange"],
                "data": [[320193, "Apple Inc", "AAPL", "Nasdaq"]]}
    with patch.object(sec_xbrl, "_get_json", return_value=(resposta, None)), \
         patch.object(sec_xbrl, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k))):
        mapa = sec_xbrl._mapa_ticker_cik()
    _limpar_caches_mapa_ticker_cik()
    assert mapa == {"AAPL": 320193}
    assert len(chamadas) == 1
    args, kwargs = chamadas[0]
    assert args[0] == "SEC EDGAR (XBRL)"
    assert kwargs["execucao_ok"] is True
    assert kwargs["registros_novos"] == 1


def test_mapa_ticker_cik_formato_inesperado_registra_tentativa_de_falha():
    """Mesma proteção já existente (colunas 'cik'/'ticker' ausentes) -
    antes devolvia {} silenciosamente, sem nenhum rastro no painel."""
    _limpar_caches_mapa_ticker_cik()
    chamadas = []
    resposta = {"fields": ["name", "ticker", "exchange"], "data": []}
    with patch.object(sec_xbrl, "_get_json", return_value=(resposta, None)), \
         patch.object(sec_xbrl, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k))):
        assert sec_xbrl._mapa_ticker_cik() == {}
    _limpar_caches_mapa_ticker_cik()
    assert chamadas and chamadas[0][1]["execucao_ok"] is False


# ---------------------------------------------------------------------
# Regressão (missão isolada SAÚDE DOS DADOS/Earnings, 2026-11-19): causa
# raiz real do coletor "SEC EDGAR (XBRL)" com 50 falhas seguidas desde
# 2026-10-29 (~2x/dia), nunca 1 sucesso - ver docstring de _get_json/
# _mapa_ticker_cik/_TTL_FALHA_TICKERS em data/earnings/sec_xbrl.py.
# ---------------------------------------------------------------------

def test_get_json_propaga_causa_real_timeout_vs_http_vs_json_invalido():
    """_get_json tinha que devolver so' None pra QUALQUER falha antes -
    agora devolve (None, diagnostico) com a causa real, distinguindo
    timeout, erro de conexão, HTTP != 2xx (com status) e corpo não-JSON
    (com o corpo da resposta) - nenhum desses textos pode ser genérico
    tipo 'sem resposta válida'."""
    import requests as requests_mod

    class _RespostaHTTP:
        def __init__(self, status_code, texto):
            self.status_code = status_code
            self.text = texto
            self.ok = 200 <= status_code < 300

        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    with patch.object(sec_xbrl.requests, "get", side_effect=requests_mod.exceptions.Timeout("read timed out")):
        _, diagnostico = sec_xbrl._get_json("https://exemplo/x")
    assert "timeout" in diagnostico.lower()

    with patch.object(sec_xbrl.requests, "get",
                       side_effect=requests_mod.exceptions.ConnectionError("Failed to resolve host")):
        _, diagnostico = sec_xbrl._get_json("https://exemplo/x")
    assert "conex" in diagnostico.lower()
    assert "Failed to resolve host" in diagnostico

    with patch.object(sec_xbrl.requests, "get", return_value=_RespostaHTTP(403, "Forbidden - rate limited")):
        _, diagnostico = sec_xbrl._get_json("https://exemplo/x")
    assert "403" in diagnostico
    assert "Forbidden" in diagnostico

    with patch.object(sec_xbrl.requests, "get", return_value=_RespostaHTTP(200, "<html>not json</html>")):
        _, diagnostico = sec_xbrl._get_json("https://exemplo/x")
    assert "não-json" in diagnostico.lower() or "nao-json" in diagnostico.lower()
    assert "not json" in diagnostico


def test_mapa_ticker_cik_falha_propaga_causa_real_nao_generica():
    """registrar_tentativa(erro=...) tem que carregar a causa REAL da
    falha (ex: 'HTTP 403 ... corpo=...'), não mais o texto genérico fixo
    'mapa ticker->CIK (company_tickers.json) sem resposta válida' que
    existia antes desta correção (não dizia nada sobre timeout x bloqueio
    x formato mudado)."""
    _limpar_caches_mapa_ticker_cik()
    chamadas = []
    diagnostico_real = "HTTP 403 ao buscar https://www.sec.gov/files/company_tickers.json: corpo='Request blocked'"
    with patch.object(sec_xbrl, "_get_json", return_value=(None, diagnostico_real)), \
         patch.object(sec_xbrl, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k))):
        sec_xbrl._mapa_ticker_cik()
    _limpar_caches_mapa_ticker_cik()
    assert len(chamadas) == 1
    erro = chamadas[0][1]["erro"]
    assert "403" in erro
    assert "Request blocked" in erro
    assert erro != "mapa ticker->CIK (company_tickers.json) sem resposta válida"


def test_falha_do_mapa_ticker_cik_nao_fica_presa_no_ttl_longo_de_sucesso():
    """O bug real desta missão: ANTES, sucesso e falha do mapa ticker->CIK
    compartilhavam o MESMO @st.cache_data(ttl=24h) - uma falha retornando
    {} ficava cacheada por 24h inteiras, então mesmo que a SEC voltasse a
    responder normalmente minutos depois, _mapa_ticker_cik continuava
    devolvendo {} até o TTL de 24h expirar.

    Este teste simula exatamente essa sequência (falha, depois sucesso
    LOGO em seguida, sem deixar o TTL de 24h expirar) e confirma que o
    sucesso aparece imediatamente - a falha só é protegida por um
    cooldown de minutos (_TTL_FALHA_TICKERS), nunca pelas 24h de sucesso.

    Mesmo bug real de isolamento de teste do grupo acima (ver docstring de
    test_mapa_ticker_cik_fonte_indisponivel_devolve_dict_vazio): o bloco
    de falha abaixo não mockava `registrar_tentativa`."""
    _limpar_caches_mapa_ticker_cik()
    resposta_boa = {"fields": ["cik", "name", "ticker", "exchange"],
                     "data": [[320193, "Apple Inc", "AAPL", "Nasdaq"]]}

    # 1) 1a tentativa falha (SEC fora do ar/bloqueada)
    with patch.object(sec_xbrl, "_get_json", return_value=(None, "HTTP 503 ao buscar X: corpo='Service Unavailable'")), \
         patch.object(sec_xbrl, "registrar_tentativa"):
        assert sec_xbrl._mapa_ticker_cik() == {}

    # 2) a SEC volta a responder normalmente poucos segundos depois (bem
    # ANTES de qualquer TTL de 24h expirar) - como o cooldown de falha
    # (_TTL_FALHA_TICKERS) ainda não passou, _mapa_ticker_cik ainda NÃO
    # tenta de novo sozinho (evita martelar a fonte a cada rerun)...
    with patch.object(sec_xbrl, "_get_json", return_value=(resposta_boa, None)), \
         patch.object(sec_xbrl, "registrar_tentativa"):
        assert sec_xbrl._mapa_ticker_cik() == {}  # ainda dentro do cooldown curto

        # ...mas assim que o cooldown de falha expira (segundos, não 24h),
        # a MESMA chamada com a MESMA fonte já respondendo bem tem que
        # devolver o mapa de verdade - nunca ficar presa até o TTL de 24h.
        # (sucesso TAMBÉM chama registrar_tentativa - ver
        # _buscar_mapa_ticker_cik_ok - por isso o patch acima cobre os
        # dois sub-blocos, não só a falha.)
        falha = sec_xbrl._ultima_falha_mapa_ticker_cik()
        falha["quando"] -= sec_xbrl._TTL_FALHA_TICKERS + 1
        assert sec_xbrl._mapa_ticker_cik() == {"AAPL": 320193}

    _limpar_caches_mapa_ticker_cik()


def test_falha_apos_sucesso_reaproveita_ultimo_mapa_valido_nao_zera():
    """Se o mapa ticker->CIK JÁ teve 1 sucesso nesta sessão do servidor e
    DEPOIS a SEC falha transitoriamente, _mapa_ticker_cik não pode voltar
    a {} (derrubaria obter_cik pra TODO ticker) - tem que reaproveitar o
    último mapa bom conhecido (mesmo padrão de data/cvm.py:
    _ultimo_mapa_ticker_valido / data/ibovespa.py:_ultima_composicao_valida)."""
    # Mesmo bug real do teste acima (ver docstring de
    # test_mapa_ticker_cik_fonte_indisponivel_devolve_dict_vazio): o
    # segundo bloco (falha simulada) não mockava `registrar_tentativa` -
    # sem isso, gravava a falha fake de verdade em coletores_status de
    # PRODUÇÃO quando a suíte roda com credencial real.
    _limpar_caches_mapa_ticker_cik()
    resposta_boa = {"fields": ["cik", "name", "ticker", "exchange"],
                     "data": [[320193, "Apple Inc", "AAPL", "Nasdaq"]]}

    with patch.object(sec_xbrl, "_get_json", return_value=(resposta_boa, None)), \
         patch.object(sec_xbrl, "registrar_tentativa"):
        assert sec_xbrl._mapa_ticker_cik() == {"AAPL": 320193}

    sec_xbrl._buscar_mapa_ticker_cik_ok.clear()  # simula o TTL de 24h expirando
    with patch.object(sec_xbrl, "_get_json", return_value=(None, "timeout (>30s) ao buscar X: boom")), \
         patch.object(sec_xbrl, "registrar_tentativa"):
        assert sec_xbrl._mapa_ticker_cik() == {"AAPL": 320193}  # reaproveita, nunca {}

    _limpar_caches_mapa_ticker_cik()
