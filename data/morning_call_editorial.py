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
import re
import unicodedata
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

import config
from data.eventos import (
    STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_LABEL, STATUS_PRAZO_CVM,
    calcular_calendario_cacheado,
)
from data.macro import (
    motivo_indisponivel, obter_cdi, obter_focus_ipca, obter_focus_selic, obter_selic_meta,
)
from data.news import (
    obter_resumos_prontos, obter_top_mercado, obter_top_mercado_internacional, separar_secoes_resumo,
)
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


def _referencia_cotacao(cot):
    """Rótulo de referência de uma cotação + data da sessão (date).

    Causa dos horários '16/10 00:00', '16/10 01:00' e '17/10 20:00' na
    edição de 18/10/2026: _barra_em é o índice da barra DIÁRIA do Yahoo,
    que fica sempre à meia-noite no fuso da bolsa (São Paulo, Nova York,
    Londres no câmbio) - convertida para Brasília virava um 'horário' que
    não é de negócio nenhum. Agora: com o horário do último negócio da
    fonte (regularMarketTime, mesmo dia da barra) mostra esse horário em
    Brasília; sem ele, só 'fech. dd/mm' da sessão - nunca um horário
    inventado. A data da sessão é a do fuso da própria bolsa."""
    sessao = None
    try:
        barra = datetime.fromisoformat(cot.get("_barra_em"))
        sessao = barra.date()
    except (TypeError, ValueError):
        barra = None
    negocio = cot.get("_negocio_em")
    if negocio:
        rotulo = brt_label(negocio)
    elif sessao:
        rotulo = f"fech. {sessao.strftime('%d/%m')}"
    else:
        rotulo = None
    if rotulo and cot.get("_fallback_cache"):
        rotulo += " (cache)"
    return rotulo, sessao


def _indicador(nome, ticker):
    """Mesma leitura 1x de data/prices.py:obter_cotacao_indice usada pelo
    e-mail em texto simples - nunca um valor novo/recalculado aqui."""
    cot = obter_cotacao_indice(nome, ticker)
    if not isinstance(cot, dict) or cot.get("erro"):
        erro = cot.get("erro", "sem dado") if isinstance(cot, dict) else "sem dado"
        return {"nome": nome, "preco": None, "variacao_pct": None, "barra_fmt": None, "sessao": None,
                "erro": erro}
    rotulo, sessao = _referencia_cotacao(cot)
    return {
        "nome": nome,
        "preco": cot.get("preco"),
        "variacao_pct": cot.get("variacao_pct"),
        "barra_fmt": rotulo,
        "sessao": sessao,
        "erro": None,
    }


_DIAS_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira",
                "sábado", "domingo")


def nota_sessao(indicadores, agora):
    """Aviso quando as cotações vêm de uma sessão anterior ao dia da
    edição (fim de semana, feriado, antes da abertura): a 'variação' é a
    da última sessão, não a de hoje. None quando todas são de hoje."""
    sessoes = [i.get("sessao") for i in indicadores if i.get("sessao")]
    if not sessoes:
        return None
    ultima = max(sessoes)
    if ultima >= agora.date():
        return None
    texto = (f"Cotações e variações referem-se à última sessão disponível "
             f"({_DIAS_SEMANA[ultima.weekday()]}, {ultima.strftime('%d/%m')}), "
             f"comparada com a sessão anterior")
    if agora.weekday() >= 5:
        texto += "; não há pregão no fim de semana"
    return texto + "."


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


def _data_br(valor):
    try:
        return pd.Timestamp(valor).strftime("%d/%m/%Y")
    except Exception:
        return None


def _linha_macro(indicador, valor, unidade, referencia, detalhe=None, erro=None):
    """Contrato de uma linha da tabela macro do PDF - valor numérico +
    unidade + referência já legíveis; nunca nome de coluna do DataFrame."""
    return {"indicador": indicador, "valor": valor, "unidade": unidade,
            "referencia": referencia or "—", "detalhe": detalhe, "erro": erro}


