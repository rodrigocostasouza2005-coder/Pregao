# -*- coding: utf-8 -*-
"""RADAR - camada de AGREGAÇÃO pura (2026-10-09). Zero coleta nova, zero
chamada de IA nova: só combina dado que outros módulos já coletam/
persistem (data/research/historico.py, data/cvm.py, data/eventos.py,
data/prices.py) pra alimentar ui/radar_tab.py. Nenhuma função aqui faz
requisição de rede que os módulos de origem já não fariam por conta
própria - isso é deliberado (ver PROGRESSO.md, matriz de classificação
dos coletores da FASE 7: o RADAR herda a confiabilidade de cada fonte,
não reinveste nem reinventa coleta).

Convenção de evidência usada em todo alerta/sinal deste módulo (pedida
explicitamente: "diferencie FATO, INTERPRETAÇÃO e DADO INSUFICIENTE"):

- FATO: algo que de fato aconteceu e está registrado numa fonte
  verificável e datada (mudança de recomendação/preço-alvo persistida no
  histórico, documento oficial da CVM, evento de calendário confirmado/
  estimado/prazo regulatório).
- CALCULO_INTERNO: número DERIVADO aqui a partir de FATOs (ex: potencial
  de valorização recalculado com o preço atual, mediana setorial),
  explicitamente diferenciado do que a própria fonte publicou - nunca
  apresentado como "consenso de mercado" ou estimativa de terceiros.
- DADO_INSUFICIENTE: quando não há evidência real suficiente pra algo -
  o módulo declara a lacuna em vez de inventar um valor."""

from datetime import date, datetime, timedelta, timezone
from statistics import median
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import config
from data.cvm import obter_documentos_watchlist
from data.eventos import (
    PRIORIDADE_STATUS,
    STATUS_CONFIRMADO,
    STATUS_LABEL,
    calcular_calendario_cacheado,
)
from data.news import obter_noticias_watchlist
from data.posicoes import obter_posicoes
from data.prices import _calcular_beta, obter_cotacao, obter_historico, obter_indicadores
from data.research import genial
from data.research.historico import historico_ticker

_TZ_SP = ZoneInfo("America/Sao_Paulo")

TIPO_FATO = "FATO"
TIPO_CALCULO = "CALCULO_INTERNO"
TIPO_INSUFICIENTE = "DADO_INSUFICIENTE"

# só Genial tem histórico ESTRUTURADO de recomendação/preço-alvo hoje
# (ver data/research/historico.py - "casa" genérico, mas só essa casa
# alimenta a tabela na prática) - documentado aqui pra não reinventar.
_CASA_COM_HISTORICO = "Genial Analisa"

JANELAS_DIAS = {"HOJE": 1, "7 DIAS": 7, "30 DIAS": 30}

_TTL_AGREGACAO = 10 * 60  # so' pra nao reler Supabase/CVM a cada rerun/troca de secao


def _hoje_br() -> date:
    return datetime.now(_TZ_SP).date()


def _parse_data(valor) -> date | None:
    if not valor:
        return None
    try:
        if isinstance(valor, date):
            return valor
        texto = str(valor)
        if "T" in texto:
            return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(_TZ_SP).date()
        return date.fromisoformat(texto[:10])
    except (ValueError, TypeError):
        return None


def _parse_datetime(valor) -> datetime | None:
    if not valor:
        return None
    try:
        texto = str(valor).replace("Z", "+00:00")
        dt = datetime.fromisoformat(texto)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_TZ_SP)
    except (ValueError, TypeError):
        return None


# ============================================================
# A. MUDANÇAS DE TESE - prioridade máxima (pedido explícito do Rodrigo)
# ============================================================

def _descricao_mudanca_recomendacao(anterior: dict, atual: dict) -> str | None:
    de, para = anterior.get("recomendacao"), atual.get("recomendacao")
    if de == para or not para:
        return None
    if de:
        return f"Recomendação mudou de {de} para {para}"
    return f"Recomendação iniciada em {para}"


def _descricao_mudanca_preco_alvo(anterior: dict, atual: dict) -> str | None:
    de, para = anterior.get("preco_alvo"), atual.get("preco_alvo")
    if de == para or para is None:
        return None
    if de is None:
        return f"Preço-alvo iniciado em R$ {para:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    sinal = "subiu" if para > de else "caiu"
    return (
        f"Preço-alvo {sinal} de R$ {de:,.2f} para R$ {para:,.2f}"
    ).replace(",", "X").replace(".", ",").replace("X", ".")


