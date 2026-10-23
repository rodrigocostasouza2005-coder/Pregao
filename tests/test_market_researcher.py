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


def test_listar_achados_historico_banco_indisponivel_e_none():
    with patch.object(mr, "obter_cliente", return_value=None):
        assert mr.listar_achados_historico() is None


def test_historico_achado_sem_registro_e_none():
    cliente = _ClienteAchadosFake()
    with patch.object(mr, "obter_cliente", return_value=cliente):
        assert mr.historico_achado("NEWS (Brasil)", "Noticias", "FALHA_EXECUCAO") is None
