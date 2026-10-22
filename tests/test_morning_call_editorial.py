# -*- coding: utf-8 -*-
"""Cobertura de data/morning_call_editorial.py - camada de dado pura
(dict) que alimenta jobs/morning_call_pdf.py. Sem rede real: cada
provedor é mockado no nível de função, igual a tests/test_morning_call.py."""
from datetime import date, datetime, timezone
from unittest.mock import patch

import pandas as pd

import data.morning_call_editorial as ed

TZ_SP = ed.TZ_SP

_COT_OK = {"erro": None, "preco": 128_432.0, "variacao_pct": 1.23, "_barra_em": "2026-10-14T10:00:00-03:00"}
_COT_ERRO = {"erro": "sem dado"}


def _sem_rede(**overrides):
    base = dict(
        obter_cotacao_indice=lambda *_a, **_k: dict(_COT_ERRO),
        obter_historico=lambda *_a, **_k: None,
        obter_selic_meta=lambda: None,
        obter_selic_meta_copom=lambda: None,
        obter_cdi=lambda: None,
        obter_focus_ipca=lambda: None,
        obter_focus_selic=lambda: None,
        obter_top_mercado=lambda *_a: [],
        obter_top_mercado_internacional=lambda *_a: [],
        calcular_calendario_cacheado=lambda *_a, **_k: [],
        obter_resumos_prontos=lambda *_a, **_k: {},
        # camadas 2 e 3 de _resumos_para_edicao: sem Supabase e sem IA nos
        # testes que não tratam disso
        obter_resumos_news_por_link=lambda *_a, **_k: {},
        obter_resumo_grupo=lambda *_a, **_k: {"resumo": None},
        _noticias_do_setor=lambda _setor: [],
    )
    base.update(overrides)
    return base


def _pools(noticias, data="2026-10-14T06:30:00-03:00"):
    """Separa notícias de teste nos dois pools reais (BR / INT), com data
    dentro da janela da edição quando o item não traz uma."""
    itens = [{"data": data, **n} for n in noticias]
    return dict(obter_top_mercado=lambda setor="TODOS": [n for n in itens if n.get("regiao") == "BR"]
                if setor == "TODOS" else [],
                obter_top_mercado_internacional=lambda *_a: [n for n in itens if n.get("regiao") != "BR"])


class _MultiPatch:
    def __init__(self, **overrides):
        self._patches = [patch.object(ed, nome, fn) for nome, fn in _sem_rede(**overrides).items()]

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()


def test_manchetes_em_ingles_sao_traduzidas_no_pdf_sem_perder_link():
    from data import news as news_mod

    noticia = {
        "titulo": "Fed signals interest rate cuts as inflation cools",
        "link": "https://example.com/fed-story",
    }
    resposta = "1. Fed sinaliza cortes de juros com desaceleração da inflação"
    with patch.object(news_mod, "_chamar_groq", return_value=(resposta, None)):
        traduzido = news_mod.traduzir_manchetes_pdf([noticia])
    assert traduzido["https://example.com/fed-story"] == (
        "Fed sinaliza cortes de juros com desaceleração da inflação"
    )


def test_manchete_internacional_curta_sem_acentos_e_identificada():
    from data import news as news_mod

    noticia = {
        "titulo": "US inflation accelerates in September",
        "link": "https://example.com/inflation",
    }
    resposta = "1. A inflação dos EUA acelera em setembro"
    with patch.object(news_mod, "_chamar_groq", return_value=(resposta, None)) as chamada:
        traduzido = news_mod.traduzir_manchetes_pdf([noticia])
    chamada.assert_called_once()
    assert traduzido["https://example.com/inflation"] == "A inflação dos EUA acelera em setembro"


def test_falha_de_traducao_nao_apaga_manchete_original():
    from data import news as news_mod

    noticia = {
        "titulo": "Fed signals interest rate cuts as inflation cools",
        "link": "https://example.com/fed-story",
    }
    with patch.object(news_mod, "_chamar_groq", return_value=(None, "cota")):
        traduzido = news_mod.traduzir_manchetes_pdf([noticia])
    assert traduzido == {}



def test_paragrafo_de_resumo_em_ingles_e_traduzido_sem_perder_identificador():
    from data import news as news_mod

    texto = "The company reported revenue growth of 12% in the third quarter."
    resposta = "1. A empresa reportou crescimento da receita de 12% no terceiro trimestre."
    with patch.object(news_mod, "_chamar_groq", return_value=(resposta, None)):
        traduzido = news_mod.traduzir_paragrafos_pdf([
            {"link": "https://example.com/story", "indice": 0, "texto": texto}
        ])
    assert traduzido[("https://example.com/story", 0)].startswith("A empresa reportou")
    assert "12%" in traduzido[("https://example.com/story", 0)]


