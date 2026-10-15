# -*- coding: utf-8 -*-
"""Testes de data/research/genial.py - _tentar_buscar (timeout, sucesso,
orcamento esgotado) e o motivo de falha exposto pra SAUDE DOS DADOS.
Mocka cffi_requests.get, nunca faz chamada de rede real.

Uso: python -m pytest tests/test_genial.py (venv do projeto)."""
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


def test_timeout_em_todas_as_tentativas_retorna_none_e_motivo_descreve_timeout():
    """Regressao real (auditoria 2026-10-15): confirmado em producao
    (GitHub Actions) que a Genial estoura o TIMEOUT (10s, 'Operation
    timed out ... 0 bytes received') - nao e' um bug de timeout curto
    demais, e' a fonte genuinamente nao respondendo a partir de rede de
    nuvem/datacenter."""
    genial_mod._ultimo_motivo_falha = None
    with patch.object(genial_mod, "cffi_requests") as mock_req:
        mock_req.get.side_effect = TimeoutError("Operation timed out after 10002 milliseconds")
        r, rotulo = genial_mod._tentar_buscar("https://analisa.genialinvestimentos.com.br", orcamento_s=0.01)
    assert r is None and rotulo is None
    motivo = genial_mod.motivo_ultima_falha()
    assert motivo is not None
    assert "esgotado" in motivo or "TimeoutError" in motivo


def test_sucesso_na_primeira_tentativa_zera_o_motivo_de_falha_anterior():
    genial_mod._ultimo_motivo_falha = "falha anterior qualquer"
    with patch.object(genial_mod, "cffi_requests") as mock_req:
        mock_req.get.return_value = _resposta_ok()
        r, rotulo = genial_mod._tentar_buscar("https://analisa.genialinvestimentos.com.br")
    assert r is not None
    assert "impersonate=chrome" in rotulo
    assert genial_mod.motivo_ultima_falha() is None


def test_http_2_reset_e_registrado_como_motivo_quando_todas_falham():
    """Sintoma real observado em producao: conexao chega no servidor mas
    e' resetada no HTTP/2 (comportamento de WAF/Akamai, nao timeout)."""
    genial_mod._ultimo_motivo_falha = None
    with patch.object(genial_mod, "cffi_requests") as mock_req:
        mock_req.get.side_effect = Exception("HTTP/2 stream 1 reset by server (error 0x2 INTERNAL_ERROR)")
        r, rotulo = genial_mod._tentar_buscar("https://analisa.genialinvestimentos.com.br")
    assert r is None
    motivo = genial_mod.motivo_ultima_falha()
    assert "Exception" in motivo and "tentativas falharam" in motivo


def test_http_nao_200_tambem_conta_como_tentativa_falha():
    genial_mod._ultimo_motivo_falha = None
    with patch.object(genial_mod, "cffi_requests") as mock_req:
        resposta_403 = MagicMock(status_code=403, text="bloqueado")
        mock_req.get.return_value = resposta_403
        r, rotulo = genial_mod._tentar_buscar("https://analisa.genialinvestimentos.com.br")
    assert r is None
    assert "HTTP 403" in genial_mod.motivo_ultima_falha()


def test_obter_relatorios_none_quando_home_falha_sem_lancar_excecao():
    genial_mod.obter_relatorios.clear()
    with patch.object(genial_mod, "_buscar_next_data", return_value=None):
        resultado = genial_mod.obter_relatorios()
    assert resultado is None
