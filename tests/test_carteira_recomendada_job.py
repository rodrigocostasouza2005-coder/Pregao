# -*- coding: utf-8 -*-
"""jobs/carteira_recomendada_job.py (missão 2026-11-14): fecha o ciclo de
persistência da Carteira Recomendada 1x/dia - monta, compara com o
snapshot anterior, persiste, grava só as revisões REAIS no histórico e
grava o acompanhamento do dia.

As 3 tabelas (sql/carteira_recomendada.sql) foram aplicadas em produção
em 2026-11-14 com aprovação explícita, mas os testes abaixo nunca tocam
rede/Supabase real - usam providers/fakes injetados, mesmo padrão do
resto do projeto (ver tests/test_carteira_recomendada.py e
tests/test_comite_noturno.py)."""
from datetime import date, datetime, timezone
from unittest.mock import patch

import jobs.carteira_recomendada_job as job

_AGORA = datetime(2026, 11, 14, 22, 45, tzinfo=timezone.utc)


def _item(ticker, peso_pct=10.0, tese="Tese original.", preco_alvo=120.0,
          criterio_saida="Reavaliar se o sinal cair.", preco_referencia=100.0,
          sinal_comite=None, confianca_comite=None, score_comite=None, riscos=None):
    return {
        "ticker": ticker,
        "peso_pct": peso_pct,
        "tese": tese,
        "preco_alvo": preco_alvo,
        "criterio_saida": criterio_saida,
        "preco_referencia": preco_referencia,
        "sinal_comite": sinal_comite,
        "confianca_comite": confianca_comite,
        "score_comite": score_comite,
        "riscos": riscos,
    }


# ---------------------------------------------------------------------
# calcular_revisoes - a parte mais delicada: só os campos que mudaram.
# ---------------------------------------------------------------------

def test_calcular_revisoes_nao_gera_nenhuma_linha_quando_nada_mudou():
    anterior = [_item("PETR4"), _item("VALE3", peso_pct=15.0, preco_alvo=90.0)]
    novo = [_item("PETR4"), _item("VALE3", peso_pct=15.0, preco_alvo=90.0)]
    assert job.calcular_revisoes(anterior, novo) == []


def test_calcular_revisoes_tolera_ruido_de_ponto_flutuante_sem_registrar_mudanca():
    anterior = [_item("PETR4", peso_pct=10.0, preco_alvo=120.0)]
    novo = [_item("PETR4", peso_pct=10.0 + 1e-9, preco_alvo=120.0 - 1e-9)]
    assert job.calcular_revisoes(anterior, novo) == []


def test_calcular_revisoes_detecta_mudanca_de_peso_pct():
    anterior = [_item("PETR4", peso_pct=10.0)]
    novo = [_item("PETR4", peso_pct=12.5)]
    revisoes = job.calcular_revisoes(anterior, novo)
    assert len(revisoes) == 1
    assert revisoes[0]["ticker"] == "PETR4"
    assert revisoes[0]["campo"] == "peso_pct"
    assert revisoes[0]["valor_anterior"] == 10.0
    assert revisoes[0]["valor_novo"] == 12.5


def test_calcular_revisoes_detecta_mudanca_de_tese_preco_alvo_e_criterio_saida_independentemente():
    anterior = [_item("PETR4", tese="Tese A", preco_alvo=120.0, criterio_saida="Sair se cair.")]
    novo = [_item("PETR4", tese="Tese B", preco_alvo=130.0, criterio_saida="Sair se cair.")]
    revisoes = job.calcular_revisoes(anterior, novo)
    campos = {r["campo"] for r in revisoes}
    assert campos == {"tese", "preco_alvo"}  # criterio_saida não mudou - não aparece
    assert len(revisoes) == 2


