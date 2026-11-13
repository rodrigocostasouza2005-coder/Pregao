# -*- coding: utf-8 -*-
"""Perfil de Empresa ("Equity Research" profundo) - missao noturna
2026-11-12/13, frente PERFIL DE EMPRESA (pedido do Rodrigo: responder 18
perguntas de equity research pra qualquer ticker, com fonte e periodo de
cada dado, nunca um texto generico de preenchimento).

NAO E' UMA FONTE NOVA DE DADO: esta e' so' uma CAMADA DE CONSOLIDACAO
(funcao pura, zero chamada de IA nova, zero requisicao de rede nova
alem das que os modulos abaixo ja fariam de qualquer forma) sobre o que
o projeto ja coleta/calcula:
- data/research/comparador.py:comparar_ticker - research consolidado
  (premissas/projecoes/riscos extraidos por casa via Groq, ja' persistido
  na biblioteca PERMANENTE research_premissas - ver data/research/
  resumir.py/store.py) + indicadores fundamentalistas (ROE real, ROIC via
  CVM quando disponivel, alertas deterministicos de qualidade).
- data/prices.py:obter_indicadores - fundamentos numericos completos via
  yfinance (P/L, P/VP, margens, divida liquida, fluxo de caixa livre,
  dividend yield, beta, valor de mercado).
- data/prices.py:obter_perfil_institucional (NOVO nesta missao) - resumo
  de negocio/setor/industria/pais/funcionarios via yfinance (mesmo
  tk.info, zero requisicao extra).
- data/news.py:obter_noticias - METADADO de noticias recentes (titulo/
  data/veiculo/link) - NUNCA o resumo editorial (isso exigiria uma
  chamada de IA nova por noticia, fora do escopo de uma camada de
  consolidacao "funcao pura").

AS 18 PERGUNTAS (pedido literal do Rodrigo) sao respondidas, cada uma,
com um "dado" estruturado (nunca texto livre inventado), a FONTE exata
(yfinance/research-<casas>/indicadores fundamentalistas/CVM) e, quando a
resposta vier de research, a lista de EVIDENCIAS reais (casa, trecho
verbatim extraido pela pipeline de resumo, data de publicacao, link) que
sustentam o dado. Pergunta sem informacao suficiente em NENHUMA fonte
disponivel vem com disponivel=False e um motivo explicito - NUNCA
preenchida com texto vago/generico (regra explicita do pedido).

CAMADA DE DADOS - a UI (Agente A) consome o shape documentado em
obter_perfil_empresa() e decide como exibir; este modulo nunca importa
nem referencia nada de ui/*.py."""

import re
import unicodedata
from datetime import datetime, timezone

from data.news import obter_noticias
from data.prices import obter_indicadores, obter_perfil_institucional
from data.research.comparador import comparar_ticker

# ============================================================
# Normalizacao/busca de palavras-chave sobre texto JA EXTRAIDO pela
# pipeline de research (premissas/riscos, ver data/research/resumir.py) -
# NUNCA um classificador de IA novo, so' um filtro deterministico de
# substring (acento/caixa normalizados) pra achar trechos REAIS que
# mencionem o assunto de cada pergunta "qualitativa" (concorrencia/
# posicao competitiva/vantagem competitiva/estrutura de custo/uso de
# capital) - perguntas que o projeto ainda nao extrai como campo
# estruturado proprio (diferente de receita/margem/divida/caixa/riscos,
# que ja' tem campo dedicado real, ver _indicadores_fundamentalistas e
# CAMPO_* em data/research/comparador.py).
# ============================================================

def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def _bate_palavra_chave(texto: str, palavras_chave: tuple) -> bool:
    texto_norm = _sem_acento(texto)
    return any(p in texto_norm for p in palavras_chave)


