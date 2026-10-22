# -*- coding: utf-8 -*-
"""Texto das matérias do Morning Call em camadas (data/morning_call_editorial.py:
_resumos_para_edicao). Regressão do envio real de 21/10/2026 (run
39630028404): "brasil=8 (0 com texto); empresas=2 (0 com texto); exterior=8
(0 com texto)" - a edição saiu só com manchetes."""
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import data.ia_cache as ia_cache
import data.morning_call_editorial as ed

AGORA = datetime(2026, 10, 21, 8, 3, tzinfo=ZoneInfo("America/Sao_Paulo"))
RESUMO = "RESUMO\nO Copom manteve a Selic em 15%, segundo o comunicado.\n\nLEITURA DE MERCADO\nInterpretação."


def _item(n, importancia=1, fontes=None):
    fontes = fontes or [{"veiculo": "Valor", "link": f"https://fonte/{n}"}]
    return {"titulo": f"Notícia {n}", "link": f"https://grupo/{n}", "fontes": fontes, "importancia": importancia}


def _rodar(itens, *, exata=None, por_url=None, gerar=None, api_key=None):
    chamadas = {"gerar": [], "por_url": []}

    def _por_url(links, desde):
        chamadas["por_url"].append((list(links), desde))
        return por_url or {}

    def _gerar(titulo, fontes, titulos=()):
        chamadas["gerar"].append(titulo)
        return (gerar or {}).get(titulo, {"resumo": None})

    with patch.object(ed, "obter_resumos_prontos", lambda grupos: exata or {}), \
         patch.object(ed, "obter_resumos_news_por_link", _por_url), \
         patch.object(ed, "obter_resumo_grupo", _gerar), \
         patch.object(ed.config, "obter_credenciais_groq", lambda: (api_key, "modelo")):
        prontos, stats = ed._resumos_para_edicao(itens, AGORA)
    return prontos, stats, chamadas


def test_chave_exata_continua_sendo_a_primeira_camada():
    itens = [_item(1)]
    prontos, stats, chamadas = _rodar(itens, exata={"https://grupo/1": {"resumo": RESUMO}})
    assert stats["exata"] == 1 and stats["sem_texto"] == 0
    assert chamadas["por_url"] == [] and chamadas["gerar"] == []


def test_resumo_achado_pela_url_da_fonte_quando_o_grupo_mudou():
    itens = [_item(1, fontes=[{"veiculo": "Valor", "link": "https://valor/a"},
                              {"veiculo": "InfoMoney", "link": "https://infomoney/b"}])]
    prontos, stats, chamadas = _rodar(itens, por_url={"https://infomoney/b": {"resumo": RESUMO}})
    assert prontos["https://grupo/1"]["resumo"] == RESUMO
    assert stats["por_url"] == 1 and stats["sem_texto"] == 0
    links, desde = chamadas["por_url"][0]
    assert set(links) == {"https://valor/a", "https://infomoney/b"}
    # janela da edição: nada anterior às 06:00 BRT do dia útil anterior
    assert desde.startswith("2026-10-20T09:00:00")


def test_foto_ja_validada_e_preservada_ao_achar_texto():
    itens = [_item(1)]
    exata = {"https://grupo/1": {"resumo": None, "imagem": "https://img/1.jpg", "imagem_status": "confirmada"}}
    prontos, _stats, _ = _rodar(itens, exata=exata, por_url={"https://fonte/1": {"resumo": RESUMO}})
    assert prontos["https://grupo/1"]["imagem"] == "https://img/1.jpg"
    assert prontos["https://grupo/1"]["resumo"] == RESUMO


def test_sem_chave_de_ia_nao_gera_e_registra_o_motivo():
    itens = [_item(1), _item(2)]
    _prontos, stats, chamadas = _rodar(itens, api_key=None)
    assert chamadas["gerar"] == []
    assert stats["sem_ia"] == "GROQ_API_KEY ausente" and stats["sem_texto"] == 2


def test_com_chave_gera_o_que_falta_por_importancia_e_com_limite():
    itens = [_item(n, importancia=n) for n in range(1, 16)]
    gerar = {f"Notícia {n}": {"resumo": RESUMO} for n in range(1, 16)}
    _prontos, stats, chamadas = _rodar(itens, gerar=gerar, api_key="chave")
    assert chamadas["gerar"][0] == "Notícia 15"  # mais importante primeiro
    assert len(chamadas["gerar"]) == ed._MAX_RESUMOS_GERADOS_EDICAO
    assert stats["gerados"] == ed._MAX_RESUMOS_GERADOS_EDICAO
    assert stats["sem_texto"] == 15 - ed._MAX_RESUMOS_GERADOS_EDICAO


def test_geracao_que_falha_nao_derruba_a_edicao():
    itens = [_item(1), _item(2)]

    def _quebra(*_a, **_k):
        raise RuntimeError("cota")

    with patch.object(ed, "obter_resumos_prontos", lambda g: {}), \
         patch.object(ed, "obter_resumos_news_por_link", lambda *_a: {}), \
         patch.object(ed, "obter_resumo_grupo", _quebra), \
         patch.object(ed.config, "obter_credenciais_groq", lambda: ("chave", "m")):
        _prontos, stats = ed._resumos_para_edicao(itens, AGORA)
    assert stats["sem_texto"] == 2 and stats["gerados"] == 0


def test_busca_por_url_filtra_news_concluido_janela_e_fica_com_o_mais_recente():
    cliente = MagicMock()
    consulta = cliente.table.return_value.select.return_value.in_.return_value
    final = consulta.eq.return_value.eq.return_value.gte.return_value.order.return_value
    final.execute.return_value.data = [
        {"link_principal": "https://a", "resultado": {"resumo": "novo"}, "atualizado_em": "2026-10-21T10:00:00Z"},
        {"link_principal": "https://a", "resultado": {"resumo": "velho"}, "atualizado_em": "2026-10-21T09:00:00Z"},
        {"link_principal": "https://b", "resultado": {"resumo": None}, "atualizado_em": "2026-10-21T09:00:00Z"},
    ]
    with patch.object(ia_cache, "obter_cliente", return_value=cliente):
        achados = ia_cache.obter_resumos_news_por_link(["https://a", "https://b", "https://a"], "2026-10-20T09:00:00+00:00")
    assert achados == {"https://a": {"resumo": "novo"}}
    consulta.eq.assert_called_with("origem", "news")
    consulta.eq.return_value.eq.assert_called_with("status", "concluido")
    consulta.eq.return_value.eq.return_value.gte.assert_called_with("atualizado_em", "2026-10-20T09:00:00+00:00")


def test_busca_por_url_sem_banco_ou_sem_links_devolve_vazio():
    assert ia_cache.obter_resumos_news_por_link([], "x") == {}
    with patch.object(ia_cache, "obter_cliente", return_value=None):
        assert ia_cache.obter_resumos_news_por_link(["https://a"], "x") == {}


def test_log_da_edicao_explica_de_onde_veio_o_texto():
    from jobs import morning_call as mc

    edicao = {"brasil": {"noticias": [{"corpo": ["p"]}], "indicadores": []}, "empresas": {"cards": []},
              "exterior": {"noticias": []},
              "texto_stats": {"exata": 1, "por_url": 2, "gerados": 0, "sem_texto": 5,
                              "sem_ia": "GROQ_API_KEY ausente", "orcamento_esgotado": False}}
    linha = mc._resumo_edicao(edicao, b"%PDF")
    assert "1 cache exato, 2 pela URL da fonte, 0 gerado(s) agora, 5 só manchete (GROQ_API_KEY ausente)" in linha
