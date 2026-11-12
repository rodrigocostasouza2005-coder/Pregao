# -*- coding: utf-8 -*-
"""Testes da arquitetura comum dos coletores de research (auditoria
Agente A, 2026-11-12) - contrato padrao de item, retry com backoff,
cooldown generico por chave, e a orquestracao generica de "sitemap + N
paginas individuais" extraida pra data/research/base.py. Tudo mockado
(sem rede real) - os testes de comportamento OBSERVAVEL de cada casa
sitemap continuam em tests/test_research_<casa>.py (esta extracao nunca
mudou o resultado deles, so' onde o codigo mora - ver lá).

Uso: python -m pytest tests/test_research_base_contrato.py"""
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.base as base_mod


# ============================================================
# Contrato padrao de item
# ============================================================

def test_validar_item_ok_quando_todos_obrigatorios_presentes():
    item = {"casa": "X", "titulo": "Y", "tipo": "ACOES", "link": "https://x/1"}
    assert base_mod.validar_item(item) == []


def test_validar_item_lista_cada_campo_obrigatorio_faltante():
    item = {"casa": "X", "titulo": ""}  # tipo/link ausentes, titulo vazio
    faltantes = base_mod.validar_item(item)
    assert "titulo" in faltantes
    assert "tipo" in faltantes
    assert "link" in faltantes
    assert "casa" not in faltantes


def test_validar_item_nao_e_dict_todos_faltantes():
    assert base_mod.validar_item(None) == list(base_mod.CAMPOS_OBRIGATORIOS_ITEM)


def test_normalizar_item_preenche_opcionais_ausentes_sem_inventar_valor():
    item = {"casa": "X", "titulo": "Y", "tipo": "ACOES", "link": "https://x/1"}
    normalizado = base_mod.normalizar_item(item)
    assert normalizado["empresa"] is None
    assert normalizado["setor"] == ""
    assert normalizado["preco_referencia"] is None
    assert normalizado["horizonte"] is None
    assert normalizado["texto_integral_disponivel"] is False
    # obrigatorios preservados intactos
    assert normalizado["casa"] == "X"
    assert normalizado["link"] == "https://x/1"


def test_normalizar_item_nunca_sobrescreve_valor_real_ja_presente():
    item = {
        "casa": "X", "titulo": "Y", "tipo": "ACOES", "link": "https://x/1",
        "setor": "Bancos", "empresa": "Banco X", "texto_integral_disponivel": True,
    }
    normalizado = base_mod.normalizar_item(item)
    assert normalizado["setor"] == "Bancos"
    assert normalizado["empresa"] == "Banco X"
    assert normalizado["texto_integral_disponivel"] is True


def test_normalizar_item_devolve_copia_nao_muta_original():
    item = {"casa": "X", "titulo": "Y", "tipo": "ACOES", "link": "https://x/1"}
    base_mod.normalizar_item(item)
    assert "setor" not in item  # original intocado


def test_campos_canonicos_para_store_cobre_todo_o_vocabulario_do_pedido():
    pedido_original = {
        "casa", "analista", "empresa", "ticker", "setor", "data_publicacao",
        "tipo_relatorio", "recomendacao", "preco_alvo", "preco_referencia",
        "horizonte", "url_fonte", "texto_integral_disponivel",
    }
    assert pedido_original == set(base_mod.CAMPOS_CANONICOS_PARA_STORE.keys())


# ============================================================
# Retry com backoff
# ============================================================

def test_requisitar_com_retry_sucesso_de_primeira_nao_dorme():
    chamadas = []
    dormidas = []
    resultado = base_mod.requisitar_com_retry(
        lambda: (chamadas.append(1), "ok")[1],
        tentativas=3, dormir=lambda s: dormidas.append(s),
    )
    assert resultado == "ok"
    assert len(chamadas) == 1
    assert dormidas == []


def test_requisitar_com_retry_tenta_de_novo_apos_excecao_transiente():
    chamadas = []

    def _fn():
        chamadas.append(1)
        if len(chamadas) < 2:
            raise ConnectionError("falhou na 1a")
        return "ok na 2a"

    dormidas = []
    resultado = base_mod.requisitar_com_retry(
        _fn, tentativas=3, espera_inicial_s=1.0, fator_backoff=2.0,
        excecoes=(ConnectionError,), dormir=lambda s: dormidas.append(s),
    )
    assert resultado == "ok na 2a"
    assert len(chamadas) == 2
    assert dormidas == [1.0]  # so' 1 espera, antes da 2a tentativa


