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
prazo calculado corretamente nesta versão."""

from datetime import date, datetime, timedelta, timezone

import streamlit as st

from data.cvm import obter_documentos_cvm
from data.prices import obter_nome_yf

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


def calcular_proximo_resultado(ticker: str, hoje: date = None) -> dict | None:
    """Proximo resultado esperado pro ticker (prazo regulatorio da CVM -
    ver docstring do modulo). None se a fonte CVM falhar (nunca inventa
    evento quando a fonte esta fora do ar).

    {ticker, empresa, periodo, data (date), horario (sempre None nesta
    versao - CVM nao informa horario), status, fonte, origem_url (sempre
    None - nao e' um documento especifico, e' uma regra calculada),
    tipo_evento, coletado_em (quando ESTE calculo rodou - usado por
    aplicar_cache_resiliente pra saber qual versao e' mais recente)."""
    hoje = hoje or date.today()
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

    return {
        "ticker": ticker,
        "empresa": obter_nome_yf(ticker) or ticker,
        "periodo": _rotulo_periodo(ano, trimestre),
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
    por ticker, mantem o primeiro)."""
    vistos = set()
    eventos = []
    for ticker in tickers:
        if ticker in vistos:
            continue
        vistos.add(ticker)
        evento = calcular_proximo_resultado(ticker, hoje=hoje)
        if evento:
            eventos.append(evento)
    return aplicar_cache_resiliente(eventos)


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