def test_paragrafos_ja_em_portugues_nao_disparam_traducao():
    from data import news as news_mod

    with patch.object(news_mod, "_chamar_groq") as chamada:
        assert news_mod.traduzir_paragrafos_pdf([
            {"link": "https://example.com/story", "indice": 0,
             "texto": "A empresa reportou crescimento da receita de 12% no terceiro trimestre."}
        ]) == {}
    chamada.assert_not_called()


def test_manchetes_em_portugues_nao_disparam_chamada_de_traducao():
    from data import news as news_mod

    noticia = {
        "titulo": "Banco Central mantém a taxa Selic em decisão do Copom",
        "link": "https://example.com/copom",
    }
    with patch.object(news_mod, "_chamar_groq") as chamada:
        assert news_mod.traduzir_manchetes_pdf([noticia]) == {}
    chamada.assert_not_called()



def test_montar_edicao_aplica_traducao_a_manchete_e_resumo_em_ingles():
    noticia = {
        "titulo": "Fed signals interest rate cuts as inflation cools",
        "link": "https://example.com/fed-story",
        "regiao": "INT",
        "veiculos": ["Reuters"],
        "importancia": 10,
    }
    resumo = "RESUMO:\\nThe company reported revenue growth of 12% in the third quarter."
    traducoes = {
        "https://example.com/fed-story": "Fed sinaliza cortes de juros com inflação mais baixa"
    }
    paragrafos_pt = {
        ("https://example.com/fed-story", 0):
            "A empresa reportou crescimento da receita de 12% no terceiro trimestre."
    }
    overrides = {
        **_pools([noticia]),
        "obter_resumos_prontos": lambda _grupos: {
            "https://example.com/fed-story": {"resumo": resumo}
        },
        "traduzir_manchetes_pdf": lambda _itens: traducoes,
        "traduzir_paragrafos_pdf": lambda _textos: paragrafos_pt,
    }
    with _MultiPatch(**overrides):
        edicao = ed.montar_edicao(datetime(2026, 10, 14, 8, 0, tzinfo=TZ_SP))
    fato = edicao["exterior"]["noticias"][0]
    assert fato["titulo"] == traducoes["https://example.com/fed-story"]
    assert fato["link"] == "https://example.com/fed-story"
    assert fato["corpo"] == [paragrafos_pt[("https://example.com/fed-story", 0)]]


def test_brt_label_converte_fuso_de_origem_pra_horario_de_brasilia():
    # 14:30 em Nova York (UTC-4, horário de verão) -> 15:30 em Brasília (UTC-3).
    assert ed.brt_label("2026-10-14T14:30:00-04:00") == "14/10 15:30 (horário de Brasília)"


def test_brt_label_sem_valor_diz_indisponivel():
    assert ed.brt_label(None) == "indisponível"
    assert ed.brt_label("") == "indisponível"


def test_indicador_com_erro_nunca_inventa_preco():
    with _MultiPatch(obter_cotacao_indice=lambda *_a, **_k: dict(_COT_ERRO)):
        info = ed._indicador("Ibovespa", "^BVSP")
    assert info["preco"] is None
    assert info["erro"] == "sem dado"


def test_referencia_usa_horario_do_ultimo_negocio_em_brasilia():
    """Regressão: a barra diária do Yahoo fica à meia-noite do fuso da
    bolsa e virava '16/10 00:00' / '16/10 01:00' no PDF."""
    cot = {**_COT_OK, "_barra_em": "2026-10-16T00:00:00-04:00", "_negocio_em": "2026-10-16T16:59:58-04:00"}
    with _MultiPatch(obter_cotacao_indice=lambda *_a, **_k: cot):
        info = ed._indicador("S&P 500 futuro", "ES=F")
    assert info["barra_fmt"] == "16/10 17:59 (horário de Brasília)"
    assert info["sessao"] == date(2026, 10, 16)


def test_referencia_sem_horario_de_negocio_mostra_so_a_sessao():
    cot = {**_COT_OK, "_barra_em": "2026-10-16T00:00:00-04:00"}
    with _MultiPatch(obter_cotacao_indice=lambda *_a, **_k: cot):
        info = ed._indicador("Ouro", "GC=F")
    assert info["barra_fmt"] == "fech. 16/10"
    assert "00:00" not in info["barra_fmt"] and "01:00" not in info["barra_fmt"]