def _potencial_calculado(ticker: str, preco_alvo) -> tuple[float | None, str]:
    """Potencial de valorização recalculado com a cotação ATUAL (não o
    preço da época da mudança, que não temos persistido) - sempre
    marcado como CÁLCULO_INTERNO, nunca apresentado como número da
    própria casa de research (essa, quando existe, vem em
    'potencial_pct_fonte')."""
    if preco_alvo is None:
        return None, "sem preço-alvo pra calcular potencial"
    cot = obter_cotacao(ticker)
    if cot.get("erro") or not cot.get("preco"):
        return None, "cotação atual indisponível pra calcular potencial"
    preco_atual = cot["preco"]
    potencial = (preco_alvo - preco_atual) / preco_atual * 100
    return potencial, ""


def _montar_alerta_research(ticker: str, casa: str, anterior: dict, atual: dict, data_evento: date, capturado_em: datetime) -> dict | None:
    descricoes = [
        d for d in (
            _descricao_mudanca_recomendacao(anterior, atual),
            _descricao_mudanca_preco_alvo(anterior, atual),
        ) if d
    ]
    if not descricoes:
        return None
    potencial_calc, motivo_sem_potencial = _potencial_calculado(ticker, atual.get("preco_alvo"))
    relevancia = (
        f"{casa} revisou a tese pra {ticker} - mudança registrada no histórico de recomendações. "
        "Vale conferir se o motivo foi divulgado num relatório novo (aba RESEARCH)."
    )
    return {
        "ticker": ticker,
        "categoria": "Research — recomendação/preço-alvo",
        "descricao": "; ".join(descricoes),
        "data_evento": data_evento,
        "horario_coleta": capturado_em,
        "fonte_label": casa,
        "fonte_url": genial.BASE_URL if casa == _CASA_COM_HISTORICO else None,
        "tipo_evidencia": TIPO_FATO,
        "relevancia": relevancia,
        "detalhe": {
            "de": {"recomendacao": anterior.get("recomendacao"), "preco_alvo": anterior.get("preco_alvo")},
            "para": {"recomendacao": atual.get("recomendacao"), "preco_alvo": atual.get("preco_alvo")},
        },
        "potencial_pct_fonte": atual.get("potencial_pct"),
        "potencial_pct_calculado": potencial_calc,
        "potencial_pct_motivo_insuficiente": motivo_sem_potencial,
        "argumento_contrario": None,  # sem texto/justificativa da própria casa persistido - não inventamos um
    }


def _mudancas_research(tickers: tuple, limite_data: date) -> list:
    alertas = []
    vistos = set()
    for ticker in tickers:
        historico = historico_ticker(_CASA_COM_HISTORICO, ticker, limite=12)
        for i in range(len(historico) - 1):
            atual, anterior = historico[i], historico[i + 1]
            capturado_em = _parse_datetime(atual.get("capturado_em"))
            data_evento = capturado_em.date() if capturado_em else _parse_data(atual.get("capturado_em"))
            if data_evento is None or data_evento < limite_data:
                continue
            chave = (ticker, atual.get("capturado_em"))
            if chave in vistos:
                continue
            vistos.add(chave)
            alerta = _montar_alerta_research(ticker, _CASA_COM_HISTORICO, anterior, atual, data_evento, capturado_em)
            if alerta:
                alertas.append(alerta)
    return alertas


def _montar_alerta_cvm(documento: dict) -> dict:
    data_evento = _parse_data(documento["data"]) or _hoje_br()
    return {
        "ticker": documento["ticker"],
        "categoria": f"CVM — {documento['tipo_label']}",
        "descricao": documento["assunto"],
        "data_evento": data_evento,
        "horario_coleta": None,  # CVM não expõe hora de protocolo, só a data
        "fonte_label": "CVM (documento oficial)",
        "fonte_url": documento["link"],
        "tipo_evidencia": TIPO_FATO,
        "relevancia": (
            "Fato relevante protocolado na CVM - comunicação oficial da própria companhia, "
            "maior nível de confiabilidade entre as fontes deste projeto."
        ),
        "detalhe": None,
        "potencial_pct_fonte": None,
        "potencial_pct_calculado": None,
        "potencial_pct_motivo_insuficiente": "",
        "argumento_contrario": None,
    }


