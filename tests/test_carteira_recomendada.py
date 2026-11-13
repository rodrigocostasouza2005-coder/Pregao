# -*- coding: utf-8 -*-
"""data/carteira_recomendada.py (módulo novo, missão "Frente 4"
2026-11-12/13): construção da carteira recomendada a partir das análises
REAIS do Comitê de Investimentos (coordenador_analises, consumido via
provedor injetado - nunca rede/Supabase real em teste) e persistência
opcional (tabelas propostas em sql/carteira_recomendada.sql, ainda não
aplicadas - funções degradam para None/False sem lançar)."""
from datetime import datetime, timezone
from unittest.mock import patch

import data.carteira_recomendada as cr


def _linha(ticker, sinal="COMPRA", score=6, confianca="ALTA", preco_atual=100.0,
           preco_alvo_consenso=120.0, preco_alvo_modelo=None, preco_alvo_pl_setorial=None,
           contrarios=None, resumo="Tese resumida.", iniciado_em="2026-11-12T03:00:00+00:00",
           status="CONCLUIDA", analise_id="id-1"):
    return {
        "id": analise_id,
        "ticker": ticker,
        "status": status,
        "iniciado_em": iniciado_em,
        "resultado": {
            "resumo_executivo": resumo,
            "sinal_comite": {
                "sinal": sinal,
                "score": score,
                "confianca": confianca,
                "justificativa": f"Sinal {sinal} com score {score}.",
                "favoraveis": ["ROE forte"],
                "contrarios": contrarios or [],
                "preco_atual": preco_atual,
                "preco_atual_consultado_em": "2026-11-12T18:00:00+00:00",
                "preco_alvo_consenso": preco_alvo_consenso,
                "preco_alvo_modelo": preco_alvo_modelo,
                "metodo_preco_alvo_modelo": "DCF" if preco_alvo_modelo else None,
                "preco_alvo_pl_setorial": preco_alvo_pl_setorial,
            },
        },
    }


def _provedor(linhas):
    return lambda limite: linhas


# ---------------------------------------------------------------------
# _analises_concluidas_recentes / _extrair_sinal
# ---------------------------------------------------------------------

def test_analises_concluidas_recentes_ignora_nao_concluidas_e_deduplica_por_ticker():
    linhas = [
        _linha("PETR4", iniciado_em="2026-11-10T03:00:00+00:00", analise_id="antiga"),
        _linha("PETR4", iniciado_em="2026-11-12T03:00:00+00:00", analise_id="nova"),
        _linha("VALE3", status="EM_ANDAMENTO"),
        _linha("ITUB4", status="ERRO"),
    ]
    resultado = cr._analises_concluidas_recentes(500, _provedor(linhas))
    tickers = {r["ticker"] for r in resultado}
    assert tickers == {"PETR4"}
    assert [r for r in resultado if r["ticker"] == "PETR4"][0]["id"] == "nova"


def test_analises_concluidas_recentes_none_quando_supabase_indisponivel():
    assert cr._analises_concluidas_recentes(500, lambda limite: None) is None


def test_extrair_sinal_none_sem_sinal_comite():
    assert cr._extrair_sinal({"ticker": "PETR4", "resultado": {}}) is None
    assert cr._extrair_sinal({"ticker": "PETR4", "resultado": {"sinal_comite": {}}}) is None


def test_extrair_sinal_le_campos_do_sinal_comite():
    sinal = cr._extrair_sinal(_linha("PETR4", preco_alvo_pl_setorial=130.0))
    assert sinal["ticker"] == "PETR4"
    assert sinal["sinal"] == "COMPRA"
    assert sinal["preco_atual"] == 100.0
    assert sinal["preco_alvo_consenso"] == 120.0
    assert sinal["preco_alvo_pl_setorial"] == 130.0


# ---------------------------------------------------------------------
# cenários / critério de saída
# ---------------------------------------------------------------------

def test_cenarios_conservador_base_otimista_sem_inventar_numero():
    cenarios = cr._cenarios(preco_atual=100.0, preco_alvo=120.0, preco_alvo_pl_setorial=130.0)
    assert cenarios["base"]["preco"] == 120.0
    assert cenarios["base"]["retorno_pct"] == 20.0
    assert cenarios["conservador"]["preco"] == 110.0  # ponto médio 100->120
    assert cenarios["conservador"]["retorno_pct"] == 10.0
    assert cenarios["otimista"]["preco"] == 130.0  # P/L setorial mais otimista que o consenso
    assert "nunca é retorno garantido" in cenarios["aviso"]


