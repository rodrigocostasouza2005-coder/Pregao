# -*- coding: utf-8 -*-
"""data/carteira_recomendada.py (módulo novo, missão "Frente 4"
2026-11-12/13): construção da carteira recomendada a partir das análises
REAIS do Comitê de Investimentos (coordenador_analises, consumido via
provedor injetado - nunca rede/Supabase real em teste) e persistência
opcional (tabelas propostas em sql/carteira_recomendada.sql, ainda não
aplicadas - funções degradam para None/False sem lançar).

Testes abaixo acrescentados na validação de ponta a ponta da PR #304
(2026-11-13, worktree feat/validacao-carteira-recomendada-20261113):
confirmado contra o Supabase REAL de produção que a migration de
sql/carteira_recomendada.sql nunca foi aplicada (PGRST205 nas 3 tabelas) -
por isso os testes de persistência/histórico/acompanhamento abaixo usam
um cliente Supabase fake EM MEMÓRIA (não um mock de chamada isolada) pra
provar o comportamento de imutabilidade por data que só poderá ser
confirmado contra produção depois da migration ser aplicada (ver SQL
revisado em anexo ao relatório da missão - NÃO aplicado)."""
from datetime import datetime, timedelta, timezone
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


def test_registrar_acompanhamento_usa_upsert_por_ticker_e_data_nunca_insert_simples():
    chamadas = []

    class _TabelaFake:
        def upsert(self, payload, on_conflict=None):
            chamadas.append((payload, on_conflict))
            return self

        def execute(self):
            return None

    class _ClienteFake:
        def table(self, nome):
            assert nome == cr.TABELA_ACOMPANHAMENTO
            return _TabelaFake()

    with patch("data.carteira_recomendada._cliente_ou_none", return_value=_ClienteFake()):
        ok = cr.registrar_acompanhamento("2026-11-13", [{"ticker": "PETR4", "peso_pct": 10.0,
                                                           "preco_referencia": 100.0,
                                                           "preco_atual": 110.0, "retorno_pct": 10.0}])
    assert ok is True
    assert len(chamadas) == 1
    # idempotente: reexecução no mesmo dia sobrescreve a checagem em vez de
    # lançar erro de unicidade (chave composta, nunca só o ticker).
    assert chamadas[0][1] == "ticker,data_referencia"


# ---------------------------------------------------------------------
# comparar_carteira_persistida_com_atual - fecha o ciclo: snapshot
# persistido (recomendação de X dias atrás) x preço ATUAL, com
# persistência automática em carteira_recomendada_acompanhamento.
# ---------------------------------------------------------------------

def test_comparar_none_quando_tabela_de_itens_ausente_ou_supabase_indisponivel():
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=None):
        assert cr.comparar_carteira_persistida_com_atual() is None


def test_comparar_lista_vazia_quando_nunca_houve_snapshot_salvo():
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=[]):
        assert cr.comparar_carteira_persistida_com_atual() == []


def test_comparar_calcula_retorno_pct_a_partir_do_snapshot_e_da_cotacao_atual():
    snapshot = [{"ticker": "PETR4", "peso_pct": 10.0, "preco_referencia": 100.0}]
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=snapshot), \
         patch("data.carteira_recomendada.registrar_acompanhamento", return_value=True) as mock_registrar:
        resultado = cr.comparar_carteira_persistida_com_atual(
            data_referencia="2026-11-20",
            provedor_cotacao=lambda ticker: {"preco": 115.0},
        )
    assert resultado == [{
        "ticker": "PETR4", "peso_pct": 10.0, "preco_referencia": 100.0,
        "preco_atual": 115.0, "retorno_pct": 15.0, "data_referencia": "2026-11-20",
    }]
    mock_registrar.assert_called_once_with("2026-11-20", resultado)


