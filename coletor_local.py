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

FASE 8 (2026-10-09): o universo passado pra coletar_eventos_universo e'
ROTACIONADO a cada execucao (ver _universo_rotativo) - bug real
encontrado na auditoria: ticker que nunca vira CONFIRMADO (ESTIMADO/
PRAZO_CVM nao tem atalho pra pular RI/NEWS) refaz a parte cara de rede
em TODA execucao; sem rotacionar o ponto de partida, so' os primeiros
~15-20 tickers da ordem fixa de config.IBOVESPA_SETORES.keys() jamais
recebiam esse orcamento, os do fim da lista nunca eram alcancados.

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
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import config
from data.coletores_status import registrar_tentativa
from data.eventos import salvar_snapshot_calendario
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


_JANELA_ROTACAO_S = 30 * 60  # mesmo intervalo do agendamento (Agendador de Tarefas roda a cada 30min)


def _universo_rotativo(tickers: list, agora: float = None) -> list:
    """Rotaciona o ponto de partida do universo a cada janela de 30min
    (mesmo intervalo do agendamento), sem precisar de nenhum estado
    persistido novo - so' usa o relogio.

    Bug real corrigido (2026-10-09, FASE 8): coletar_eventos_universo tem
    orcamento de tempo fixo (eventos_coleta._ORCAMENTO_TOTAL_S = 5min) e
    RI/NEWS por ticker sao caros (rede, ate' ~10-20s cada); a MAIORIA dos
    tickers do universo nunca chega a CONFIRMADO (RI so' le' a URL exata
    registrada na CVM, taxa de sucesso baixa por design - ver docstring
    de data/eventos_coleta.py) e fica so' em ESTIMADO/PRAZO_CVM, status
    que NAO tem o atalho que pula RI/NEWS (so' CONFIRMADO tem, ver
    coletar_evento). Sem rotacao, toda execucao comecava do MESMO
    ticker0 (list(config.IBOVESPA_SETORES.keys()), ordem fixa de dict) -
    os tickers do fim da lista que nunca virassem CONFIRMADO ficavam
    permanentemente fora do orcamento, igual ao bug ja corrigido pra
    tickers JA'-confirmados, so' um nivel acima (aqui e' estrutural, nao
    tem atalho possivel - ESTIMADO/PRAZO_CVM sempre tentam RI de novo).
    Rotacionar o ponto de partida garante que, ao longo de varias
    execucoes, TODO ticker eventualmente fica no inicio da lista e recebe
    seu orcamento de rede - nao so' os primeiros ~15-20 da ordem fixa."""
    if not tickers:
        return []
    agora = time.time() if agora is None else agora
    offset = int(agora // _JANELA_ROTACAO_S) % len(tickers)
    return tickers[offset:] + tickers[:offset]


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
    stats_eventos = coletar_eventos_universo(_universo_rotativo(list(config.IBOVESPA_SETORES.keys())))
    if stats_eventos["tabela_disponivel"] is False:
        logger.warning(
            "  eventos de resultado: tabela 'eventos_resultados' nao encontrada/inacessivel no "
            "Supabase - rode sql/eventos.sql no SQL Editor do projeto. Nenhum CONFIRMADO/ESTIMADO "
            "pode ser persistido nem lido pelo CALENDARIO ate isso ser feito."
        )
    elif stats_eventos["tabela_disponivel"] is None:
        logger.warning("  eventos de resultado: Supabase fora do ar (nao deu pra checar a tabela nem persistir nada)")
    logger.info(
        f"  eventos de resultado: {stats_eventos['processados']} ticker(s) processado(s), "
        f"{stats_eventos['confirmados']} confirmado(s) novo(s), {stats_eventos['estimados']} estimado(s) novo(s), "
        f"{stats_eventos['mantidos_prazo_cvm']} sem fonte melhor (prazo CVM)"
        + (" - tempo esgotado, proximo run continua" if stats_eventos["tempo_esgotado"] else "")
    )

    # snapshot do calendario (2026-10-05, ver data/eventos.py): grava o
    # calendario do universo INTEIRO pra UI so' ler (nunca recalcular ao
    # abrir/navegar). Reaproveita o MESMO agendamento deste script (ja
    # roda a cada 30min, seg-sex 07h-20h) - cobre de sobra os ~2x/dia
    # (08h/18h) pedidos, sem precisar de uma tarefa agendada nova.
    # Rodado DEPOIS do coletor de eventos acima, pra o snapshot refletir
    # qualquer CONFIRMADO/ESTIMADO achado agora mesmo nesta execucao.
    snapshot_ok = salvar_snapshot_calendario(list(config.IBOVESPA_SETORES.keys()))
    if snapshot_ok:
        logger.info("  snapshot do calendario: atualizado")
    else:
        logger.warning("  snapshot do calendario: mantido o anterior (calculo vazio ou Supabase indisponivel)")

    # registro de SAUDE DOS DADOS (ver data/saude_dados.py/coletores_status.py)
    # pra CALENDARIO - combina os 2 passos acima (coleta de eventos
    # RI/NEWS/PRAZO_CVM + persistencia do snapshot que a UI realmente le,
    # ver data/eventos.py:calcular_calendario_cacheado) porque nenhum dos
    # dois isolado representa "a UI vai mostrar o dado certo": a coleta
    # pode achar CONFIRMADO/ESTIMADO novo mas o snapshot falhar ao gravar
    # (ou vice-versa, sem nada novo mas o snapshot so' re-grava o mesmo
    # calculo). execucao_ok=True sempre aqui: o pipeline RI/NEWS roda por
    # ticker independente do Supabase estar de pe' (nunca lanca excecao,
    # ver coletar_eventos_universo) - so' a PERSISTENCIA depende do banco.
    _erros_calendario = []
    _persistencia_ok_calendario = True
    if stats_eventos["tabela_disponivel"] is False:
        _erros_calendario.append("tabela eventos_resultados ausente/inacessivel - rode sql/eventos.sql")
        _persistencia_ok_calendario = False
    elif stats_eventos["tabela_disponivel"] is None:
        _erros_calendario.append("Supabase indisponivel (eventos_resultados nao verificada)")
        _persistencia_ok_calendario = False
    if not snapshot_ok:
        _erros_calendario.append("snapshot do calendario nao atualizado (calculo vazio ou Supabase indisponivel)")
        _persistencia_ok_calendario = False
    registrar_tentativa(
        "CALENDARIO", "RI das empresas + NEWS + prazo CVM",
        execucao_ok=True, persistencia_ok=_persistencia_ok_calendario,
        registros_novos=stats_eventos["confirmados"] + stats_eventos["estimados"],
        erro="; ".join(_erros_calendario) or None,
        parcial=stats_eventos["tempo_esgotado"], categoria="Calendario",
    )

    return 1 if any(not info["ok"] for info in resultado.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
