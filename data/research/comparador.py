# -*- coding: utf-8 -*-
"""Agente Comparador de Casas de Research (Fase D, 2026-10-30, pedido
do Rodrigo) - le a biblioteca PERMANENTE de premissas/projecoes
(research_premissas, ver sql/research_premissas.sql e
data/research/store.py:listar_premissas) e monta uma comparacao
estruturada entre casas de research pra UM ticker: estado atual por
casa, dispersao de preco-alvo, divergencias (numerica/qualitativa/
premissas), evolucao historica e um relatorio determinístico com
rastreabilidade obrigatoria.

Nenhuma chamada de IA nesta integracao: tudo aqui e calculo puro sobre
dado JA estruturado por outra pipeline (resumir.py, feita por outro
agente); confirmar isso e' inclusive um teste obrigatorio
(tests/test_research_comparador.py:test_modulo_nao_importa_nada_de_ia).

============================================================
API PUBLICA (pensada pra ser chamada por UI - ui/analises_tab.py - e,
numa 3a etapa feita por outra pessoa, por jobs/coordenador.py):
    comparar_ticker(ticker: str) -> dict
    montar_relatorio_comparativo(ticker: str) -> dict
    CATEGORIA_OTIMISTA / CATEGORIA_NEUTRO / CATEGORIA_CAUTELOSO /
    CATEGORIA_NAO_CLASSIFICADO (constantes de categoria, uteis pra UI
    colorir/rotular sem duplicar o dicionario de mapeamento)

INTERNAS (prefixo `_`, podem mudar de assinatura sem aviso - nao
importar fora deste modulo):
    tudo mais abaixo.
============================================================

GAPS HONESTOS (reportados, nunca inventados/estimados):
- "riscos": research_premissas NAO tem campo de riscos estruturado -
  a extracao atual (data/research/resumir.py) nunca populou isso.
  Reportado em todo retorno como disponivel=False + motivo.
- ROE/ROIC/outros indicadores de rentabilidade: tambem nao sao
  extraidos por nenhuma pipeline hoje (projecoes so' tem as chaves
  receita/ebitda_margem/lucro, quando explicitas no texto original).
  Mesmo tratamento: disponivel=False + motivo, nunca um valor chutado.

PREMISSA DE MOEDA (documentada aqui, nunca implicita): todo `preco_alvo`
usado por este modulo e tratado como BRL - o universo de tickers do
PREGAO nesta funcao e' B3 (acoes locais), sem ADR/BDR cross-currency.
Nao ha conversao de cambio nem deteccao de moeda por ticker. Se um dia
este comparador precisar cobrir um ticker com preco-alvo em outra moeda,
isso exige tratamento explicito ANTES de comparar precos entre casas
(nunca comparar numeros de moedas diferentes como se fossem o mesmo
dado) - hoje e' um gap assumido e documentado, nao resolvido.
"""

import statistics
from datetime import datetime

from data.market_researcher import cobertura_cruzada_casas
from data.research import historico
from data.research.store import listar_premissas

# ============================================================
# Normalizacao de recomendacao (heuristica PEQUENA e EXPLICITA, NUNCA um
# classificador de IA) - `recomendacao` em research_premissas e' texto
# LIVRE por casa (cada uma escreve do seu jeito). Este dicionario cobre
# so' os termos mais comuns observados nas casas hoje monitoradas
# (Genial/XP/BTG/Monte Bravo/Nord) + termos internacionais genericos de
# equity research (OUTPERFORM/OVERWEIGHT/HOLD/UNDERPERFORM etc, usados
# por sell-side em ingles). Qualquer texto que nao bata EXATAMENTE
# (apos strip+upper) com uma chave aqui vira CATEGORIA_NAO_CLASSIFICADO -
# nunca chuta uma categoria por semelhanca/sinonimo nao listado.
#
# Extensivel: pra cobrir um termo novo de verdade visto numa casa nova,
# adicione a chave aqui (maiuscula, texto exato da casa) - nunca inferida
# em tempo de execucao.
# ============================================================
CATEGORIA_OTIMISTA = "OTIMISTA"
CATEGORIA_NEUTRO = "NEUTRO"
CATEGORIA_CAUTELOSO = "CAUTELOSO"
CATEGORIA_NAO_CLASSIFICADO = "NAO_CLASSIFICADO"

_CATEGORIAS_RECOMENDACAO = {CATEGORIA_OTIMISTA, CATEGORIA_NEUTRO, CATEGORIA_CAUTELOSO}