def test_nota_de_sessao_no_fim_de_semana():
    indicadores = [{"sessao": date(2026, 10, 16)}, {"sessao": date(2026, 10, 15)}, {"sessao": None}]
    nota = ed.nota_sessao(indicadores, datetime(2026, 10, 18, 12, tzinfo=TZ_SP))
    assert "sexta-feira, 16/10" in nota and "fim de semana" in nota
    assert ed.nota_sessao([{"sessao": date(2026, 10, 19)}], datetime(2026, 10, 19, 11, tzinfo=TZ_SP)) is None


def test_indicador_ok_reaproveita_mesmo_dado_do_provedor():
    with _MultiPatch(obter_cotacao_indice=lambda *_a, **_k: dict(_COT_OK)):
        info = ed._indicador("Ibovespa", "^BVSP")
    assert info["preco"] == 128_432.0
    assert info["variacao_pct"] == 1.23
    assert info["erro"] is None


def test_serie_fechamento_vazia_quando_historico_indisponivel():
    with _MultiPatch(obter_historico=lambda *_a, **_k: None):
        assert ed._serie_fechamento("^BVSP") == []


def test_serie_fechamento_le_data_e_close_do_historico():
    df = pd.DataFrame({
        "Data": pd.to_datetime(["2026-10-13", "2026-10-14"]),
        "Close": [127_000.0, 128_432.0],
    })
    with _MultiPatch(obter_historico=lambda *_a, **_k: df):
        serie = ed._serie_fechamento("^BVSP")
    assert len(serie) == 2
    assert serie[-1][1] == 128_432.0


def test_macro_rows_focus_do_ano_corrente_e_seguinte_com_data_do_boletim():
    """Regressão da edição de 18/10/2026: o PDF mostrava a linha de 2028
    (iloc[-1]) com o texto cru 'mediana pct: ...; media pct: ...; numero
    respondentes: ...'. Agora: ano corrente e seguinte, valor numérico +
    unidade, boletim na referência e respondentes no detalhe."""
    focus_ipca = pd.DataFrame({
        "ano_referencia": [2026, 2027, 2028],
        "mediana_pct": [5.2245, 4.30, 3.79],
        "media_pct": [5.25, 4.35, 3.80],
        "numero_respondentes": [144, 140, 120],
        "data_calculo": pd.to_datetime(["2026-10-09"] * 3).tz_localize(TZ_SP),
    })
    agora = datetime(2026, 10, 19, 8, tzinfo=TZ_SP)
    with _MultiPatch(obter_focus_ipca=lambda: focus_ipca):
        linhas = ed._macro_rows(agora)
    por_nome = {l["indicador"]: l for l in linhas}
    assert por_nome["Focus IPCA 2026"]["valor"] == 5.2245
    assert por_nome["Focus IPCA 2026"]["unidade"] == "%"
    assert por_nome["Focus IPCA 2026"]["referencia"] == "boletim 09/10/2026"
    assert por_nome["Focus IPCA 2026"]["detalhe"] == "144 respondentes"
    assert por_nome["Focus IPCA 2027"]["valor"] == 4.30
    assert "Focus IPCA 2028" not in por_nome
    texto = repr(linhas)
    assert "mediana pct" not in texto and "media pct" not in texto and "numero respondentes" not in texto


def test_macro_rows_selic_e_cdi_com_colunas_reais():
    selic = pd.DataFrame({"data": pd.to_datetime(["2026-10-15", "2026-10-16"]).tz_localize(TZ_SP),
                          "selic_meta_pct": [15.0, 15.0]})
    cdi = pd.DataFrame({"data": pd.to_datetime(["2026-10-16"]).tz_localize(TZ_SP),
                        "cdi_diario_pct": [0.055131], "cdi_anualizado_pct": [14.90]})
    with _MultiPatch(obter_selic_meta=lambda: selic, obter_cdi=lambda: cdi):
        linhas = ed._macro_rows(datetime(2026, 10, 19, 8, tzinfo=TZ_SP))
    por_nome = {l["indicador"]: l for l in linhas}
    assert por_nome["Selic meta"]["valor"] == 15.0
    assert por_nome["Selic meta"]["referencia"] == "16/10/2026"
    assert por_nome["CDI"]["valor"] == 14.90
    assert por_nome["CDI"]["unidade"] == "% a.a."


def test_macro_rows_indisponivel_com_motivo_quando_provedor_falha():
    with _MultiPatch(obter_selic_meta=lambda: (_ for _ in ()).throw(RuntimeError("fora do ar"))):
        linhas = ed._macro_rows()
    linha_selic = next(l for l in linhas if l["indicador"] == "Selic meta")
    assert linha_selic["valor"] is None
    assert "fora do ar" in linha_selic["erro"]


