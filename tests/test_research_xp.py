# -*- coding: utf-8 -*-
"""Testes de data/research/xp.py - mocka curl_cffi/requests, nunca faz
chamada de rede real.

Auditoria 2026-10-16 (coletores Genial/XP sempre FALHOU no log desde
24/09): rodando os dois coletores direto da maquina real do Rodrigo
(fora de qualquer sandbox), XP continuou devolvendo HTTP 403 em toda
tentativa (curl_cffi impersonate=chrome E requests com UA comum) - nao
e' bloqueio por User-Agent/TLS, e' um bloqueio de BORDA do Akamai por
IP/reputacao: o corpo da resposta e' uma pagina "Acesso Bloqueado" com
Reference ID + IP bloqueado, cabecalho `edge-rsp-blk: true` confirma que
a origem (WordPress) nunca chegou a ser consultada. O FIXTURE abaixo e'
o corpo REAL capturado nessa investigacao (requisicao real contra
conteudos.xpi.com.br), nao um exemplo inventado."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.xp as xp_mod

# corpo real devolvido pelo Akamai em 2026-10-16 (ver PROGRESSO.md,
# auditoria "CORRECAO DEFINITIVA DOS COLETORES") - IP/Reference ID reais
# daquela execucao, preservados aqui so' como fixture de formato.
_CORPO_BLOQUEIO_AKAMAI_REAL = """<html>
	<head>
		<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
			<title>Acesso Bloqueado</title>
	</head>
	<body>
		<blockquote><table border="0" cellpadding="1" width="80%"><tbody><tr><td><img src="https://www.xpi.com.br/assets/images/xp-inc-hero.png"></td></tr></tbody></table></blockquote>
		<br><br><br>
		<blockquote>
			<table border="0" cellpadding="1" width="80%">
				<tbody><tr><td>
					<font face="Helvetica"><big><strong>A sua requisição foi bloqueada. Caso esteja com problemas para acessar nossos serviços, por favor entre em contato através do e-mail bloqueio-cdn@xpi.com.br com as informações apresentadas no texto abaixo.</strong></big><br></font>
					<br><br>
					<font face="Helvetica">
						<strong>Reference ID:</strong> 0.8c91002.1792183300.242dd338<br>
						<strong>Endereço IP:</strong> 186.235.126.240
						<br><br>
					</font>
				</td></tr></tbody>
			</table>
		</blockquote>
	</body>
</html>"""


def _resposta(status_code, text="", json_data=None):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    if json_data is not None:
        r.json.return_value = json_data
    else:
        r.json.side_effect = ValueError("no JSON")
    return r


def test_detalhe_bloqueio_cdn_extrai_reference_id_e_ip_do_corpo_real():
    detalhe = xp_mod._detalhe_bloqueio_cdn(_CORPO_BLOQUEIO_AKAMAI_REAL)
    assert "0.8c91002.1792183300.242dd338" in detalhe
    assert "186.235.126.240" in detalhe
    assert "bloqueio-cdn@xpi.com.br" in detalhe


def test_detalhe_bloqueio_cdn_corpo_generico_nao_inventa_reference_id():
    assert xp_mod._detalhe_bloqueio_cdn("<html><body>Forbidden</body></html>") == ""
    assert xp_mod._detalhe_bloqueio_cdn("") == ""
    assert xp_mod._detalhe_bloqueio_cdn(None) == ""


def test_tentar_requisitar_loga_reference_id_quando_403_e_pagina_akamai(capsys):
    resposta_403 = _resposta(403, text=_CORPO_BLOQUEIO_AKAMAI_REAL)
    with patch.object(xp_mod.cffi_requests, "get", return_value=resposta_403), \
         patch.object(xp_mod.plain_requests, "get", return_value=resposta_403):
        r, rotulo = xp_mod._tentar_requisitar("https://conteudos.xpi.com.br/x", {})
    assert r is None and rotulo is None
    saida = capsys.readouterr().out
    assert "0.8c91002.1792183300.242dd338" in saida
    assert "bloqueio-cdn@xpi.com.br" in saida


def test_tentar_requisitar_sucesso_na_segunda_tentativa():
    resposta_403 = _resposta(403, text="generico")
    resposta_200 = _resposta(200, json_data=[{"id": 1}])
    with patch.object(xp_mod.cffi_requests, "get", return_value=resposta_403), \
         patch.object(xp_mod.plain_requests, "get", return_value=resposta_200):
        r, rotulo = xp_mod._tentar_requisitar("https://conteudos.xpi.com.br/x", {})
    assert r is resposta_200
    assert rotulo == "requests+UA-comum+Accept-json"


def test_tentar_requisitar_excecao_de_conexao_nao_propaga():
    with patch.object(xp_mod.cffi_requests, "get", side_effect=ConnectionError("timeout")), \
         patch.object(xp_mod.plain_requests, "get", side_effect=ConnectionError("timeout")):
        r, rotulo = xp_mod._tentar_requisitar("https://conteudos.xpi.com.br/x", {})
    assert r is None and rotulo is None


# ============================================================
# categoria_ultima_falha() - classificacao usada por coletor_local.py
# pra decidir o exit code sem mascarar uma falha nova (auditoria
# 2026-10-18, ver data/research/__init__.py:_classificar_falha e
# coletor_local.py:_falha_critica).
# ============================================================

def test_categoria_bloqueio_akamai_real_e_bloqueio_externo_conhecido():
    """Item 1 da missao: XP falhando com o padrao de bloqueio externo
    JA documentado (pagina real 'Acesso Bloqueado' + Reference ID) ->
    'bloqueio_externo_conhecido', nao 'erro'."""
    resposta_403 = _resposta(403, text=_CORPO_BLOQUEIO_AKAMAI_REAL)
    with patch.object(xp_mod.cffi_requests, "get", return_value=resposta_403), \
         patch.object(xp_mod.plain_requests, "get", return_value=resposta_403):
        xp_mod._tentar_requisitar("https://conteudos.xpi.com.br/x", {})
    assert xp_mod.categoria_ultima_falha() == "bloqueio_externo_conhecido"


def test_categoria_403_generico_sem_pagina_akamai_e_erro():
    """Um 403 QUALQUER (sem a pagina real do Akamai, ex: outro WAF ou
    bloqueio generico) nao pode virar 'bloqueio_externo_conhecido' so'
    por ser 403 - so' o padrao especifico ja documentado conta."""
    resposta_403 = _resposta(403, text="<html><body>Forbidden</body></html>")
    with patch.object(xp_mod.cffi_requests, "get", return_value=resposta_403), \
         patch.object(xp_mod.plain_requests, "get", return_value=resposta_403):
        xp_mod._tentar_requisitar("https://conteudos.xpi.com.br/x", {})
    assert xp_mod.categoria_ultima_falha() == "erro"