def _evidencias_por_palavras_chave(estado_atual_por_casa: dict, palavras_chave: tuple) -> list:
    """Varre premissas+riscos da publicacao MAIS RECENTE de cada casa
    (mesmo "estado atual" usado no Comparador - ver data/research/
    comparador.py:_agrupar_por_casa) procurando qualquer uma das
    `palavras_chave` - devolve so' os trechos que bateram, cada um com
    a casa/data/link de onde veio (rastreabilidade obrigatoria, nunca
    um trecho sem origem). [] quando nenhuma casa monitorada tem
    publicacao (nunca quando so' nao bate a palavra - esse caso tambem
    devolve [], a distincao fica no `disponivel` de quem chama)."""
    evidencias = []
    for casa, info in (estado_atual_por_casa or {}).items():
        atual = info.get("atual") or {}
        trechos = list(atual.get("premissas") or []) + list(atual.get("riscos") or [])
        for trecho in trechos:
            if _bate_palavra_chave(trecho, palavras_chave):
                evidencias.append({
                    "casa": casa, "texto": trecho,
                    "data_publicacao": atual.get("data_publicacao"),
                    "link": atual.get("link"),
                })
    return evidencias


_PALAVRAS_CONCORRENTES = ("concorrente", "concorrencia", "rival", "market share", "participacao de mercado",
                          "fatia de mercado", "player")
_PALAVRAS_POSICAO_COMPETITIVA = ("lider", "lideranca", "maior player", "segunda maior", "principal player",
                                 "posicao de destaque", "referencia no setor", "maior empresa")
_PALAVRAS_VANTAGEM_COMPETITIVA = ("vantagem competitiva", "diferencial competitivo", "barreira de entrada",
                                  "economia de escala", "marca forte", "moat", "vantagem de custo")
_PALAVRAS_ESTRUTURA_CUSTO = ("custo", "insumo", "cpv", "despesa operacional", "materia-prima", "materia prima")
_PALAVRAS_USO_CAPITAL = ("capex", "dividendo", "recompra", "buyback", "investimento em expansao",
                         "alocacao de capital", "capital allocation")
_PALAVRAS_RECEITA = ("receita", "volume", "crescimento de vendas", "ticket medio", "faturamento")
_PALAVRAS_MARGEM = ("margem", "ebitda", "rentabilidade")


def _campo(dado, chave: str, motivo_padrao: str) -> dict:
    """Resposta estruturada pra uma pergunta de FATO NUMERICO direto
    (yfinance/CVM, ver data/prices.py:obter_indicadores) - disponivel
    False exatamente quando o campo veio None (nunca inventa um valor
    pra substituir ausencia)."""
    valor = (dado or {}).get(chave)
    return {"dado": valor, "disponivel": valor is not None,
            "motivo_indisponivel": None if valor is not None else motivo_padrao}


def _pergunta_qualitativa(estado_atual_por_casa: dict, palavras_chave: tuple, motivo_padrao: str) -> dict:
    evidencias = _evidencias_por_palavras_chave(estado_atual_por_casa, palavras_chave)
    return {
        "dado": [e["texto"] for e in evidencias],
        "evidencias": evidencias,
        "disponivel": bool(evidencias),
        "motivo_indisponivel": None if evidencias else motivo_padrao,
    }


_MOTIVO_SEM_RESEARCH = ("nenhuma casa de research monitorada tem publicacao com trecho explicito sobre este "
                        "assunto na biblioteca permanente - pode ser que nenhum relatorio aborde isso, ou que "
                        "ainda nao haja relatorio coletado para este ticker")
_MOTIVO_SEM_RESUMO_NEGOCIO = "yfinance nao retornou descricao institucional (tk.info vazio/bloqueado ou campo ausente para este ticker)"


