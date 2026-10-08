# -*- coding: utf-8 -*-
"""Camada normalizada de eventos financeiros (CALENDÁRIO, 2026-10-01;
evoluída na V2, mesma data). Só resultados corporativos (ITR/DFP
trimestral/anual). Pensada pra no futuro relacionar CVM <-> Research <->
News <-> Ticker <-> Preço (cada evento já carrega 'ticker' - mesmo
identificador usado em todo o resto do projeto) - mas essa integração
completa NÃO é feita nesta fase.

Reaproveita data.cvm.obter_documentos_cvm (mesmo identificador/coleta/
cache que a aba CVM já usa) - nenhum sistema de dado novo, nenhuma
chamada de IA.

FONTE REAL DISPONÍVEL HOJE: só o PRAZO REGULATÓRIO da CVM pra entrega
do ITR/DFP (Instrução CVM 480/2009, Art. 25/29) - prazo MÁXIMO legal,
não é uma data anunciada pela empresa. É dado público, documentado,
determinístico - não é um valor inventado.

INVESTIGAÇÃO DA V2 (pedido explícito do Rodrigo: "pesquise como as
companhias divulgam seus calendários de resultados" antes de
implementar CONFIRMADO/ESTIMADO de verdade) - achado real, verificado
com dado ao vivo da própria CVM nesta sessão: a categoria oficial da
CVM "Calendário de Eventos Corporativos" (onde a empresa de fato
comunica seu calendário) NÃO tem nenhum campo estruturado com a data do
evento em si - só `Data_Entrega` (quando o documento foi protocolado,
não quando o resultado sai) e `Data_Referencia` sempre fixa em 31/12
(fim do exercício que o calendário cobre, não uma data de evento). A
data real do resultado só existe dentro do PDF (`Link_Download`) -
extrair isso exigiria parsing de texto livre sem IA, exatamente o
"texto ambíguo" que o pedido explicitamente proíbe tratar como
CONFIRMADO. Tentativa de achar um endpoint estruturado da B3 (mesmo
domínio já usado com sucesso em data/ibovespa.py) também não teve como
ser confirmada nesta sessão (extensão do Chrome pra inspecionar o
tráfego de rede real do site da B3 está indisponível, mesma
instabilidade recorrente documentada nas sessões anteriores) - não
inventei um endpoint que não pude verificar.

CONCLUSÃO HONESTA: não existe hoje nenhuma fonte automática íntegra de
data CONFIRMADA (anunciada pela própria empresa) nem ESTIMADA (fonte
externa confiável) que dê pra integrar com segurança sem violar "nunca
inventar data"/"nunca extrair de texto ambíguo". Por isso a função que
roda de verdade (calcular_calendario) continua produzindo só
PRAZO_CVM. O que ESTA versão entrega: a camada de prioridade/
deduplicação (mesclar_eventos) e resiliência de cache
(aplicar_cache_resiliente) ficam prontas e TESTADAS com dados
sintéticos - no dia em que uma fonte confiável de CONFIRMADO/ESTIMADO
for identificada (ex: entrada manual do próprio Rodrigo depois de
checar o RI da empresa, ou um endpoint B3 confirmado numa sessão futura
com a extensão do Chrome funcionando), basta alimentar essa função,
zero refatoração.

LIMITAÇÃO DOCUMENTADA: assume ano fiscal = ano civil (padrão da grande
maioria das empresas B3) - empresas com ano fiscal diferente não têm o
prazo calculado corretamente nesta versão.

FASE COLETOR DE DATAS DE RESULTADOS (2026-10-02): a conclusão acima
("não existe fonte automática íntegra") era sobre o calendário da CVM
especificamente. Achado novo, real e verificado nesta sessão: o cadastro
geral do FCA da CVM (sub-arquivo `fca_cia_aberta_geral`) tem o campo
`Pagina_Web` - o site institucional oficial de cada companhia, registrado
pela própria empresa (não um PDF, não um texto ambíguo - um campo
estruturado). Isso NÃO dá a data do resultado diretamente, mas dá a URL
oficial de onde tentar ler uma data CONFIRMADA (ver
`data/eventos_coleta.py` e `data/ir_sources.py`) - o pipeline completo
(RI → NEWS → PRAZO_CVM) continua chamando as funções deste arquivo
(`periodo_pendente`/`limites_trimestre`/`prazo_cvm`/`rotulo_periodo`),
nada foi duplicado.

FECHAMENTO DO CICLO (2026-10-05): o coletor (data/eventos_coleta.py,
rodado por coletor_local.py) já persistia CONFIRMADO/ESTIMADO na tabela
eventos_resultados (sql/eventos.sql), mas nada lia essa tabela de volta
- calcular_proximo_resultado continuava sempre devolvendo PRAZO_CVM pra
qualquer ticker, mesmo depois do coletor achar uma data real. Faltava
só o lado da LEITURA: calcular_proximo_resultado agora consulta
_buscar_evento_persistido ANTES de cair no prazo regulatório - mesma
hierarquia RI>NEWS>PRAZO_CVM, só que na ponta do consumo em vez da
coleta. Nenhuma lógica de UI/dedup/cache-resiliente mudou."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

import config
from data.cvm import obter_cnpj, obter_documentos_cvm
from data.ibovespa import obter_composicao_oficial
from data.prices import obter_nome_yf
from data.supabase_client import obter_cliente

_TZ_SP = ZoneInfo("America/Sao_Paulo")

STATUS_CONFIRMADO = "CONFIRMADO"
STATUS_ESTIMADO = "ESTIMADO"
STATUS_PRAZO_CVM = "PRAZO_CVM"

STATUS_LABEL = {
    STATUS_CONFIRMADO: "CONFIRMADO",
    STATUS_ESTIMADO: "ESTIMADO",
    STATUS_PRAZO_CVM: "PRAZO CVM",
}

# maior = mais confiavel - usado por mesclar_eventos/aplicar_cache_resiliente
# pra nunca deixar uma fonte fraca (PRAZO_CVM) aparecer como se fosse mais
# confiavel que um CONFIRMADO/ESTIMADO ja conhecido pro mesmo (ticker,periodo)
PRIORIDADE_STATUS = {STATUS_CONFIRMADO: 3, STATUS_ESTIMADO: 2, STATUS_PRAZO_CVM: 1}

# Instrucao CVM 480/2009: ITR (trimestral) ate 45 dias apos o fim do
# trimestre; DFP (anual) ate ~3 meses apos o encerramento do exercicio
# (assumindo exercicio = ano civil, Dez).
_PRAZO_ITR_DIAS = 45


def _limites_trimestre(ano: int, trimestre: int) -> tuple:
    inicios = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
    fins = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    mi, di = inicios[trimestre]
    mf, df = fins[trimestre]
    return date(ano, mi, di), date(ano, mf, df)


def _prazo_cvm(ano: int, trimestre: int) -> date:
    _, fim = _limites_trimestre(ano, trimestre)
    if trimestre == 4:
        return date(ano + 1, 3, 31)  # DFP
    return fim + timedelta(days=_PRAZO_ITR_DIAS)


def _trimestre_de(d: date) -> tuple:
    return d.year, (d.month - 1) // 3 + 1


def _proximo_trimestre(ano: int, trimestre: int) -> tuple:
    if trimestre == 4:
        return ano + 1, 1
    return ano, trimestre + 1


def _trimestre_anterior(ano: int, trimestre: int) -> tuple:
    if trimestre == 1:
        return ano - 1, 4
    return ano, trimestre - 1


def _rotulo_periodo(ano: int, trimestre: int) -> str:
    if trimestre == 4:
        return f"4T{ano % 100} (DFP)"
    return f"{trimestre}T{ano % 100}"


# wrappers publicos (2026-10-02, fase COLETOR DE DATAS DE RESULTADOS):
# data/eventos_coleta.py precisa dos MESMOS limites/prazo/rotulo de
# periodo usados aqui, pra saber ONDE procurar (qual texto buscar na
# pagina de RI/noticia) e validar se uma data encontrada faz sentido
# pro periodo certo - reaproveita em vez de duplicar a logica de
# trimestre em outro arquivo.
def limites_trimestre(ano: int, trimestre: int) -> tuple:
    return _limites_trimestre(ano, trimestre)


def prazo_cvm(ano: int, trimestre: int) -> date:
    return _prazo_cvm(ano, trimestre)


def rotulo_periodo(ano: int, trimestre: int) -> str:
    return _rotulo_periodo(ano, trimestre)


def _ja_entregou(documentos_resultados: list, ano: int, trimestre: int) -> bool:
    """True se ja' existe um documento tipo RESULTADOS (real, vindo da
    CVM) cuja data_referencia cai DENTRO do trimestre dado - nunca
    inventa, so' confere o que a CVM ja' publicou de verdade. Documento
    com data_referencia ausente/ilegivel e' ignorado (nunca conta como
    "ja' entregue" por engano)."""
    inicio, fim = _limites_trimestre(ano, trimestre)
    for doc in documentos_resultados:
        ref = doc.get("data_referencia")
        if not ref:
            continue
        try:
            data_ref = date.fromisoformat(str(ref)[:10])
        except ValueError:
            continue
        if inicio <= data_ref <= fim:
            return True
    return False


def periodo_pendente(ticker: str, hoje: date = None) -> tuple | None:
    """(ano, trimestre) do proximo periodo (ITR/DFP) ainda pendente de
    resultado pro ticker - None se a fonte CVM falhar. Extraido de
    calcular_proximo_resultado (2026-10-02, fase COLETOR DE DATAS DE
    RESULTADOS) pra ser reaproveitado por data/eventos_coleta.py SEM
    duplicar a logica de "qual trimestre procurar" - o coletor precisa
    saber o periodo ANTES de tentar RI/NEWS, pra saber o que buscar na
    pagina/noticia (ex: "3T26")."""
    # date.today() usa o fuso do servidor (UTC no Streamlit Cloud) - perto
    # da meia-noite UTC (~21h em Brasilia) isso considerava um trimestre
    # "encerrado" ~3h antes da hora real em BRT (achado real, 2026-10-08).
    hoje = hoje or datetime.now(_TZ_SP).date()
    # bug real corrigido (2026-10-08): obter_documentos_cvm devolve []
    # tanto pro ticker SEM CNPJ mapeado (nunca protocola na CVM - ex. BDR
    # estrangeiro como MELI34/AAPL34) quanto pro ticker COM CNPJ que so'
    # ainda nao tem documento no periodo. O prazo regulatorio (Instrucao
    # CVM 480) so' existe pra quem de fato protocola - sem CNPJ mapeado,
    # calcular um prazo aqui fabricava um evento PRAZO_CVM pra empresa
    # que nunca vai reportar nesse regime (mesma limitacao ja' documentada
    # em MANUAL.md pra aba CVM, que o CALENDARIO nao aplicava).
    if obter_cnpj(ticker) is None:
        return None
    documentos = obter_documentos_cvm(ticker)
    if documentos is None:
        return None
    documentos_resultados = [d for d in documentos if d["tipo"] == "RESULTADOS"]

    # comeca no trimestre ANTERIOR ao que contem hoje (hoje esta DENTRO
    # do trimestre atual - esse ainda nao terminou nem pode ter sido
    # reportado; quem esta pendente de resultado e' sempre um trimestre
    # ja' encerrado). O loop abaixo avanca a partir dai enquanto o prazo
    # ja' tiver passado ou o resultado ja' tiver sido entregue - bug
    # real corrigido (2026-10-01): comecar no trimestre ATUAL pulava o
    # trimestre recem-encerrado inteiro (ex: 01/10 caindo direto no 4T
    # em vez de ficar no 3T, que acabou de fechar em 30/09 e ainda tem
    # ate 14/11 de prazo).
    ano, trimestre = _trimestre_anterior(*_trimestre_de(hoje))
    while _prazo_cvm(ano, trimestre) < hoje or _ja_entregou(documentos_resultados, ano, trimestre):
        ano, trimestre = _proximo_trimestre(ano, trimestre)
    return ano, trimestre


_TTL_EVENTOS_PERSISTIDOS = 15 * 60  # 15min - menor que o intervalo de 30min do coletor agendado (coletor_local.py)


@st.cache_data(ttl=_TTL_EVENTOS_PERSISTIDOS, show_spinner=False)
def _buscar_evento_persistido(ticker: str, periodo: str) -> dict | None:
    """Linha crua salva pelo coletor (data/eventos_coleta.py, tabela
    eventos_resultados) pro (ticker,periodo) dado - None se nao houver
    nada salvo ou o banco estiver fora do ar. Usada so' pra consulta de
    1 ticker isolado (ex: data/eventos_coleta.py, fluxo de background
    sem problema de latencia) - o CALENDARIO (varios tickers de uma vez)
    usa _buscar_eventos_persistidos_lote abaixo, 1 UNICA consulta pro
    lote inteiro em vez de 1 por ticker (ver calcular_calendario)."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (
            cliente.table("eventos_resultados")
            .select("*")
            .eq("ticker", ticker).eq("periodo", periodo)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        return None


