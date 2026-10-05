# -*- coding: utf-8 -*-
"""Coleta de research standalone, pra rodar FORA do Streamlit Cloud (na
maquina local, via Agendador de Tarefas do Windows - passo a passo em
PROGRESSO.md, secao AÇÕES MANUAIS PENDENTES) quando uma fonte estiver
bloqueada la mas funcionar daqui.

Chama data.research.coletar_todas_disponiveis() (mesma logica de coleta
do app, sem o gate de 30min - faz sentido aqui porque quem decide a
frequencia e' o agendamento, nao o app) e roda a limpeza de itens com
mais de 5 dias (data.research.store.apagar_itens_antigos). Tambem
coleta o snapshot de recomendacoes/preco-alvo da Genial pro historico
nao-perecivel (data.research.historico.coletar_snapshot_genial,
2026-10-01) - mesma logica/motivo: bloqueado por WAF no Cloud, so'
funciona rodando daqui. Nao depende do app rodando - so precisa do
.streamlit/secrets.toml (Supabase) no mesmo diretorio, igual o app usa.

Tambem roda o coletor de datas REAIS de resultado (RI->NEWS->PRAZO_CVM,
data.eventos_coleta.coletar_eventos_universo, 2026-10-02) pro universo
de tickers de config.IBOVESPA_SETORES (mesmo universo que MERCADO/TOP
MERCADO ja usam) - decisao deliberada: este script roda fora de
qualquer sessao logada, entao nao tem acesso a watchlist de nenhum
usuario especifico (watchlist e' por usuario, em user_prefs); rodar pro
universo inteiro da cobertura igual pra qualquer um depois. Tem
orcamento proprio de tempo (5min, ver
data.eventos_coleta._ORCAMENTO_TOTAL_S) - como fontes de RI/NEWS sao
mais lentas que a coleta de research, pode nao terminar o universo
inteiro numa execucao so'; o proximo run (agendado a cada 30min)
continua cobrindo gradualmente (tickers ja' CONFIRMADOS nao regridem,
ver data.eventos_coleta.salvar_evento_se_mais_confiavel).

Uso: python coletor_local.py (rodar com o python do .venv do projeto) ou
pythonw coletor_local.py (mesma coisa, sem abrir janela de console - e' o
que o Agendador de Tarefas usa, ver PROGRESSO.md). Saida: exit code 0 se
todas as casas disponiveis coletaram OK, 1 se alguma falhou (util pro
Agendador de Tarefas registrar erro no historico da tarefa sem precisar
ler o log). Log gravado em coletor_local.log (raiz do projeto, ao lado
deste arquivo) - com pythonw nao tem console nenhum, entao o arquivo e' o
UNICO jeito de conferir depois o que aconteceu numa execucao passada.
Rotaciona sozinho (1MB x 3 arquivos) pra nao crescer sem limite com
execucoes a cada 30min.

Importante sobre pythonw: sem console, sys.stdout/sys.stderr podem vir
None (em vez de so' "sem terminal visivel") - um print() bater nisso
lança AttributeError e derruba o processo antes de chegar no log. Os
modulos de coleta (data/research/*.py) usam print() de proposito (pra
aparecer nos Logs do Streamlit Cloud quando rodam de la) - aqui, rodando
via pythonw, esses mesmos print()s precisam de um stdout/stderr que pelo
menos nao quebre. As duas linhas abaixo garantem isso ANTES de importar
qualquer coisa que possa chamar print()."""

import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = sys.stdout

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import config
from data.eventos_coleta import coletar_eventos_universo
from data.research import coletar_todas_disponiveis
from data.research.historico import coletar_snapshot_genial
from data.research.store import apagar_itens_antigos

_LOG_PATH = Path(__file__).parent / "coletor_local.log"

logger = logging.getLogger("coletor_local")
logger.setLevel(logging.INFO)
_formato = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

_handler_arquivo = RotatingFileHandler(_LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_handler_arquivo.setFormatter(_formato)
logger.addHandler(_handler_arquivo)

_handler_console = logging.StreamHandler(sys.stdout)
_handler_console.setFormatter(_formato)
logger.addHandler(_handler_console)

# streamlit e' importado indiretamente (varios modulos usam
# st.cache_data/st.cache_resource como decorator, mesmo fora de uma
# sessao Streamlit de verdade) e loga WARNING tipo "No runtime found,
# using MemoryCacheStorageManager" toda vez - inofensivo (e' exatamente
# o esperado rodando fora do app), mas polui o log/console a toa. Sobe o
# nivel minimo pra ERROR so' pro logger do streamlit, sem mexer no logger
# proprio deste script (logger acima continua em INFO).
logging.getLogger("streamlit").setLevel(logging.ERROR)


def main() -> int:
    logger.info("iniciando coleta local...")

    resultado = coletar_todas_disponiveis()
    if not resultado:
        logger.info("nenhuma casa disponivel pra coletar (ver CASAS em data/research/__init__.py)")

    for nome, info in resultado.items():
        status = "OK" if info["ok"] else "FALHOU"
        logger.info(f"  {nome}: {status} ({info['coletados']} itens)")

    removidos = apagar_itens_antigos()
    if removidos >= 0:
        logger.info(f"  limpeza: {removidos} item(ns) com mais de 5 dias removido(s)")
    else:
        logger.info("  limpeza: Supabase fora do ar, pulou")

    # historico de recomendacoes/preco-alvo da Genial (2026-10-01, ver
    # data/research/historico.py) - diferente de coletar_todas_disponiveis
    # (relatorios), isso busca obter_recomendacoes() da Genial e so' grava
    # um snapshot novo quando recomendacao/preco-alvo mudam de verdade.
    # Precisa rodar daqui (e nao so' no app ao vivo) pelo mesmo motivo que
    # a coleta de relatorios da Genial ja precisava: bloqueada por WAF no
    # Streamlit Cloud, so' funciona de uma maquina real (ver CASAS em
    # data/research/__init__.py, tentar_coleta_automatica=False).
    n_comparados, n_mudancas = coletar_snapshot_genial()
    if n_comparados == 0:
        logger.info("  historico de recomendacoes: fonte indisponivel (WAF/rede) ou nenhuma recomendacao retornada")
    else:
        logger.info(f"  historico de recomendacoes: {n_comparados} ticker(s) comparado(s), {n_mudancas} mudanca(s) real(is) registrada(s)")

    # datas reais de resultado (RI->NEWS->PRAZO_CVM, 2026-10-02) - ver
    # data/eventos_coleta.py. Orcamento proprio de tempo (5min), pode nao
    # cobrir o universo inteiro numa execucao so' (ver docstring do modulo).
    stats_eventos = coletar_eventos_universo(list(config.IBOVESPA_SETORES.keys()))
    logger.info(
        f"  eventos de resultado: {stats_eventos['processados']} ticker(s) processado(s), "
        f"{stats_eventos['confirmados']} confirmado(s) novo(s), {stats_eventos['estimados']} estimado(s) novo(s), "
        f"{stats_eventos['mantidos_prazo_cvm']} sem fonte melhor (prazo CVM)"
        + (" - tempo esgotado, proximo run continua" if stats_eventos["tempo_esgotado"] else "")
    )

    return 1 if any(not info["ok"] for info in resultado.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