def _perguntas(estado_atual_por_casa: dict, indicadores: dict, perfil_inst: dict, riscos_por_casa: dict,
               divergencia_premissas: dict) -> dict:
    """As 18 perguntas (pedido literal do Rodrigo) - cada uma com
    pergunta/dado/fonte_primaria/disponivel/motivo_indisponivel e
    'evidencias' (lista, so' quando a fonte e' research) ou vazia
    (quando a fonte e' numerica direta, ja rastreada em
    indicadores_fundamentalistas/identificacao no nivel acima)."""
    resumo_negocio = (perfil_inst or {}).get("resumo_negocio")
    perguntas = {}

    def _add(chave, pergunta, fonte_primaria, resultado):
        perguntas[chave] = {"pergunta": pergunta, "fonte_primaria": fonte_primaria, **resultado}

    # 1-6: descricao institucional (yfinance - mesmo resumo da empresa
    # cobre as 6 perguntas juntas: o que faz/como ganha dinheiro/
    # produtos/clientes/segmentos/onde atua - a fonte nao separa por
    # pergunta, repassado integral + setor/pais como pistas estruturadas
    # complementares, nunca uma fragmentacao artificial do texto que a
    # fonte nao fez)
    disponivel_resumo = bool(resumo_negocio)
    base_institucional = {
        "dado": resumo_negocio, "evidencias": [],
        "disponivel": disponivel_resumo,
        "motivo_indisponivel": None if disponivel_resumo else _MOTIVO_SEM_RESUMO_NEGOCIO,
    }
    _add("o_que_a_empresa_faz", "O que a empresa faz?", "yfinance (resumo institucional)", dict(base_institucional))
    _add("como_ganha_dinheiro", "Como a empresa ganha dinheiro?", "yfinance (resumo institucional)",
         dict(base_institucional))
    # produtos/clientes/segmentos (3 das 18 perguntas) - yfinance devolve
    # 1 UNICO resumo institucional que, quando cobre o assunto, cobre os
    # 3 juntos (a fonte nao vem fragmentada por pergunta) - repassado
    # integral pras 3 chaves, nunca uma divisao artificial do texto que
    # a fonte nao fez.
    _add("produtos", "Quais são os principais produtos da empresa?", "yfinance (resumo institucional)",
         dict(base_institucional))
    _add("clientes", "Quem são os principais clientes da empresa?", "yfinance (resumo institucional)",
         dict(base_institucional))
    _add("segmentos", "Em quais segmentos a empresa atua?", "yfinance (resumo institucional)",
         dict(base_institucional))
    onde_atua = {
        "dado": {"pais_sede": (perfil_inst or {}).get("pais"), "resumo": resumo_negocio},
        "evidencias": [],
        "disponivel": bool((perfil_inst or {}).get("pais") or resumo_negocio),
        "motivo_indisponivel": None if ((perfil_inst or {}).get("pais") or resumo_negocio) else _MOTIVO_SEM_RESUMO_NEGOCIO,
    }
    _add("onde_atua", "Onde a empresa atua geograficamente?", "yfinance (país sede + resumo institucional)",
         onde_atua)

    # 7-9: concorrencia/posicionamento - so' existe se algum relatorio de
    # research mencionar explicitamente (ver _evidencias_por_palavras_chave)
    _add("concorrentes", "Quem são os concorrentes da empresa?", "research (premissas/riscos por casa)",
         _pergunta_qualitativa(estado_atual_por_casa, _PALAVRAS_CONCORRENTES, _MOTIVO_SEM_RESEARCH))
    _add("posicao_competitiva", "Qual é a posição competitiva da empresa no setor?",
         "research (premissas/riscos por casa)",
         _pergunta_qualitativa(estado_atual_por_casa, _PALAVRAS_POSICAO_COMPETITIVA, _MOTIVO_SEM_RESEARCH))
    _add("vantagens_competitivas", "Quais são as vantagens competitivas da empresa?",
         "research (premissas/riscos por casa)",
         _pergunta_qualitativa(estado_atual_por_casa, _PALAVRAS_VANTAGEM_COMPETITIVA, _MOTIVO_SEM_RESEARCH))

    # 10-11: drivers de receita / pressoes de margem - projecoes por casa
    # (campo dedicado, ver CAMPO_PROJECAO_RECEITA/EBITDA_MARGEM em
    # data/research/comparador.py) + qualquer premissa/risco que
    # tambem mencione o assunto (sinal complementar)
    projecoes_receita = [
        {"casa": casa, "texto": (info.get("atual") or {}).get("projecoes", {}).get("receita"),
         "data_publicacao": (info.get("atual") or {}).get("data_publicacao"), "link": (info.get("atual") or {}).get("link")}
        for casa, info in (estado_atual_por_casa or {}).items()
        if (info.get("atual") or {}).get("projecoes", {}).get("receita")
    ]
    evidencias_receita = projecoes_receita + _evidencias_por_palavras_chave(estado_atual_por_casa, _PALAVRAS_RECEITA)
    _add("drivers_de_receita", "Quais são os principais drivers de receita da empresa?",
         "research (projeção de receita por casa + premissas/riscos)",
         {"dado": [e["texto"] for e in evidencias_receita], "evidencias": evidencias_receita,
          "disponivel": bool(evidencias_receita),
          "motivo_indisponivel": None if evidencias_receita else _MOTIVO_SEM_RESEARCH})

    projecoes_margem = [
        {"casa": casa, "texto": (info.get("atual") or {}).get("projecoes", {}).get("ebitda_margem"),
         "data_publicacao": (info.get("atual") or {}).get("data_publicacao"), "link": (info.get("atual") or {}).get("link")}
        for casa, info in (estado_atual_por_casa or {}).items()
        if (info.get("atual") or {}).get("projecoes", {}).get("ebitda_margem")
    ]
    evidencias_margem = projecoes_margem + _evidencias_por_palavras_chave(estado_atual_por_casa, _PALAVRAS_MARGEM)
    margens_atuais = {
        "margem_liquida_pct": (indicadores or {}).get("margem_liquida"),
        "margem_operacional_pct": (indicadores or {}).get("margem_operacional"),
        "margem_ebitda_pct": (indicadores or {}).get("margem_ebitda"),
    }
    disponivel_margem = bool(evidencias_margem) or any(v is not None for v in margens_atuais.values())
    _add("pressoes_de_margem", "Quais são as pressões sobre a margem da empresa?",
         "yfinance (margens atuais) + research (projeção de margem por casa + premissas/riscos)",
         {"dado": {"margens_atuais": margens_atuais, "evidencias_research": [e["texto"] for e in evidencias_margem]},
          "evidencias": evidencias_margem, "disponivel": disponivel_margem,
          "motivo_indisponivel": None if disponivel_margem else _MOTIVO_SEM_RESEARCH})

    # 12: estrutura de custo - so' qualitativo (research), yfinance nao
    # reporta estrutura de custo detalhada (so' margens agregadas, ja
    # cobertas acima)
    _add("estrutura_de_custo", "Como é a estrutura de custo da empresa?", "research (premissas/riscos por casa)",
         _pergunta_qualitativa(estado_atual_por_casa, _PALAVRAS_ESTRUTURA_CUSTO, _MOTIVO_SEM_RESEARCH))

    # 13-14: divida/geracao de caixa - FATO numerico direto (yfinance)
    _add("divida", "Qual é a situação de dívida da empresa?", "yfinance (dívida líquida / dívida líquida sobre EBITDA)",
         {**_campo(indicadores, "divida_liquida",
                   "yfinance não reportou dívida líquida para este ticker (campo ausente/indisponível)"),
          "evidencias": [],
          "dado": {"divida_liquida": (indicadores or {}).get("divida_liquida"),
                   "divida_liquida_ebitda": (indicadores or {}).get("divida_liquida_ebitda")}})
    _add("geracao_de_caixa", "Como é a geração de caixa da empresa?", "yfinance (fluxo de caixa livre)",
         {**_campo(indicadores, "fluxo_caixa_livre",
                   "yfinance não reportou fluxo de caixa livre para este ticker (campo ausente/indisponível)"),
          "evidencias": []})

    # 15: uso de capital - FATO numerico (dividend yield, fluxo de caixa
    # livre) + qualquer premissa/risco que mencione capex/dividendo/
    # recompra explicitamente
    evidencias_capital = _evidencias_por_palavras_chave(estado_atual_por_casa, _PALAVRAS_USO_CAPITAL)
    fatos_capital = {"dividend_yield_pct": (indicadores or {}).get("dividend_yield"),
                     "fluxo_caixa_livre": (indicadores or {}).get("fluxo_caixa_livre")}
    disponivel_capital = bool(evidencias_capital) or any(v is not None for v in fatos_capital.values())
    _add("uso_de_capital", "Como a empresa usa o capital que gera (capex, dividendos, recompras)?",
         "yfinance (dividend yield + fluxo de caixa livre) + research (premissas/riscos por casa)",
         {"dado": {"fatos": fatos_capital, "evidencias_research": [e["texto"] for e in evidencias_capital]},
          "evidencias": evidencias_capital, "disponivel": disponivel_capital,
          "motivo_indisponivel": None if disponivel_capital else _MOTIVO_SEM_RESEARCH})

    # 16: riscos - campo DEDICADO (ja existe pronto, ver
    # data/research/comparador.py:_riscos_por_casa) - nunca recalculado
    # aqui, so' repassado com a mesma rastreabilidade
    riscos_evidencias = [
        {"casa": casa, "texto": risco, "data_publicacao": info.get("data_publicacao"), "link": info.get("link")}
        for casa, info in (riscos_por_casa.get("por_casa") or {}).items()
        for risco in info.get("riscos") or []
    ]
    _add("riscos", "Quais são os principais riscos identificados para a empresa?",
         "research (campo dedicado 'riscos' por casa)",
         {"dado": [e["texto"] for e in riscos_evidencias], "evidencias": riscos_evidencias,
          "disponivel": bool(riscos_evidencias),
          "motivo_indisponivel": None if riscos_evidencias else riscos_por_casa.get("motivo")})

    # 17: perspectivas - projecoes de receita/margem/lucro (ja' extraidas
    # acima) + noticias recentes (metadado, sem resumo de IA)
    projecoes_lucro = [
        {"casa": casa, "texto": (info.get("atual") or {}).get("projecoes", {}).get("lucro"),
         "data_publicacao": (info.get("atual") or {}).get("data_publicacao"), "link": (info.get("atual") or {}).get("link")}
        for casa, info in (estado_atual_por_casa or {}).items()
        if (info.get("atual") or {}).get("projecoes", {}).get("lucro")
    ]
    evidencias_perspectivas = evidencias_receita + evidencias_margem + projecoes_lucro
    _add("perspectivas", "Quais são as perspectivas para a empresa?",
         "research (projeções de receita/margem/lucro por casa)",
         {"dado": [e["texto"] for e in evidencias_perspectivas], "evidencias": evidencias_perspectivas,
          "disponivel": bool(evidencias_perspectivas),
          "motivo_indisponivel": None if evidencias_perspectivas else _MOTIVO_SEM_RESEARCH})

    # 18: o que quebraria a tese - reusa riscos (16) + divergencia entre
    # casas (quando as proprias casas de research discordam das
    # premissas centrais, isso E' informacao real sobre fragilidade da
    # tese - nunca uma conclusao nova, so' repassa o que
    # divergencia_premissas (ja calculado no Comparador) ja' apurou)
    premissas_divergentes = (divergencia_premissas or {}).get("premissas_divergentes") or []
    tem_divergencia = bool(premissas_divergentes)
    dado_quebra_tese = {
        "riscos": [e["texto"] for e in riscos_evidencias],
        "divergencia_entre_casas": premissas_divergentes or None,
    }
    _add("o_que_quebraria_a_tese", "O que poderia invalidar/quebrar a tese de investimento?",
         "research (campo dedicado 'riscos' por casa + divergência entre casas)",
         {"dado": dado_quebra_tese, "evidencias": riscos_evidencias,
          "disponivel": bool(riscos_evidencias) or tem_divergencia,
          "motivo_indisponivel": None if (riscos_evidencias or tem_divergencia) else riscos_por_casa.get("motivo")})

    return perguntas