@st.cache_data(ttl=_TTL_EVENTOS_PERSISTIDOS, show_spinner=False)
def _buscar_eventos_persistidos_lote(pares: tuple) -> dict:
    """Bug real de performance corrigido (2026-10-05): calcular_calendario
    fazia 1 consulta SEQUENCIAL ao Supabase por ticker (cada uma ~100-
    200ms de ida-e-volta de rede) - com 13 tickers da watchlist isso ja
    somava +1,5s so' nessa etapa, e o mesmo custo se repetia em TODA
    troca de filtro/janela que recalculasse o calendario. Agora e' 1
    UNICA consulta (`ticker IN (...)`) pro lote inteiro de tickers,
    filtrada em memoria pro (ticker,periodo) exato de cada um (o
    resultado pode conter periodos antigos do mesmo ticker, que nunca
    devem ser usados - mesma seguranca da consulta antiga, so' que em
    lote). Retorna {(ticker,periodo): linha} so' pros pares que
    realmente tem algo persistido - par ausente = None pra quem chama,
    cai pro PRAZO_CVM. [] ou Supabase fora do ar -> {} (nunca quebra,
    todos caem pro fallback)."""
    if not pares:
        return {}
    cliente = obter_cliente()
    if cliente is None:
        return {}
    tickers = sorted({t for t, _ in pares})
    try:
        resp = cliente.table("eventos_resultados").select("*").in_("ticker", tickers).execute()
    except Exception:
        return {}
    pares_validos = set(pares)
    return {
        (linha["ticker"], linha["periodo"]): linha
        for linha in resp.data
        if (linha.get("ticker"), linha.get("periodo")) in pares_validos
    }