def test_requisitar_com_retry_esgota_tentativas_relanca_ultima_excecao():
    def _fn():
        raise ConnectionError("sempre falha")

    with pytest.raises(ConnectionError):
        base_mod.requisitar_com_retry(_fn, tentativas=3, dormir=lambda s: None)


def test_requisitar_com_retry_nao_retenta_excecao_fora_da_lista():
    chamadas = []

    def _fn():
        chamadas.append(1)
        raise ValueError("erro permanente, nunca deveria retentar")

    with pytest.raises(ValueError):
        base_mod.requisitar_com_retry(
            _fn, tentativas=3, excecoes=(ConnectionError,), dormir=lambda s: None,
        )
    assert len(chamadas) == 1  # propagou na 1a, sem retry


def test_requisitar_com_retry_backoff_exponencial_entre_tentativas():
    chamadas = []

    def _fn():
        chamadas.append(1)
        raise ConnectionError("falha")

    dormidas = []
    with pytest.raises(ConnectionError):
        base_mod.requisitar_com_retry(
            _fn, tentativas=4, espera_inicial_s=0.5, fator_backoff=2.0,
            dormir=lambda s: dormidas.append(s),
        )
    assert dormidas == [0.5, 1.0, 2.0]  # 3 esperas entre as 4 tentativas


# ============================================================
# Cooldown generico por chave
# ============================================================

def test_cooldown_nao_ativo_sem_nenhuma_tentativa_marcada():
    cooldown = base_mod.CooldownPorChave(janela_s=60)
    assert cooldown.em_cooldown("casa-x") is False
    assert cooldown.tempo_restante_s("casa-x") == 0.0


def test_cooldown_ativo_logo_apos_marcar_tentativa():
    cooldown = base_mod.CooldownPorChave(janela_s=60)
    cooldown.marcar_tentativa("casa-x")
    assert cooldown.em_cooldown("casa-x") is True
    assert cooldown.tempo_restante_s("casa-x") > 0


def test_cooldown_expira_apos_a_janela():
    cooldown = base_mod.CooldownPorChave(janela_s=60)
    with patch.object(time, "monotonic", return_value=1000.0):
        cooldown.marcar_tentativa("casa-x")
    with patch.object(time, "monotonic", return_value=1000.0 + 61):
        assert cooldown.em_cooldown("casa-x") is False


def test_cooldown_chaves_diferentes_sao_independentes():
    cooldown = base_mod.CooldownPorChave(janela_s=60)
    cooldown.marcar_tentativa("casa-a")
    assert cooldown.em_cooldown("casa-a") is True
    assert cooldown.em_cooldown("casa-b") is False


def test_cooldown_janela_por_chamada_sobrescreve_a_janela_padrao():
    """Caso real: data/research/__init__.py:coletar_pendentes usa a MESMA
    instancia pra cooldown por casa (janela padrao, 10min) e pro throttle
    de limpeza (janela maior, 1h, so' na chave '_limpeza')."""
    cooldown = base_mod.CooldownPorChave(janela_s=60)
    with patch.object(time, "monotonic", return_value=1000.0):
        cooldown.marcar_tentativa("_limpeza")
    with patch.object(time, "monotonic", return_value=1000.0 + 61):
        # expirou pra janela padrao (60s)...
        assert cooldown.em_cooldown("_limpeza") is False
        # ...mas ainda em cooldown pra uma janela maior passada explicitamente
        assert cooldown.em_cooldown("_limpeza", janela_s=3600) is True


# ============================================================
# testar_conexao_url (generaliza testar_conexao de cada casa sitemap)
# ============================================================

def _resp(status_code=200, content=b"", text="<html></html>", headers=None):
    class _R:
        pass
    r = _R()
    r.status_code = status_code
    r.content = content
    r.text = text
    r.headers = headers or {"content-type": "application/xml"}
    return r


def test_testar_conexao_url_bloqueado_por_robots():
    ok, detalhe = base_mod.testar_conexao_url("https://x/sitemap.xml", permitido_fn=lambda u: False)
    assert ok is False
    assert "robots" in detalhe


def test_testar_conexao_url_sucesso():
    with patch.object(base_mod.requests, "get", return_value=_resp(200, content=b"abc")):
        ok, detalhe = base_mod.testar_conexao_url("https://x/sitemap.xml", permitido_fn=lambda u: True)
    assert ok is True
    assert "OK" in detalhe


