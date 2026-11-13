# -*- coding: utf-8 -*-
"""Teste de integração PONTA A PONTA do fluxo real do Comitê de
Investimentos (auditoria noturna 2026-11-12, Agente B): prova que a
CADEIA inteira roda de verdade sobre uma chamada real a
data.coordenador_central.fluxos.analisar_ticker - não só peças isoladas
mockadas (os testes unitários de cada módulo já cobrem isso: ver
test_coordenador_central_fluxos.py, test_coordenador_central_consolidacao.py,
test_coordenador_modelagem.py, test_coordenador_dcf.py).

O QUE RODA DE VERDADE (zero mock) nesta chamada:
  - data.coordenador_central.executor (ThreadPoolExecutor real, timeout real)
  - data.coordenador_central.registro (REGISTRO real, todos os 8
    especialistas acionados por analisar_ticker)
  - data.coordenador_central.fluxos.analisar_ticker (orquestração real,
    inclusive _anexar_premissas_dcf escolhendo dívida líquida da CVM)
  - data.coordenador_central.modelagem.modelar_empresa/revisar_valuation
    (Model Builder + Valuation Reviewer) e data.coordenador_central.dcf
    (cálculo DCF de 3 cenários + sensibilidade) - nenhuma destas é
    mockada: são funções puras, sem rede/IA, então correm 100% reais
    aqui, com premissas explícitas (equivalente ao analista marcar
    "Calcular DCF" na UI) - diferente do caminho automático do comitê
    noturno (jobs/comite_noturno.py), que nunca fornece premissas e por
    isso sempre pula estes dois especialistas (ver
    test_analisar_ticker_pula_model_builder_e_reviewer_sem_premissas_dcf).
  - data.coordenador_central.consolidacao.consolidar +
    data.coordenador_central.pareceres.montar_pareceres/montar_sinal_comite
    (toda a síntese/cross-check/confiança)
  - data.coordenador_central.persistencia (grava e lê de volta através
    de um cliente Supabase FALSO em memória, abaixo - prova que o
    resultado final é CONSULTÁVEL, não só devolvido em memória)

O QUE É MOCKADO (fronteira de rede/IA real, mesmo padrão já usado em
tests/test_market_researcher.py:_patches_analise_ticker e
tests/test_comite_noturno.py:_Cliente - nunca a lógica de negócio, só a
função registrada em registro.py que faria a chamada de rede/Supabase):
  - analise_ticker (yfinance/CVM/Supabase via data.market_researcher)
  - comparador (Supabase via data.research.comparador)
  - memoria_research (Gemini/Supabase via data.research.embeddings)
  - noticias (RSS do Google News via data.news)
  - catalisadores (Supabase/CVM via data.radar)
  - resultados_corporativos (CVM via data.earnings.reviewer)
  - data.supabase_client.obter_cliente (usado por persistencia.py) -
    substituído por um cliente fake em memória que implementa o mesmo
    encadeamento (.table().insert()/.update().eq()/.select().eq()
    .order().limit()).execute()) usado de verdade pelo projeto.
"""
import copy
import dataclasses
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.coordenador_central import executor, fluxos, modelagem, persistencia
from data.coordenador_central import registro as registro_mod

TICKER = "WEGE3"


# ============================================================
# Cliente Supabase fake em memória (mesma interface real usada por
# data/coordenador_central/persistencia.py) - guarda linhas por tabela
# num dict, suporta insert/update/select com eq/order/limit, o
# suficiente pro módulo real de persistência funcionar sem rede.
# ============================================================

class _FakeResposta:
    def __init__(self, data):
        self.data = data