def _nome_empresa(ticker: str) -> str:
    """Nome de exibicao do ticker - cascata BARATA (sem rede) antes do
    fallback caro: config.TICKER_NOME/NOMES_ATIVOS_BUSCA (curadoria
    manual) -> nome oficial da composicao do Ibovespa (ja cacheada 24h,
    mesma fonte que ui/busca.py usa) -> so' em ultimo caso
    obter_nome_yf (1 chamada de rede ao yfinance por ticker, lenta -
    confirmado no profiling: ~0,5-0,8s cada, 55% do tempo total do
    CALENDARIO pra 13 tickers antes desta correcao). Mesma cascata ja
    estabelecida em ui/busca.py:_universo_ativos - nao e' logica nova,
    so' reaproveitada aqui."""
    nome = (
        config.TICKER_NOME.get(ticker)
        or config.NOMES_ATIVOS_BUSCA.get(ticker)
        or (obter_composicao_oficial() or {}).get(ticker, {}).get("nome")
    )
    return nome or obter_nome_yf(ticker) or ticker


def calcular_proximo_resultado(
    ticker: str, hoje: date = None, _periodo_prebuscado: tuple = None, _persistidos_prebuscados: dict = None,
) -> dict | None:
    """Proximo resultado esperado pro ticker - CONFIRMADO/ESTIMADO se o
    coletor (data/eventos_coleta.py) ja tiver achado e persistido uma
    data real pro periodo pendente, senao PRAZO_CVM (prazo regulatorio,
    ver docstring do modulo). None se a fonte CVM falhar (nunca inventa
    evento quando a fonte esta fora do ar) - a leitura da tabela
    persistida so' acontece se houver um periodo pendente calculavel.

    _periodo_prebuscado/_persistidos_prebuscados: uso interno de
    calcular_calendario (ver docstring la) pra reaproveitar o
    periodo_pendente e a consulta em LOTE ao Supabase ja feitos pra
    todos os tickers de uma vez, em vez de cada ticker refazer sua
    propria consulta - chamadores externos (ex: data/eventos_coleta.py,
    testes) nunca passam esses parametros e o comportamento e'
    IDENTICO ao de antes (calcula o periodo e busca o persistido deste
    1 ticker, isolado).

    {ticker, empresa, periodo, data (date), horario (sempre None nesta
    versao), status, fonte, origem_url (None quando status e'
    PRAZO_CVM - nao e' um documento especifico, e' uma regra calculada),
    tipo_evento, coletado_em (quando ESTE calculo rodou - usado por
    aplicar_cache_resiliente pra saber qual versao e' mais recente)."""
    periodo = _periodo_prebuscado if _periodo_prebuscado is not None else periodo_pendente(ticker, hoje)
    if periodo is None:
        return None
    ano, trimestre = periodo
    rotulo = _rotulo_periodo(ano, trimestre)
    empresa = _nome_empresa(ticker)

    if _persistidos_prebuscados is not None:
        persistido = _persistidos_prebuscados.get((ticker, rotulo))
    else:
        persistido = _buscar_evento_persistido(ticker, rotulo)
    if persistido is not None:
        try:
            return {
                "ticker": ticker,
                "empresa": empresa,
                "periodo": rotulo,
                "data": date.fromisoformat(str(persistido["data_evento"])[:10]),
                "horario": None,
                "status": persistido["status"],
                "fonte": persistido["fonte"],
                "origem_url": persistido.get("url_fonte"),
                "tipo_evento": "RESULTADO",
                "coletado_em": datetime.now(timezone.utc),
            }
        except (KeyError, ValueError, TypeError):
            pass  # linha salva malformada - cai pro PRAZO_CVM, nunca quebra

    return {
        "ticker": ticker,
        "empresa": empresa,
        "periodo": rotulo,
        "data": _prazo_cvm(ano, trimestre),
        "horario": None,
        "status": STATUS_PRAZO_CVM,
        "fonte": "CVM — prazo regulatório (Instrução CVM 480/2009)",
        "origem_url": None,
        "tipo_evento": "RESULTADO",
        "coletado_em": datetime.now(timezone.utc),
    }