def obter_perfil_empresa(ticker: str) -> dict:
    """Perfil de empresa consolidado (ver docstring do modulo pro shape
    completo e a lista de fontes). Funcao PURA: nunca lanca excecao -
    cada fonte que falhar vira disponivel=False NA PROPRIA PERGUNTA
    afetada, nunca aborta o perfil inteiro (mesmo principio de
    resiliencia parcial ja usado em data/research/comparador.py).

    Retorno:
    {
      "ticker": str,
      "gerado_em": str (ISO UTC - quando ESTE perfil foi montado; cada
                   fonte interna tem seu proprio timestamp de coleta,
                   ver "identificacao"/"indicadores_fundamentalistas"),
      "identificacao": {
          "setor": str|None, "industria": str|None, "pais": str|None,
          "website": str|None, "funcionarios": int|None,
          "resumo_negocio": str|None, "fonte": str|None,
          "consultado_em": str|None, "disponivel": bool,
      },
      "indicadores_fundamentalistas": dict (repasse integral de
          data/prices.py:obter_indicadores - P/L, P/VP, margens, divida
          liquida, fluxo de caixa livre, dividend yield, beta, ROE),
      "research": {
          "disponivel": bool, "motivo": str|None,
          "casas": list[str] (casas com publicacao pra este ticker),
          "indicadores_adicionais": dict (ROE/ROIC real + alertas de
              qualidade, ver comparador.py:_indicadores_fundamentalistas),
          "dispersao_precos_alvo": dict|None,
          "divergencia_recomendacao": dict|None,
          "divergencia_premissas": dict|None,
          "evolucao_historica": dict|None,
      },
      "noticias_recentes": list[dict] (titulo/data/link/veiculos/selo -
          METADADO, nunca o resumo editorial - ver docstring do modulo;
          [] se nao houver noticia recente, None nunca aparece aqui -
          fonte indisponivel vira [] com 'noticias_disponivel'=False
          no nivel acima),
      "noticias_disponivel": bool,
      "perguntas": dict com as 18 chaves (ver _perguntas) - cada uma
          {"pergunta", "fonte_primaria", "dado", "evidencias",
           "disponivel", "motivo_indisponivel"}.
    }"""
    ticker = (ticker or "").strip().upper()
    agora = datetime.now(timezone.utc).isoformat()

    try:
        perfil_inst = obter_perfil_institucional(ticker)
    except Exception as exc:
        perfil_inst = {"disponivel": False, "resumo_negocio": None, "setor": None, "industria": None,
                       "pais": None, "website": None, "funcionarios": None, "fonte": None,
                       "consultado_em": None, "_erro": f"{exc!r}"}

    try:
        indicadores = obter_indicadores(ticker)
    except Exception:
        indicadores = {}

    try:
        comparacao = comparar_ticker(ticker)
    except Exception:
        comparacao = {"disponivel": False, "motivo": "falha ao consultar research consolidado"}

    estado_atual_por_casa = comparacao.get("estado_atual_por_casa") or {}
    riscos_por_casa = comparacao.get("riscos") or {"disponivel": False, "por_casa": {}, "motivo": None}
    divergencia_premissas = comparacao.get("divergencia_premissas") or {}

    try:
        noticias = obter_noticias(ticker)
    except Exception:
        noticias = None
    noticias_disponivel = noticias is not None
    noticias_recentes = noticias or []

    return {
        "ticker": ticker,
        "gerado_em": agora,
        "identificacao": perfil_inst,
        "indicadores_fundamentalistas": indicadores,
        "research": {
            "disponivel": comparacao.get("disponivel", False),
            "motivo": comparacao.get("motivo"),
            "casas": comparacao.get("casas") or [],
            "indicadores_adicionais": comparacao.get("indicadores_adicionais"),
            "dispersao_precos_alvo": comparacao.get("dispersao_precos_alvo"),
            "divergencia_recomendacao": comparacao.get("divergencia_recomendacao"),
            "divergencia_premissas": comparacao.get("divergencia_premissas"),
            "evolucao_historica": comparacao.get("evolucao_historica"),
        },
        "noticias_recentes": noticias_recentes,
        "noticias_disponivel": noticias_disponivel,
        "perguntas": _perguntas(estado_atual_por_casa, indicadores, perfil_inst, riscos_por_casa,
                                divergencia_premissas),
    }