def test_calcular_revisoes_nao_monitora_sinal_confianca_score_do_comite():
    """ACHADO REAL (2026-11-23, confirmado contra produção): carteira_
    recomendada_itens NUNCA teve as colunas sinal_comite/confianca_comite/
    score_comite (schema real só tem ticker/setor/peso_pct/justificativa/
    preco_referencia/preco_alvo/tese/riscos/criterio_saida/data_revisao/
    origem_analise_id/atualizado_em). `anterior` vem dessa tabela (sempre
    sem esses 3 campos) e `novo` vem da montagem em memória (sempre COM
    eles) - se fossem monitorados aqui, TODO ticker geraria 'mudou de
    None para COMPRA/ALTA/6' em TODA rodada, pra sempre (falso positivo
    permanente). Por isso NÃO estão em _CAMPOS_MONITORADOS - exigiria
    antes uma migration aditiva (documentada, não aplicada) + atualizar
    salvar_carteira() pra persisti-los. Este teste prova que a ausência
    desses campos no item anterior nunca gera revisão nenhuma (mesmo
    quando o item novo os tem, como qualquer saída real de
    montar_carteira_recomendada)."""
    anterior = [_item("PETR4")]  # sem sinal_comite/confianca_comite/score_comite - igual à tabela real
    novo = [_item("PETR4", sinal_comite="VENDA", confianca_comite="BAIXA", score_comite=-5)]
    assert job.calcular_revisoes(anterior, novo) == []


def test_calcular_revisoes_entrada_na_carteira_registra_sinal_confianca_score_so_como_fato_historico():
    """O que sobrevive da tentativa original: capturado 1x, só no evento
    append-only de entrada (JSONB, sem depender de coluna nova) - nunca
    comparado dia a dia (essa comparação é a que exigiria a migration)."""
    anterior = [_item("PETR4")]
    novo = [_item("PETR4"), _item("WEGE3", sinal_comite="COMPRA", confianca_comite="ALTA", score_comite=6)]
    revisoes = job.calcular_revisoes(anterior, novo)
    entrada = next(r for r in revisoes if r["ticker"] == "WEGE3")
    assert entrada["valor_novo"]["sinal_comite"] == "COMPRA"
    assert entrada["valor_novo"]["confianca_comite"] == "ALTA"
    assert entrada["valor_novo"]["score_comite"] == 6


def test_calcular_revisoes_riscos_reordenados_nao_conta_como_mudanca():
    anterior = [_item("PETR4", riscos=["Câmbio", "Regulação"])]
    novo = [_item("PETR4", riscos=["Regulação", "Câmbio"])]
    assert job.calcular_revisoes(anterior, novo) == []


def test_calcular_revisoes_detecta_mudanca_real_de_riscos():
    anterior = [_item("PETR4", riscos=["Câmbio"])]
    novo = [_item("PETR4", riscos=["Câmbio", "Novo risco regulatório"])]
    revisoes = job.calcular_revisoes(anterior, novo)
    assert len(revisoes) == 1 and revisoes[0]["campo"] == "riscos"


def test_calcular_revisoes_marca_entrada_na_carteira_para_ticker_novo():
    anterior = [_item("PETR4")]
    novo = [_item("PETR4"), _item("WEGE3")]
    revisoes = job.calcular_revisoes(anterior, novo)
    assert len(revisoes) == 1
    assert revisoes[0] == {
        "ticker": "WEGE3", "campo": "entrada_na_carteira", "valor_anterior": None,
        "valor_novo": {
            "peso_pct": 10.0, "tese": "Tese original.", "preco_referencia": 100.0,
            "preco_alvo": 120.0, "sinal_comite": None, "confianca_comite": None,
            "score_comite": None,
        },
        "motivo": job._MOTIVO_ENTRADA,
    }


def test_calcular_revisoes_marca_saida_da_carteira_para_ticker_removido():
    anterior = [_item("PETR4"), _item("ITUB4", peso_pct=20.0)]
    novo = [_item("PETR4")]
    revisoes = job.calcular_revisoes(anterior, novo)
    assert len(revisoes) == 1
    assert revisoes[0]["ticker"] == "ITUB4"
    assert revisoes[0]["campo"] == "saida_da_carteira"
    assert revisoes[0]["valor_novo"] is None
    assert revisoes[0]["valor_anterior"] == {"peso_pct": 20.0}


