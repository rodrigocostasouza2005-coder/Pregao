# -*- coding: utf-8 -*-
"""Testes de data/research/safra_carteiras.py - mocka requests, nunca faz
chamada de rede real. O fixture TEXTO_PAGINA_1_REAL abaixo é o texto
extraído via pypdf do PDF real "Outubro_Acoes.pdf" (Carteira Safra Top
10 Ações, outubro/2026), baixado e inspecionado em sessão de auditoria
real (2026-10-16) - confirma que essa fonte é pública, sem login e sem
bot-detection (diferente de Genial/XP, bloqueadas na borda Akamai; BTG
não tem esse bloqueio - ver data/research/btg.py)."""
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

# Fixture real (investigacao Fase 5, 2026-11-23): texto extraido via
# pypdf do PDF real "Novembro_Acoes.pdf", baixado ao vivo deste
# ambiente - mesma tabela de outubro, mas com PONTO como separador
# decimal em vez de VIRGULA (ex: "48.36" em vez de "48,36"). Confirma a
# causa raiz real de "Safra Corretora (carteiras)" ficar "fonte
# indisponivel"/"tabela rejeitada: 0 ticker(s) encontrados" por semanas:
# a fonte mudou o separador decimal do PDF sem aviso e o regex antigo
# so' aceitava virgula.
TEXTO_PAGINA_1_REAL_PONTO_DECIMAL = (
    "Carteira Safra\nTOP 10 Ações\nSafra Corretora 1\nNovembro de 2026\n"
    "Carteira Safra Top 10 Ações\nApós a forte volatilidade observada em outubro...\n"
    "Recomendações para novembro\nFonte: Estimativas Safra e Bloomberg\n"
    "Cauê Pinheiro\nEstrategista\nLuana Nunes \nEstrategista\nYves Adam, CFA\nEstrategista\n"
    "Código Companhia Setor\nCot. fech. \n30/10/2026\n(BRL/ação)\nP/L 2026E Peso \n"
    "anterior Peso atual\n"
    "WEGE3 Weg Bens de Capital 48.36 29.4x 12.0% 12.0%\n"
    "ITSA4 Itaúsa Serviços Financeiros 12.45 5.2x 0.0% 15.0%\n"
    "CXSE3 Caixa Seguridade Serviços Financeiros 21.38 13.3x 10.0% 10.0%\n"
    "SUZB3 Suzano Papel e Celulose 50.14 7.9x 0.0% 7.5%\n"
    "VALE3 Vale Siderurgia e Mineração 62.02 8.4x 10.0% 7.5%\n"
    "PETR4 Petrobras Petróleo e Gás 52.71 5.2x 10.0% 10.0%\n"
    "IGTI11 Iguatemi Shoppings Centers 21.79 12.1x 10.0% 10.0%\n"
    "TIMS3 TIM Brasil TMT 19.17 10.7x 0.0% 8.0%\n"
    "ENEV3 Eneva Utilidades Básicas 25.70 58.0x 0.0% 10.0%\n"
    "EQTL3 Equatorial Utilidades Básicas 32.60 13.5x 10.0% 10.0%"
)
_HOJE_NOVEMBRO = datetime.date(2026, 11, 23)
_URL_PDF_NOVEMBRO = "https://www.safra.com.br/data/files/yyy/Novembro_Acoes.pdf"


def test_parsear_texto_aceita_ponto_como_separador_decimal():
    """Regressao do bug real encontrado em produção: o PDF de novembro
    usa ponto decimal (48.36) em vez de vírgula (48,36) - o regex antigo
    rejeitava TODAS as linhas da tabela (0 tickers), classificando a
    fonte inteira como indisponível por semanas, mesmo com a página e o
    PDF respondendo normalmente."""
    itens = safra_mod._parsear_texto(TEXTO_PAGINA_1_REAL_PONTO_DECIMAL, _URL_PDF_NOVEMBRO, hoje=_HOJE_NOVEMBRO)
    assert itens is not None
    assert len(itens) == 10
    tickers = {i["ticker"] for i in itens}
    assert tickers == {
        "WEGE3", "ITSA4", "CXSE3", "SUZB3", "VALE3",
        "PETR4", "IGTI11", "TIMS3", "ENEV3", "EQTL3",
    }