def test_testar_conexao_url_http_erro():
    with patch.object(base_mod.requests, "get", return_value=_resp(503)):
        ok, detalhe = base_mod.testar_conexao_url("https://x/sitemap.xml", permitido_fn=lambda u: True)
    assert ok is False
    assert "503" in detalhe


def test_testar_conexao_url_excecao_de_rede():
    with patch.object(base_mod.requests, "get", side_effect=ConnectionError("falhou")):
        ok, detalhe = base_mod.testar_conexao_url("https://x/sitemap.xml", permitido_fn=lambda u: True)
    assert ok is False
    assert "ConnectionError" in detalhe


# ============================================================
# coletar_via_sitemap (orquestracao generica - comportamento observavel
# equivalente ao antigo obter_relatorios() hand-rolled de cada casa, ver
# tests/test_research_jpmorgan.py etc. pra confirmacao fim-a-fim por casa)
# ============================================================

_SITEMAP_FAKE = (
    b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    b"<url><loc>https://x.com/a</loc><lastmod>2026-11-10</lastmod></url>"
    b"<url><loc>https://x.com/b</loc><lastmod>2026-11-09</lastmod></url>"
    b"</urlset>"
)


def _candidatos_fake(conteudo: bytes) -> list:
    from xml.etree import ElementTree as ET
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(conteudo)
    out = []
    for url in root.findall("sm:url", ns):
        loc = url.find("sm:loc", ns).text
        lastmod = url.find("sm:lastmod", ns).text
        out.append((lastmod, loc))
    out.sort(key=lambda c: c[0], reverse=True)
    return out


def _item_fake_ok(html, loc):
    return {"casa": "Fake", "titulo": f"titulo de {loc}", "tipo": "MACRO", "link": loc}


def test_coletar_via_sitemap_bloqueado_por_robots():
    itens, motivo = base_mod.coletar_via_sitemap(
        sitemap_url="https://x.com/sitemap.xml", candidatos_do_sitemap=_candidatos_fake,
        parser_item=_item_fake_ok, permitido_fn=lambda u: False,
    )
    assert itens is None
    assert "robots" in motivo


def test_coletar_via_sitemap_sucesso_fim_a_fim():
    with patch.object(base_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP_FAKE), _resp(200), _resp(200)]
        itens, motivo = base_mod.coletar_via_sitemap(
            sitemap_url="https://x.com/sitemap.xml", candidatos_do_sitemap=_candidatos_fake,
            parser_item=_item_fake_ok, permitido_fn=lambda u: True,
        )
    assert motivo is None
    assert len(itens) == 2


def test_coletar_via_sitemap_sem_candidato_lista_vazia_nao_none():
    sitemap_vazio = b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    with patch.object(base_mod.requests, "get", return_value=_resp(200, content=sitemap_vazio)):
        itens, motivo = base_mod.coletar_via_sitemap(
            sitemap_url="https://x.com/sitemap.xml", candidatos_do_sitemap=_candidatos_fake,
            parser_item=_item_fake_ok, permitido_fn=lambda u: True,
        )
    assert itens == []
    assert motivo is None


def test_coletar_via_sitemap_todas_paginas_falham_retorna_none_com_motivo():
    with patch.object(base_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP_FAKE), _resp(404), _resp(404)]
        itens, motivo = base_mod.coletar_via_sitemap(
            sitemap_url="https://x.com/sitemap.xml", candidatos_do_sitemap=_candidatos_fake,
            parser_item=_item_fake_ok, permitido_fn=lambda u: True,
            descricao_esperada="com o campo esperado",
        )
    assert itens is None
    assert "nenhuma página individual respondeu" in motivo
    assert "com o campo esperado" in motivo


def test_coletar_via_sitemap_descricao_esperada_vazia_sem_trailing_space():
    with patch.object(base_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP_FAKE), _resp(404), _resp(404)]
        itens, motivo = base_mod.coletar_via_sitemap(
            sitemap_url="https://x.com/sitemap.xml", candidatos_do_sitemap=_candidatos_fake,
            parser_item=_item_fake_ok, permitido_fn=lambda u: True,
            descricao_esperada="",
        )
    assert motivo.endswith("respondeu")  # sem espaco sobrando no fim


