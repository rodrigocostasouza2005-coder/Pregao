# -*- coding: utf-8 -*-
"""Testes de data/research/btg.py - mocka requests, nunca faz chamada de
rede real.

Fixture de item baseada na estrutura REAL confirmada na investigacao
2026-10-17 (requisicao real contra content.btgpactual.com/api/research/
content-hub/analysis/filter): o campo "tier" vem no proprio lote, com
valores "AREA_PUBLICA"/"AREA_LOGADA" - ver docstring do modulo pros
detalhes completos da investigacao (robots.txt, amostra de 300 itens
reais, ausencia de bloqueio)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.btg as btg_mod


def _item(tier, caption="Análise", id_="abc123", analyze_asset=None, authors=None, ref_date="2026-10-16T10:00:00.000"):
    return {
        "id": id_,
        "tier": tier,
        "caption": caption,
        "referenceDate": ref_date,
        "analyzeAsset": analyze_asset or [],
        "authors": authors or [{"name": "Analista Exemplo"}],
        "analyzeComponents": {"body": "<p>texto</p>"},
    }


def _resposta(status_code, json_data=None):
    r = MagicMock()
    r.status_code = status_code
    if json_data is not None:
        r.json.return_value = json_data
    else:
        r.json.side_effect = ValueError("no JSON")
    return r


def test_obter_relatorios_filtra_area_logada_mantendo_so_area_publica():
    btg_mod._ultimo_motivo_falha = None
    itens_pagina = {
        "paging": {"pageNumber": 1, "pageSize": 25, "totalResults": 2},
        "response": [
            _item("AREA_PUBLICA", id_="publico-1", caption="Análise | PETR4"),
            _item("AREA_LOGADA", id_="logado-1", caption="Análise | VALE3"),
        ],
    }
    resposta_vazia = {"paging": {}, "response": []}
    with patch.object(btg_mod, "permitido", return_value=True), \
         patch.object(btg_mod.requests, "post") as mock_post:
        mock_post.side_effect = [
            _resposta(200, itens_pagina),
            _resposta(200, resposta_vazia),
            _resposta(200, resposta_vazia),
            _resposta(200, resposta_vazia),
        ]
        resultado = btg_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) == 1
    assert resultado[0]["link"] == btg_mod.DETAIL_URL.format(id="publico-1")
    assert "logado-1" not in str(resultado)


def test_item_sem_tier_reconhecido_nao_e_persistido():
    """Item sem campo 'tier' (ou com valor inesperado) tambem e' descartado
    - so' tier == 'AREA_PUBLICA' explicito entra no resultado, nunca por
    omissao/default."""
    item_sem_tier = _item(None, id_="sem-tier")
    item_sem_tier.pop("tier")
    item_tier_desconhecido = _item("ALGO_NOVO_DA_API", id_="tier-novo")
    itens_pagina = {"response": [item_sem_tier, item_tier_desconhecido]}
    resposta_vazia = {"response": []}
    with patch.object(btg_mod, "permitido", return_value=True), \
         patch.object(btg_mod.requests, "post") as mock_post:
        mock_post.side_effect = [
            _resposta(200, itens_pagina),
            _resposta(200, resposta_vazia),
            _resposta(200, resposta_vazia),
            _resposta(200, resposta_vazia),
        ]
        resultado = btg_mod.obter_relatorios()
    assert resultado is None  # nenhum item publico -> relatorios vazio -> None


def test_falha_em_1_pagina_nao_derruba_as_outras():
    """Mesmo padrao de degradacao graciosa de xp.py/genial.py - 1 pagina
    com erro de rede nao pode descartar itens que outra pagina trouxe."""
    pagina_ok = {"response": [_item("AREA_PUBLICA", id_="pub-2")]}
    with patch.object(btg_mod, "permitido", return_value=True), \
         patch.object(btg_mod.requests, "post") as mock_post:
        mock_post.side_effect = [
            ConnectionError("timeout"),
            _resposta(200, pagina_ok),
            _resposta(200, {"response": []}),
            _resposta(200, {"response": []}),
        ]
        resultado = btg_mod.obter_relatorios()
    assert resultado is not None
    assert len(resultado) == 1
    assert resultado[0]["link"] == btg_mod.DETAIL_URL.format(id="pub-2")


def test_obter_relatorios_todas_as_paginas_falham_retorna_none():
    btg_mod._ultimo_motivo_falha = None
    with patch.object(btg_mod, "permitido", return_value=True), \
         patch.object(btg_mod.requests, "post", side_effect=ConnectionError("timeout")):
        resultado = btg_mod.obter_relatorios()
    assert resultado is None
    assert btg_mod.motivo_ultima_falha() is not None
    assert "4" in btg_mod.motivo_ultima_falha()  # as 4 paginas falharam


def test_obter_relatorios_respeita_robots_txt_antes_de_chamar_rede():
    with patch.object(btg_mod, "permitido", return_value=False), \
         patch.object(btg_mod.requests, "post") as mock_post:
        resultado = btg_mod.obter_relatorios()
    assert resultado is None
    assert not mock_post.called


def test_1_item_malformado_na_pagina_nao_derruba_os_outros():
    item_bom = _item("AREA_PUBLICA", id_="bom")
    item_ruim = _item("AREA_PUBLICA", id_="ruim")
    del item_ruim["authors"]  # ainda deve funcionar (so' autor vazio) - nao e' esse o caso de quebra
    item_sem_id = {"tier": "AREA_PUBLICA"}  # sem "id" -> KeyError em _link, deve ser isolado
    itens_pagina = {"response": [item_bom, item_sem_id, item_ruim]}
    with patch.object(btg_mod, "permitido", return_value=True), \
         patch.object(btg_mod.requests, "post") as mock_post:
        mock_post.side_effect = [
            _resposta(200, itens_pagina),
            _resposta(200, {"response": []}),
            _resposta(200, {"response": []}),
            _resposta(200, {"response": []}),
        ]
        resultado = btg_mod.obter_relatorios()
    assert resultado is not None
    ids_presentes = {r["link"] for r in resultado}
    assert btg_mod.DETAIL_URL.format(id="bom") in ids_presentes
    assert btg_mod.DETAIL_URL.format(id="ruim") in ids_presentes
    assert len(resultado) == 2


def test_tickers_vem_do_analyze_asset_quando_presente():
    item = _item("AREA_PUBLICA", id_="t1", analyze_asset=[{"asset": {"ticker": "PETR4"}}])
    assert btg_mod._tickers(item) == ["PETR4"]


def test_tickers_fallback_pro_caption_quando_analyze_asset_vazio():
    item = _item("AREA_PUBLICA", id_="t2", caption="Análise | TOTS3, LWSA3, INTB3")
    assert btg_mod._tickers(item) == ["TOTS3", "LWSA3", "INTB3"]


def test_tipo_acoes_quando_tem_ticker_macro_quando_nao_tem():
    item_com_ticker = _item("AREA_PUBLICA", id_="t3", analyze_asset=[{"asset": {"ticker": "VALE3"}}])
    item_sem_ticker = _item("AREA_PUBLICA", id_="t4", caption="Análise")
    assert btg_mod._item_relatorio(item_com_ticker)["tipo"] == "ACOES"
    assert btg_mod._item_relatorio(item_sem_ticker)["tipo"] == "MACRO"


def test_testar_conexao_respeita_robots_txt():
    with patch.object(btg_mod, "permitido", return_value=False):
        ok, detalhe = btg_mod.testar_conexao()
    assert ok is False
    assert "robots" in detalhe


def test_obter_texto_publico_reconfirma_tier_antes_de_devolver_texto():
    """Defesa em profundidade: mesmo que o link tenha sido coletado como
    publico, obter_texto_publico reconsulta o detalhe e so' devolve texto
    se o tier AINDA for AREA_PUBLICA nesse momento."""
    link = btg_mod.DETAIL_URL.format(id="x1")
    detalhe_logado = {"tier": "AREA_LOGADA", "analyzeComponents": {"body": "<p>" + "a" * 300 + "</p>"}}
    with patch.object(btg_mod, "permitido", return_value=True), \
         patch.object(btg_mod.requests, "get", return_value=_resposta(200, detalhe_logado)):
        texto, motivo = btg_mod.obter_texto_publico(link)
    assert texto is None
    assert "AREA_PUBLICA" in motivo


def test_obter_texto_publico_sucesso_extrai_texto_do_body_html():
    link = btg_mod.DETAIL_URL.format(id="x2")
    corpo_html = "<p>" + "Texto de analise real sobre o ativo. " * 10 + "</p>"
    detalhe_publico = {"tier": "AREA_PUBLICA", "analyzeComponents": {"body": corpo_html}}
    with patch.object(btg_mod, "permitido", return_value=True), \
         patch.object(btg_mod.requests, "get", return_value=_resposta(200, detalhe_publico)):
        texto, motivo = btg_mod.obter_texto_publico(link)
    assert motivo is None
    assert texto is not None and "Texto de analise real" in texto
    assert "<p>" not in texto


def test_obter_texto_publico_corpo_curto_nao_vira_resumo():
    link = btg_mod.DETAIL_URL.format(id="x3")
    detalhe_publico = {"tier": "AREA_PUBLICA", "analyzeComponents": {"body": "<p>curto</p>"}}
    with patch.object(btg_mod, "permitido", return_value=True), \
         patch.object(btg_mod.requests, "get", return_value=_resposta(200, detalhe_publico)):
        texto, motivo = btg_mod.obter_texto_publico(link)
    assert texto is None
    assert motivo is not None


def test_obter_texto_publico_link_sem_id_nao_chama_rede():
    with patch.object(btg_mod.requests, "get") as mock_get:
        texto, motivo = btg_mod.obter_texto_publico("")
    assert texto is None
    assert not mock_get.called