_MAPA_RECOMENDACAO = {
    # OTIMISTA
    "COMPRA": CATEGORIA_OTIMISTA,
    "COMPRAR": CATEGORIA_OTIMISTA,
    "OUTPERFORM": CATEGORIA_OTIMISTA,
    "OVERWEIGHT": CATEGORIA_OTIMISTA,
    "STRONG BUY": CATEGORIA_OTIMISTA,
    "BUY": CATEGORIA_OTIMISTA,
    "ADICIONAR": CATEGORIA_OTIMISTA,
    # NEUTRO
    "MANTER": CATEGORIA_NEUTRO,
    "NEUTRO": CATEGORIA_NEUTRO,
    "NEUTRAL": CATEGORIA_NEUTRO,
    "MARKET PERFORM": CATEGORIA_NEUTRO,
    "HOLD": CATEGORIA_NEUTRO,
    "EQUAL WEIGHT": CATEGORIA_NEUTRO,
    "EQUALWEIGHT": CATEGORIA_NEUTRO,
    # CAUTELOSO
    "VENDA": CATEGORIA_CAUTELOSO,
    "VENDER": CATEGORIA_CAUTELOSO,
    "UNDERPERFORM": CATEGORIA_CAUTELOSO,
    "UNDERWEIGHT": CATEGORIA_CAUTELOSO,
    "REDUCE": CATEGORIA_CAUTELOSO,
    "SELL": CATEGORIA_CAUTELOSO,
    "REDUZIR": CATEGORIA_CAUTELOSO,
}


def _normalizar_recomendacao(texto):
    """None quando a casa simplesmente nao informou recomendacao (campo
    ausente - diferente de ter informado algo nao reconhecido).
    CATEGORIA_NAO_CLASSIFICADO quando ha texto mas ele nao bate com o
    dicionario (heuristica limitada de proposito - nunca chuta)."""
    if not texto:
        return None
    chave = str(texto).strip().upper()
    if not chave:
        return None
    return _MAPA_RECOMENDACAO.get(chave, CATEGORIA_NAO_CLASSIFICADO)


# ============================================================
# Regra de comparabilidade (item 7 do pedido) - NUNCA comparar valores
# de natureza diferente (ex: preco_alvo numerico vs projecoes.receita
# texto livre) mesmo que estejam "no mesmo lugar" do dict. Cada campo
# so e' comparavel com ele mesmo entre casas distintas.
# ============================================================
CAMPO_PRECO_ALVO = "preco_alvo"
CAMPO_RECOMENDACAO = "recomendacao"
CAMPO_DATA_PUBLICACAO = "data_publicacao"
CAMPO_PROJECAO_RECEITA = "projecoes.receita"
CAMPO_PROJECAO_EBITDA_MARGEM = "projecoes.ebitda_margem"
CAMPO_PROJECAO_LUCRO = "projecoes.lucro"

_CAMPOS_COMPARAVEIS = {
    CAMPO_PRECO_ALVO, CAMPO_RECOMENDACAO, CAMPO_DATA_PUBLICACAO,
    CAMPO_PROJECAO_RECEITA, CAMPO_PROJECAO_EBITDA_MARGEM, CAMPO_PROJECAO_LUCRO,
}


def _comparavel(campo_a: str, campo_b: str) -> bool:
    """True so' quando os dois campos sao EXATAMENTE o mesmo campo
    conhecido (preco_alvo com preco_alvo, projecoes.receita com
    projecoes.receita etc) - nunca compara campos de natureza
    diferente (ex: preco_alvo com projecoes.receita), e nunca confunde
    `data_publicacao` (metadado de QUANDO a casa publicou) com qualquer
    periodo projetado mencionado DENTRO do texto livre de `projecoes`
    (ex: "crescimento de 12% a.a. nos proximos 3 anos" - esse texto
    nunca e parseado pra um ano especifico, e preservado como a casa
    escreveu). Campo desconhecido (fora de _CAMPOS_COMPARAVEIS) nunca e
    comparavel com nada, por seguranca."""
    if campo_a not in _CAMPOS_COMPARAVEIS or campo_b not in _CAMPOS_COMPARAVEIS:
        return False
    return campo_a == campo_b


# ============================================================
# Agrupamento por casa + identificacao do estado "atual"
# ============================================================

def _chave_recencia(publicacao: dict) -> datetime:
    """Data pra ordenar publicacoes da mais recente pra mais antiga:
    data_publicacao (texto 'YYYY-MM-DD') quando presente e nao vazia,
    com fallback pra extraido_em (timestamptz) - NUNCA inventa uma data
    quando as duas faltam (cai pra datetime.min, fica como a mais
    antiga possivel, nunca "ganha" a posicao de mais recente por
    acidente)."""
    bruto = publicacao.get(CAMPO_DATA_PUBLICACAO) or publicacao.get("extraido_em")
    if not bruto:
        return datetime.min
    texto = str(bruto).strip()
    if not texto:
        return datetime.min
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return datetime.strptime(texto[:10], "%Y-%m-%d")
    except ValueError:
        return datetime.min


