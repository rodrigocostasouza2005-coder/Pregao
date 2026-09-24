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
da tarefa sem precisar ler o log)."""

import sys
from datetime import datetime

from data.research import coletar_todas_disponiveis
from data.research.store import apagar_itens_antigos


def main() -> int:
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{agora}] iniciando coleta local...")

    resultado = coletar_todas_disponiveis()
    if not resultado:
        print("  nenhuma casa disponivel pra coletar (ver CASAS em data/research/__init__.py)")

    for nome, info in resultado.items():
        status = "OK" if info["ok"] else "FALHOU"
        print(f"  {nome}: {status} ({info['coletados']} itens)")

    removidos = apagar_itens_antigos()
    if removidos >= 0:
        print(f"  limpeza: {removidos} item(ns) com mais de 5 dias removido(s)")
    else:
        print("  limpeza: Supabase fora do ar, pulou")

    return 1 if any(not info["ok"] for info in resultado.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