def test_comparar_cotacao_indisponivel_entra_com_none_sem_derrubar_os_demais():
    snapshot = [
        {"ticker": "PETR4", "peso_pct": 10.0, "preco_referencia": 100.0},
        {"ticker": "VALE3", "peso_pct": 10.0, "preco_referencia": 60.0},
    ]

    def _cotacao(ticker):
        if ticker == "PETR4":
            raise ConnectionError("sem rede")
        return {"preco": 66.0}

    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=snapshot), \
         patch("data.carteira_recomendada.registrar_acompanhamento", return_value=True):
        resultado = cr.comparar_carteira_persistida_com_atual(
            data_referencia="2026-11-20", provedor_cotacao=_cotacao,
        )
    petr4, vale3 = resultado
    assert petr4["preco_atual"] is None and petr4["retorno_pct"] is None
    assert vale3["preco_atual"] == 66.0 and vale3["retorno_pct"] == 10.0


def test_comparar_persistir_false_nunca_chama_registrar_acompanhamento():
    snapshot = [{"ticker": "PETR4", "peso_pct": 10.0, "preco_referencia": 100.0}]
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=snapshot), \
         patch("data.carteira_recomendada.registrar_acompanhamento") as mock_registrar:
        cr.comparar_carteira_persistida_com_atual(
            data_referencia="2026-11-20", provedor_cotacao=lambda t: {"preco": 110.0},
            persistir=False,
        )
    mock_registrar.assert_not_called()


def test_comparar_integra_fim_a_fim_com_tabela_de_acompanhamento_fake():
    """Fluxo completo: snapshot persistido + cotação atual -> comparação
    calculada -> gravada em carteira_recomendada_acompanhamento via upsert
    (ticker, data_referencia) - exatamente o ciclo "persistir histórico,
    acompanhar recomendações e comparar resultados" pedido pela missão,
    validado com mock de tabela (migration ainda não aplicada)."""
    gravados = []

    class _TabelaItens:
        def select(self, _):
            return self

        def order(self, *a, **k):
            return self

        def execute(self):
            class _Resp:
                data = [{"ticker": "PETR4", "peso_pct": 10.0, "preco_referencia": 100.0}]
            return _Resp()

    class _TabelaAcompanhamento:
        def upsert(self, payload, on_conflict=None):
            gravados.append((payload, on_conflict))
            return self

        def execute(self):
            return None

    class _ClienteFake:
        def table(self, nome):
            if nome == cr.TABELA_ITENS:
                return _TabelaItens()
            if nome == cr.TABELA_ACOMPANHAMENTO:
                return _TabelaAcompanhamento()
            raise AssertionError(f"tabela inesperada: {nome}")

    with patch("data.carteira_recomendada._cliente_ou_none", return_value=_ClienteFake()):
        resultado = cr.comparar_carteira_persistida_com_atual(
            data_referencia="2026-11-20", provedor_cotacao=lambda t: {"preco": 120.0},
        )
    assert resultado[0]["retorno_pct"] == 20.0
    assert len(gravados) == 1
    assert gravados[0][0][0]["ticker"] == "PETR4"
    assert gravados[0][0][0]["retorno_pct"] == 20.0
    assert gravados[0][1] == "ticker,data_referencia"


# ---------------------------------------------------------------------
# Validação ponta-a-ponta da missão (2026-11-13) - imutabilidade de
# snapshot, exclusão de ativo sem dado confiável e cenario_macro real.
#
# Cliente Supabase FAKE EM MEMÓRIA (não um mock de 1 chamada isolada):
# simula o upsert/insert/select/eq/order real do Postgres o suficiente
# pra provar que uma chave já existente é SUBSTITUÍDA (upsert) e uma
# chave nova nunca apaga as demais - mesma semântica das tabelas
# propostas em sql/carteira_recomendada.sql. Necessário porque, nesta
# validação, confirmamos contra o Supabase REAL de produção que essas 3
# tabelas NUNCA foram criadas (PGRST205: "Could not find the table") -
# a migration ficou só proposta (ver sql/carteira_recomendada.sql e o
# relatório da missão). Enquanto ela não for aplicada E APROVADA pelo
# Rodrigo, este é o único jeito de testar a imutabilidade do histórico
# com algo que se comporta como o Postgres real.
# ---------------------------------------------------------------------

