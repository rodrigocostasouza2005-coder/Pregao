# -*- coding: utf-8 -*-
"""Fixtures de publicacoes REALISTAS do X pros testes do RADAR X
(secao 10 do pedido) - nenhum teste que usa isso depende de chamada
paga a API nenhuma (Groq ou X); os 7 exemplos cobrem exatamente os
casos pedidos: analise fundamentada, opiniao sem evidencia, rumor,
fato confirmado, macro, spam, publicacao repetida."""

from datetime import datetime, timezone

from data.x_signals import EstadoSinal, NivelEvidencia, Sinal


def _sinal(post_id, autor, texto, *, horas_atras=1, verificado=False):
    return Sinal(
        post_id=post_id, autor=autor,
        link_original=f"https://x.com/{autor.lstrip('@')}/status/{post_id}",
        horario_publicacao=datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
        horario_captura=datetime.now(timezone.utc),
        contexto=texto, chave_acontecimento="",
        nivel_evidencia=NivelEvidencia.NAO_CONFIRMADO, estado=EstadoSinal.DETECTADO,
        conta_verificada=verificado,
    )


SINAL_ANALISE_FUNDAMENTADA = _sinal(
    "1001", "@analista_br",
    "PETR4: ROIC caiu de 18% pra 14% nos ultimos 2 trimestres, margem EBITDA "
    "tambem recuou - olhando o release do 2T, o aumento de custo operacional "
    "explica boa parte. Tese de valuation atrativo fica mais fraca nesse cenario.",
)

SINAL_OPINIAO_SEM_EVIDENCIA = _sinal(
    "1002", "@investidor_qualquer",
    "acho que VALE3 vai disparar esse mes, minerio ta bombando",
)

SINAL_RUMOR = _sinal(
    "1003", "@fonte_anonima",
    "ouvi de um amigo no mercado que a Magalu pode ser comprada por um "
    "fundo estrangeiro ainda esse ano - ningem confirmou nada ainda",
)

SINAL_FATO_CONFIRMADO = _sinal(
    "1004", "@cvmoficial",
    "Comunicado oficial: a CVM publicou hoje o Formulario de Referencia "
    "atualizado da Petrobras com os dados do 3T26, disponivel no site da CVM.",
    verificado=True,
)

SINAL_MACRO = _sinal(
    "1005", "@economista_br",
    "Copom deve manter a Selic em 10,5% na reuniao de novembro, segundo "
    "pesquisa Focus do Banco Central divulgada hoje.",
)

SINAL_SPAM = _sinal(
    "1006", "@cripto_bot_200",
    "GANHE 10000 TOKENS GRATIS agora clicando no link da bio!!! airdrop "
    "exclusivo, nao perca!!!",
)

SINAL_DUPLICADO_A = _sinal(
    "1007", "@analista_x",
    "WEGE3 anunciou guidance revisado pra cima no Investor Day de hoje",
)
SINAL_DUPLICADO_B = _sinal(
    "1008", "@outro_analista",
    "Vi que a WEGE3 revisou o guidance pra cima no Investor Day - mesma "
    "informacao que o analista_x postou",
)

TODOS = [
    SINAL_ANALISE_FUNDAMENTADA, SINAL_OPINIAO_SEM_EVIDENCIA, SINAL_RUMOR,
    SINAL_FATO_CONFIRMADO, SINAL_MACRO, SINAL_SPAM, SINAL_DUPLICADO_A, SINAL_DUPLICADO_B,
]
