# -*- coding: utf-8 -*-
"""Camada de preparação editorial do Morning Call em PDF.

Monta uma estrutura de dados pura (dict), sem nenhum import de biblioteca
de PDF/gráfico - jobs/morning_call_pdf.py (camada de apresentação,
ReportLab) consome o dict devolvido por montar_edicao() e nunca chama
provedor nenhum diretamente. Separação exigida pela missão: dados !=
layout, cada camada testável sem a outra (sem rede em teste de nenhuma
das duas).

Reaproveita os MESMOS provedores que jobs/morning_call.py já usa
(data/prices.py, data/macro.py, data/news.py, data/eventos.py) - nunca
reconsulta nem reformula um número/fato com regra própria diferente da
do e-mail em texto simples (mesma fonte única de verdade).

TAGS editoriais (exigência explícita da missão, nunca misturadas):
FATO = reportado por uma fonte identificada (cotação, indicador,
manchete com link/veículo). INTERPRETAÇÃO = leitura de cenário/risco,
nunca um número novo (mesmas 3 linhas de TENDÊNCIAS E RISCOS do
e-mail-texto - jobs/morning_call.py - única fonte de verdade,
reaproveitada aqui, nunca duplicada com texto diferente). ACOMPANHAR =
evento futuro da agenda (ainda não aconteceu - por definição não é fato
consumado nem interpretação de risco).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import config
from data.eventos import (
    STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_LABEL, STATUS_PRAZO_CVM,
    calcular_calendario_cacheado,
)
from data.macro import obter_cdi, obter_focus_ipca, obter_focus_selic, obter_selic_meta
from data.news import obter_resumos_prontos, obter_top_mercado_tudo
from data.prices import obter_cotacao_indice, obter_historico

TZ_SP = ZoneInfo("America/Sao_Paulo")

TAG_FATO = "FATO"
TAG_INTERPRETACAO = "INTERPRETAÇÃO"
TAG_ACOMPANHAR = "ACOMPANHAR"

_NOTA_STATUS_EVENTO = {
    STATUS_PRAZO_CVM: "prazo MÁXIMO regulatório da CVM (Instrução CVM 480/2009) — não é data anunciada pela empresa.",
    STATUS_CONFIRMADO: "data CONFIRMADA pela própria empresa/fonte oficial.",
    STATUS_ESTIMADO: "data ESTIMADA por fonte externa — ainda não confirmada pela empresa.",
}

# Mesmas 3 linhas de TENDÊNCIAS E RISCOS do e-mail em texto simples
# (jobs/morning_call.py) - única fonte de verdade pra interpretação de
# cenário; nunca reescritas aqui com palavras diferentes (duplicaria
# conteúdo editorial com 2 formulações divergentes do mesmo risco).
INTERPRETACOES_PADRAO = (
    "Risco global: acompanhe a direção dos futuros americanos, dólar e "
    "commodities; confirme os movimentos nas fontes originais.",
    "Brasil: observe juros futuros, câmbio e notícias fiscais/políticas; "
    "o efeito depende da surpresa frente às expectativas.",
    "Empresas: valide comunicados oficiais e resultados antes de "
    "atribuir causalidade a movimentos de preço.",
)

LIMITACOES_PADRAO = (
    "Fontes gratuitas podem ter atraso e indisponibilidade; esta edição "
    "não garante cotação em tempo real.",
    "Não foram incluídos preços ou fatos que não puderam ser confirmados "
    "nesta execução.",
    "Itens marcados INTERPRETAÇÃO são leitura de cenário, não fato nem "
    "previsão garantida; itens marcados ACOMPANHAR são eventos futuros, "
    "não resultados já ocorridos.",
    "Conteúdo informativo, não constitui recomendação de investimento.",
)

FONTES_PADRAO = (
    "Cotações: Yahoo Finance (yfinance) — dados podem ter atraso conforme o provedor.",
    "Indicadores macro: Banco Central do Brasil (Selic/CDI) e Boletim Focus (BCB).",
    "Agenda de resultados: CVM (Instrução CVM 480/2009) — ver nota de confiabilidade em cada evento.",
    "Notícias: Google News (agregador); veículo original e link em cada manchete.",
)


def _fmt_num(valor, casas=2):
    try:
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "indisponível"


def brt_label(iso_str):
    """Converte um ISO 8601 com fuso (de hist.index[-1].isoformat(), que
    vem no fuso LOCAL DA FONTE/bolsa - ex: Nova York pra futuros dos EUA,
    São Paulo pro Ibovespa) pra um rótulo SEMPRE em horário de Brasília,
    explícito ('horário de Brasília') - causa real do sintoma relatado
    ("barras de datas e fusos diferentes", relatório de 17/10/2026): cada
    índice aparecia com o horário/fuso CRU da própria fonte, nunca
    convertido pra um fuso comum, então duas linhas lado a lado pareciam
    inconsistentes mesmo as duas estando corretas na sua própria fonte.

    Usa datetime.fromisoformat (nunca aritmética manual de offset) +
    .astimezone(TZ_SP) - única forma correta de converter um ISO com
    offset/zoneinfo próprio pra outro fuso (ver ZoneInfo, nunca
    timedelta fixo: alguns fusos de origem observam horário de verão,
    BRT não desde 2019 - um deslocamento fixo erraria o resultado em
    parte do ano)."""
    if not iso_str:
        return "indisponível"
    try:
        momento = datetime.fromisoformat(iso_str)
        if momento.tzinfo is None:
            return str(iso_str)
        return momento.astimezone(TZ_SP).strftime("%d/%m %H:%M") + " (horário de Brasília)"
    except (TypeError, ValueError):
        return str(iso_str)


def _indicador(nome, ticker):
    """Mesma leitura 1x de data/prices.py:obter_cotacao_indice usada pelo
    e-mail em texto simples - nunca um valor novo/recalculado aqui."""
    cot = obter_cotacao_indice(nome, ticker)
    if not isinstance(cot, dict) or cot.get("erro"):
        erro = cot.get("erro", "sem dado") if isinstance(cot, dict) else "sem dado"
        return {"nome": nome, "preco": None, "variacao_pct": None, "barra_fmt": None, "erro": erro}
    return {
        "nome": nome,
        "preco": cot.get("preco"),
        "variacao_pct": cot.get("variacao_pct"),
        "barra_fmt": brt_label(cot.get("_barra_em")),
        "erro": None,
    }


def _serie_fechamento(ticker, periodo_label="1M"):
    """Série (data, close) pro mini-gráfico de página - None/lista vazia
    em qualquer falha (ticker sem histórico, fonte fora do ar) nunca
    propaga exceção pra quem monta a edição; jobs/morning_call_pdf.py
    trata lista vazia como "gráfico indisponível", nunca inventa ponto."""
    try:
        df = obter_historico(ticker, periodo_label)
        if df is None or df.empty:
            return []
        pontos = df[["Data", "Close"]].dropna()
        return [(row["Data"], float(row["Close"])) for _, row in pontos.iterrows()]
    except Exception:
        return []


def _macro_rows():
    """Última leitura de cada indicador macro, como linhas de tabela
    estruturadas (pro PDF) - mesma lógica de leitura de coluna por
    indicador (Selic/CDI usam 'data'; Focus usa 'ano_referencia') já
    usada em jobs/morning_call.py:montar_morning_call, nunca
    reinterpretada com regra diferente."""
    linhas = []
    for nome, fn in (("Selic", obter_selic_meta), ("CDI", obter_cdi),
                      ("Focus IPCA", obter_focus_ipca), ("Focus Selic", obter_focus_selic)):
        try:
            dado = fn()
            if not isinstance(dado, pd.DataFrame) or dado.empty:
                linhas.append({"indicador": nome, "referencia": "—", "detalhe": "indisponível"})
                continue
            coluna_rotulo = "data" if "data" in dado.columns else (
                "ano_referencia" if "ano_referencia" in dado.columns else None
            )
            colunas_inteiras = {"ano_referencia", "numero_respondentes"}
            colunas_valor = [c for c in dado.columns if c != coluna_rotulo]
            ultimo = dado.iloc[-1]
            bruto_rotulo = ultimo.get(coluna_rotulo) if coluna_rotulo else None
            referencia = (
                f"{int(bruto_rotulo)}" if coluna_rotulo == "ano_referencia" and pd.notna(bruto_rotulo)
                else str(bruto_rotulo)[:10] if coluna_rotulo and pd.notna(bruto_rotulo) else "—"
            )
            valores = []
            for coluna in colunas_valor:
                valor = ultimo.get(coluna)
                if not pd.notna(valor):
                    continue
                rotulo_coluna = coluna.replace("_", " ")
                if coluna in colunas_inteiras:
                    valores.append(f"{rotulo_coluna}: {int(valor)}")
                elif isinstance(valor, (int, float)):
                    valores.append(f"{rotulo_coluna}: {_fmt_num(valor)}")
            linhas.append({
                "indicador": nome, "referencia": referencia,
                "detalhe": "; ".join(valores) if valores else "sem valor estruturado",
            })
        except Exception:
            linhas.append({"indicador": nome, "referencia": "—", "detalhe": "indisponível"})
    return linhas


def _coletar_noticias():
    """Mesma coleta/classificação de jobs/morning_call.py - BR com ticker
    reconhecido -> empresas; BR sem ticker -> macro Brasil; INT ->
    exterior. Nunca reclassificado com regra própria, nunca refeito.

    erro != None distingue "a coleta falhou" (precisa dizer isso
    explicitamente em cada seção) de "a coleta funcionou mas não achou
    nada pra essa categoria agora" (listas vazias) - mesma distinção que
    jobs/morning_call.py já faz com noticias_erro."""
    try:
        noticias = obter_top_mercado_tudo()
        candidatos = noticias if isinstance(noticias, list) else []
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}", [], [], []
    brasil, empresas, exterior = [], [], []
    for item in candidatos:
        if item.get("regiao") == "BR":
            (empresas if item.get("tickers") else brasil).append(item)
        else:
            exterior.append(item)
    return None, brasil, empresas, exterior


def _item_fato(item):
    """Manchete -> {titulo, link, veiculo, tag=FATO} - veículo atribuído
    explicitamente (nunca um fato sem fonte visível no PDF)."""
    veiculos = item.get("veiculos") or []
    return {
        "titulo": str(item.get("titulo") or "").strip(),
        "link": str(item.get("link") or "").strip() or None,
        "veiculo": veiculos[0] if veiculos else None,
        "tag": TAG_FATO,
    }


def _destaque(itens):
    """'Destaque' de página = a manchete de maior importância do grupo,
    atribuída ao veículo - nunca uma citação textual inventada (não há
    fonte de aspas verbatim de pessoa nenhuma neste pipeline; usar a
    própria manchete, atribuída, preserva o efeito editorial do mockup
    sem fabricar uma frase que ninguém disse)."""
    if not itens:
        return None
    melhor = max(itens, key=lambda i: i.get("importancia") or 0)
    return _item_fato(melhor)


def _cards_empresas(itens, limite=4):
    """Cards com foto pra EMPRESAS E SETORES - usa SÓ
    data/news.py:obter_resumos_prontos (leitura em lote do cache já
    existente, sem custo de rede/IA novo aqui) pra resumo+imagem; grupo
    sem resumo cacheado ainda aparece como card, só sem foto/resumo
    (nunca inventa um resumo nem baixa imagem on-demand - ver docstring
    de obter_resumos_prontos)."""
    selecionados = itens[:limite]
    if not selecionados:
        return []
    grupos = [{"titulo": i.get("titulo"), "fontes": i.get("fontes") or [], "link": i.get("link")} for i in selecionados]
    try:
        prontos = obter_resumos_prontos(grupos)
    except Exception:
        prontos = {}
    cards = []
    for item in selecionados:
        fato = _item_fato(item)
        pronto = prontos.get(item.get("link")) or {}
        cards.append({
            **fato,
            "resumo": pronto.get("resumo"),
            "imagem": pronto.get("imagem"),
            "link_original": pronto.get("link_original") or fato["link"],
        })
    return cards


def _linha_evento(evento):
    status = evento.get("status")
    rotulo_status = STATUS_LABEL.get(status, status or "status desconhecido")
    nota_status = _NOTA_STATUS_EVENTO.get(status, "nível de confiabilidade da data não identificado.")
    empresa = evento.get("empresa") or evento.get("ticker") or "Empresa não identificada"
    return {
        "empresa": empresa,
        "ticker": evento.get("ticker") or "?",
        "tipo_evento": evento.get("tipo_evento") or "EVENTO",
        "periodo": evento.get("periodo") or "",
        "horario": evento.get("horario") or "sem horário divulgado",
        "status_rotulo": rotulo_status,
        "status_nota": nota_status,
        "tag": TAG_ACOMPANHAR,
    }


def _agenda_hoje(agora):
    try:
        tickers = list(config.IBOVESPA_SETORES.keys())
        eventos = calcular_calendario_cacheado(tickers, hoje=agora.date())
        eventos_hoje = [e for e in eventos if e.get("data") == agora.date()]
        eventos_hoje.sort(key=lambda e: (e.get("horario") or "99:99", e.get("ticker") or ""))
        return [_linha_evento(e) for e in eventos_hoje]
    except Exception:
        return None


def montar_edicao(agora=None):
    """Monta a edição completa do Morning Call em PDF - um dict puro
    (capa/brasil/exterior/empresas/fontes/limitações), sem nenhuma
    dependência de ReportLab/Pillow. Cada seção degrada graciosamente
    (lista vazia/None + motivo) em vez de lançar exceção - mesmo espírito
    de jobs/morning_call.py: falha de UMA fonte nunca derruba a edição
    inteira nem é omitida em silêncio."""
    agora = agora or datetime.now(TZ_SP)

    ibov = _indicador("Ibovespa", "^BVSP")
    dolar = _indicador("Dólar (USD/BRL)", "USDBRL=X")
    sp500 = _indicador("S&P 500 futuro", "ES=F")
    nasdaq = _indicador("Nasdaq futuro", "NQ=F")
    ouro = _indicador("Ouro", "GC=F")
    petroleo = _indicador("Petróleo Brent", "BZ=F")

    # Uma única coleta de notícias (obter_top_mercado_tudo já é
    # cacheada, mas chamar 1x só aqui evita depender desse cache pra
    # consistência - as 3 seções abaixo e a capa precisam ver EXATAMENTE
    # o mesmo conjunto de itens, nunca uma segunda leitura que poderia
    # vir diferente entre chamadas).
    noticias_erro, brasil_bruto, empresas_bruto, exterior_bruto = _coletar_noticias()
    brasil_bruto = brasil_bruto or []
    empresas_bruto = empresas_bruto or []
    exterior_bruto = exterior_bruto or []
    noticias_brasil = [_item_fato(i) for i in brasil_bruto]
    noticias_exterior_fatos = [_item_fato(i) for i in exterior_bruto]

    def _top_capa(fatos_brutos, limite=3):
        ordenados = sorted(fatos_brutos, key=lambda i: i.get("importancia") or 0, reverse=True)
        return [_item_fato(i) for i in ordenados[:limite]]

    todos_brutos = brasil_bruto + empresas_bruto + exterior_bruto

    edicao = {
        "agora": agora,
        "capa": {
            "indicadores": [ibov, dolar],
            "destaques": _top_capa(todos_brutos, 3),
        },
        "brasil": {
            "indicadores": [ibov, dolar] + _macro_rows(),
            "historico_ibov": _serie_fechamento("^BVSP", "1M"),
            "destaque": _destaque(brasil_bruto),
            "noticias": noticias_brasil[:8] or None,
            "noticias_erro": noticias_erro,
        },
        "exterior": {
            "indicadores": [sp500, nasdaq, ouro, petroleo],
            "historico_petroleo": _serie_fechamento("BZ=F", "1M"),
            "destaque": _destaque(exterior_bruto),
            "noticias": noticias_exterior_fatos[:8] or None,
            "noticias_erro": noticias_erro,
            "interpretacoes": [
                {"texto": t, "tag": TAG_INTERPRETACAO} for t in INTERPRETACOES_PADRAO
            ],
        },
        "empresas": {
            "cards": _cards_empresas(empresas_bruto),
            "agenda": _agenda_hoje(agora),
            "noticias_erro": noticias_erro,
        },
        "limitacoes": LIMITACOES_PADRAO,
        "fontes": FONTES_PADRAO,
    }
    return edicao