class _TabelaMemoria:
    def __init__(self, chave):
        self._chave = tuple(chave)
        self._linhas = {}
        self._seq = 0

    def _chave_de(self, linha):
        return tuple(linha.get(c) for c in self._chave)

    def upsert(self, payload, on_conflict=None):
        linhas = payload if isinstance(payload, list) else [payload]
        for linha in linhas:
            self._linhas[self._chave_de(linha)] = dict(linha)
        return self

    def insert(self, payload):
        linhas = payload if isinstance(payload, list) else [payload]
        for linha in linhas:
            self._seq += 1
            self._linhas[("__historico__", self._seq)] = dict(linha)
        return self

    def select(self, *_a, **_k):
        self._consulta = list(self._linhas.values())
        return self

    def eq(self, campo, valor):
        self._consulta = [l for l in self._consulta if l.get(campo) == valor]
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self._consulta = self._consulta[:n]
        return self

    def execute(self):
        class _Resp:
            pass
        resp = _Resp()
        resp.data = list(getattr(self, "_consulta", list(self._linhas.values())))
        return resp


class _ClienteMemoria:
    _CHAVES = {
        "carteira_recomendada_itens": ("ticker",),
        "carteira_recomendada_acompanhamento": ("ticker", "data_referencia"),
    }

    def __init__(self):
        self._tabelas = {}

    def table(self, nome):
        if nome not in self._tabelas:
            self._tabelas[nome] = _TabelaMemoria(self._CHAVES.get(nome, ("id",)))
        return self._tabelas[nome]


def test_snapshot_vigente_e_sobrescrito_a_cada_rodada_nunca_preserva_valor_antigo():
    """carteira_recomendada_itens é documentado como o snapshot VIGENTE
    (1 linha por ticker, upsert por ticker) - NUNCA um histórico por
    data. Prova concreta pedida na missão: gera 1 snapshot (peso 10%),
    simula uma rodada posterior com peso diferente (15%) pro MESMO
    ticker, e confirma que o valor antigo não existe mais em nenhum
    lugar acessível por obter_ultima_carteira_persistida - achado real:
    quem precisar do estado da carteira EM CADA DATA (não só o vigente)
    depende de registrar_revisao, que hoje não é chamado por nenhum
    caller automático (ver relatório da missão)."""
    cliente = _ClienteMemoria()
    with patch("data.carteira_recomendada._cliente_ou_none", return_value=cliente):
        ok1 = cr.salvar_carteira(
            [{"ticker": "PETR4", "peso_pct": 10.0, "preco_referencia": 40.0}], agora=_AGORA)
        snapshot_rodada_1 = cr.obter_ultima_carteira_persistida()

        ok2 = cr.salvar_carteira(
            [{"ticker": "PETR4", "peso_pct": 15.0, "preco_referencia": 45.0}],
            agora=_AGORA + timedelta(days=1))
        snapshot_rodada_2 = cr.obter_ultima_carteira_persistida()

    assert ok1 is True and ok2 is True
    assert snapshot_rodada_1[0]["peso_pct"] == 10.0
    assert len(snapshot_rodada_2) == 1
    assert snapshot_rodada_2[0]["peso_pct"] == 15.0
    pesos_restantes = [l["peso_pct"] for l in snapshot_rodada_2]
    assert 10.0 not in pesos_restantes  # o valor da rodada 1 foi sobrescrito, não preservado


