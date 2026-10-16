# -*- coding: utf-8 -*-
"""Testes de data/research/xp.py - _tentar_requisitar (HTTP 403, sucesso
via fallback, as 2 tentativas falhando) e o motivo de falha exposto pra
SAUDE DOS DADOS. Mocka cffi_requests/plain_requests, nunca faz chamada
de rede real.

Uso: python -m pytest tests/test_xp.py (venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.xp as xp_mod


def _resposta(status_code=200, json_data=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data if json_data is not None else []
    return r


def test_http_403_nas_2_tentativas_retorna_none_e_motivo_cita_403():
    """Regressao real (auditoria 2026-10-15): confirmado que a XP devolve
    403 tanto via curl_cffi (fingerprint TLS) quanto via requests puro
    (UA comum) - o bloqueio e' por IP/geografia, nao por TLS/UA, por
    isso as 2 estrategias falham identicamente."""
    xp_mod._ultimo_motivo_falha = None
    with patch.object(xp_mod, "cffi_requests") as mock_cffi, \
         patch.object(xp_mod, "plain_requests") as mock_plain:
        mock_cffi.get.return_value = _resposta(403)
        mock_plain.get.return_value = _resposta(403)
        r, rotulo = xp_mod._tentar_requisitar("https://conteudos.xpi.com.br/x", {})
    assert r is None and rotulo is None
    motivo = xp_mod.motivo_ultima_falha()
    assert "403" in motivo


def test_excecao_de_conexao_preserva_mensagem_especifica_no_motivo():
    """Bug real (auditoria 2026-10-16): ultimo_erro so' guardava
    type(e).__name__ ('Exception'), descartando a mensagem real da
    excecao (ex: 'TLS handshake falhou') - o motivo exposto pro painel
    SAUDE DOS DADOS ficava indistinguivel de qualquer outra falha
    generica, mesmo quando as 2 estrategias davam erros bem diferentes
    um do outro."""
    xp_mod._ultimo_motivo_falha = None
    with patch.object(xp_mod, "cffi_requests") as mock_cffi, \
         patch.object(xp_mod, "plain_requests") as mock_plain:
        mock_cffi.get.side_effect = Exception("TLS handshake falhou de verdade")
        mock_plain.get.side_effect = Exception("connection refused pelo CDN")
        r, rotulo = xp_mod._tentar_requisitar("https://conteudos.xpi.com.br/x", {})
    assert r is None and rotulo is None
    motivo = xp_mod.motivo_ultima_falha()
    assert "connection refused pelo CDN" in motivo


def test_sucesso_no_fallback_requests_puro_apos_curl_cffi_falhar():
    xp_mod._ultimo_motivo_falha = "falha anterior"
    with patch.object(xp_mod, "cffi_requests") as mock_cffi, \
         patch.object(xp_mod, "plain_requests") as mock_plain:
        mock_cffi.get.side_effect = Exception("TLS handshake falhou")
        mock_plain.get.return_value = _resposta(200, [{"id": 1}])
        r, rotulo = xp_mod._tentar_requisitar("https://conteudos.xpi.com.br/x", {})
    assert r is not None and rotulo == "requests+UA-comum+Accept-json"
    assert xp_mod.motivo_ultima_falha() is None


def test_obter_relatorios_none_so_quando_todas_as_categorias_falham():
    xp_mod.obter_relatorios.clear()
    with patch.object(xp_mod, "_requisitar", return_value=None):
        resultado = xp_mod.obter_relatorios()
    assert resultado is None


def test_obter_relatorios_degrada_parcialmente_quando_1_categoria_falha():
    """obter_relatorios nao e' tudo-ou-nada entre categorias: se
    rel-acoes-fund falhar mas rel-artigo-aloc responder, o relatorio da
    categoria que funcionou nao pode ser perdido."""
    xp_mod.obter_relatorios.clear()
    item_valido = {
        "title": {"rendered": "Estrategia de alocação"}, "date": "2026-10-15T10:00:00",
        "custom_data": {}, "class_list": ["tag-petr4"], "link": "https://x/1",
    }

    def _fake_requisitar(path, params):
        if "rel-acoes-fund" in path:
            return None
        return [item_valido]

    with patch.object(xp_mod, "_requisitar", side_effect=_fake_requisitar):
        resultado = xp_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) >= 1
    assert any(r["tickers"] == ["PETR4"] for r in resultado)


def test_obter_texto_aberto_sem_slug_retorna_motivo_claro():
    texto, motivo = xp_mod.obter_texto_aberto("")
    assert texto is None
    assert motivo == "link sem slug reconhecível"
