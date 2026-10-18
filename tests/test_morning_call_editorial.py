# -*- coding: utf-8 -*-
"""Cobertura de data/morning_call_editorial.py - camada de dado pura
(dict) que alimenta jobs/morning_call_pdf.py. Sem rede real: cada
provedor é mockado no nível de função, igual a tests/test_morning_call.py."""
from datetime import date, datetime, timezone
from unittest.mock import patch

import pandas as pd

import data.morning_call_editorial as ed

TZ_SP = ed.TZ_SP

_COT_OK = {"erro": None, "preco": 128_432.0, "variacao_pct": 1.23, "_barra_em": "2026-10-14T10:00:00-03:00"}
_COT_ERRO = {"erro": "sem dado"}


def _sem_rede(**overrides):
    base = dict(
        obter_cotacao_indice=lambda *_a, **_k: dict(_COT_ERRO),
        obter_historico=lambda *_a, **_k: None,
        obter_selic_meta=lambda: None,
        obter_cdi=lambda: None,
        obter_focus_ipca=lambda: None,
        obter_focus_selic=lambda: None,
        obter_top_mercado_tudo=lambda: [],
        calcular_calendario_cacheado=lambda *_a, **_k: [],
        obter_resumos_prontos=lambda *_a, **_k: {},
    )
    base.update(overrides)
    return base


class _MultiPatch:
    def __init__(self, **overrides):
        self._patches = [patch.object(ed, nome, fn) for nome, fn in _sem_rede(**overrides).items()]

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()


def test_brt_label_converte_fuso_de_origem_pra_horario_de_brasilia():
    # 14:30 em Nova York (UTC-4, horário de verão) -> 15:30 em Brasília (UTC-3).
    assert ed.brt_label("2026-10-14T14:30:00-04:00") == "14/10 15:30 (horário de Brasília)"


def test_brt_label_sem_valor_diz_indisponivel():
    assert ed.brt_label(None) == "indisponível"
    assert ed.brt_label("") == "indisponível"


def test_indicador_com_erro_nunca_inventa_preco():
    with _MultiPatch(obter_cotacao_indice=lambda *_a, **_k: dict(_COT_ERRO)):
        info = ed._indicador("Ibovespa", "^BVSP")
    assert info["preco"] is None
    assert info["erro"] == "sem dado"


def test_indicador_ok_reaproveita_mesmo_dado_do_provedor():
    with _MultiPatch(obter_cotacao_indice=lambda *_a, **_k: dict(_COT_OK)):
        info = ed._indicador("Ibovespa", "^BVSP")
    assert info["preco"] == 128_432.0
    assert info["variacao_pct"] == 1.23
    assert info["erro"] is None


def test_serie_fechamento_vazia_quando_historico_indisponivel():
    with _MultiPatch(obter_historico=lambda *_a, **_k: None):
        assert ed._serie_fechamento("^BVSP") == []


def test_serie_fechamento_le_data_e_close_do_historico():
    df = pd.DataFrame({
        "Data": pd.to_datetime(["2026-10-13", "2026-10-14"]),
        "Close": [127_000.0, 128_432.0],
    })
    with _MultiPatch(obter_historico=lambda *_a, **_k: df):
        serie = ed._serie_fechamento("^BVSP")
    assert len(serie) == 2
    assert serie[-1][1] == 128_432.0


def test_macro_rows_usa_ano_referencia_pro_focus_sem_formatar_como_dinheiro():
    """Mesma regressão corrigida em jobs/morning_call.py (2026-10-15):
    Focus IPCA/Selic usam coluna 'ano_referencia', não 'data'."""
    focus_ipca = pd.DataFrame({
        "ano_referencia": [2026],
        "mediana_pct": [5.22],
        "numero_respondentes": [144],
    })
    with _MultiPatch(obter_focus_ipca=lambda: focus_ipca):
        linhas = ed._macro_rows()
    linha_focus = next(l for l in linhas if l["indicador"] == "Focus IPCA")
    assert linha_focus["referencia"] == "2026"
    assert "numero respondentes: 144" in linha_focus["detalhe"]
    assert "2.026" not in linha_focus["detalhe"]


def test_macro_rows_indisponivel_quando_provedor_falha():
    with _MultiPatch(obter_selic_meta=lambda: (_ for _ in ()).throw(RuntimeError("fora do ar"))):
        linhas = ed._macro_rows()
    linha_selic = next(l for l in linhas if l["indicador"] == "Selic")
    assert linha_selic["detalhe"] == "indisponível"


def test_coletar_noticias_classifica_por_regiao_e_ticker():
    noticias = [
        {"titulo": "PETR4 anuncia dividendo", "link": "https://x/1", "regiao": "BR", "tickers": ["PETR4"]},
        {"titulo": "Governo anuncia pacote fiscal", "link": "https://x/2", "regiao": "BR", "tickers": []},
        {"titulo": "Fed sinaliza postura sobre juros", "link": "https://x/3", "regiao": "INT", "tickers": []},
    ]
    with _MultiPatch(obter_top_mercado_tudo=lambda: noticias):
        erro, brasil, empresas, exterior = ed._coletar_noticias()
    assert erro is None
    assert [i["titulo"] for i in brasil] == ["Governo anuncia pacote fiscal"]
    assert [i["titulo"] for i in empresas] == ["PETR4 anuncia dividendo"]
    assert [i["titulo"] for i in exterior] == ["Fed sinaliza postura sobre juros"]


