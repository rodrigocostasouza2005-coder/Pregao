# -*- coding: utf-8 -*-
"""X (Twitter) como fonte de DESCOBERTA de sinais - FASE 4 da auditoria
2026-10-09. MODULO DESLIGADO DE PROPOSITO (DISPONIVEL=False) - nenhuma
funcao aqui faz chamada de rede nem retorna dado simulado. Ver
BACKLOG.md pra decisao completa; resumo:

Verificado (pesquisa real, 2026-10-09, nao presumido): a API do X nao
tem mais tier gratuito pra desenvolvedor novo desde 06/02/2026 - o free
tier antigo (que ja' nao incluia /search, so' ~50 leituras/dia) foi
descontinuado, e o Basic ($200/mes fixo) foi forcado pra cobranca por
uso (pay-per-use, ~US$0,005 por leitura de post) e nao aceita mais
assinante novo. Busca/filtro de posts recentes (o uso que este modulo
precisaria - "descobrir" sinais, nao so' ler um post especifico) parece
exigir tier Enterprise (a partir de US$42.000/mes) ou pelo menos uma
camada paga especifica - nenhuma fonte confirma acesso de busca
incluido no pay-per-use basico. Scraping nao-oficial contorna
controles de acesso (Termos de Servico do X) - fora de cogitacao pelo
mesmo principio ja aplicado a outras fontes deste projeto (ver
genial_lives.py: so' uma excecao justificada, documentada, pra
robots.txt do YouTube - scraping de login/API privada do X e'
categoria diferente e mais invasiva, nao comparavel).

Conclusao: sem credencial nova e paga (nao aprovada), nao ha'
integracao viavel hoje. Este modulo fica isolado, desligado e
preparado - define o CONTRATO de dados (niveis de evidencia, ciclo de
vida do sinal, dedup por acontecimento) que uma integracao futura
preencheria, sem forcar nenhuma decisao de arquitetura a ser retomada
do zero quando/se o Rodrigo aprovar o custo.

NUNCA import este modulo de ui/*.py nem do app principal - permanece
fora do grafo de import do app ate' uma decisao explicita de ligar."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

DISPONIVEL = False

MOTIVO_INDISPONIVEL = (
    "API do X sem tier gratuito pra desenvolvedor novo desde 06/02/2026; "
    "busca/descoberta de posts recentes parece exigir tier pago especifico "
    "ou Enterprise (US$42k+/mes) - nenhuma fonte confirma busca incluida no "
    "pay-per-use basico (~US$0,005/leitura). Scraping nao-oficial contorna "
    "Termos de Servico - nao usado neste projeto. Decisao: aguardar "
    "aprovacao explicita de custo/credencial, nunca simular conexao."
)


class NivelEvidencia(str, Enum):
    """Nivel 1: publicacao relevante, ainda nao confirmada (NAO
    CONFIRMADO). Nivel 2: ha' fontes adicionais, mas sem evidencia
    primaria suficiente (EM VERIFICACAO) - MULTIPLAS contas reproduzindo
    o MESMO post/origem NAO contam como corroboracao independente (ver
    `mesma_origem` em Sinal). Nivel 3: confirmado por fonte confiavel -
    comunicado oficial, documento regulatorio, publicacao original
    verificavel ou evidencia independente de verdade - a fonte
    confirmadora fica em `evidencias_confirmacao`, nunca so' 'confiavel'
    sem citar o que confirmou."""
    NAO_CONFIRMADO = "nivel_1_sinal_social"
    EM_VERIFICACAO = "nivel_2_corroboracao_parcial"
    CONFIRMADO = "nivel_3_confirmado_fonte_confiavel"


class EstadoSinal(str, Enum):
    DETECTADO = "detectado"
    EM_VERIFICACAO = "em_verificacao"
    CONFIRMADO = "confirmado"
    REFUTADO = "refutado"
    EXPIRADO = "expirado"


@dataclass
class Sinal:
    """Contrato de dados pra UM sinal descoberto - preenchido por uma
    integracao futura, nunca por este modulo (DISPONIVEL=False).

    autor / link_original / horario_publicacao: preservados sempre que
    disponiveis - nunca normalizados/removidos.
    horario_captura: quando o PREGAO viu o post, separado de
    horario_publicacao (podem divergir bastante).
    chave_acontecimento: dedup por FATO, nao por post - varios posts
    (inclusive de contas diferentes) sobre o MESMO acontecimento
    compartilham a chave; calculada por uma integracao futura (ex:
    entidades citadas + janela de tempo, mesmo princípio de
    data/news.py:_agrupar), nunca aqui.
    mesma_origem: True se este post e' replica/retuite/citacao de outro
    ja' catalogado (nunca conta como fonte adicional independente pra
    subir nivel de evidencia - ver NivelEvidencia).
    conta_verificada: informativo, NUNCA usado por si so' pra subir
    nivel de evidencia (conta verificada nao e' confiavel por
    definicao).
    evidencias_confirmacao: lista de fontes PRIMARIAS (link de
    comunicado oficial, documento regulatorio etc) que sustentam
    NivelEvidencia.CONFIRMADO - obrigatorio preencher se o nivel for
    CONFIRMADO, nunca inferido."""
    autor: str
    link_original: str
    horario_publicacao: datetime | None
    horario_captura: datetime
    contexto: str
    chave_acontecimento: str
    nivel_evidencia: NivelEvidencia
    estado: EstadoSinal
    mesma_origem: bool = False
    conta_verificada: bool = False
    evidencias_confirmacao: list = field(default_factory=list)


def status_modulo() -> dict:
    """Pra uso pela aba SAUDE DOS DADOS/CONFIG se algum dia quiser
    exibir 'X: desligado, motivo Y' - nao chamado por nenhuma UI ainda
    (modulo fora do grafo de import do app, ver docstring)."""
    return {"disponivel": DISPONIVEL, "motivo": MOTIVO_INDISPONIVEL}


def buscar_sinais(*_args, **_kwargs):
    """Nunca implementado enquanto DISPONIVEL=False - lanca explicito
    em vez de retornar [] (que pareceria 'buscou e nao achou nada',
    falso-negativo) ou dado inventado (pior ainda)."""
    raise NotImplementedError(
        "Integracao com X nao disponivel - ver data.x_signals.MOTIVO_INDISPONIVEL"
    )