def _macro_rows(agora=None):
    """Linhas da tabela macro do PDF, normalizadas.

    Causa dos defeitos da edição de 18/10/2026 (auditoria): (1) as linhas
    eram montadas com o nome cru das colunas ("mediana pct: 3,79; media
    pct...; numero respondentes...") e o renderer procurava chaves que não
    existem nos dados reais ("valor"/"mediana"), caindo nesse texto bruto;
    (2) o Focus usava dado.iloc[-1], a ÚLTIMA linha da tabela por ano - o
    ano corrente + 2 (2028), não o ano corrente. Agora: Selic meta e CDI
    anualizado com a data da leitura; Focus IPCA e Selic para o ano
    corrente e o seguinte, com a data do boletim; sem dado -> 'indisponível'
    com o motivo (nunca um valor estimado)."""
    agora = agora or datetime.now(TZ_SP)
    linhas = []

    def _serie(nome, fn, coluna, chave_motivo):
        try:
            dado = fn()
        except Exception as exc:
            dado = None
            motivo = str(exc)[:200]
        else:
            motivo = None
        if isinstance(dado, pd.DataFrame) and not dado.empty and coluna in dado.columns:
            validos = dado.dropna(subset=[coluna])
            if not validos.empty:
                ultimo = validos.iloc[-1]
                linhas.append(_linha_macro(nome, float(ultimo[coluna]), "% a.a.", _data_br(ultimo.get("data"))))
                return
        motivo = motivo or motivo_indisponivel(chave_motivo) or "Banco Central (SGS) sem dado nesta execução"
        linhas.append(_linha_macro(nome, None, "% a.a.", None, erro=motivo))

    _serie("Selic meta", obter_selic_meta, "selic_meta_pct", "selic")
    _serie("CDI", obter_cdi, "cdi_anualizado_pct", "cdi")

    for nome, fn in (("Focus IPCA", obter_focus_ipca), ("Focus Selic", obter_focus_selic)):
        try:
            dado = fn()
        except Exception:
            dado = None
        anos = (agora.year, agora.year + 1)
        if not isinstance(dado, pd.DataFrame) or dado.empty or "ano_referencia" not in dado.columns:
            linhas.append(_linha_macro(f"{nome} {anos[0]}", None, "%", None,
                                       erro="Boletim Focus sem dado nesta execução"))
            continue
        for ano in anos:
            sel = dado[dado["ano_referencia"].astype(int) == ano]
            if sel.empty or pd.isna(sel.iloc[0].get("mediana_pct")):
                linhas.append(_linha_macro(f"{nome} {ano}", None, "%", None,
                                           erro=f"Focus sem projeção para {ano}"))
                continue
            r = sel.iloc[0]
            resp = r.get("numero_respondentes")
            detalhe = f"{int(resp)} respondentes" if pd.notna(resp) else None
            boletim = _data_br(r.get("data_calculo"))
            linhas.append(_linha_macro(f"{nome} {ano}", float(r["mediana_pct"]), "%",
                                       f"boletim {boletim}" if boletim else None, detalhe=detalhe))
    return linhas


def _coletar_noticias():
    """Coleta as notícias das editorias: pool Brasil (obter_top_mercado)
    e pool internacional (obter_top_mercado_internacional), cada um com o
    próprio ranking. BR com ticker reconhecido -> empresas; BR sem ticker
    -> Brasil; INT -> Mundo.

    Causa da editoria Mundo vazia na edição de 18/10/2026: a coleta usava
    obter_top_mercado_tudo(), que junta os dois pools e corta o TOTAL nas
    20 mais importantes - naquele dia as 20 eram todas do pool Brasil
    (821 itens contra 110), e o internacional sumia inteiro. As funções
    usadas aqui são as mesmas do app (abas BRASIL/INTERNACIONAL do TOP
    MERCADO), sem nenhuma alteração no pipeline de notícias.

    erro != None distingue "a coleta falhou" de "funcionou mas não achou
    nada" (listas vazias). Um pool falhar sozinho não derruba o outro:
    o erro vem por região."""
    erros = {}
    pools = {}
    for regiao, fn in (("BR", obter_top_mercado), ("INT", obter_top_mercado_internacional)):
        try:
            itens = fn()
        except Exception as exc:
            erros[regiao] = f"{type(exc).__name__}: {exc}"
            itens = None
        if itens is None and regiao not in erros:
            erros[regiao] = "coleta do Google News falhou nesta execução"
        pools[regiao] = itens if isinstance(itens, list) else []
    brasil, empresas = [], []
    for item in pools["BR"]:
        (empresas if item.get("tickers") else brasil).append(item)
    return erros, brasil, empresas, list(pools["INT"])


# Itens de serviço que o pool de "negócios" do Google News às vezes traz
# e que não são notícia de mercado (achado real: "Resultado da Quina" no
# topo da edição de 18/10/2026). Filtro editorial do PDF, por título.
_TERMOS_FORA_DE_PAUTA = ("quina", "mega-sena", "mega sena", "lotofacil", "lotomania", "loteria",
                         "dupla sena", "timemania", "dia de sorte", "+milionaria", "horoscopo")


def _fora_de_pauta(titulo):
    texto = _sem_acento(titulo).lower()
    return any(re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z])", texto) for t in _TERMOS_FORA_DE_PAUTA)


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto or "")) if not unicodedata.combining(c))