def _mudancas_cvm(tickers: tuple, limite_data: date) -> list:
    documentos, _falhas = obter_documentos_watchlist(tuple(tickers))
    alertas = []
    for d in documentos:
        if d["tipo"] != "FATO_RELEVANTE":
            continue
        data_evento = _parse_data(d["data"])
        if data_evento is None or data_evento < limite_data:
            continue
        alertas.append(_montar_alerta_cvm(d))
    return alertas


@st.cache_data(ttl=_TTL_AGREGACAO, show_spinner=False)
def mudancas_tese(tickers: tuple, janela: str = "7 DIAS") -> list:
    """Alertas de 'O QUE MUDOU' pra uma lista de tickers, dentro da
    janela pedida (ver JANELAS_DIAS). [] se não houver nenhuma mudança
    verificada no período - estado vazio honesto, nunca preenchido com
    ruído. Ordenado por data do evento (mais recente primeiro)."""
    dias = JANELAS_DIAS.get(janela, 7)
    limite_data = _hoje_br() - timedelta(days=dias)
    alertas = _mudancas_research(tuple(tickers), limite_data) + _mudancas_cvm(tuple(tickers), limite_data)
    alertas.sort(key=lambda a: a["data_evento"], reverse=True)
    return alertas


# ============================================================
# B. VALUATION RADAR
# ============================================================

def _indicadores_desatualizados(indicadores: dict) -> bool:
    coletado_em = indicadores.get("_coletado_em")
    if not coletado_em:
        return False  # sem timestamp = veio direto da coleta de agora, não do fallback
    dt = _parse_datetime(coletado_em)
    if dt is None:
        return False
    return (datetime.now(_TZ_SP) - dt) > timedelta(hours=24)


@st.cache_data(ttl=90, show_spinner=False)
def linha_valuation(ticker: str) -> dict:
    """1 linha da tabela de Valuation Radar - só dados rastreáveis
    (cotação + múltiplos do yfinance), SEM valor justo/estimativa
    calculada (ver comparaveis_setor pra isso, sob demanda). TTL curto
    (90s, igual obter_cotacao) porque o preço é o campo mais sensível ao
    tempo aqui - os múltiplos (obter_indicadores) já têm cache próprio
    de 12h, então reconsultar aqui não gera chamada de rede extra na
    prática."""
    info = config.info_ativo(ticker)
    cot = obter_cotacao(ticker)
    ind = obter_indicadores(ticker)
    return {
        "ticker": ticker,
        "setor": config.IBOVESPA_SETORES.get(ticker),
        "moeda": info["moeda"],
        "preco": None if cot.get("erro") else cot.get("preco"),
        "preco_erro": cot.get("erro"),
        "consultado_em": datetime.now(_TZ_SP),
        "pl": ind.get("pl"),
        "pvp": ind.get("pvp"),
        "dividend_yield": ind.get("dividend_yield"),
        "roe": ind.get("roe"),
        "margem_liquida": ind.get("margem_liquida"),
        "divida_liquida_ebitda": ind.get("divida_liquida_ebitda"),
        "valor_mercado": ind.get("valor_mercado"),
        "desatualizado": _indicadores_desatualizados(ind),
        "alerta_qualidade": _alertas_qualidade(ind),
    }


def _alertas_qualidade(indicadores: dict) -> list:
    """Sinais de qualidade/deterioração que o PRÓPRIO dado sustenta
    (nunca uma inferência de causa) - lista vazia se nada bater."""
    alertas = []
    pl = indicadores.get("pl")
    if pl is not None and pl < 0:
        alertas.append("P/L negativo (lucro negativo no período - múltiplo não é comparável)")
    margem = indicadores.get("margem_liquida")
    if margem is not None and margem < 0:
        alertas.append("margem líquida negativa")
    divida_ebitda = indicadores.get("divida_liquida_ebitda")
    if divida_ebitda is not None and divida_ebitda > 4:
        alertas.append(f"dívida líquida/EBITDA elevada ({divida_ebitda:.1f}x)")
    return alertas