def _agrupar_por_casa(publicacoes: list) -> dict:
    """{casa: {"atual": publicacao_mais_recente, "todas": [todas as
    publicacoes da casa, mais recente primeiro]}} - preserva TODAS as
    publicacoes (nao so' a mais recente) pra seção de evolucao
    historica/rastreabilidade, mesmo que o "estado atual" exibido na
    tabela comparativa use so' a mais recente."""
    por_casa = {}
    for publicacao in publicacoes:
        por_casa.setdefault(publicacao["casa"], []).append(publicacao)
    agrupado = {}
    for casa, pubs in por_casa.items():
        ordenadas = sorted(pubs, key=_chave_recencia, reverse=True)
        agrupado[casa] = {"atual": ordenadas[0], "todas": ordenadas}
    return agrupado


# ============================================================
# Dispersao de precos-alvo - NUNCA trata ausencia (None) como zero;
# uma casa sem preco_alvo e EXCLUIDA do calculo, nunca conta como 0
# (contar como 0 distorceria media/min/max pra baixo de forma enganosa).
# ============================================================

def _dispersao_precos_alvo(estado_atual_por_casa: dict) -> dict:
    """min/max/media/mediana SO' entre casas com preco_alvo NUMERICO
    (int/float, nunca bool - bool e subclasse de int em Python) no
    estado mais recente. LIMIAR documentado e testavel: menos de 2
    casas com preco_alvo numerico = `amostra_insuficiente` (min/max/
    media/mediana so' informam algo sobre DISPERSAO com pelo menos 2
    pontos - com 1 valor so' nao ha dispersao pra medir, com 0 nao ha
    nada pra calcular). O campo `resumo` sempre deixa explicito
    QUANTAS casas sustentam o numero (ex: "calculado com 2 de 3 casas"),
    nunca silencia a exclusao de quem nao tinha o dado."""
    n_total = len(estado_atual_por_casa)
    validos = {
        casa: info["atual"].get(CAMPO_PRECO_ALVO)
        for casa, info in estado_atual_por_casa.items()
        if isinstance(info["atual"].get(CAMPO_PRECO_ALVO), (int, float))
        and not isinstance(info["atual"].get(CAMPO_PRECO_ALVO), bool)
    }
    n_validos = len(validos)
    amostra_insuficiente = n_validos < 2

    base = {
        "moeda": "BRL",  # ver nota de moeda no docstring do modulo/comparar_ticker
        "n_casas_total": n_total,
        "n_casas_com_preco_alvo": n_validos,
        "amostra_insuficiente": amostra_insuficiente,
        "precos_por_casa": validos,
    }
    if n_validos == 0:
        base.update({
            "minimo": None, "maximo": None, "media": None, "mediana": None,
            "resumo": f"nenhuma casa com preco-alvo numerico (0 de {n_total} casa(s) cobrindo o ticker).",
        })
        return base
    if amostra_insuficiente:  # exatamente 1
        valor = next(iter(validos.values()))
        base.update({
            "minimo": valor, "maximo": valor, "media": valor, "mediana": valor,
            "resumo": f"apenas 1 de {n_total} casa(s) com preco-alvo numerico - dispersao nao e significativa com 1 dado so'.",
        })
        return base
    valores = list(validos.values())
    base.update({
        "minimo": min(valores), "maximo": max(valores),
        "media": statistics.mean(valores), "mediana": statistics.median(valores),
        "resumo": f"calculado com {n_validos} de {n_total} casa(s) cobrindo o ticker.",
    })
    return base


# ============================================================
# Divergencias: NUMERICA (preco-alvo) e QUALITATIVA (categoria de
# recomendacao) sao coisas DIFERENTES - nunca confundidas uma com a
# outra no retorno.
# ============================================================

_LIMIAR_DIVERGENCIA_MIN_CASAS = 2  # mesmo limiar usado na dispersao numerica