def test_macro_rows_usa_motivo_registrado_pelo_sgs():
    with _MultiPatch(motivo_indisponivel=lambda chave: "SGS 432: página de erro HTML" if chave == "selic" else None):
        linhas = ed._macro_rows()
    assert next(l for l in linhas if l["indicador"] == "Selic meta")["erro"] == "SGS 432: página de erro HTML"


def test_coletar_noticias_classifica_por_regiao_e_ticker():
    noticias = [
        {"titulo": "PETR4 anuncia dividendo", "link": "https://x/1", "regiao": "BR", "tickers": ["PETR4"]},
        {"titulo": "Governo anuncia pacote fiscal", "link": "https://x/2", "regiao": "BR", "tickers": []},
        {"titulo": "Fed sinaliza postura sobre juros", "link": "https://x/3", "regiao": "INT", "tickers": []},
    ]
    with _MultiPatch(**_pools(noticias)):
        erros, brasil, empresas, exterior = ed._coletar_noticias()
    assert erros == {}
    assert [i["titulo"] for i in brasil] == ["Governo anuncia pacote fiscal"]
    assert [i["titulo"] for i in empresas] == ["PETR4 anuncia dividendo"]
    assert [i["titulo"] for i in exterior] == ["Fed sinaliza postura sobre juros"]


def test_coletar_noticias_erro_de_um_pool_nao_esvazia_o_outro():
    falha = lambda: (_ for _ in ()).throw(RuntimeError("Google News fora do ar"))
    fed = {"titulo": "Fed", "link": "https://x/3", "regiao": "INT", "tickers": []}
    with _MultiPatch(obter_top_mercado=falha, obter_top_mercado_internacional=lambda: [fed]):
        erros, brasil, empresas, exterior = ed._coletar_noticias()
    # o texto vai pro PDF: diz que falhou, sem expor exceção/host ao leitor
    assert erros["BR"] == "coleta do Google News falhou nesta execução"
    assert "RuntimeError" not in erros["BR"] and "fora do ar" not in erros["BR"]
    assert "INT" not in erros
    assert brasil == [] and empresas == []
    assert exterior == [fed]


def test_mundo_nao_fica_vazio_quando_pool_brasil_domina_o_ranking():
    """Regressão da edição de 18/10/2026: com o ranking combinado (top 20
    de BR+INT) as 20 mais importantes eram do Brasil e Mundo saía vazio."""
    brasil = [{"titulo": f"Notícia Brasil {n}", "link": f"https://br/{n}", "regiao": "BR", "tickers": [],
               "importancia": 90 - n} for n in range(25)]
    mundo = [{"titulo": "Wall Street closes higher", "link": "https://int/1", "regiao": "INT", "tickers": [],
              "importancia": 10}]
    with _MultiPatch(**_pools(brasil + mundo)):
        edicao = ed.montar_edicao(datetime(2026, 10, 14, 7, tzinfo=TZ_SP))
    assert [n["titulo"] for n in edicao["exterior"]["noticias"]] == ["Wall Street closes higher"]


def test_filtro_descarta_noticia_antiga_futura_e_sem_data():
    agora = datetime(2026, 10, 19, 7, tzinfo=TZ_SP)  # segunda -> janela desde sexta 06:00
    itens = [
        {"titulo": "Sexta de manhã", "data": "2026-10-16T09:00:00-03:00", "importancia": 1},
        {"titulo": "Terça passada", "data": "2026-10-13T09:00:00-03:00", "importancia": 9},
        {"titulo": "Sexta de madrugada", "data": "2026-10-16T05:00:00-03:00", "importancia": 9},
        {"titulo": "Sem data", "importancia": 9},
        {"titulo": "Do futuro", "data": "2026-10-20T09:00:00-03:00", "importancia": 9},
    ]
    assert [i["titulo"] for i in ed.filtrar_noticias(itens, agora)] == ["Sexta de manhã"]


def test_janela_de_noticias_comeca_no_dia_util_anterior():
    assert ed.inicio_janela_noticias(datetime(2026, 10, 19, 7, tzinfo=TZ_SP)) == datetime(2026, 10, 16, 6, tzinfo=TZ_SP)
    assert ed.inicio_janela_noticias(datetime(2026, 10, 18, 12, tzinfo=TZ_SP)) == datetime(2026, 10, 16, 6, tzinfo=TZ_SP)
    assert ed.inicio_janela_noticias(datetime(2026, 10, 21, 7, tzinfo=TZ_SP)) == datetime(2026, 10, 20, 6, tzinfo=TZ_SP)