def valuation_radar(tickers: tuple) -> list:
    """Linha de valuation pra cada ticker da lista - sem comparáveis
    setoriais (ver comparaveis_setor, carregado sob demanda pra não
    pagar o custo de N consultas yfinance no primeiro render)."""
    return [linha_valuation(t) for t in tickers]


@st.cache_data(ttl=_TTL_AGREGACAO, show_spinner=False)
def comparaveis_setor(ticker: str, minimo_pares: int = 3) -> dict:
    """Mediana de P/L, P/VP e dividend yield entre os PARES do mesmo
    setor (universo = config.IBOVESPA_SETORES, ~84 papéis do Ibovespa) -
    chamado SÓ quando o usuário pede explicitamente (botão/expander),
    nunca no primeiro render do Valuation Radar (evita N consultas
    yfinance em cascata). Cada métrica só reporta mediana se houver pelo
    menos `minimo_pares` pares com valor não-nulo - caso contrário
    declara dado insuficiente em vez de calcular com amostra pequena
    demais pra ser útil."""
    setor = config.IBOVESPA_SETORES.get(ticker)
    if not setor:
        return {"setor": None, "pares_considerados": 0, "insuficiente": True, "motivo": "ticker sem setor cadastrado"}
    pares = [t for t, s in config.IBOVESPA_SETORES.items() if s == setor and t != ticker]
    valores_pl, valores_pvp, valores_dy = [], [], []
    for par in pares:
        ind = obter_indicadores(par)
        if ind.get("pl") is not None and ind["pl"] > 0:  # P/L negativo nao e' comparavel (empresa com prejuizo)
            valores_pl.append(ind["pl"])
        if ind.get("pvp") is not None:
            valores_pvp.append(ind["pvp"])
        if ind.get("dividend_yield") is not None:
            valores_dy.append(ind["dividend_yield"])

    resultado = {"setor": setor, "pares_considerados": len(pares), "insuficiente": False}
    for chave, valores in (("pl_mediana", valores_pl), ("pvp_mediana", valores_pvp), ("dy_mediana", valores_dy)):
        resultado[chave] = median(valores) if len(valores) >= minimo_pares else None
        resultado[f"{chave}_n"] = len(valores)
    if all(resultado[c] is None for c in ("pl_mediana", "pvp_mediana", "dy_mediana")):
        resultado["insuficiente"] = True
        resultado["motivo"] = f"menos de {minimo_pares} pares do setor com dado válido"
    return resultado


# ============================================================
# C. CATALISADORES - integra o CALENDÁRIO existente, sem duplicar fonte
# ============================================================

def catalisadores(tickers: tuple, dias_passado: int = 7, dias_futuro: int = 60) -> list:
    """Reaproveita calcular_calendario_cacheado (mesmo snapshot que a
    aba CALENDÁRIO lê) + documentos de PROVENTOS da CVM (dividendo/JCP
    já anunciado) - nenhuma fonte nova, nenhum evento artificial. Janela
    [-dias_passado, +dias_futuro] a partir de hoje."""
    hoje = _hoje_br()
    inicio, fim = hoje - timedelta(days=dias_passado), hoje + timedelta(days=dias_futuro)

    eventos_resultado = calcular_calendario_cacheado(tuple(tickers))
    catalisadores_lista = []
    for e in eventos_resultado:
        if not (inicio <= e["data"] <= fim):
            continue
        catalisadores_lista.append({
            "ticker": e["ticker"],
            "empresa": e.get("empresa") or e["ticker"],
            "categoria": "Resultado corporativo",
            "data": e["data"],
            "status": e["status"],
            "status_label": STATUS_LABEL.get(e["status"], e["status"]),
            "fonte_label": e.get("fonte"),
            "fonte_url": e.get("origem_url"),
            "confirmado": e["status"] == STATUS_CONFIRMADO,
        })

    documentos, _falhas = obter_documentos_watchlist(tuple(tickers))
    for d in documentos:
        if d["tipo"] != "PROVENTOS":
            continue
        data_doc = _parse_data(d["data"])
        if data_doc is None or not (inicio <= data_doc <= fim):
            continue
        catalisadores_lista.append({
            "ticker": d["ticker"],
            "empresa": d["ticker"],
            "categoria": "Proventos (dividendo/JCP)",
            "data": data_doc,
            "status": STATUS_CONFIRMADO,  # documento ja protocolado na CVM - nao e' estimativa
            "status_label": STATUS_LABEL[STATUS_CONFIRMADO],
            "fonte_label": "CVM (documento oficial)",
            "fonte_url": d["link"],
            "confirmado": True,
        })

    catalisadores_lista.sort(key=lambda c: (c["data"], -PRIORIDADE_STATUS.get(c["status"], 0)))
    return catalisadores_lista