def _casa_mais_otimista_cautelosa(estado_atual_por_casa: dict):
    """(casa_mais_otimista, casa_mais_cautelosa, criterio_usado).
    Criterio documentado (resolve ambiguidade explicitamente, nunca
    escondida): preco-alvo NUMERICO tem prioridade quando >=2 casas o
    tem (mais objetivo, direto em R$) - so' cai pra categoria
    qualitativa (OTIMISTA > NEUTRO > CAUTELOSO) quando menos de 2 casas
    tem preco-alvo numerico. Empate e' resolvido pela ordem alfabetica
    da casa (determinismo), nunca arbitrario - por isso as duas
    estruturas sao montadas com `sorted()` antes do max()/min()."""
    com_preco = {
        casa: info["atual"].get(CAMPO_PRECO_ALVO)
        for casa, info in sorted(estado_atual_por_casa.items())
        if isinstance(info["atual"].get(CAMPO_PRECO_ALVO), (int, float))
        and not isinstance(info["atual"].get(CAMPO_PRECO_ALVO), bool)
    }
    if len(com_preco) >= 2:
        mais_otimista = max(com_preco, key=com_preco.get)
        mais_cautelosa = min(com_preco, key=com_preco.get)
        return mais_otimista, mais_cautelosa, (
            "preco_alvo (maior/menor preco-alvo numerico entre as casas com esse dado - BRL)"
        )

    ordem_categoria = {CATEGORIA_CAUTELOSO: 0, CATEGORIA_NEUTRO: 1, CATEGORIA_OTIMISTA: 2}
    com_categoria = {
        casa: ordem_categoria[info["categoria"]]
        for casa, info in sorted(estado_atual_por_casa.items())
        if info.get("categoria") in ordem_categoria
    }
    if len(com_categoria) >= 2:
        mais_otimista = max(com_categoria, key=com_categoria.get)
        mais_cautelosa = min(com_categoria, key=com_categoria.get)
        return mais_otimista, mais_cautelosa, (
            "categoria_recomendacao (OTIMISTA > NEUTRO > CAUTELOSO - menos de 2 casas tinham "
            "preco-alvo numerico suficiente pra decidir por esse criterio)"
        )
    return None, None, "dado insuficiente (menos de 2 casas com preco-alvo numerico OU categoria de recomendacao classificada)"


def _divergencia_recomendacao(estado_atual_por_casa: dict, dispersao: dict) -> dict:
    """Divergencia NUMERICA (precos-alvo distantes entre si) e
    QUALITATIVA (categorias de recomendacao diferentes) - calculadas
    de forma independente, cada uma com seu proprio `amostra_insuficiente`
    e contagem de quantas casas sustentam aquela conclusao especifica."""
    n_total = len(estado_atual_por_casa)

    numerica = (not dispersao["amostra_insuficiente"]) and (dispersao["maximo"] != dispersao["minimo"])

    categorias_validas = {
        casa: info["categoria"]
        for casa, info in estado_atual_por_casa.items()
        if info.get("categoria") in _CATEGORIAS_RECOMENDACAO
    }
    n_com_categoria = len(categorias_validas)
    amostra_insuficiente_qualitativa = n_com_categoria < _LIMIAR_DIVERGENCIA_MIN_CASAS
    qualitativa = (not amostra_insuficiente_qualitativa) and len(set(categorias_validas.values())) > 1

    mais_otimista, mais_cautelosa, criterio = _casa_mais_otimista_cautelosa(estado_atual_por_casa)

    return {
        "n_casas_total": n_total,
        "numerica": numerica,
        "n_casas_com_preco_alvo": dispersao["n_casas_com_preco_alvo"],
        "qualitativa": qualitativa,
        "n_casas_com_categoria_classificada": n_com_categoria,
        "amostra_insuficiente_qualitativa": amostra_insuficiente_qualitativa,
        "casa_mais_otimista": mais_otimista,
        "casa_mais_cautelosa": mais_cautelosa,
        "criterio_otimismo": criterio,
    }


def _divergencia_premissas(estado_atual_por_casa: dict) -> dict:
    """Premissas (texto livre, 1 frase cada, do estado mais recente de
    cada casa) que aparecem em ALGUMAS casas e nao em outras pro mesmo
    ticker - so' reporta o FATO (presente aqui/ausente la'), nunca
    infere PORQUE elas divergem. LIMIAR documentado: menos de 2 casas
    com pelo menos 1 premissa extraida = `amostra_insuficiente` (nao ha
    base pra comparar premissa entre casas com 0 ou 1 fonte)."""
    n_total = len(estado_atual_por_casa)
    por_casa = {
        casa: set(info["atual"].get("premissas") or [])
        for casa, info in estado_atual_por_casa.items()
    }
    n_com_premissas = sum(1 for conjunto in por_casa.values() if conjunto)
    todas_premissas = set()
    for conjunto in por_casa.values():
        todas_premissas |= conjunto

    divergentes = []
    for premissa in sorted(todas_premissas):
        presentes = sorted(casa for casa, conjunto in por_casa.items() if premissa in conjunto)
        ausentes = sorted(casa for casa in por_casa if casa not in presentes)
        if ausentes:  # aparece em algumas casas, nao em todas - e' a divergencia
            divergentes.append({
                "premissa": premissa,
                "casas_que_mencionam": presentes,
                "casas_que_nao_mencionam": ausentes,
            })

    return {
        "n_casas_total": n_total,
        "n_casas_com_premissas_extraidas": n_com_premissas,
        "amostra_insuficiente": n_com_premissas < 2,
        "premissas_divergentes": divergentes,
    }


# ============================================================
# Evolucao historica/revisoes recentes - REUTILIZA data/research/
# historico.py (nunca reimplementa deteccao de mudanca do zero).
# "preco-alvo ATUAL" (mais recente) e "preco-alvo HISTORICO" (qualquer
# snapshot/publicacao anterior) sao rotulos SEPARADOS no retorno, nunca
# misturados.
# ============================================================

