# -*- coding: utf-8 -*-
"""Testes de data/research/store.py:apagar_itens_antigos - bug real
encontrado em auditoria (2026-11-02): o coletor Nord (data/research/
nord.py) não tem RSS, descobre posts via sitemap/lastmod com latência
real de semanas/meses entre a publicação ('data') e a descoberta -
confirmado com coleta real: 8 itens, 'data' 80-90 dias atrás. A regra de
'data velha' da limpeza apagava esses itens na passada seguinte à
própria coleta que os inseriu (coletor reportava sucesso/persistência
OK, mas o item nunca sobrevivia em research_itens). Corrigido excluindo
'Nord Research' (_CASAS_RETENCAO_SO_POR_COLETA) da deleção por 'data
velha' - essa casa só sai pela regra de 'coletado_em', igual as demais
quando param de ser recoletadas.

Mocka só a cadeia do cliente Supabase (sem rede real), mesmo padrão de
outros testes de store.py (ver tests/test_research_fase3.py)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import data.research.store as store_mod


def _cliente_delete_capturando(chamadas: list, resultado_data=None):
    """Cliente fake que registra, por chamada de delete(), a sequência
    de filtros aplicados (nome do método + argumentos) - permite
    verificar que 'Nord Research' nunca entra na query de 'data velha'."""
    cliente = MagicMock()

    class _QueryBuilder:
        def __init__(self, filtros):
            self.filtros = filtros

        def neq(self, campo, valor):
            return _QueryBuilder(self.filtros + [("neq", campo, valor)])

        def lt(self, campo, valor):
            return _QueryBuilder(self.filtros + [("lt", campo, valor)])

        def execute(self):
            chamadas.append(list(self.filtros))
            resp = MagicMock()
            resp.data = resultado_data if resultado_data is not None else []
            return resp

    def _delete():
        return _QueryBuilder([])

    cliente.table.return_value.delete.side_effect = _delete
    return cliente


def test_nord_excluida_da_query_de_data_velha():
    """A query de 'data velha' (1ª chamada de delete) precisa ter um
    neq('casa', 'Nord Research') - bug real: sem esse filtro, itens
    recém-coletados da Nord (data sistematicamente >5 dias) eram
    apagados na limpeza seguinte à própria coleta."""
    chamadas = []
    cliente = _cliente_delete_capturando(chamadas)
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        store_mod.apagar_itens_antigos(dias=5)
    query_data_velha = chamadas[0]
    excecoes_casa = [v for (op, campo, v) in query_data_velha if op == "neq" and campo == "casa"]
    assert "Nord Research" in excecoes_casa


def test_query_de_coletado_em_nao_exclui_nenhuma_casa():
    """A 2ª chamada (coletado_em velho) continua valendo pra TODAS as
    casas, inclusive Nord - um item da Nord que parou de ser recoletado
    (fonte mudou, bloqueio permanente etc.) ainda deve expirar normalmente,
    só não pela regra de 'data velha'."""
    chamadas = []
    cliente = _cliente_delete_capturando(chamadas)
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        store_mod.apagar_itens_antigos(dias=5)
    query_coletado_em = chamadas[1]
    excecoes_casa = [v for (op, campo, v) in query_coletado_em if op == "neq" and campo == "casa"]
    assert excecoes_casa == []


def test_apagar_itens_antigos_soma_as_duas_queries():
    chamadas = []
    cliente = _cliente_delete_capturando(chamadas, resultado_data=[{"id": 1}, {"id": 2}])
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        total = store_mod.apagar_itens_antigos(dias=5)
    assert total == 4  # 2 linhas por query, 2 queries


def test_banco_fora_do_ar_devolve_menos_1():
    with patch.object(store_mod, "obter_cliente", return_value=None):
        assert store_mod.apagar_itens_antigos() == -1


def test_simulacao_real_nord_80_dias_sobrevive_a_limpeza_de_data_velha():
    """Simula exatamente o cenário real encontrado (2026-11-02): item da
    Nord com 'data' de 80 dias atrás, coletado_em de agora (recém-
    inserido). A query de 'data velha' não pode incluir esse item -
    verificado indiretamente confirmando que a exclusão de casa está
    presente (mesmo teste de test_nord_excluida_da_query_de_data_velha,
    mas documentando o cenário real que motivou a correção)."""
    data_post_antiga = (datetime.now(timezone.utc) - timedelta(days=83)).strftime("%Y-%m-%d")
    coletado_em_agora = datetime.now(timezone.utc).isoformat()
    linha_nord = {
        "casa": "Nord Research", "titulo": "PETR4: resultado 2T26",
        "data": data_post_antiga, "coletado_em": coletado_em_agora,
    }
    chamadas = []
    cliente = _cliente_delete_capturando(chamadas)
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        store_mod.apagar_itens_antigos(dias=5)
    query_data_velha = chamadas[0]
    excecoes_casa = [v for (op, campo, v) in query_data_velha if op == "neq" and campo == "casa"]
    assert linha_nord["casa"] in excecoes_casa, (
        "item real da Nord (data 83 dias atrás, coletado_em agora) seria apagado "
        "pela query de 'data velha' sem a exceção de casa"
    )