def test_parsear_texto_cotacao_com_ponto_decimal_fica_float_valida():
    itens = safra_mod._parsear_texto(TEXTO_PAGINA_1_REAL_PONTO_DECIMAL, _URL_PDF_NOVEMBRO, hoje=_HOJE_NOVEMBRO)
    item = next(i for i in itens if i["ticker"] == "PETR4")
    assert item["empresa"] == "Petrobras"


def test_parsear_texto_separa_setor_tmt_do_nome_da_empresa():
    """Achado real no mesmo PDF de novembro/2026: sem 'TMT' no vocabulario
    de setores conhecidos, a empresa da TIM Brasil ficava poluída com o
    setor colado ('TIM Brasil TMT') - o ticker/dado numérico continuavam
    corretos, só o nome de exibição ficava errado."""
    itens = safra_mod._parsear_texto(TEXTO_PAGINA_1_REAL_PONTO_DECIMAL, _URL_PDF_NOVEMBRO, hoje=_HOJE_NOVEMBRO)
    item = next(i for i in itens if i["ticker"] == "TIMS3")
    assert item["empresa"] == "TIM Brasil"


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


# ---------------------------------------------------------------------
# motivo_ultima_falha(): regressão real (auditoria SAÚDE DOS DADOS
# 2026-11-18) - "Safra Corretora (carteiras)" ficou "fonte indisponível"
# por 20 dias seguidos sem que ninguém soubesse a causa real: QUALQUER
# falha (rede, robots.txt, PDF do mês ainda não publicado, parsing
# rejeitado, mudança de layout) colapsava em None, e a causa real só
# chegava a um print() de log, nunca ao campo `erro` persistido via
# registrar_tentativa. Estes testes confirmam que, pra cada cenário de
# falha, motivo_ultima_falha() devolve a causa REAL (nunca um texto
# genérico tipo "erro desconhecido") - mesmo padrão já usado em
# data/research/genial.py e data/research/xp.py.
# ---------------------------------------------------------------------

def test_motivo_ultima_falha_nenhuma_chamada_ainda_e_none():
    """Sem nenhuma chamada registrada neste processo, não inventa causa."""
    with patch.object(safra_mod, "_ultimo_motivo_falha", None):
        assert safra_mod.motivo_ultima_falha() is None


def test_motivo_ultima_falha_bloqueio_por_robots_txt():
    with patch.object(safra_mod, "permitido", return_value=False):
        assert safra_mod.coletar_carteiras(hoje=_HOJE) is None
    motivo = safra_mod.motivo_ultima_falha()
    assert motivo is not None and "robots.txt" in motivo


def test_motivo_ultima_falha_excecao_de_rede_propaga_mensagem_real():
    """Timeout/ConnectionError real - a mensagem da própria exceção chega
    no motivo, nunca um rótulo fixo genérico."""
    with patch.object(safra_mod, "permitido", return_value=True), \
         patch.object(safra_mod.requests, "get",
                      side_effect=ConnectionError("Failed to establish a new connection: [Errno 110]")):
        assert safra_mod.coletar_carteiras(hoje=_HOJE) is None
    motivo = safra_mod.motivo_ultima_falha()
    assert motivo is not None
    assert "ConnectionError" in motivo
    assert "Failed to establish a new connection: [Errno 110]" in motivo


