# -*- coding: utf-8 -*-
"""Status real de cobertura das casas de research (Fase 3 da missão
RESEARCH institucional, 2026-10-23) - camada de leitura pura, zero
coleta nova e zero tabela nova: combina o registro estático de `CASAS`
(data/research/__init__.py: método de acesso, se a coleta automática
está bloqueada no Cloud) com o status REAL já instrumentado em
`data/saude_dados.py` (categoria "Research", já existia desde a
auditoria de 2026-10-22 - este módulo só filtra e reaproveita).

Nunca infla cobertura: casa sem nenhuma evidência no painel de saúde
aparece como "Não comprovado" (mesmo vocabulário de saude_dados.py),
nunca como "funcionando" por omissão. Candidatas investigadas e NÃO
implementadas (Itaú BBA, Safra, Rico, Ágora, BB Investalk etc.) não
aparecem aqui - essa investigação já está documentada, com evidência
real via runner do GitHub Actions, em
docs/research-fontes-20261022.md (não duplicado aqui)."""

from data import saude_dados

from . import CASAS


def obter_status_casas() -> list:
    """Uma linha por casa em CASAS (ordem de cadastro), cada uma com o
    método de acesso, se a coleta automática roda no Cloud ou só via
    coletor_local.py, e o estado real mais recente do painel de saúde
    (categoria Research). Nunca lança exceção - casa sem correspondência
    no painel (não deveria acontecer, mas não é garantido por contrato)
    cai no mesmo estado conservador de "nunca avaliada"."""
    painel_research = {
        item["nome"]: item
        for item in saude_dados.obter_painel_saude()
        if item["categoria"] == "Research"
    }
    resultado = []
    for casa in CASAS:
        item_saude = painel_research.get(casa["nome"])
        status_bruto = (item_saude or {}).get("status_bruto") or {}
        resultado.append({
            "nome": casa["nome"],
            "fonte": casa.get("fonte", casa["nome"]),
            "coleta_automatica_cloud": bool(casa.get("tentar_coleta_automatica", True)),
            "codigo_estado": item_saude["codigo_estado"] if item_saude else "NAO_COMPROVADO",
            "rotulo_estado": item_saude["rotulo_estado"] if item_saude else saude_dados.ESTADOS["NAO_COMPROVADO"] + " (sem linha no painel de saúde)",
            "ultimo_sucesso_em": status_bruto.get("ultimo_sucesso_em"),
            "ultima_tentativa_em": status_bruto.get("ultima_tentativa_em"),
            "registros_novos_ultima_coleta": status_bruto.get("registros_novos"),
            "alerta": bool((item_saude or {}).get("alerta")),
        })
    return resultado
