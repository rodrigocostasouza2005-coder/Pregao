# -*- coding: utf-8 -*-
"""Registro das casas de research: um coletor por casa, todos no mesmo
formato (casa, titulo, data, autor, tipo, setor, tickers, link).

Pra ligar/desligar uma casa (por padrao ou por usuario, via prefs), mexa
so nessa lista - a UI (ui/research_tab.py) le CASAS pra montar o filtro.

Verificado na pratica (data desta implementacao) quais casas de research
tem conteudo publico coletavel sem login:
- Genial Analisa: publica, coletavel (JSON __NEXT_DATA__ da home).
- BTG Research: API interna identificada mas bloqueada por bot-detection
  (Akamai) - ver genial.py/relatorio da tarefa pros detalhes tecnicos.
- XP, Itau BBA, BB Investimentos, Santander, Safra, Agora/Bradesco,
  Inter: nao entraram nesta versao (robots.txt permite em varias delas,
  mas ou o conteudo publico e' raso/generico - caso da XP - ou nao foi
  possivel confirmar a pagina/API certa de research dentro do tempo desta
  tarefa - casos de Itau BBA e Agora, os mais promissores pra um proximo
  passo). Nenhuma delas guarda credenciais nem tenta contornar login.

Os itens coletados sao persistidos no Supabase (tabela research_itens,
ver data/research/store.py) - a aba RESEARCH sempre le do banco, nunca
direto da fonte; a coleta (fonte -> banco) roda no maximo a cada 30min
por casa (store.precisa_recoletar)."""

from . import genial, store

CASAS = [
    {
        "id": "genial",
        "nome": "Genial Analisa",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": genial.obter_relatorios,
    },
    {
        "id": "btg",
        "nome": "BTG Research",
        "ativa_por_padrao": False,
        "disponivel": False,
        "obter_relatorios": None,
        "motivo_indisponivel": (
            "API interna identificada, mas bloqueada por bot-detection (Akamai) - "
            "precisa de navegador real (Playwright/Chromium) pra passar do desafio JS."
        ),
    },
]


def coletar_casa(casa: dict) -> tuple[int, bool]:
    """Busca relatorios de uma casa na fonte real e grava no Supabase
    (upsert por link, coletado_em=agora). Retorna (n_itens, ok) - ok=False
    se a fonte ou o Supabase falharem. Funcao separada (nao inline em
    obter_relatorios_unificado) pra poder ser chamada tambem por um job
    agendado no futuro (GitHub Actions, fase opcional do roadmap), sem
    depender da UI nem do gate de 30min - so import data.research e chama
    coletar_casa(casa) ou coletar_todas_disponiveis() direto."""
    itens = casa["obter_relatorios"]()
    if itens is None:
        return 0, False
    return len(itens), store.salvar_itens(itens)


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


def obter_relatorios_unificado(casas_ativas=None):
    """Le os itens de research salvos no Supabase, das casas ativas (por
    id). Antes de ler, garante que cada casa foi coletada ha no maximo
    30min (store.precisa_recoletar) - se nao, chama coletar_casa() pra
    essa casa antes de ler. A leitura em si sempre vem do banco, nunca
    direto da fonte. Retorna (relatorios, falhas) - falhas: casas
    indisponiveis ou cuja coleta/leitura deu erro."""
    if casas_ativas is None:
        casas_ativas = [c["id"] for c in CASAS if c["ativa_por_padrao"]]

    falhas = []
    nomes_para_ler = []
    for casa in CASAS:
        if casa["id"] not in casas_ativas:
            continue
        if not casa["disponivel"]:
            falhas.append(f"{casa['nome']} ({casa.get('motivo_indisponivel', 'indisponível')})")
            continue
        nomes_para_ler.append(casa["nome"])
        if store.precisa_recoletar(casa["nome"]):
            _, ok = coletar_casa(casa)
            if not ok:
                falhas.append(casa["nome"])

    if not nomes_para_ler:
        return [], falhas

    relatorios = store.listar_itens(nomes_para_ler)
    if relatorios is None:
        falhas.append("Supabase (leitura do research)")
        return [], falhas
    return relatorios, falhas
