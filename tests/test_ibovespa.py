# -*- coding: utf-8 -*-
"""Testes de data/ibovespa.py (composicao oficial do Ibovespa via B3) -
bug real corrigido (auditoria 2026-10-10): obter_composicao_oficial()
retornava {} numa falha e o @st.cache_data(ttl=24h) guardava esse {}
pelas MESMAS 24h de uma resposta boa - uma falha transitoria "trancava"
o app no fallback estatico curado por ate 24h mesmo que a B3 voltasse a
responder minutos depois. Mocka cffi_requests.get - nunca faz chamada
de rede.

Uso: python tests/test_ibovespa.py (python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.ibovespa as ibovespa_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


def _resposta_ok(resultados):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"results": resultados}
    return r


def _item(cod, part="10,0", asset="Empresa X"):
    return {"cod": cod, "part": part, "asset": asset}


def _limpar_cache():
    ibovespa_mod.obter_composicao_oficial.clear()
    ibovespa_mod._ultima_composicao_valida.clear()


def test_1_sucesso_preenche_dict_e_atualiza_cache_de_fallback():
    _limpar_cache()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req:
        mock_req.get.return_value = _resposta_ok([_item("PETR4")])
        resultado = ibovespa_mod.obter_composicao_oficial()
    _checar("1a retorna o ticker coletado", "PETR4" in resultado, f"(resultado={resultado})")
    _checar("1b cache de fallback foi atualizado", ibovespa_mod._ultima_composicao_valida() == resultado)


def test_2_falha_apos_sucesso_reaproveita_ultima_composicao_valida():
    """O bug real: antes desta correcao, uma falha TRANSITORIA (depois de
    um sucesso anterior) retornava {} e isso ficava cacheado por 24h -
    agora reaproveita o ultimo resultado bom em vez de {}."""
    _limpar_cache()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req:
        mock_req.get.return_value = _resposta_ok([_item("VALE3")])
        primeiro = ibovespa_mod.obter_composicao_oficial()

    ibovespa_mod.obter_composicao_oficial.clear()  # simula o TTL de 24h expirando
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req:
        resposta_falha = MagicMock()
        resposta_falha.status_code = 500
        mock_req.get.return_value = resposta_falha
        segundo = ibovespa_mod.obter_composicao_oficial()

    _checar("2a primeira chamada (sucesso) tem VALE3", "VALE3" in primeiro, f"(primeiro={primeiro})")
    _checar(
        "2b falha transitoria NAO retorna {} - reaproveita a composicao boa anterior",
        segundo == primeiro, f"(segundo={segundo}, primeiro={primeiro})",
    )


def test_3_falha_sem_nenhum_sucesso_anterior_retorna_vazio():
    """So' retorna {} quando NUNCA houve sucesso - quem chama (data/mercado.py)
    trata isso como o unico caso legitimo de cair pro fallback estatico curado."""
    _limpar_cache()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req:
        resposta_falha = MagicMock()
        resposta_falha.status_code = 500
        mock_req.get.return_value = resposta_falha
        resultado = ibovespa_mod.obter_composicao_oficial()
    _checar("3 sem sucesso anterior nenhum -> {} (nunca inventa papel)", resultado == {})


def test_4_resposta_200_mas_results_vazio_tambem_reaproveita_fallback():
    _limpar_cache()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req:
        mock_req.get.return_value = _resposta_ok([_item("ITUB4")])
        primeiro = ibovespa_mod.obter_composicao_oficial()

    ibovespa_mod.obter_composicao_oficial.clear()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req:
        mock_req.get.return_value = _resposta_ok([])  # 200 OK mas sem resultados
        segundo = ibovespa_mod.obter_composicao_oficial()

    _checar("4 200 com results=[] nao sobrescreve a composicao boa anterior", segundo == primeiro, f"({segundo} vs {primeiro})")


def test_5_excecao_de_rede_tambem_reaproveita_fallback():
    _limpar_cache()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req:
        mock_req.get.return_value = _resposta_ok([_item("BBAS3")])
        primeiro = ibovespa_mod.obter_composicao_oficial()

    ibovespa_mod.obter_composicao_oficial.clear()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req:
        mock_req.get.side_effect = Exception("timeout")
        segundo = ibovespa_mod.obter_composicao_oficial()

    _checar("5 excecao de rede reaproveita a composicao boa anterior", segundo == primeiro, f"({segundo} vs {primeiro})")


def test_6_sucesso_registra_tentativa_ok_em_saude_dos_dados():
    # bug real corrigido (auditoria missao coletores 2026-10-13,
    # continuacao): obter_composicao_oficial nunca chamava
    # registrar_tentativa - a B3 (fonte real de MERCADO/altas-baixas/
    # setorial/treemap/CALENDARIO) nao tinha NENHUMA representacao em
    # SAUDE DOS DADOS, nem sucesso nem falha.
    _limpar_cache()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req, \
         patch.object(ibovespa_mod, "registrar_tentativa") as mock_registrar:
        mock_req.get.return_value = _resposta_ok([_item("PETR4"), _item("VALE3")])
        ibovespa_mod.obter_composicao_oficial()
    _checar("6a registrar_tentativa chamado no sucesso", mock_registrar.called)
    args, kwargs = mock_registrar.call_args
    _checar("6b nome do coletor e' 'B3 (composição Ibovespa)'", args[0] == "B3 (composição Ibovespa)", f"(args={args})")
    _checar("6c execucao_ok=True e registros_novos=2 (nunca conta item vazio como novo)",
            kwargs.get("execucao_ok") is True and kwargs.get("registros_novos") == 2, f"(kwargs={kwargs})")


def test_6b_erro_de_rede_transitorio_se_recupera_na_segunda_tentativa():
    """2026-10-15: timeout/erro de conexao pontual nao deve cair direto
    pro fallback se uma 2a tentativa (curta, 1x so') resolver - mesmo
    espirito do retry ja existente em MERCADO pra lote de cotacoes."""
    _limpar_cache()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req, \
         patch.object(ibovespa_mod.time, "sleep") as mock_sleep:
        mock_req.get.side_effect = [OSError("timeout transitorio"), _resposta_ok([_item("PETR4")])]
        resultado = ibovespa_mod.obter_composicao_oficial()
    _checar("6b1 recupera na 2a tentativa (nao cai pro fallback vazio)", "PETR4" in resultado, f"(resultado={resultado})")
    _checar("6b2 fez exatamente 2 chamadas (1 original + 1 retry)", mock_req.get.call_count == 2)
    _checar("6b3 dormiu entre as tentativas (nao martela a fonte sem esperar)", mock_sleep.called)


def test_6c_falha_http_5xx_tenta_retry_curto():
    """Achado real 2026-10-17 (auditoria SAUDE DOS DADOS): a B3 respondeu
    HTTP 500 numa janela e voltou a responder 200 minutos depois, mesmo
    endpoint/payload - instabilidade transitoria de servidor, nao erro
    de requisicao. HTTP 500/502/503/504/429 agora ganha a MESMA 1 retry
    curta (backoff 1.5s) que erro de rede/timeout ja tinha."""
    _limpar_cache()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req, \
         patch.object(ibovespa_mod.time, "sleep") as mock_sleep:
        resposta_falha = MagicMock()
        resposta_falha.status_code = 500
        mock_req.get.return_value = resposta_falha
        ibovespa_mod.obter_composicao_oficial()
    _checar("6c1 faz 2 chamadas pra HTTP 500 (1 original + 1 retry)", mock_req.get.call_count == 2)
    _checar("6c2 dormiu entre as tentativas", mock_sleep.called)


def test_6d_falha_http_5xx_se_recupera_na_segunda_tentativa():
    """Reproduz o caso real: 1o HTTP 500, 2a tentativa volta 200 com a
    composicao completa - nao deve cair pro fallback cacheado."""
    _limpar_cache()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req, \
         patch.object(ibovespa_mod.time, "sleep") as mock_sleep:
        resposta_falha = MagicMock()
        resposta_falha.status_code = 500
        mock_req.get.side_effect = [resposta_falha, _resposta_ok([_item("PETR4")])]
        resultado = ibovespa_mod.obter_composicao_oficial()
    _checar("6d1 recupera na 2a tentativa apos HTTP 500", "PETR4" in resultado, f"(resultado={resultado})")
    _checar("6d2 fez exatamente 2 chamadas", mock_req.get.call_count == 2)
    _checar("6d3 dormiu entre as tentativas", mock_sleep.called)


def test_7_falha_http_registra_tentativa_com_erro_real():
    _limpar_cache()
    with patch.object(ibovespa_mod, "cffi_requests") as mock_req, \
         patch.object(ibovespa_mod, "registrar_tentativa") as mock_registrar:
        resposta_falha = MagicMock()
        resposta_falha.status_code = 500
        mock_req.get.return_value = resposta_falha
        ibovespa_mod.obter_composicao_oficial()
    kwargs = mock_registrar.call_args.kwargs
    _checar("7 HTTP 500 registra execucao_ok=False com o erro real (nunca finge sucesso)",
            kwargs.get("execucao_ok") is False and "500" in (kwargs.get("erro") or ""), f"(kwargs={kwargs})")


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
    print("TODOS OS TESTES DE IBOVESPA.PY PASSARAM")
