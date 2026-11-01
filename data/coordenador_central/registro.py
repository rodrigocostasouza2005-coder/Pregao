# -*- coding: utf-8 -*-
"""Registro central de especialistas (Fase E, Coordenador Central) -
catálogo das inteligências Python já existentes e dispersas no PREGÃO,
cada uma envolvida (nunca reescrita) num contrato padronizado de
entrada/saída pra o executor (data/coordenador_central/executor.py) poder
chamar qualquer uma de forma uniforme.

Cada Especialista tem:
- funcao: a função REAL já existente (importada, nunca reimplementada) ou
  um wrapper FINO sobre ela quando a assinatura original não aceita os
  kwargs padronizados direto (ex: catalisadores espera uma tupla de
  tickers, não um ticker solto; resultados_corporativos precisa descobrir
  ano/trimestre antes de chamar a função real) - o wrapper só adapta a
  CHAMADA, nunca a lógica de negócio de dentro do módulo original.
- extrator_saida: função pequena e pura que recebe o retorno BRUTO da
  função real (formato DIFERENTE pra cada especialista hoje) e devolve o
  contrato comum:
    {"disponivel": bool, "resumo": str|None, "evidencias": list,
     "motivo_indisponivel": str|None, "dados": <retorno bruto original>}
  `dados` carrega o retorno bruto original (além das 4 chaves exigidas)
  pra consolidacao.py poder fazer comparação cruzada entre especialistas
  sem precisar re-chamar nada - nunca removido nem resumido aqui.

Nenhum especialista é removido do registro por estar indisponível hoje
(ex: radar_x sem X_BEARER_TOKEN) - "indisponível e documentado" é um
estado válido do especialista, não motivo pra escondê-lo."""

from dataclasses import dataclass, field
from typing import Callable

from data import eventos, radar
from data import x_radar
from data.earnings import reviewer as earnings_reviewer
from data.market_researcher import analise_ticker as _analise_ticker_real
from data.news import obter_noticias
from data.research.comparador import montar_relatorio_comparativo
from data.research.embeddings import buscar as _buscar_memoria_research


@dataclass(frozen=True)
class Especialista:
    id: str
    nome: str
    descricao: str
    capacidades: tuple
    pre_requisitos: tuple
    entradas_aceitas: dict
    funcao: Callable
    extrator_saida: Callable


# ============================================================
# Wrappers finos (adaptação de chamada, nunca de lógica de negócio)
# ============================================================

def _chamar_catalisadores(ticker: str = None, dias_passado: int = 7, dias_futuro: int = 60, **_ignorado) -> list:
    """data.radar.catalisadores espera uma TUPLA de tickers (pensado pra
    watchlist inteira) - aqui sempre chamado com 1 ticker só, mesma
    função, sem duplicar a lógica de janela/fonte."""
    ticker = (ticker or "").strip().upper()
    return radar.catalisadores((ticker,), dias_passado=dias_passado, dias_futuro=dias_futuro)


def _trimestre_mais_recente_antes_do_pendente(ano_pendente: int, trimestre_pendente: int) -> tuple:
    if trimestre_pendente <= 1:
        return ano_pendente - 1, 4
    return ano_pendente, trimestre_pendente - 1


def _chamar_resultados_corporativos(ticker: str = None, ano: int = None, trimestre: int = None, **_ignorado) -> dict:
    """data.earnings.reviewer.montar_nota_br exige (ticker, ano,
    trimestre) explícitos - quando ano/trimestre não são informados,
    deriva o ÚLTIMO trimestre já encerrado a partir de
    data.eventos.periodo_pendente (que devolve o período AINDA pendente -
    o reportável mais recente é sempre o anterior a esse). Nunca inventa
    um período quando a fonte CVM está indisponível ou o ticker não tem
    CNPJ mapeado (periodo_pendente devolve None nesses dois casos) -
    reporta disponivel=False com motivo explícito em vez disso."""
    ticker = (ticker or "").strip().upper()
    if ano is None or trimestre is None:
        periodo = eventos.periodo_pendente(ticker)
        if periodo is None:
            return {
                "ticker": ticker, "pais": "BR", "disponivel": False,
                "motivo": "período de resultado não identificável (ticker sem CNPJ mapeado na CVM, ou "
                          "fonte CVM indisponível) - impossível determinar automaticamente qual trimestre revisar.",
            }
        ano, trimestre = _trimestre_mais_recente_antes_do_pendente(*periodo)
    return earnings_reviewer.montar_nota_br(ticker, ano, trimestre)


