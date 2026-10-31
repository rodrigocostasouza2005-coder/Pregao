# -*- coding: utf-8 -*-
"""X (Twitter) como fonte de DESCOBERTA de sinais - FASE 4 da auditoria
2026-10-09, LIGADO explicitamente (pedido do Rodrigo, 2026-10-30, ver
docs/x-radar-inteligencia-social-20261030.md) na camada data/x_radar/,
mas sem simular nenhuma coleta real: nenhuma funcao aqui retorna dado
inventado quando a credencial nao existe ou nao tem permissao de busca.

Verificado (pesquisa real, 2026-10-09, reconfirmado 2026-10-30 - nada
mudou): a API do X nao tem mais tier gratuito pra desenvolvedor novo
desde 06/02/2026 - o free tier antigo (que ja' nao incluia /search, so'
~50 leituras/dia) foi descontinuado, e o Basic ($200/mes fixo) foi
forcado pra cobranca por uso (pay-per-use, ~US$0,005 por leitura de
post) e nao aceita mais assinante novo. Busca/filtro de posts recentes
(o uso que este modulo precisa - "descobrir" sinais, nao so' ler um
post especifico) parece exigir tier Enterprise (a partir de
US$42.000/mes) ou pelo menos uma camada paga especifica - nenhuma fonte
confirma acesso de busca incluido no pay-per-use basico. Scraping
nao-oficial contorna controles de acesso (Termos de Servico do X) -
fora de cogitacao pelo mesmo principio ja aplicado a outras fontes
deste projeto (ver data/research/genial_lives.py: so' uma excecao
justificada, documentada, pra robots.txt do YouTube - scraping de
login/API privada do X e' categoria diferente e mais invasiva, nao
comparavel).

Conclusao: sem credencial nova e paga (nao aprovada), nao ha'
integracao viavel hoje. `status_credencial()` abaixo e' a unica funcao
que faz rede (1 chamada minima de validacao) e SO quando X_BEARER_TOKEN
existe - nunca presume sucesso so' por a variavel estar configurada
(tier Basic pago pode nao incluir /search, so' uma chamada real
confirma). `buscar_sinais()` nunca retorna [] nem dado inventado quando
indisponivel - lanca NotImplementedError com o motivo exato.

Import: so' data/x_radar/conector.py importa este modulo diretamente -
o resto do app (ui/*.py, app.py, outros modulos de data/) nunca deve
importar data.x_signals direto, sempre via data.x_radar (camada que
agrega classificacao/relevancia/cruzamento antes de qualquer UI ler
algo) - ver tests/test_x_signals.py test_7 (invariante atualizada
2026-10-30, nao mais 'nunca importado', e sim 'importado so por
data/x_radar')."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import requests

import config

TIMEOUT = 10
_BUSCA_URL = "https://api.twitter.com/2/tweets/search/recent"
_HEADERS_BASE = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}

# Mantido como constante estatica (nao recalculada a cada import) pra
# nao quebrar quem le DISPONIVEL direto (tests 1/2) - reflete o estado
# CONHECIDO e documentado acima. status_credencial() abaixo e' a
# verificacao DINAMICA e real (chamada de rede) que data/x_radar/
# conector.py usa de fato antes de qualquer tentativa de coleta -
# DISPONIVEL por si so nunca autoriza uma chamada.
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
    """Contrato de dados pra UM post bruto descoberto - preenchido por
    data/x_radar/conector.py quando houver credencial valida, nunca por
    este modulo sozinho.

    autor / link_original / horario_publicacao: preservados sempre que
    disponiveis - nunca normalizados/removidos.
    horario_captura: quando o PREGAO viu o post, separado de
    horario_publicacao (podem divergir bastante).
    chave_acontecimento: dedup por FATO, nao por post - varios posts
    (inclusive de contas diferentes) sobre o MESMO acontecimento
    compartilham a chave; calculada por data/x_radar/cruzamento.py (ex:
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
    post_id: str
    autor: str
    link_original: str
    horario_publicacao: datetime | None
    horario_captura: datetime
    contexto: str
    chave_acontecimento: str
    nivel_evidencia: NivelEvidencia
    estado: EstadoSinal
    conta_verificada: bool = False
    mesma_origem: bool = False
    evidencias_confirmacao: list = field(default_factory=list)


def status_modulo() -> dict:
    """Status ESTATICO documentado (motivo da pesquisa de 2026-10-09) -
    usado pela UI (ui/research_tab.py:render_radar_x, 'saude do
    conector') quando nenhuma credencial existe (caso de hoje). Quando
    X_BEARER_TOKEN estiver configurado, a UI deve preferir
    status_credencial() (abaixo, verificacao real) a este."""
    return {"disponivel": DISPONIVEL, "motivo": MOTIVO_INDISPONIVEL}


def status_credencial() -> dict:
    """Verificacao DINAMICA e real do acesso atual - NUNCA faz chamada
    de rede se nao houver token configurado (nada a verificar; evita
    erro de rede sem sentido em todo ambiente sem credencial, que e' o
    caso de hoje). Se houver token, faz EXATAMENTE 1 chamada minima
    (max_results=10, uma query generica) contra o endpoint de busca real
    - a mesma permissao que buscar_sinais() precisaria - e reporta o
    resultado real do HTTP, nunca presumido:

    - {'estado': 'sem_credencial', ...} - X_BEARER_TOKEN nao configurado.
    - {'estado': 'credencial_invalida', ...} - 401, token rejeitado.
    - {'estado': 'sem_permissao_busca', ...} - 403, token valido mas sem
      acesso ao endpoint de busca (ex: tier Basic sem essa permissao).
    - {'estado': 'limite_excedido', ...} - 429 ja' na validacao.
    - {'estado': 'erro_conexao', ...} - falha de rede/timeout.
    - {'estado': 'ok', ...} - busca real funcionou; motivo None.

    Nunca cacheia 'ok' permanentemente - quem chama decide a frequencia
    (ver data/x_radar/conector.py, mesmo espirito de TTL dos outros
    coletores)."""
    token = config.obter_credencial_x()
    if not token:
        return {"estado": "sem_credencial", "motivo": MOTIVO_INDISPONIVEL, "token_presente": False}
    headers = dict(_HEADERS_BASE, Authorization=f"Bearer {token}")
    try:
        resp = requests.get(_BUSCA_URL, headers=headers,
                             params={"query": "lang:pt -is:retweet", "max_results": 10},
                             timeout=TIMEOUT)
    except requests.RequestException as exc:
        return {"estado": "erro_conexao", "motivo": f"falha de rede ao validar credencial do X: {exc!r}", "token_presente": True}
    if resp.status_code == 401:
        return {"estado": "credencial_invalida", "motivo": "X_BEARER_TOKEN rejeitado (HTTP 401) pela API do X", "token_presente": True}
    if resp.status_code == 403:
        return {"estado": "sem_permissao_busca", "motivo": "credencial valida, mas sem permissao de busca (HTTP 403) - provavelmente o tier atual nao inclui /2/tweets/search/recent", "token_presente": True}
    if resp.status_code == 429:
        return {"estado": "limite_excedido", "motivo": "rate limit atingido ja na chamada de validacao (HTTP 429)", "token_presente": True}
    if resp.ok:
        return {"estado": "ok", "motivo": None, "token_presente": True}
    return {"estado": "erro_desconhecido", "motivo": f"HTTP {resp.status_code} inesperado ao validar credencial", "token_presente": True}


def _item_para_sinal(item: dict, autores_por_id: dict) -> Sinal:
    autor_id = item.get("author_id")
    autor_info = autores_por_id.get(autor_id, {})
    username = autor_info.get("username")
    link = f"https://x.com/{username}/status/{item['id']}" if username else f"https://x.com/i/web/status/{item['id']}"
    publicado_em = None
    if item.get("created_at"):
        try:
            publicado_em = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
        except ValueError:
            publicado_em = None
    return Sinal(
        post_id=str(item["id"]),
        autor=f"@{username}" if username else (autor_id or "desconhecido"),
        link_original=link,
        horario_publicacao=publicado_em,
        horario_captura=datetime.now(timezone.utc),
        contexto=item.get("text", ""),
        chave_acontecimento="",  # calculada por data/x_radar/cruzamento.py, nunca aqui
        nivel_evidencia=NivelEvidencia.NAO_CONFIRMADO,
        estado=EstadoSinal.DETECTADO,
        conta_verificada=bool(autor_info.get("verified", False)),
    )


def buscar_sinais(query: str, *, max_resultados: int = 50, desde: datetime | None = None,
                   max_paginas: int = 3) -> tuple[list[Sinal], dict]:
    """Busca posts recentes que combinem com `query` (sintaxe da API do
    X: termos, OR, from:handle, cashtags $PETR4 etc - ver
    data/x_radar/__init__.py pra como o universo configurado vira essa
    string). Pagina via meta.next_token ate max_paginas ou acabar.
    Dedup por post_id dentro do proprio lote (a persistencia, ver
    data/x_radar/store.py, faz upsert por post_id tambem - defesa em
    camadas, nunca confia so' numa).

    NUNCA retorna [] quando a causa real e' falta de acesso - lanca
    NotImplementedError com o `estado`/`motivo` exatos de
    status_credencial() em vez disso (uma lista vazia pareceria 'buscou
    e nao achou nada', falso-negativo que esconderia o problema real).

    Retorna (sinais, info_consumo) onde info_consumo tem
    {'leituras': N, 'limite_restante': int|None} pra
    data/x_radar/conector.py registrar em x_radar_consumo (sql/x_radar.sql)."""
    status = status_credencial()
    if status["estado"] != "ok":
        raise NotImplementedError(
            f"Integracao com X nao disponivel (estado={status['estado']!r}): {status['motivo']}"
        )

    token = config.obter_credencial_x()
    headers = dict(_HEADERS_BASE, Authorization=f"Bearer {token}")
    vistos: set[str] = set()
    sinais: list[Sinal] = []
    leituras = 0
    limite_restante = None
    proximo_token = None

    for _pagina in range(max_paginas):
        params = {
            "query": query,
            "max_results": min(max_resultados, 100),
            "tweet.fields": "created_at,author_id",
            "expansions": "author_id",
            "user.fields": "username,verified",
        }
        if desde is not None:
            params["start_time"] = desde.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if proximo_token:
            params["next_token"] = proximo_token

        resp = requests.get(_BUSCA_URL, headers=headers, params=params, timeout=TIMEOUT)
        leituras += 1
        limite_restante = resp.headers.get("x-rate-limit-remaining", limite_restante)
        if not resp.ok:
            raise NotImplementedError(
                f"Integracao com X falhou durante a busca (HTTP {resp.status_code}): {resp.text[:200]!r}"
            )
        corpo = resp.json()
        autores_por_id = {u["id"]: u for u in corpo.get("includes", {}).get("users", [])}
        for item in corpo.get("data", []):
            if item["id"] in vistos:
                continue
            vistos.add(item["id"])
            sinais.append(_item_para_sinal(item, autores_por_id))
            if len(sinais) >= max_resultados:
                break

        proximo_token = corpo.get("meta", {}).get("next_token")
        if not proximo_token or len(sinais) >= max_resultados:
            break

    info_consumo = {"leituras": leituras, "limite_restante": int(limite_restante) if limite_restante else None}
    return sinais, info_consumo
