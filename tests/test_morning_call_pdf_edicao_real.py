# -*- coding: utf-8 -*-
"""Defeitos vistos no PDF gerado com dados reais em 22/10/2026 (runner do
GitHub Actions, sem IA): capa aberta por fonte fraca ("ACIA Araçatuba"),
coluna esquerda da capa vazia quando nenhuma matéria tem texto e manchetes
em inglês sem aviso no Mundo."""
import io
import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).parent))

import data.morning_call_editorial as ed  # noqa: E402
import jobs.morning_call_pdf as pdf_mod  # noqa: E402
import morning_call_amostras as amostras  # noqa: E402


def _fato(titulo, veiculo, importancia, confiavel):
    return {"titulo": titulo, "veiculo": veiculo, "importancia": importancia, "corpo": [],
            "fonte_confiavel": confiavel, "link": f"https://x.invalid/{importancia}"}


def test_capa_prefere_fonte_confiavel_a_importancia_pura():
    fraca = _fato("LJQQ3 sobe 5,9% enquanto Ibovespa cai", "ACIA Araçatuba", 0.99, False)
    forte = _fato("Ibovespa cai 1,2% com eleições e petróleo", "InfoMoney", 0.80, True)
    manchete, chamadas = ed.selecionar_manchete([fraca, forte])
    assert manchete is forte and chamadas == [fraca]


def test_tem_fonte_confiavel_olha_todos_os_veiculos_do_grupo():
    assert ed._tem_fonte_confiavel({"veiculos": ["Balada In", "Valor Econômico"]})
    assert not ed._tem_fonte_confiavel({"veiculos": ["Balada In", "Blog do Alberes Xavier"]})


def _texto_paginas(edicao):
    leitor = PdfReader(io.BytesIO(pdf_mod.gerar_pdf(edicao)))
    return [p.extract_text() for p in leitor.pages]


def test_capa_sem_texto_usa_a_coluna_esquerda_para_mais_manchetes():
    edicao = amostras.edicao_tipica()
    for chave, campo in (("brasil", "noticias"), ("exterior", "noticias"), ("empresas", "cards")):
        for item in (edicao.get(chave) or {}).get(campo) or []:
            item["corpo"] = []
    todos = (edicao["brasil"]["noticias"] or []) + (edicao["exterior"]["noticias"] or []) + edicao["empresas"]["cards"]
    manchete, chamadas = ed.selecionar_manchete(todos)
    edicao["capa"]["manchete"], edicao["capa"]["chamadas"] = manchete, chamadas
    capa = PdfReader(io.BytesIO(pdf_mod.gerar_pdf(edicao))).pages[0]
    limite_esq = pdf_mod.MARGEM_X + pdf_mod.LARGURA_UTIL * pdf_mod.LARGURA_ESQ_CAPA
    a_esquerda = []

    def _visitor(texto, cm, tm, _fd, _fs):
        x = cm[4] + tm[4] * cm[0]  # texto dos frames vem deslocado pela matriz cm
        if texto.strip() and x < limite_esq - 5:
            a_esquerda.append(texto)

    capa.extract_text(visitor_text=_visitor)
    esquerda = " ".join(" ".join(a_esquerda).split())
    na_esquerda = [c for c in chamadas[2:] if " ".join(c["titulo"].split()[:3]) in esquerda]
    assert na_esquerda, "nenhuma chamada na coluna esquerda da capa"


def test_mundo_avisa_manchete_sem_traducao():
    edicao = amostras.edicao_tipica()
    edicao["exterior"]["noticias"][0]["sem_traducao"] = True
    texto = "\n".join(_texto_paginas(edicao))
    assert "idioma original: a tradução não estava disponível" in texto


def test_agenda_proximos_dias_so_com_data_anunciada():
    from datetime import date, datetime
    from unittest.mock import patch
    from zoneinfo import ZoneInfo

    eventos = [
        {"ticker": "WEGE3", "empresa": "WEG", "data": date(2026, 10, 23), "status": "CONFIRMADO",
         "tipo_evento": "RESULTADO", "periodo": "3T26"},
        {"ticker": "PETR4", "empresa": "Petrobras", "data": date(2026, 10, 27), "status": "ESTIMADO",
         "tipo_evento": "RESULTADO", "periodo": "3T26"},
        {"ticker": "VALE3", "empresa": "Vale", "data": date(2026, 10, 24), "status": "PRAZO_CVM",
         "tipo_evento": "RESULTADO", "periodo": "3T26"},
        {"ticker": "ITUB4", "empresa": "Itaú", "data": date(2026, 11, 20), "status": "CONFIRMADO",
         "tipo_evento": "RESULTADO", "periodo": "3T26"},
    ]
    agora = datetime(2026, 10, 22, 8, 3, tzinfo=ZoneInfo("America/Sao_Paulo"))
    with patch.object(ed, "calcular_calendario_cacheado", return_value=eventos):
        proximos = ed._agenda_proximos(agora)
    assert [e["ticker"] for e in proximos] == ["WEGE3", "PETR4"]  # sem prazo CVM e sem além de 7 dias

    edicao = amostras.edicao_tipica()
    edicao["empresas"]["agenda_proximos"] = proximos
    texto = " ".join("\n".join(_texto_paginas(edicao)).split())
    assert "PRÓXIMOS DIAS" in texto and "sex 23/10" in texto and "ter 27/10" in texto


def test_noticia_e_apresentada_pelo_veiculo_confiavel_do_grupo():
    """Grupo real de 22/10: "veiculos" em ordem alfabética punha "Acia
    Araçatuba" na capa; o grupo também tinha InfoMoney."""
    item = {"titulo": "LJQQ3 sobe 5,9% enquanto Ibovespa cai 1,1% na B3 hoje", "link": "https://acia.invalid/1",
            "veiculos": ["Acia Araçatuba", "InfoMoney"],
            "fontes": [{"veiculo": "Acia Araçatuba", "link": "https://acia.invalid/1"},
                       {"veiculo": "InfoMoney", "link": "https://www.infomoney.com.br/x"}],
            "titulos": ["LJQQ3 sobe 5,9% enquanto Ibovespa cai 1,1% na B3 hoje",
                        "Ibovespa cai 1,1% com eleições; Lojas Quero-Quero dispara"],
            "importancia": 9}
    preferido = ed._com_fonte_preferida(item)
    fato = ed._item_fato(preferido)
    assert fato["veiculo"] == "InfoMoney" and fato["link"] == "https://www.infomoney.com.br/x"
    assert fato["titulo"] == "Ibovespa cai 1,1% com eleições; Lojas Quero-Quero dispara"
    assert preferido["link"] == item["link"]  # chave do grupo (cache de resumo/tradução) intacta
    sem_confiavel = {**item, "fontes": item["fontes"][:1], "titulos": item["titulos"][:1], "veiculos": ["Acia Araçatuba"]}
    assert ed._com_fonte_preferida(sem_confiavel) is sem_confiavel