def _evolucao_historica(ticker: str, agrupado: dict) -> dict:
    """Por casa: estado ATUAL (mais recente) + duas fontes de HISTORICO,
    nunca confundidas com o atual:
    - `publicacoes_historicas`: as demais publicacoes da MESMA casa pro
      mesmo ticker ja persistidas em research_premissas (qualquer casa -
      e' a biblioteca permanente de relatorios reais, com link/titulo).
    - `historico_estruturado`: snapshots de MUDANCA real de
      recomendacao/preco-alvo (data/research/historico.py:
      historico_ticker) - hoje so' tem dado de verdade pra casas que
      alimentam research_recomendacoes_historico (so' Genial Analisa na
      pratica, ver docstring de historico.py); outras casas voltam lista
      vazia com `historico_estruturado_disponivel=False` (nao e' erro,
      e' so' ausencia real dessa fonte especifica pra essa casa)."""
    evolucao = {}
    for casa, info in agrupado.items():
        atual = info["atual"]
        anteriores = info["todas"][1:]

        try:
            snapshots = historico.historico_ticker(casa, ticker, limite=10)
        except Exception:
            snapshots = []
        try:
            mudancas_hoje_casa = historico.mudancas_hoje(casa)
        except Exception:
            mudancas_hoje_casa = []
        mudou_hoje = any(m.get("ticker") == ticker for m in mudancas_hoje_casa)

        evolucao[casa] = {
            "preco_alvo_atual": atual.get(CAMPO_PRECO_ALVO),
            "recomendacao_atual": atual.get(CAMPO_RECOMENDACAO),
            "data_publicacao_atual": atual.get(CAMPO_DATA_PUBLICACAO),
            "publicacoes_historicas": [
                {
                    "data_publicacao": pub.get(CAMPO_DATA_PUBLICACAO),
                    "titulo": pub.get("titulo"),
                    "link": pub.get("link"),
                    "recomendacao": pub.get(CAMPO_RECOMENDACAO),
                    "preco_alvo": pub.get(CAMPO_PRECO_ALVO),
                }
                for pub in anteriores
            ],
            "historico_estruturado_disponivel": bool(snapshots),
            "historico_estruturado": [
                {
                    "recomendacao": s.get(CAMPO_RECOMENDACAO),
                    "preco_alvo": s.get(CAMPO_PRECO_ALVO),
                    "capturado_em": s.get("capturado_em"),
                }
                for s in snapshots
            ],
            "mudou_recomendacao_ou_alvo_hoje": mudou_hoje,
        }
    return evolucao


# ============================================================
# API PUBLICA
# ============================================================