def _chamar_radar_x(**_ignorado) -> dict:
    """RADAR X não é por ticker (ciclo de coleta geral) - ignora qualquer
    kwarg (ticker/pergunta/etc) recebido dos fluxos que o acionam junto
    com especialistas por-ticker."""
    return x_radar.executar_ciclo()


# ============================================================
# Extratores de saída (adaptadores pro contrato comum, nunca reescrevem
# a função original)
# ============================================================

def _extrair_comparador(bruto: dict) -> dict:
    if not bruto.get("disponivel"):
        return {
            "disponivel": False, "resumo": None, "evidencias": [],
            "motivo_indisponivel": bruto.get("motivo") or "indisponível", "dados": bruto,
        }
    evidencias = [
        {"fonte": f.get("casa"), "data": f.get("data_publicacao"), "link": f.get("link"), "titulo": f.get("titulo")}
        for f in (bruto.get("fontes_evidencias") or [])
    ]
    return {
        "disponivel": True, "resumo": bruto.get("resumo_executivo"), "evidencias": evidencias,
        "motivo_indisponivel": None, "dados": bruto,
    }


_AVISO_BANCO_INDISPONIVEL_MEMORIA = "banco de research indisponivel no momento"


def _extrair_memoria_research(bruto: dict) -> dict:
    aviso = bruto.get("aviso")
    resultados = bruto.get("resultados") or []
    confianca = bruto.get("confianca")
    banco_indisponivel = confianca == "SEM_EVIDENCIA" and aviso == _AVISO_BANCO_INDISPONIVEL_MEMORIA
    if banco_indisponivel:
        return {"disponivel": False, "resumo": None, "evidencias": [], "motivo_indisponivel": aviso, "dados": bruto}

    evidencias = [
        {"fonte": r.get("casa"), "data": r.get("data_publicacao"), "link": r.get("link"), "titulo": r.get("titulo")}
        for r in resultados
    ]
    if resultados:
        resumo = f"{len(resultados)} publicação(ões) encontrada(s) na memória de research (confiança {confianca})."
    else:
        resumo = "Nenhuma publicação encontrada na memória de research para os filtros informados."
    return {"disponivel": True, "resumo": resumo, "evidencias": evidencias, "motivo_indisponivel": aviso, "dados": bruto}


def _extrair_analise_ticker(bruto: dict) -> dict:
    fontes_indisponiveis = bruto.get("fontes_indisponiveis") or []
    catalisadores = bruto.get("catalisadores") or []
    cobertura = bruto.get("cobertura_research") or {}
    cobertura_lista = cobertura.get("cobertura") or []

    partes = []
    if bruto.get("fundamentos"):
        partes.append("fundamentos disponíveis")
    if catalisadores:
        partes.append(f"{len(catalisadores)} catalisador(es) na janela")
    if cobertura_lista:
        partes.append(f"{len(cobertura_lista)} casa(s) com cobertura recente")

    resumo = f"Síntese agregada de {bruto.get('ticker')}: " + (
        ", ".join(partes) if partes else "sem dado agregado disponível nesta chamada"
    ) + "."

    evidencias = []
    for c in catalisadores:
        evidencias.append({"fonte": c.get("fonte_label"), "data": c.get("data"), "link": c.get("fonte_url"), "titulo": c.get("categoria")})
    for cob in cobertura_lista:
        evidencias.append({"fonte": cob.get("casa"), "data": cob.get("data"), "link": cob.get("link"), "titulo": cob.get("titulo")})

    # 3 fontes internas possíveis (fundamentos/contexto_mercado/
    # cobertura_research) - só indisponível de verdade quando TODAS falharam.
    disponivel = len(fontes_indisponiveis) < 3
    motivo = None if disponivel else "fundamentos, contexto de mercado e cobertura de research indisponíveis: " + ", ".join(fontes_indisponiveis)
    return {"disponivel": disponivel, "resumo": resumo, "evidencias": evidencias, "motivo_indisponivel": motivo, "dados": bruto}