def test_calcular_revisoes_none_quando_sem_baseline_anterior_nunca_assume_tudo_mudou():
    novo = [_item("PETR4"), _item("WEGE3")]
    assert job.calcular_revisoes(None, novo) == []


def test_calcular_revisoes_primeira_rodada_persistida_trata_cada_ticker_como_entrada():
    novo = [_item("PETR4"), _item("WEGE3")]
    revisoes = job.calcular_revisoes([], novo)
    assert {r["ticker"] for r in revisoes} == {"PETR4", "WEGE3"}
    assert all(r["campo"] == "entrada_na_carteira" for r in revisoes)


# ---------------------------------------------------------------------
# _itens_com_preco_atual - comparação preço de referência x preço de hoje
# ---------------------------------------------------------------------

def test_itens_com_preco_atual_calcula_retorno_pct():
    itens = [_item("PETR4", preco_referencia=100.0)]
    resultado = job._itens_com_preco_atual(itens, lambda ticker: {"preco": 110.0})
    assert resultado == [{
        "ticker": "PETR4", "peso_pct": 10.0, "preco_referencia": 100.0,
        "preco_atual": 110.0, "retorno_pct": 10.0,
    }]


def test_itens_com_preco_atual_cotacao_falha_entra_com_none_sem_derrubar_os_demais():
    itens = [_item("PETR4", preco_referencia=100.0), _item("VALE3", preco_referencia=60.0)]

    def _cotacao(ticker):
        if ticker == "PETR4":
            raise ConnectionError("sem rede")
        return {"preco": 66.0}

    resultado = job._itens_com_preco_atual(itens, _cotacao)
    petr4, vale3 = resultado
    assert petr4["preco_atual"] is None and petr4["retorno_pct"] is None
    assert vale3["preco_atual"] == 66.0 and vale3["retorno_pct"] == 10.0


# ---------------------------------------------------------------------
# executar() - fluxo completo, degrade seguro, nunca inventa dado.
# ---------------------------------------------------------------------

def _carteira(itens):
    return {"itens": itens, "resumo": {"n_ativos": len(itens)}, "avisos": []}


def test_executar_carteira_vazia_nao_persiste_nada():
    with patch.object(job, "montar_carteira_recomendada", return_value=_carteira([])) as montar, \
         patch.object(job, "obter_ultima_carteira_persistida") as obter_anterior, \
         patch.object(job, "salvar_carteira") as salvar, \
         patch.object(job, "registrar_revisao") as revisao, \
         patch.object(job, "registrar_acompanhamento") as acompanhamento:
        assert job.executar(agora=_AGORA) is False
    montar.assert_called_once()
    obter_anterior.assert_not_called()
    salvar.assert_not_called()
    revisao.assert_not_called()
    acompanhamento.assert_not_called()


def test_executar_salvar_carteira_falha_nao_grava_historico_nem_acompanhamento():
    novo = [_item("PETR4")]
    with patch.object(job, "montar_carteira_recomendada", return_value=_carteira(novo)), \
         patch.object(job, "obter_ultima_carteira_persistida", return_value=[]), \
         patch.object(job, "salvar_carteira", return_value=False), \
         patch.object(job, "registrar_revisao") as revisao, \
         patch.object(job, "registrar_acompanhamento") as acompanhamento:
        assert job.executar(agora=_AGORA) is False
    revisao.assert_not_called()
    acompanhamento.assert_not_called()