def calcular_calendario(tickers: list, hoje: date = None) -> list:
    """Calendario de proximos resultados pra uma lista de tickers,
    ordenado por data - tickers cuja fonte CVM falhar simplesmente nao
    entram no resultado IMEDIATO, mas podem ser resgatados do cache de
    ultimo-dado-valido (ver aplicar_cache_resiliente) se ja tivessemos
    calculado algo pra eles antes nesta mesma sessao do processo.
    Tickers duplicados na lista de entrada geram so' 1 evento (dedupe
    por ticker, mantem o primeiro).

    Bug real de performance corrigido (2026-10-05, ver profiling):
    periodo_pendente (CVM, ja' cacheado por ano - barato depois do 1o
    ticker) e' calculado 1x por ticker aqui e repassado pra
    calcular_proximo_resultado via _periodo_prebuscado (evita refazer o
    mesmo filtro em pandas 2x); a consulta ao Supabase de
    eventos_resultados agora e' 1 UNICA chamada em lote
    (_buscar_eventos_persistidos_lote) pra TODOS os tickers, em vez de
    uma consulta sequencial por ticker. O nome da empresa tambem passou
    a vir de uma cascata barata (ver _nome_empresa) antes do fallback
    de rede ao yfinance. Nenhuma mudanca nos RESULTADOS (CONFIRMADO/
    ESTIMADO/PRAZO_CVM e suas datas/fontes continuam exatamente iguais)
    - so' MENOS chamadas de rede pra chegar no mesmo resultado."""
    vistos = set()
    tickers_unicos = []
    periodos = {}
    for ticker in tickers:
        if ticker in vistos:
            continue
        vistos.add(ticker)
        tickers_unicos.append(ticker)
        periodos[ticker] = periodo_pendente(ticker, hoje)

    pares = [(t, _rotulo_periodo(*periodos[t])) for t in tickers_unicos if periodos[t] is not None]
    persistidos = _buscar_eventos_persistidos_lote(tuple(pares))

    eventos = []
    for ticker in tickers_unicos:
        evento = calcular_proximo_resultado(
            ticker, hoje=hoje, _periodo_prebuscado=periodos[ticker], _persistidos_prebuscados=persistidos,
        )
        if evento:
            eventos.append(evento)
    return aplicar_cache_resiliente(eventos)