def test_filtro_descarta_loteria_e_mantem_noticia_com_palavra_parecida():
    agora = datetime(2026, 10, 19, 7, tzinfo=TZ_SP)
    d = "2026-10-18T20:00:00-03:00"
    itens = [{"titulo": "Resultado da Quina 6855 de sábado", "data": d, "importancia": 9},
             {"titulo": "Mega-Sena acumula e prêmio vai a R$ 50 milhões", "data": d, "importancia": 8},
             {"titulo": "Passagens aéreas para São Paulo a partir de R$ 351 ida e volta", "data": d, "importancia": 7},
             {"titulo": "Quinta-feira tem dados de inflação nos EUA", "data": d, "importancia": 1}]
    assert [i["titulo"] for i in ed.filtrar_noticias(itens, agora)] == ["Quinta-feira tem dados de inflação nos EUA"]


def test_filtro_descarta_carta_de_leitor_em_primeira_pessoa():
    """Caso real (Mundo, 18/10/2026): colunas de aconselhamento do MarketWatch."""
    agora = datetime(2026, 10, 19, 7, tzinfo=TZ_SP)
    d = "2026-10-18T12:00:00-03:00"
    itens = [{"titulo": "I\u2019m 63 and diagnosed with lymphoma. Should I take my Social Security next year?",
              "data": d, "importancia": 9},
             {"titulo": "I'm 64 with two sons, but only one works in the family business", "data": d, "importancia": 8},
             {"titulo": "Microsoft pulls plug on Nscale data centre deal", "data": d, "importancia": 1}]
    assert [i["titulo"] for i in ed.filtrar_noticias(itens, agora)] == ["Microsoft pulls plug on Nscale data centre deal"]


def test_filtro_remove_duplicata_do_mesmo_fato_mantendo_a_mais_importante():
    """Caso real de 18/10/2026: duas manchetes do mesmo fechamento."""
    agora = datetime(2026, 10, 19, 7, tzinfo=TZ_SP)
    d = "2026-10-16T18:00:00-03:00"
    itens = [{"titulo": "IBOVESPA fecha hoje com alta de 0,54%", "data": d, "importancia": 70},
             {"titulo": "Ibovespa sobe 0,54% e fecha semana no azul", "data": d, "importancia": 60},
             {"titulo": "Dólar cai 0,54% frente ao real", "data": d, "importancia": 50}]
    titulos = [i["titulo"] for i in ed.filtrar_noticias(itens, agora)]
    assert titulos == ["IBOVESPA fecha hoje com alta de 0,54%", "Dólar cai 0,54% frente ao real"]


def test_agenda_hoje_none_quando_calendario_falha():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with _MultiPatch(calcular_calendario_cacheado=lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("CVM fora do ar"))):
        assert ed._agenda_hoje(agora) is None


def test_agenda_hoje_lista_vazia_quando_nao_ha_evento():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with _MultiPatch(calcular_calendario_cacheado=lambda *_a, **_k: []):
        assert ed._agenda_hoje(agora) == []


def test_agenda_hoje_filtra_so_eventos_de_hoje_e_marca_tag_acompanhar():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    evento_hoje = {
        "ticker": "PETR4", "empresa": "Petrobras", "data": agora.date(),
        "horario": "08:00", "status": ed.STATUS_CONFIRMADO, "tipo_evento": "RESULTADO", "periodo": "3T26",
    }
    evento_futuro = {**evento_hoje, "ticker": "VALE3", "data": date(2026, 11, 1)}
    with _MultiPatch(calcular_calendario_cacheado=lambda *_a, **_k: [evento_hoje, evento_futuro]):
        agenda = ed._agenda_hoje(agora)
    assert len(agenda) == 1
    assert agenda[0]["ticker"] == "PETR4"
    assert agenda[0]["tag"] == ed.TAG_ACOMPANHAR


def test_montar_edicao_estrutura_completa_sem_rede():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with _MultiPatch():
        edicao = ed.montar_edicao(agora)
    assert edicao["agora"] == agora
    assert set(edicao.keys()) == {"agora", "capa", "brasil", "exterior", "empresas", "limitacoes", "fontes",
                                  "mercados_nota", "janela_noticias", "radar", "texto_stats"}
    # sem notícia de setor nenhum, o radar sai vazio e registra cada exclusão
    assert edicao["radar"]["setores"] == []
    assert all("evidência insuficiente" in e["motivo"] for e in edicao["radar"]["excluidos"])
    assert edicao["brasil"]["noticias"] is None
    assert edicao["empresas"]["agenda"] == []
    # sem notícia nenhuma, a capa não inventa manchete
    assert edicao["capa"]["manchete"] is None and edicao["capa"]["chamadas"] == []
    # as 3 "interpretações" genéricas fixas (iguais todo dia) saíram da edição
    assert "interpretacoes" not in edicao["exterior"]


