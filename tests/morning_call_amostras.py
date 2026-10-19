# -*- coding: utf-8 -*-
"""Edições de AMOSTRA do Morning Call (formato de
data/morning_call_editorial.py:montar_edicao) pra testes de paginação e
prévias visuais do PDF - NUNCA usadas em produção.

`edicao_tipica` usa manchetes reais coletadas em produção em 17/10/2026
(log do run 39088619143, títulos truncados lá e completados aqui); os
resumos, cotações e agenda são CONTEÚDO DE EXEMPLO, escritos pra ter o
tamanho e a estrutura do que o pipeline real entrega (resumo em blocos
RESUMO/LEITURA DE MERCADO já separado em parágrafos de corpo)."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from data.morning_call_editorial import selecionar_manchete, sintese_pagina2

TZ_SP = ZoneInfo("America/Sao_Paulo")


def _ind(nome, preco, var, barra="16/10 17:18 (horário de Brasília)", erro=None):
    return {"nome": nome, "preco": preco, "variacao_pct": var, "barra_fmt": barra, "erro": erro,
            "sessao": date(2026, 10, 16) if barra else None}


def _noticia(titulo, veiculo, importancia, corpo=None, link=None, horas_atras=13, tickers=None, regiao="BR"):
    agora = datetime(2026, 10, 19, 8, 0, tzinfo=TZ_SP)
    slug = "-".join(titulo.lower().split()[:6])
    return {
        "titulo": titulo,
        "link": link or f"https://exemplo.invalid/{slug}",
        "veiculo": veiculo,
        "tag": "FATO",
        "importancia": importancia,
        "data": (agora - timedelta(hours=horas_atras)).isoformat(),
        "tickers": tickers or [],
        "regiao": regiao,
        "corpo": corpo or [],
        "imagem": None,
        "link_original": None,
    }


def _serie_ibov():
    base = datetime(2026, 9, 18, tzinfo=TZ_SP)
    valores = [141210, 141880, 140950, 142300, 142940, 142110, 143020, 143650, 142780,
               141900, 142450, 143380, 144020, 143510, 144260, 144870, 143990, 144530, 145010, 144540, 145320]
    return [(base + timedelta(days=i), float(v)) for i, v in enumerate(valores)]


def _macro():
    """Linhas macro geradas pelo PRÓPRIO data/morning_call_editorial.py a
    partir de DataFrames com as colunas reais de data/macro.py (valores
    do diagnóstico real de 18/10/2026) - a amostra antiga usava chaves
    inventadas ('valor', 'mediana') e escondeu o defeito do Focus."""
    import pandas as pd
    from unittest.mock import patch
    import data.morning_call_editorial as editorial

    def _focus(medianas, respondentes):
        return pd.DataFrame({
            "ano_referencia": [2026, 2027, 2028], "mediana_pct": medianas, "media_pct": medianas,
            "numero_respondentes": respondentes,
            "data_calculo": pd.to_datetime(["2026-10-09"] * 3).tz_localize(TZ_SP)})

    selic = pd.DataFrame({"data": pd.to_datetime(["2026-10-16"]).tz_localize(TZ_SP), "selic_meta_pct": [15.0]})
    cdi = pd.DataFrame({"data": pd.to_datetime(["2026-10-16"]).tz_localize(TZ_SP),
                        "cdi_diario_pct": [0.055131], "cdi_anualizado_pct": [14.90]})
    with patch.object(editorial, "obter_selic_meta", lambda: selic), \
            patch.object(editorial, "obter_cdi", lambda: cdi), \
            patch.object(editorial, "obter_focus_ipca", lambda: _focus([5.2245, 4.30, 3.79], [144, 138, 117])), \
            patch.object(editorial, "obter_focus_selic", lambda: _focus([13.25, 12.00, 10.50], [140, 135, 115])):
        return editorial._macro_rows(datetime(2026, 10, 19, 8, 0, tzinfo=TZ_SP))


def edicao_tipica():
    agora = datetime(2026, 10, 19, 8, 0, tzinfo=TZ_SP)
    ibov = _ind("Ibovespa", 145320.48, 0.54)
    dolar = _ind("Dólar (USD/BRL)", 5.0712, -0.30)
    brasil = [
        _noticia("Ibovespa sobe 0,54% com apoio de ações do petróleo", "InfoMoney", 0.94, [
            "O Ibovespa fechou a sexta-feira em alta de 0,54%, aos 145.320 pontos, sustentado pelas ações "
            "da Petrobras, que acompanharam a valorização do petróleo no mercado internacional.",
            "O volume financeiro somou R$ 21,4 bilhões, abaixo da média diária de outubro. Na semana, o "
            "índice acumulou ganho de 1,2%, o terceiro avanço semanal consecutivo.",
            "O dólar à vista recuou 0,30%, a R$ 5,07, em sessão de menor aversão a risco no exterior.",
        ]),
        _noticia("Focus eleva projeção do IPCA de 2026 pela quarta semana seguida", "Valor Econômico", 0.88, [
            "A mediana das projeções para o IPCA de 2026 no Boletim Focus subiu de 5,18% para 5,22%, a quarta "
            "alta consecutiva, segundo o levantamento semanal do Banco Central com instituições financeiras.",
            "Para 2027, a estimativa ficou estável em 4,10%. A projeção para a taxa Selic no fim de 2026 "
            "permaneceu em 15,00% ao ano.",
        ]),
        _noticia("IPCA sobe 0,82% em setembro, pressionado pela energia elétrica", "g1", 0.80, [
            "O Índice Nacional de Preços ao Consumidor Amplo (IPCA) subiu 0,82% em setembro, informou o IBGE. "
            "O grupo Habitação, influenciado pela bandeira tarifária da energia elétrica, respondeu pela maior "
            "contribuição individual.",
            "Em 12 meses, a inflação acumulada passou a 5,36%, acima do teto da meta perseguida pelo Banco Central.",
        ]),
        _noticia("Prisma Fiscal eleva previsão de déficit primário do governo central em 2026", "Agência Brasil", 0.71, [
            "A mediana das projeções do Prisma Fiscal, do Ministério da Fazenda, para o déficit primário do "
            "governo central em 2026 passou de R$ 74,1 bilhões para R$ 81,3 bilhões.",
        ]),
        _noticia("Lula defende crescimento econômico como caminho para o ajuste fiscal", "Folha de S.Paulo", 0.62),
        _noticia("Aluguel sobe o dobro da inflação no ano, diz pesquisa", "Estadão", 0.40),
    ]
    exterior = [
        _noticia("Inflação dos EUA acelera em setembro e reacende debate sobre juros", "Reuters", 0.90, [
            "O índice de preços ao consumidor dos Estados Unidos subiu 0,4% em setembro, acima da alta de 0,3% "
            "de agosto, segundo o Departamento do Trabalho. Em 12 meses, a inflação foi a 3,1%.",
            "O núcleo do índice, que exclui alimentos e energia, avançou 0,3% no mês.",
        ], regiao="INT"),
        _noticia("Livro Bege do Fed aponta alta de preços e estabilidade no emprego", "Valor Econômico", 0.74, [
            "O relatório Livro Bege, do Federal Reserve, descreveu atividade econômica estável na maior parte "
            "dos 12 distritos do banco central americano, com pressões de preços moderadas a elevadas.",
        ], regiao="INT"),
        _noticia("Déficit orçamentário dos EUA se aproxima de US$ 2 trilhões no ano fiscal", "Bloomberg Línea", 0.55, regiao="INT"),
        _noticia("Bitcoin se estabiliza perto de US$ 82 mil após semana volátil", "CoinDesk", 0.38, regiao="INT"),
    ]
    empresas = [
        _noticia("Petrobras atinge R$ 820 bilhões em valor de mercado", "InfoMoney", 0.86, [
            "As ações da Petrobras renovaram máximas históricas e levaram o valor de mercado da companhia a "
            "R$ 820 bilhões, o maior entre as empresas listadas na B3.",
            "PETR4 subiu 1,9% na sessão, acompanhando o avanço do petróleo Brent.",
        ], tickers=["PETR4", "PETR3"]),
        _noticia("Caixa Seguridade (CXSE3): XP eleva preço-alvo e mantém recomendação de compra", "Money Times", 0.66, [
            "A XP Investimentos elevou o preço-alvo de Caixa Seguridade para o fim de 2026 e manteve a "
            "recomendação de compra, citando a geração de caixa da operação de seguros.",
        ], tickers=["CXSE3"]),
        _noticia("Seguradoras no 3T26: resultados devem ser fracos, apontam analistas", "Exame", 0.45, tickers=["BBSE3"]),
    ]
    todas = sorted(brasil + empresas + exterior, key=lambda i: i["importancia"], reverse=True)
    manchete, chamadas = selecionar_manchete(todas)
    edicao = {
        "agora": agora,
        "capa": {"indicadores": [ibov, dolar], "destaques": todas[:3], "manchete": manchete, "chamadas": chamadas},
        "brasil": {
            "indicadores": [ibov, dolar] + _macro(),
            "historico_ibov": _serie_ibov(),
            "destaque": brasil[0],
            "noticias": brasil,
            "noticias_erro": None,
        },
        "exterior": {
            "indicadores": [_ind("S&P 500 futuro", 6712.25, 0.35), _ind("Nasdaq futuro", 24850.50, 0.52),
                            _ind("Ouro", 4012.10, -0.81), _ind("Petróleo Brent", 62.35, 1.42)],
            "historico_petroleo": [],
            "destaque": exterior[0],
            "noticias": exterior,
            "noticias_erro": None,
            "interpretacoes": [],
        },
        "empresas": {
            "cards": empresas,
            "agenda": [
                {"empresa": "Usiminas", "ticker": "USIM5", "tipo_evento": "RESULTADO", "periodo": "3T26",
                 "horario": "após o fechamento", "status_rotulo": "CONFIRMADO",
                 "status_nota": "data CONFIRMADA pela própria empresa/fonte oficial.", "tag": "ACOMPANHAR"},
                {"empresa": "WEG", "ticker": "WEGE3", "tipo_evento": "RESULTADO", "periodo": "3T26",
                 "horario": "antes da abertura", "status_rotulo": "ESTIMADO",
                 "status_nota": "data ESTIMADA por fonte externa — ainda não confirmada pela empresa.", "tag": "ACOMPANHAR"},
            ],
            "noticias_erro": None,
        },
        "mercados_nota": ("Cotações e variações referem-se à última sessão disponível (sexta-feira, 16/10), "
                          "comparada com a sessão anterior."),
        "janela_noticias": datetime(2026, 10, 16, 6, 0, tzinfo=TZ_SP),
        "limitacoes": (
            "Fontes gratuitas podem ter atraso e indisponibilidade; esta edição não garante cotação em tempo real.",
            "Conteúdo informativo, não constitui recomendação de investimento.",
        ),
        "fontes": (
            "Cotações: Yahoo Finance (yfinance) — dados podem ter atraso conforme o provedor.",
            "Indicadores macro: Banco Central do Brasil (Selic/CDI) e Boletim Focus (BCB).",
            "Notícias: Google News (agregador); veículo original e link em cada matéria.",
        ),
    }
    edicao["sintese_pagina2"] = sintese_pagina2(edicao, agora)
    return edicao


def edicao_vazia():
    """Nenhuma notícia, nenhuma cotação, agenda indisponível - o caso mais
    adverso que o renderer precisa sobreviver sem inventar conteúdo."""
    agora = datetime(2026, 10, 19, 8, 0, tzinfo=TZ_SP)
    sem = lambda n: _ind(n, None, None, barra=None, erro="sem dado")  # noqa: E731
    edicao = {
        "agora": agora,
        "capa": {"indicadores": [sem("Ibovespa"), sem("Dólar (USD/BRL)")], "destaques": [],
                 "manchete": None, "chamadas": []},
        "brasil": {"indicadores": [sem("Ibovespa"), sem("Dólar (USD/BRL)")], "historico_ibov": [],
                   "destaque": None, "noticias": None, "noticias_erro": "ConnectionError: fonte fora do ar"},
        "exterior": {"indicadores": [], "historico_petroleo": [], "destaque": None, "noticias": None,
                     "noticias_erro": "ConnectionError: fonte fora do ar", "interpretacoes": []},
        "empresas": {"cards": [], "agenda": None, "noticias_erro": "ConnectionError: fonte fora do ar"},
        "limitacoes": ("Conteúdo informativo, não constitui recomendação de investimento.",),
        "fontes": ("Cotações: Yahoo Finance (yfinance).",),
    }
    edicao["sintese_pagina2"] = sintese_pagina2(edicao, agora)
    return edicao


def edicao_cheia():
    """Volume alto (muitas matérias com corpo longo e títulos longos) -
    força quebra de página/coluna e o limite de extensão."""
    ed = edicao_tipica()
    paragrafo = ("Segundo a reportagem, o movimento ocorreu em meio a revisões de projeções de analistas e a "
                 "uma agenda carregada de indicadores, com investidores atentos a sinais sobre a trajetória "
                 "dos juros e do câmbio nas próximas semanas.")
    extras = [
        _noticia(f"Manchete adicional número {i} com título propositalmente longo para testar a quebra "
                 f"natural de linhas em colunas estreitas da edição", "Veículo de Teste", 0.5 - i / 100,
                 [paragrafo] * (1 + i % 3))
        for i in range(1, 16)
    ]
    ed["brasil"]["noticias"] = ed["brasil"]["noticias"] + extras[:8]
    ed["exterior"]["noticias"] = ed["exterior"]["noticias"] + [dict(e, regiao="INT") for e in extras[8:]]
    ed["empresas"]["agenda"] = ed["empresas"]["agenda"] * 6
    todas = ed["brasil"]["noticias"] + ed["empresas"]["cards"] + ed["exterior"]["noticias"]
    ed["capa"]["manchete"], ed["capa"]["chamadas"] = selecionar_manchete(todas)
    # recalcula a síntese da página 2 sobre o dict JÁ com os extras de volume
    # (edicao_tipica() calculou a dela antes desses acréscimos, ficaria stale)
    ed["sintese_pagina2"] = sintese_pagina2(ed, ed["agora"])
    return ed


def _noticia_setor(titulo, veiculo, horas_atras, importancia, tickers=None):
    agora = datetime(2026, 10, 19, 8, 0, tzinfo=TZ_SP)
    slug = "-".join(titulo.lower().split()[:5])
    return {"titulo": titulo, "veiculos": [veiculo], "link": f"https://exemplo.invalid/setor/{slug}",
            "data": (agora - timedelta(hours=horas_atras)).isoformat(), "importancia": importancia,
            "tickers": tickers or [], "regiao": "BR"}


# Manchetes de EXEMPLO por setor (formato do coletor data/news.py) - só
# para testes; o exemplo real vem do diagnóstico com dados reais.
NOTICIAS_SETOR_AMOSTRA = {
    "PETRÓLEO & GÁS": [
        _noticia_setor("Petrobras renova recorde de produção no pré-sal no terceiro trimestre", "Valor Econômico", 20, 90, ["PETR4"]),
        _noticia_setor("Brent sobe com cortes de oferta da Opep+ e estoques menores nos EUA", "InfoMoney", 30, 80),
        _noticia_setor("PRIO conclui aquisição de fatia em campo na Bacia de Campos", "Money Times", 40, 60, ["PRIO3"]),
    ],
    "IMOBILIÁRIO": [
        _noticia_setor("Construtoras de baixa renda aceleram lançamentos e vendas com novas faixas do Minha Casa, Minha Vida", "Estadão", 22, 70),
        _noticia_setor("Cury e Direcional lideram vendas de imóveis no trimestre", "Valor Econômico", 26, 65, ["CURY3", "DIRR3"]),
    ],
    "BANCOS": [
        _noticia_setor("Bancos ampliam provisões para inadimplência de pequenas empresas", "Folha de S.Paulo", 18, 85),
        _noticia_setor("Itaú e Bradesco divulgam balanços na próxima semana; crédito é foco", "InfoMoney", 28, 75, ["ITUB4", "BBDC4"]),
    ],
    "VAREJO": [
        _noticia_setor("Vendas no varejo surpreendem e sobem em agosto, diz IBGE", "G1", 24, 70),
        _noticia_setor("Varejistas de moda reforçam estoques para a Black Friday", "Exame", 34, 50),
    ],
    # só uma fonte: deve sair do radar por evidência insuficiente
    "ENERGIA ELÉTRICA": [_noticia_setor("Aneel mantém bandeira tarifária amarela em novembro", "Agência Brasil", 12, 60)],
}


def radar_amostra():
    from data import radar_setorial
    agora = datetime(2026, 10, 19, 8, 0, tzinfo=TZ_SP)
    return radar_setorial.montar_radar(
        agora, buscar=lambda setor: NOTICIAS_SETOR_AMOSTRA.get(setor, []),
        inicio=datetime(2026, 10, 16, 6, 0, tzinfo=TZ_SP))