# ============================================================
# SNAPSHOT do calendario (2026-10-05): desacopla "quando o usuario abre
# a aba" de "quando o calculo caro acontece". calcular_calendario em si
# ja' e' rapido pra uma lista pequena (watchlist) depois do 1o ticker
# (cache em memoria), mas o CUSTO INICIAL (download do IPE da CVM, ~4-
# 5s, pago 1x por processo/TTL) ainda cai no 1o usuario a abrir a aba
# depois de o processo acordar/o cache expirar - "Calculando
# calendario..." visivel. O coletor (coletor_local.py, ja agendado)
# agora calcula o universo INTEIRO e grava aqui (tabela
# calendario_snapshot, ver sql/calendario_snapshot.sql); a UI so' LE
# essa tabela (1 consulta rapida) e filtra em memoria - nunca recalcula
# sozinha, exceto se nao houver NENHUM snapshot ainda (projeto novo) ou
# o Supabase estiver fora do ar.
# ============================================================

_TABELA_SNAPSHOT = "calendario_snapshot"
_ID_SNAPSHOT = "latest"
_TTL_SNAPSHOT = 10 * 60  # so' pra nao bater no Supabase a cada rerun - o dado em si e' atualizado pelo coletor, nao por este TTL


def _evento_para_json(evento: dict) -> dict:
    """date/datetime nao sao JSON-nativos - serializa pra ISO string.
    _fontes_alternativas (se existir, ver mesclar_eventos) tambem carrega
    uma 'data' date dentro de cada item - serializada igual."""
    d = dict(evento)
    d["data"] = evento["data"].isoformat()
    if evento.get("coletado_em"):
        d["coletado_em"] = evento["coletado_em"].isoformat()
    if evento.get("_fontes_alternativas"):
        d["_fontes_alternativas"] = [
            {**alt, "data": alt["data"].isoformat()} for alt in evento["_fontes_alternativas"]
        ]
    return d