def comparar_ticker(ticker: str) -> dict:
    """Comparacao estruturada entre casas de research pra UM ticker,
    lendo so' a biblioteca PERMANENTE (research_premissas) - nunca
    lanca excecao: banco fora do ar e falta de publicacao sao estados
    explicitos no retorno, nunca um erro propagado pra quem chama.

    PREMISSA DE MOEDA (ver tambem docstring do modulo): todo preco_alvo
    aqui e' tratado como BRL (universo B3, sem ADR/BDR cross-currency
    nesta funcao) - nenhuma conversao de cambio e feita.

    Retornos possiveis:
    - {"disponivel": False, "motivo": "banco indisponivel"} - Supabase
      fora do ar (listar_premissas devolveu None).
    - {"disponivel": True, "ticker": ..., "casas": [], "motivo": ...} -
      banco respondeu, zero publicacao estruturada pra esse ticker.
    - dict completo (ver chaves abaixo) quando ha' pelo menos 1
      publicacao de pelo menos 1 casa."""
    ticker = (ticker or "").strip().upper()
    publicacoes = listar_premissas(tickers=[ticker])
    if publicacoes is None:
        return {"disponivel": False, "motivo": "banco indisponivel"}
    if not publicacoes:
        return {
            "disponivel": True, "ticker": ticker, "casas": [],
            "motivo": "sem publicacoes estruturadas para este ticker na biblioteca permanente de research",
            # mesmas chaves honestas do retorno completo abaixo (ver comentario
            # la') - sem isso, montar_relatorio_comparativo quebrava com
            # KeyError ao tentar acessar comparacao["riscos"] pra um ticker
            # sem nenhuma publicacao (achado real na auditoria, 2026-10-30).
            "riscos": {
                "disponivel": False,
                "motivo": "pipeline de extracao atual (research_premissas) nao captura riscos estruturalmente - "
                          "gap conhecido, fora do escopo desta implementacao",
            },
            "indicadores_adicionais": {
                "disponivel": False,
                "motivo": "ROE/ROIC e outros indicadores de rentabilidade nao sao extraidos por nenhuma pipeline "
                          "hoje (projecoes so' tem as chaves receita/ebitda_margem/lucro, quando explicitas no "
                          "texto original) - gap conhecido, fora do escopo desta implementacao",
            },
        }

    agrupado = _agrupar_por_casa(publicacoes)
    estado_atual_por_casa = {
        casa: {
            "atual": info["atual"],
            "categoria": _normalizar_recomendacao(info["atual"].get(CAMPO_RECOMENDACAO)),
        }
        for casa, info in agrupado.items()
    }

    dispersao = _dispersao_precos_alvo(estado_atual_por_casa)
    divergencia_recomendacao = _divergencia_recomendacao(estado_atual_por_casa, dispersao)
    divergencia_premissas = _divergencia_premissas(estado_atual_por_casa)
    evolucao_historica = _evolucao_historica(ticker, agrupado)

    try:
        cobertura_cruzada = cobertura_cruzada_casas(ticker)
    except Exception:
        # cobertura_cruzada_casas ja se protege internamente - este
        # try/except e' so' defesa em profundidade (mesmo padrao de
        # data/market_researcher.py), nunca deve disparar na pratica.
        cobertura_cruzada = None

    return {
        "disponivel": True,
        "ticker": ticker,
        "casas": sorted(agrupado.keys()),
        "estado_atual_por_casa": estado_atual_por_casa,
        "publicacoes_por_casa": {casa: info["todas"] for casa, info in agrupado.items()},
        "dispersao_precos_alvo": dispersao,
        "divergencia_recomendacao": divergencia_recomendacao,
        "divergencia_premissas": divergencia_premissas,
        "evolucao_historica": evolucao_historica,
        "cobertura_cruzada": cobertura_cruzada,
        "riscos": {
            "disponivel": False,
            "motivo": "pipeline de extracao atual (research_premissas) nao captura riscos estruturalmente - "
                      "gap conhecido, fora do escopo desta implementacao",
        },
        "indicadores_adicionais": {
            "disponivel": False,
            "motivo": "ROE/ROIC e outros indicadores de rentabilidade nao sao extraidos por nenhuma pipeline "
                      "hoje (projecoes so' tem as chaves receita/ebitda_margem/lucro, quando explicitas no "
                      "texto original) - gap conhecido, fora do escopo desta implementacao",
        },
    }


def _tabela_comparativa(estado_atual_por_casa: dict) -> list:
    """Uma linha por casa (estado mais recente) - None explicito (nunca
    omitido) onde a casa nao informou aquele campo."""
    linhas = []
    for casa in sorted(estado_atual_por_casa):
        atual = estado_atual_por_casa[casa]["atual"]
        projecoes = atual.get("projecoes") or {}
        linhas.append({
            "casa": casa,
            "data_publicacao": atual.get(CAMPO_DATA_PUBLICACAO),
            "tipo_documento": atual.get("tipo_documento"),
            "recomendacao_original": atual.get(CAMPO_RECOMENDACAO),
            "recomendacao_categoria": estado_atual_por_casa[casa]["categoria"],
            "preco_alvo": atual.get(CAMPO_PRECO_ALVO),
            "projecao_receita": projecoes.get("receita"),
            "projecao_ebitda_margem": projecoes.get("ebitda_margem"),
            "projecao_lucro": projecoes.get("lucro"),
            "titulo": atual.get("titulo"),
            "link": atual.get("link"),
        })
    return linhas


_LIMIAR_CONSENSO_MIN_CASAS = 2


def _consenso(estado_atual_por_casa: dict) -> dict:
    """Categoria de recomendacao mais comum entre o estado atual das
    casas + contagem por categoria (inclui SEM_RECOMENDACAO quando a
    casa nao informou nada, e NAO_CLASSIFICADO quando informou algo
    fora do dicionario - nenhuma das duas conta como "classificada").
    LIMIAR documentado: menos de 2 casas com recomendacao CLASSIFICADA
    (OTIMISTA/NEUTRO/CAUTELOSO) = `amostra_insuficiente` (nao faz
    sentido falar em "consenso" com 0 ou 1 dado classificavel). Empate
    entre categorias com a mesma contagem maxima = sem categoria mais
    comum (nunca escolhe uma arbitrariamente)."""
    n_total = len(estado_atual_por_casa)
    contagem = {}
    for info in estado_atual_por_casa.values():
        categoria = info["categoria"] or "SEM_RECOMENDACAO"
        contagem[categoria] = contagem.get(categoria, 0) + 1

    n_classificadas = sum(n for categoria, n in contagem.items() if categoria in _CATEGORIAS_RECOMENDACAO)
    amostra_insuficiente = n_classificadas < _LIMIAR_CONSENSO_MIN_CASAS

    categoria_mais_comum = None
    empate = False
    if contagem:
        maximo = max(contagem.values())
        candidatos = sorted(categoria for categoria, n in contagem.items() if n == maximo)
        if len(candidatos) == 1:
            categoria_mais_comum = candidatos[0]
        else:
            empate = True

    return {
        "n_casas_total": n_total,
        "n_casas_com_recomendacao_classificada": n_classificadas,
        "amostra_insuficiente": amostra_insuficiente,
        "categoria_mais_comum": categoria_mais_comum,
        "contagem_por_categoria": contagem,
        "empate": empate,
    }