# ============================================================
# D. RISCO DA CARTEIRA - cálculo real quando o usuário tem posição
# cadastrada (quantidade + preço médio por ativo, tabela posicoes_carteira
# - ver data/posicoes.py); aviso honesto, SEM calcular nada, quando não há
# nenhuma posição cadastrada. Watchlist (lista de tickers, sem peso/
# quantidade) NUNCA é usada como proxy de carteira (regra explícita do
# projeto) - mesmo com posição cadastrada, concentração/correlação/
# volatilidade/drawdown/cenários só consideram os ativos com posição real.
# ============================================================

_PERIODO_RISCO = "6M"  # janela de historico (retornos diarios) pra correlacao/volatilidade/drawdown/cenario historico
_LIMIAR_CONCENTRACAO_PCT = 25  # so' sinaliza o numero (concentracao_ativo/setor acima disso) - nunca e' recomendacao
_CHOQUES_CENARIO_IBOV_PCT = (-10, -20)  # magnitudes do cenario de estresse por beta (ver _cenario_beta)


def _posicoes_com_cotacao(posicoes: list) -> tuple:
    """Cada posição + preço/valor atual (1 única requisição em lote via
    data/mercado.py:obter_cotacoes_lote, mesmo mecanismo da watchlist em
    app.py - evita N chamadas individuais ao Yahoo). Retorna
    (com_preco, tickers_sem_preco) - ticker cuja cotação falhou nunca
    entra no cálculo com um valor inventado, só é listado como ausente."""
    from data.mercado import obter_cotacoes_lote

    cotacoes = obter_cotacoes_lote(tuple(p["ticker"] for p in posicoes))
    com_preco, sem_preco = [], []
    for p in posicoes:
        cot = cotacoes.get(p["ticker"], {"erro": "sem dado"})
        preco_atual = cot.get("preco") if not cot.get("erro") else None
        if not preco_atual:
            sem_preco.append(p["ticker"])
            continue
        quantidade, preco_medio = float(p["quantidade"]), float(p["preco_medio"])
        com_preco.append({
            "ticker": p["ticker"],
            "quantidade": quantidade,
            "preco_medio": preco_medio,
            "preco_atual": preco_atual,
            "valor_atual": quantidade * preco_atual,
            "valor_investido": quantidade * preco_medio,
            "lucro_pct": ((preco_atual - preco_medio) / preco_medio) * 100 if preco_medio else None,
        })
    return com_preco, sem_preco


def _concentracao(com_preco: list, valor_total: float) -> tuple:
    """(por_ativo, por_setor): cada um [{'nome','valor','peso_pct'}],
    ordenado por peso desc. Setor via config.IBOVESPA_SETORES (mesmo mapa
    da aba MERCADO/SETORES) - ticker sem entrada cai em 'Outros', nunca
    inventa classificação."""
    por_ativo = sorted(
        (
            {"nome": p["ticker"], "valor": p["valor_atual"], "peso_pct": p["valor_atual"] / valor_total * 100}
            for p in com_preco
        ),
        key=lambda x: -x["peso_pct"],
    )
    valores_setor = {}
    for p in com_preco:
        setor = config.IBOVESPA_SETORES.get(p["ticker"], "Outros")
        valores_setor[setor] = valores_setor.get(setor, 0) + p["valor_atual"]
    por_setor = sorted(
        ({"nome": s, "valor": v, "peso_pct": v / valor_total * 100} for s, v in valores_setor.items()),
        key=lambda x: -x["peso_pct"],
    )
    return por_ativo, por_setor