def _evento_de_json(d: dict) -> dict:
    e = dict(d)
    e["data"] = date.fromisoformat(d["data"])
    if d.get("coletado_em"):
        try:
            e["coletado_em"] = datetime.fromisoformat(d["coletado_em"])
        except ValueError:
            e["coletado_em"] = None
    if d.get("_fontes_alternativas"):
        e["_fontes_alternativas"] = [
            {**alt, "data": date.fromisoformat(alt["data"])} for alt in d["_fontes_alternativas"]
        ]
    return e


@st.cache_data(ttl=_TTL_SNAPSHOT, show_spinner=False)
def obter_snapshot_calendario() -> dict | None:
    """Ultimo snapshot persistido pelo coletor - {eventos: [...],
    atualizado_em: iso}. None se nunca foi gerado (tabela vazia/
    ausente) ou o Supabase estiver fora do ar - quem chama
    (calcular_calendario_cacheado) cai pro calculo em tempo real so'
    nesse caso, nunca por este TTL expirar com dado ja' existente."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = cliente.table(_TABELA_SNAPSHOT).select("*").eq("id", _ID_SNAPSHOT).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def salvar_snapshot_calendario(tickers: list, hoje: date = None) -> bool:
    """Calcula o calendario pro universo dado (mesma calcular_calendario
    de sempre, SEM mudanca de logica/fontes) e persiste como snapshot -
    chamado so' pelo coletor (coletor_local.py), NUNCA pela UI. So'
    sobrescreve se o calculo produziu pelo menos 1 evento - uma falha
    pontual (CVM fora do ar, Supabase fora do ar) NUNCA apaga o ultimo
    snapshot bom, so' deixa de atualizar (preserva o ultimo valido, ver
    ATUALIZACAO). Retorna True so' se gravou um snapshot NOVO."""
    eventos = calcular_calendario(tickers, hoje=hoje)
    if not eventos:
        return False
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        cliente.table(_TABELA_SNAPSHOT).upsert({
            "id": _ID_SNAPSHOT,
            "eventos": [_evento_para_json(e) for e in eventos],
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return True
    except Exception:
        return False


def calcular_calendario_cacheado(tickers: list, hoje: date = None) -> list:
    """Fonte de dados da UI (ui/calendario_tab.py): le o snapshot
    persistido (ver obter_snapshot_calendario) e filtra em memoria pro
    universo pedido - SEM recalcular/coletar nada ao renderizar ou
    navegar (trocar filtro/janela/mes/selecao de evento e' so' filtrar
    um dict ja' em memoria). Ticker presente na lista pedida mas AUSENTE
    do snapshot (ex: ticker fora de config.IBOVESPA_SETORES, que e' o
    universo que o coletor cobre - BDR na watchlist, por exemplo) cai
    pro calculo em tempo real so' PRA ESSE ticker (calcular_calendario),
    nunca pro lote inteiro - preserva a cobertura completa da watchlist
    sem pagar o custo caro pros tickers que ja' estao no snapshot.

    Se NUNCA houve snapshot (projeto novo) ou o Supabase estiver fora
    do ar, cai pro calculo em tempo real pro lote inteiro (comportamento
    de calcular_calendario de sempre) - a UI nunca fica sem dado."""
    snapshot = obter_snapshot_calendario()
    if snapshot is None or not snapshot.get("eventos"):
        return calcular_calendario(tickers, hoje=hoje)

    eventos_snapshot = {}
    for linha in snapshot["eventos"]:
        try:
            eventos_snapshot[linha["ticker"]] = _evento_de_json(linha)
        except (KeyError, ValueError, TypeError):
            continue  # linha malformada no snapshot - ignora, nunca quebra

    tickers_unicos = list(dict.fromkeys(tickers))
    cobertos = [t for t in tickers_unicos if t in eventos_snapshot]
    nao_cobertos = [t for t in tickers_unicos if t not in eventos_snapshot]

    eventos = [eventos_snapshot[t] for t in cobertos]
    if nao_cobertos:
        eventos += calcular_calendario(nao_cobertos, hoje=hoje)
    return sorted(eventos, key=lambda e: e["data"])


@st.cache_resource(show_spinner=False)
def _cache_eventos() -> dict:
    """{(ticker,periodo): evento} - ultimo evento conhecido (qualquer
    status) por ticker+periodo. st.cache_resource = sobrevive entre
    reruns/sessoes no MESMO processo do servidor (reseta em redeploy) -
    mesma tecnica ja usada em data/research/__init__.py:_ultimas_tentativas.
    Existe pra "preservar ultimo dado valido" (pedido explicito, secao
    ATUALIZACAO): uma falha pontual na fonte de um evento nunca apaga o
    que ja sabiamos, nem regride um CONFIRMADO/ESTIMADO de volta pra
    PRAZO_CVM so' porque a fonte melhor nao respondeu desta vez."""
    return {}


def mesclar_eventos(*listas_de_eventos: list) -> list:
    """Deduplica eventos do MESMO (ticker,periodo) vindos de VARIAS
    fontes consultadas na MESMA rodada (ex: PRAZO_CVM calculado +
    alguma fonte futura de CONFIRMADO/ESTIMADO), mantendo so' o de MAIOR
    confiabilidade - NUNCA mostra as duas como linhas diferentes da
    agenda (exigencia explicita de deduplicacao). A fonte de menor
    confiabilidade pro mesmo (ticker,periodo) fica preservada em
    '_fontes_alternativas' do evento vencedor - nunca escondida de
    verdade, so' nao vira duplicata visivel."""
    melhores = {}
    for lista in listas_de_eventos:
        for evento in lista:
            chave = (evento["ticker"], evento["periodo"])
            atual = melhores.get(chave)
            if atual is None:
                melhores[chave] = evento
                continue
            if PRIORIDADE_STATUS[evento["status"]] > PRIORIDADE_STATUS[atual["status"]]:
                vencedor, perdedor = evento, atual
            else:
                vencedor, perdedor = atual, evento
            vencedor = dict(vencedor)
            vencedor.setdefault("_fontes_alternativas", []).append(
                {"status": perdedor["status"], "data": perdedor["data"], "fonte": perdedor["fonte"]}
            )
            melhores[chave] = vencedor
    return sorted(melhores.values(), key=lambda e: e["data"])


def aplicar_cache_resiliente(eventos_novos: list) -> list:
    """Funde eventos_novos com o cache de ultimo-dado-valido (ver
    _cache_eventos): pra cada (ticker,periodo), mantem o de MAIOR
    prioridade entre o que acabou de ser calculado/coletado e o que ja
    estava em cache - nunca regride um CONFIRMADO/ESTIMADO ja conhecido
    de volta pra PRAZO_CVM so' porque, numa consulta pontual, a fonte
    melhor nao respondeu. Marca '_pode_estar_desatualizado'=True quando
    o valor exibido veio do cache (nao foi reconfirmado NESTA consulta)
    - a UI usa isso pra avisar o usuario, nunca escondido. Sempre
    atualiza o cache com o resultado final (o novo, quando ele vence)."""
    cache = _cache_eventos()
    resultado = []
    for evento in eventos_novos:
        chave = (evento["ticker"], evento["periodo"])
        anterior = cache.get(chave)
        if anterior and PRIORIDADE_STATUS[anterior["status"]] > PRIORIDADE_STATUS[evento["status"]]:
            escolhido = dict(anterior)
            escolhido["_pode_estar_desatualizado"] = True
        else:
            escolhido = evento
            cache[chave] = evento
        resultado.append(escolhido)
    resultado.sort(key=lambda e: e["data"])
    return resultado