def test_coletar_via_sitemap_passa_lastmod_ao_parser_quando_pedido():
    capturados = []

    def _parser_com_lastmod(html, loc, lastmod):
        capturados.append((loc, lastmod))
        return {"casa": "Fake", "titulo": "t", "tipo": "MACRO", "link": loc}

    with patch.object(base_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=_SITEMAP_FAKE), _resp(200), _resp(200)]
        base_mod.coletar_via_sitemap(
            sitemap_url="https://x.com/sitemap.xml", candidatos_do_sitemap=_candidatos_fake,
            parser_item=_parser_com_lastmod, permitido_fn=lambda u: True,
            passar_lastmod_ao_parser=True,
        )
    assert len(capturados) == 2
    assert all(lastmod for _, lastmod in capturados)


def test_coletar_via_sitemap_limita_max_itens():
    sitemap_grande = b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + b"".join(
        f'<url><loc>https://x.com/{i}</loc><lastmod>2026-11-{i:02d}</lastmod></url>'.encode()
        for i in range(1, 11)
    ) + b"</urlset>"
    with patch.object(base_mod.requests, "get") as mock_get:
        mock_get.side_effect = [_resp(200, content=sitemap_grande)] + [_resp(200) for _ in range(50)]
        base_mod.coletar_via_sitemap(
            sitemap_url="https://x.com/sitemap.xml", candidatos_do_sitemap=_candidatos_fake,
            parser_item=_item_fake_ok, permitido_fn=lambda u: True, max_itens=3,
        )
    assert mock_get.call_count <= 1 + 3


def test_coletar_via_sitemap_sitemap_malformado_retorna_none():
    with patch.object(base_mod.requests, "get", return_value=_resp(200, content=b"nao e xml")):
        itens, motivo = base_mod.coletar_via_sitemap(
            sitemap_url="https://x.com/sitemap.xml", candidatos_do_sitemap=_candidatos_fake,
            parser_item=_item_fake_ok, permitido_fn=lambda u: True,
        )
    assert itens is None
    assert "XML" in motivo


def test_coletar_via_sitemap_sitemap_http_erro():
    with patch.object(base_mod.requests, "get", return_value=_resp(503)):
        itens, motivo = base_mod.coletar_via_sitemap(
            sitemap_url="https://x.com/sitemap.xml", candidatos_do_sitemap=_candidatos_fake,
            parser_item=_item_fake_ok, permitido_fn=lambda u: True,
        )
    assert itens is None
    assert "503" in motivo


def test_coletar_via_sitemap_retenta_sitemap_apos_excecao_transiente():
    """A requisicao do SITEMAP (so' ela) usa requisitar_com_retry - uma
    falha de rede transiente na 1a tentativa nao derruba a coleta se a
    2a tentativa funcionar."""
    chamadas = []

    def _get(url, headers=None, timeout=None):
        chamadas.append(url)
        if url == "https://x.com/sitemap.xml" and len(chamadas) == 1:
            raise ConnectionError("instavel")
        if url == "https://x.com/sitemap.xml":
            return _resp(200, content=_SITEMAP_FAKE)
        return _resp(200)

    with patch.object(base_mod.requests, "get", side_effect=_get), \
         patch.object(base_mod.time, "sleep", return_value=None):
        itens, motivo = base_mod.coletar_via_sitemap(
            sitemap_url="https://x.com/sitemap.xml", candidatos_do_sitemap=_candidatos_fake,
            parser_item=_item_fake_ok, permitido_fn=lambda u: True,
        )
    assert motivo is None
    assert len(itens) == 2


def test_coletar_via_sitemap_pagina_individual_nunca_retenta():
    """Diferente do sitemap: 1 pagina que falha com excecao de rede NUNCA
    e' retentada (orcamento de tempo e' compartilhado entre paginas) -
    so' e' pulada, a proxima pagina do lote segue normalmente."""
    with patch.object(base_mod.requests, "get") as mock_get:
        mock_get.side_effect = [
            _resp(200, content=_SITEMAP_FAKE),
            ConnectionError("pagina a falhou"),
            _resp(200),
        ]
        itens, motivo = base_mod.coletar_via_sitemap(
            sitemap_url="https://x.com/sitemap.xml", candidatos_do_sitemap=_candidatos_fake,
            parser_item=_item_fake_ok, permitido_fn=lambda u: True,
        )
    # so' 3 chamadas no total (sitemap + 2 paginas, nenhum retry extra)
    assert mock_get.call_count == 3
    assert itens is not None
    assert len(itens) == 1  # a pagina que funcionou


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