def _extrair_noticias(bruto) -> dict:
    if bruto is None:
        return {
            "disponivel": False, "resumo": None, "evidencias": [],
            "motivo_indisponivel": "fonte de notícias indisponível (Google News não respondeu)", "dados": None,
        }
    if not bruto:
        return {"disponivel": True, "resumo": "Nenhuma notícia recente encontrada.", "evidencias": [], "motivo_indisponivel": None, "dados": bruto}
    resumo = f"{len(bruto)} notícia(s)/grupo(s) de notícia recente encontrado(s)."
    evidencias = [
        {"fonte": (n.get("veiculos") or [None])[0], "data": n.get("data"), "link": n.get("link"), "titulo": n.get("titulo")}
        for n in bruto
    ]
    return {"disponivel": True, "resumo": resumo, "evidencias": evidencias, "motivo_indisponivel": None, "dados": bruto}


def _extrair_calendario(bruto) -> dict:
    if bruto is None:
        return {
            "disponivel": False, "resumo": None, "evidencias": [],
            "motivo_indisponivel": "período de resultado não identificável (sem CNPJ mapeado na CVM ou fonte CVM indisponível)",
            "dados": None,
        }
    resumo = f"Próximo resultado esperado: {bruto.get('periodo')} ({bruto.get('status')}), data {bruto.get('data')}."
    evidencias = [{"fonte": bruto.get("fonte"), "data": bruto.get("data"), "link": bruto.get("origem_url"), "titulo": bruto.get("periodo")}]
    return {"disponivel": True, "resumo": resumo, "evidencias": evidencias, "motivo_indisponivel": None, "dados": bruto}


def _extrair_catalisadores_lista(bruto: list) -> dict:
    if not bruto:
        return {"disponivel": True, "resumo": "Nenhum catalisador identificado na janela coberta.", "evidencias": [], "motivo_indisponivel": None, "dados": bruto}
    resumo = f"{len(bruto)} catalisador(es) identificado(s) na janela coberta."
    evidencias = [
        {"fonte": c.get("fonte_label"), "data": c.get("data"), "link": c.get("fonte_url"), "titulo": c.get("categoria")}
        for c in bruto
    ]
    return {"disponivel": True, "resumo": resumo, "evidencias": evidencias, "motivo_indisponivel": None, "dados": bruto}


def _extrair_resultados_corporativos(bruto: dict) -> dict:
    if not bruto.get("disponivel"):
        return {"disponivel": False, "resumo": None, "evidencias": [], "motivo_indisponivel": bruto.get("motivo") or "indisponível", "dados": bruto}
    periodo_label = bruto.get("periodo_label")
    resumo = f"Nota de resultado trimestral disponível para {periodo_label or 'o período revisado'}."
    evidencias = [{"fonte": "CVM/DRE" if bruto.get("pais") == "BR" else "SEC/XBRL", "data": None, "link": None, "titulo": periodo_label}]
    return {"disponivel": True, "resumo": resumo, "evidencias": evidencias, "motivo_indisponivel": None, "dados": bruto}


def _extrair_radar_x(bruto: dict) -> dict:
    """Sempre disponivel=False com motivo quando sem credencial (decisão
    explícita do Rodrigo, custo de API não aprovado) - nunca removido do
    registro por isso, só reportado como indisponível."""
    if not bruto.get("ok"):
        return {"disponivel": False, "resumo": None, "evidencias": [], "motivo_indisponivel": bruto.get("motivo") or "indisponível", "dados": bruto}
    resumo = f"{bruto.get('sinais_novos', 0)} sinal(is) novo(s) de inteligência social coletado(s)."
    return {"disponivel": True, "resumo": resumo, "evidencias": [], "motivo_indisponivel": None, "dados": bruto}


# ============================================================
# REGISTRO
# ============================================================