def test_categoria_http_500_novo_e_erro_nao_bloqueio_conhecido():
    """Item 3 da missao: se a XP comecar a devolver um erro DIFERENTE do
    403/Akamai conhecido (ex: HTTP 500), isso e' uma mudanca real de
    comportamento - tem que continuar derrubando o exit code, nunca ser
    mascarado como 'e' o mesmo bloqueio de sempre'."""
    resposta_500 = _resposta(500, text="Internal Server Error")
    with patch.object(xp_mod.cffi_requests, "get", return_value=resposta_500), \
         patch.object(xp_mod.plain_requests, "get", return_value=resposta_500):
        xp_mod._tentar_requisitar("https://conteudos.xpi.com.br/x", {})
    assert xp_mod.categoria_ultima_falha() == "erro"


def test_categoria_sem_falha_registrada_e_erro_nunca_bloqueio_por_padrao():
    """Item 6 da missao: motivo ausente (nenhuma falha registrada nesta
    sessao do processo, ou ultima chamada teve sucesso) nunca pode virar
    'bloqueio_externo_conhecido' por padrao/default."""
    xp_mod._ultimo_motivo_falha = None
    assert xp_mod.categoria_ultima_falha() == "erro"


def test_obter_relatorios_todas_as_fontes_bloqueadas_retorna_none():
    xp_mod.obter_relatorios.clear()  # @st.cache_data - evita cache de outro teste
    with patch.object(xp_mod, "_requisitar", return_value=None), \
         patch.object(xp_mod, "permitido", return_value=True):
        resultado = xp_mod.obter_relatorios()
    assert resultado is None


def test_obter_relatorios_isola_falha_por_tipo_de_post():
    """Um tipo de post bloqueado (None) nao pode descartar os itens de
    outro tipo que respondeu normalmente - mesmo padrao de degradacao
    graciosa documentado no modulo."""
    xp_mod.obter_relatorios.clear()  # @st.cache_data - evita cache de outro teste
    item_ok = {
        "title": {"rendered": "Relatorio OK"}, "date": "2026-10-16T10:00:00",
        "custom_data": {}, "class_list": ["tag-petr4"], "link": "https://x/r",
    }

    def _fake_requisitar(path, params):
        if "rel-acoes-fund" in path:
            return [item_ok]
        return None

    with patch.object(xp_mod, "_requisitar", side_effect=_fake_requisitar):
        resultado = xp_mod.obter_relatorios()
    assert resultado is not None and len(resultado) == 1
    assert resultado[0]["titulo"] == "Relatorio OK"
    assert resultado[0]["tickers"] == ["PETR4"]


def test_requisitar_respeita_robots_txt_antes_de_chamar_rede():
    with patch.object(xp_mod, "permitido", return_value=False) as mock_permitido, \
         patch.object(xp_mod, "_tentar_requisitar") as mock_tentar:
        resultado = xp_mod._requisitar("/wp-json/wp/v2/rel-acoes-fund", {"per_page": 1})
    assert resultado is None
    assert mock_permitido.called
    assert not mock_tentar.called