def test_executar_fluxo_completo_registra_so_o_que_mudou_e_grava_acompanhamento():
    anterior = [_item("PETR4", peso_pct=10.0), _item("ITUB4", peso_pct=20.0)]
    novo = [_item("PETR4", peso_pct=15.0), _item("WEGE3", peso_pct=5.0)]  # PETR4 mudou peso, ITUB4 saiu, WEGE3 entrou

    with patch.object(job, "montar_carteira_recomendada", return_value=_carteira(novo)), \
         patch.object(job, "obter_ultima_carteira_persistida", return_value=anterior), \
         patch.object(job, "salvar_carteira", return_value=True) as salvar, \
         patch.object(job, "registrar_revisao", return_value=True) as revisao, \
         patch.object(job, "registrar_acompanhamento", return_value=True) as acompanhamento, \
         patch.object(job, "obter_cotacao", return_value={"preco": 110.0}):
        assert job.executar(agora=_AGORA) is True

    salvar.assert_called_once_with(novo, agora=_AGORA)
    tickers_revisados = {chamada.args[0] for chamada in revisao.call_args_list}
    assert tickers_revisados == {"PETR4", "ITUB4", "WEGE3"}
    campos_revisados = {chamada.args[1] for chamada in revisao.call_args_list}
    assert campos_revisados == {"peso_pct", "saida_da_carteira", "entrada_na_carteira"}

    acompanhamento.assert_called_once()
    data_chamada, itens_chamada = acompanhamento.call_args.args
    assert data_chamada == _AGORA.date()
    assert {i["ticker"] for i in itens_chamada} == {"PETR4", "WEGE3"}


def test_executar_sem_mudanca_real_nao_gera_nenhuma_linha_de_historico():
    item = _item("PETR4")
    with patch.object(job, "montar_carteira_recomendada", return_value=_carteira([item])), \
         patch.object(job, "obter_ultima_carteira_persistida", return_value=[item]), \
         patch.object(job, "salvar_carteira", return_value=True), \
         patch.object(job, "registrar_revisao") as revisao, \
         patch.object(job, "registrar_acompanhamento", return_value=True), \
         patch.object(job, "obter_cotacao", return_value={"preco": 101.0}):
        assert job.executar(agora=_AGORA) is True
    revisao.assert_not_called()


def test_executar_registrar_acompanhamento_falha_retorna_false():
    item = _item("PETR4")
    with patch.object(job, "montar_carteira_recomendada", return_value=_carteira([item])), \
         patch.object(job, "obter_ultima_carteira_persistida", return_value=[item]), \
         patch.object(job, "salvar_carteira", return_value=True), \
         patch.object(job, "registrar_revisao"), \
         patch.object(job, "registrar_acompanhamento", return_value=False), \
         patch.object(job, "obter_cotacao", return_value={"preco": 101.0}):
        assert job.executar(agora=_AGORA) is False


def test_executar_nunca_lanca_mesmo_com_falha_inesperada():
    with patch.object(job, "montar_carteira_recomendada", side_effect=RuntimeError("boom")):
        assert job.executar(agora=_AGORA) is False


# ---------------------------------------------------------------------
# idempotência do acompanhamento no mesmo dia - usa um cliente Supabase
# FAKE em memória (não um mock de 1 chamada isolada), mesmo padrão de
# tests/test_carteira_recomendada.py, pra provar o upsert por
# (ticker, data_referencia) de ponta a ponta através do job.
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


def test_executar_duas_vezes_no_mesmo_dia_nao_duplica_linha_de_acompanhamento():
    cliente = _ClienteMemoria()
    item = _item("PETR4", preco_referencia=100.0)

    with patch("data.carteira_recomendada._cliente_ou_none", return_value=cliente), \
         patch.object(job, "montar_carteira_recomendada", return_value=_carteira([item])), \
         patch.object(job, "obter_cotacao", return_value={"preco": 108.0}):
        assert job.executar(agora=_AGORA) is True
        # Reexecução no mesmo dia (retry de job, chamada manual 2x) - preço
        # real mudou um pouco entre as duas chamadas, mas ainda é o mesmo dia.
        with patch.object(job, "obter_cotacao", return_value={"preco": 109.0}):
            assert job.executar(agora=_AGORA) is True

    acompanhamento = cliente.table("carteira_recomendada_acompanhamento")
    linhas = acompanhamento.execute().data
    assert len(linhas) == 1  # idempotente: 1 linha só pro par (ticker, data_referencia)
    assert linhas[0]["preco_atual"] == 109.0  # a 2a execução sobrescreveu a checagem do dia

    itens_persistidos = cliente.table("carteira_recomendada_itens").execute().data
    assert len(itens_persistidos) == 1  # snapshot vigente também não duplicou