def _retornos_diarios_alinhados(tickers: list):
    """DataFrame (coluna por ticker) de retorno diário nos últimos
    _PERIODO_RISCO, só com as DATAS EM COMUM entre todos os ativos que
    tiverem histórico (dropna) - garante que correlação/volatilidade/
    drawdown da carteira comparam o mesmo dia pra todo ativo. None se
    nenhum ativo tiver histórico suficiente (>=10 pregões) ou sobrar menos
    de 5 datas em comum. Usa data/prices.py:obter_historico (mesmo
    histórico do gráfico de preços, já cacheado - nenhuma requisição
    nova)."""
    series = {}
    for t in tickers:
        df = obter_historico(t, _PERIODO_RISCO)
        if df is None or len(df) < 10:
            continue
        serie = df.set_index("Data")["Close"].pct_change().dropna()
        if not serie.empty:
            series[t] = serie
    if not series:
        return None
    df_ret = pd.DataFrame(series).dropna()
    return df_ret if not df_ret.empty and len(df_ret) >= 5 else None


def _serie_carteira(com_preco: list, df_ret) -> "pd.Series | None":
    """Retorno diário PONDERADO da carteira, só dos ativos presentes em
    `df_ret` (peso renormalizado entre eles - ex: 1 ativo sem histórico
    numa carteira de 3 não quebra o cálculo dos outros 2, só fica de fora,
    listado em tickers_sem_historico pra quem chama)."""
    if df_ret is None:
        return None
    valor_considerado = sum(p["valor_atual"] for p in com_preco if p["ticker"] in df_ret.columns)
    if not valor_considerado:
        return None
    pesos = pd.Series({
        p["ticker"]: p["valor_atual"] / valor_considerado
        for p in com_preco if p["ticker"] in df_ret.columns
    })
    return (df_ret[pesos.index] * pesos).sum(axis=1)


def _drawdown_maximo_pct(serie_retornos) -> float | None:
    """Maior queda (pico ao vale, %) da carteira ponderada dentro da
    janela _PERIODO_RISCO - histórico real, não projeção."""
    if serie_retornos is None or serie_retornos.empty:
        return None
    patrimonio = (1 + serie_retornos).cumprod()
    drawdown = (patrimonio / patrimonio.cummax() - 1) * 100
    return float(drawdown.min())


def _cenario_beta(com_preco: list) -> dict | None:
    """Estimativa (CALCULO_INTERNO, nunca FATO) do impacto na carteira se
    o Ibovespa sofrer cada choque de _CHOQUES_CENARIO_IBOV_PCT, ponderando
    o beta real de cada ativo (data/prices.py:_calcular_beta - calculado
    localmente contra o índice de referência, cache de 1h; usado direto em
    vez de obter_indicadores() porque este faz várias outras chamadas ao
    Yahoo só pra devolver o mesmo beta). Só considera ativos com beta
    disponível (peso renormalizado entre eles) - None se nenhum tiver."""
    betas, sem_beta = {}, []
    for p in com_preco:
        beta = _calcular_beta(p["ticker"])
        if beta is None:
            sem_beta.append(p["ticker"])
        else:
            betas[p["ticker"]] = beta
    if not betas:
        return None
    valor_considerado = sum(p["valor_atual"] for p in com_preco if p["ticker"] in betas)
    beta_carteira = sum(betas[t] * (v["valor_atual"] / valor_considerado) for v in com_preco if (t := v["ticker"]) in betas)
    return {
        "beta_carteira": beta_carteira,
        "tickers_sem_beta": sem_beta,
        "impacto_pct": {choque: beta_carteira * choque for choque in _CHOQUES_CENARIO_IBOV_PCT},
    }