def test_montar_edicao_capa_usa_top3_por_importancia():
    noticias = [
        {"titulo": "Mercado: baixa importância", "link": "https://x/1", "regiao": "INT", "tickers": [], "importancia": 1},
        {"titulo": "Mercado: alta importância", "link": "https://x/2", "regiao": "INT", "tickers": [], "importancia": 9},
        {"titulo": "Mercado: média importância", "link": "https://x/3", "regiao": "BR", "tickers": [], "importancia": 5},
    ]
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with _MultiPatch(**_pools(noticias)):
        edicao = ed.montar_edicao(agora)
    titulos_capa = [d["titulo"] for d in edicao["capa"]["destaques"]]
    assert titulos_capa[0] == "Mercado: alta importância"
    assert "Mercado: baixa importância" in titulos_capa  # só 3 notícias no total, as 3 entram


def _fato(titulo, importancia, corpo=None):
    return {"titulo": titulo, "importancia": importancia, "corpo": corpo or []}


def test_manchete_e_a_mais_importante_entre_as_que_tem_texto():
    """Relevância editorial manda, não volume de texto: a mais importante
    com texto publicável abre a capa; uma mais importante SEM texto vira
    chamada (não ganha manchete só de título enquanto houver opção com texto)."""
    sem_texto = _fato("Muito importante, sem texto", 0.99)
    lider = _fato("Importante com texto", 0.90, ["Parágrafo."])
    longa = _fato("Menos importante e mais longa", 0.50, ["Texto longo. " * 40])
    manchete, chamadas = ed.selecionar_manchete([longa, sem_texto, lider])
    assert manchete is lider
    assert chamadas == [sem_texto, longa]


def test_manchete_so_de_titulo_quando_nenhuma_tem_texto():
    a, b = _fato("A", 0.3), _fato("B", 0.8)
    manchete, chamadas = ed.selecionar_manchete([a, b])
    assert manchete is b and chamadas == [a]


def test_sem_noticia_nao_ha_manchete():
    assert ed.selecionar_manchete([]) == (None, [])


def test_corpo_vem_do_bloco_resumo_do_cache_sem_a_leitura_de_mercado():
    """O jornal publica o RESUMO (fato) já cacheado - nunca a LEITURA DE
    MERCADO (interpretação do modelo) - e não chama IA nenhuma."""
    noticia = {"titulo": "Ibovespa sobe", "link": "https://x/1", "regiao": "BR", "tickers": [],
               "importancia": 0.9, "veiculos": ["InfoMoney"], "fontes": [], "data": "2026-10-17T18:00:00-03:00"}
    pronto = {"resumo": "RESUMO:\nO Ibovespa subiu 0,5%.\n\nO volume foi de R$ 21 bilhões.\n\n"
                        "LEITURA DE MERCADO:\nInvestidores devem seguir otimistas.",
              "imagem": "https://img/x.jpg", "link_original": "https://veiculo/materia"}
    agora = datetime(2026, 10, 19, 7, tzinfo=TZ_SP)
    with _MultiPatch(**_pools([noticia]),
                     obter_resumos_prontos=lambda grupos: {"https://x/1": pronto}):
        edicao = ed.montar_edicao(agora)
    item = edicao["brasil"]["noticias"][0]
    assert item["corpo"] == ["O Ibovespa subiu 0,5%.", "O volume foi de R$ 21 bilhões."]
    assert "otimistas" not in " ".join(item["corpo"])
    assert item["imagem"] == "https://img/x.jpg"
    assert item["veiculo"] == "InfoMoney"
    assert edicao["capa"]["manchete"] is item


def test_falha_na_leitura_do_cache_nao_derruba_a_edicao():
    noticia = {"titulo": "Mercado X", "link": "https://x/1", "regiao": "BR", "tickers": [], "importancia": 1}

    def _quebra(_g):
        raise RuntimeError("cache fora do ar")

    agora = datetime(2026, 10, 19, 7, tzinfo=TZ_SP)
    with _MultiPatch(**_pools([noticia], data="2026-10-18T09:00:00-03:00"), obter_resumos_prontos=_quebra):
        edicao = ed.montar_edicao(agora)
    assert edicao["brasil"]["noticias"][0]["corpo"] == []
    assert edicao["capa"]["manchete"]["titulo"] == "Mercado X"