def test_coletar_noticias_erro_devolve_mensagem_e_listas_vazias():
    with _MultiPatch(obter_top_mercado_tudo=lambda: (_ for _ in ()).throw(RuntimeError("Google News fora do ar"))):
        erro, brasil, empresas, exterior = ed._coletar_noticias()
    assert "RuntimeError" in erro
    assert brasil == [] and empresas == [] and exterior == []


def test_agenda_hoje_none_quando_calendario_falha():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with _MultiPatch(calcular_calendario_cacheado=lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("CVM fora do ar"))):
        assert ed._agenda_hoje(agora) is None


def test_agenda_hoje_lista_vazia_quando_nao_ha_evento():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with _MultiPatch(calcular_calendario_cacheado=lambda *_a, **_k: []):
        assert ed._agenda_hoje(agora) == []


def test_agenda_hoje_filtra_so_eventos_de_hoje_e_marca_tag_acompanhar():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    evento_hoje = {
        "ticker": "PETR4", "empresa": "Petrobras", "data": agora.date(),
        "horario": "08:00", "status": ed.STATUS_CONFIRMADO, "tipo_evento": "RESULTADO", "periodo": "3T26",
    }
    evento_futuro = {**evento_hoje, "ticker": "VALE3", "data": date(2026, 11, 1)}
    with _MultiPatch(calcular_calendario_cacheado=lambda *_a, **_k: [evento_hoje, evento_futuro]):
        agenda = ed._agenda_hoje(agora)
    assert len(agenda) == 1
    assert agenda[0]["ticker"] == "PETR4"
    assert agenda[0]["tag"] == ed.TAG_ACOMPANHAR


def test_montar_edicao_estrutura_completa_sem_rede():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with _MultiPatch():
        edicao = ed.montar_edicao(agora)
    assert edicao["agora"] == agora
    assert set(edicao.keys()) == {"agora", "capa", "brasil", "exterior", "empresas", "limitacoes", "fontes"}
    assert edicao["brasil"]["noticias"] is None
    assert edicao["brasil"]["destaque"] is None
    assert edicao["empresas"]["agenda"] == []
    assert len(edicao["exterior"]["interpretacoes"]) == 3
    assert all(i["tag"] == ed.TAG_INTERPRETACAO for i in edicao["exterior"]["interpretacoes"])


def test_cards_empresas_sem_resumo_mantem_tag_fato():
    """Card sem resumo cacheado mostra a manchete literal - tag continua FATO."""
    itens = [{"titulo": "PETR4 anuncia dividendo", "link": "https://x/1", "veiculos": ["InfoMoney"]}]
    with _MultiPatch(obter_resumos_prontos=lambda *_a, **_k: {}):
        cards = ed._cards_empresas(itens)
    assert len(cards) == 1
    assert cards[0]["tag"] == ed.TAG_FATO
    assert cards[0]["resumo"] is None


def test_cards_empresas_com_resumo_usa_tag_sintese_nao_fato():
    """Achado real (2026-10-18): quando ha' resumo de IA cacheado, o card
    passa a mostrar esse texto sintetizado em vez do titulo literal (ver
    jobs/morning_call_pdf.py: `card.get("resumo") or card.get("titulo")`) -
    a tag precisa acompanhar isso. Antes da correcao, `tag` continuava
    FATO mesmo com o texto exibido sendo sintese de IA."""
    itens = [{"titulo": "PETR4 anuncia dividendo", "link": "https://x/1", "veiculos": ["InfoMoney"]}]
    resumos = {"https://x/1": {"resumo": "Petrobras anuncia dividendo extraordinário, segundo comunicado.",
                                "imagem": "https://img/1.jpg", "link_original": "https://x/1"}}
    with _MultiPatch(obter_resumos_prontos=lambda *_a, **_k: resumos):
        cards = ed._cards_empresas(itens)
    assert len(cards) == 1
    assert cards[0]["tag"] == ed.TAG_SINTESE
    assert cards[0]["tag"] != ed.TAG_FATO
    assert cards[0]["resumo"] == resumos["https://x/1"]["resumo"]


def test_montar_edicao_capa_usa_top3_por_importancia():
    noticias = [
        {"titulo": "Baixa importância", "link": "https://x/1", "regiao": "INT", "tickers": [], "importancia": 1},
        {"titulo": "Alta importância", "link": "https://x/2", "regiao": "INT", "tickers": [], "importancia": 9},
        {"titulo": "Média importância", "link": "https://x/3", "regiao": "BR", "tickers": [], "importancia": 5},
    ]
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with _MultiPatch(obter_top_mercado_tudo=lambda: noticias):
        edicao = ed.montar_edicao(agora)
    titulos_capa = [d["titulo"] for d in edicao["capa"]["destaques"]]
    assert titulos_capa[0] == "Alta importância"
    assert "Baixa importância" in titulos_capa  # só 3 notícias no total, as 3 entram
