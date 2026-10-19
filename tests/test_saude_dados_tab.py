# -*- coding: utf-8 -*-
"""ui/saude_dados_tab.py não tinha nenhum teste automatizado antes desta
missão de redesign (2026-10-19) - cobre o resumo compacto novo (seção
3.6 do pedido: "resumo compacto com métricas reais"), que agrega a
MESMA classificação já usada por linha (_COR_POR_ESTADO), nunca uma
métrica nova/inventada."""
from unittest.mock import patch

import ui.saude_dados_tab as sd_tab


def _item(codigo_estado, nome="COLETOR X"):
    return {
        "nome": nome, "fonte": "fonte-x", "categoria": "CATEGORIA",
        "frequencia_esperada": "diária", "instrumentado": True,
        "codigo_estado": codigo_estado, "rotulo_estado": codigo_estado,
        "status_bruto": {}, "alerta": False, "desconhecido": False,
    }


def _render(painel, disponivel="ok"):
    blocos = []
    with patch.object(sd_tab.saude_dados, "obter_painel_saude", return_value=painel), \
         patch.object(sd_tab.saude_dados, "diagnostico_infraestrutura", return_value=disponivel), \
         patch.object(sd_tab.st, "markdown", side_effect=lambda t, **_k: blocos.append(t)), \
         patch.object(sd_tab.st, "button", return_value=False):
        sd_tab.render_saude_dados()
    return "\n".join(blocos)


def test_resumo_agrega_pela_mesma_classificacao_das_linhas():
    painel = [
        _item("SUCESSO_COM_NOVIDADE"), _item("SUCESSO_SEM_NOVIDADE"),
        _item("PARCIAL"), _item("FALHA_EXECUCAO"), _item("NAO_COMPROVADO"),
        _item("NUNCA_EXECUTADO"),
    ]
    saida = _render(painel)
    assert "2 SAUDÁVEIS" in saida
    assert "1 EM ATENÇÃO" in saida
    assert "1 EM FALHA" in saida
    assert "2 NÃO COMPROVADOS" in saida
    assert "6 coletores monitorados" in saida


def test_resumo_singular_com_1_coletor():
    saida = _render([_item("SUCESSO_COM_NOVIDADE")])
    assert "1 SAUDÁVEL" in saida and "SAUDÁVEIS" not in saida
    assert "1 coletor monitorado" in saida and "coletores" not in saida


def test_sem_coletores_nao_mostra_resumo_nem_quebra():
    saida = _render([])
    assert "SAUDÁVEL" not in saida and "monitorado" not in saida