def test_radar_consulta_cada_setor_e_aplica_regras_da_edicao():
    """O radar pede as notícias de cada setor e aplica a janela, o filtro
    de pauta e a validação de fonte."""
    pedidos = []
    agora = datetime(2026, 10, 19, 8, tzinfo=TZ_SP)

    def por_setor(setor="TODOS"):
        pedidos.append(setor)
        if setor == "TODOS":
            return []
        return [
            {"titulo": "Bancos ampliam provisões", "veiculos": ["Valor Econômico"], "link": "https://v/1",
             "data": "2026-10-18T20:00:00-03:00", "importancia": 5, "tickers": []},
            {"titulo": "Crédito bancario desacelera, diz BC", "veiculos": ["Folha de S.Paulo"], "link": "https://f/2",
             "data": "2026-10-18T21:00:00-03:00", "importancia": 4, "tickers": []},
            {"titulo": "Resultado da Quina: bancos fecham", "veiculos": ["G1"], "link": "https://g/3",
             "data": "2026-10-18T21:00:00-03:00", "importancia": 9, "tickers": []},
        ]

    with _MultiPatch(obter_top_mercado=por_setor,
                     _noticias_do_setor=lambda setor: por_setor(setor)):
        edicao = ed.montar_edicao(agora)
    assert "BANCOS" in pedidos
    bancos = next(b for b in edicao["radar"]["setores"] if b["setor"] == "BANCOS")
    assert [f["veiculo"] for f in bancos["fontes"]] == ["Valor Econômico", "Folha de S.Paulo"]


def test_noticias_do_setor_busca_dedicada_mais_ranking_geral(monkeypatch):
    from data import news as coletor
    urls = []
    monkeypatch.setattr(coletor, "_buscar_feed_de_url", lambda url: urls.append(url) or [{"link": "x"}])
    monkeypatch.setattr(coletor, "_processar_pool", lambda entries, setor, regiao: [{"titulo": "dedicada"}])
    monkeypatch.setattr(ed, "obter_top_mercado", lambda *_a: [{"titulo": "geral"}])
    itens = ed._noticias_do_setor("BANCOS")
    assert [i["titulo"] for i in itens] == ["dedicada", "geral"]
    assert len(urls) == 1 and "when%3A3d" in urls[0] and "Ita%C3%BA" in urls[0]


def test_noticias_do_setor_none_quando_as_duas_coletas_falham(monkeypatch):
    from data import news as coletor
    monkeypatch.setattr(coletor, "_buscar_feed_de_url", lambda url: None)
    monkeypatch.setattr(ed, "obter_top_mercado", lambda *_a: None)
    assert ed._noticias_do_setor("BANCOS") is None


# ------------------------------------------------------------------
# Selic/CDI: erro nunca vira valor; última coleta válida (só leitura)
# ------------------------------------------------------------------

def test_taxa_plausivel_rejeita_texto_nan_e_absurdos():
    assert ed._taxa_plausivel(15.0) == 15.0
    for invalido in ("Internal error", None, float("nan"), -1, 0, 150, "15,00% a.a."):
        assert ed._taxa_plausivel(invalido) is None, invalido


def test_selic_com_valor_absurdo_sai_indisponivel_sem_numero():
    selic = pd.DataFrame({"data": pd.to_datetime(["2026-10-16"]).tz_localize(TZ_SP), "selic_meta_pct": [1500.0]})
    with _MultiPatch(obter_selic_meta=lambda: selic, ultima_coleta_valida=lambda _c: None):
        linha = next(l for l in ed._macro_rows() if l["indicador"] == "Selic meta")
    assert linha["valor"] is None
    assert "fora da faixa" in linha["erro"]


def test_indisponivel_informa_ultima_coleta_valida_sem_inventar_valor():
    with _MultiPatch(obter_selic_meta=lambda: None,
                     motivo_indisponivel=lambda c: "SGS 432: página de erro HTML" if c == "selic" else None,
                     ultima_coleta_valida=lambda c: "16/10/2026 18:41" if c == "selic" else None):
        linhas = {l["indicador"]: l for l in ed._macro_rows()}
    assert linhas["Selic meta"]["valor"] is None
    assert linhas["Selic meta"]["erro"] == ("SGS 432: página de erro HTML; última coleta válida registrada em "
                                           "16/10/2026 18:41 (horário de Brasília)")


def test_ultima_coleta_valida_le_o_painel_de_saude_e_converte_para_brasilia(monkeypatch):
    import data.coletores_status as cs
    monkeypatch.setattr(cs, "obter_status", lambda nome: {"ultimo_sucesso_em": "2026-10-16T21:41:00+00:00"}
                        if nome == "MACRO (BCB - Selic)" else None)
    assert ed.ultima_coleta_valida("selic") == "16/10/2026 18:41"
    assert ed.ultima_coleta_valida("cdi") is None