def test_motivo_ultima_falha_http_nao_200():
    resposta = MagicMock(status_code=503, content=b"")
    with patch.object(safra_mod, "permitido", return_value=True), \
         patch.object(safra_mod.requests, "get", return_value=resposta):
        assert safra_mod.coletar_carteiras(hoje=_HOJE) is None
    motivo = safra_mod.motivo_ultima_falha()
    assert motivo is not None and "HTTP 503" in motivo


def test_motivo_ultima_falha_pdf_do_mes_ainda_nao_publicado():
    resposta_listagem = MagicMock(
        status_code=200, content=b"x",
        text='<a href="/Setembro_Acoes.pdf">Setembro</a>',
    )
    with patch.object(safra_mod, "permitido", return_value=True), \
         patch.object(safra_mod.requests, "get", return_value=resposta_listagem):
        assert safra_mod.coletar_carteiras(hoje=_HOJE) is None
    motivo = safra_mod.motivo_ultima_falha()
    assert motivo is not None and "outubro" in motivo and "não encontrado" in motivo


def test_motivo_ultima_falha_pdf_ilegivel_propaga_excecao_real_do_pypdf():
    with patch.object(safra_mod, "PdfReader", side_effect=ValueError("EOF marker not found")):
        assert safra_mod.parsear_pdf(b"bytes-invalidos", _URL_PDF, hoje=_HOJE) is None
    motivo = safra_mod.motivo_ultima_falha()
    assert motivo is not None and "ValueError" in motivo and "EOF marker not found" in motivo


def test_motivo_ultima_falha_parsing_rejeitado_por_poucos_tickers():
    texto_quebrado = "Código Companhia Setor\nWEGE3 Weg Bens de Capital 49,46 33,1x 12,0% 12,0%"
    assert safra_mod._parsear_texto(texto_quebrado, _URL_PDF, hoje=_HOJE) is None
    motivo = safra_mod.motivo_ultima_falha()
    assert motivo is not None and "tabela rejeitada" in motivo and "1 ticker" in motivo


def test_motivo_ultima_falha_excecao_nao_prevista_propaga_str_da_excecao_nunca_generico():
    """Qualquer falha fora dos pontos já tratados (ex: mudança de
    estrutura que quebra uma chamada fora dos try/except específicos)
    precisa propagar str(exc) real - nunca um texto fixo tipo 'erro
    desconhecido'."""
    with patch.object(safra_mod, "_url_pdf_mes", side_effect=KeyError("layout inesperado")):
        with patch.object(safra_mod, "permitido", return_value=True), \
             patch.object(safra_mod.requests, "get",
                          return_value=MagicMock(status_code=200, content=b"x", text="<html></html>")):
            assert safra_mod.coletar_carteiras(hoje=_HOJE) is None
    motivo = safra_mod.motivo_ultima_falha()
    assert motivo is not None
    assert "KeyError" in motivo
    assert "layout inesperado" in motivo
    assert "erro desconhecido" not in motivo.lower()


def test_motivo_ultima_falha_reseta_para_none_apos_sucesso():
    """Uma falha anterior não pode continuar "vazando" como causa de uma
    coleta que, desta vez, teve sucesso pleno."""
    with patch.object(safra_mod, "permitido", return_value=False):
        assert safra_mod.coletar_carteiras(hoje=_HOJE) is None
    assert safra_mod.motivo_ultima_falha() is not None

    resposta_listagem = MagicMock(status_code=200, content=b"x", text='<a href="/Outubro_Acoes.pdf">x</a>')
    resposta_pdf = MagicMock(status_code=200, content=b"PDF-BYTES-FAKE")
    with patch.object(safra_mod, "permitido", return_value=True), \
         patch.object(safra_mod.requests, "get", side_effect=[resposta_listagem, resposta_pdf]), \
         patch.object(safra_mod, "parsear_pdf", return_value=[{"ticker": "PETR4"}]):
        itens = safra_mod.coletar_carteiras(hoje=_HOJE)
    assert itens == [{"ticker": "PETR4"}]
    assert safra_mod.motivo_ultima_falha() is None
