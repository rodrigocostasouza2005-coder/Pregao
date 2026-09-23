# -*- coding: utf-8 -*-
"""Registro das casas de research: um coletor por casa, todos no mesmo
formato (casa, titulo, data, autor, tipo, setor, tickers, link).

Pra ligar/desligar uma casa (por padrao ou por usuario, via prefs), mexa
so nessa lista - a UI (ui/research_tab.py) le CASAS pra montar o filtro.

Verificado na pratica quais casas de research tem conteudo publico
coletavel sem login:
- Genial Analisa: publica, coletavel (JSON __NEXT_DATA__ da home).
- XP Investimentos: publica, coletavel (API do WordPress, wp-json/wp/v2 -
  ver xp.py). IP deste sandbox de dev bloqueado pelo CDN da XP, coletor
  escrito a partir da estrutura confirmada pelo Rodrigo no navegador, sem
  teste ao vivo aqui - por isso comeca com ativa_por_padrao=False.
- BTG Research: API interna identificada mas bloqueada por bot-detection
  (Akamai) - ver genial.py/relatorio da tarefa pros detalhes tecnicos.
- Itau BBA, BB Investimentos, Santander, Safra, Agora/Bradesco, Inter:
  ainda nao investigadas (ver BACKLOG.md).

Os itens coletados sao persistidos no Supabase (tabela research_itens,
ver data/research/store.py) - a aba RESEARCH sempre le do banco primeiro
(preparar_leitura, rapido) e so depois dispara coleta pras casas
desatualizadas (coletar_pendentes, com timeout por requisicao e orcamento
total de tempo - ver data/research/base.py); a coleta roda no maximo a
cada 30min por casa (store.precisa_recoletar)."""

import time

from . import genial, store, xp
from .base import TEMPO_MAX_COLETA_S

CASAS = [
    {
        "id": "genial",
        "nome": "Genial Analisa",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": genial.obter_relatorios,
        "extrator_texto": None,  # generico (baixa a pagina publica do relatorio)
    },
    {
        "id": "xp",
        "nome": "XP Investimentos",
        "ativa_por_padrao": False,  # nao testado ao vivo neste ambiente, ver xp.py
        "disponivel": True,
        "obter_relatorios": xp.obter_relatorios,
        "extrator_texto": xp.obter_texto_aberto,  # nunca baixa a pagina publica (paywall)
    },
    {
        "id": "btg",
        "nome": "BTG Research",
        "ativa_por_padrao": False,
        "disponivel": False,
        "obter_relatorios": None,
        "extrator_texto": None,
        "motivo_indisponivel": (
            "API interna identificada, mas bloqueada por bot-detection (Akamai) - "
            "precisa de navegador real (Playwright/Chromium) pra passar do desafio JS."
        ),
    },
]


def coletar_casa(casa: dict) -> tuple[int, bool]:
    """Busca relatorios de uma casa na fonte real e grava no Supabase
    (upsert por link, coletado_em=agora). Retorna (n_itens, ok) - ok=False
    se a fonte ou o Supabase falharem. Funcao separada (nao inline no
    fluxo de leitura da UI) pra poder ser chamada tambem por um job
    agendado no futuro (GitHub Actions, fase opcional do roadmap), sem
    depender da UI nem do gate de 30min - so import data.research e chama
    coletar_casa(casa) ou coletar_todas_disponiveis() direto.

    Print() de proposito (nao logging): Streamlit Cloud captura stdout no
    painel de Logs - da pra conferir dali se a fonte esta respondendo a
    partir do servidor do Cloud (pode se comportar diferente do ambiente
    local, ex: bloqueio de WAF por IP/regiao)."""
    inicio = time.monotonic()
    itens = casa["obter_relatorios"]()
    duracao = time.monotonic() - inicio
    if itens is None:
        print(f"[research] coleta {casa['nome']} falhou apos {duracao:.1f}s")
        return 0, False
    ok = store.salvar_itens(itens)
    print(f"[research] coleta {casa['nome']}: {len(itens)} itens em {duracao:.1f}s (salvou={ok})")
    return len(itens), ok


def coletar_todas_disponiveis() -> dict:
    """Coleta (sem gate de tempo) todas as casas marcadas como disponiveis.
    Pensada pra ser chamada por um job agendado, nao pelo app ao vivo (o
    app usa obter_relatorios_unificado, que respeita o gate de 30min).
    Retorna {nome_da_casa: {'coletados': N, 'ok': bool}}."""
    resultado = {}
    for casa in CASAS:
        if not casa["disponivel"]:
            continue
        coletados, ok = coletar_casa(casa)
        resultado[casa["nome"]] = {"coletados": coletados, "ok": ok}
    return resultado


def preparar_leitura(casas_ativas=None):
    """So a leitura do que ja esta salvo no Supabase (rapida, sem tocar em
    nenhuma fonte externa) - pensada pra UI desenhar a tela imediatamente
    com isso antes de tentar coletar algo novo. Retorna (relatorios,
    falhas, casas_para_coletar, nomes_para_ler):
    - falhas: casas indisponiveis ou erro de leitura do banco;
    - casas_para_coletar: casas ativas+disponiveis cuja ultima coleta
      salva tem mais de 30min (store.precisa_recoletar) - quem chama
      decide se/quando coletar (ver coletar_pendentes);
    - nomes_para_ler: nomes de casa usados pra reler o banco depois de
      coletar (ver ler_itens_salvos)."""
    if casas_ativas is None:
        casas_ativas = [c["id"] for c in CASAS if c["ativa_por_padrao"]]

    falhas = []
    nomes_para_ler = []
    casas_para_coletar = []
    for casa in CASAS:
        if casa["id"] not in casas_ativas:
            continue
        if not casa["disponivel"]:
            falhas.append(f"{casa['nome']} ({casa.get('motivo_indisponivel', 'indisponível')})")
            continue
        nomes_para_ler.append(casa["nome"])
        if store.precisa_recoletar(casa["nome"]):
            casas_para_coletar.append(casa)

    if not nomes_para_ler:
        return [], falhas, casas_para_coletar, nomes_para_ler

    relatorios = store.listar_itens(nomes_para_ler)
    if relatorios is None:
        falhas.append("Supabase (leitura do research)")
        return [], falhas, casas_para_coletar, nomes_para_ler
    return relatorios, falhas, casas_para_coletar, nomes_para_ler


def ler_itens_salvos(nomes: list):
    """So a leitura do banco (sem gate nem coleta) - usado pra reler apos
    coletar_pendentes(). None se o banco estiver fora do ar."""
    return store.listar_itens(nomes)


def coletar_pendentes(casas: list) -> list:
    """Coleta uma lista de casas (ja filtradas como pendentes por
    preparar_leitura), respeitando um orcamento total de tempo
    (base.TEMPO_MAX_COLETA_S) - se estourar, para e deixa o resto pra
    proxima chamada (a casa nao coletada continua 'pendente' porque seu
    coletado_em nao foi atualizado). Retorna as falhas (nomes de casa que
    nao atualizaram, por erro ou tempo esgotado)."""
    falhas = []
    limite = time.monotonic() + TEMPO_MAX_COLETA_S
    for casa in casas:
        if time.monotonic() > limite:
            falhas.append(f"{casa['nome']} (tempo esgotado)")
            continue
        _, ok = coletar_casa(casa)
        if not ok:
            falhas.append(casa["nome"])
    return falhas
