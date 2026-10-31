# -*- coding: utf-8 -*-
"""MARKET RESEARCHER (data/market_researcher.py): camada de avaliação de
qualidade dos coletores (reaproveita data/saude_dados.py) + comparação
de cobertura entre casas de research (reaproveita data/research/store.py)
- sem coletor novo, sem tabela nova, sem chamada de IA nova. Testes
cobrem: priorização por severidade/criticidade, degradação quando uma
fonte falha, e que "divergência" só é apontada com campo estruturado
real (nunca inferida de título/sentimento)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from data import market_researcher as mr


def _coletor(nome, categoria, codigo_estado, alerta=True, desconhecido=False, erro=None):
    return {
        "nome": nome, "categoria": categoria, "codigo_estado": codigo_estado,
        "rotulo_estado": codigo_estado, "alerta": alerta, "desconhecido": desconhecido,
        "status_bruto": {"ultimo_sucesso_em": None, "ultima_tentativa_em": "2026-10-23T10:00:00Z", "ultimo_erro": erro},
    }


def test_achados_ignora_coletores_saudaveis():
    painel = [_coletor("NEWS (Brasil)", "Noticias", "SUCESSO_COM_NOVIDADE", alerta=False, desconhecido=False)]
    with patch.object(mr.saude_dados, "obter_painel_saude", return_value=painel):
        achados = mr.achados_qualidade_coletores()
    assert achados == []


def test_achados_prioriza_critico_sobre_secundario_mesmo_codigo_igual():
    painel = [
        _coletor("Genial Analisa", "Research", "FALHA_EXECUCAO", erro="bloqueio WAF"),
        _coletor("NEWS (Brasil)", "Noticias", "FALHA_EXECUCAO", erro="timeout"),
    ]
    with patch.object(mr.saude_dados, "obter_painel_saude", return_value=painel):
        achados = mr.achados_qualidade_coletores()
    assert [a["coletor"] for a in achados] == ["NEWS (Brasil)", "Genial Analisa"]
    assert achados[0]["critico"] is True
    assert achados[1]["critico"] is False


def test_achados_prioriza_falha_persistencia_antes_de_fonte_indisponivel():
    painel = [
        _coletor("CVM (watchlist)", "CVM", "FONTE_INDISPONIVEL"),
        _coletor("MERCADO", "Cotacoes", "FALHA_PERSISTENCIA"),
    ]
    with patch.object(mr.saude_dados, "obter_painel_saude", return_value=painel):
        achados = mr.achados_qualidade_coletores()
    assert achados[0]["coletor"] == "MERCADO"


def test_achados_degrada_sem_excecao_quando_painel_falha():
    with patch.object(mr.saude_dados, "obter_painel_saude", side_effect=RuntimeError("Supabase fora do ar")):
        assert mr.achados_qualidade_coletores() == []


def _item(casa, data_iso, titulo="Relatório", recomendacao=None, preco_alvo=None, tickers=("WEGE3",)):
    return {"casa": casa, "data": data_iso, "titulo": titulo, "link": f"https://{casa}/x",
            "recomendacao": recomendacao, "preco_alvo": preco_alvo, "tickers": list(tickers)}


def test_cobertura_cruzada_lista_quem_cobriu_e_quem_nao_cobriu():
    hoje = datetime.now(timezone.utc)
    itens = [_item("Genial Analisa", hoje.isoformat()), _item("XP Investimentos", (hoje - timedelta(days=40)).isoformat())]
    with patch.object(mr, "listar_itens", return_value=itens), \
         patch.object(mr, "_casas_ativas_nomes", return_value=["Genial Analisa", "XP Investimentos", "BTG Research"]):
        resultado = mr.cobertura_cruzada_casas("WEGE3")
    nomes_cobertura = {c["casa"] for c in resultado["cobertura"]}
    assert nomes_cobertura == {"Genial Analisa"}  # XP está fora da janela de 30 dias
    assert resultado["sem_cobertura"] == ["BTG Research", "XP Investimentos"]
    assert resultado["divergencia"] is None


def test_cobertura_cruzada_banco_indisponivel_e_distinto_de_sem_cobertura():
    with patch.object(mr, "listar_itens", return_value=None):
        resultado = mr.cobertura_cruzada_casas("WEGE3")
    assert resultado["cobertura"] is None
    assert resultado["sem_cobertura"] == []


def test_cobertura_cruzada_so_aponta_divergencia_com_campo_estruturado_real():
    hoje = datetime.now(timezone.utc).isoformat()
    itens = [
        _item("Genial Analisa", hoje, recomendacao="COMPRA"),
        _item("XP Investimentos", hoje, recomendacao="VENDA"),
    ]
    with patch.object(mr, "listar_itens", return_value=itens), \
         patch.object(mr, "_casas_ativas_nomes", return_value=["Genial Analisa", "XP Investimentos"]):
        resultado = mr.cobertura_cruzada_casas("WEGE3")
    assert resultado["divergencia"]["por_casa"] == {"Genial Analisa": "COMPRA", "XP Investimentos": "VENDA"}


def test_cobertura_cruzada_nunca_infere_divergencia_so_de_titulo():
    hoje = datetime.now(timezone.utc).isoformat()
    itens = [
        _item("Genial Analisa", hoje, titulo="WEGE3: hora de vender?", recomendacao=None),
        _item("XP Investimentos", hoje, titulo="WEGE3 é uma boa compra", recomendacao=None),
    ]
    with patch.object(mr, "listar_itens", return_value=itens), \
         patch.object(mr, "_casas_ativas_nomes", return_value=["Genial Analisa", "XP Investimentos"]):
        resultado = mr.cobertura_cruzada_casas("WEGE3")
    assert resultado["divergencia"] is None  # sem campo estruturado, nunca infere do título


# ============================================================
# Memória operacional persistente (sql/market_researcher_achados.sql)
# ============================================================

class _TabelaAchadosFake:
    def __init__(self, cliente):
        self.cliente = cliente
        self._op = None
        self._filtros = {}
        self._payload = None

    def select(self, *_a, **_k):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = dict(payload)
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = dict(payload)
        return self

    def eq(self, campo, valor):
        self._filtros[campo] = valor
        return self

    def limit(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def execute(self):
        if self._op == "insert":
            linha = {"id": len(self.cliente.linhas) + 1, **self._payload}
            self.cliente.linhas[linha["id"]] = linha
            return _RespostaFake([linha])
        if self._op == "update":
            alvo_id = self._filtros.get("id")
            afetadas = []
            for linha in self.cliente.linhas.values():
                if alvo_id is not None and linha["id"] != alvo_id:
                    continue
                if alvo_id is None and not all(linha.get(k) == v for k, v in self._filtros.items()):
                    continue
                linha.update(self._payload)
                afetadas.append(linha)
            return _RespostaFake(afetadas)
        if self._op == "select":
            linhas = [l for l in self.cliente.linhas.values()
                      if all(l.get(k) == v for k, v in self._filtros.items())]
            return _RespostaFake(linhas)
        return _RespostaFake([])


class _RespostaFake:
    def __init__(self, data):
        self.data = data


class _ClienteAchadosFake:
    def __init__(self):
        self.linhas = {}

    def table(self, _nome):
        return _TabelaAchadosFake(self)


def test_registrar_achados_sem_banco_retorna_ok_false():
    with patch.object(mr, "obter_cliente", return_value=None):
        resultado = mr.registrar_achados_atuais()
    assert resultado == {"ok": False, "motivo": "Supabase indisponível"}


def test_registrar_achados_cria_linha_nova_e_atualiza_em_chamada_repetida():
    achado = {"coletor": "NEWS (Brasil)", "categoria": "Noticias", "codigo_estado": "FALHA_EXECUCAO",
              "rotulo_estado": "Falha de execucao", "critico": True, "evidencia": {}}
    cliente = _ClienteAchadosFake()
    with patch.object(mr, "obter_cliente", return_value=cliente), \
         patch.object(mr, "achados_qualidade_coletores", return_value=[achado]):
        r1 = mr.registrar_achados_atuais()
        r2 = mr.registrar_achados_atuais()
    assert r1 == {"ok": True, "achados_atuais": 1}
    assert r2 == {"ok": True, "achados_atuais": 1}
    assert len(cliente.linhas) == 1  # 2ª chamada atualiza a MESMA linha, nunca duplica
    linha = next(iter(cliente.linhas.values()))
    assert linha["ocorrencias"] == 2
    assert linha["status"] == "ABERTO"


def test_achado_que_some_da_lista_atual_e_marcado_resolvido():
    achado = {"coletor": "NEWS (Brasil)", "categoria": "Noticias", "codigo_estado": "FALHA_EXECUCAO",
              "rotulo_estado": "Falha", "critico": True, "evidencia": {}}
    cliente = _ClienteAchadosFake()
    with patch.object(mr, "obter_cliente", return_value=cliente), \
         patch.object(mr, "achados_qualidade_coletores", return_value=[achado]):
        mr.registrar_achados_atuais()
    with patch.object(mr, "obter_cliente", return_value=cliente), \
         patch.object(mr, "achados_qualidade_coletores", return_value=[]):
        mr.registrar_achados_atuais()
    linha = next(iter(cliente.linhas.values()))
    assert linha["status"] == "RESOLVIDO"
    assert linha["resolvido_em"] is not None


def test_registrar_achados_preserva_triagem_manual_em_andamento():
    """Coordenador/Backoffice (2026-10-29): registrar_achados_atuais()
    agora roda por agendamento (jobs/coordenador.py), não só por clique
    - precisa parar de resetar pra ABERTO um achado que o Rodrigo já
    avançou manualmente na interface web (INVESTIGANDO/
    AGUARDANDO_INTERVENCAO/INCONCLUSIVO), senão toda rodada do cron
    apagaria a triagem em andamento."""
    achado = {"coletor": "NEWS (Brasil)", "categoria": "Noticias", "codigo_estado": "FALHA_EXECUCAO",
              "rotulo_estado": "Falha de execucao", "critico": True, "evidencia": {}}
    cliente = _ClienteAchadosFake()
    with patch.object(mr, "obter_cliente", return_value=cliente), \
         patch.object(mr, "achados_qualidade_coletores", return_value=[achado]):
        mr.registrar_achados_atuais()
    linha = next(iter(cliente.linhas.values()))
    linha["status"] = "INVESTIGANDO"  # triagem manual feita na web

    with patch.object(mr, "obter_cliente", return_value=cliente), \
         patch.object(mr, "achados_qualidade_coletores", return_value=[achado]):
        mr.registrar_achados_atuais()

    linha = next(iter(cliente.linhas.values()))
    assert linha["status"] == "INVESTIGANDO"  # preservado, não resetado pra ABERTO
    assert linha["ocorrencias"] == 2  # continua contando ocorrência normalmente


def test_registrar_achados_reabre_achado_resolvido_que_volta_a_acontecer():
    achado = {"coletor": "NEWS (Brasil)", "categoria": "Noticias", "codigo_estado": "FALHA_EXECUCAO",
              "rotulo_estado": "Falha de execucao", "critico": True, "evidencia": {}}
    cliente = _ClienteAchadosFake()
    with patch.object(mr, "obter_cliente", return_value=cliente), \
         patch.object(mr, "achados_qualidade_coletores", return_value=[achado]):
        mr.registrar_achados_atuais()
    linha = next(iter(cliente.linhas.values()))
    linha["status"] = "RESOLVIDO"

    with patch.object(mr, "obter_cliente", return_value=cliente), \
         patch.object(mr, "achados_qualidade_coletores", return_value=[achado]):
        mr.registrar_achados_atuais()

    linha = next(iter(cliente.linhas.values()))
    assert linha["status"] == "ABERTO"  # problema voltou -> reabre, nunca fica RESOLVIDO escondendo recorrência


def test_listar_achados_historico_banco_indisponivel_e_none():
    with patch.object(mr, "obter_cliente", return_value=None):
        assert mr.listar_achados_historico() is None


def test_historico_achado_sem_registro_e_none():
    cliente = _ClienteAchadosFake()
    with patch.object(mr, "obter_cliente", return_value=cliente):
        assert mr.historico_achado("NEWS (Brasil)", "Noticias", "FALHA_EXECUCAO") is None


# ============================================================
# analise_ticker() - agregador puro (fundamentos + market_makers +
# cobertura cruzada) - caso de teste WEGE3.
# ============================================================

_FUNDAMENTOS_WEGE3 = {"ticker": "WEGE3", "preco": 40.0, "pl": 28.5, "pvp": 9.1, "dividend_yield": 1.2,
                      "roe": 32.0, "margem_liquida": 14.0, "divida_liquida_ebitda": 0.3,
                      "valor_mercado": 150_000_000_000, "alerta_qualidade": []}
_CONTEXTO_WEGE3 = {"ticker": "WEGE3", "catalisadores": [{"categoria": "Resultado corporativo"}],
                   "mudancas": [], "riscos": [], "interpretacao": None}
_COBERTURA_WEGE3 = {"ticker": "WEGE3", "cobertura": [{"casa": "Genial Analisa"}], "sem_cobertura": [], "divergencia": None}
_HISTORICO_WEGE3 = {"disponivel": True, "periodos": ["1T2026", "2T2026"],
                     "receita_liquida": {"yoy_pct_serie": [2.0, 5.0], "tendencia": "RECUPERACAO"},
                     "ebit": {"yoy_pct_serie": [1.0, 3.0], "tendencia": "RECUPERACAO"},
                     "lucro_liquido_consolidado": {"yoy_pct_serie": [0.5, 1.0], "tendencia": "ESTABILIDADE"},
                     "margem_bruta_pct": {"serie": [38.0, 38.5], "tendencia": "ESTABILIDADE"}}
_SETORIAL_WEGE3 = {"setor": "Bens de Capital e Industrial", "pares_considerados": 6, "insuficiente": False,
                   "pl_mediana": 18.0, "pl_mediana_n": 5, "pvp_mediana": 4.0, "pvp_mediana_n": 5,
                   "dy_mediana": 2.5, "dy_mediana_n": 4}


def _patches_analise_ticker(fundamentos=_FUNDAMENTOS_WEGE3, contexto=_CONTEXTO_WEGE3,
                             cobertura=_COBERTURA_WEGE3, historico=_HISTORICO_WEGE3,
                             setorial=_SETORIAL_WEGE3, fund_kw=None, ctx_kw=None, cob_kw=None,
                             hist_kw=None, set_kw=None):
    """Monta os 5 patches de analise_ticker de uma vez - mantém os testes
    novos (historico_fundamentos/comparaveis_setor) do mesmo tamanho dos
    já existentes, sem rede real (CVM/yfinance) em nenhum teste aqui."""
    kw = lambda d: d if d is not None else {}  # noqa: E731
    return (
        patch.object(mr, "linha_valuation", **(kw(fund_kw) or {"return_value": fundamentos})),
        patch.object(mr, "contexto_ticker", **(kw(ctx_kw) or {"return_value": contexto})),
        patch.object(mr, "cobertura_cruzada_casas", **(kw(cob_kw) or {"return_value": cobertura})),
        patch.object(mr, "historico_fundamentos", **(kw(hist_kw) or {"return_value": historico})),
        patch.object(mr, "comparaveis_setor", **(kw(set_kw) or {"return_value": setorial})),
    )


def test_analise_ticker_compoe_os_5_blocos_sem_consulta_duplicada():
    p_fund, p_ctx, p_cob, p_hist, p_set = _patches_analise_ticker()
    with p_fund as m_fund, p_ctx as m_ctx, p_cob as m_cob, p_hist as m_hist, p_set as m_set:
        resultado = mr.analise_ticker("WEGE3")

    assert resultado["ticker"] == "WEGE3"
    assert resultado["fundamentos"] == _FUNDAMENTOS_WEGE3
    assert resultado["catalisadores"] == _CONTEXTO_WEGE3["catalisadores"]
    assert resultado["cobertura_research"] == _COBERTURA_WEGE3
    assert resultado["fundamentos_historicos"] == _HISTORICO_WEGE3
    assert resultado["comparativo_setorial"] == _SETORIAL_WEGE3
    assert resultado["fontes_indisponiveis"] == []
    # cada fonte chamada exatamente 1x pra 1 ticker - nenhuma consulta duplicada
    m_fund.assert_called_once_with("WEGE3")
    m_ctx.assert_called_once()
    m_cob.assert_called_once_with("WEGE3")
    m_hist.assert_called_once_with("WEGE3")
    m_set.assert_called_once_with("WEGE3")


def test_analise_ticker_normaliza_ticker_minusculo_com_espaco():
    p_fund, p_ctx, p_cob, p_hist, p_set = _patches_analise_ticker()
    with p_fund, p_ctx, p_cob, p_hist, p_set:
        resultado = mr.analise_ticker(" wege3 ")
    assert resultado["ticker"] == "WEGE3"


def test_analise_ticker_fonte_de_fundamentos_falha_outros_blocos_seguem():
    p_fund, p_ctx, p_cob, p_hist, p_set = _patches_analise_ticker(
        fund_kw={"side_effect": RuntimeError("yfinance fora do ar")})
    with p_fund, p_ctx, p_cob, p_hist, p_set:
        resultado = mr.analise_ticker("WEGE3")

    assert resultado["fundamentos"] is None
    assert resultado["fontes_indisponiveis"] == ["fundamentos"]
    assert resultado["catalisadores"] == _CONTEXTO_WEGE3["catalisadores"]  # não contaminado
    assert resultado["fundamentos_historicos"] == _HISTORICO_WEGE3  # não contaminado


def test_analise_ticker_fonte_de_historico_falha_outros_blocos_seguem():
    p_fund, p_ctx, p_cob, p_hist, p_set = _patches_analise_ticker(
        hist_kw={"side_effect": RuntimeError("CVM fora do ar")})
    with p_fund, p_ctx, p_cob, p_hist, p_set:
        resultado = mr.analise_ticker("WEGE3")

    assert resultado["fundamentos_historicos"] is None
    assert resultado["fontes_indisponiveis"] == ["historico_fundamentos"]
    assert resultado["fundamentos"] == _FUNDAMENTOS_WEGE3  # não contaminado


def test_analise_ticker_todas_as_fontes_falham_nunca_lanca_excecao():
    p_fund, p_ctx, p_cob, p_hist, p_set = _patches_analise_ticker(
        fund_kw={"side_effect": RuntimeError("x")}, ctx_kw={"side_effect": RuntimeError("y")},
        cob_kw={"side_effect": RuntimeError("z")}, hist_kw={"side_effect": RuntimeError("w")},
        set_kw={"side_effect": RuntimeError("v")})
    with p_fund, p_ctx, p_cob, p_hist, p_set:
        resultado = mr.analise_ticker("WEGE3")

    assert resultado["fundamentos"] is None
    assert resultado["catalisadores"] is None
    assert resultado["cobertura_research"] is None
    assert resultado["fundamentos_historicos"] is None
    assert resultado["comparativo_setorial"] is None
    assert set(resultado["fontes_indisponiveis"]) == {
        "fundamentos", "contexto_mercado", "cobertura_research", "historico_fundamentos", "comparativo_setorial",
    }


def test_analise_ticker_sem_dado_nenhum_nunca_inventa_informacao():
    contexto_vazio = {"ticker": "WEGE3", "catalisadores": [], "mudancas": [], "riscos": [], "interpretacao": None}
    cobertura_vazia = {"ticker": "WEGE3", "cobertura": [], "sem_cobertura": ["Genial Analisa"], "divergencia": None}
    p_fund, p_ctx, p_cob, p_hist, p_set = _patches_analise_ticker(
        fundamentos={"ticker": "WEGE3", "preco": None, "alerta_qualidade": []}, contexto=contexto_vazio,
        cobertura=cobertura_vazia, historico={"disponivel": False, "motivo": "sem DRE nesta janela."},
        setorial={"setor": None, "pares_considerados": 0, "insuficiente": True, "motivo": "sem setor"})
    with p_fund, p_ctx, p_cob, p_hist, p_set:
        resultado = mr.analise_ticker("WEGE3")

    assert resultado["fontes_indisponiveis"] == []  # todas as fontes RESPONDERAM
    assert resultado["catalisadores"] == []  # mas sem dado - lista vazia, nunca inventada
    assert resultado["interpretacao_movimento"] is None


def test_analise_ticker_nao_escreve_em_nenhuma_tabela(monkeypatch):
    """Agregador é só leitura - nunca chama obter_cliente/persistência
    nenhuma (ausência de efeito colateral)."""
    chamou_cliente = []
    monkeypatch.setattr(mr, "obter_cliente", lambda: chamou_cliente.append(True) or None)
    p_fund, p_ctx, p_cob, p_hist, p_set = _patches_analise_ticker()
    with p_fund, p_ctx, p_cob, p_hist, p_set:
        mr.analise_ticker("WEGE3")
    assert chamou_cliente == []


# ============================================================
# historico_fundamentos() - só Brasil nesta versão (ver _pais_code)
# ============================================================

def test_historico_fundamentos_br_delega_pra_serie_historica_br():
    with patch.object(mr, "_pais_code", return_value="BR"), \
         patch.object(mr.earnings_reviewer, "serie_historica_br", return_value=_HISTORICO_WEGE3) as m:
        resultado = mr.historico_fundamentos("WEGE3")
    assert resultado == _HISTORICO_WEGE3
    m.assert_called_once_with("WEGE3")


def test_historico_fundamentos_internacional_declara_lacuna_sem_chamar_cvm():
    with patch.object(mr, "_pais_code", return_value="US"), \
         patch.object(mr.earnings_reviewer, "serie_historica_br") as m:
        resultado = mr.historico_fundamentos("AAPL34")
    assert resultado["disponivel"] is False
    assert "calendário fiscal" in resultado["motivo"]
    m.assert_not_called()


# ============================================================
# consenso_research() - reorganiza cobertura_cruzada_casas, zero cálculo
# novo. Ausência de cobertura nunca é tratada como sinal.
# ============================================================

def test_consenso_research_banco_indisponivel():
    resultado = mr.consenso_research({"ticker": "WEGE3", "cobertura": None, "sem_cobertura": [], "divergencia": None})
    assert resultado["disponivel"] is False


def test_consenso_research_conta_casas_cobrindo_e_sem_cobertura():
    resultado = mr.consenso_research(_COBERTURA_WEGE3)
    assert resultado["disponivel"] is True
    assert resultado["n_casas_cobrindo"] == 1
    assert resultado["n_casas_sem_cobertura"] == 0
    assert resultado["itens"] == _COBERTURA_WEGE3["cobertura"]


def test_consenso_research_sem_cobertura_nenhuma_nao_e_sinal():
    cobertura = {"ticker": "XPTO3", "cobertura": [], "sem_cobertura": ["Genial Analisa", "XP Investimentos"],
                 "divergencia": None}
    resultado = mr.consenso_research(cobertura)
    assert resultado["disponivel"] is True
    assert resultado["n_casas_cobrindo"] == 0
    assert resultado["n_casas_sem_cobertura"] == 2
    assert resultado["itens"] == []  # fato (nenhuma publicou), nunca interpretado como neutro/negativo


def test_consenso_research_propaga_divergencia_estruturada():
    cobertura = {**_COBERTURA_WEGE3, "divergencia": {"descricao": "diverge", "por_casa": {"A": "COMPRA", "B": "VENDA"}}}
    resultado = mr.consenso_research(cobertura)
    assert resultado["divergencia"]["descricao"] == "diverge"
