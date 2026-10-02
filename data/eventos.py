# -*- coding: utf-8 -*-
"""Camada normalizada de eventos financeiros (CALENDÁRIO, 2026-10-01).
V1: só resultados corporativos (ITR/DFP trimestral/anual). Pensada pra
no futuro relacionar CVM <-> Research <-> News <-> Ticker <-> Preço
(cada evento já carrega 'ticker' - mesmo identificador usado em todo o
resto do projeto) - mas essa integração completa NÃO é feita nesta fase.

Reaproveita data.cvm.obter_documentos_cvm (mesmo identificador/coleta/
cache que a aba CVM já usa) - nenhum sistema de dado novo, nenhuma
chamada de IA.

FONTE REAL DISPONÍVEL HOJE: só o PRAZO REGULATÓRIO da CVM pra entrega
do ITR/DFP (Instrução CVM 480/2009, Art. 25/29) - prazo MÁXIMO legal,
não é uma data anunciada pela empresa. É dado público, documentado,
determinístico - não é um valor inventado. Por isso, nesta primeira
versão, todo evento calculado tem status PRAZO_CVM: não existe hoje
nenhuma fonte automática íntegra de data CONFIRMADA (anunciada pela
própria empresa, ex: um "Calendário de Eventos Corporativos" da CVM
com data explícita dentro do PDF) nem ESTIMADA (fonte não-oficial) já
integrada ao projeto. Extrair isso de PDF exigiria parsing de texto
livre sem IA (risco real de ler a data errada e apresentá-la como se
fosse oficial) - decisão deliberada de NÃO fazer isso nesta fase (ver
PROGRESSO.md). O campo `status` já está pronto pra CONFIRMADO/ESTIMADO
quando/se uma fonte confiável for integrada depois.

LIMITAÇÃO DOCUMENTADA: assume ano fiscal = ano civil (padrão da grande
maioria das empresas B3) - empresas com ano fiscal diferente não têm o
prazo calculado corretamente nesta v1."""

from datetime import date, timedelta

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
    v1 - CVM nao informa horario), status, fonte, origem_url (sempre
    None - nao e' um documento especifico, e' uma regra calculada),
    tipo_evento}."""
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
    }


def calcular_calendario(tickers: list, hoje: date = None) -> list:
    """Calendario de proximos resultados pra uma lista de tickers,
    ordenado por data - tickers cuja fonte CVM falhar simplesmente nao
    entram (nunca quebra o calendario inteiro por causa de 1 ticker).
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
    eventos.sort(key=lambda e: e["data"])
    return eventos