def test_cenarios_otimista_cai_para_preco_alvo_quando_pl_setorial_nao_e_maior():
    cenarios = cr._cenarios(preco_atual=100.0, preco_alvo=120.0, preco_alvo_pl_setorial=105.0)
    assert cenarios["otimista"]["preco"] == 120.0


def test_cenarios_none_sem_preco_atual_ou_preco_alvo():
    assert cr._cenarios(None, 120.0, None) is None
    assert cr._cenarios(100.0, None, None) is None


def test_criterio_saida_destaca_confianca_baixa():
    saida_normal = cr._criterio_saida({"confianca": "ALTA"})
    saida_baixa = cr._criterio_saida({"confianca": "BAIXA"})
    assert "BAIXA" in saida_baixa and "prioritária" in saida_baixa
    assert "BAIXA" not in saida_normal


# ---------------------------------------------------------------------
# montar_carteira_recomendada - fluxo completo com providers injetados
# ---------------------------------------------------------------------

_AGORA = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)


def _setores_fake(mapa):
    def _classificar(ticker):
        return mapa.get(ticker)
    return _classificar


def test_carteira_filtra_so_compra_e_confianca_suficiente():
    linhas = [
        _linha("PETR4", sinal="COMPRA", confianca="ALTA", score=8),
        _linha("VALE3", sinal="VENDA", confianca="ALTA", score=-8),
        _linha("ITUB4", sinal="COMPRA", confianca="INSUFICIENTE", score=5),
        _linha("BBAS3", sinal="NEUTRO", confianca="MÉDIA", score=0),
    ]
    with patch("data.research.classificacao.classificar_setor", _setores_fake({"PETR4": "Petróleo"})):
        carteira = cr.montar_carteira_recomendada(
            agora=_AGORA, provedor_analises=_provedor(linhas),
            incluir_liquidez=False, incluir_macro=False,
        )
    tickers = [i["ticker"] for i in carteira["itens"]]
    assert tickers == ["PETR4"]
    assert carteira["universo_elegivel"] == 1
    assert carteira["universo_consultado"] == 4


def test_carteira_respeita_limite_por_setor():
    linhas = [_linha(t, sinal="COMPRA", confianca="ALTA", score=10 - i)
              for i, t in enumerate(["AAAA4", "BBBB4", "CCCC4", "DDDD4"])]
    setores = {"AAAA4": "Bancos", "BBBB4": "Bancos", "CCCC4": "Bancos", "DDDD4": "Varejo"}
    with patch("data.research.classificacao.classificar_setor", _setores_fake(setores)):
        carteira = cr.montar_carteira_recomendada(
            agora=_AGORA, provedor_analises=_provedor(linhas), maximo_por_setor=2,
            incluir_liquidez=False, incluir_macro=False,
        )
    tickers = [i["ticker"] for i in carteira["itens"]]
    # AAAA4/BBBB4 (Bancos, score mais alto) entram; CCCC4 (3o Banco) fica
    # de fora pelo teto de setor; DDDD4 (Varejo) entra.
    assert tickers == ["AAAA4", "BBBB4", "DDDD4"]
    assert carteira["resumo"]["diversificacao_setorial"]["Bancos"] <= carteira["resumo"]["concentracao_maxima_pct"] * 2 + 0.01


def test_carteira_respeita_peso_maximo_por_ativo():
    linhas = [_linha(t, sinal="COMPRA", confianca="ALTA", score=10) for t in ["A4", "B4"]]
    with patch("data.research.classificacao.classificar_setor", _setores_fake({})):
        carteira = cr.montar_carteira_recomendada(
            agora=_AGORA, provedor_analises=_provedor(linhas), peso_maximo_pct=30.0,
            incluir_liquidez=False, incluir_macro=False,
        )
    assert all(i["peso_pct"] == 30.0 for i in carteira["itens"])
    assert carteira["resumo"]["peso_total_pct"] == 60.0  # soma fica abaixo de 100% por causa do teto


def test_carteira_campos_pedidos_pela_missao_presentes_em_cada_item():
    linhas = [_linha("PETR4", sinal="COMPRA", confianca="ALTA", score=7)]
    with patch("data.research.classificacao.classificar_setor", _setores_fake({"PETR4": "Petróleo"})):
        carteira = cr.montar_carteira_recomendada(
            agora=_AGORA, provedor_analises=_provedor(linhas),
            incluir_liquidez=False, incluir_macro=False,
        )
    item = carteira["itens"][0]
    for campo in ("peso_pct", "justificativa", "preco_referencia", "preco_alvo", "tese",
                  "riscos", "criterio_saida", "data_revisao", "historico_alteracao"):
        assert campo in item
    assert item["data_revisao"] == "2026-12-13"
    assert item["historico_alteracao"] == []
    assert item["cenarios"]["aviso"]