def risco_carteira(sub: str, prefs: dict) -> dict:
    """Risco real da carteira (concentração por ativo/setor, correlação,
    volatilidade e drawdown históricos de _PERIODO_RISCO, cenários de
    estresse) quando `sub` tem posição cadastrada (ver data/posicoes.py) -
    aviso honesto, SEM NENHUM cálculo, nos casos em que falta dado real:
    banco indisponível (carteira_cadastrada=None), ninguém cadastrou nada
    ainda (False) ou nenhuma posição conseguiu cotação agora."""
    posicoes = obter_posicoes(sub)
    if posicoes is None:
        return {
            "carteira_cadastrada": None,
            "motivo": "Não foi possível consultar suas posições agora (banco indisponível) - tente de novo em alguns instantes.",
            "watchlist_tamanho": len(prefs.get("watchlist") or []),
        }
    if not posicoes:
        return {
            "carteira_cadastrada": False,
            "motivo": (
                "Você ainda não cadastrou nenhuma posição (quantidade e preço médio por ativo) - "
                "a watchlist é uma lista de acompanhamento, não uma carteira real."
            ),
            "o_que_falta": (
                "Pra calcular concentração por ativo/setor, correlação, volatilidade, drawdown e "
                "cenários de estresse de verdade, cadastre quantidade e preço médio de cada posição "
                "abaixo."
            ),
            "watchlist_tamanho": len(prefs.get("watchlist") or []),
        }

    com_preco, tickers_sem_preco = _posicoes_com_cotacao(posicoes)
    if not com_preco:
        return {
            "carteira_cadastrada": True,
            "sem_cotacao": True,
            "tickers_sem_preco": tickers_sem_preco,
            "motivo": "Nenhuma das posições cadastradas conseguiu cotação agora (fonte de preço indisponível) - tente de novo em alguns instantes.",
        }

    valor_total = sum(p["valor_atual"] for p in com_preco)
    por_ativo, por_setor = _concentracao(com_preco, valor_total)

    df_ret = _retornos_diarios_alinhados([p["ticker"] for p in com_preco])
    tickers_sem_historico = [p["ticker"] for p in com_preco if df_ret is None or p["ticker"] not in df_ret.columns]
    correlacao = df_ret.corr().round(4).to_dict() if df_ret is not None and len(df_ret.columns) >= 2 else None

    serie_carteira = _serie_carteira(com_preco, df_ret)
    volatilidade_anual_pct = float(serie_carteira.std() * (252 ** 0.5) * 100) if serie_carteira is not None else None
    drawdown_pct = _drawdown_maximo_pct(serie_carteira)
    maior_queda_diaria_pct = float(serie_carteira.min() * 100) if serie_carteira is not None else None

    return {
        "carteira_cadastrada": True,
        "valor_total": valor_total,
        "posicoes": com_preco,
        "tickers_sem_preco": tickers_sem_preco,
        "tickers_sem_historico": tickers_sem_historico,
        "concentracao_ativo": por_ativo,
        "concentracao_setor": por_setor,
        "limiar_concentracao_pct": _LIMIAR_CONCENTRACAO_PCT,
        "correlacao": correlacao,
        "periodo_historico": _PERIODO_RISCO,
        "volatilidade_anual_pct": volatilidade_anual_pct,
        "drawdown_pct": drawdown_pct,
        "maior_queda_diaria_pct": maior_queda_diaria_pct,
        "cenario_beta": _cenario_beta(com_preco),
        "watchlist_tamanho": len(prefs.get("watchlist") or []),
    }


# ============================================================
# E. RESEARCH COM EVIDÊNCIAS - feed compacto reaproveitando NEWS/CVM já
# buscados (nenhuma consulta nova além das que mudancas_tese/
# catalisadores já fazem) + notícias da watchlist.
# ============================================================

@st.cache_data(ttl=_TTL_AGREGACAO, show_spinner=False)
def evidencias_recentes(tickers: tuple, limite: int = 12) -> list:
    """Feed compacto (notícia OU documento CVM) pra abrir no dialog
    existente (ver ui/radar_tab.py:abrir_card_noticia/abrir_card_documento,
    que reaproveitam ui/news_tab.py e ui/cvm_tab.py). Cada item carrega
    '_tipo_item' ('noticia'/'documento') pra UI saber qual dialog abrir."""
    noticias, _falhas_news = obter_noticias_watchlist(list(tickers))
    documentos, _falhas_cvm = obter_documentos_watchlist(tuple(tickers))

    itens = []
    for n in noticias:
        itens.append({"_tipo_item": "noticia", "_data_ord": n["data"], "_payload": n})
    for d in documentos:
        if d["tipo"] not in ("FATO_RELEVANTE", "COMUNICADO", "RESULTADOS"):
            continue
        itens.append({"_tipo_item": "documento", "_data_ord": d["data"], "_payload": d})

    itens.sort(key=lambda i: i["_data_ord"], reverse=True)
    return itens[:limite]