def test_acompanhamento_preserva_checagens_de_datas_diferentes_sem_sobrescrever():
    """carteira_recomendada_acompanhamento É o histórico imutável por
    data (chave única ticker+data_referencia) - ao contrário de
    carteira_recomendada_itens (teste acima). Gera a checagem do dia 13,
    depois simula uma atualização de preço numa data POSTERIOR (dia 20)
    e confirma que a linha do dia 13 permanece intacta - snapshot antigo
    não foi sobrescrito."""
    cliente = _ClienteMemoria()
    snapshot = [{"ticker": "PETR4", "peso_pct": 10.0, "preco_referencia": 40.0}]
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=snapshot), \
         patch("data.carteira_recomendada._cliente_ou_none", return_value=cliente):
        cr.comparar_carteira_persistida_com_atual(
            data_referencia="2026-11-13", provedor_cotacao=lambda t: {"preco": 44.0})
        cr.comparar_carteira_persistida_com_atual(
            data_referencia="2026-11-20", provedor_cotacao=lambda t: {"preco": 50.0})

        historico = cr.obter_acompanhamento("PETR4")

    por_data = {l["data_referencia"]: l for l in historico}
    assert len(por_data) == 2
    assert por_data["2026-11-13"]["preco_atual"] == 44.0  # checagem antiga intacta
    assert por_data["2026-11-20"]["preco_atual"] == 50.0  # checagem nova, linha separada


def test_acompanhamento_mesma_data_e_idempotente_por_design_sobrescreve_so_a_propria_checagem():
    """Contraste deliberado com o teste acima: reexecução na MESMA data
    (retry de job, chamada manual 2x no mesmo dia) sobrescreve só a
    checagem daquele dia - por design (docstring de
    registrar_acompanhamento), não um bug. Datas diferentes continuam
    imutáveis entre si (teste anterior)."""
    cliente = _ClienteMemoria()
    snapshot = [{"ticker": "PETR4", "peso_pct": 10.0, "preco_referencia": 40.0}]
    with patch("data.carteira_recomendada.obter_ultima_carteira_persistida", return_value=snapshot), \
         patch("data.carteira_recomendada._cliente_ou_none", return_value=cliente):
        cr.comparar_carteira_persistida_com_atual(
            data_referencia="2026-11-13", provedor_cotacao=lambda t: {"preco": 44.0})
        cr.comparar_carteira_persistida_com_atual(
            data_referencia="2026-11-13", provedor_cotacao=lambda t: {"preco": 46.0})

        historico = cr.obter_acompanhamento("PETR4")

    assert len(historico) == 1
    assert historico[0]["preco_atual"] == 46.0  # retry no mesmo dia substitui a checagem do dia


def test_ticker_sem_cobertura_confiavel_insuficiente_nunca_entra_na_carteira():
    """Ativo de baixa liquidez/sem cobertura - análise CONCLUIDA mas o
    Comitê marcou confiança INSUFICIENTE (dado insuficiente pra confiar
    no sinal) - nunca entra na carteira, mesmo com sinal COMPRA e score
    alto. Achado real (consultado nesta validação contra produção,
    2026-11-13): das 53 análises CONCLUIDA vigentes no Supabase real
    hoje, nenhuma tem confiança BAIXA/MEDIA/INSUFICIENTE (todas vieram
    ALTA) - não há exemplo real disponível agora pra validar fim-a-fim
    contra produção; este teste cobre a regra com dado injetado, mesmo
    padrão de testabilidade que o resto do módulo já usa."""
    linhas = [
        _linha("ILIQ4", sinal="COMPRA", confianca="INSUFICIENTE", score=9,
               contrarios=["Baixíssima liquidez - poucos negócios na sessão.",
                           "Cobertura de research insuficiente pra validar o sinal."]),
        _linha("PETR4", sinal="COMPRA", confianca="ALTA", score=7),
    ]
    with patch("data.research.classificacao.classificar_setor", _setores_fake({})):
        carteira = cr.montar_carteira_recomendada(
            agora=_AGORA, provedor_analises=_provedor(linhas),
            incluir_liquidez=False, incluir_macro=False,
        )
    tickers = [i["ticker"] for i in carteira["itens"]]
    assert "ILIQ4" not in tickers
    assert tickers == ["PETR4"]
    assert carteira["universo_consultado"] == 2
    assert carteira["universo_elegivel"] == 1