def inicio_janela_noticias(agora):
    """06:00 (Brasília) do dia útil anterior ao da edição. Segunda-feira
    -> sexta 06:00 (cobre o fim de semana); domingo -> sexta 06:00."""
    dia = agora.date() - timedelta(days=1)
    while dia.weekday() >= 5:
        dia -= timedelta(days=1)
    return datetime.combine(dia, time(6, 0), tzinfo=TZ_SP)


def _data_item(item):
    try:
        momento = datetime.fromisoformat(str(item.get("data")))
    except (TypeError, ValueError):
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=TZ_SP)


_PERCENTUAL = re.compile(r"\d+(?:[.,]\d+)?\s?%")
_PALAVRAS_VAZIAS = {"de", "da", "do", "das", "dos", "e", "em", "com", "a", "o", "as", "os", "no", "na",
                    "nos", "nas", "por", "para", "que", "hoje", "fecha", "sobe", "cai", "alta", "queda",
                    "the", "of", "to", "in", "and", "on", "for"}


def _assinatura(titulo):
    texto = _sem_acento(titulo).lower()
    pcts = {p.replace(" ", "").replace(".", ",") for p in _PERCENTUAL.findall(texto)}
    palavras = {w for w in re.findall(r"[a-z]{4,}", texto) if w not in _PALAVRAS_VAZIAS}
    return pcts, palavras


def _mesmo_fato(a, b):
    """Duas manchetes sobre o mesmo número do mesmo assunto ('IBOVESPA
    fecha hoje com alta de 0,54%' x 'Ibovespa sobe 0,54% ...') - o
    agrupador do pipeline de notícias deixou as duas em grupos separados
    na edição de 18/10/2026. Regra estrita de propósito: mesmo percentual
    E ao menos uma palavra de conteúdo em comum."""
    pa, wa = _assinatura(a.get("titulo"))
    pb, wb = _assinatura(b.get("titulo"))
    return bool(pa & pb) and bool(wa & wb)


def filtrar_noticias(itens, agora):
    """Seleção editorial do PDF (não altera o pipeline de notícias):
    descarta itens fora da janela da edição (publicados antes de 06:00 do
    dia útil anterior, ou com data no futuro), itens fora de pauta
    (loterias) e duplicatas do mesmo fato (fica o de maior importância).
    Item sem data é descartado - não dá pra afirmar que é recente."""
    inicio = inicio_janela_noticias(agora)
    limite_futuro = agora + timedelta(hours=1)
    candidatos = []
    for item in itens or []:
        momento = _data_item(item)
        if momento is None or momento < inicio or momento > limite_futuro:
            continue
        if _fora_de_pauta(item.get("titulo")):
            continue
        candidatos.append(item)
    candidatos.sort(key=lambda i: i.get("importancia") or 0, reverse=True)
    escolhidos = []
    for item in candidatos:
        if any(_mesmo_fato(item, e) for e in escolhidos):
            continue
        escolhidos.append(item)
    return escolhidos


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

    # Uma única coleta de notícias - as 3 seções e a capa precisam ver
    # EXATAMENTE o mesmo conjunto de itens.
    erros_noticias, brasil_bruto, empresas_bruto, exterior_bruto = _coletar_noticias()
    # filtro editorial (janela, fora de pauta, duplicatas) no pool Brasil
    # inteiro antes de separar Brasil/Empresas, pra dedupe valer entre as duas
    br_ok = {id(i) for i in filtrar_noticias((brasil_bruto or []) + (empresas_bruto or []), agora)}
    brasil_bruto = [i for i in brasil_bruto or [] if id(i) in br_ok]
    empresas_bruto = [i for i in empresas_bruto or [] if id(i) in br_ok]
    exterior_bruto = filtrar_noticias(exterior_bruto or [], agora)
    erro_br = erros_noticias.get("BR")
    erro_int = erros_noticias.get("INT")
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
            "indicadores": [ibov, dolar] + _macro_rows(agora),
            "historico_ibov": _serie_fechamento("^BVSP", "1M"),
            "noticias": noticias_brasil or None,
            "noticias_erro": erro_br,
        },
        "exterior": {
            "indicadores": [sp500, nasdaq, ouro, petroleo],
            "historico_petroleo": _serie_fechamento("BZ=F", "1M"),
            "noticias": noticias_exterior_fatos or None,
            "noticias_erro": erro_int,
        },
        "empresas": {
            "cards": noticias_empresas,
            "agenda": _agenda_hoje(agora),
            "noticias_erro": erro_br,
        },
        "mercados_nota": nota_sessao([ibov, dolar, sp500, nasdaq, ouro, petroleo], agora),
        "janela_noticias": inicio_janela_noticias(agora),
        "limitacoes": LIMITACOES_PADRAO,
        "fontes": FONTES_PADRAO,
    }
    return edicao