def _resumo_executivo(ticker: str, estado_atual_por_casa: dict, dispersao: dict, consenso: dict) -> str:
    """Texto determinístico por template/f-string - NUNCA gerado por
    chamada de IA (ver docstring do modulo)."""
    n = len(estado_atual_por_casa)
    partes = [f"{n} casa(s) de research cobrem {ticker} na biblioteca permanente."]
    if not dispersao["amostra_insuficiente"]:
        partes.append(
            f"Preco-alvo entre R$ {dispersao['minimo']:.2f} e R$ {dispersao['maximo']:.2f} "
            f"(media R$ {dispersao['media']:.2f}; {dispersao['resumo']})"
        )
    else:
        partes.append(f"Dispersao de preco-alvo: {dispersao['resumo']}")
    if consenso["categoria_mais_comum"]:
        partes.append(
            f"Consenso: {consenso['categoria_mais_comum']} "
            f"({consenso['contagem_por_categoria'][consenso['categoria_mais_comum']]} de "
            f"{consenso['n_casas_com_recomendacao_classificada']} casa(s) com recomendacao classificada)."
        )
    elif consenso["amostra_insuficiente"]:
        partes.append(
            f"Sem consenso calculavel: so' {consenso['n_casas_com_recomendacao_classificada']} de {n} "
            "casa(s) tem recomendacao classificada (minimo de 2 exigido)."
        )
    else:
        partes.append("Sem consenso claro (empate entre categorias de recomendacao).")
    return " ".join(partes)


def _fontes_evidencias(agrupado_publicacoes_por_casa: dict) -> list:
    """Uma entrada por publicacao REAL usada em qualquer secao do
    relatorio (tabela comparativa usa a mais recente de cada casa;
    revisoes_recentes usa as demais) - deduplicada por link. Toda
    conclusao do relatorio remonta a pelo menos 1 entrada aqui."""
    fontes = []
    vistos = set()
    for casa in sorted(agrupado_publicacoes_por_casa):
        for publicacao in agrupado_publicacoes_por_casa[casa]:
            link = publicacao.get("link")
            if link in vistos:
                continue
            vistos.add(link)
            fontes.append({
                "casa": casa, "link": link,
                "data_publicacao": publicacao.get(CAMPO_DATA_PUBLICACAO),
                "titulo": publicacao.get("titulo"),
            })
    return fontes


def _pontos_atencao(comparacao: dict) -> list:
    """Lista DETERMINISTICA de avisos (nunca interpretacao/opiniao) -
    cobertura ausente, dados faltantes por casa, amostra insuficiente
    em qualquer secao agregada."""
    avisos = []
    cobertura_cruzada = comparacao.get("cobertura_cruzada")
    if cobertura_cruzada and cobertura_cruzada.get("sem_cobertura"):
        avisos.append(
            f"Sem cobertura recente (janela de {cobertura_cruzada.get('janela_dias', 30)} dias) de: "
            f"{', '.join(cobertura_cruzada['sem_cobertura'])}."
        )

    for casa, info in sorted(comparacao["estado_atual_por_casa"].items()):
        atual = info["atual"]
        if atual.get(CAMPO_PRECO_ALVO) is None:
            avisos.append(f"{casa}: sem preco-alvo numerico na publicacao mais recente.")
        if info["categoria"] == CATEGORIA_NAO_CLASSIFICADO:
            avisos.append(
                f"{casa}: recomendacao '{atual.get(CAMPO_RECOMENDACAO)}' nao reconhecida pelo mapeador "
                "(NAO_CLASSIFICADO)."
            )

    dispersao = comparacao["dispersao_precos_alvo"]
    if dispersao["amostra_insuficiente"]:
        avisos.append(f"Dispersao de preco-alvo: {dispersao['resumo']}")

    consenso = comparacao.get("_consenso_para_pontos_atencao")
    if consenso and consenso["amostra_insuficiente"]:
        avisos.append(
            f"Consenso de recomendacao: amostra insuficiente ({consenso['n_casas_com_recomendacao_classificada']} "
            f"de {consenso['n_casas_total']} casa(s) com recomendacao classificada; minimo de 2 exigido)."
        )

    divergencia = comparacao["divergencia_recomendacao"]
    if divergencia["amostra_insuficiente_qualitativa"]:
        avisos.append(
            f"Divergencia qualitativa: amostra insuficiente ({divergencia['n_casas_com_categoria_classificada']} "
            f"de {divergencia['n_casas_total']} casa(s) com categoria classificada; minimo de 2 exigido)."
        )

    divergencia_premissas = comparacao["divergencia_premissas"]
    if divergencia_premissas["amostra_insuficiente"]:
        avisos.append(
            f"Divergencia de premissas: amostra insuficiente ({divergencia_premissas['n_casas_com_premissas_extraidas']} "
            f"de {divergencia_premissas['n_casas_total']} casa(s) com premissas extraidas; minimo de 2 exigido)."
        )

    return avisos