def test_liquidez_baixa_e_apenas_informativa_nao_exclui_nem_avisa_gap_documentado():
    """Achado da validação (comportamento REAL do código, não suposição):
    liquidez hoje é só informativa (volume mais recente na ficha do
    ativo) - não existe piso de liquidez que exclua ou gere aviso
    específico pra um ativo pouco negociado, mesmo quando o volume é
    baixíssimo. Isto já é um GAP DOCUMENTADO no próprio código
    (_CRITERIOS_EXPLICITOS["liquidez"]: "nunca usado pra excluir um
    ativo nesta primeira versão, sem piso de liquidez definido pelo
    Rodrigo ainda") - este teste apenas confirma que o comportamento
    documentado é o comportamento real, pra não regredir silenciosamente
    se algum dia um piso for adicionado sem atualizar este teste."""
    linhas = [_linha("BAIXALIQ4", sinal="COMPRA", confianca="ALTA", score=7)]
    with patch("data.research.classificacao.classificar_setor", _setores_fake({})):
        carteira = cr.montar_carteira_recomendada(
            agora=_AGORA, provedor_analises=_provedor(linhas),
            provedor_cotacao=lambda t: {"volume": 1, "cotacao_em": "2026-11-13T13:00:00+00:00"},
            incluir_liquidez=True, incluir_macro=False,
        )
    item = carteira["itens"][0]
    assert item["ticker"] == "BAIXALIQ4"  # não foi excluído por volume baixo
    assert item["liquidez"]["volume"] == 1
    assert not any("liquidez" in (a or "").lower() for a in carteira["avisos"])


# ---------------------------------------------------------------------
# cenario_macro - regressão do bug encontrado nesta validação (2026-11-13):
# _contexto_macro() guardava o DataFrame CRU (até ~400 linhas de
# histórico) retornado por obter_selic_meta/obter_cdi/obter_focus_ipca
# em vez do valor mais recente - tornava `resumo` não serializável em
# JSON e inútil como "contexto da rodada". Corrigido reaproveitando
# data/morning_call_editorial.py:_macro_rows (mesma extração que o
# Morning Call já usa).
# ---------------------------------------------------------------------

def test_contexto_macro_usa_macro_rows_e_nunca_guarda_dataframe_cru():
    linha_fake = {"indicador": "Selic meta", "valor": 13.75, "unidade": "% a.a.",
                  "referencia": "13/11/2026", "detalhe": None, "erro": None}
    with patch("data.morning_call_editorial._macro_rows", return_value=[linha_fake]):
        contexto = cr._contexto_macro()
    assert contexto == {"Selic meta": {"valor": 13.75, "unidade": "% a.a.",
                                        "referencia": "13/11/2026", "detalhe": None, "erro": None}}
    import json
    json.dumps(contexto)  # nunca lança - nenhum DataFrame/objeto não serializável


def test_contexto_macro_indisponivel_nunca_derruba_a_carteira():
    with patch("data.morning_call_editorial._macro_rows", side_effect=RuntimeError("SGS indisponível")):
        contexto = cr._contexto_macro()
    assert contexto == {}
    linhas = [_linha("PETR4", sinal="COMPRA", confianca="ALTA")]
    with patch("data.research.classificacao.classificar_setor", _setores_fake({})), \
         patch("data.morning_call_editorial._macro_rows", side_effect=RuntimeError("SGS indisponível")):
        carteira = cr.montar_carteira_recomendada(
            agora=_AGORA, provedor_analises=_provedor(linhas), incluir_liquidez=False, incluir_macro=True,
        )
    assert carteira["itens"]  # carteira montada normalmente mesmo com macro indisponível
    assert carteira["resumo"]["cenario_macro"] == {}
