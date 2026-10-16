# -*- coding: utf-8 -*-
"""Testes de data/research/safra_carteiras.py - mocka requests, nunca faz
chamada de rede real. O fixture TEXTO_PAGINA_1_REAL abaixo é o texto
extraído via pypdf do PDF real "Outubro_Acoes.pdf" (Carteira Safra Top
10 Ações, outubro/2026), baixado e inspecionado em sessão de auditoria
real (2026-10-16) - confirma que essa fonte é pública, sem login e sem
bot-detection (diferente de Genial/XP/BTG, bloqueadas na borda Akamai)."""
import datetime
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.safra_carteiras as safra_mod

TEXTO_PAGINA_1_REAL = (
    "Carteira Safra\nTOP 10 Ações\nSafra Corretora 1\nOutubro de 2026\n"
    "Carteira Safra Top 10 Ações\nEm outubro, realizamos três trocas...\n"
    "Recomendações para outubro\nFonte: Estimativas Safra e Bloomberg\n"
    "Cauê Pinheiro\nEstrategista\nLuana Nunes \nEstrategista\nYves Adam, CFA\nEstrategista\n"
    "Código Companhia Setor\nCot. fech. \n30/09/2026\n(BRL/ação)\nP/L 2026E Peso \n"
    "anterior Peso atual\n"
    "WEGE3 Weg Bens de Capital 49,46 33,1x 12,0% 12,0%\n"
    "B3SA3 B3 Serviços Financeiros 18,34 13,9x 0,0% 15,0%\n"
    "CXSE3 Caixa Seguridade Serviços Financeiros 19,88 12,7x 10,0% 10,0%\n"
    "RDOR3 Rede D'Or Saúde 38,29 16,4x 0,0% 8,0%\n"
    "VALE3 Vale Siderurgia e Mineração 69,91 9,2x 10,0% 10,0%\n"
    "PETR4 Petrobras Petróleo e Gás 49,12 7,1x 10,0% 10,0%\n"
    "IGTI11 Iguatemi Shoppings Centers 27,02 12,8x 0,0% 10,0%\n"
    "GGBR4 Gerdau Siderurgia e Mineração 24,27 5,9x 5,0% 5,0%\n"
    "CPLE3 Copel Utilidades Básicas 16,00 16,3x 8,0% 10,0%\n"
    "EQTL3 Equatorial Utilidades Básicas 40,65 15,1x 12,0% 10,0%"
)

_HOJE = datetime.date(2026, 10, 16)
_URL_PDF = "https://www.safra.com.br/data/files/xxx/Outubro_Acoes.pdf"


def test_parsear_texto_extrai_os_10_tickers_reais():
    itens = safra_mod._parsear_texto(TEXTO_PAGINA_1_REAL, _URL_PDF, hoje=_HOJE)
    assert itens is not None
    assert len(itens) == 10
    tickers = {i["ticker"] for i in itens}
    assert tickers == {
        "WEGE3", "B3SA3", "CXSE3", "RDOR3", "VALE3",
        "PETR4", "IGTI11", "GGBR4", "CPLE3", "EQTL3",
    }


def test_parsear_texto_separa_empresa_do_setor_conhecido():
    itens = safra_mod._parsear_texto(TEXTO_PAGINA_1_REAL, _URL_PDF, hoje=_HOJE)
    por_ticker = {i["ticker"]: i for i in itens}
    assert por_ticker["WEGE3"]["empresa"] == "Weg"
    assert por_ticker["CXSE3"]["empresa"] == "Caixa Seguridade"
    assert por_ticker["RDOR3"]["empresa"] == "Rede D'Or"


