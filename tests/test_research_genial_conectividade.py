# -*- coding: utf-8 -*-
"""Testes de conectividade de data/research/genial.py (_tentar_buscar) -
mocka curl_cffi, nunca faz chamada de rede real.

Auditoria 2026-10-16: rodando direto da maquina real do Rodrigo (fora de
qualquer sandbox), a Genial continuou indisponivel - confirmado em 2
modos distintos e reproduziveis: HTTP/2 "stream reset by server" (ativo,
~0.1s) com impersonate=chrome auto, e timeout completo sem nenhum byte
recebido (passivo, 10-15s) com HTTP/1.1 forcado. Os dois sao tratados
exatamente da mesma forma por _tentar_buscar - cobrindo aqui pra garantir
que nenhum dos 2 modos faz a funcao propagar excecao ou travar o
orcamento de tempo."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.genial as genial_mod


def _resposta_ok(texto="<html>ok</html>"):
    r = MagicMock()
    r.status_code = 200
    r.text = texto
    return r


def test_tentar_buscar_sucesso_na_primeira_tentativa_nao_tenta_as_outras():
    with patch.object(genial_mod.cffi_requests, "get", return_value=_resposta_ok()) as mock_get:
        r, rotulo = genial_mod._tentar_buscar("https://x")
    assert r is not None
    assert mock_get.call_count == 1


def test_tentar_buscar_http2_stream_reset_cai_pra_proxima_tentativa():
    """Reproduz o sintoma real encontrado 2026-10-16: a 1a tentativa
    (impersonate=chrome, HTTP/1.1 forcado) sofre reset ativo; a 2a (HTTP/2
    auto) tambem - ambas tratadas como falha transitoria, nao excecao."""
    erro_reset = Exception(
        "Failed to perform, curl: (92) HTTP/2 stream 1 reset by server (error 0x2 INTERNAL_ERROR)."
    )
    with patch.object(genial_mod.cffi_requests, "get", side_effect=erro_reset):
        r, rotulo = genial_mod._tentar_buscar("https://x")
    assert r is None and rotulo is None


def test_tentar_buscar_timeout_silencioso_sem_bytes_cai_pra_proxima_tentativa():
    """Reproduz o 2o sintoma real: timeout completo sem nenhum byte
    recebido (bloqueio passivo, servidor nao responde nada)."""
    erro_timeout = TimeoutError(
        "Operation timed out after 15008 milliseconds with 0 bytes received."
    )
    with patch.object(genial_mod.cffi_requests, "get", side_effect=erro_timeout):
        r, rotulo = genial_mod._tentar_buscar("https://x")
    assert r is None and rotulo is None


def test_tentar_buscar_respeita_orcamento_total_e_para_antes_da_ultima_tentativa():
    """Com _ORCAMENTO_TOTAL_S esgotado, _tentar_buscar para ANTES de
    disparar as tentativas restantes - achado real da auditoria de
    performance (ver docstring do modulo): sem esse orcamento, timeouts
    de 10s x 4 tentativas podiam somar bem mais que o esperado."""
    chamadas = {"n": 0}

    def _tempo_falso():
        # chamada 1: calculo do `limite` inicial. chamada 2: checagem da
        # 1a iteracao do loop (dentro do orcamento, dispara a 1a
        # tentativa). chamada 3 em diante: orcamento ja esgotado - para
        # ANTES de disparar a 2a tentativa.
        chamadas["n"] += 1
        return 0 if chamadas["n"] <= 2 else 999

    with patch.object(genial_mod.time, "monotonic", side_effect=_tempo_falso), \
         patch.object(genial_mod.cffi_requests, "get", side_effect=Exception("timeout")) as mock_get:
        r, rotulo = genial_mod._tentar_buscar("https://x", orcamento_s=20)
    assert r is None and rotulo is None
    assert mock_get.call_count == 1  # parou apos a 1a, nunca tentou as outras 3


def test_buscar_next_data_retorna_none_quando_todas_as_tentativas_falham():
    genial_mod._buscar_next_data.clear()  # @st.cache_data - evita cache de outro teste
    with patch.object(genial_mod, "_tentar_buscar", return_value=(None, None)), \
         patch.object(genial_mod, "permitido", return_value=True):
        assert genial_mod._buscar_next_data() is None


def test_obter_relatorios_retorna_none_quando_conexao_cai():
    genial_mod.obter_relatorios.clear()  # @st.cache_data - evita cache de outro teste
    with patch.object(genial_mod, "_buscar_next_data", return_value=None):
        assert genial_mod.obter_relatorios() is None