class _FakeTabela:
    def __init__(self, cliente, nome):
        self.cliente = cliente
        self.nome = nome
        self._op = None
        self._payload = None
        self._filtros = []
        self._order = None
        self._limit = None

    def insert(self, payload):
        self._op, self._payload = "insert", dict(payload)
        return self

    def update(self, payload):
        self._op, self._payload = "update", dict(payload)
        return self

    def select(self, _cols="*"):
        self._op = "select"
        return self

    def eq(self, campo, valor):
        self._filtros.append((campo, valor))
        return self

    def order(self, campo, desc=False):
        self._order = (campo, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        linhas = self.cliente.dados.setdefault(self.nome, {})
        if self._op == "insert":
            row = dict(self._payload)
            row_id = row.get("id") or str(len(linhas) + 1)
            row.setdefault("id", row_id)
            linhas[row_id] = row
            return _FakeResposta([row])
        if self._op == "update":
            alvo = [r for r in linhas.values() if all(r.get(c) == v for c, v in self._filtros)]
            for r in alvo:
                r.update(self._payload)
            return _FakeResposta(alvo)
        if self._op == "select":
            resultado = [r for r in linhas.values() if all(r.get(c) == v for c, v in self._filtros)]
            if self._order:
                campo, desc = self._order
                resultado = sorted(resultado, key=lambda r: r.get(campo) or "", reverse=desc)
            if self._limit is not None:
                resultado = resultado[: self._limit]
            return _FakeResposta(resultado)
        return _FakeResposta([])


class _FakeCliente:
    def __init__(self):
        self.dados = {}

    def table(self, nome):
        return _FakeTabela(self, nome)


# ============================================================
# Fixtures realistas (fronteira de rede/IA) - 1 ticker real da
# watchlist (WEGE3), valores plausíveis, moeda consistente (BRL/REAL)
# de propósito pra exercitar o caminho real de prioridade CVM de
# data.coordenador_central.fluxos._anexar_premissas_dcf.
# ============================================================

_ANALISE_TICKER_BRUTO = {
    "ticker": TICKER,
    "gerado_em": date(2026, 11, 12),
    "fundamentos": {
        "preco": 40.0, "pl": 24.0, "pvp": 7.5, "dividend_yield": 1.6,
        "roe": 30.0, "margem_liquida": 14.5, "divida_liquida_ebitda": 0.4,
        "fluxo_caixa_livre": 1_500_000_000.0, "ebitda": 3_000_000_000.0,
        "valor_mercado": 150_000_000_000.0, "moeda": "BRL", "moeda_fonte": "BRL",
        "consultado_em": "2026-11-12T18:00:00-03:00",
    },
    "catalisadores": [
        {"categoria": "Resultado 4T26", "data": date(2026, 11, 20),
         "fonte_label": "Calendário B3", "fonte_url": "https://b3.com.br/calendario"},
    ],
    "mudancas_tese": [],
    "riscos_indicadores": ["Exposição cambial relevante na receita de exportação."],
    "interpretacao_movimento": None,
    "cobertura_research": {
        "ticker": TICKER,
        "cobertura": [{"casa": "BTG Pactual", "data": "2026-11-10", "link": "https://btg.com/wege3",
                        "titulo": "WEGE3: resultado consistente", "recomendacao": "COMPRA"}],
        "sem_cobertura": [], "divergencia": None,
    },
    "fundamentos_historicos": {
        "disponivel": True,
        "receita_liquida": {"yoy_pct_serie": [8.0, 9.5]},
        "roic_pct": {"serie": [18.0, 19.5]},
    },
    "comparativo_setorial": {"pl_mediana": 20.0},
    "fontes_indisponiveis": [],
}

_COMPARADOR_BRUTO = {
    "disponivel": True, "ticker": TICKER,
    "resumo_executivo": "1 casa cobre WEGE3, recomendação OTIMISTA.",
    "tabela_comparativa": [{
        "casa": "BTG Pactual", "recomendacao_categoria": "OTIMISTA", "recomendacao_original": "COMPRA",
        "preco_alvo": 46.0, "data_publicacao": "2026-11-10", "titulo": "WEGE3: resultado consistente",
        "link": "https://btg.com/wege3", "projecao_receita": "+9%", "projecao_ebitda_margem": "21%",
        "projecao_lucro": "+7%",
    }],
    "dispersao_precos_alvo": {
        "moeda": "BRL", "n_casas_total": 1, "n_casas_com_preco_alvo": 1, "amostra_insuficiente": False,
        "minimo": 46.0, "maximo": 46.0, "media": 46.0, "mediana": 46.0, "resumo": "1 casa com preço-alvo.",
    },
    "fontes_evidencias": [
        {"casa": "BTG Pactual", "data_publicacao": "2026-11-10", "link": "https://btg.com/wege3",
         "titulo": "WEGE3: resultado consistente"},
    ],
    "riscos": [], "indicadores_adicionais": {}, "pontos_atencao": [], "revisoes_recentes": {},
    "consenso": {"n_casas_total": 1, "amostra_insuficiente": False},
}

_MEMORIA_RESEARCH_BRUTO = {
    "resultados": [{
        "casa": "BTG Pactual", "recomendacao": "COMPRA", "preco_alvo": 46.0,
        "data_publicacao": "2026-11-10", "titulo": "WEGE3: resultado consistente",
        "link": "https://btg.com/wege3", "premissas": ["Margem EBITDA sustentada acima de 20%."],
        "riscos": ["Câmbio"], "projecoes": {"receita": "+9%"},
    }],
    "confianca": "MEDIA", "aviso": None,
}

_NOTICIAS_BRUTO = [
    {"veiculos": ["InfoMoney"], "data": "2026-11-11", "link": "https://infomoney.com/wege3",
     "titulo": "WEG anuncia novo contrato de exportação"},
]

_CATALISADORES_BRUTO = [
    {"fonte_label": "Calendário B3", "data": date(2026, 11, 20),
     "fonte_url": "https://b3.com.br/calendario", "categoria": "Resultado 4T26"},
]

_RESULTADOS_CORPORATIVOS_BRUTO = {
    "ticker": TICKER, "pais": "BR", "disponivel": True,
    "periodo_label": "3T2026", "dt_referencia": "2026-09-30", "moeda": "REAL",
    "metricas": {
        "receita_liquida": {"atual": 2_500_000_000.0, "yoy_variacao_pct": 9.5},
        "ebit": {"atual": 450_000_000.0, "yoy_variacao_pct": 7.0},
        "lucro_liquido_consolidado": {"atual": 380_000_000.0, "yoy_variacao_pct": 6.0},
    },
    "margem_bruta_pct": 33.5, "margem_bruta_yoy_anterior_pct": 32.0,
    "balanco_fluxo_caixa": {"divida_liquida_atual": 900_000_000.0, "roic_pct": 19.0},
    "fontes": ["CVM ITR 3T2026"],
    "limitacoes": ["Nota determinística; não substitui o relatório integral."],
}

_PREMISSAS_DCF_MANUAIS = {
    "crescimento_fcf_otimista": 12, "crescimento_fcf_base": 8, "crescimento_fcf_pessimista": 3,
    "wacc": 11, "g_terminal": 4,
}

_BRUTOS_POR_ESPECIALISTA = {
    "analise_ticker": _ANALISE_TICKER_BRUTO,
    "comparador": _COMPARADOR_BRUTO,
    "memoria_research": _MEMORIA_RESEARCH_BRUTO,
    "noticias": _NOTICIAS_BRUTO,
    "catalisadores": _CATALISADORES_BRUTO,
    "resultados_corporativos": _RESULTADOS_CORPORATIVOS_BRUTO,
}


def _obter_especialista_com_fixtures(especialista_id):
    """Substitui SÓ a `funcao` (fronteira de rede/IA) dos 6 especialistas
    acima por um stub que devolve a fixture fixa - o extrator_saida
    (real) e todo o resto do pipeline (executor/fluxos/consolidacao/
    pareceres/modelagem/dcf/persistencia) roda sem nenhum mock."""
    original = registro_mod.obter_especialista(especialista_id)
    if original is None or especialista_id not in _BRUTOS_POR_ESPECIALISTA:
        return original
    bruto = _BRUTOS_POR_ESPECIALISTA[especialista_id]
    # deepcopy a cada chamada: fluxos._anexar_premissas_dcf muta
    # resultados["analise_ticker"]["dados"] IN PLACE (o mesmo dict que o
    # extrator_saida devolve como "dados" == o `bruto` abaixo) - sem a
    # cópia, o teste de premissas_dcf=None (que roda depois, mesma
    # fixture módulo) herdaria o "premissas_dcf" calculado pelo teste
    # anterior e o Model Builder deixaria de ser pulado por engano.
    return dataclasses.replace(original, funcao=lambda **_kwargs: copy.deepcopy(bruto))


def test_fluxo_completo_comite_produz_recomendacao_consultavel():
    cliente = _FakeCliente()
    with patch.object(persistencia, "obter_cliente", return_value=cliente), \
         patch.object(executor, "obter_especialista", side_effect=_obter_especialista_com_fixtures):
        consolidado = fluxos.analisar_ticker(TICKER, premissas_dcf=_PREMISSAS_DCF_MANUAIS)

        # --------------------------------------------------------
        # 1) Cada etapa recebeu o dado da etapa anterior e processou:
        # Market Researcher -> Earnings Reviewer -> Model Builder ->
        # Valuation Reviewer -> Coordenador (consolidacao/pareceres).
        # --------------------------------------------------------
        visao = consolidado["visao_especialistas"]
        for especialista_id in (
            "analise_ticker", "comparador", "memoria_research", "noticias",
            "catalisadores", "resultados_corporativos", "model_builder", "valuation_reviewer",
        ):
            assert especialista_id in visao, especialista_id
            assert "pulado" not in visao[especialista_id], (
                f"{especialista_id} não deveria ser pulado - premissas_dcf foi fornecida"
            )
            assert visao[especialista_id]["disponivel"] is True, (
                especialista_id, visao[especialista_id].get("motivo_indisponivel")
            )

        assert consolidado["status_execucao"] == "CONCLUIDA"
        assert consolidado["persistencia_analise_ok"] is True

        pareceres = consolidado["pareceres_analistas"]
        analistas_por_id = {a["id"]: a for a in pareceres["analistas"]}

        # Model Builder recebeu as premissas derivadas de analise_ticker +
        # resultados_corporativos (prioridade de dívida líquida da CVM -
        # ver data/coordenador_central/fluxos.py:_anexar_premissas_dcf)
        # e calculou um DCF real de 3 cenários.
        model_builder = analistas_por_id["model_builder"]
        assert model_builder["recomendacao"] == "MODELADO"
        cenarios = model_builder["cenarios"]
        assert set(cenarios) == {"pessimista", "base", "otimista"}
        alvo_pess = cenarios["pessimista"]["preco_alvo"]
        alvo_base = cenarios["base"]["preco_alvo"]
        alvo_otim = cenarios["otimista"]["preco_alvo"]
        assert alvo_pess <= alvo_base <= alvo_otim
        premissas_modelo = model_builder["premissas"]
        assert premissas_modelo["divida_liquida"] == 900_000_000.0  # veio da CVM, não do yfinance
        assert premissas_modelo["origem_divida_liquida"] == "CVM — balanço patrimonial consolidado"

        # Valuation Reviewer auditou o MESMO DCF do Model Builder (não
        # recalculou) e aprovou (dados consistentes/ordenados/rastreáveis).
        valuation_reviewer = analistas_por_id["valuation_reviewer"]
        assert valuation_reviewer["recomendacao"] == "APROVADO"
        assert valuation_reviewer["achados"] == []
        assert valuation_reviewer["preco_alvo"] == alvo_base

        # --------------------------------------------------------
        # 2) Campos pedidos pro shape de "recomendação final" (Frente 2):
        # ativo, preço atual + data, preço-alvo, potencial, cenários,
        # premissas, catalisadores, riscos, pros/contras, indicadores,
        # fontes, confiança, horizonte, data da análise.
        # --------------------------------------------------------
        sinal = consolidado["sinal_comite"]
        assert consolidado["ticker"] == TICKER  # ativo/empresa
        assert sinal["preco_atual"] == 40.0  # preço atual
        assert sinal["preco_atual_consultado_em"] == "2026-11-12T18:00:00-03:00"  # data/hora da cotação
        assert sinal["preco_alvo_modelo"] == alvo_base  # preço-alvo (DCF cenário-base)
        assert isinstance(sinal["upside_modelo_pct"], float)  # potencial de alta/baixa
        assert sinal["horizonte_dcf"] == "5 anos de fluxo de caixa explícito + valor terminal (Gordon Growth)"
        assert sinal["data_analise"]  # data da análise (ISO, setado por consolidacao.consolidar)
        assert sinal["sinal"] in {"COMPRA", "VENDA", "NEUTRO", "INSUFICIENTE"}
        # confiança NUNCA no formato acentuado "MÉDIA" (achado real desta
        # auditoria: data/research/sinal.py usava grafia diferente de
        # consolidacao.py/ui, corrigido nesta mesma missão).
        assert sinal["confianca"] in {"ALTA", "MEDIA", "BAIXA", "INSUFICIENTE"}
        assert consolidado["confianca"]["categoria"] in {"ALTA", "MEDIA", "BAIXA", "INSUFICIENTE"}

        market_researcher = analistas_por_id["market_researcher"]
        assert market_researcher["indicadores"]  # indicadores usados
        assert market_researcher["fontes"]  # fontes
        earnings_reviewer = analistas_por_id["earnings_reviewer"]
        assert earnings_reviewer["fontes"] == ["CVM ITR 3T2026"]

        # cenários pessimista/base/otimista com premissas explícitas -
        # nunca um único número "preço-alvo" sem a faixa.
        assert cenarios["pessimista"]["crescimento_fcf"] < cenarios["otimista"]["crescimento_fcf"]

        # catalisadores e riscos aparecem na análise consolidada (via
        # analise_ticker, dados brutos) - nenhum deles inventado.
        dados_analise = visao["analise_ticker"]["dados"]
        assert dados_analise["catalisadores"] == _ANALISE_TICKER_BRUTO["catalisadores"]
        assert dados_analise["riscos_indicadores"] == _ANALISE_TICKER_BRUTO["riscos_indicadores"]

        # --------------------------------------------------------
        # 3) Persistência real (cliente fake) + consulta de volta -
        # prova que o resultado final é CONSULTÁVEL, não só devolvido
        # em memória pra quem chamou analisar_ticker.
        # --------------------------------------------------------
        analise_id = consolidado["_analise_id"]
        linha_persistida = cliente.dados["coordenador_analises"][analise_id]
        assert linha_persistida["status"] == "CONCLUIDA"
        assert linha_persistida["resultado"]["ticker"] == TICKER
        assert linha_persistida["resultado"]["sinal_comite"]["preco_alvo_modelo"] == alvo_base

        execucoes = list(cliente.dados["coordenador_especialistas_execucoes"].values())
        especialistas_com_execucao = {e["especialista_id"] for e in execucoes}
        assert especialistas_com_execucao == set(visao.keys())
        assert all(e["disponivel"] for e in execucoes)

    # Consulta de volta (fora do bloco de patch de obter_especialista,
    # só com o Supabase fake ainda mockado) - mesmo caminho real que
    # ui/coordenador_tab.py usa pra exibir o histórico/aba Analisar.
    with patch.object(persistencia, "obter_cliente", return_value=cliente):
        obtida = persistencia.obter_analise(analise_id)
        assert obtida["ticker"] == TICKER
        assert obtida["resultado"]["sinal_comite"]["sinal"] == consolidado["sinal_comite"]["sinal"]

        historico_ticker = persistencia.listar_analises_por_ticker(TICKER)
        assert len(historico_ticker) == 1
        assert historico_ticker[0]["id"] == analise_id

        metricas = persistencia.metricas_especialistas()
        assert metricas["model_builder"]["total_execucoes"] == 1
        assert metricas["model_builder"]["taxa_sucesso_pct"] == 100.0


def test_fluxo_sem_premissas_pula_model_builder_mas_resto_da_cadeia_continua_real():
    """Caminho real de jobs/comite_noturno.py (nunca passa premissas_dcf) -
    confirma que mesmo SEM DCF, o restante da cadeia (Market Researcher,
    Earnings Reviewer, comparador, memória, notícias, catalisadores,
    consolidação, persistência) continua rodando de verdade e produz um
    sinal consultável; model_builder/valuation_reviewer ficam
    corretamente marcados como pulados (não inventam WACC/crescimento)."""
    cliente = _FakeCliente()
    with patch.object(persistencia, "obter_cliente", return_value=cliente), \
         patch.object(executor, "obter_especialista", side_effect=_obter_especialista_com_fixtures):
        consolidado = fluxos.analisar_ticker(TICKER)

    visao = consolidado["visao_especialistas"]
    assert visao["model_builder"]["pulado"] is True
    assert visao["model_builder"]["disponivel"] is False
    assert visao["valuation_reviewer"]["pulado"] is True
    assert consolidado["status_execucao"] == "CONCLUIDA"
    sinal = consolidado["sinal_comite"]
    assert sinal["sinal"] in {"COMPRA", "VENDA", "NEUTRO", "INSUFICIENTE"}
    # Sem DCF, o preço-alvo do cabeçalho cai pro fallback mecânico de P/L
    # setorial (nunca None silencioso, nunca um DCF fantasma).
    assert sinal["horizonte_dcf"] is None
    assert sinal["metodo_preco_alvo_modelo"] == (
        "Estimativa mecânica por P/L setorial; DCF indisponível até receber premissas completas. "
        "Não é alvo de research."
    )