def test_parsear_texto_nunca_copia_texto_do_relatorio():
    """Princípio do projeto (mesmo de genial.py/xp.py): só metadados de
    composição, nunca o texto analítico (a justificativa de cada
    recomendação, nas páginas seguintes do PDF de verdade)."""
    itens = safra_mod._parsear_texto(TEXTO_PAGINA_1_REAL, _URL_PDF, hoje=_HOJE)
    chaves = set()
    for item in itens:
        chaves.update(item.keys())
    assert "texto" not in chaves and "analise" not in chaves and "justificativa" not in chaves


def test_parsear_texto_campos_do_contrato_do_radar():
    itens = safra_mod._parsear_texto(TEXTO_PAGINA_1_REAL, _URL_PDF, hoje=_HOJE)
    item = next(i for i in itens if i["ticker"] == "PETR4")
    assert item["casa"] == "Safra Corretora"
    assert item["carteira"] == "Top 10 Ações"
    assert item["fonte_url"] == _URL_PDF
    assert item["data_publicacao"] == "2026-10-01"
    assert item["status_coleta"] == "COLETADO"
    assert item["preco_alvo"] is None  # Top 10 é alocação por peso, não preço-alvo


def test_parsear_texto_rejeita_tabela_com_poucos_tickers():
    texto_quebrado = "Código Companhia Setor\nWEGE3 Weg Bens de Capital 49,46 33,1x 12,0% 12,0%"
    assert safra_mod._parsear_texto(texto_quebrado, _URL_PDF, hoje=_HOJE) is None


def test_parsear_texto_ignora_linhas_de_prosa_sem_quebrar():
    texto_com_lixo = "Isto não é uma linha de tabela de jeito nenhum.\n" + TEXTO_PAGINA_1_REAL
    itens = safra_mod._parsear_texto(texto_com_lixo, _URL_PDF, hoje=_HOJE)
    assert itens is not None and len(itens) == 10


def test_url_pdf_mes_acha_o_link_do_mes_vigente_e_ignora_bdr():
    html = (
        '<a href="../../data/files/aaa/Outubro_Acoes.pdf">Acoes</a>'
        '<a href="../../data/files/bbb/Outubro_BDRs.pdf">BDRs</a>'
        '<a href="../../data/files/ccc/Setembro_Acoes.pdf">Setembro</a>'
    )
    url = safra_mod._url_pdf_mes(html, _HOJE)
    assert url is not None and "Outubro_Acoes.pdf" in url and "BDRs" not in url


def test_url_pdf_mes_retorna_none_se_mes_vigente_nao_publicado():
    html = '<a href="../../data/files/ccc/Setembro_Acoes.pdf">Setembro</a>'
    assert safra_mod._url_pdf_mes(html, _HOJE) is None


def test_coletar_carteiras_respeita_robots_txt():
    with patch.object(safra_mod, "permitido", return_value=False):
        assert safra_mod.coletar_carteiras(hoje=_HOJE) is None


def test_coletar_carteiras_listagem_indisponivel_retorna_none():
    with patch.object(safra_mod, "permitido", return_value=True), \
         patch.object(safra_mod.requests, "get", side_effect=ConnectionError("timeout")):
        assert safra_mod.coletar_carteiras(hoje=_HOJE) is None


def test_coletar_carteiras_ponta_a_ponta_com_rede_mockada():
    resposta_listagem = MagicMock(status_code=200, content=b"x", text='<a href="/Outubro_Acoes.pdf">x</a>')
    resposta_pdf = MagicMock(status_code=200, content=b"PDF-BYTES-FAKE")
    with patch.object(safra_mod, "permitido", return_value=True), \
         patch.object(safra_mod.requests, "get", side_effect=[resposta_listagem, resposta_pdf]), \
         patch.object(safra_mod, "parsear_pdf", return_value=[{"ticker": "PETR4"}]) as mock_parse:
        itens = safra_mod.coletar_carteiras(hoje=_HOJE)
    assert itens == [{"ticker": "PETR4"}]
    mock_parse.assert_called_once()
    assert mock_parse.call_args[0][1] == "https://www.safra.com.br/Outubro_Acoes.pdf"