def test_ultima_coleta_valida_com_banco_fora_do_ar_devolve_none(monkeypatch):
    import data.coletores_status as cs
    monkeypatch.setattr(cs, "obter_status", lambda nome: (_ for _ in ()).throw(RuntimeError("supabase fora")))
    assert ed.ultima_coleta_valida("selic") is None


def test_selic_usa_historico_oficial_do_copom_quando_sgs_falha():
    meta = {"valor": 13.75, "vigente_desde": date(2026, 9, 17), "reuniao": 281}
    with _MultiPatch(obter_selic_meta=lambda: None, obter_selic_meta_copom=lambda: meta):
        linha = next(l for l in ed._macro_rows() if l["indicador"] == "Selic meta")
    assert linha["valor"] == 13.75
    assert linha["referencia"] == "vigente desde 17/09/2026"
    assert "281ª reunião do Copom" in linha["detalhe"] and "SGS indisponível" in linha["detalhe"]


def test_selic_do_sgs_tem_prioridade_sobre_o_copom():
    selic = pd.DataFrame({"data": pd.to_datetime(["2026-10-16"]).tz_localize(TZ_SP), "selic_meta_pct": [13.75]})
    chamado = []
    with _MultiPatch(obter_selic_meta=lambda: selic, obter_selic_meta_copom=lambda: chamado.append(1)):
        linha = next(l for l in ed._macro_rows() if l["indicador"] == "Selic meta")
    assert linha["referencia"] == "16/10/2026" and not chamado


def test_selic_copom_invalido_mantem_indisponivel_com_os_dois_motivos():
    with _MultiPatch(obter_selic_meta=lambda: None, obter_selic_meta_copom=lambda: {"valor": "erro"},
                     motivo_indisponivel=lambda c: {"selic": "SGS 432: timeout",
                                                    "selic_copom": "histórico do Copom (bcb.gov.br): HTTP 500"}.get(c),
                     ultima_coleta_valida=lambda _c: None):
        linha = next(l for l in ed._macro_rows() if l["indicador"] == "Selic meta")
    assert linha["valor"] is None
    # as duas fontes continuam nomeadas; o detalhe técnico fica só no log
    assert linha["erro"] == ("SGS 432 não respondeu nesta execução; "
                             "histórico do Copom (bcb.gov.br) não respondeu nesta execução")


def test_cdi_nao_tem_plano_b_e_continua_indisponivel():
    meta = {"valor": 13.75, "vigente_desde": date(2026, 9, 17), "reuniao": 281}
    with _MultiPatch(obter_cdi=lambda: None, obter_selic_meta_copom=lambda: meta,
                     ultima_coleta_valida=lambda _c: None):
        linha = next(l for l in ed._macro_rows() if l["indicador"] == "CDI")
    assert linha["valor"] is None


def test_resumo_cacheado_chega_tambem_na_editoria_mundo():
    """O PDF publica o RESUMO cacheado de matérias internacionais (pool
    INT separado) - mesma regra do pool Brasil, sem chamar IA."""
    mundo = {"titulo": "Fed holds rates", "link": "https://int/1", "regiao": "INT", "tickers": [],
             "importancia": 9, "veiculos": ["Reuters"], "fontes": [], "data": "2026-10-18T20:00:00-03:00"}
    pronto = {"resumo": "RESUMO:\nO Fed manteve os juros.\n\nLEITURA DE MERCADO:\nOpinião do modelo."}
    with _MultiPatch(**_pools([mundo]), obter_resumos_prontos=lambda grupos: {"https://int/1": pronto}):
        edicao = ed.montar_edicao(datetime(2026, 10, 19, 7, tzinfo=TZ_SP))
    item = edicao["exterior"]["noticias"][0]
    assert item["corpo"] == ["O Fed manteve os juros."]
    assert "Opinião" not in " ".join(item["corpo"])


def test_sem_resumo_cacheado_mundo_sai_so_com_manchete_e_fonte():
    mundo = {"titulo": "Fed holds rates", "link": "https://int/1", "regiao": "INT", "tickers": [],
             "importancia": 9, "veiculos": ["Reuters"], "fontes": [], "data": "2026-10-18T20:00:00-03:00"}
    with _MultiPatch(**_pools([mundo]), obter_resumos_prontos=lambda grupos: {}):
        edicao = ed.montar_edicao(datetime(2026, 10, 19, 7, tzinfo=TZ_SP))
    item = edicao["exterior"]["noticias"][0]
    assert item["corpo"] == [] and item["veiculo"] == "Reuters" and item["link"] == "https://int/1"