# ============================================================
# F. COPILOTO DE RESEARCH - respostas DETERMINÍSTICAS construídas só a
# partir da evidência já agregada acima (sem chamada de IA nova - as
# perguntas sugeridas pelo pedido já têm resposta objetiva nos dados
# que o RADAR já tem; inventar uma síntese por LLM aqui arriscaria gerar
# "resposta confiante pra preencher a interface", que o pedido proíbe
# explicitamente). Cada resposta cita fonte/data real ou diz que não há
# evidência suficiente.
# ============================================================

PERGUNTAS_SUGERIDAS = [
    "O que mudou na tese desta empresa nos últimos 30 dias?",
    "Quais são os principais riscos desta tese?",
    "Quais eventos podem afetar este ativo?",
    "O que contradiz a interpretação apresentada?",
]


def _resposta_o_que_mudou(ticker: str) -> dict:
    alertas = [a for a in mudancas_tese((ticker,), "30 DIAS") if a["ticker"] == ticker]
    if not alertas:
        return {"resposta": f"Sem mudança de tese verificada pra {ticker} nos últimos 30 dias.", "evidencias": [], "tipo": TIPO_INSUFICIENTE}
    linhas = [f"[{a['data_evento'].strftime('%d/%m')}] {a['categoria']}: {a['descricao']}" for a in alertas]
    return {"resposta": " · ".join(linhas), "evidencias": alertas, "tipo": TIPO_FATO}


def _resposta_riscos(ticker: str) -> dict:
    linha = linha_valuation(ticker)
    alertas = linha.get("alerta_qualidade") or []
    if not alertas:
        return {
            "resposta": f"Nenhum sinal de risco identificável nos indicadores disponíveis de {ticker} (P/L, margem líquida, dívida/EBITDA).",
            "evidencias": [],
            "tipo": TIPO_INSUFICIENTE,
        }
    return {"resposta": "; ".join(alertas), "evidencias": [linha], "tipo": TIPO_CALCULO}


def _resposta_eventos(ticker: str) -> dict:
    eventos = [c for c in catalisadores((ticker,)) if c["ticker"] == ticker]
    if not eventos:
        return {"resposta": f"Nenhum evento de calendário (resultado/proventos) identificado pra {ticker} na janela coberta.", "evidencias": [], "tipo": TIPO_INSUFICIENTE}
    linhas = [f"[{e['data'].strftime('%d/%m')}] {e['categoria']} ({e['status_label']})" for e in eventos]
    return {"resposta": " · ".join(linhas), "evidencias": eventos, "tipo": TIPO_FATO}


def _resposta_contradicao(ticker: str) -> dict:
    # sem texto/justificativa persistido por trás de cada mudança (ver
    # 'argumento_contrario' em _montar_alerta_research, sempre None hoje)
    # - não há base pra apontar contradição sem inventar - resposta
    # honesta em vez de uma "resposta confiante pra preencher a tela".
    return {
        "resposta": (
            "Não há, hoje, evidência estruturada suficiente (texto/justificativa da própria fonte) "
            "pra apontar uma contradição de forma confiável - os dados agregados aqui são números "
            "(recomendação/preço-alvo/documento), não o racional por escrito de cada mudança."
        ),
        "evidencias": [],
        "tipo": TIPO_INSUFICIENTE,
    }


_RESPOSTAS_POR_PERGUNTA = {
    PERGUNTAS_SUGERIDAS[0]: _resposta_o_que_mudou,
    PERGUNTAS_SUGERIDAS[1]: _resposta_riscos,
    PERGUNTAS_SUGERIDAS[2]: _resposta_eventos,
    PERGUNTAS_SUGERIDAS[3]: _resposta_contradicao,
}


def responder_copiloto(pergunta: str, ticker: str) -> dict:
    """Resposta determinística (sem IA) pra uma das PERGUNTAS_SUGERIDAS,
    sempre citando fonte/data real ou declarando dado insuficiente.
    {"resposta": "pergunta não reconhecida", ...} se vier algo fora da
    lista (hoje a UI só oferece botões com as perguntas exatas)."""
    funcao = _RESPOSTAS_POR_PERGUNTA.get(pergunta)
    if funcao is None:
        return {"resposta": "Pergunta não reconhecida.", "evidencias": [], "tipo": TIPO_INSUFICIENTE}
    return funcao(ticker)
