# -*- coding: utf-8 -*-
"""Testes de data/cvm.py (ate 2026-10-08 esse modulo nao tinha NENHUM
teste automatizado, apesar de ser a fonte usada por CVM/CALENDARIO/
EQUITY). Cobre 2 achados reais desta sessao:

1. obter_documentos_cvm NUNCA chama _documentos_brutos (nem bate na
   fonte) quando o ticker nao tem CNPJ mapeado - so' confere a curto-
   circuito, sem rede real (mocka obter_cnpj/_mapa_ticker_cnpj).
2. data_referencia vindo do CSV da CVM as vezes chega como float('nan')
   (campo vazio, lido pelo pandas) - precisa virar None (nunca "nan"
   literal na UI, bug real corrigido em data/cvm.py:obter_documentos_cvm).

Mocka _documentos_brutos/_mapa_ticker_cnpj diretamente - nunca faz
chamada de rede. Uso: python tests/test_cvm.py (venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.cvm as cvm_mod

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


def _limpar_cache():
    # obter_documentos_cvm/obter_documentos_watchlist sao @st.cache_data
    # (2026-10-08) - limpa entre testes pra cada mock valer de verdade,
    # nunca reaproveitar resultado de uma chamada anterior do MESMO
    # processo de teste.
    cvm_mod.obter_documentos_cvm.clear()
    cvm_mod.obter_documentos_watchlist.clear()


def test_1_sem_cnpj_mapeado_nao_busca_documentos_brutos():
    _limpar_cache()
    chamadas = []
    with patch.object(cvm_mod, "obter_cnpj", return_value=None), \
         patch.object(cvm_mod, "_documentos_brutos", side_effect=lambda cnpj: chamadas.append(cnpj) or []):
        resultado = cvm_mod.obter_documentos_cvm("MELI34")
    _checar("1a ticker sem CNPJ mapeado -> [] (nunca None - fonte respondeu, so' nao ha' nada pra esse ticker)",
             resultado == [])
    _checar("1b _documentos_brutos NUNCA e' chamado (curto-circuito antes de bater na fonte)",
             chamadas == [], f"(chamadas={chamadas})")


def test_2_com_cnpj_mapeado_busca_documentos_brutos_normalmente():
    _limpar_cache()
    with patch.object(cvm_mod, "obter_cnpj", return_value="11.222.333/0001-44"), \
         patch.object(cvm_mod, "_documentos_brutos", return_value=[]):
        resultado = cvm_mod.obter_documentos_cvm("PETR4")
    _checar("2 ticker com CNPJ mapeado mas sem documento nenhum -> [] (fonte respondeu, lista vazia de verdade)",
             resultado == [])


def test_3_fonte_indisponivel_retorna_none_nao_lista_vazia():
    _limpar_cache()
    with patch.object(cvm_mod, "obter_cnpj", return_value="11.222.333/0001-44"), \
         patch.object(cvm_mod, "_documentos_brutos", return_value=None):
        resultado = cvm_mod.obter_documentos_cvm("PETR4")
    _checar("3 fonte de verdade fora do ar -> None (distinto de [] - nunca confunde 'sem CNPJ' com 'fonte caiu')",
             resultado is None)


def _linha_bruta(data_entrega="2026-09-15", data_referencia=None, categoria="Fato Relevante", tipo=None):
    linha = {
        "Categoria": categoria, "Tipo": tipo, "Assunto": "Comunicado de teste",
        "Data_Entrega": data_entrega, "Data_Referencia": data_referencia,
        "Link_Download": "https://cvm.example/doc.pdf",
    }
    return linha


def test_4_data_referencia_nan_vira_none_nunca_aparece_como_texto():
    # pandas le campo vazio do CSV como float('nan') - bool(nan) e' True
    # em Python, entao "if d.get('data_referencia')" NAO filtra isso;
    # sem _limpar_texto, a UI mostrava "(ref. nan)" literalmente
    # (achado real, ver ui/calendario_tab.py:_render_contexto_historico).
    _limpar_cache()
    bruta = _linha_bruta(data_referencia=float("nan"))
    with patch.object(cvm_mod, "obter_cnpj", return_value="11.222.333/0001-44"), \
         patch.object(cvm_mod, "_documentos_brutos", return_value=[bruta]):
        resultado = cvm_mod.obter_documentos_cvm("PETR4")
    _checar("4a documento foi retornado", len(resultado) == 1)
    _checar("4b data_referencia NaN virou None (nunca a string 'nan')",
             resultado[0]["data_referencia"] is None, f"(valor={resultado[0]['data_referencia']!r})")


def test_5_data_referencia_valida_passa_intacta():
    _limpar_cache()
    bruta = _linha_bruta(data_referencia="2026-06-30")
    with patch.object(cvm_mod, "obter_cnpj", return_value="11.222.333/0001-44"), \
         patch.object(cvm_mod, "_documentos_brutos", return_value=[bruta]):
        resultado = cvm_mod.obter_documentos_cvm("PETR4")
    _checar("5 data_referencia valida (string ISO) passa intacta, sem ser descartada por engano",
             resultado[0]["data_referencia"] == "2026-06-30", f"(valor={resultado[0]['data_referencia']!r})")


def test_6_data_referencia_none_continua_none():
    _limpar_cache()
    bruta = _linha_bruta(data_referencia=None)
    with patch.object(cvm_mod, "obter_cnpj", return_value="11.222.333/0001-44"), \
         patch.object(cvm_mod, "_documentos_brutos", return_value=[bruta]):
        resultado = cvm_mod.obter_documentos_cvm("PETR4")
    _checar("6 data_referencia ausente (None) continua None (nunca virou 'None' string)",
             resultado[0]["data_referencia"] is None)


def test_7_watchlist_so_salva_quando_ha_documento():
    _limpar_cache()
    salvou = []
    with patch.object(cvm_mod, "obter_cnpj", return_value=None), \
         patch.object(cvm_mod, "_documentos_brutos", return_value=[]), \
         patch.object(cvm_mod, "salvar_documentos", side_effect=lambda docs: salvou.append(docs) or True):
        documentos, falhas = cvm_mod.obter_documentos_watchlist(["MELI34"])
    _checar("7a nenhum documento (sem CNPJ) -> lista vazia, sem falha reportada (fonte respondeu)",
             documentos == [] and falhas == [])
    _checar("7b salvar_documentos nunca e' chamado quando nao ha' nenhum documento",
             salvou == [])


def test_8_mesmo_documento_em_2_tickers_do_mesmo_emissor_mantem_os_2_tickers():
    """Bug real corrigido (auditoria 2026-10-10): watchlist com 2 tickers
    do mesmo emissor (ex: PETR3+PETR4) - obter_documentos_cvm retorna o
    MESMO Fato Relevante (mesmo link) pra cada um, so' com 'ticker'
    diferente. Antes da correcao, salvar_documentos criava 1 item por
    ticker (tickers=[ticker]) e store.salvar_itens deduplicava por link
    mantendo so' a ULTIMA ocorrencia - o outro ticker era perdido."""
    itens_salvos = []
    with patch.object(cvm_mod.store, "salvar_itens", side_effect=lambda itens: itens_salvos.append(itens) or True):
        ok = cvm_mod.salvar_documentos([
            {"ticker": "PETR3", "assunto": "Fato Relevante - Acordo X", "data": "2026-10-01",
             "tipo": "FATO_RELEVANTE", "link": "https://cvm/doc/123"},
            {"ticker": "PETR4", "assunto": "Fato Relevante - Acordo X", "data": "2026-10-01",
             "tipo": "FATO_RELEVANTE", "link": "https://cvm/doc/123"},
        ])
    _checar("8a salvar_documentos retorna True", ok is True)
    _checar("8b chamou store.salvar_itens exatamente 1x", len(itens_salvos) == 1, f"(itens_salvos={itens_salvos})")
    itens = itens_salvos[0]
    _checar("8c so' 1 item persistido pro link duplicado (nao 2 linhas pro mesmo documento)",
             len(itens) == 1, f"(itens={itens})")
    _checar("8d o item final tem OS 2 tickers (PETR3 e PETR4), nenhum perdido",
             sorted(itens[0]["tickers"]) == ["PETR3", "PETR4"], f"(tickers={itens[0]['tickers']})")


def test_9_documentos_de_links_diferentes_continuam_itens_separados():
    itens_salvos = []
    with patch.object(cvm_mod.store, "salvar_itens", side_effect=lambda itens: itens_salvos.append(itens) or True):
        cvm_mod.salvar_documentos([
            {"ticker": "PETR4", "assunto": "Fato Relevante A", "data": "2026-10-01",
             "tipo": "FATO_RELEVANTE", "link": "https://cvm/doc/1"},
            {"ticker": "VALE3", "assunto": "Fato Relevante B", "data": "2026-10-02",
             "tipo": "FATO_RELEVANTE", "link": "https://cvm/doc/2"},
        ])
    itens = itens_salvos[0]
    _checar("9 links diferentes continuam 2 itens separados (nao agrupa indevidamente)", len(itens) == 2, f"(itens={itens})")


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
    print("TODOS OS TESTES DE DATA/CVM.PY PASSARAM")