def montar_relatorio_comparativo(ticker: str) -> dict:
    """Relatorio estruturado (dado puro, NUNCA texto narrativo gerado
    por IA) organizado nas 9 secoes pedidas - chama comparar_ticker e
    so' reorganiza/formata o que ja' foi calculado la', sem nenhuma
    consulta ou calculo novo fora do que esta documentado abaixo
    (resumo_executivo/consenso/tabela/pontos_atencao/fontes sao
    puramente derivados do dict de comparar_ticker)."""
    ticker_normalizado = (ticker or "").strip().upper()
    comparacao = comparar_ticker(ticker_normalizado)

    if not comparacao.get("disponivel"):
        return {
            "disponivel": False, "ticker": ticker_normalizado,
            "motivo": comparacao.get("motivo") or "indisponivel",
        }

    if not comparacao.get("casas"):
        motivo = comparacao.get("motivo") or "sem publicacoes estruturadas"
        return {
            "disponivel": True, "ticker": comparacao["ticker"],
            "resumo_executivo": f"Nenhuma casa de research monitorada tem publicacao estruturada sobre "
                                 f"{comparacao['ticker']} na biblioteca permanente de research. {motivo}.",
            "consenso": {
                "n_casas_total": 0, "n_casas_com_recomendacao_classificada": 0,
                "amostra_insuficiente": True, "categoria_mais_comum": None,
                "contagem_por_categoria": {}, "empate": False,
            },
            "tabela_comparativa": [],
            "dispersao_precos_alvo": {
                "moeda": "BRL", "n_casas_total": 0, "n_casas_com_preco_alvo": 0,
                "amostra_insuficiente": True, "precos_por_casa": {},
                "minimo": None, "maximo": None, "media": None, "mediana": None,
                "resumo": motivo,
            },
            "divergencias_premissas": {
                "recomendacao": {
                    "n_casas_total": 0, "numerica": False, "n_casas_com_preco_alvo": 0,
                    "qualitativa": False, "n_casas_com_categoria_classificada": 0,
                    "amostra_insuficiente_qualitativa": True, "casa_mais_otimista": None,
                    "casa_mais_cautelosa": None,
                    "criterio_otimismo": "dado insuficiente (nenhuma casa cobre o ticker)",
                },
                "premissas": {
                    "n_casas_total": 0, "n_casas_com_premissas_extraidas": 0,
                    "amostra_insuficiente": True, "premissas_divergentes": [],
                },
            },
            "revisoes_recentes": {},
            "riscos": comparacao["riscos"],
            "indicadores_adicionais": comparacao["indicadores_adicionais"],
            "pontos_atencao": [motivo],
            "fontes_evidencias": [],
        }

    estado_atual_por_casa = comparacao["estado_atual_por_casa"]
    tabela = _tabela_comparativa(estado_atual_por_casa)
    consenso = _consenso(estado_atual_por_casa)
    resumo = _resumo_executivo(comparacao["ticker"], estado_atual_por_casa, comparacao["dispersao_precos_alvo"], consenso)

    # usado so' por _pontos_atencao (chave privada, nunca exposta no
    # retorno final) - evita recalcular _consenso duas vezes.
    comparacao["_consenso_para_pontos_atencao"] = consenso
    pontos_atencao = _pontos_atencao(comparacao)
    del comparacao["_consenso_para_pontos_atencao"]

    fontes = _fontes_evidencias(comparacao["publicacoes_por_casa"])

    return {
        "disponivel": True,
        "ticker": comparacao["ticker"],
        "resumo_executivo": resumo,
        "consenso": consenso,
        "tabela_comparativa": tabela,
        "dispersao_precos_alvo": comparacao["dispersao_precos_alvo"],
        "divergencias_premissas": {
            "recomendacao": comparacao["divergencia_recomendacao"],
            "premissas": comparacao["divergencia_premissas"],
        },
        "revisoes_recentes": comparacao["evolucao_historica"],
        "riscos": comparacao["riscos"],
        "indicadores_adicionais": comparacao["indicadores_adicionais"],
        "pontos_atencao": pontos_atencao,
        "fontes_evidencias": fontes,
    }