def test_carteira_vazia_quando_nenhum_elegivel_nao_e_erro():
    linhas = [_linha("PETR4", sinal="VENDA")]
    carteira = cr.montar_carteira_recomendada(
        agora=_AGORA, provedor_analises=_provedor(linhas),
        incluir_liquidez=False, incluir_macro=False,
    )
    assert carteira["itens"] == []
    assert any("Nenhum ativo com sinal COMPRA" in a for a in carteira["avisos"])


def test_carteira_supabase_indisponivel_nunca_finge_sucesso():
    carteira = cr.montar_carteira_recomendada(
        agora=_AGORA, provedor_analises=lambda limite: None,
        incluir_liquidez=False, incluir_macro=False,
    )
    assert carteira["itens"] == []
    assert carteira["universo_consultado"] is None
    assert any("indisponível" in a for a in carteira["avisos"])


def test_liquidez_best_effort_nunca_derruba_a_carteira():
    linhas = [_linha("PETR4", sinal="COMPRA", confianca="ALTA")]

    def _cotacao_falha(ticker):
        raise ConnectionError("sem rede")

    with patch("data.research.classificacao.classificar_setor", _setores_fake({})):
        carteira = cr.montar_carteira_recomendada(
            agora=_AGORA, provedor_analises=_provedor(linhas),
            provedor_cotacao=_cotacao_falha, incluir_liquidez=True, incluir_macro=False,
        )
    assert carteira["itens"][0]["liquidez"] is None


def test_liquidez_usa_provedor_injetado():
    linhas = [_linha("PETR4", sinal="COMPRA", confianca="ALTA")]
    cotacao = {"volume": 42, "cotacao_em": "2026-11-13T13:00:00+00:00"}
    with patch("data.research.classificacao.classificar_setor", _setores_fake({})):
        carteira = cr.montar_carteira_recomendada(
            agora=_AGORA, provedor_analises=_provedor(linhas),
            provedor_cotacao=lambda ticker: cotacao, incluir_liquidez=True, incluir_macro=False,
        )
    assert carteira["itens"][0]["liquidez"]["volume"] == 42


def test_incluir_liquidez_false_nunca_chama_o_provedor_de_cotacao():
    linhas = [_linha("PETR4", sinal="COMPRA", confianca="ALTA")]

    def _nunca_deveria_ser_chamado(ticker):
        raise AssertionError("provedor_cotacao chamado com incluir_liquidez=False")

    with patch("data.research.classificacao.classificar_setor", _setores_fake({})):
        carteira = cr.montar_carteira_recomendada(
            agora=_AGORA, provedor_analises=_provedor(linhas),
            provedor_cotacao=_nunca_deveria_ser_chamado, incluir_liquidez=False, incluir_macro=False,
        )
    assert carteira["itens"][0]["liquidez"] is None


# ---------------------------------------------------------------------
# persistência (tabelas propostas, não aplicadas) - degrada sem lançar
# ---------------------------------------------------------------------

def test_persistencia_degrada_sem_lancar_quando_supabase_indisponivel():
    with patch("data.carteira_recomendada._cliente_ou_none", return_value=None):
        assert cr.salvar_carteira([{"ticker": "PETR4"}]) is False
        assert cr.obter_ultima_carteira_persistida() is None
        assert cr.registrar_revisao("PETR4", "peso_pct", 10, 12, "rebalanceamento") is False
        assert cr.listar_historico_alteracoes("PETR4") is None
        assert cr.registrar_acompanhamento("2026-11-13", [{"ticker": "PETR4"}]) is False
        assert cr.obter_acompanhamento("PETR4") is None


def test_salvar_carteira_upsert_por_ticker_nunca_delete_em_massa():
    chamadas = []

    class _TabelaFake:
        def upsert(self, payload, on_conflict=None):
            chamadas.append((payload, on_conflict))
            return self

        def execute(self):
            return None

    class _ClienteFake:
        def table(self, nome):
            assert nome == cr.TABELA_ITENS
            return _TabelaFake()

    with patch("data.carteira_recomendada._cliente_ou_none", return_value=_ClienteFake()):
        ok = cr.salvar_carteira([{"ticker": "PETR4", "peso_pct": 10.0}], agora=_AGORA)
    assert ok is True
    assert len(chamadas) == 1
    assert chamadas[0][1] == "ticker"  # upsert pelo próprio ticker, nunca delete-all antes
