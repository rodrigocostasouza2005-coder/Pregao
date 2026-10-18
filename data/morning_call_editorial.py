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

Separação fato/comentário: o jornal publica só FATO com fonte (cotação,
indicador, matéria com veículo e link; o texto vem do bloco RESUMO do
resumo já cacheado, nunca da LEITURA DE MERCADO do modelo). ACOMPANHAR
marca evento futuro da agenda. As 3 "interpretações" genéricas fixas que
saíam em toda edição foram retiradas (eram iguais todo dia - enchimento,
não informação).
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
from data.news import obter_resumos_prontos, obter_top_mercado_tudo, separar_secoes_resumo
from data.prices import obter_cotacao_indice, obter_historico

TZ_SP = ZoneInfo("America/Sao_Paulo")

TAG_FATO = "FATO"
TAG_ACOMPANHAR = "ACOMPANHAR"

_NOTA_STATUS_EVENTO = {
    STATUS_PRAZO_CVM: "prazo MÁXIMO regulatório da CVM (Instrução CVM 480/2009) — não é data anunciada pela empresa.",
    STATUS_CONFIRMADO: "data CONFIRMADA pela própria empresa/fonte oficial.",
    STATUS_ESTIMADO: "data ESTIMADA por fonte externa — ainda não confirmada pela empresa.",
}

LIMITACOES_PADRAO = (
    "Fontes gratuitas podem ter atraso e indisponibilidade; esta edição "
    "não garante cotação em tempo real.",
    "Não foram incluídos preços ou fatos que não puderam ser confirmados "
    "nesta execução.",
    "A agenda lista eventos previstos, não resultados já divulgados.",
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
                linhas.append({"indicador": nome, "referencia": "—", "detalhe": "indisponível", "valores": {}})
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
            # mesmos valores, numericos e por coluna original - o PDF
            # formata com a unidade documentada de cada serie (ver
            # data/macro.py) em vez de reaproveitar o texto montado acima
            valores_num = {}
            for coluna in colunas_valor:
                valor = ultimo.get(coluna)
                if not pd.notna(valor):
                    continue
                if isinstance(valor, (int, float)):
                    valores_num[coluna] = float(valor)
                rotulo_coluna = coluna.replace("_", " ")
                if coluna in colunas_inteiras:
                    valores.append(f"{rotulo_coluna}: {int(valor)}")
                elif isinstance(valor, (int, float)):
                    valores.append(f"{rotulo_coluna}: {_fmt_num(valor)}")
            linhas.append({
                "indicador": nome, "referencia": referencia,
                "detalhe": "; ".join(valores) if valores else "sem valor estruturado",
                "valores": valores_num,
            })
        except Exception:
            linhas.append({"indicador": nome, "referencia": "—", "detalhe": "indisponível", "valores": {}})
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


def _item_fato(item, pronto=None):
    """Manchete -> {titulo, link, veiculo, tag=FATO, ...} - veículo
    atribuído explicitamente (nunca um fato sem fonte visível no PDF).

    `pronto` = resultado JÁ CACHEADO do resumo desse grupo (ver
    _resumos_cacheados) - "corpo" recebe só os parágrafos do bloco RESUMO
    (separar_secoes_resumo); a LEITURA DE MERCADO (interpretação do
    modelo) fica de fora do jornal de propósito: o PDF publica fato com
    fonte, não opinião gerada. Sem resumo cacheado, corpo=[] e o renderer
    publica só a manchete com a fonte (nunca inventa texto)."""
    veiculos = item.get("veiculos") or []
    pronto = pronto or {}
    corpo = []
    if pronto.get("resumo"):
        try:
            corpo, _leitura = separar_secoes_resumo(pronto["resumo"])
        except Exception:
            corpo = []
    return {
        "titulo": str(item.get("titulo") or "").strip(),
        "link": str(item.get("link") or "").strip() or None,
        "veiculo": veiculos[0] if veiculos else None,
        "tag": TAG_FATO,
        "importancia": item.get("importancia") or 0,
        "data": item.get("data"),
        "tickers": list(item.get("tickers") or []),
        "corpo": corpo,
        "imagem": pronto.get("imagem"),
        "link_original": pronto.get("link_original"),
    }


def _resumos_cacheados(itens):
    """{link_do_grupo: resultado} dos resumos JÁ cacheados - uma única
    leitura em lote (obter_resumos_prontos nunca gera resumo nem chama IA).
    Falha de leitura -> {} (a edição sai só com manchetes, nunca quebra)."""
    grupos = [{"titulo": i.get("titulo"), "fontes": i.get("fontes") or [], "link": i.get("link")}
              for i in itens if i.get("link")]
    if not grupos:
        return {}
    try:
        return obter_resumos_prontos(grupos) or {}
    except Exception:
        return {}


def selecionar_manchete(fatos, n_chamadas=5):
    """(manchete, chamadas) da capa - a manchete é a matéria de MAIOR
    importância editorial (data/news.py:_calcular_importancia: veículos,
    recência, termos de mercado) entre as que têm texto publicável;
    nunca a que tem mais texto ou foto. Sem nenhuma matéria com texto, a
    de maior importância vira manchete só com título. Sem nenhuma
    notícia -> (None, []): a capa não inventa manchete."""
    ordenados = sorted(fatos, key=lambda f: f.get("importancia") or 0, reverse=True)
    if not ordenados:
        return None, []
    com_texto = [f for f in ordenados if f.get("corpo")]
    manchete = com_texto[0] if com_texto else ordenados[0]
    chamadas = [f for f in ordenados if f is not manchete][:n_chamadas]
    return manchete, chamadas


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
    # Limite de extensão da edição (o PDF cresce com o conteúdo, mas não
    # sem limite): as N mais importantes de cada editoria.
    def _top(itens, limite):
        return sorted(itens, key=lambda i: i.get("importancia") or 0, reverse=True)[:limite]

    brasil_sel = _top(brasil_bruto, 8)
    exterior_sel = _top(exterior_bruto, 8)
    empresas_sel = _top(empresas_bruto, 6)
    prontos = _resumos_cacheados(brasil_sel + exterior_sel + empresas_sel)

    def _fatos(itens):
        return [_item_fato(i, prontos.get(i.get("link"))) for i in itens]

    noticias_brasil = _fatos(brasil_sel)
    noticias_exterior_fatos = _fatos(exterior_sel)
    noticias_empresas = _fatos(empresas_sel)
    todos_fatos = noticias_brasil + noticias_empresas + noticias_exterior_fatos
    manchete, chamadas = selecionar_manchete(todos_fatos)

    edicao = {
        "agora": agora,
        "capa": {
            "indicadores": [ibov, dolar],
            "destaques": sorted(todos_fatos, key=lambda f: f["importancia"], reverse=True)[:3],
            "manchete": manchete,
            "chamadas": chamadas,
        },
        "brasil": {
            "indicadores": [ibov, dolar] + _macro_rows(),
            "historico_ibov": _serie_fechamento("^BVSP", "1M"),
            "noticias": noticias_brasil or None,
            "noticias_erro": noticias_erro,
        },
        "exterior": {
            "indicadores": [sp500, nasdaq, ouro, petroleo],
            "historico_petroleo": _serie_fechamento("BZ=F", "1M"),
            "noticias": noticias_exterior_fatos or None,
            "noticias_erro": noticias_erro,
        },
        "empresas": {
            "cards": noticias_empresas,
            "agenda": _agenda_hoje(agora),
            "noticias_erro": noticias_erro,
        },
        "limitacoes": LIMITACOES_PADRAO,
        "fontes": FONTES_PADRAO,
    }
    return edicao
