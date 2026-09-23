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
  passo). Nenhuma delas guarda credenciais nem tenta contornar login."""

from . import genial

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


def obter_relatorios_unificado(casas_ativas=None):
    """Agrega relatorios de todas as casas ativas (por id). Retorna
    (relatorios, casas_com_falha) - casas_com_falha e' lista de nomes
    cuja coleta falhou ou nao esta disponivel nesta versao."""
    if casas_ativas is None:
        casas_ativas = [c["id"] for c in CASAS if c["ativa_por_padrao"]]

    relatorios = []
    falhas = []
    for casa in CASAS:
        if casa["id"] not in casas_ativas:
            continue
        if not casa["disponivel"]:
            motivo = casa.get("motivo_indisponivel", "indisponível")
            falhas.append(f"{casa['nome']} ({motivo})")
            continue
        resultado = casa["obter_relatorios"]()
        if resultado is None:
            falhas.append(casa["nome"])
        else:
            relatorios.extend(resultado)
    return relatorios, falhas
