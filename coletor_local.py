# -*- coding: utf-8 -*-
"""Coleta de research standalone, pra rodar FORA do Streamlit Cloud (na
maquina local, via Agendador de Tarefas do Windows - passo a passo em
PROGRESSO.md, secao AÇÕES MANUAIS PENDENTES) quando uma fonte estiver
bloqueada la mas funcionar daqui.

Chama data.research.coletar_todas_disponiveis() (mesma logica de coleta
do app, sem o gate de 30min - faz sentido aqui porque quem decide a
frequencia e' o agendamento, nao o app) e roda a limpeza de itens com
mais de 5 dias (data.research.store.apagar_itens_antigos). Nao depende
do app rodando - so precisa do .streamlit/secrets.toml (Supabase) no
mesmo diretorio, igual o app usa.

Uso: python coletor_local.py (rodar com o python do .venv do projeto).
Saida: exit code 0 se todas as casas disponiveis coletaram OK, 1 se
alguma falhou (util pro Agendador de Tarefas registrar erro no historico
da tarefa sem precisar ler o log). Log tambem gravado em
coletor_local.log (raiz do projeto, ao lado deste arquivo) - roda "sem
abrir janela" no Agendador de Tarefas, entao stdout nao fica visivel em
lugar nenhum; o arquivo e' o unico jeito de conferir depois o que
aconteceu numa execucao passada. Rotaciona sozinho (1MB x 3 arquivos)
pra nao crescer sem limite com execucoes a cada 30min."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from data.research import coletar_todas_disponiveis
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

    return 1 if any(not info["ok"] for info in resultado.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
