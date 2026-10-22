# -*- coding: utf-8 -*-
"""Seleção editorial do Morning Call portada do PR #81 (casos reais das
edições de 18 e 19/10/2026): editoria pelo assunto do título, Empresas só
com a empresa no próprio título, opinião/serviço fora de pauta e piso de
relevância financeira no PDF."""
from datetime import datetime
from zoneinfo import ZoneInfo

import data.morning_call_editorial as ed

TZ_SP = ZoneInfo("America/Sao_Paulo")


def test_editoria_pelo_assunto_do_titulo():
    assert ed.editoria_por_assunto("Déficit orçamentário dos EUA se aproxima de US$ 2 trilhões", "BR") == "INT"
    assert ed.editoria_por_assunto("Bitcoin se estabiliza após Warsh, do Fed", "BR") == "INT"
    assert ed.editoria_por_assunto("Brazil's central bank holds Selic", "INT") == "BR"
    # marcador dos dois lados: fica na editoria da coleta
    assert ed.editoria_por_assunto("Lula e Trump discutem tarifas", "BR") == "BR"
    # "irá" (verbo) não é o Irã
    assert ed.editoria_por_assunto("Dólar irá subir com fiscal, dizem gestores", "BR") == "BR"


def test_empresa_so_com_a_empresa_no_proprio_titulo():
    assert ed.e_noticia_de_empresa("PETR4 sobe 2% após anúncio de dividendos")
    assert not ed.e_noticia_de_empresa("Ibovespa reage com Petrobras e bancos")
    assert not ed.e_noticia_de_empresa("Plano econômico de Flávio pode garantir equilíbrio fiscal")


def test_opiniao_carta_e_servico_ficam_fora_de_pauta():
    assert ed._fora_de_pauta("O Estelionato Eleitoral e a Irresponsabilidade Fiscal do Governo Lula")
    assert ed._fora_de_pauta("Opinião: o Copom errou")
    assert ed._fora_de_pauta("‘Some people did everything right’: I lost my home in the Great Recession")
    assert ed._fora_de_pauta("Tesouro Selic, Tesouro Reserva ou CDB: qual rende mais R$ 10 mil?")
    assert not ed._fora_de_pauta("Haddad anuncia corte de gastos de R$ 15 bilhões")


def test_piso_de_relevancia_financeira():
    assert not ed.tem_relevancia_financeira({"titulo": "Saiba como emitir a Certidão Única de Débitos"})
    assert not ed.tem_relevancia_financeira({"titulo": "Lula desafia Flávio a abrir sigilos bancário, telefônico e fiscal"})
    assert ed.tem_relevancia_financeira({"titulo": "Saiba como fica o IR com a reforma tributária"})
    assert ed.tem_relevancia_financeira({"titulo": "Haddad anuncia corte de gastos e déficit menor"})


def test_filtro_do_pdf_aplica_o_piso_e_o_do_email_nao():
    agora = datetime(2026, 10, 19, 7, tzinfo=TZ_SP)
    itens = [{"titulo": "Saiba como emitir a Certidão Única de Débitos", "data": "2026-10-18T09:00:00-03:00",
              "importancia": 5}]
    assert ed.filtrar_noticias(itens, agora, exigir_relevancia=True) == []
    assert len(ed.filtrar_noticias(itens, agora)) == 1