REGISTRO: dict = {
    "comparador": Especialista(
        id="comparador", nome="Comparador de Casas",
        descricao="Comparação estruturada entre casas de research pra um ticker (dispersão de preço-alvo, "
                   "divergência de recomendação/premissas, evolução histórica) - 100% determinístico, zero IA.",
        capacidades=("comparacao_casas", "preco_alvo", "recomendacao", "divergencia"),
        pre_requisitos=(),
        entradas_aceitas={"ticker": str},
        funcao=montar_relatorio_comparativo,
        extrator_saida=_extrair_comparador,
    ),
    "memoria_research": Especialista(
        id="memoria_research", nome="Memória de Research (RAG)",
        descricao="Busca híbrida (estrutural + semântica + lexical) na biblioteca permanente de premissas/"
                   "projeções de research. Busca semântica exige GEMINI_API_KEY; sem ela, degrada pra "
                   "estrutural/lexical sem quebrar.",
        capacidades=("busca_semantica", "publicacoes_originais", "premissas", "projecoes"),
        pre_requisitos=("GEMINI_API_KEY",),
        entradas_aceitas={"pergunta": "str|None", "ticker": "str|None", "casa": "str|None"},
        funcao=_buscar_memoria_research,
        extrator_saida=_extrair_memoria_research,
    ),
    "analise_ticker": Especialista(
        id="analise_ticker", nome="Análise de Ticker (Market Researcher)",
        descricao="Agregador de fundamentos + catalisadores/mudança de tese + cobertura cruzada de research "
                   "pra um ticker - zero IA, zero consulta nova (fachada sobre módulos já existentes).",
        capacidades=("fundamentos", "catalisadores", "cobertura_research"),
        pre_requisitos=(),
        entradas_aceitas={"ticker": str, "janela": "str"},
        funcao=_analise_ticker_real,
        extrator_saida=_extrair_analise_ticker,
    ),
    "noticias": Especialista(
        id="noticias", nome="Notícias",
        descricao="Notícias recentes de uma empresa via RSS do Google News, com score de confiabilidade "
                   "(regras, sem IA) e confirmação cruzada com documentos oficiais da CVM quando aplicável.",
        capacidades=("noticias", "score_confiabilidade"),
        pre_requisitos=(),
        entradas_aceitas={"ticker": str},
        funcao=obter_noticias,
        extrator_saida=_extrair_noticias,
    ),
    "calendario": Especialista(
        id="calendario", nome="Calendário de Resultados",
        descricao="Próximo resultado corporativo esperado pro ticker (confirmado/estimado pelo coletor, ou "
                   "prazo regulatório CVM) - nunca inventa evento quando a fonte CVM está fora do ar.",
        capacidades=("calendario_resultados", "prazo_cvm"),
        pre_requisitos=(),
        entradas_aceitas={"ticker": str},
        funcao=eventos.calcular_proximo_resultado,
        extrator_saida=_extrair_calendario,
    ),
    "catalisadores": Especialista(
        id="catalisadores", nome="Catalisadores",
        descricao="Eventos de calendário (resultado/proventos) do ticker numa janela passado/futuro - "
                   "reaproveita o mesmo snapshot da aba CALENDÁRIO, nenhuma fonte nova.",
        capacidades=("catalisadores", "proventos", "calendario"),
        pre_requisitos=(),
        entradas_aceitas={"ticker": str, "dias_passado": "int", "dias_futuro": "int"},
        funcao=_chamar_catalisadores,
        extrator_saida=_extrair_catalisadores_lista,
    ),
    "resultados_corporativos": Especialista(
        id="resultados_corporativos", nome="Resultados Corporativos (Earnings Reviewer)",
        descricao="Nota estruturada do resultado trimestral mais recente já reportado (DRE da CVM) - "
                   "fatos rotulados vs interpretação, nunca inventa consenso/guidance/preço-alvo.",
        capacidades=("resultados_trimestrais", "dre", "yoy_qoq"),
        pre_requisitos=(),
        entradas_aceitas={"ticker": str, "ano": "int|None", "trimestre": "int|None"},
        funcao=_chamar_resultados_corporativos,
        extrator_saida=_extrair_resultados_corporativos,
    ),
    "radar_x": Especialista(
        id="radar_x", nome="Radar X (Inteligência Social)",
        descricao="Inteligência social (X/Twitter) sobre empresas/casas/macro monitoradas - implementado, "
                   "mas DESLIGADO hoje (sem X_BEARER_TOKEN, decisão deliberada de custo) - continua "
                   "registrado como especialista real, só reporta indisponível.",
        capacidades=("inteligencia_social",),
        pre_requisitos=("X_BEARER_TOKEN",),
        entradas_aceitas={},
        funcao=_chamar_radar_x,
        extrator_saida=_extrair_radar_x,
    ),
}


def listar_especialistas() -> list:
    return sorted(REGISTRO.values(), key=lambda e: e.id)


def obter_especialista(especialista_id: str) -> Especialista | None:
    return REGISTRO.get(especialista_id)
