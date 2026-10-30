# -*- coding: utf-8 -*-
"""Unico arquivo do projeto que importa data.x_signals direto (ver
docstring la' e tests/test_x_signals.py test_7b) - orquestra a coleta
do universo configurado (data/x_radar/__init__.py) respeitando o
orcamento de tempo/paginas, sempre delegando a decisao real de
disponibilidade pra x_signals.status_credencial()/buscar_sinais()
(nunca duplicada aqui)."""

from datetime import datetime, timedelta, timezone

from data import x_signals

TEMPO_MAX_COLETA_S = 25  # mesmo orcamento de data/research/base.py
MAX_RESULTADOS_POR_CICLO = 100
JANELA_DESDE_HORAS = 6  # nao busca posts mais antigos que isso por ciclo (coleta periodica, nao historico)


def coletar(*, tickers: list[str] | None = None, termos: list[str] | None = None,
            contas: list[str] | None = None) -> tuple[list, dict]:
    """Monta a query do universo configurado e delega pra
    x_signals.buscar_sinais(). Propaga NotImplementedError tal como
    recebido (quem chama, data/x_radar/__init__.py:executar_ciclo, ja'
    verifica status_credencial ANTES de chegar aqui - nunca deveria
    chegar aqui sem credencial valida, mas se chegar, nao mascara)."""
    from data.x_radar import montar_query

    query = montar_query(tickers=tickers, termos=termos, contas=contas)
    desde = datetime.now(timezone.utc) - timedelta(hours=JANELA_DESDE_HORAS)
    return x_signals.buscar_sinais(query, max_resultados=MAX_RESULTADOS_POR_CICLO, desde=desde)
